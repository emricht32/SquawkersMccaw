#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
sudo apt update
sudo apt install -y imx500-all python3-picamera2 python3-opencv curl
mkdir -p vision/models
BASE=https://github.com/opencv/opencv_zoo/raw/main/models
curl -fL --retry 3 -o vision/models/face_detection_yunet_2023mar.onnx "$BASE/face_detection_yunet/face_detection_yunet_2023mar.onnx"
curl -fL --retry 3 -o vision/models/face_recognition_sface_2021dec.onnx "$BASE/face_recognition_sface/face_recognition_sface_2021dec.onnx"
python3 - <<'PY'
from pathlib import Path
for filename, minimum in [('face_detection_yunet_2023mar.onnx',100000),('face_recognition_sface_2021dec.onnx',1000000)]:
    p = Path('vision/models') / filename
    if p.stat().st_size < minimum or p.read_bytes()[:40].startswith(b'version https://git-lfs'):
        raise SystemExit(f'Incomplete model download: {p}; see README_V9.md')
print('Downloaded both OpenCV models')
PY
printf '\nReboot if this is your first time installing imx500-all.\n'
