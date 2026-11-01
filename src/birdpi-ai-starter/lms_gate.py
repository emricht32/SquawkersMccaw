"""Polly/song performance gate: the first to start plays, the other is queued.

LMS is the single source of truth for songs, so this works across hosts without
changing the piCorePlayer nodes:
- Song first: Polly waits until the current track ends. If LMS moves on to the
  next track, that track is stopped and held until Polly has finished.
- Polly first: any song that starts is stopped and held until she has finished.
Held songs are restarted from the top so every bird_daemon re-syncs.
"""
import json
import logging
import queue
import socket
import threading
import time
import http.client
import urllib.parse

log = logging.getLogger('birdpi.lms_gate')


class GateUnavailable(RuntimeError):
    pass


class LmsClient:
    def __init__(self, host, cli_port=9090, web_port=9000, timeout=3.0):
        self.host = host
        self.cli_port = cli_port
        self.web_port = web_port
        self.timeout = timeout

    def rpc(self, player_id, command):
        conn = http.client.HTTPConnection(self.host, self.web_port, timeout=self.timeout)
        try:
            body = json.dumps({'id': 1, 'method': 'slim.request', 'params': [player_id, command]})
            conn.request('POST', '/jsonrpc.js', body=body, headers={'Content-Type': 'application/json'})
            resp = conn.getresponse()
            data = resp.read()
            if resp.status != 200:
                raise GateUnavailable(f'LMS JSON-RPC HTTP {resp.status}')
            return json.loads(data.decode('utf-8')).get('result', {})
        except (OSError, ValueError) as exc:
            raise GateUnavailable(f'LMS unreachable at {self.host}: {exc}') from exc
        finally:
            conn.close()

    def playing_players(self):
        result = self.rpc('', ['serverstatus', '0', '99'])
        return [p['playerid'] for p in result.get('players_loop', [])
                if str(p.get('isplaying', 0)) == '1' and p.get('playerid')]

    def stop(self, player_id):
        self.rpc(player_id, ['stop'])

    def play(self, player_id):
        self.rpc(player_id, ['play'])

    def find_player(self, name):
        result = self.rpc('', ['players', '0', '99'])
        for p in result.get('players_loop', []):
            if str(p.get('name', '')).lower() == name.lower():
                return p
        return None

    def status(self, player_id):
        result = self.rpc(player_id, ['status', '-', '1'])
        try:
            position = float(result.get('time'))
        except (TypeError, ValueError):
            position = None
        return result.get('mode'), position

    def track_state(self, player_id):
        result = self.rpc(player_id, ['status', '-', '1'])
        try:
            position = float(result.get('time'))
        except (TypeError, ValueError):
            position = 0.0
        return {'mode': result.get('mode'), 'index': result.get('playlist_cur_index'), 'time': position}

    def play_url(self, player_id, url, title):
        self.rpc(player_id, ['playlist', 'repeat', '0'])
        self.rpc(player_id, ['playlist', 'play', url, title])

    def local_ip(self):
        """Address of this host as seen on the route to LMS (for LMS to fetch audio from us)."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            try:
                s.connect((self.host, self.web_port))
            except OSError as exc:
                raise GateUnavailable(f'No route to LMS at {self.host}: {exc}') from exc
            return s.getsockname()[0]

    def open_subscription(self):
        sock = socket.create_connection((self.host, self.cli_port), timeout=self.timeout)
        try:
            sock.sendall(b'subscribe playlist\n')
            ack = b''
            while not ack.endswith(b'\n'):
                chunk = sock.recv(1)
                if not chunk:
                    raise GateUnavailable('LMS CLI did not acknowledge subscribe')
                ack += chunk
        except (OSError, GateUnavailable) as exc:
            sock.close()
            raise GateUnavailable(f'LMS CLI subscribe failed: {exc}') from exc
        return sock


def parse_song_start(line):
    """Return the player id if a CLI line announces audio starting or resuming, else None."""
    decoded = urllib.parse.unquote(line.strip())
    parts = decoded.split(' ', 2)
    if len(parts) < 3 or parts[1] != 'playlist':
        return None
    event = parts[2]
    if event == 'newsong' or event.startswith(('newsong ', 'open ')) or event == 'pause 0':
        return parts[0]
    return None


class NullGate:
    """1-bird mode: there are no songs to collide with."""
    kind = 'none'

    def acquire(self, max_wait_s=0.0):
        return True

    def release(self):
        pass


class LmsPerformanceGate:
    kind = 'lms_first_come_queue'

    def __init__(self, client, player_ids=None, poll_s=0.5, exclude_ids=(),
                 restart_slack_s=2.0, clock=time.monotonic):
        self.client = client
        self.player_ids = set(player_ids or [])
        self.exclude_ids = set(exclude_ids)
        self.poll_s = poll_s
        self.restart_slack_s = restart_slack_s
        self.clock = clock
        self._lock = threading.Lock()
        self._state = 'idle'
        self._deferred = []
        self._events = queue.Queue()
        self._sock = None
        self._thread = None
        self._stop = threading.Event()

    def _relevant(self, player_id):
        if player_id in self.exclude_ids:
            return False
        return not self.player_ids or player_id in self.player_ids

    def acquire(self, max_wait_s=0.0):
        """Claim the bird for Polly, queueing up to max_wait_s behind a playing song.

        Returns False if the wait ran out. Fails closed (raises) if LMS cannot be checked.
        """
        with self._lock:
            if self._state != 'idle':
                return False
            # Subscribe before checking state so a song starting in between is still caught.
            self._sock = self.client.open_subscription()
            self._state = 'waiting'
            self._deferred = []
            self._events = queue.Queue()
            self._stop.clear()
            self._thread = threading.Thread(target=self._watch, args=(self._sock,), daemon=True)
            self._thread.start()
        try:
            got_turn = self._wait_for_turn(max_wait_s)
        except Exception:
            self.release()
            raise
        if not got_turn:
            log.info('Polly gave up after waiting %.0fs for the song to finish', max_wait_s)
            self.release()
            return False
        with self._lock:
            self._state = 'active'
        while True:
            try:
                player_id = self._events.get_nowait()
            except queue.Empty:
                break
            self._defer_if_playing(player_id)
        return True

    def _wait_for_turn(self, max_wait_s):
        deadline = self.clock() + max_wait_s
        baseline = {}
        for player_id in self.client.playing_players():
            if self._relevant(player_id):
                baseline[player_id] = (self.client.track_state(player_id), self.clock())
        if baseline:
            log.info('Polly queued behind song on %s', sorted(baseline))
        while baseline:
            if self.clock() >= deadline:
                return False
            try:
                player_id = self._events.get(timeout=self.poll_s)
            except queue.Empty:
                player_id = None
            # A song starting on a player that was idle when Polly queued goes behind her.
            if player_id is not None and player_id not in baseline:
                self._defer_if_playing(player_id)
            for pid in list(baseline):
                prev, seen_at = baseline[pid]
                now = self.client.track_state(pid)
                if now['mode'] != 'play':
                    del baseline[pid]
                elif (now['index'] != prev['index'] or
                      now['time'] + self.restart_slack_s < prev['time'] + (self.clock() - seen_at)):
                    # The song Polly was waiting on ended and LMS moved on; hold the next one.
                    self._defer(pid)
                    del baseline[pid]
        return True

    def on_song_start(self, player_id):
        if not self._relevant(player_id):
            return
        with self._lock:
            state = self._state
        if state == 'waiting':
            self._events.put(player_id)
        elif state == 'active':
            self._defer_if_playing(player_id)

    def _defer_if_playing(self, player_id):
        try:
            if self.client.track_state(player_id)['mode'] != 'play':
                return
        except GateUnavailable:
            log.exception('Could not read LMS player %s; holding it anyway', player_id)
        self._defer(player_id)

    def _defer(self, player_id):
        # stop is sent under the lock so release() can never issue play before it.
        with self._lock:
            if self._state == 'idle' or player_id in self._deferred:
                return
            log.info('Holding song on %s until Polly is done', player_id)
            self._deferred.append(player_id)
            try:
                self.client.stop(player_id)
            except GateUnavailable:
                log.exception('Could not stop LMS player %s', player_id)

    def release(self):
        with self._lock:
            if self._state == 'idle':
                return
            self._state = 'idle'
            deferred, self._deferred = self._deferred, []
            self._stop.set()
            self._close_sock()
        if self._thread:
            self._thread.join(timeout=2)
        for player_id in deferred:
            try:
                self.client.play(player_id)
            except GateUnavailable:
                log.exception('Could not restart held song on %s', player_id)

    def _close_sock(self):
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _watch(self, sock):
        sock.settimeout(self.poll_s)
        buf = b''
        while not self._stop.is_set():
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1)
                player_id = parse_song_start(line.decode('utf-8', 'replace'))
                if player_id:
                    self.on_song_start(player_id)
        if not self._stop.is_set():
            log.error('LMS CLI subscription dropped while Polly was queued/performing')


def make_client(lms_cfg):
    if not lms_cfg or not lms_cfg.get('host'):
        raise GateUnavailable('lms.host is required in the topology config')
    return LmsClient(lms_cfg['host'], int(lms_cfg.get('cli_port', 9090)),
                     int(lms_cfg.get('web_port', 9000)), float(lms_cfg.get('timeout_s', 3.0)))


def build_gate(bird_count, lms_cfg, exclude_ids=()):
    if bird_count == 1:
        return NullGate()
    return LmsPerformanceGate(make_client(lms_cfg), lms_cfg.get('player_ids'), exclude_ids=exclude_ids)
