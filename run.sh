#!/bin/bash
set -e

# Enable debug mode if needed
#set -x

# Default music folder
MUSIC_FOLDER="./music"

# Source folder for .mp3 files
SOURCE_FOLDER="./music"

# Check if /media/BIRDS/music and /media/BIRDS/config_multi_song.json exist
if [ -d "/media/BIRDS/music" ] && [ -f "/media/BIRDS/config_multi_song.json" ]; then
    SOURCE_FOLDER="/media/BIRDS/music"
fi

echo "Source folder: $SOURCE_FOLDER"
echo "Destination folder: $MUSIC_FOLDER"

find "$SOURCE_FOLDER" -name '*.mp3' -print0 | while IFS= read -d '' f; do
    F="$f"
    # Determine the relative path of the .mp3 file
    relative_path="${f#"$SOURCE_FOLDER/"}"
    
    # Create the corresponding directory structure in the destination folder
    dest_dir="$MUSIC_FOLDER/$(dirname "$relative_path")"
    mkdir -p "$dest_dir"
    
    # Define the destination .wav file path
    wav_file="$dest_dir/$(basename "${relative_path%.mp3}.wav")"

    echo "Processing file: $f"
    echo "Relative path: $relative_path"
    echo "Destination directory: $dest_dir"
    echo "WAV file path: $wav_file"

    if ! [ -f "$wav_file" ]; then
        echo "Creating WAV file for $f"
        if ! ffmpeg -i "$f" -ar 48000 "$wav_file"; then
            echo "Error converting $f to WAV" >&2
            exit 1
        fi
    else
        echo "WAV file already exists for $f"
    fi

    echo "*Processing file: $f"
    echo "*Relative path: $relative_path"
    echo "*Destination directory: $dest_dir"
    echo "*WAV file path: $wav_file"
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
