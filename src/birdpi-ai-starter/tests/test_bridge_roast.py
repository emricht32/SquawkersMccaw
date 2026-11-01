import json
import os
import tempfile
import unittest
from unittest import mock

import birdpi_bridge
import chirp_engine
from birdpi_roles import RoutingError

CHIRP = {
    'id': 'polly_test_1', 'family_id': 'fam1', 'text': 'Nice shirt, did it come free with the haircut?',
    'speaker': 'polly', 'type': 'roast', 'required_tags': ['adult_mode', 'direct_insult'],
    'optional_tags': [], 'excluded_tags': [], 'tags': [], 'trigger': 'interaction',
    'audience': 'adults', 'min_age': 18,
}
META = {'duration': 1.0, 'singing_ranges': [[0.1, 0.3]], 'voice_model': 'en_GB-semaine-medium', 'speaker_id': 3}


class Gate:
    kind = 'fake'

    def __init__(self, allow=True):
        self.allow, self.released, self.waits = allow, False, []

    def acquire(self, max_wait_s=0.0):
        self.waits.append(max_wait_s)
        return self.allow

    def release(self):
        self.released = True


class Performer:
    def __init__(self, played=True):
        self.played, self.calls = played, 0

    def perform(self, wav, ranges, duration, abort=None):
        self.calls += 1
        return {'played': self.played, 'beak': 'gpio', 'aborted': False}


class BridgeRoastTest(unittest.TestCase):
    def setUp(self):
        self.old = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        lib = os.path.join(self.tmp.name, 'lib.json')
        with open(lib, 'w') as f:
            json.dump({'chirps': [CHIRP]}, f)
        self.db = os.path.join(self.tmp.name, 'c.sqlite')
        chirp_engine.import_file(chirp_engine.connect(self.db), lib)
        patcher = mock.patch.object(chirp_engine, 'render', return_value=(b'RIFF', META, 'k'))
        self.render = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def plays(self):
        return chirp_engine.connect(self.db).execute('SELECT COUNT(*) FROM plays').fetchone()[0]

    def run_roast(self, gate, performer, count=4, play=True, tags='adult_mode,direct_insult', wait=0.0):
        return birdpi_bridge.roast(count, self.db, tags, ['g1'], 's1', 'http://x', play, gate, performer, wait)

    def test_queue_wait_is_passed_to_gate(self):
        gate = Gate()
        self.run_roast(gate, Performer(), wait=120.0)
        self.assertEqual(gate.waits, [120.0])

    def test_requires_adult_mode_and_challenge(self):
        for tags in ('adult_mode', 'direct_insult', 'adult_mode,red_shirt'):
            with self.assertRaises(RoutingError):
                self.run_roast(Gate(), Performer(), tags=tags)

    def test_preview_never_performs_or_records(self):
        perf = Performer()
        result = self.run_roast(Gate(), perf, play=False)
        self.assertFalse(result['recorded'])
        self.assertEqual(perf.calls, 0)
        self.render.assert_not_called()

    def test_song_playing_blocks_and_does_not_record(self):
        perf = Performer()
        result = self.run_roast(Gate(allow=False), perf)
        self.assertEqual(result['reason'], 'song_playing')
        self.assertEqual(perf.calls, 0)
        self.assertEqual(self.plays(), 0)

    def test_success_records_and_releases_gate(self):
        gate = Gate()
        result = self.run_roast(gate, Performer())
        self.assertTrue(result['played'] and result['recorded'])
        self.assertTrue(gate.released)
        self.assertEqual(self.plays(), 1)
        self.assertEqual(result['audio_cues']['speaker_id'], 3)

    def test_failed_playback_not_recorded(self):
        gate = Gate()
        result = self.run_roast(gate, Performer(played=False))
        self.assertFalse(result['recorded'])
        self.assertTrue(gate.released)
        self.assertEqual(self.plays(), 0)

    def test_invalid_topologies_rejected(self):
        for n in (0, 2, 3, 6):
            with self.assertRaises(RoutingError):
                self.run_roast(Gate(), Performer(), count=n)


class ConfigTest(unittest.TestCase):
    def test_shipped_config_and_pins_load(self):
        cfg = birdpi_bridge.load_config(birdpi_bridge.BASE_DIR / 'config' / 'birdpi_topology.json')
        self.assertIn(cfg['bird_count'], (1, 4, 5))
        self.assertIn('beak', birdpi_bridge.load_pins(cfg))

    def test_bad_count_rejected(self):
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            json.dump({'bird_count': 3}, f)
        self.addCleanup(os.unlink, f.name)
        with self.assertRaises(RoutingError):
            birdpi_bridge.load_config(f.name)


if __name__ == '__main__':
    unittest.main()
