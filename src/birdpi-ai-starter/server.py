#!/usr/bin/env python3
"""Persistent Piper speech API. Runs on Python's standard-library HTTP server."""
import argparse
import inspect
import json
import logging
import subprocess
import threading
import time
import uuid
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from speech_animation import phonemes_to_ranges, pcm_to_ranges, merge_ranges

log = logging.getLogger('birdpi.tts')

class SpeechService:
    """Lazy-load individual Piper voice models and select multi-speaker IDs."""
    def __init__(self, voice_path: Path, output_dir: Path, profiles_path: Path):
        from piper import PiperVoice
        self.output_dir = output_dir.resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.default_voice = voice_path
        self.profiles = json.loads(profiles_path.read_text(encoding='utf-8'))
        self.models = {}
        self.load_times = {}
        self.lock = threading.RLock()
        self.piper_voice = PiperVoice
        self._load(voice_path)  # fail early if the original voice is missing
        self.load_s = self.load_times[str(voice_path.resolve())]

    def _load(self, path):
        path = Path(path)
        key = str(path.resolve())
        if key not in self.models:
            if not path.is_file():
                raise FileNotFoundError(f'Piper voice missing: {path}. Download it with: '
                                        f'(cd voices && ../.venv/bin/python -m piper.download_voices {path.stem})')
            start = time.perf_counter()
            self.models[key] = self.piper_voice.load(str(path), include_alignments=True)
            self.load_times[key] = time.perf_counter() - start
            log.info('Loaded %s in %.3fs', path, self.load_times[key])
        return self.models[key]

    def profile_for(self, bird):
        if bird not in {'jose', 'michael', 'fritz', 'pierre', 'polly'}:
            raise ValueError('Unknown bird')
        profile = self.profiles.get(bird, {})
        if not isinstance(profile, dict):
            raise ValueError('Voice profile must be an object')
        model = profile.get('model', '')
        path = Path('voices') / (model + '.onnx') if model else self.default_voice
        return profile, path

    def generate(self, text: str, bird: str, play: bool = False):
        from piper import SynthesisConfig
        profile, path = self.profile_for(bird)
        with self.lock:
            voice = self._load(path)
            cfg_fields = inspect.signature(SynthesisConfig).parameters
            requested = {
                'speaker_id': profile.get('speaker_id'),
                'length_scale': profile.get('length_scale', 1.0),
                'noise_scale': profile.get('noise_scale', 0.667),
                'noise_w_scale': profile.get('noise_w', 0.8),
            }
            cfg = SynthesisConfig(**{k: v for k, v in requested.items() if k in cfg_fields and v is not None})
            started = time.perf_counter()
            sample_rate = None
            frames = bytearray()
            candidate = []
            aligned = True
            total_samples = 0
            for chunk in voice.synthesize(text, syn_config=cfg, include_alignments=True):
                if sample_rate is not None and chunk.sample_rate != sample_rate:
                    raise ValueError('Sample rate changed mid-utterance')
                sample_rate = chunk.sample_rate
                pcm = chunk.audio_int16_bytes
                frames.extend(pcm)
                if chunk.phoneme_alignments is None:
                    aligned = False
                else:
                    ranges = phonemes_to_ranges(chunk.phoneme_alignments, sample_rate,
                                               gap=0.07, min_open=0.08,
                                               min_closed=0.06, max_open=0.25)
                    offset = total_samples / sample_rate
                    candidate.extend((a + offset, b + offset) for a, b in ranges)
                total_samples += len(pcm) // 2
            if not frames or sample_rate is None:
                raise RuntimeError('Piper returned no speech audio')
            synthesis_s = time.perf_counter() - started
        if aligned:
            ranges = merge_ranges(candidate)
            timing_method = 'phoneme_alignments'
        else:
            ranges = pcm_to_ranges(bytes(frames), sample_rate)
            timing_method = 'audio_energy_fallback'
        speech_id = uuid.uuid4().hex
        wav_path = self.output_dir / f'{speech_id}.wav'
        with wave.open(str(wav_path), 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(frames)
        duration = total_samples / sample_rate
        payload = {
            'id': speech_id, 'type': 'speech', 'bird': bird, 'text': text,
            'voice_model': path.stem, 'speaker_id': profile.get('speaker_id'),
            'audio': f'/api/audio/{speech_id}', 'sample_rate': sample_rate,
            'duration': round(duration, 3), 'timing_method': timing_method,
            'singing_ranges': ranges,
            'metrics': {
                'model_load_s': round(self.load_times[str(path.resolve())], 3),
                'synthesis_s': round(synthesis_s, 3),
                'synthesis_realtime_factor': round(synthesis_s / duration, 3)
            }
        }
        (self.output_dir / f'{speech_id}.json').write_text(json.dumps(payload, indent=2) + '\n')
        if play:
            subprocess.Popen(['aplay', '-q', str(wav_path)], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return payload


def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        def reply_json(self, status, payload):
            body = json.dumps(payload).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/health':
                return self.reply_json(200, {'ok': True, 'model_load_s': round(service.load_s, 3)})
            if path.startswith('/api/audio/'):
                audio_id = path.removeprefix('/api/audio/')
                if len(audio_id) != 32 or any(c not in '0123456789abcdef' for c in audio_id):
                    return self.reply_json(400, {'error': 'Invalid audio ID'})
                wav_path = service.output_dir / f'{audio_id}.wav'
                if not wav_path.is_file():
                    return self.reply_json(404, {'error': 'Audio not found'})
                audio = wav_path.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'audio/wav')
                self.send_header('Content-Length', str(len(audio)))
                self.end_headers()
                self.wfile.write(audio)
                return
            return self.reply_json(404, {'error': 'Not found'})

        def do_POST(self):
            if urlsplit(self.path).path != '/api/speech':
                return self.reply_json(404, {'error': 'Not found'})
            try:
                size = int(self.headers.get('Content-Length', '-1'))
                if not 1 <= size <= 16384:
                    return self.reply_json(400, {'error': 'Request must be 1–16384 bytes'})
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    return self.reply_json(400, {'error': 'Expected JSON object'})
                text = data.get('text')
                bird = data.get('bird', 'jose')
                play = data.get('play', False)
                if not isinstance(text, str) or not 1 <= len(text.strip()) <= 1000:
                    return self.reply_json(400, {'error': 'text must be 1–1000 characters'})
                if not isinstance(bird, str) or bird not in {'jose','michael','fritz','pierre','polly'}:
                    return self.reply_json(400, {'error': 'Unknown bird'})
                if not isinstance(play, bool):
                    return self.reply_json(400, {'error': 'play must be boolean'})
                return self.reply_json(200, service.generate(text, bird, play))
            except (ValueError, json.JSONDecodeError) as exc:
                return self.reply_json(400, {'error': str(exc)})
            except Exception:
                log.exception('Synthesis failed')
                return self.reply_json(500, {'error': 'Speech synthesis failed'})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--voice', type=Path, default=Path('voices/en_US-lessac-medium.onnx'))
    parser.add_argument('--profiles', type=Path, default=Path('voices/profiles.json'))
    parser.add_argument('--out', type=Path, default=Path('output/server'))
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8081)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    if not args.voice.exists():
        parser.error(f'Voice not found at {args.voice}. Run install.sh first.')
    service = SpeechService(args.voice, args.out, args.profiles)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(service))
    log.info('Listening on http://%s:%d', args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
