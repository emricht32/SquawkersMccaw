#!/bin/sh
# bootlocal.sh - TinyCore (piCorePlayer) startup script for BirdPi cluster.
# Place this in /opt/bootlocal.sh (persistent). After editing, run 'pcp bu' on piCorePlayer
# to persist changes across reboots.

set -e

HOSTNAME="$(hostname)"
ROOT=/mnt/mmcblk0p2/birdpi
LOG_DIR="$ROOT/log"
mkdir -p "$LOG_DIR"
echo "[bootlocal] Booting $HOSTNAME at $(date)" >> "$LOG_DIR/boot.log"

# Allow network + squeezelite + LMS discovery time.
sleep 8

# Ensure python path layout (run_* scripts will create if absent during --install)
if [ "$HOSTNAME" = "birdpi-main" ]; then
  echo "[bootlocal] Launching main script" >> "$LOG_DIR/boot.log"
  # Main handles song control & validation
  /mnt/mmcblk0p2/SquawkersMccaw/run_main.sh >> "$LOG_DIR/main.stdout.log" 2>&1 &
else
  echo "[bootlocal] Launching node script" >> "$LOG_DIR/boot.log"
  /mnt/mmcblk0p2/SquawkersMccaw/run_node.sh >> "$LOG_DIR/node.stdout.log" 2>&1 &
fi

echo "[bootlocal] Startup sequence dispatched" >> "$LOG_DIR/boot.log"