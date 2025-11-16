#!/usr/bin/env python3
# piCorePlayer Event Listener Plugin Script
# Logs all activity to /mnt/mmcblk0p2/tc/birdpi-logs/event_listener.log

import sys
import os
import subprocess
import json
from datetime import datetime
from typing import List

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

# Location of bird.py
BIRD_PY_PATH = os.path.join(os.path.dirname(__file__), "../../src/common/bird.py")

# Log file location (SD card, NOT RAM)
LOG_DIR = "/mnt/mmcblk0p2/tc/birdpi-logs"
LOG_FILE = os.path.join(LOG_DIR, "event_listener.log")

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)


# -------------------------------------------------------------------
# Logging helper
# -------------------------------------------------------------------

def log(msg: str):
    """Append timestamped log message to log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")


# -------------------------------------------------------------------
# CLI argument translation
# -------------------------------------------------------------------

def build_args_from_event(raw_args: List[str]) -> List[str]:
    """Translate piCorePlayer event listener arguments into bird.py CLI args."""
    if not raw_args:
        return []

    event_type = raw_args[0].upper()
    rest = raw_args[1:]
    cli_args: List[str] = []

    if event_type == "SONG_START":
        if rest:
            if rest[0].startswith("--song"):
                cli_args.extend(rest)
            else:
                cli_args.extend(["--song", rest[0]])

    elif event_type == "SONG_STOP":
        # Placeholder for cancellation
        pass

    else:
        cli_args.extend(rest)

    return cli_args

def parseName(d: dict) -> str:
    """
    Returns the title of the first song in the playlist_loop.
    If not found, returns an empty string.
    """
    try:
        playlist = d.get("playlist_loop", [])
        if playlist and isinstance(playlist, list):
            first = playlist[0]
            return first.get("title", "")
    except Exception:
        pass
    return ""


# -------------------------------------------------------------------
# Main execution
# -------------------------------------------------------------------

if __name__ == "__main__":
    raw_args = sys.argv[1:]
    bird_cli_args = build_args_from_event(raw_args)
    name = parseName(bird_cli_args)
    cmd = ["python3", BIRD_PY_PATH, name]

    # Log the incoming event
    log(f"Invoked with raw_args={raw_args}, translated_args={bird_cli_args}")
    log(f"Running command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Log output
        if result.stdout:
            log(f"stdout: {result.stdout.strip()}")

        if result.stderr:
            log(f"stderr: {result.stderr.strip()}")

        log(f"Exit code: {result.returncode}")

        sys.exit(result.returncode)

    except FileNotFoundError:
        msg = f"bird.py not found at {BIRD_PY_PATH}"
        log(msg)
        print(msg, file=sys.stderr)
        sys.exit(127)

    except Exception as e:
        err = f"Error running bird.py: {e}"
        log(err)
        print(err, file=sys.stderr)
        sys.exit(1)
