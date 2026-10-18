#!/bin/sh
# Roast Master installer for Raspberry Pi OS Bookworm 64-bit + Raspberry Pi AI Camera (IMX500).
# Usage: sh roast_install.sh
#   LLM_MODEL=llama3.2:1b sh roast_install.sh   # pick a different Ollama model
#   INSTALL_OLLAMA=0 sh roast_install.sh        # LLM runs on another machine (set llm.host in config)
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
MODELS="$REPO_DIR/models"
VENV="$REPO_DIR/.roast-venv"
LLM_MODEL="${LLM_MODEL:-qwen2.5:1.5b}"
INSTALL_OLLAMA="${INSTALL_OLLAMA:-1}"

echo "== apt packages (AI camera firmware, picamera2, OpenCV, ALSA tools)"
sudo apt update
sudo apt install -y imx500-all python3-picamera2 python3-opencv python3-numpy python3-gpiozero \
    python3-venv alsa-utils curl unzip

echo "== models -> $MODELS"
mkdir -p "$MODELS"
cd "$MODELS"
if [ ! -d vosk-model-small-en-us-0.15 ]; then
    curl -fLO https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
    unzip -q vosk-model-small-en-us-0.15.zip && rm vosk-model-small-en-us-0.15.zip
fi
if [ ! -x piper/piper ]; then
    curl -fL https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz | tar xz
fi
for f in en_US-ryan-medium.onnx en_US-ryan-medium.onnx.json; do
    [ -f "$f" ] || curl -fLO "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/$f"
done
# 2022mar YuNet matches the OpenCV 4.6 shipped by Bookworm apt (2023mar needs OpenCV >= 4.8).
[ -f face_detection_yunet_2022mar.onnx ] || \
    curl -fLO https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2022mar.onnx
[ -f face_recognition_sface_2021dec.onnx ] || \
    curl -fLO https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
cd "$REPO_DIR"

echo "== python venv -> $VENV"
python3 -m venv --system-site-packages "$VENV"
"$VENV/bin/pip" install -r "$REPO_DIR/roast-requirements.txt"

if [ "$INSTALL_OLLAMA" = "1" ]; then
    echo "== Ollama + $LLM_MODEL"
    command -v ollama >/dev/null 2>&1 || curl -fsSL https://ollama.com/install.sh | sh
    ollama pull "$LLM_MODEL"
fi

echo "== systemd service roast-bird"
sudo tee /etc/systemd/system/roast-bird.service >/dev/null <<EOF
[Unit]
Description=Squawkers McCaw Roast Master
After=network-online.target sound.target ollama.service
Wants=network-online.target

[Service]
User=$(id -un)
WorkingDirectory=$REPO_DIR
ExecStart=$VENV/bin/python $REPO_DIR/src/roast_daemon.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable roast-bird.service

echo
echo "Done. Next:"
echo "  1. Reboot once so the IMX500 firmware loads."
echo "  2. Enroll faces:  $VENV/bin/python src/roast_daemon.py --enroll \"Name\""
echo "  3. Start:         sudo systemctl start roast-bird && journalctl -u roast-bird -f"
