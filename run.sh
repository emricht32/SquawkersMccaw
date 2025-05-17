#!/bin/bash
set -e

# Parse arguments
INSTALL_FLAG=false
for arg in "$@"; do
  if [[ "$arg" == "--install" || "$arg" == "-install" ]]; then
    INSTALL_FLAG=true
  fi
done

# Default music folder
MUSIC_FOLDER="./music"
SOURCE_FOLDER="./music"

# Check for external music/config source
if [ -d "/media/BIRDS/music" ] && [ -f "/media/BIRDS/config_multi_song.json" ]; then
    SOURCE_FOLDER="/media/BIRDS/music"
    cp /media/BIRDS/config_multi_song.json .
fi

# Convert MP3s to WAVs
mp3_files=$(find "$SOURCE_FOLDER" -name '*.mp3' -print0 | tr '\0' '\n')
for f in $mp3_files; do
    relative_path="${f#$SOURCE_FOLDER/}"
    dest_dir="$MUSIC_FOLDER/$(dirname "$relative_path")"
    mkdir -p "$dest_dir"
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

# Run install steps only if flag is passed
if $INSTALL_FLAG; then
  echo "⚙️ Running installation steps..."

  sudo apt update
  sudo apt install -y libportaudio2 portaudio19-dev python3-pyaudio libcairo2-dev \
      libgirepository1.0-dev gir1.2-glib-2.0 python3-gi python3-cairo pkg-config python3-dbus \
      cmake build-essential dbus python3-venv

  MODEL_DIR="models/vosk-model-small-en-us-0.15"
  ZIP_FILE="models/vosk-model-small-en-us-0.15.zip"

  if [ ! -d "$MODEL_DIR" ]; then
    echo "🔍 Model not found. Downloading and extracting..."
    mkdir -p models
    cd models || exit 1

    if [ ! -f "$(basename "$ZIP_FILE")" ]; then
      wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
    fi

    unzip -q vosk-model-small-en-us-0.15.zip
    echo "✅ Model downloaded and extracted."
    rm vosk-model-small-en-us-0.15.zip
    echo "✅ Removed zip file"
    cd ..
  else
    echo "✅ Model already exists. Skipping download."
  fi

  python3 -m venv --system-site-packages ~/birdpi-venv
  source ~/birdpi-venv/bin/activate

  if ! pip3 install -r pi-requirements.txt; then
      echo "Error installing Python dependencies" >&2
      exit 1
  fi
else
  echo "🚫 Skipping install steps. Run with --install if needed."
  source ~/birdpi-venv/bin/activate
fi

echo "waiting for usb sound devices to initialize"
python3 src/wait_devices_init.py
echo "usb sound devices initialized"

if ! python3 src/main.py; then
    echo "Error running the Python script" >&2
    exit 1
fi
