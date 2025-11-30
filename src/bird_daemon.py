#!/usr/bin/env python3
"""
bird_daemon.py

Long-lived daemon that:
- Connects to LMS CLI
- Subscribes to playlist events
- On new track, queries LMS JSON-RPC for title/time/duration
- Maps the title to a song in config_multi_song_with_triggers.json
- Drives LEDs via Bird + manage_leds from bird.py

LMS host is auto-discovered:
  1. Env var BIRDPI_LMS_HOST
  2. Cached host (config_lms_host.json)
  3. Hostnames: birdpi-main, birdpi-main.local
  4. Neighbor IPs from ip neigh / arp -n
  5. Local /24 subnet scan
"""

import os
import sys
import socket
import time
import json
import subprocess
import re
import threading
import urllib.parse
import http.client
from datetime import datetime

# -------------------------------------------------------------------
# Logging for the daemon
# -------------------------------------------------------------------
PRIMARY_LOG_DIR = "/mnt/mmcblk0p2/tc/birdpi-logs"
LOG_FILENAME = "daemon.log"


def _open_log():
    try:
        os.makedirs(PRIMARY_LOG_DIR, exist_ok=True)
        path = os.path.join(PRIMARY_LOG_DIR, LOG_FILENAME)
        f = open(path, "a", buffering=1)
        f.write(f"[{datetime.now().isoformat()}] bird_daemon logger started in {PRIMARY_LOG_DIR}\n")
        return f
    except Exception as e:
        sys.stdout.write(f"[{datetime.now().isoformat()}] bird_daemon: failed to open log file: {e}\n")
        sys.stdout.flush()

        class StdoutLogger:
            def write(self, msg):
                sys.stdout.write(msg)
                sys.stdout.flush()

            def flush(self):
                sys.stdout.flush()

            def close(self):
                pass

        return StdoutLogger()


_log = _open_log()


def log(msg: str):
    ts = datetime.now().isoformat()
    try:
        _log.write(f"[{ts}] {msg}\n")
    except Exception:
        try:
            sys.stdout.write(f"[{ts}] {msg}\n")
            sys.stdout.flush()
        except Exception:
            pass


# -------------------------------------------------------------------
# LMS host discovery helpers
# -------------------------------------------------------------------
LMS_HOST_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "../config_lms_host.json",
)


def is_lms_server(host: str, timeout: float = 0.3) -> bool:
    """
    Check whether the given host looks like an LMS server by probing port 9090.
    If TCP connect succeeds (and optionally returns a response), we accept it.
    """
    try:
        log(f"Probing potential LMS host {host}:9090")
        s = socket.create_connection((host, 9090), timeout=timeout)
        try:
            try:
                s.sendall(b"version ?\n")
                s.settimeout(timeout)
                data = s.recv(1024)
                if data:
                    log(f"Host {host} responded to LMS probe")
                    return True
            except Exception as inner:
                # TCP connect success is enough to treat as LMS
                log(f"LMS probe to {host} had inner error: {inner}")
                return True
        finally:
            try:
                s.close()
            except Exception:
                pass
    except OSError as e:
        log(f"LMS probe to {host} failed: {e}")
        return False
    return False


def load_cached_lms_host() -> str | None:
    try:
        with open(LMS_HOST_CACHE_PATH, "r") as f:
            data = json.load(f)
        host = data.get("lms_host")
        if host:
            log(f"Loaded cached LMS host: {host}")
            return host
    except Exception:
        pass
    return None


def save_cached_lms_host(host: str) -> None:
    try:
        with open(LMS_HOST_CACHE_PATH, "w") as f:
            json.dump({"lms_host": host}, f)
        log(f"Saved LMS host cache: {host}")
    except Exception as e:
        log(f"Failed to write LMS host cache: {e}")


def get_neighbor_ips() -> list[str]:
    """
    Return a list of IPs from ARP / neighbor tables.
    Prefer these "known" IPs before scanning the whole subnet.
    """
    candidates: set[str] = set()

    # On piCorePlayer, `ip` doesn't exist, so we just use `arp -n`
    for cmd in (["arp", "-n"],):
        try:
            out = subprocess.check_output(cmd, text=True)
        except Exception as e:
            log(f"Neighbor discovery via {cmd} failed: {e}")
            continue

        for line in out.splitlines():
            log(f"Checking line {line}")
            for token in line.split():
                # e.g. token = "(10.0.0.121)" → strip parens
                token_clean = token.strip("()")
                m = re.match(r"\d+\.\d+\.\d+\.\d+", token_clean)
                if m:
                    candidates.add(m.group(0))

    filtered = [
        ip for ip in candidates
        if ip.startswith("10.") or ip.startswith("192.168.") or ip.startswith("172.")
    ]
    log(f"Neighbor IPs discovered: {filtered}")
    return filtered



def get_local_subnet_ips() -> list[str]:
    """
    Return a list of IPs on the local /24 subnet based on our own IP.
    Used as a last resort (unknown IP scan).
    """
    local_ip = None
    try:
        out = subprocess.check_output(["ip", "-4", "addr", "show"], text=True)
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                cidr = line.split()[1]  # e.g. '10.0.0.121/24'
                ip, prefix = cidr.split("/")
                prefix = int(prefix)
                if ip.startswith(("10.", "192.168.", "172.")):
                    local_ip = ip
                    if prefix <= 24:
                        break
    except Exception as e:
        log(f"get_local_subnet_ips: failed to get local IP via ip addr: {e}")

    if not local_ip:
        log("get_local_subnet_ips: no local private IP found; skipping subnet scan")
        return []

    octets = local_ip.split(".")
    if len(octets) != 4:
        log(f"get_local_subnet_ips: invalid local IP {local_ip}")
        return []

    base = ".".join(octets[:3])  # treat as /24, e.g. 10.0.0.x
    ips = [f"{base}.{i}" for i in range(1, 255)]
    log(f"Local /24 subnet candidates: {base}.1-254")
    return ips


def discover_lms_host(current: str | None = None) -> str:
    """
    Determine the LMS host to use, trying in this order:
      1. Env var BIRDPI_LMS_HOST
      2. Cached host in config_lms_host.json
      3. Hostnames: 'birdpi-main', 'birdpi-main.local'
      4. Neighbor IPs
      5. Subnet scan on local /24

    On 'birdpi-main' itself, always return 'localhost'.
    """
    raw_hostname = socket.gethostname()
    short_hostname = raw_hostname.split(".")[0].lower()
    log(f"discover_lms_host: raw_hostname={raw_hostname}, short={short_hostname}")

    # On the actual LMS host, always talk to localhost
    if short_hostname == "birdpi-main":
        log("discover_lms_host: this is birdpi-main, using localhost")
        return "localhost"

    # 1. Env override
    env_host = os.environ.get("BIRDPI_LMS_HOST")
    if env_host:
        if is_lms_server(env_host):
            save_cached_lms_host(env_host)
            return env_host
        else:
            log(f"Env BIRDPI_LMS_HOST={env_host} did not respond as LMS")

    # 2. Cached host
    cached = load_cached_lms_host()
    if cached and cached != current:
        if is_lms_server(cached):
            return cached
        else:
            log(f"Cached LMS host {cached} is no longer valid")

    # 3. Hostnames
    for candidate in ("birdpi-main", "birdpi-main.local"):
        if candidate == current:
            continue
        try:
            if is_lms_server(candidate):
                save_cached_lms_host(candidate)
                return candidate
        except Exception as e:
            log(f"Hostname candidate {candidate} failed: {e}")

    # 4. Neighbor IPs (ARP)
    tried: set[str] = set()
    for ip in get_neighbor_ips():
        if ip == current:
            continue
        if ip in tried:
            continue
        tried.add(ip)
        if is_lms_server(ip):
            save_cached_lms_host(ip)
            return ip

    # 5. Subnet scan (unknown IPs)
    for ip in get_local_subnet_ips():
        if ip == current:
            continue
        if ip in tried:
            continue
        tried.add(ip)
        if is_lms_server(ip):
            save_cached_lms_host(ip)
            return ip

    log("discover_lms_host: no LMS host found via discovery; falling back")
    if current:
        return current
    return "birdpi-main"


# -------------------------------------------------------------------
# LMS host and ports
# -------------------------------------------------------------------
LMS_HOST = discover_lms_host(current=None)
LMS_CLI_PORT = 9090
LMS_WEB_PORT = 9000
log(f"Initial LMS_HOST: {LMS_HOST}")

# -------------------------------------------------------------------
# Import Bird core from bird.py
# -------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

try:
    from bird import Bird, manage_leds, load_config, cancel_current_song, _derive_bird_name
except Exception as e:
    log(f"FATAL: Could not import bird core: {e}")
    sys.exit(1)

DEFAULT_CONFIG = os.path.join(BASE_DIR, "../config_single_bird.json")
SONGS_CONFIG_PATH = os.path.join(BASE_DIR, "../config_multi_song_with_triggers.json")

pins_config = load_config(DEFAULT_CONFIG)
if pins_config is None:
    log(f"WARN: No pin config loaded from {DEFAULT_CONFIG}; GPIO pins may be undefined.")
else:
    log(f"Loaded pin config from {DEFAULT_CONFIG}")

songs_config = load_config(SONGS_CONFIG_PATH)
if songs_config is None:
    log(f"WARN: No songs config loaded from {SONGS_CONFIG_PATH}. Songs may not map to titles.")
else:
    log(f"Loaded songs config from {SONGS_CONFIG_PATH}")

# -------------------------------------------------------------------
# Bird instance and current song state
# -------------------------------------------------------------------
bird_instance_lock = threading.Lock()
bird_instance: Bird | None = None

current_song_lock = threading.Lock()
current_song_name: str | None = None
current_player_id: str | None = None
current_led_thread: threading.Thread | None = None


def get_or_create_bird() -> Bird:
    global bird_instance
    with bird_instance_lock:
        if bird_instance is None:
            hostname = socket.gethostname()
            bird_name = _derive_bird_name(hostname)
            beak_pin = pins_config.get("beak") if pins_config else None
            body_pin = pins_config.get("body") if pins_config else None
            spotlight_pin = pins_config.get("light") if pins_config else None
            log(f"Creating Bird instance name={bird_name}, beak={beak_pin}, body={body_pin}, light={spotlight_pin}")
            bird_instance = Bird(
                name=bird_name,
                beak_led_pin=beak_pin,
                body_led_pin=body_pin,
                spotlight_led_pin=spotlight_pin,
            )
        return bird_instance


def select_song_for_title(title_norm: str) -> dict | None:
    """
    Given a normalized title (spaces -> underscores), return the matching song dict
    from songs_config["songs"].
    """
    if not songs_config:
        return None
    try:
        songs = songs_config.get("songs", [])
        log(f"select_song_for_title.songs={songs}")
        for s in songs:
            if str(s.get("name", "")).lower() == title_norm.lower():
                return s
    except Exception as e:
        log(f"select_song_for_title: error scanning songs_config: {e}")
    return None


def parse_status_json(status_obj: dict) -> tuple[str | None, float | None, float | None]:
    """
    Parse LMS JSON-RPC "status" result:
      - normalized title (spaces -> underscores)
      - time (float)
      - duration (float)
    Returns (title_norm_or_None, time_or_None, duration_or_None)
    """
    if not status_obj:
        return None, None, None

    result = status_obj.get("result", {})
    playlist = result.get("playlist_loop", [])
    title = ""
    if playlist and isinstance(playlist, list):
        title = str(playlist[0].get("title", "") or "")
    title_norm = title.replace(" ", "_") if title else None

    def to_float(val):
        if val is None or val == "":
            return None
        try:
            return float(val)
        except Exception:
            return None

    time_val = to_float(result.get("time"))
    duration_val = to_float(result.get("duration"))
    log(f"parse_status_json: title_norm={title_norm}, time={time_val}, duration={duration_val}")
    return title_norm, time_val, duration_val


def fetch_current_track_status(player_id: str) -> tuple[str | None, float | None, float | None]:
    """
    Call LMS JSON-RPC 'status' for a given player and extract title/time/duration.
    """
    conn = http.client.HTTPConnection(LMS_HOST, LMS_WEB_PORT, timeout=3)
    try:
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [player_id, ["status", "-", "1", "tags:u"]],
        }
        body = json.dumps(payload)
        conn.request("POST", "/jsonrpc.js", body=body, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = resp.read()
        if resp.status != 200:
            raise RuntimeError(f"JSON-RPC status {resp.status}: {data!r}")
        doc = json.loads(data.decode("utf-8"))
        return parse_status_json(doc)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def stop_current_song():
    """
    Stop the current LED animation/song using bird.py's cancel_current_song().
    """
    global current_song_name, current_player_id, current_led_thread
    with current_song_lock:
        if current_song_name is None:
            log("stop_current_song: no active song to stop")
            return
        log(f"Stopping current song: {current_song_name} (player={current_player_id})")
        try:
            cancel_current_song()
            b = get_or_create_bird()
            b.stop_moving()
        except Exception as e:
            log(f"Error while stopping current song: {e}")
        current_song_name = None
        current_player_id = None
        current_led_thread = None


def start_song_from_status(player_id: str):
    """
    Fetch status for the given player, map the title to a song, and start LEDs.
    """
    global current_song_name, current_player_id, current_led_thread

    log(f"start_song_from_status: player={player_id}")
    if songs_config is None:
        log("No songs_config loaded; cannot map title to a song.")
        return

    try:
        title_norm, time_val, duration_val = fetch_current_track_status(player_id)
    except Exception as e:
        log(f"Error fetching track status via JSON-RPC: {e}")
        return

    if not title_norm:
        log("No title returned for current track; cannot start song.")
        return

    song_dict = select_song_for_title(title_norm)
    log(f"song_dict={song_dict}")
    if not song_dict:
        log(f"No song config found for title_norm='{title_norm}'")
        return

    with current_song_lock:
        log("with current_song_lock")
        if current_song_name == title_norm and current_player_id == player_id:
            log(f"Song {title_norm} already active for player {player_id}; ignoring duplicate event.")
            return

        # Stop any previous song
        stop_current_song()

        try:
            b = get_or_create_bird()
            b.prepare_song(song_dict)

            # Compute fallback duration from intervals
            max_singing = max((num for pair in b.speech_intervals for num in pair), default=0)
            max_dancing = max((num for pair in b.dancing_intervals for num in pair), default=0)
            interval_duration = max(max_singing, max_dancing)

            # Prefer explicit duration from LMS
            if duration_val is not None and duration_val > 0:
                audio_duration = duration_val
            else:
                audio_duration = interval_duration

            if audio_duration <= 0:
                log("Computed non-positive audio_duration; skipping LED management.")
                return

            start_offset = time_val if (time_val is not None and time_val > 0) else 0.0

            log(
                f"Starting song '{title_norm}' for player {player_id} "
                f"audio_duration={audio_duration}, start_offset={start_offset}"
            )

            led_thread = threading.Thread(
                target=manage_leds,
                args=([b], audio_duration),
                kwargs={"start_offset": start_offset},
                daemon=True,
            )
            led_thread.start()

            current_song_name = title_norm
            current_player_id = player_id
            current_led_thread = led_thread

        except Exception as e:
            log(f"Error starting song {title_norm} for player {player_id}: {e}")
            current_song_name = None
            current_player_id = None
            current_led_thread = None


# -------------------------------------------------------------------
# LMS CLI subscription loop
# -------------------------------------------------------------------
def subscribe_loop():
    """
    Connects to LMS CLI, subscribes to playlist events, and reacts to:
      - playlist newsong  -> start_song_from_status()
      - playlist open ... -> start_song_from_status() (early)
      - playlist stop/jump -> stop_current_song()
    """
    global LMS_HOST

    while True:
        try:
            log(f"Connecting to LMS CLI {LMS_HOST}:{LMS_CLI_PORT}")
            sock = socket.create_connection((LMS_HOST, LMS_CLI_PORT), timeout=5)
            sock.settimeout(None)
            f = sock.makefile("rwb", buffering=0)

            # Subscribe to playlist events
            cmd = b"subscribe playlist\n"
            log(f"Sending CLI subscribe command: {cmd!r}")
            f.write(cmd)
            f.flush()

            line = f.readline()
            if not line:
                raise RuntimeError("No subscribe response from LMS")
            log(f"subscribe response: {line.decode().strip()}")

            # Event loop
            while True:
                line = f.readline()
                if not line:
                    raise RuntimeError("CLI connection closed")
                raw = line.decode("utf-8").strip()
                if not raw:
                    continue

                try:
                    decoded = urllib.parse.unquote(raw)
                except Exception:
                    decoded = raw

                # Example: "2c:cf:67:f8:c7:15 playlist newsong 5"
                parts = decoded.split(" ", 2)
                if len(parts) < 2:
                    continue

                player_id = parts[0]   # MAC address
                rest = parts[1:]
                if len(rest) < 2:
                    log(f"Ignoring CLI line without command: {parts}")
                    continue

                event_group = rest[0]   # e.g. "playlist"
                event_cmd_full = rest[1]  # e.g. "newsong", "open file://...", "stop", "jump", etc.

                if event_group != "playlist":
                    continue

                if event_cmd_full == "newsong":
                    start_song_from_status(player_id)
                elif event_cmd_full.startswith("open "):
                    # We could parse filename from here, but we just call status()
                    start_song_from_status(player_id)
                elif event_cmd_full in ("stop", "jump"):
                    stop_current_song()

        except Exception as e:
            log(f"subscribe_loop error: {e}, reconnecting in 5s")
            msg = str(e)
            # If this looks like DNS / network error, re-discover LMS host
            if isinstance(e, socket.gaierror) or "Name or service not known" in msg or "Network is unreachable" in msg:
                old = LMS_HOST
                LMS_HOST = discover_lms_host(current=old)
                log(f"Updated LMS_HOST from {old} to {LMS_HOST} after error")
            time.sleep(5)


# -------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------
if __name__ == "__main__":
    try:
        log("bird_daemon starting subscribe_loop")
        subscribe_loop()
    except KeyboardInterrupt:
        log("bird_daemon interrupted by user")
    except Exception as e:
        log(f"bird_daemon crashed: {e}")
    finally:
        try:
            _log.close()
        except Exception:
            pass
