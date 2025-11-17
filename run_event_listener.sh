#!/bin/sh

# Absolute paths
VENV_PATH="/mnt/mmcblk0p2/tc/birdpi-venv"
SCRIPT="/mnt/mmcblk0p2/tc/SquawkersMccaw/deployment/picoreplayer_event_listener/event_listener.py"
PYTHON="$VENV_PATH/bin/python"

LOG="/mnt/mmcblk0p2/tc/SquawkersMccaw/event_listener.log"

# Ensure log file exists
touch "$LOG"

# Log start
echo "---- $(date) ----" >> "$LOG"
echo "Running event listener" >> "$LOG"
echo "Args: $@" >> "$LOG"

# Activate venv (export correct PATH for gpiozero)
. "$VENV_PATH/bin/activate"

# Execute the listener with forwarded args, logging output
"$PYTHON" "$SCRIPT" "$@" >> "$LOG" 2>&1
