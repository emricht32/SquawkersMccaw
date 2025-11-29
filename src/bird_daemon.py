#!/usr/bin/env python3
"""
bird_daemon.py

Single long-lived daemon that:
- Connects to LMS CLI
- Subscribes to playlist events
- Fetches full player status via JSON-RPC
- Drives local Bird GPIO/LEDs via your existing bird.py core

Runs on:
- LMS server Pi (birdpi-main): talks to LMS at localhost
- Any piCorePlayer/BirdPi node: talks to LMS at birdpi-main.local

No per-node config required.
"""

import os
import sys
import socket
import time
import json
import threading
import urllib.parse
import http.client
from datetime import datetime

# -------------------------------------------------------------------
# Logging (simple, one file for the daemon)
# -------------------------------------------------------------------
PRIMARY_LOG_DIR = "/mnt/mmcblk0p2/tc/birdpi-logs"
LOG_FILENAME = "daemon.log"


def _open_log():
    try:
        # Try primary Pi path
        os.makedirs(PRIMARY_LOG_DIR, exist_ok=True)
        path = os.path.join(PRIMARY_LOG_DIR, LOG_FILENAME)
        f = open(path, "a", buffering=1)
        f.write(f"[{datetime.now().isoformat()}] bird_daemon logger started in {PRIMARY_LOG_DIR}\n")
        return f
    except Exception as e:
        # IMPORTANT: real stdout, so you see this even before logger is set up
        sys.__stdout__.write(
            f"[bird_daemon] WARNING: Could not create log directory '{PRIMARY_LOG_DIR}': {e}\n"
        )
        sys.__stdout__.write("[bird_daemon] Falling back to console logging only.\n")
        sys.__stdout__.flush()
        # From now on, log() will write to stdout
        return sys.__stdout__


_log = _open_log()


def log(msg: str):
    ts = datetime.now().isoformat()
    try:
        _log.write(f"[{ts}] {msg}\n")
    except Exception:
        # Best-effort only; don't crash on logging
        pass


# -------------------------------------------------------------------
# Make sure user site-packages (gpiozero, etc.) are visible
# -------------------------------------------------------------------
USER_SITE = "/home/tc/.local/lib/python3.11/site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.append(USER_SITE)
    log(f"Added USER_SITE to sys.path: {USER_SITE}")

# -------------------------------------------------------------------
# Auto-detect LMS host based on our hostname
# -------------------------------------------------------------------
raw_hostname = socket.gethostname()
short_hostname = raw_hostname.split(".")[0].lower()

if short_hostname == "birdpi-main":
    LMS_HOST = "localhost"
else:
    LMS_HOST = "birdpi-main"

LMS_CLI_PORT = 9090
LMS_WEB_PORT = 9000

log(f"Host detected as '{raw_hostname}', short='{short_hostname}', LMS_HOST='{LMS_HOST}'")

# Optional: filter to only handle events for the local player.
# We'll use the player name from LMS status and compare to our hostname.
# Set to None for "handle any player".
PLAYER_NAME_FILTER = None  # or short_hostname for strict per-node filtering

# -------------------------------------------------------------------
# Import bird core logic
# -------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

try:
    from bird import (
        Bird,
        manage_leds,
        load_config,
        _derive_bird_name,
        cancel_current_song,
        keep_playing,  # global bool in bird.py
    )
    log("Imported bird core successfully")
except Exception as e:
    log(f"FATAL: Failed to import bird core: {e}")
    sys.exit(1)

# -------------------------------------------------------------------
# One Bird instance per node, initialized once
# -------------------------------------------------------------------
default_config = os.path.join(BASE_DIR, "../config_single_bird.json")
songs_path = os.path.join(BASE_DIR, "../config_multi_song_with_triggers.json")

pins_config = load_config(default_config)
if pins_config is None:
    log(f"WARN: No pin config loaded from {default_config}; GPIO pins may be undefined.")
else:
    log(f"Loaded pin config from {default_config}")

# songs_config may be None; we handle that later
try:
    with open(songs_path, "r", encoding="utf-8") as f:
        songs_config = json.load(f)
    log(f"Loaded songs config from {songs_path}")
except Exception as e:
    songs_config = None
    log(f"WARN: Could not load songs config {songs_path}: {e}")

_hostname = socket.gethostname()
bird_name = _derive_bird_name(_hostname)
beak_pin = pins_config.get("beak") if pins_config else None
body_pin = pins_config.get("body") if pins_config else None
spotlight_pin = pins_config.get("light") if pins_config else None

bird_instance = Bird(
    name=bird_name,
    beak_led_pin=beak_pin,
    body_led_pin=body_pin,
    spotlight_led_pin=spotlight_pin,
)
log(f"Created Bird instance for '{bird_name}' with beak={beak_pin}, body={body_pin}, light={spotlight_pin}")

_current_thread = None
_thread_lock = threading.Lock()

# Track what song is currently considered "playing" on this node
current_song_key = None          # e.g. "2c:cf:67:f8:c7:15:happy_birthday"
current_song_start_ts = 0.0      # wall-clock when this play started (LMS-aligned if possible)
current_song_end_ts = 0.0        # wall-clock when this play should end


# -------------------------------------------------------------------
# JSON-RPC helpers
# -------------------------------------------------------------------
def call_lms_status(player_id: str, tags: str = "cgtAsRbehldrtyrSuKN") -> dict:
    """
    Call LMS /jsonrpc.js for 'status' on a specific player_id (MAC address).
    Returns the parsed JSON dict (full JSON-RPC response).
    """
    conn = http.client.HTTPConnection(LMS_HOST, LMS_WEB_PORT, timeout=5)
    payload = {
        "id": 1,
        "method": "slim.request",
        "params": [
            player_id,
            ["status", "-", "1", f"tags:{tags}"],
        ],
    }
    body = json.dumps(payload)
    headers = {"Content-Type": "application/json"}
    conn.request("POST", "/jsonrpc.js", body, headers)
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", errors="ignore")
    conn.close()

    if resp.status != 200:
        raise RuntimeError(f"LMS HTTP status {resp.status}: {data[:200]}")

    try:
        j = json.loads(data)
    except Exception as e:
        raise RuntimeError(f"Failed to parse LMS JSON-RPC response: {e}, data={data[:200]}")

    return j


def extract_song_from_open_cmd(cmd: str) -> str | None:
    """
    Given playlist 'open file:///path/to/song.mp3',
    extract 'song' (basename without extension).
    """
    # Example input: "open file:///mnt/.../happy_birthday/happy_birthday.mp3"
    parts = cmd.split(" ", 1)
    if len(parts) != 2:
        return None

    url = parts[1].strip()
    if url.startswith("file://"):
        url = url[len("file://"):]
    else:
        return None

    # URL-decode just in case
    path = urllib.parse.unquote(url)

    # Extract filename
    filename = os.path.basename(path)
    if not filename:
        return None

    # Remove extension
    song, ext = os.path.splitext(filename)
    return song or None


def extract_status_core(result_obj: dict) -> tuple[str | None, float | None, float | None, str | None]:
    """
    Given the 'result' portion of an LMS JSON-RPC status response,
    extract:
      - normalized song title (spaces -> underscores)
      - time (float or None)
      - duration (float or None)
      - player_name (string or None)
    """
    # playlist_loop[0].title
    title = ""
    playlist = result_obj.get("playlist_loop", [])
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

    time_val = to_float(result_obj.get("time"))
    duration_val = to_float(result_obj.get("duration"))
    player_name = result_obj.get("player_name")

    return title_norm, time_val, duration_val, player_name


# -------------------------------------------------------------------
# Song tracking helpers
# -------------------------------------------------------------------
def is_same_song_still_playing(track_key: str, now_ts: float) -> bool:
    """
    Returns True if we believe the same song (track_key) is currently
    playing on this node & hasn't passed its expected end time yet.
    """
    global current_song_key, current_song_end_ts
    if current_song_key != track_key:
        return False
    if current_song_end_ts <= 0:
        return False
    return now_ts <= current_song_end_ts


# -------------------------------------------------------------------
# Bird / LED control
# -------------------------------------------------------------------
def stop_current_song():
    global _current_thread, current_song_key, current_song_start_ts, current_song_end_ts
    with _thread_lock:
        if _current_thread and _current_thread.is_alive():
            log("Stopping current song via cancel_current_song()")
            try:
                cancel_current_song()
                _current_thread.join(timeout=1.0)
            except Exception as e:
                log(f"Error while stopping current song: {e}")
        _current_thread = None
        current_song_key = None
        current_song_start_ts = 0.0
        current_song_end_ts = 0.0


def handle_newsong(player_id: str):
    """
    Generic backup handler for 'newsong' events when we
    DIDN'T already get a filename from 'open'.
    """
    global _current_thread, keep_playing, songs_config
    global current_song_key, current_song_start_ts, current_song_end_ts

    try:
        j = call_lms_status(player_id)
        log(f"call_lms_status (newsong).j={j}")
    except Exception as e:
        log(f"call_lms_status failed for {player_id}: {e}")
        return

    result = j.get("result") or {}
    title_norm, time_val, duration_val, player_name = extract_status_core(result)
    playlist_ts = result.get("playlist_timestamp")

    log(
        f"Status (newsong) for player_id={player_id}, player_name={player_name}, "
        f"title={title_norm}, time={time_val}, duration={duration_val}, playlist_timestamp={playlist_ts}"
    )

    # Filter by player_name so each node only reacts to its own player
    if PLAYER_NAME_FILTER and player_name:
        if player_name.lower() != PLAYER_NAME_FILTER.lower():
            log(f"Ignoring newsong: player_name '{player_name}' != filter '{PLAYER_NAME_FILTER}'")
            return

    if not title_norm:
        log("No title_norm in status; cannot resolve song config.")
        return

    track_key = f"{player_id}:{title_norm}"
    now_ts = time.time()

    # Ignore if same song is already marked as playing
    if is_same_song_still_playing(track_key, now_ts):
        log(
            f"Ignoring newsong: same song '{track_key}' already marked as playing "
            f"(now={now_ts:.3f}, end={current_song_end_ts:.3f})"
        )
        return

    # Match song config
    selected_song_dict = None
    if songs_config:
        try:
            songs = songs_config.get("songs", [])
            matches = [s for s in songs if s.get("name", "").lower() == title_norm.lower()]
            if matches:
                selected_song_dict = matches[0]
            else:
                log(f"Song '{title_norm}' not found in config; continuing without intervals.")
        except Exception as e:
            log(f"Error searching songs config: {e}")

    bird_instance.prepare_song(selected_song_dict)

    # Determine audio_duration
    if duration_val and duration_val > 0:
        audio_duration = duration_val
    else:
        intervals = bird_instance.speech_intervals + bird_instance.dancing_intervals
        audio_duration = max((t for pair in intervals for t in pair), default=0)
    if audio_duration <= 0:
        log("No positive audio_duration; not starting LEDs (newsong).")
        return

    # Offset calculation (same logic as filename path, but using title_norm)
    start_offset = 0.0
    offset_source = "default_zero"

    try:
        if playlist_ts is not None:
            playlist_ts_f = float(playlist_ts)
            now_ts_pre_thread = time.time()
            start_offset = max(now_ts_pre_thread - playlist_ts_f, 0.0)
            offset_source = "playlist_timestamp"
            actual_start_ts = playlist_ts_f
            log(
                f"[newsong] Offset from playlist_timestamp: now={now_ts_pre_thread:.3f}, "
                f"playlist_ts={playlist_ts_f:.3f}, start_offset={start_offset:.3f}"
            )
        elif time_val is not None and time_val > 0:
            start_offset = time_val
            offset_source = "status_time"
            now_ts_pre_thread = time.time()
            actual_start_ts = max(now_ts_pre_thread - time_val, 0.0)
            log(
                f"[newsong] Offset from status time_val: time_val={time_val:.3f}, "
                f"now={now_ts_pre_thread:.3f}, start_offset={start_offset:.3f}"
            )
        else:
            now_ts_pre_thread = time.time()
            actual_start_ts = now_ts_pre_thread
            log("[newsong] No playlist_timestamp or time_val; starting from offset=0.0")
    except Exception as e:
        log(f"Error computing offset/start_ts (newsong): {e}")
        now_ts_pre_thread = time.time()
        actual_start_ts = now_ts_pre_thread
        start_offset = 0.0
        offset_source = "fallback_zero"

    new_end_ts = actual_start_ts + audio_duration

    log(
        f"[newsong] Starting LEDs: song={title_norm}, duration={audio_duration:.3f}, "
        f"start_offset={start_offset:.3f} (source={offset_source}), "
        f"start_ts={actual_start_ts:.3f}, end_ts={new_end_ts:.3f}"
    )

    stop_current_song()
    keep_playing = True

    current_song_key = track_key
    current_song_start_ts = actual_start_ts
    current_song_end_ts = new_end_ts

    t = threading.Thread(
        target=manage_leds,
        args=([bird_instance], audio_duration),
        kwargs={"start_offset": start_offset},
        daemon=True,
    )
    with _thread_lock:
        _current_thread = t
    t.start()


def handle_newsong_from_filename(song_name: str, player_id: str):
    """
    Kick off LEDs as soon as we know the song name from 'open'.
    Uses JSON-RPC to get timing info, computes an offset from playlist_timestamp,
    and ignores duplicate triggers for the same song while it's still playing.
    """
    global _current_thread, keep_playing, songs_config
    global current_song_key, current_song_start_ts, current_song_end_ts

    log(f"handle_newsong_from_filename: song '{song_name}'")

    # Fetch LMS status to get time, duration, playlist_timestamp, etc.
    try:
        j = call_lms_status(player_id)
        log(f"call_lms_status (newsong).j={j}")
    except Exception as e:
        log(f"call_lms_status failed for {player_id}: {e}")
        return

    result = j.get("result") or {}
    status_title_norm, time_val, duration_val, player_name = extract_status_core(result)
    playlist_ts = result.get("playlist_timestamp")

    log(
        f"Filename-based trigger — LMS status: "
        f"title={status_title_norm}, time={time_val}, duration={duration_val}, "
        f"playlist_timestamp={playlist_ts}, player_name={player_name}"
    )

    # Optionally restrict to a single player_name
    if PLAYER_NAME_FILTER and player_name:
        if player_name.lower() != PLAYER_NAME_FILTER.lower():
            log(
                f"Ignoring filename-based event: player_name '{player_name}' "
                f"!= filter '{PLAYER_NAME_FILTER}'"
            )
            return

    # Use filename-based normalized name as our key
    title_norm = song_name.replace(" ", "_")
    track_key = f"{player_id}:{title_norm}"
    now_ts = time.time()

    # Ignore if same song is already marked as playing
    if is_same_song_still_playing(track_key, now_ts):
        log(
            f"Ignoring trigger: same song '{track_key}' is already marked as playing "
            f"(now={now_ts:.3f}, end={current_song_end_ts:.3f})"
        )
        return

    # Match song config
    selected_song_dict = None
    if songs_config:
        try:
            songs = songs_config.get("songs", [])
            matches = [s for s in songs if s.get("name", "").lower() == title_norm.lower()]
            if matches:
                selected_song_dict = matches[0]
            else:
                log(f"Song '{title_norm}' not found in config; continuing without intervals.")
        except Exception as e:
            log(f"Error searching songs config: {e}")

    bird_instance.prepare_song(selected_song_dict)

    # Determine audio_duration
    if duration_val and duration_val > 0:
        audio_duration = duration_val
    else:
        intervals = bird_instance.speech_intervals + bird_instance.dancing_intervals
        audio_duration = max((t for pair in intervals for t in pair), default=0)
    if audio_duration <= 0:
        log("No positive audio_duration; not starting LEDs.")
        return

    # Offset calculation using playlist_timestamp when possible
    start_offset = 0.0
    offset_source = "default_zero"

    try:
        if playlist_ts is not None:
            playlist_ts_f = float(playlist_ts)
            now_ts_pre_thread = time.time()
            start_offset = max(now_ts_pre_thread - playlist_ts_f, 0.0)
            offset_source = "playlist_timestamp"
            actual_start_ts = playlist_ts_f
            log(
                f"Offset from playlist_timestamp: now={now_ts_pre_thread:.3f}, "
                f"playlist_ts={playlist_ts_f:.3f}, start_offset={start_offset:.3f}"
            )
        elif time_val is not None and time_val > 0:
            start_offset = time_val
            offset_source = "status_time"
            now_ts_pre_thread = time.time()
            actual_start_ts = max(now_ts_pre_thread - time_val, 0.0)
            log(
                f"Offset from status time_val: time_val={time_val:.3f}, "
                f"now={now_ts_pre_thread:.3f}, start_offset={start_offset:.3f}"
            )
        else:
            now_ts_pre_thread = time.time()
            actual_start_ts = now_ts_pre_thread
            log("No playlist_timestamp or time_val; starting from offset=0.0")
    except Exception as e:
        log(f"Error computing offset/start_ts from playlist_timestamp/time: {e}")
        now_ts_pre_thread = time.time()
        actual_start_ts = now_ts_pre_thread
        start_offset = 0.0
        offset_source = "fallback_zero"

    new_end_ts = actual_start_ts + audio_duration

    log(
        f"Starting LEDs early: song={song_name}, duration={audio_duration:.3f}, "
        f"start_offset={start_offset:.3f} (source={offset_source}), "
        f"start_ts={actual_start_ts:.3f}, end_ts={new_end_ts:.3f}"
    )

    # Stop any currently-running animation
    stop_current_song()
    keep_playing = True

    # Record new 'current song' state
    current_song_key = track_key
    current_song_start_ts = actual_start_ts
    current_song_end_ts = new_end_ts

    # Fire LEDs
    t = threading.Thread(
        target=manage_leds,
        args=([bird_instance], audio_duration),
        kwargs={"start_offset": start_offset},
        daemon=True,
    )
    with _thread_lock:
        _current_thread = t
    t.start()


# -------------------------------------------------------------------
# LMS CLI subscription loop
# -------------------------------------------------------------------
def subscribe_loop():
    """
    Connects to LMS CLI, subscribes to playlist events, and reacts to:
      - 'playlist open ...' via handle_newsong_from_filename (early)
      - 'playlist newsong ...' via handle_newsong (backup)
      - 'playlist stop' or 'playlist jump' via stop_current_song
    """
    while True:
        try:
            log(f"Connecting to LMS CLI {LMS_HOST}:{LMS_CLI_PORT}")
            sock = socket.create_connection((LMS_HOST, LMS_CLI_PORT), timeout=5)
            # Once connected, block indefinitely while waiting for events
            sock.settimeout(None)
            f = sock.makefile("rwb", buffering=0)

            # subscribe to playlist events
            cmd = "subscribe playlist\n".encode("utf-8")
            f.write(cmd)

            # read subscribe response
            line = f.readline()
            if not line:
                raise RuntimeError("No subscribe response from LMS")
            log(f"subscribe response: {line.decode().strip()}")

            # main event loop
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

                # Example: "2c:cf:67:f8:c7:15 playlist newsong ..."
                parts = decoded.split(" ", 2)
                if len(parts) < 2:
                    continue

                player_id = parts[0]   # MAC address
                rest = parts[1:]
                if len(rest) < 2:
                    log(f"Ignoring CLI line without command: parts={parts}")
                    continue

                event_group = rest[0]   # e.g. 'playlist'
                event_cmd = rest[1]     # e.g. 'open file://...', 'newsong ...', 'stop', 'jump', etc.

                log(f"decoded_line={decoded}")
                log(f"parts={parts}")

                if event_group == "playlist":
                    # STOP / SKIP handling
                    if event_cmd.startswith("stop") or event_cmd.startswith("jump"):
                        log(f"Playlist stop/skip detected for player_id={player_id} → stopping LEDs")
                        stop_current_song()
                        continue

                    # EARLY TRIGGER ON OPEN
                    if event_cmd.startswith("open "):
                        song = extract_song_from_open_cmd(event_cmd)
                        if song:
                            log(f"EARLY: playlist open detected for player_id={player_id}, song={song}")
                            handle_newsong_from_filename(song, player_id)
                        else:
                            log(f"Could not extract song from cmd: '{event_cmd}'")
                        continue

                    # # BACKUP: NEWSPLIT (late / extra event)
                    # if event_cmd.startswith("newsong"):
                    #     log(f"Received playlist newsong for player_id={player_id}")
                    #     handle_newsong(player_id)

        except Exception as e:
            log(f"subscribe_loop error: {e}, reconnecting in 5s")
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
