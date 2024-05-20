#!/bin/bash
set -e

# Enable debug mode if needed
#set -x

# Default music folder
MUSIC_FOLDER="./music"

# Check if /media/BIRDS/music and /media/BIRDS/config_multi_song.json exist
if [ -d "/media/BIRDS/music" ] && [ -f "/media/BIRDS/config_multi_song.json" ]; then
    MUSIC_FOLDER="/media/BIRDS/music"
fi

find "$MUSIC_FOLDER" -name '*.mp3' -print0 | while IFS= read -r -d '' f; do
    wav_file="${f%.mp3}.wav"
    if ! [ -f "$wav_file" ]; then
        echo "Creating WAV file for $f"
        if ! ffmpeg -i "$f" -ar 48000 "$wav_file"; then
            echo "Error converting $f to WAV" >&2
            exit 1
        fi
    else
        echo "WAV file already exists for $f"
    fi
done

# Allow some time for processing if necessary
sleep 5

# Install Python dependencies
if ! pip3 install -r pi-requirements.txt; then
    echo "Error installing Python dependencies" >&2
    exit 1
fi

# Pull the latest code from the repository
# Uncomment if needed
# git pull

# Run the Python script
if ! python3 src/main.py; then
    echo "Error running the Python script" >&2
    exit 1
fi
