# BirdPi AI Starter v8 — Multi-voice + Polly Poppy + squawk auditions

Full replacement for v7 (preserves the previous CLI and master library). Contains 991 comedy chirps and the consolidated generation prompt.

## Upgrade

From the parent folder, back up local changes and `data/chirps.sqlite` before unzipping. The ZIP deliberately omits `.venv`, `data`, and generated WAVs.

```bash
cd ~/SquawkersMccaw/src
unzip -o birdpi-ai-starter-v8.zip
cd birdpi-ai-starter
./install_polly_voice.sh
```

The existing `.venv` and the previously installed `en_US-lessac-medium` voice must be present; if you have a new environment, run `./install.sh` first. Voice model filenames must exist inside `voices/`.

## Multi-voice Piper service

Stop the old running `server.py` (`Ctrl+C`) and restart:

```bash
.venv/bin/python server.py
```

Normal birds default to Lessac. Polly uses `en_GB-semaine-medium`, speaker 3 (Poppy), `length_scale=0.90`. Polly's voice is loaded lazily the first time she speaks. Models stay resident in memory. You can edit `voices/profiles.json` for other birds. The `noise_w` JSON value maps to Piper's `noise_w_scale` synthesis field.

```bash
curl -s http://127.0.0.1:8081/health
curl -s http://127.0.0.1:8081/api/speech -H 'Content-Type: application/json' \
  -d '{"bird":"polly","text":"Fuck you! Bring your best comeback.","play":true}'
```

`play:true` starts ALSA playback asynchronously. For sequential test clips, synthesize to WAV and call `aplay`, or wait for each audio duration.

## Library CLI

```bash
.venv/bin/python chirp_engine.py import libraries/birdpi_comedy_library.json
.venv/bin/python chirp_engine.py select --bird polly --tags adult_mode,direct_insult --listeners guest7 --session demo --play
```

## Squawk audition script (interactive input fixed)

```bash
.venv/bin/python test_squawks.py
```

Select 1/2/3, R replay, S skip, Q quit. WAVs and ratings go into `output/polly_squawk_tests`. Re-running skips already synthesized samples; `--no-rating` runs non-interactively. Samples use Poppy directly, not the HTTP service.

## Known limits

* `pitch_factor` is NOT available as a native Piper control; no pitch processor is implemented in v8.
* Other birds still share Lessac until their own voice models are chosen.
* Existing `audio_cache` has been version-bumped to avoid reusing v7 single-voice audio; changing `voices/profiles.json` invalidates the matching cached audio automatically.
* The Pi5 may require enough RAM to hold all voices; models load on first use, not all at startup.
* Camera, microphone streaming, and physical beak motor integration are still future work.
