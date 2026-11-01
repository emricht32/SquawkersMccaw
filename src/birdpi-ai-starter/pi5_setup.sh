#!/usr/bin/env bash
# BirdPi Pi 5 setup: LMS server + Polly's Squeezelite player + Piper + voice triggers.
#
#   ./pi5_setup.sh --birds 1 --lms-deb ~/Downloads/lyrionmusicserver_9.1.1_arm64.deb --adult-mode
#   ./pi5_setup.sh --birds 5 --set-hostname        # after José's Zero is renamed birdpi-jose
#
# Safe to re-run: it only installs what is missing and re-syncs music + config.
set -euo pipefail
cd "$(dirname "$0")"
STARTER_DIR="$(pwd)"
REPO_DIR="$(cd ../.. && pwd)"
RUN_USER="$(id -un)"

BIRDS=""
LMS_DEB=""
SET_HOSTNAME=0
ADULT_MODE=""
SONG_PLAYER=""
MIC_DEVICE=""
MUSIC_DIR="/srv/birdpi/music"
VOSK_MODEL="vosk-model-small-en-us-0.15"

usage() {
    sed -n '2,8p' "$0"
    cat <<EOF
Options:
  --birds 1|5            Installed physical birds (4 is not supported by this script yet)
  --lms-deb PATH         Lyrion Music Server .deb (Raspberry Pi) from https://lyrion.org/getting-started/
  --set-hostname         Rename this Pi to birdpi-main so the Zeros find LMS here
  --adult-mode           Allow Polly's adult roasts (operator decision)
  --no-adult-mode        Disable Polly's adult roasts
  --song-player NAME     LMS player José sings on (default birdpi-jose for 5 birds)
  --mic DEVICE           ALSA capture device for voice (default: ALSA default)
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --birds) BIRDS="$2"; shift 2 ;;
        --lms-deb) LMS_DEB="$2"; shift 2 ;;
        --set-hostname) SET_HOSTNAME=1; shift ;;
        --adult-mode) ADULT_MODE=true; shift ;;
        --no-adult-mode) ADULT_MODE=false; shift ;;
        --song-player) SONG_PLAYER="$2"; shift 2 ;;
        --mic) MIC_DEVICE="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
    esac
done

if [[ "$BIRDS" != "1" && "$BIRDS" != "5" ]]; then
    echo "ERROR: --birds must be 1 or 5" >&2
    exit 2
fi
if [[ "$(uname -m)" != "aarch64" ]]; then
    echo "ERROR: expected 64-bit Raspberry Pi OS (aarch64)" >&2
    exit 1
fi
if [[ "$BIRDS" == "5" && -z "$SONG_PLAYER" ]]; then
    SONG_PLAYER="birdpi-jose"
fi

echo "== apt packages"
sudo apt-get update
sudo apt-get install -y squeezelite alsa-utils python3-venv python3-pip python3-gpiozero python3-lgpio \
    python3-numpy libsndfile1 curl unzip rsync

echo "== Lyrion Music Server"
LMS_SERVICE=""
for svc in lyrionmusicserver logitechmediaserver; do
    if systemctl list-unit-files "${svc}.service" --no-legend 2>/dev/null | grep -q "$svc"; then
        LMS_SERVICE="$svc"
    fi
done
if [[ -z "$LMS_SERVICE" ]]; then
    if [[ -z "$LMS_DEB" ]]; then
        echo "ERROR: LMS is not installed. Download the Raspberry Pi .deb from" >&2
        echo "       https://lyrion.org/getting-started/ and re-run with --lms-deb PATH" >&2
        exit 1
    fi
    sudo apt-get install -y "$(realpath "$LMS_DEB")"
    LMS_SERVICE="lyrionmusicserver"
fi
sudo systemctl enable --now "$LMS_SERVICE"

echo "== music library -> $MUSIC_DIR (LMS cannot read files inside a private home directory)"
sudo mkdir -p "$MUSIC_DIR"
sudo rsync -a --delete --include='*/' --include='*.mp3' --include='*.flac' --include='*.wav' \
    --include='*.m4a' --exclude='*' "$REPO_DIR/music/" "$MUSIC_DIR/"
sudo chmod -R a+rX "$(dirname "$MUSIC_DIR")"

echo "== Python venv, Piper voices, Vosk"
if [[ ! -x .venv/bin/python ]]; then
    ./install.sh
fi
# gpiozero/lgpio come from apt; the venv must be able to see them for Polly's beak.
sed -i 's/^include-system-site-packages = false/include-system-site-packages = true/' .venv/pyvenv.cfg
.venv/bin/python -m pip install --quiet 'piper-tts[alignment]' vosk
if [[ ! -f voices/en_GB-semaine-medium.onnx ]]; then
    ./install_polly_voice.sh
fi
mkdir -p "$REPO_DIR/models"
if [[ ! -d "$REPO_DIR/models/$VOSK_MODEL" ]]; then
    (cd "$REPO_DIR/models" && curl -fLO "https://alphacephei.com/vosk/models/$VOSK_MODEL.zip" \
        && unzip -q "$VOSK_MODEL.zip" && rm "$VOSK_MODEL.zip")
fi
mkdir -p data
.venv/bin/python chirp_engine.py import libraries/birdpi_comedy_library.json

echo "== per-device config -> config/birdpi_topology.local.json"
BIRDS="$BIRDS" ADULT_MODE="$ADULT_MODE" SONG_PLAYER="$SONG_PLAYER" MIC_DEVICE="$MIC_DEVICE" \
.venv/bin/python - <<'EOF'
import json, os
from pathlib import Path
local = Path('config/birdpi_topology.local.json')
cfg = json.loads((local if local.exists() else Path('config/birdpi_topology.json')).read_text())
cfg['bird_count'] = int(os.environ['BIRDS'])
cfg.setdefault('lms', {})['host'] = 'localhost'
cfg.setdefault('audio', {})['output'] = 'lms'
if os.environ['SONG_PLAYER']:
    cfg['lms']['song_player'] = os.environ['SONG_PLAYER']
if os.environ['ADULT_MODE']:
    cfg.setdefault('voice', {})['adult_mode'] = os.environ['ADULT_MODE'] == 'true'
if os.environ['MIC_DEVICE']:
    cfg.setdefault('voice', {})['mic_device'] = os.environ['MIC_DEVICE']
local.write_text(json.dumps(cfg, indent=2) + '\n')
print(json.dumps({k: cfg.get(k) for k in ('bird_count', 'lms', 'voice')}, indent=2))
EOF

echo "== Squeezelite player birdpi-polly"
# Stable locally-administered MAC so LMS always sees the same Polly player.
POLLY_MAC="02:$(sha256sum /etc/machine-id | cut -c1-10 | sed 's/../&:/g; s/:$//')"
sudo systemctl disable --now squeezelite.service 2>/dev/null || true

write_unit() {
    sudo tee "/etc/systemd/system/$1.service" >/dev/null
}

write_unit birdpi-squeezelite-polly <<EOF
[Unit]
Description=BirdPi Polly Squeezelite player
After=network-online.target sound.target ${LMS_SERVICE}.service
Wants=network-online.target

[Service]
User=$RUN_USER
SupplementaryGroups=audio
ExecStart=/usr/bin/squeezelite -n birdpi-polly -m $POLLY_MAC -s 127.0.0.1 -o default -C 1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

write_unit birdpi-tts <<EOF
[Unit]
Description=BirdPi Piper speech server
After=network-online.target

[Service]
User=$RUN_USER
WorkingDirectory=$STARTER_DIR
ExecStart=$STARTER_DIR/.venv/bin/python server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

write_unit birdpi-voice <<EOF
[Unit]
Description=BirdPi voice triggers (Polly roasts, José songs)
After=birdpi-tts.service birdpi-squeezelite-polly.service ${LMS_SERVICE}.service sound.target
Wants=birdpi-tts.service birdpi-squeezelite-polly.service

[Service]
User=$RUN_USER
SupplementaryGroups=gpio audio
WorkingDirectory=$STARTER_DIR
ExecStart=$STARTER_DIR/.venv/bin/python voice_service.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now birdpi-squeezelite-polly birdpi-tts birdpi-voice

if [[ "$SET_HOSTNAME" == "1" ]]; then
    echo "== hostname -> birdpi-main"
    sudo hostnamectl set-hostname birdpi-main
    sudo sed -i 's/^127\.0\.1\.1.*/127.0.1.1\tbirdpi-main/' /etc/hosts
    echo "Hostname changed: reboot so mDNS announces birdpi-main.local"
fi

cat <<EOF

Done. Remaining one-time steps:
  1. Open http://$(hostname -I | awk '{print $1}'):9000 -> Settings -> Basic Settings -> Media Folders:
     add $MUSIC_DIR, then "Rescan". (Re-run this script after adding songs to music/.)
  2. Check Polly's player registered:  .venv/bin/python birdpi_bridge.py status
  3. Watch voice triggers:             journalctl -u birdpi-voice -f
EOF
if [[ "$BIRDS" == "5" ]]; then
    cat <<EOF
  4. 5 birds: point every Zero's Squeezelite "LMS IP" (pCP Squeezelite Settings) at this Pi,
     disable LMS on José's Zero, and sync José/Michael/Fritz/Pierre in LMS. Do NOT sync birdpi-polly.
EOF
fi
