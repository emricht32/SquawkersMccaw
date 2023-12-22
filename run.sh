#!/bin/bash
set -x
MUSIC_FOLDER=./music/*
for f in $(find $MUSIC_FOLDER -name '*.mp3'); do 
    if ! [ -f "${f%.mp3}.wav" ]; then
        echo "File does not exist. creating it"
        ffmpeg -i "$f" -ar 48000 "${f%.mp3}.wav"
    fi
done
sleep 5

pip3 install -r pi-requirements.txt
# git pull
python3 src/main.py
