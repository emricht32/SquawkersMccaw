#!/bin/bash

TARGET="src/main.py"

# Find the PID of the running Python script
PID=$(ps aux | grep "[p]ython3 $TARGET" | awk '{print $2}')

if [ -z "$PID" ]; then
  echo "No running process found for $TARGET"
else
  echo "Killing $TARGET (PID $PID)"
  kill "$PID"
fi