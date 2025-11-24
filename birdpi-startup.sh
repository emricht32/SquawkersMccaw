#!/bin/sh
# BirdPi startup script
# Jonathan Emrich, 2025

# Usage: sh /mnt/mmcblk0p2/tc/birdpi-startup.sh &

VENV_DIR="/mnt/mmcblk0p2/tc/birdpi-venv"
APP_DIR="/mnt/mmcblk0p2/tc/SquawkersMccaw/src"
DAEMON="${APP_DIR}/bird_daemon.py"
LOG_DIR="/mnt/mmcblk0p2/tc/birdpi-logs"
PID_FILE="/tmp/bird_daemon.pid"

mkdir -p "$LOG_DIR"

echo "[startup] $(date) Starting BirdPi..." >> "$LOG_DIR/startup.log"

# Prevent duplicate daemon instances
if [ -f "$PID_FILE" ]; then
    if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "[startup] Daemon already running (PID $(cat $PID_FILE))" >> "$LOG_DIR/startup.log"
        exit 0
    else
        echo "[startup] Stale PID file detected, removing." >> "$LOG_DIR/startup.log"
        rm -f "$PID_FILE"
    fi
fi

# Activate venv if available
if [ -d "$VENV_DIR" ]; then
    echo "[startup] Activating venv at $VENV_DIR" >> "$LOG_DIR/startup.log"
    . "$VENV_DIR/bin/activate"
else
    echo "[startup] No venv found at $VENV_DIR, using system Python" >> "$LOG_DIR/startup.log"
fi

# Start daemon with nohup so it stays alive
echo "[startup] Launching bird_daemon.py" >> "$LOG_DIR/startup.log"
nohup python3 "$DAEMON" >> "$LOG_DIR/daemon_stdout.log" 2>&1 &

# Save PID
echo $! > "$PID_FILE"
echo "[startup] Daemon started with PID $!" >> "$LOG_DIR/startup.log"
