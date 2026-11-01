#!/usr/bin/env python3
"""Voice triggers for the show.

  "Hey Polly, roast me" / "Fuck you Polly" / "Polly want a cracker?"  -> Polly roast
  "Hey José, play a song" / "José play Wellerman"                    -> José song via LMS

Runs on Polly's host with a USB mic. Roasts go through birdpi_bridge (role checks,
song/roast queue gate, LMS audio + beak). Songs are started on the LMS song player,
so bird_daemon animates them as usual. Use --console to type transcripts instead.
"""
import argparse
import json
import logging
import os
import queue
import sys
import threading
import time
from pathlib import Path

import birdpi_bridge
from birdpi_roles import RoutingError, route
from lms_gate import GateUnavailable, make_client
from song_requests import SongCatalog, request_song
from voice_intents import parse_intent

log = logging.getLogger('birdpi.voice')

BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent.parent
SONGS_PATH = REPO_DIR / 'config_multi_song_with_triggers.json'


def _spawn(fn):
    threading.Thread(target=fn, daemon=True).start()


class VoiceService:
    def __init__(self, cfg, catalog, roast_fn=None, song_fn=None, spawn=_spawn, clock=time.monotonic):
        self.cfg = cfg
        self.count = cfg['bird_count']
        self.voice = cfg.get('voice', {})
        self.catalog = catalog
        self.roast_fn = roast_fn or self._default_roast
        self.song_fn = song_fn or self._default_song
        self.spawn = spawn
        self.clock = clock
        self.cooldown_s = float(self.voice.get('cooldown_s', 3.0))
        self._last = {}
        self._roast_busy = threading.Lock()

    def handle(self, transcript):
        intent = parse_intent(transcript, self.catalog,
                              self.voice.get('polly_aliases'), self.voice.get('jose_aliases'))
        if intent is None:
            return None
        if self.clock() - self._last.get(intent.kind, float('-inf')) < self.cooldown_s:
            return {'ignored': 'cooldown', 'kind': intent.kind}
        self._last[intent.kind] = self.clock()
        try:
            return self._roast(intent) if intent.kind == 'roast' else self._song(intent)
        except (RoutingError, GateUnavailable) as exc:
            log.warning('%s request %r refused: %s', intent.kind, transcript, exc)
            return {'error': str(exc), 'kind': intent.kind}

    def _roast(self, intent):
        route(self.count, 'polly', 'comedy')
        # Voice only supplies the challenge; permission for adult roasts is the operator's call.
        if self.voice.get('adult_mode') is not True:
            return {'ignored': 'adult_mode_off', 'kind': 'roast'}
        if not self._roast_busy.acquire(blocking=False):
            return {'ignored': 'polly_busy', 'kind': 'roast'}
        tags = ','.join(['adult_mode', *sorted(intent.tags)])

        def run():
            try:
                result = self.roast_fn(tags)
                log.info('Roast result: played=%s reason=%s', result.get('played'), result.get('reason'))
            except Exception:
                log.exception('Roast failed')
            finally:
                # Cooldown counts from the end so Polly's own echo can't re-trigger her.
                self._last['roast'] = self.clock()
                self._roast_busy.release()
        self.spawn(run)
        return {'roast': tags}

    def _song(self, intent):
        route(self.count, 'jose', 'sing')
        song = intent.song or self.catalog.pick_random()
        if song is None:
            return {'ignored': 'no_songs', 'kind': 'song'}
        result = self.song_fn(song)
        self.catalog.last = song
        return {'song': self.catalog.title(song), 'random': intent.song is None, **result}

    def _default_roast(self, tags):
        session = 'voice-' + time.strftime('%Y%m%d')
        return birdpi_bridge.play_roast(self.cfg, self.voice.get('db', 'data/chirps.sqlite'), tags, [], session,
                                        self.voice.get('tts_url', 'http://127.0.0.1:8081'))

    def _default_song(self, song):
        lms_cfg = self.cfg.get('lms', {})
        client = make_client(lms_cfg)
        name = lms_cfg.get('song_player', 'birdpi-main')
        player = client.find_player(name)
        if not player or str(player.get('connected', 0)) != '1':
            raise GateUnavailable(f'Song player {name!r} is not registered/connected on {client.host}')
        return request_song(client, player['playerid'], song)


def load_catalog(path=SONGS_PATH):
    return SongCatalog(json.loads(Path(path).read_text()).get('songs', []))


def main():
    p = argparse.ArgumentParser(description='BirdPi voice triggers (Polly roasts, José songs)')
    p.add_argument('--config', default=str(birdpi_bridge.default_config_path()))
    p.add_argument('--songs', default=str(SONGS_PATH))
    p.add_argument('--console', action='store_true', help='Type transcripts instead of using the mic')
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(name)s %(levelname)s: %(message)s')

    cfg = birdpi_bridge.load_config(args.config)
    os.chdir(BASE_DIR)  # bridge paths (data/, voices/) are relative to the starter dir
    service = VoiceService(cfg, load_catalog(args.songs))
    events = queue.Queue()

    if args.console:
        def read_stdin():
            for line in sys.stdin:
                if line.strip():
                    events.put(('speech', line.strip()))
            events.put(('eof', None))
        threading.Thread(target=read_stdin, daemon=True).start()
    else:
        if str(REPO_DIR / 'src') not in sys.path:
            sys.path.append(str(REPO_DIR / 'src'))
        from roast.speech import Listener
        voice = cfg.get('voice', {})
        stt = {'vosk_model': str(REPO_DIR / voice.get('vosk_model', 'models/vosk-model-small-en-us-0.15')),
               'device': voice.get('mic_device', 'default'), 'min_chars': 3}
        Listener(stt, events).start()

    log.info('Voice service ready: %d birds, adult_mode=%s, %d songs',
             cfg['bird_count'], cfg.get('voice', {}).get('adult_mode') is True, len(service.catalog.songs))
    while True:
        kind, text = events.get()
        if kind == 'eof':
            # Let any in-flight roast finish before exiting console mode.
            with service._roast_busy:
                return
        result = service.handle(text)
        if result:
            log.info('%r -> %s', text, json.dumps(result, ensure_ascii=False))
        else:
            log.debug('No intent in %r', text)


if __name__ == '__main__':
    main()
