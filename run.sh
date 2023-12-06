#!/bin/bash
MUSIC_FOLDER=./music/*
for f in $(find $MUSIC_FOLDER -name '*.mp3'); do 
    if ! [ -f "${f%.mp3}.wav" ]; then
        echo "File does not exist. creating it"
        ffmpeg -i "$f" -acodec pcm_s16le -ac 1 -ar 48000 "${f%.mp3}.wav"
    fi
done

python3 src/main.py
