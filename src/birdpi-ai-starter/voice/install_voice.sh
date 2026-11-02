#!/bin/sh
set -eu
sudo apt update
sudo apt install -y git cmake build-essential alsa-utils
if [ ! -d "$HOME/whisper.cpp/.git" ]; then
    git clone https://github.com/ggml-org/whisper.cpp "$HOME/whisper.cpp"
fi
cd "$HOME/whisper.cpp"
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j 4
sh ./models/download-ggml-model.sh base.en
test -s models/ggml-base.en.bin
echo 'Whisper ready. Run: arecord -l  (to find the USB microphone)'
