"""Play Polly's speech and drive the beak from mouth cues on the playback position.

Audio goes through a sink: LmsSink (Polly's own LMS/Squeezelite player) or
AplaySink (local ALSA fallback). The beak follows the sink's reported position,
is always switched off on exit, and pins are released so the song daemon can
reuse them on a shared bird.
"""
import logging
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger('birdpi.performer')

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_body_factory(pins):
    if SRC_DIR not in sys.path:
        sys.path.append(SRC_DIR)
    from roast.body import BirdBody
    return BirdBody(pins)


def default_player_factory(wav_path):
    return subprocess.Popen(['aplay', '-q', wav_path], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _close(device):
    if device is not None:
        try:
            device.off()
        finally:
            close = getattr(device, 'close', None)
            if close:
                close()


class AplaySink:
    name = 'aplay'
    start_timeout_s = 0.0

    def __init__(self, player_factory=default_player_factory, clock=time.monotonic):
        self.player_factory = player_factory
        self.clock = clock
        self.proc = None

    def start(self, wav_path, duration):
        self.proc = self.player_factory(wav_path)
        self.t0 = self.clock()

    def position(self):
        return self.clock() - self.t0

    def poll(self):
        code = self.proc.poll()
        if code is None:
            return None
        if code == 0:
            return True, None
        err = self.proc.stderr.read().decode('utf-8', 'replace').strip() if getattr(self.proc, 'stderr', None) else ''
        return False, f'aplay exited {code}: {err}'

    def stop(self):
        self.proc.terminate()

    def close(self):
        if self.proc:
            self.proc.kill()


class WavServer:
    """Serves one WAV at an unguessable URL so LMS can fetch it; lives only for one performance."""

    def __init__(self, wav_path, bind_host, port=0):
        with open(wav_path, 'rb') as f:
            data = f.read()
        path = f'/polly/{secrets.token_urlsafe(16)}.wav'

        class Handler(BaseHTTPRequestHandler):
            def _head(self):
                if self.path != path:
                    self.send_error(404)
                    return False
                self.send_response(200)
                self.send_header('Content-Type', 'audio/wav')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                return True

            def do_HEAD(self):
                self._head()

            def do_GET(self):
                if self._head():
                    self.wfile.write(data)

            def log_message(self, fmt, *args):
                log.debug('wav server: ' + fmt, *args)

        self.httpd = ThreadingHTTPServer((bind_host, port), Handler)
        self.url = f'http://{bind_host}:{self.httpd.server_address[1]}{path}'
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def shutdown(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class LmsSink:
    name = 'lms'

    def __init__(self, client, player_id, bind_host, port=0, start_timeout_s=8.0,
                 resync_s=0.25, end_tolerance_s=0.75, clock=time.monotonic, server_factory=WavServer):
        self.client = client
        self.player_id = player_id
        self.bind_host = bind_host
        self.port = port
        self.start_timeout_s = start_timeout_s
        self.resync_s = resync_s
        self.end_tolerance_s = end_tolerance_s
        self.clock = clock
        self.server_factory = server_factory
        self.server = None
        self.mode = None

    def start(self, wav_path, duration):
        self.duration = duration or 0.0
        self.mode = None
        self.anchor = None
        self.seen_play = False
        self.last_poll = float('-inf')
        self.server = self.server_factory(wav_path, self.bind_host, self.port)
        self.client.play_url(self.player_id, self.server.url, 'Polly')
        self.t0 = self.clock()

    def _refresh(self):
        now = self.clock()
        if now - self.last_poll < self.resync_s:
            return
        self.last_poll = now
        self.mode, pos = self.client.status(self.player_id)
        if self.mode == 'play':
            self.seen_play = True
            if pos is not None and pos > 0:
                # Re-anchor every poll so the beak tracks LMS's view of the playhead.
                self.anchor = now - pos

    def position(self):
        self._refresh()
        return None if self.anchor is None else self.clock() - self.anchor

    def poll(self):
        self._refresh()
        if not self.seen_play:
            if self.clock() - self.t0 > self.start_timeout_s:
                return False, 'LMS did not start Polly audio'
            return None
        if self.mode == 'play':
            return None
        reached = self.anchor is not None and self.clock() - self.anchor >= self.duration - self.end_tolerance_s
        return (True, None) if reached else (False, f'Polly player went to {self.mode!r} early')

    def stop(self):
        self.client.stop(self.player_id)
        self.mode = 'stop'

    def close(self):
        try:
            if self.mode == 'play':
                self.client.stop(self.player_id)
        finally:
            if self.server:
                self.server.shutdown()


class PollyPerformer:
    def __init__(self, pins, sink, audio_latency_s=0.0, max_open_s=0.4, min_closed_s=0.06,
                 tick_s=0.01, timeout_margin_s=2.0, body_factory=default_body_factory,
                 clock=time.monotonic, sleep=time.sleep):
        self.pins = pins or {}
        self.sink = sink
        self.audio_latency_s = audio_latency_s
        self.max_open_s = max_open_s
        self.min_closed_s = min_closed_s
        self.tick_s = tick_s
        self.timeout_margin_s = timeout_margin_s
        self.body_factory = body_factory
        self.clock = clock
        self.sleep = sleep

    def perform(self, wav, ranges, duration, abort=None):
        """Return {'played': bool, 'beak': 'gpio'|'unavailable', ...}; never leaves the beak on."""
        body = self.body_factory(self.pins)
        beak = getattr(body, 'beak', None)
        result = {'played': False, 'beak': 'gpio' if beak else 'unavailable',
                  'aborted': False, 'audio': self.sink.name}
        fd, wav_path = tempfile.mkstemp(prefix='polly-', suffix='.wav')
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(wav)
            if getattr(body, 'body', None):
                body.body.on()
            self.sink.start(wav_path, duration)
            start = self.clock()
            deadline = (duration or 0) + self.timeout_margin_s + self.sink.start_timeout_s
            is_open = False
            opened_at = closed_at = start
            while True:
                done = self.sink.poll()
                if done is not None:
                    ok, err = done
                    break
                now = self.clock()
                if (abort is not None and abort.is_set()) or now - start > deadline:
                    result['aborted'] = True
                    self.sink.stop()
                    ok, err = False, None
                    break
                pos = self.sink.position()
                want = pos is not None and any(a <= pos - self.audio_latency_s < b for a, b in ranges)
                if is_open and (not want or now - opened_at >= self.max_open_s):
                    is_open, closed_at = False, now
                    if beak:
                        beak.off()
                elif not is_open and want and now - closed_at >= self.min_closed_s:
                    is_open, opened_at = True, now
                    if beak:
                        beak.on()
                self.sleep(self.tick_s)
            if err:
                result['error'] = err
            result['played'] = ok and not result['aborted']
            return result
        finally:
            for device in [beak, getattr(body, 'body', None)] + list(getattr(body, 'lights', []) or []):
                try:
                    _close(device)
                except Exception:
                    log.exception('Failed to release GPIO device %s', device)
            try:
                self.sink.close()
            except Exception:
                log.exception('Failed to close %s audio sink', self.sink.name)
            os.unlink(wav_path)
