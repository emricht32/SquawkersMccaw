#!/bin/bash
set -e

# Enable debug mode if needed
# set -x

# Default music folder
MUSIC_FOLDER="./music"

# Source folder for .mp3 files
SOURCE_FOLDER="./music"

# Check if /media/BIRDS/music and /media/BIRDS/config_multi_song.json exist
if [ -d "/media/BIRDS/music" ] && [ -f "/media/BIRDS/config_multi_song.json" ]; then
    SOURCE_FOLDER="/media/BIRDS/music"
    cp /media/BIRDS/config_multi_song.json .
fi

# Save the result of find into a variable
mp3_files=$(find "$SOURCE_FOLDER" -name '*.mp3' -print0 | tr '\0' '\n')

# Iterate over the list stored in the variable
for f in $mp3_files; do
    # Determine the relative path of the .mp3 file
    relative_path="${f#$SOURCE_FOLDER/}"
    
    # Create the corresponding directory structure in the destination folder
    dest_dir="$MUSIC_FOLDER/$(dirname "$relative_path")"
    mkdir -p "$dest_dir"
    
    # Define the destination .wav file path
    wav_file="$dest_dir/$(basename "${f%.mp3}.wav")"

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