import socket
import threading
import unittest

from lms_gate import (GateUnavailable, LmsPerformanceGate, NullGate, build_gate,
                      parse_song_start)


class FakeClient:
    """LMS stand-in. `tracks` maps player id -> {'mode','index','time'}; tests mutate it live."""

    def __init__(self, tracks=None, fail=False):
        self.tracks = tracks or {}
        self.fail = fail
        self.calls = []
        self.lock = threading.Lock()
        self.server, self.sock = socket.socketpair()

    def close(self):
        self.server.close()
        self.sock.close()

    def open_subscription(self):
        if self.fail:
            raise GateUnavailable('down')
        return self.sock

    def playing_players(self):
        with self.lock:
            return [p for p, t in self.tracks.items() if t['mode'] == 'play']

    def track_state(self, pid):
        with self.lock:
            return dict(self.tracks.get(pid, {'mode': 'stop', 'index': None, 'time': 0.0}))

    def set(self, pid, **kw):
        with self.lock:
            self.tracks.setdefault(pid, {'mode': 'stop', 'index': 0, 'time': 0.0}).update(kw)

    def stop(self, pid):
        self.calls.append(('stop', pid))
        self.set(pid, mode='stop')

    def play(self, pid):
        self.calls.append(('play', pid))


def playing(index=0, time=30.0):
    return {'mode': 'play', 'index': index, 'time': time}


class ParseTest(unittest.TestCase):
    def test_song_start_events(self):
        self.assertEqual(parse_song_start('aa:bb playlist newsong 5'), 'aa:bb')
        self.assertEqual(parse_song_start('aa%3Abb playlist open file%3A%2F%2Fx.mp3'), 'aa:bb')
        self.assertEqual(parse_song_start('aa:bb playlist pause 0'), 'aa:bb')
        self.assertIsNone(parse_song_start('aa:bb playlist pause 1'))
        self.assertIsNone(parse_song_start('aa:bb playlist stop'))
        self.assertIsNone(parse_song_start('aa:bb mixer volume 5'))
        self.assertIsNone(parse_song_start('subscribe playlist'))


class GateTest(unittest.TestCase):
    def client(self, **kw):
        c = FakeClient(**kw)
        self.addCleanup(c.close)
        return c

    def gate(self, client, **kw):
        g = LmsPerformanceGate(client, poll_s=0.02, **kw)
        self.addCleanup(g.release)
        return g

    def later(self, delay, fn):
        t = threading.Timer(delay, fn)
        t.start()
        self.addCleanup(t.cancel)

    def test_gate_modes(self):
        self.assertIsInstance(build_gate(1, None), NullGate)
        self.assertIsInstance(build_gate(4, {'host': 'x'}), LmsPerformanceGate)
        self.assertIsInstance(build_gate(5, {'host': 'x'}), LmsPerformanceGate)
        for n in (4, 5):
            with self.assertRaises(GateUnavailable):
                build_gate(n, {})

    def test_song_first_no_wait_refuses(self):
        client = self.client(tracks={'p1': playing()})
        gate = self.gate(client)
        self.assertFalse(gate.acquire(0))
        self.assertEqual(gate._state, 'idle')
        self.assertEqual(client.calls, [])

    def test_song_first_polly_waits_for_song_to_end(self):
        client = self.client(tracks={'p1': playing()})
        gate = self.gate(client)
        self.later(0.15, lambda: client.set('p1', mode='stop'))
        self.assertTrue(gate.acquire(5))
        gate.release()
        self.assertEqual(client.calls, [])

    def test_song_first_next_track_is_held_behind_polly(self):
        client = self.client(tracks={'p1': playing(index=0, time=100.0)})
        gate = self.gate(client)
        self.later(0.15, lambda: client.set('p1', index=1, time=0.2))
        self.assertTrue(gate.acquire(5))
        self.assertEqual(client.calls, [('stop', 'p1')])
        gate.release()
        self.assertEqual(client.calls, [('stop', 'p1'), ('play', 'p1')])

    def test_repeat_one_restart_detected_by_time_reset(self):
        client = self.client(tracks={'p1': playing(index=0, time=100.0)})
        gate = self.gate(client)
        self.later(0.15, lambda: client.set('p1', time=0.1))
        self.assertTrue(gate.acquire(5))
        self.assertEqual(client.calls, [('stop', 'p1')])

    def test_same_song_progressing_keeps_polly_waiting(self):
        client = self.client(tracks={'p1': playing(index=0, time=10.0)})
        gate = self.gate(client)
        self.assertFalse(gate.acquire(0.2))
        self.assertEqual(client.calls, [])

    def test_wait_timeout_restores_held_songs(self):
        client = self.client(tracks={'p1': playing(), 'p2': {'mode': 'stop', 'index': 0, 'time': 0.0}})
        gate = self.gate(client)

        def start_p2():
            client.set('p2', mode='play', time=0.1)
            client.server.sendall(b'p2 playlist newsong 1\n')
        self.later(0.05, start_p2)
        self.assertFalse(gate.acquire(0.4))
        self.assertIn(('stop', 'p2'), client.calls)
        self.assertEqual(client.calls[-1], ('play', 'p2'))

    def test_unrelated_player_does_not_block(self):
        gate = self.gate(self.client(tracks={'other': playing()}), player_ids=['p1'])
        self.assertTrue(gate.acquire(0))

    def test_lms_down_fails_closed(self):
        with self.assertRaises(GateUnavailable):
            self.gate(self.client(fail=True)).acquire(0)

    def test_no_double_acquire(self):
        gate = self.gate(self.client())
        self.assertTrue(gate.acquire(0))
        self.assertFalse(gate.acquire(0))

    def test_polly_first_song_is_held_until_release(self):
        client = self.client()
        gate = self.gate(client)
        self.assertTrue(gate.acquire(0))
        seen = threading.Event()
        original = gate.on_song_start

        def spy(pid):
            original(pid)
            seen.set()
        gate.on_song_start = spy
        client.set('p1', mode='play', time=0.1)
        client.server.sendall(b'p1 playlist newsong 3\np1 playlist newsong 3\n')
        self.assertTrue(seen.wait(2))
        self.assertEqual(client.calls, [('stop', 'p1')])
        gate.release()
        self.assertEqual(client.calls, [('stop', 'p1'), ('play', 'p1')])

    def test_stale_event_for_idle_player_is_not_restarted(self):
        client = self.client()
        gate = self.gate(client)
        self.assertTrue(gate.acquire(0))
        gate.on_song_start('p1')
        gate.release()
        self.assertEqual(client.calls, [])

    def test_polly_own_player_is_ignored(self):
        client = self.client(tracks={'polly': playing()})
        gate = self.gate(client, exclude_ids=['polly'])
        self.assertTrue(gate.acquire(0))
        gate.on_song_start('polly')
        gate.release()
        self.assertEqual(client.calls, [])

    def test_song_after_release_is_untouched(self):
        client = self.client()
        gate = self.gate(client)
        self.assertTrue(gate.acquire(0))
        gate.release()
        client.set('p1', mode='play')
        gate.on_song_start('p1')
        self.assertEqual(client.calls, [])


if __name__ == '__main__':
    unittest.main()
