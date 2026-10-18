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
