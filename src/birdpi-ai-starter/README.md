# BirdPi AI — Milestone 1: local speech + beak cues

Designed for **Raspberry Pi 5**, 64-bit Raspberry Pi OS Lite. No LLM/STT required for this first test.

## Install

```bash
chmod +x install.sh
./install.sh
```

Installer downloads Piper and one example voice. Initial installation needs internet; inference is offline afterward.

## Test

```bash
.venv/bin/python speak.py 'Ahoy! Welcome aboard!' --bird jose
aplay output/speech.wav  # if ALSA playback is available
cat output/speech.json
.venv/bin/python -m unittest discover -s tests -v
```

Outputs: `output/speech.wav` and `output/speech.json`, including a `singing_ranges` array compatible in shape with BirdPi's timing ranges. **This milestone does not transmit cues to the motor node.** Do not wire to motors without checking actuator duty-cycle limits and ensuring a stop/timeout path.

## Measurements

`metrics.synthesis_s` is synthesis-only. `metrics.model_load_s` is listed separately because the final service will load Piper only once at startup. `synthesis_realtime_factor < 1` indicates faster-than-real-time synthesis.

## Timing logic

Use Piper experimental phoneme alignment when supported; otherwise derive pulses from 20 ms RMS audio envelopes. The model can synthesize correctly while returning no alignment data. This code simplifies IPA vowels to 1-DOF beak openings and does not represent full visemes. The pulse limiter here is a *motion-shaping prototype*, not a guarantee of electrical or thermal safety.

## Next milestones

1. Inspect generated WAV and JSON; calibrate thresholds, motion duration, and per-bird delay.
2. Keep Piper loaded in a long-running local HTTP/WebSocket service.
3. Add audio/cue delivery to the existing main BirdPi controller, then node scheduling/acknowledgments.
4. Integrate llama.cpp and phrase streaming; then add streaming STT/VAD.

Piper's alignment API and the voice patching instructions: https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/ALIGNMENTS.md

## Persistent speech server (Milestone 2)

Unlike `speak.py`, `server.py` loads Piper **once** and keeps it in memory.

In terminal 1, from the project directory:

```bash
.venv/bin/python server.py
```

Keep it running. In terminal 2, from the same directory:

```bash
curl http://127.0.0.1:8081/health
curl -sS -X POST http://127.0.0.1:8081/api/speech \
  -H 'Content-Type: application/json' \
  -d '{"bird":"jose","text":"Ahoy! Welcome aboard!","play":true}'
```

`play:true` launches `aplay` on ALSA's working default device. Omit `play` to synthesize without local playback. The JSON contains `singing_ranges` and an `audio` URL like `/api/audio/<id>`. Download that audio via `curl -o sample.wav http://127.0.0.1:8081/api/audio/<id>`.

This version deliberately binds to **127.0.0.1 only**. If you later allow remote devices to access it, avoid exposing the endpoint to the internet; there's no authentication. It stores generated WAV/JSON files under `output/server/`, so periodically clean up old files if disk use matters. `play:true` is a local convenience; it does not yet synchronize beak motor cues with playback.

## Milestone 3 — Local LLM to spoken speech

Keep the existing `server.py` running on port 8081. In a separate shell:

```bash
./setup_llm.sh
./llama.cpp/build/bin/llama-server -hf Qwen/Qwen3-0.6B-GGUF:Q4_K_M --host 127.0.0.1 --port 8082 -c 2048 -t 4
```

The first run downloads the GGUF model. When the LLM is listening, in a third shell:

```bash
.venv/bin/python llm_speak.py 'Tell me a short pirate joke' --bird jose
```

The script reads streaming response tokens, extracts complete phrases, sends them to the existing Piper API, downloads the WAV, and plays them **in order** using the tested ALSA default. LLM generation overlaps with speech synthesis/playback via a queue. Test without playback using `--no-play`. It prints time-to-first-token and first synthesized phrase timing. The main Pi and physical motors are NOT connected yet.

These local test services bind to 127.0.0.1. Do not expose without authentication and request limits. As with milestone 2, generated WAV/JSON files accumulate in `output/server/` until deleted.
