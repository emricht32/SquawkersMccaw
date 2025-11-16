#!/bin/sh
# setup_picoreplayer_event_listener.sh
# Deploy event listener plugin locally or to a remote piCorePlayer host.
#
# Local usage:
#   ./setup_picoreplayer_event_listener.sh /mnt/mmcblk0p2/tce/userplugins/eventlistener
# Remote usage (scp):
#   ./setup_picoreplayer_event_listener.sh user@birdpi-node.local:/mnt/mmcblk0p2/tce/userplugins/eventlistener
#
# If a remote target is specified (contains ':'), files are copied via scp.
# Otherwise a local copy (cp) is performed.

set -euo pipefail

if [ -z "${1:-}" ]; then
  echo "Usage: $0 <TARGET_PLUGIN_DIR or user@host:dir>"
  exit 1
fi

TARGET="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_SRC_DIR="$SCRIPT_DIR/picoreplayer_event_listener"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMMON_BIRD_SRC="$REPO_ROOT/src/common/bird.py"

if [ ! -f "$COMMON_BIRD_SRC" ]; then
  echo "Could not find bird.py at $COMMON_BIRD_SRC" >&2
  exit 2
fi

echo "Preparing deployment of event listener plugin to $TARGET";

TMP_PACK_DIR="$(mktemp -d)"
cp "$PLUGIN_SRC_DIR/event_listener.py" "$TMP_PACK_DIR/"
# Copy real bird.py (lowercase) next to event_listener.py
cp "$COMMON_BIRD_SRC" "$TMP_PACK_DIR/bird.py"

chmod +x "$TMP_PACK_DIR/event_listener.py"

if echo "$TARGET" | grep -q ':'; then
  echo "Remote target detected; using scp.";
  # Ensure remote directory exists (best effort)
  REMOTE_HOST="${TARGET%%:*}"
  REMOTE_PATH="${TARGET#*:}"
  echo "Ensuring remote path $REMOTE_PATH exists on $REMOTE_HOST (if SSH permissions allow)."
  ssh "$REMOTE_HOST" "mkdir -p '$REMOTE_PATH'" || echo "Warning: could not ensure remote path exists; proceeding with scp.";
  scp "$TMP_PACK_DIR/event_listener.py" "$TMP_PACK_DIR/bird.py" "$TARGET/"
else
  echo "Local target detected; copying files.";
  mkdir -p "$TARGET"
  cp "$TMP_PACK_DIR/event_listener.py" "$TMP_PACK_DIR/bird.py" "$TARGET/"
fi

echo "Deployment complete. Files now present at: $TARGET"
echo "Contents deployed:";
echo " - event_listener.py"
echo " - bird.py (synchronized from src/common/bird.py)"
echo "Configure piCorePlayer events to execute: python3 <plugin_dir>/event_listener.py <event-args>"

rm -rf "$TMP_PACK_DIR"
