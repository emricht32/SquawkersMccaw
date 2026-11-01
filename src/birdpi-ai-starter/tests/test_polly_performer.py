import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from polly_performer import AplaySink, LmsSink, PollyPerformer, WavServer


class FakeLed:
    def __init__(self, log, name):
        self.log, self.name, self.closed = log, name, False

    def on(self):
        self.log.append((self.name, 'on'))

    def off(self):
        self.log.append((self.name, 'off'))

    def close(self):
        self.closed = True


class FakeBody:
    def __init__(self, log, beak=True):
        self.beak = FakeLed(log, 'beak') if beak else None
        self.body = FakeLed(log, 'body')
        self.lights = []


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


class FakePlayer:
    def __init__(self, clock, length, code=0, raise_at=None):
        self.clock, self.length, self.code, self.raise_at = clock, length, code, raise_at
        self.terminated = False

    def poll(self):
        if self.raise_at is not None and self.clock.t >= self.raise_at:
            raise RuntimeError('boom')
        return self.code if self.terminated or self.clock.t >= self.length else None

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.terminated = True


def make(log, clock, player, beak=True, **kw):
    sink = AplaySink(player_factory=lambda path: player, clock=clock)
    return PollyPerformer({}, sink, body_factory=lambda pins: FakeBody(log, beak),
                          clock=clock, sleep=clock.sleep, **kw)


class AplayPerformerTest(unittest.TestCase):
    def test_beak_follows_ranges_and_ends_closed(self):
        log, clock = [], FakeClock()
        result = make(log, clock, FakePlayer(clock, 1.0)).perform(b'RIFF', [[0.1, 0.2], [0.5, 0.6]], 1.0)
        self.assertTrue(result['played'])
        self.assertEqual(result['beak'], 'gpio')
        self.assertEqual(result['audio'], 'aplay')
        self.assertEqual(log.count(('beak', 'on')), 2)
        self.assertEqual(log[-2:], [('beak', 'off'), ('body', 'off')])

    def test_max_open_is_enforced(self):
        log, clock = [], FakeClock()
        make(log, clock, FakePlayer(clock, 2.0), max_open_s=0.3).perform(b'RIFF', [[0.0, 1.5]], 2.0)
        self.assertGreaterEqual(log.count(('beak', 'on')), 3)

    def test_abort_stops_and_not_played(self):
        log, clock = [], FakeClock()
        abort = threading.Event()
        abort.set()
        result = make(log, clock, FakePlayer(clock, 1.0)).perform(b'RIFF', [[0, 1]], 1.0, abort)
        self.assertFalse(result['played'])
        self.assertTrue(result['aborted'])

    def test_aplay_failure_not_played(self):
        log, clock = [], FakeClock()
        result = make(log, clock, FakePlayer(clock, 0.1, code=1)).perform(b'RIFF', [], 0.1)
        self.assertFalse(result['played'])
        self.assertIn('error', result)

    def test_beak_off_on_exception(self):
        log, clock = [], FakeClock()
        with self.assertRaises(RuntimeError):
            make(log, clock, FakePlayer(clock, 1.0, raise_at=0.15)).perform(b'RIFF', [[0.1, 0.5]], 1.0)
        self.assertEqual(log[-2], ('beak', 'off'))

    def test_hung_player_times_out(self):
        log, clock = [], FakeClock()
        result = make(log, clock, FakePlayer(clock, 99), timeout_margin_s=0.5).perform(b'RIFF', [], 0.2)
        self.assertTrue(result['aborted'])
        self.assertFalse(result['played'])

    def test_no_gpio_reports_unavailable(self):
        log, clock = [], FakeClock()
        result = make(log, clock, FakePlayer(clock, 0.1), beak=False).perform(b'RIFF', [[0, 0.1]], 0.1)
        self.assertEqual(result['beak'], 'unavailable')


class FakeLms:
    """Simulates LMS playing Polly's URL: starts after `latency`, runs for `length`."""

    def __init__(self, clock, length, latency=0.5, never_start=False, stop_at=None):
        self.clock, self.length, self.latency = clock, length, latency
        self.never_start, self.stop_at = never_start, stop_at
        self.calls = []
        self.started_at = None

    def play_url(self, pid, url, title):
        self.calls.append(('play_url', pid, url))
        self.started_at = self.clock.t + self.latency

    def status(self, pid):
        if self.never_start or self.clock.t < self.started_at:
            return 'stop', 0.0
        pos = self.clock.t - self.started_at
        if self.stop_at is not None and pos >= self.stop_at:
            return 'stop', 0.0
        return ('play', pos) if pos < self.length else ('stop', 0.0)

    def stop(self, pid):
        self.calls.append(('stop', pid))
        self.never_start = True


class FakeServer:
    def __init__(self, path, host, port):
        self.url = f'http://{host}/polly/x.wav'
        self.closed = False

    def shutdown(self):
        self.closed = True


def make_lms(log, clock, lms, **kw):
    servers = []

    def factory(*a):
        servers.append(FakeServer(*a))
        return servers[-1]
    sink = LmsSink(lms, 'polly-id', '10.0.0.5', clock=clock, server_factory=factory, **kw)
    perf = PollyPerformer({}, sink, body_factory=lambda pins: FakeBody(log), clock=clock, sleep=clock.sleep)
    return perf, servers


class LmsPerformerTest(unittest.TestCase):
    def test_beak_waits_for_lms_start_and_tracks_position(self):
        log, clock = [], FakeClock()
        lms = FakeLms(clock, length=1.0, latency=0.8)
        perf, servers = make_lms(log, clock, lms)
        on_times = []
        orig_on = FakeLed.on

        def spy(led):
            if led.name == 'beak':
                on_times.append(clock.t)
            orig_on(led)
        FakeLed.on = spy
        try:
            result = perf.perform(b'RIFF', [[0.1, 0.3]], 1.0)
        finally:
            FakeLed.on = orig_on
        self.assertTrue(result['played'])
        self.assertEqual(result['audio'], 'lms')
        self.assertEqual(lms.calls[0][:2], ('play_url', 'polly-id'))
        self.assertTrue(on_times and all(t >= 0.8 for t in on_times))
        self.assertTrue(servers[0].closed)
        self.assertEqual(log[-2:], [('beak', 'off'), ('body', 'off')])

    def test_lms_never_starts_fails_and_not_played(self):
        log, clock = [], FakeClock()
        perf, servers = make_lms(log, clock, FakeLms(clock, 1.0, never_start=True), start_timeout_s=1.0)
        result = perf.perform(b'RIFF', [[0, 1]], 1.0)
        self.assertFalse(result['played'])
        self.assertIn('did not start', result['error'])
        self.assertTrue(servers[0].closed)

    def test_stopped_early_is_not_played(self):
        log, clock = [], FakeClock()
        perf, _ = make_lms(log, clock, FakeLms(clock, 3.0, stop_at=0.6))
        result = perf.perform(b'RIFF', [], 3.0)
        self.assertFalse(result['played'])
        self.assertIn('early', result['error'])

    def test_abort_stops_lms_player(self):
        log, clock = [], FakeClock()
        lms = FakeLms(clock, 2.0)
        perf, _ = make_lms(log, clock, lms)
        abort = threading.Event()
        abort.set()
        result = perf.perform(b'RIFF', [], 2.0, abort)
        self.assertTrue(result['aborted'])
        self.assertIn(('stop', 'polly-id'), lms.calls)


class WavServerTest(unittest.TestCase):
    def test_serves_only_token_path(self):
        fd, path = tempfile.mkstemp(suffix='.wav')
        with os.fdopen(fd, 'wb') as f:
            f.write(b'RIFFdata')
        self.addCleanup(os.unlink, path)
        server = WavServer(path, '127.0.0.1')
        self.addCleanup(server.shutdown)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(server.url, timeout=2) as resp:
            self.assertEqual(resp.read(), b'RIFFdata')
            self.assertEqual(resp.headers['Content-Type'], 'audio/wav')
        base = server.url.rsplit('/', 1)[0]
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            opener.open(base + '/guess.wav', timeout=2)
        ctx.exception.close()
        self.assertEqual(ctx.exception.code, 404)


if __name__ == '__main__':
    unittest.main()
