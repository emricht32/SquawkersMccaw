#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -m)" != "aarch64" ]]; then
  echo 'Warning: this installer targets a 64-bit Raspberry Pi OS (aarch64).' >&2
fi
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip libsndfile1
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install 'piper-tts[alignment]'
mkdir -p voices output
(cd voices && ../.venv/bin/python -m piper.download_voices en_US-lessac-medium)
echo 'Installed. Try:'
echo '  .venv/bin/python speak.py "Ahoy! Welcome aboard!"'
