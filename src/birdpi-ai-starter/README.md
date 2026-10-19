# BirdPi AI starter v8

See [README_V8.md](README_V8.md) for upgrade and test instructions.

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

## Milestone 3.1 — Reliable jokes and TTS cleanup

On the existing Pi 5, start the persistent Piper service (`server.py`) as usual.
`llm_speak.py 'Tell me a pirate joke' --bird jose` now uses an offline curated joke by default
for near-immediate, meaningful setups and punchlines. This does not call llama.cpp.
For arbitrary LLM-generated jokes, use `--joke-source llm` (quality may be poor on Qwen3-0.6B).
Speech sent to Piper has common Markdown markers and labels removed.
Non-joke prompts still stream from the local LLM.

## Milestone 4 — Tagged chirp library (v6)

The full reusable comedy-generation prompt is bundled at `prompts/BIRDPI_COMEDY_LIBRARY_MASTER_V2.md`.
No new dependencies required. Existing `server.py` (Piper, port 8081), `llm_speak.py` (LLM) and other starter files are unchanged.

Import a JSON batch (first run automatically creates SQLite):

```bash
.venv/bin/python chirp_engine.py import examples/sample_chirps.json
.venv/bin/python chirp_engine.py stats
```

Simulate a visible hat on guest 7; without `--play`, selection is a non-mutating preview:

```bash
.venv/bin/python chirp_engine.py select --bird jose --tags hat --listeners guest7 --session party1
```

Generate cached Piper audio **and play the selected line** (requires your running TTS service; records history only after playback succeeds):

```bash
.venv/bin/python chirp_engine.py select --bird jose --tags hat --listeners guest7 --session party1 --play
```

Adult mode is an *operator-controlled flag*: only enable for confirmed adults-only events. No face/age inference occurs here. Example solo Polly test:

```bash
.venv/bin/python chirp_engine.py select --bird polly --tags adult_mode,direct_insult --listeners guest7 --session adultparty --play
```

The second playback attempt with the same listener/session won't repeat that `family_id`. The engine also enforces a global one-hour family cooldown by default. `--cooldown-hours` changes it; player session IDs are caller-provided temporary IDs. Store no biometric information in this prototype. `audio_cache` stores WAV and timing JSON obtained from Piper for later replay without synthesis. `--play` uses local ALSA and currently does not move physical motors. The cached cues are returned in `audio_cues` for integration with the existing synchronized bird node scheduler later.

**Important limitations:** Scene tags and adult authorization must be supplied by trusted upstream processes; camera integration and automatic voice trigger recognition are not implemented. A sample batch is bundled only to demonstrate the schema, not as a production comedy library. This is a CLI prototype, not an always-on camera-driven runtime. Because `--play` records only after successful complete playback, interruption handling and exact heard-range tracking need further development. There is no built-in personal-data deletion CLI yet: use ephemeral session IDs; manage retention before long-term deployment. If the exact text and voice model changes while retaining a cache key, explicitly invalidate old cache entries (the current key is based on speaker/text/server URL, not voice model revision). Cross-batch near-duplicate detection remains an editorial/importer enhancement.


## v7 — Spoken pre/post parrot squawks

Bundled full curated library: `libraries/birdpi_comedy_library.json` (991 entries).
Import once: `.venv/bin/python chirp_engine.py import libraries/birdpi_comedy_library.json`.

Standalone cartoon-style spoken vocalizations in `libraries/parrot_vocalizations.json` include `BRAAWK!`, `AWK-AWK!`, `SKEE-EE!`, and editable variants. Inspired by voice-actor-style cartoon parrot calls, not attempts to create realistic recordings. Entries have IDs and weights and are cached by the existing synth path. They are optional, and **not embedded into the joke's text or counted as jokes**. Polly remains isolated; its squawks are standalone Polly-only utterances.

Preview without audio (does not record or synthesize):
```
.venv/bin/python chirp_engine.py select --bird jose --tags hat --session demo --vocalize both
```

Play pre-squawk, joke, then post-squawk using the existing Piper server and your ALSA default:
```
.venv/bin/python chirp_engine.py select --bird jose --tags hat --listeners guest7 --session test1 --play --vocalize both
```

Use `--vocalize pre` or `--vocalize post` for only one side. Without `--vocalize`, prior behavior is unchanged. If Piper sounds artificial for these nonlexical utterances, record/cartoon-act the expressions or switch to a more suitable voice model in a later release. WAV plus lip-sync cue cache remains separate for every utterance. Currently it plays sequentially without a timing gap; no physical motor outputs yet.
