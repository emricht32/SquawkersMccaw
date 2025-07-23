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


  sudo apt install -y \
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

fi

sudo systemctl stop avahi-daemon

source ~/birdpi-venv/bin/activate

if ! pip3 install -r pi-requirements.txt; then
    echo "Error installing Python dependencies" >&2
    exit 1
fi

PYTHONPATH=src python3 src/birdpi_node/main.py