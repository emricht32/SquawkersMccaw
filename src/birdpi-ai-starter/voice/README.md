# BirdPi voice prototype (separate from vision)

This package adds **voice input and spoken Polly replies** without editing BirdPi's current files. No wake word or automatic listening: it records only when explicitly invoked. Audio and text go to local services. It does not use the IMX500 AI Camera; STT runs on the Pi 5 CPU.

Copy both scripts into `~/SquawkersMccaw/src/birdpi-ai-starter/voice/` on Pi, while keeping the same files on Mac.

1. On Pi: `cd ~/SquawkersMccaw/src/birdpi-ai-starter && sh voice/install_voice.sh`. Downloads & compiles whisper.cpp and `base.en` model (~142 MiB). Source: https://github.com/ggml-org/whisper.cpp.
2. Check recording hardware: `arecord -l`. If USB mic is card 1, device 0, try `arecord -D plughw:1,0 -f S16_LE -r 16000 -c 1 -d 5 /tmp/mic.wav` and `aplay /tmp/mic.wav`. For USB output ALSA default may be set separately.
3. Ensure existing BirdPi Piper server `127.0.0.1:8081` is running: `curl http://127.0.0.1:8081/health`.
4. First test no microphone (TTS only): `python3 voice/voice_test.py --text "Hello Polly" --mode echo`.
5. Test real mic with transcript echo: `python3 voice/voice_test.py --device plughw:1,0 --seconds 6 --mode echo`. Replace input device from `arecord -l`.
6. When STT + Piper work, start your existing llama.cpp server on `127.0.0.1:8082`, then: `python3 voice/voice_test.py --device plughw:1,0 --seconds 6 --mode llm`.
7. To test STT only, pass `--file /tmp/mic.wav --no-play`; it will still attempt to generate audio via TTS. For purely STT: `~/whisper.cpp/build/bin/whisper-cli -m ~/whisper.cpp/models/ggml-base.en.bin -f /tmp/mic.wav -l en`.

Be sure **a microphone is connected**. A USB speaker alone is not a microphone. There is no always-on listening, speech speaker identification, voice authentication, echo cancellation, or wake word in this prototype. Do not record visitors without appropriate permission. While testing, use headphones or avoid simultaneous mic capture and TTS to prevent feedback. Polly only, other birds untouched; no adult roast mode.
