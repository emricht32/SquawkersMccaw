#!/usr/bin/env python3
"""BirdPi local microphone -> whisper.cpp STT -> response -> Piper TTS test.

Standalone; does not start vision, use wake-word processing, or drive motors.
"""
import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

DEFAULT_WHISPER = Path.home() / 'whisper.cpp'
POLLY_PROMPT = (
    'You are Polly, a cheeky animatronic parrot. You are the only bird speaking. '
    'Speak in first person, with crisp, short, witty responses (one or two sentences). '
    'Never reference another animatronic bird or have imaginary dialogue. '
    'Do not impersonate the listener or pretend to know who they are. '
    'No stage directions, markdown, or formatting. '
    'Avoid insults or adult material unless an operator separately authorizes that mode. '
    'The present session has no adult-mode authorization. '
)


def record_audio(destination, seconds, device):
    command = ['arecord', '-q', '-D', device, '-f', 'S16_LE', '-r', '16000', '-c', '1', '-d', str(seconds), str(destination)]
    subprocess.run(command, check=True)
    if not destination.is_file() or destination.stat().st_size < 16044:
        raise RuntimeError('Microphone recording is empty or too short; check arecord -l and the selected input device')


def transcribe(path, whisper_dir, model, threads):
    executable = whisper_dir / 'build/bin/whisper-cli'
    if not executable.is_file():
        raise FileNotFoundError(f'whisper-cli not found: {executable}. Run install_voice.sh')
    if not model.is_file():
        raise FileNotFoundError(f'Speech model not found: {model}. Run install_voice.sh')
    with tempfile.TemporaryDirectory(prefix='birdpi_stt_') as tmp:
        output = Path(tmp) / 'result'
        subprocess.run([
            str(executable), '-m', str(model), '-f', str(path), '-t', str(threads),
            '-l', 'en', '-nt', '-otxt', '-of', str(output),
        ], check=True, stdout=subprocess.DEVNULL)
        result_file = Path(str(output) + '.txt')
        if not result_file.is_file():
            raise RuntimeError('whisper-cli did not create a transcript')
        transcript = re.sub(r'\s+', ' ', result_file.read_text(encoding='utf-8')).strip()
        return transcript


def llm_answer(text, url, timeout=90):
    payload = {
        'model': 'local', 'stream': False, 'temperature': 0.65, 'max_tokens': 100,
        'messages': [
            {'role': 'system', 'content': POLLY_PROMPT},
            {'role': 'user', 'content': text},
        ],
    }
    req = Request(url.rstrip('/') + '/v1/chat/completions',
                  data=json.dumps(payload).encode('utf-8'),
                  headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(req, timeout=timeout) as response:
        data = json.load(response)
    result = data['choices'][0]['message']['content']
    result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL | re.I)
    result = re.sub(r'\s+', ' ', result).strip().strip('"')
    if not result:
        raise RuntimeError('LLM returned no response')
    return result[:500]


def speak(text, url, play):
    req = Request(url.rstrip('/') + '/api/speech',
                  data=json.dumps({'bird': 'polly', 'text': text, 'play': play}).encode('utf-8'),
                  headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(req, timeout=120) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=6, help='Microphone recording duration')
    parser.add_argument('--device', default='default', help='ALSA capture device, e.g. plughw:1,0')
    parser.add_argument('--file', type=Path, help='Use existing 16 kHz mono 16-bit PCM WAV instead of recording')
    parser.add_argument('--text', help='Bypass microphone and STT to test the response pipeline')
    parser.add_argument('--mode', choices=['echo', 'llm'], default='echo')
    parser.add_argument('--whisper-dir', type=Path, default=DEFAULT_WHISPER)
    parser.add_argument('--model', type=Path, default=None)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--tts-url', default='http://127.0.0.1:8081')
    parser.add_argument('--llm-url', default='http://127.0.0.1:8082')
    parser.add_argument('--no-play', action='store_true')
    args = parser.parse_args()
    if args.seconds < 1 or args.seconds > 60:
        parser.error('--seconds must be between 1 and 60')
    model = args.model or args.whisper_dir / 'models/ggml-base.en.bin'

    if args.text is not None:
        transcript = args.text.strip()
    elif args.file:
        transcript = transcribe(args.file, args.whisper_dir, model, args.threads)
    else:
        with tempfile.TemporaryDirectory(prefix='birdpi_mic_') as temp:
            wav = Path(temp) / 'input.wav'
            print(f'Recording {args.seconds}s from {args.device}... Speak now.', flush=True)
            record_audio(wav, args.seconds, args.device)
            print('Transcribing...', flush=True)
            transcript = transcribe(wav, args.whisper_dir, model, args.threads)
    print('HEARD:', repr(transcript), flush=True)
    if not transcript or transcript.strip(' .!?') == '':
        print('No speech detected. No response played.')
        return
    if args.mode == 'echo':
        answer = f'I heard you say: {transcript}'
    else:
        print('Generating Polly response...', flush=True)
        answer = llm_answer(transcript, args.llm_url)
    print('POLLY:', answer, flush=True)
    result = speak(answer, args.tts_url, play=not args.no_play)
    print('TTS:', json.dumps({'id': result.get('id'), 'audio': result.get('audio'), 'duration': result.get('duration')}))


if __name__ == '__main__':
    main()
