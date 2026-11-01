"""Song catalog matching and LMS song requests for José.

Songs come from config_multi_song_with_triggers.json (the same file bird_daemon
uses to animate them), so anything requested here is a song the birds can sing.
"""
import difflib
import logging
import os
import random
import re

from lms_gate import GateUnavailable

log = logging.getLogger('birdpi.songs')

FILLER_WORDS = {
    'a', 'an', 'the', 'us', 'me', 'for', 'please', 'some', 'song', 'songs', 'tune', 'music',
    'something', 'anything', 'random', 'another', 'one', 'again', 'now', 'can', 'you', 'will',
    'would', 'could', 'hey', 'ok', 'okay', 'go', 'ahead', 'and', 'that', 'this', 'track',
}


def normalize(value):
    """Same normalization bird_daemon uses to match LMS titles to songs."""
    if not value:
        return ''
    text = str(value).lower()
    text = re.sub(r"\([^)]*\)", ' ', text)
    text = re.sub(r"\b(feat\.?|featuring)\b", ' ', text)
    text = re.sub(r"[^a-z0-9]+", ' ', text).strip()
    return ' '.join(text.split())


def strip_fillers(query):
    return ' '.join(w for w in normalize(query).split() if w not in FILLER_WORDS)


def _song_keys(song):
    keys = [song.get('name'), song.get('display_name')]
    if song.get('audio_dir'):
        keys.append(os.path.basename(song['audio_dir']))
    for trigger in song.get('triggers', []) or []:
        keys.append(re.sub(r'^(play|start|sing)\s+', '', normalize(trigger)))
    return [k for k in (normalize(k) for k in keys if isinstance(k, str)) if k]


class SongCatalog:
    def __init__(self, songs, rng=None):
        self.songs = [s for s in songs if _song_keys(s)]
        self.rng = rng or random.Random()
        self.last = None

    def match(self, query, threshold=0.6):
        query = strip_fillers(query)
        if not query:
            return None
        best, best_score = None, 0.0
        for song in self.songs:
            for key in _song_keys(song):
                stripped = strip_fillers(key)
                if query in (key, stripped):
                    score = 1.0
                elif stripped and (query in stripped or stripped in query):
                    score = 0.9
                else:
                    score = difflib.SequenceMatcher(None, query, stripped or key).ratio()
                if score > best_score:
                    best, best_score = song, score
        return best if best_score >= threshold else None

    def pick_random(self):
        pool = [s for s in self.songs if s is not self.last] or self.songs
        return self.rng.choice(pool) if pool else None

    def title(self, song):
        return song.get('display_name') or song.get('name')


def find_lms_track(client, song):
    """Find the LMS library track for a song, matched the same way bird_daemon matches titles."""
    keys = set(_song_keys(song))
    terms = [song.get('lms_search'), song.get('display_name'), song.get('name')]
    if song.get('audio_dir'):
        terms.append(os.path.basename(song['audio_dir']))
    for term in [t for t in terms if t]:
        result = client.rpc('', ['titles', '0', '20', f'search:{term}', 'tags:u'])
        for track in result.get('titles_loop', []):
            title = normalize(track.get('title'))
            stem = normalize(os.path.splitext(os.path.basename(str(track.get('url', ''))))[0])
            if any(k and (k == title or k in title or title in k or k == stem) for k in keys):
                return track
    return None


def request_song(client, player_id, song):
    """Play the song now, or queue it next if the song player is already playing."""
    track = find_lms_track(client, song)
    if not track:
        raise GateUnavailable(f'No LMS library track found for {song.get("display_name") or song.get("name")!r}')
    mode = client.track_state(player_id)['mode']
    cmd = 'insert' if mode == 'play' else 'load'
    client.rpc(player_id, ['playlistcontrol', f'cmd:{cmd}', f'track_id:{track["id"]}'])
    return {'action': 'queued_next' if cmd == 'insert' else 'playing', 'track': track.get('title')}
