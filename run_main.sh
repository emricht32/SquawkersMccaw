#!/bin/sh
set -e

# TinyCore / piCorePlayer optimized launcher for BirdPi master.
# Minimizes RAM usage by installing Python packages to persistent storage.

INSTALL_FLAG=false
FORCE_REINSTALL=false
for arg in "$@"; do
  [ "$arg" = "--install" ] && INSTALL_FLAG=true
  [ "$arg" = "--force-reinstall" ] && FORCE_REINSTALL=true
done

HOSTNAME="$(hostname)"
MASTER_HOST="birdpi-master"
if [ "$HOSTNAME" != "$MASTER_HOST" ]; then
  echo "[run_main] Warning: Hostname '$HOSTNAME' != expected '$MASTER_HOST'. Proceeding anyway." >&2
fi

PERSIST_ROOT=/mnt/mmcblk0p2/birdpi
PY_DIR="$PERSIST_ROOT/python-packages"
VENV_DIR="$PERSIST_ROOT/venv"
TMP_DIR=/mnt/mmcblk0p2/tmp
PIP_CACHE_DIR=/mnt/mmcblk0p2/pip-cache
LOG_DIR=/mnt/mmcblk0p2/log
mkdir -p "$PY_DIR" "$TMP_DIR" "$PIP_CACHE_DIR" "$LOG_DIR"

export TMPDIR="$TMP_DIR"
export PIP_CACHE_DIR="$PIP_CACHE_DIR"
export PYTHONUNBUFFERED=1

echo "[run_main] Hostname=$HOSTNAME"
echo "[run_main] Using persistent dirs under $PERSIST_ROOT"

# Installation (TinyCore extensions should already be loaded via onboot.lst).
if $INSTALL_FLAG; then
  echo "⚙️ Running installation steps (TinyCore) ..."
  # Ensure python present (python3.11/3.12 extensions) & optional tools loaded externally.
  # Create / refresh virtual environment if venv module exists; fallback to --target layout otherwise.
  if [ ! -d "$VENV_DIR" ] || $FORCE_REINSTALL; then
    if python3 -c 'import venv' 2>/dev/null; then
      echo "[run_main] Creating virtualenv at $VENV_DIR"; \
        python3 -m venv "$VENV_DIR" || echo "[run_main] venv failed; falling back to --target installs"
    fi
  fi
  if [ -d "$VENV_DIR" ]; then
    . "$VENV_DIR/bin/activate"
    python3 -m pip install --no-cache-dir -r pi-requirements.txt
  else
    python3 -m pip install --no-cache-dir --target "$PY_DIR" -r pi-requirements.txt
  fi
else
  echo "🚫 --install not supplied; skipping dependency install.";
  if [ -d "$VENV_DIR" ]; then
    . "$VENV_DIR/bin/activate"
  fi
fi

# Add target dir to PYTHONPATH if not using venv
if [ -d "$PY_DIR" ]; then
  export PYTHONPATH="$PY_DIR:src:$PYTHONPATH"
else
  export PYTHONPATH="src:$PYTHONPATH"
fi

# Default music folder
MUSIC_FOLDER="./music"
SOURCE_FOLDER="./music"

# Check for external music/config source
# TODO: currently not used
# if [ -d "/media/BIRDS/music" ] && [ -f "/media/BIRDS/config_multi_song.json" ]; then
#     SOURCE_FOLDER="/media/BIRDS/music"
#     cp /media/BIRDS/config_multi_song.json .
# fi

# Convert MP3s to WAVs (only if missing) – keep RAM footprint small.
find "$SOURCE_FOLDER" -type f -name '*.mp3' | while read -r f; do
  relative_path="${f#$SOURCE_FOLDER/}"
  dest_dir="$MUSIC_FOLDER/$(dirname "$relative_path")"
  mkdir -p "$dest_dir"
  wav_file="$dest_dir/$(basename "${f%.mp3}.wav")"
  if [ ! -f "$wav_file" ]; then
    echo "[audio] Converting $f -> $wav_file"
    ffmpeg -i "$f" -ar 48000 "$wav_file" >/dev/null 2>&1 || { echo "[audio] Conversion failed for $f" >&2; exit 1; }
  fi
done

echo "[run_main] Waiting for USB sound devices ..."
python3 src/wait_devices_init.py || echo "[run_main] Device init script failed, continuing"
echo "[run_main] Starting BirdPi master"

python3 src/birdpi_main/main.py >> "$LOG_DIR/master.log" 2>&1 || {
  echo "❌ BirdPi master exited with error" >&2; exit 1; }
