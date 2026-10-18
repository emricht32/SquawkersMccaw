#!/usr/bin/env python3
"""Stream local llama.cpp responses into BirdPi's persistent speech server.

The first complete phrase can play while the LLM produces later text.
Requires Python standard library only. Use localhost-only endpoints.
"""
import argparse
import json
import re
import queue
import subprocess
import tempfile
import threading
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

SYSTEM_PROMPT = ("You are José, a quick-witted animatronic tiki bird. "
                 "Speak naturally, in character, with playful pirate flavor. "
                 "Give the user exactly what they request, not commentary about it. "
                 "Keep answers short (usually 1-3 sentences). "
                 "For jokes: tell a REAL joke with a clear setup and a surprising, related punchline; "
                 "never announce you are telling a joke, and never merely state a funny-sounding fact. "
                 "Avoid repeated introductions, stage directions, markdown, and internal reasoning. "
                 "/no_think")


def prepare_question(question):
    """Strengthen constraints for requests tiny local models often mishandle."""
    if re.search(r"\b(joke|jokes|funny|pun)\b", question, re.IGNORECASE):
        return (question + "\nGive a complete setup and a punchline that actually answers "
                "the setup. No introduction or explanation. /no_think")
    return question + ' /no_think'



def phrases(buffer, final=False, max_chars=110):
    """Extract only complete sentences; at the limit use the last word boundary."""
    ready = []
    while True:
        match = re.search(r'[.!?](?:[\"\']?)(?=\s|$)', buffer)
        if match:
            end = match.end()
            text = buffer[:end].strip()
            buffer = buffer[end:].lstrip()
        elif len(buffer) >= max_chars:
            boundary = buffer.rfind(' ', 0, max_chars)
            if boundary <= 0:
                break
            text = buffer[:boundary].strip()
            buffer = buffer[boundary:].lstrip()
        else:
            break
        if text:
            ready.append(text)
    if final and buffer.strip():
        ready.append(buffer.strip())
        buffer = ''
    return ready, buffer


def stream_llm(base_url, question, max_tokens, timeout):
    request = Request(
        base_url.rstrip('/') + '/v1/chat/completions',
        data=json.dumps({
            'model': 'local',
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': prepare_question(question)},
            ],
            'max_tokens': max_tokens, 'stream': True,
            'temperature': 0.7,
            'top_p': 0.9,
            'repeat_penalty': 1.1,
        }).encode(),
        headers={'Content-Type': 'application/json', 'Accept': 'text/event-stream'},
        method='POST',
    )
    with urlopen(request, timeout=timeout) as response:
        for line in response:
            line = line.decode('utf-8').strip()
            if not line.startswith('data: '):
                continue
            data = line[6:]
            if data == '[DONE]':
                break
            item = json.loads(data)
            for choice in item.get('choices', []):
                token = choice.get('delta', {}).get('content', '')
                if token:
                    yield token


def speak(tts_url, bird, text, timeout, play=True):
    request = Request(
        tts_url.rstrip('/') + '/api/speech',
        data=json.dumps({'bird': bird, 'text': text, 'play': play}).encode(),
        headers={'Content-Type': 'application/json'}, method='POST',
    )
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


class ThinkFilter:
    def __init__(self):
        self.pending = ''
        self.thinking = False

    def feed(self, token, final=False):
        self.pending += token
        out = ''
        while self.pending:
            tag = '</think>' if self.thinking else '<think>'
            idx = self.pending.find(tag)
            if idx >= 0:
                if not self.thinking:
                    out += self.pending[:idx]
                self.pending = self.pending[idx + len(tag):]
                self.thinking = not self.thinking
                continue
            # Preserve the longest suffix that might be a partial tag.
            keep = max((n for n in range(1, min(len(tag), len(self.pending) + 1))
                        if self.pending.endswith(tag[:n])), default=0)
            if final:
                keep = 0
            if not self.thinking:
                out += self.pending[:len(self.pending) - keep] if keep else self.pending
            self.pending = self.pending[-keep:] if keep else ''
            break
        return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('question', help='Question to ask José')
    parser.add_argument('--bird', default='jose', choices=['jose', 'michael', 'fritz', 'pierre'])
    parser.add_argument('--llm-url', default='http://127.0.0.1:8082')
    parser.add_argument('--tts-url', default='http://127.0.0.1:8081')
    parser.add_argument('--max-tokens', type=int, default=100)
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--no-play', action='store_true')
    args = parser.parse_args()
    started = time.monotonic()
    first_token_s = None
    first_phrase_s = None
    phrase_count = 0
    buffer = ''
    filter_ = ThinkFilter()
    work = queue.Queue(maxsize=8)
    worker_error = []
    def player():
        nonlocal first_phrase_s, phrase_count
        while True:
            phrase = work.get()
            try:
                if phrase is None:
                    return
                response = speak(args.tts_url, args.bird, phrase, args.timeout, False)
                phrase_count += 1
                if first_phrase_s is None:
                    first_phrase_s = time.monotonic() - started
                print(f'[{phrase_count}] {phrase} | speech={response["duration"]}s '
                      f'tts={response["metrics"]["synthesis_s"]}s '
                      f'cues={len(response["singing_ranges"])}', flush=True)
                if not args.no_play:
                    audio_url = args.tts_url.rstrip('/') + response['audio']
                    with urlopen(audio_url, timeout=args.timeout) as wav_resp:
                        wav_bytes = wav_resp.read()
                    with tempfile.TemporaryDirectory(prefix='birdpi-speech-') as temp:
                        path = Path(temp) / 'speech.wav'
                        path.write_bytes(wav_bytes)
                        subprocess.run(['aplay', '-q', str(path)], check=True)
            except Exception as exc:
                worker_error.append(str(exc))
                return
            finally:
                work.task_done()

    worker = threading.Thread(target=player, daemon=True)
    worker.start()
    try:
        for token in stream_llm(args.llm_url, args.question, args.max_tokens, args.timeout):
            if first_token_s is None:
                first_token_s = time.monotonic() - started
            buffer += filter_.feed(token)
            ready, buffer = phrases(buffer)
            for phrase in ready:
                if worker_error:
                    raise RuntimeError(worker_error[0])
                work.put(phrase)
        buffer += filter_.feed('', final=True)
        ready, buffer = phrases(buffer, final=True)
        for phrase in ready:
            work.put(phrase)
        work.put(None)
        work.join()
        if worker_error:
            raise RuntimeError(worker_error[0])
    except (HTTPError, URLError, OSError, ValueError, KeyError, RuntimeError) as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    print(f'Metrics: first_token={first_token_s}, first_synthesized_phrase={first_phrase_s}, '
          f'total={time.monotonic()-started:.3f}s')
    print('Speech playback is ordered; each chunk starts after the previous chunk completes.')


if __name__ == '__main__':
    main()
