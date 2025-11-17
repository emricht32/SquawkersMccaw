#!/bin/sh
# bootlocal.sh - TinyCore (piCorePlayer) startup script for BirdPi cluster.
# Place this in /opt/bootlocal.sh (persistent). After editing, run 'pcp bu' on piCorePlayer
# to persist changes across reboots.

set -e

HOSTNAME="$(hostname)"
ROOT=/mnt/mmcblk0p2/tc
LOG_DIR="$ROOT/log"
mkdir -p "$LOG_DIR"
# sudo chown -R tc:staff "$ROOT" 2>/dev/null || true
echo "[bootlocal] Booting $HOSTNAME at $(date)" >> "$LOG_DIR/boot.log"

# Allow network + squeezelite + LMS discovery time.
sleep 8

HOSTNAME=$(cat /usr/local/etc/hostname)

case "$HOSTNAME" in
  birdpi-main)
    su - tc -c "/mnt/mmcblk0p2/tc/SquawkersMccaw/run_main.sh" &
    ;;
  birdpi-*)
    su - tc -c "/mnt/mmcblk0p2/tc/SquawkersMccaw/run_node.sh" &
    ;;
esac

echo "[bootlocal] Startup sequence dispatched" >> "$LOG_DIR/boot.log"