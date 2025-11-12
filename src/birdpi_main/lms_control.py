"""LMS (Logitech Media Server) control and per-bird volume scheduling.

Each bird Pi runs Squeezelite (piCorePlayer). A single master track plays
on all players; we adjust per-player volume so only active speakers are
audible during their singing intervals.

Inputs:
    - song['lms_track']: LMS-accessible path/URL
    - song['individuals']: list of { name, singing: [[start,end], ...] }

Dynamic Mapping:
    The caller passes a bird_player_map (bird name -> player MAC) built
    dynamically from node registration; no static config required.

Volume Strategy:
    baseline -> speaking_volume during interval -> baseline after.
    Overlapping intervals allow multiple speakers simultaneously.

Threading:
    A scheduler thread emits volume changes at computed times relative
    to agreed start_time.
"""

from __future__ import annotations
import socket
import time
import threading
from typing import Dict, List, Tuple

# Default LMS connection settings (override via environment or caller args)
LMS_HOST = "localhost"  # Change to your LMS host/IP
LMS_PORT = 9090


def _lms_cmd(cmd: str, host: str = LMS_HOST, port: int = LMS_PORT) -> str:
    """Send a single CLI command to LMS and return raw response.

    Docs: https://wiki.slimdevices.com/index.php/CLI
    Commands typically look like: <player_id> playlist add <url>
    """
    # NOTE: LMS responses can be longer; we do a simple single recv for brevity.
    # For production robustness, loop until newline or socket close.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        s.sendall((cmd + "\n").encode())
        try:
            return s.recv(8192).decode(errors="ignore")
        except Exception:
            return ""


def _set_volume(player_id: str, volume: int):
    """Set absolute volume (0-100) for a player."""
    _lms_cmd(f"{player_id} mixer volume {volume}")


def _clear_and_queue_track(player_id: str, track_ref: str):
    _lms_cmd(f"{player_id} playlist clear")
    _lms_cmd(f"{player_id} playlist add {track_ref}")


def _play(player_id: str):
    _lms_cmd(f"{player_id} play")


def _parse_singing_intervals(song: dict) -> Dict[str, List[Tuple[float, float]]]:
    """Return mapping bird_name -> list of (start,end) singing intervals.
    Assumes song["individuals"][i]["singing"] format as used elsewhere.
    """
    result: Dict[str, List[Tuple[float, float]]] = {}
    for indiv in song.get("individuals", []):
        name = indiv.get("name")
        intervals = []
        for rng in indiv.get("singing", []):
            if isinstance(rng, (list, tuple)) and len(rng) == 2:
                start, end = rng
                try:
                    start_f, end_f = float(start), float(end)
                    if end_f >= start_f:
                        intervals.append((start_f, end_f))
                except (TypeError, ValueError):
                    continue
        if intervals:
            result[name] = intervals
    return result


def play_song_with_volume_schedule(
    song: dict,
    start_time: float,
    bird_player_map: Dict[str, str],
    speaking_volume: int = 80,
    background_volume: int = 20,
    muted_volume: int = 0,
    use_background: bool = True,
):
    """Begin LMS playback of a master track & schedule per-bird volume changes.

    Parameters
    ----------
    song: dict
        Song dict containing at least "lms_track" and "individuals".
    start_time: float
        Epoch seconds when playback & movement should align.
    bird_player_map: Dict[str,str]
        Maps bird names to LMS player IDs (MAC addresses).
    speaking_volume: int
        Volume when bird is speaking.
    background_volume: int
        Volume when bird is idle (if use_background True).
    muted_volume: int
        Volume used when bird is idle (if use_background False).
    use_background: bool
        If False, birds are fully muted (muted_volume) when not speaking.
    """

    track_ref = song.get("lms_track")
    if not track_ref:
        print("⚠️ No 'lms_track' defined in song; aborting LMS playback.")
        return

    intervals_map = _parse_singing_intervals(song)
    print("Parsed singing intervals:", intervals_map)

    # Load track on each player first so buffers are ready.
    for bird_name, player_id in bird_player_map.items():
        _clear_and_queue_track(player_id, track_ref)

    # Pre-set baseline. (Either quiet background or muted.)
    base_volume = background_volume if use_background else muted_volume
    for player_id in bird_player_map.values():
        _set_volume(player_id, base_volume)

    # Start playback slightly before start_time to ensure first audio samples align.
    lead = 0.3  # seconds of preroll; tweak experimentally
    now = time.time()
    delay_to_play = start_time - lead - now
    if delay_to_play > 0:
        time.sleep(delay_to_play)
    for player_id in bird_player_map.values():
        _play(player_id)

    # Scheduler thread for volume events
    def scheduler():
        # Build unified event list: (event_time, bird_name, volume)
        events: List[Tuple[float, str, int]] = []
        for bird_name, intervals in intervals_map.items():
            player_id = bird_player_map.get(bird_name)
            if not player_id:
                continue
            for (rel_start, rel_end) in intervals:
                speak_start = start_time + rel_start
                speak_end = start_time + rel_end
                events.append((speak_start, bird_name, speaking_volume))
                # Revert after end
                events.append((speak_end, bird_name, base_volume))
        # Sort chronologically
        events.sort(key=lambda e: e[0])
        print("Scheduling volume events:", events)
        for evt_time, bird_name, vol in events:
            remaining = evt_time - time.time()
            if remaining > 0:
                time.sleep(remaining)
            player_id = bird_player_map.get(bird_name)
            if player_id:
                _set_volume(player_id, vol)
                print(f"[LMS] {bird_name} -> volume {vol} at {time.time():.3f}")
        print("All scheduled volume events completed.")

    threading.Thread(target=scheduler, daemon=True).start()
    print("✅ LMS playback initiated & volume scheduler started.")


__all__ = [
    "play_song_with_volume_schedule",
]
