import json
import unittest
from pathlib import Path

from song_requests import SongCatalog, find_lms_track, request_song
from voice_intents import parse_intent
from voice_service import VoiceService

SONGS = json.loads((Path(__file__).resolve().parents[3] / 'config_multi_song_with_triggers.json').read_text())['songs']


def catalog():
    return SongCatalog(SONGS)


def title(intent):
    return intent.song.get('display_name') or intent.song.get('name')


class IntentTest(unittest.TestCase):
    def test_roast_examples(self):
        cases = {
            'hey polly roast me': {'roast_request'},
            'fuck you polly': {'direct_insult'},
            "Fuck you, Polly!": {'direct_insult'},
            'polly want a cracker': {'roast_challenge', 'roast_request'},
            'polly give me your worst': {'roast_request'},
            'come at me polly': {'roast_challenge', 'roast_request'},
            'screw you polly': {'direct_insult'},
            'polly you asshole': {'direct_insult'},
        }
        for text, tags in cases.items():
            intent = parse_intent(text, catalog())
            self.assertIsNotNone(intent, text)
            self.assertEqual(intent.kind, 'roast', text)
            self.assertEqual(set(intent.tags), tags, text)
            self.assertNotIn('adult_mode', intent.tags)

    def test_general_song_requests_are_random(self):
        for text in ('hey jose play a song', 'jose play something', 'jose sing', 'jose play us a song please'):
            intent = parse_intent(text, catalog())
            self.assertEqual(intent.kind, 'song', text)
            self.assertTrue(intent.random_song, text)

    def test_specific_song_requests(self):
        cases = {
            'jose play wellerman': 'Wellerman',
            'hey jose play the tiki room': 'In the Tiki Room',
            'jose play in the tiki room': 'In the Tiki Room',
            "jose play let's get it started": "Let's Get It Started",
            'jose play mele kalikimaka': 'Mele Kalikimaka',
            'jose play a sea shanty': 'Wellerman',
        }
        for text, expected in cases.items():
            intent = parse_intent(text, catalog())
            self.assertIsNotNone(intent, text)
            self.assertEqual(title(intent), expected, text)

    def test_unknown_song_is_ignored(self):
        self.assertIsNone(parse_intent('jose play stairway to heaven', catalog()))

    def test_roles_never_cross(self):
        for text in ('polly play a song', 'polly sing wellerman', 'jose roast me', 'fuck you jose',
                     'jose want a cracker', 'hey polly', 'play a song', 'roast me', 'the tiki room is great'):
            self.assertIsNone(parse_intent(text, catalog()), text)

    def test_custom_aliases(self):
        intent = parse_intent('hey hosay play wellerman', catalog())
        self.assertEqual(title(intent), 'Wellerman')
        self.assertIsNone(parse_intent('hey bob play wellerman', catalog(), jose_aliases=['jose']))


class FakeLms:
    def __init__(self, mode='stop', tracks=None):
        self.mode = mode
        self.tracks = tracks if tracks is not None else [{'id': 7, 'title': 'Wellerman', 'url': 'file:///m/wellerman.mp3'}]
        self.calls = []

    def rpc(self, pid, cmd):
        self.calls.append((pid, cmd))
        if cmd[0] == 'titles':
            return {'titles_loop': self.tracks}
        return {}

    def track_state(self, pid):
        return {'mode': self.mode, 'index': 0, 'time': 0.0}


class SongRequestTest(unittest.TestCase):
    def wellerman(self):
        return next(s for s in SONGS if s.get('name') == 'Wellerman')

    def test_idle_player_loads_and_plays(self):
        lms = FakeLms()
        result = request_song(lms, 'main', self.wellerman())
        self.assertEqual(result['action'], 'playing')
        self.assertIn(('main', ['playlistcontrol', 'cmd:load', 'track_id:7']), lms.calls)

    def test_busy_player_queues_next(self):
        lms = FakeLms(mode='play')
        result = request_song(lms, 'main', self.wellerman())
        self.assertEqual(result['action'], 'queued_next')
        self.assertIn(('main', ['playlistcontrol', 'cmd:insert', 'track_id:7']), lms.calls)

    def test_wrong_library_track_not_used(self):
        lms = FakeLms(tracks=[{'id': 9, 'title': 'Something Else', 'url': 'file:///m/other.mp3'}])
        self.assertIsNone(find_lms_track(lms, self.wellerman()))

    def test_match_by_file_name(self):
        lms = FakeLms(tracks=[{'id': 3, 'title': 'Track 01', 'url': 'file:///music/wellerman/wellerman.mp3'}])
        self.assertEqual(find_lms_track(lms, self.wellerman())['id'], 3)


class FakeClock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class VoiceServiceTest(unittest.TestCase):
    def make(self, count=4, adult=True, **kw):
        self.roasts, self.songs, self.clock = [], [], FakeClock()
        cfg = {'bird_count': count, 'voice': {'adult_mode': adult, 'cooldown_s': 3}}
        return VoiceService(cfg, catalog(), roast_fn=lambda tags: self.roasts.append(tags) or {'played': True},
                            song_fn=lambda song: self.songs.append(song['name']) or {'action': 'playing'},
                            spawn=lambda fn: fn(), clock=self.clock, **kw)

    def test_roast_adds_operator_adult_mode(self):
        svc = self.make()
        self.assertEqual(svc.handle('fuck you polly'), {'roast': 'adult_mode,direct_insult'})
        self.assertEqual(self.roasts, ['adult_mode,direct_insult'])

    def test_roast_refused_without_operator_adult_mode(self):
        for adult in (False, None, 'true'):
            svc = self.make(adult=adult)
            self.assertEqual(svc.handle('hey polly roast me')['ignored'], 'adult_mode_off')
            self.assertEqual(self.roasts, [])

    def test_roast_works_in_every_topology(self):
        for n in (1, 4, 5):
            svc = self.make(count=n)
            self.assertIn('roast', svc.handle('roast me polly'))

    def test_no_songs_in_single_bird_mode(self):
        svc = self.make(count=1)
        self.assertIn('error', svc.handle('jose play wellerman'))
        self.assertEqual(self.songs, [])

    def test_song_specific_and_random(self):
        svc = self.make(count=5)
        self.assertEqual(svc.handle('jose play wellerman')['song'], 'Wellerman')
        self.clock.t += 10
        result = svc.handle('hey jose play a song')
        self.assertTrue(result['random'])
        self.assertNotEqual(self.songs[-1], 'Wellerman')

    def test_cooldown_per_kind(self):
        svc = self.make()
        svc.handle('jose play wellerman')
        self.assertEqual(svc.handle('jose play ymca')['ignored'], 'cooldown')
        self.assertIn('roast', svc.handle('roast me polly'))

    def test_polly_busy_drops_overlapping_roast(self):
        svc = self.make()
        pending = []
        svc.spawn = pending.append
        svc.handle('roast me polly')
        self.clock.t += 10
        self.assertEqual(svc.handle('fuck you polly')['ignored'], 'polly_busy')
        pending[0]()
        self.clock.t += 10
        self.assertIn('roast', svc.handle('fuck you polly'))

    def test_chatter_is_ignored(self):
        self.assertIsNone(self.make().handle('what a nice party'))


if __name__ == '__main__':
    unittest.main()
