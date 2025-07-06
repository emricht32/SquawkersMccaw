#!/bin/bash
set -e

# Parse arguments
INSTALL_FLAG=false
for arg in "$@"; do
  if [[ "$arg" == "--install" || "$arg" == "-install" ]]; then
    INSTALL_FLAG=true
  fi
done

# Run install steps only if flag is passed
if $INSTALL_FLAG; then
  echo "⚙️ Running installation steps..."

sudo apt update

sudo apt install -y \
  avahi-daemon \
  build-essential \
  cmake \
  dbus \
  dnsmasq \
  gir1.2-glib-2.0 \
  hostapd \
  libcairo2-dev \
  libfreetype6-dev \
  libgirepository1.0-dev \
  libimagequant-dev \
  libjpeg-dev \
  liblcms2-dev \
  libopenblas-dev \
  libopenjpeg-dev \
  libportaudio2 \
  libtiff-dev \
  libwebp-dev \
  libxcb-util-dev \
  libxcb1-dev \
  pkg-config \
  portaudio19-dev \
  python3-cairo \
  python3-dbus \
  python3-dev \
  python3-gi \
  python3-pyaudio \
  python3-venv \
  zlib1g-dev

  sudo systemctl disable hostapd
  sudo systemctl disable dnsmasq

  sudo systemctl enable avahi-daemon
  sudo systemctl start avahi-daemon
  sudo hostnamectl set-hostname birdpi-main


  # MODEL_DIR="models/vosk-model-small-en-us-0.15"
  # ZIP_FILE="models/vosk-model-small-en-us-0.15.zip"

  # if [ ! -d "$MODEL_DIR" ]; then
  #   echo "🔍 Model not found. Downloading and extracting..."
  #   mkdir -p models
  #   cd models || exit 1

  #   if [ ! -f "$(basename "$ZIP_FILE")" ]; then
  #     wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
  #   fi

  #   unzip -q vosk-model-small-en-us-0.15.zip
  #   echo "✅ Model downloaded and extracted."
  #   rm vosk-model-small-en-us-0.15.zip
  #   echo "✅ Removed zip file"
  #   cd ..
  # else
  #   echo "✅ Model already exists. Skipping download."
  # fi

  # Disable bonding and BR/EDR, enable LE-only mode
  sudo /usr/bin/btmgmt -i hci0 power off
  sleep 1
  sudo /usr/bin/btmgmt -i hci0 le on
  sleep 1
  sudo /usr/bin/btmgmt -i hci0 bredr off
  sleep 1
  sudo /usr/bin/btmgmt -i hci0 bondable off
  sleep 1
  sudo /usr/bin/btmgmt -i hci0 connectable on
  sleep 1
  sudo /usr/bin/btmgmt -i hci0 power on
  sleep 1

  # Use bluetoothctl to enable discoverable + advertising mode
  /usr/bin/timeout 5 /usr/bin/bluetoothctl <<EOF
  power on
  agent NoInputNoOutput
  default-agent
  pairable off
  discoverable on
  advertise yes
EOF

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

# Default music folder
MUSIC_FOLDER="./music"
SOURCE_FOLDER="./music"

# Check for external music/config source
# TODO: currently not used
# if [ -d "/media/BIRDS/music" ] && [ -f "/media/BIRDS/config_multi_song.json" ]; then
#     SOURCE_FOLDER="/media/BIRDS/music"
#     cp /media/BIRDS/config_multi_song.json .
# fi

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


echo "waiting for usb sound devices to initialize"
python3 src/wait_devices_init.py
echo "usb sound devices initialized"


if ! PYTHONPATH=src python3 src/birdpi_main/main.py; then
    echo "Error running the Python script" >&2
    exit 1
fi
