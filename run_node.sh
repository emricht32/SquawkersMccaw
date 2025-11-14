#!/bin/sh
set -e

# TinyCore / piCorePlayer optimized launcher for BirdPi node.
INSTALL_FLAG=false
FORCE_REINSTALL=false
for arg in "$@"; do
  [ "$arg" = "--install" ] && INSTALL_FLAG=true
  [ "$arg" = "--force-reinstall" ] && FORCE_REINSTALL=true
done

HOSTNAME="$(hostname)"
NODE_NAME="${HOSTNAME#birdpi-}"  # fritz|pierre|michael|master
echo "[run_node] Hostname=$HOSTNAME (node=$NODE_NAME)"

PERSIST_ROOT=/mnt/mmcblk0p2/tc
PY_DIR="$PERSIST_ROOT/python-packages"
VENV_DIR="$PERSIST_ROOT/birdpi-venv"
TMP_DIR=/mnt/mmcblk0p2/tc/tmp
PIP_CACHE_DIR=/mnt/mmcblk0p2/tc/pip-cache
LOG_DIR=/mnt/mmcblk0p2/tc/log
mkdir -p "$PY_DIR" "$TMP_DIR" "$PIP_CACHE_DIR" "$LOG_DIR"
# sudo chown -R tc:staff "$PERSIST_ROOT" "$TMP_DIR" "$PIP_CACHE_DIR" "$LOG_DIR" 2>/dev/null || true

export TMPDIR="$TMP_DIR"
export PIP_CACHE_DIR="$PIP_CACHE_DIR"
export PYTHONUNBUFFERED=1

if $INSTALL_FLAG; then
  echo "⚙️ Installing node dependencies ..."
  if [ ! -d "$VENV_DIR" ] || $FORCE_REINSTALL; then
    if command -v virtualenv >/dev/null 2>&1; then
      virtualenv "$VENV_DIR" || echo "[run_node] virtualenv failed, using --target"
    fi
  fi
  if [ -d "$VENV_DIR" ]; then
    . "$VENV_DIR/bin/activate"
    python3 -m pip install --no-cache-dir -r pi-requirements.txt
  else
    python3 -m pip install --no-cache-dir --target "$PY_DIR" -r pi-requirements.txt
  fi
else
  echo "🚫 --install not supplied; skipping dependency install."
  [ -d "$VENV_DIR" ] && . "$VENV_DIR/bin/activate"
fi

if [ -d "$PY_DIR" ]; then
  export PYTHONPATH="$PY_DIR:src:$PYTHONPATH"
else
  export PYTHONPATH="src:$PYTHONPATH"
fi

echo "[run_node] Starting registration agent"
python3 src/birdpi_node/main.py >> "$LOG_DIR/node-${NODE_NAME}.log" 2>&1 || {
  echo "❌ Node script exited with error" >&2; exit 1; }