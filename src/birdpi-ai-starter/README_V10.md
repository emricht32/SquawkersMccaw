# BirdPi AI v10 — Polly/José physical bird topology

## Important separation
- Comedy/roasts (including chirp selection, TTS and any pre/post squawks): **Polly only**.
- Singing (existing LMS/song scheduler): **José only**.
- No Polly-to-José dialogue, even when physically separate.
- The imported comedy library may contain old José/Michael/Fritz/Pierre jokes. This bridge **never selects or plays them**.
- Polly roasts only when operator has explicitly enabled `adult_mode` and audience member has challenged her (`direct_insult`, `roast_request` or `roast_challenge`).

## Physical topologies

| bird_count | Polly comedy / Pi 5 | José singing / BirdPi main | Other birds |
|--|--|--|--|
| 1 | main bird | disabled | none |
| 4 | main bird | same main bird | Michael, Fritz, Pierre |
| 5 | dedicated Polly bird | distinct José bird | Michael, Fritz, Pierre |

Configure `config/birdpi_topology.json`: `bird_count` = `1`, `4`, or `5`. Explicit configuration is intentional. Do not switch roles just because a Wi-Fi node temporarily disconnects. Changing count requires deliberate reconfiguration.

## Quick run

```sh
cd ~/SquawkersMccaw/src/birdpi-ai-starter
.venv/bin/python chirp_engine.py import libraries/birdpi_comedy_library.json
.venv/bin/python birdpi_bridge.py status
.venv/bin/python birdpi_bridge.py roast --tags adult_mode,direct_insult --listeners guest7 --session party1
# With running Piper server on :8081 and working ALSA default:
.venv/bin/python birdpi_bridge.py roast --tags adult_mode,direct_insult --listeners guest7 --session party1 --play
.venv/bin/python birdpi_bridge.py song-route
```

`roast` without `--play` is a preview, without recording it as heard. `--play` sends Polly speech to the Pi 5's configured ALSA output and then logs the joke as played. It **does not currently drive the beak motor**; its metadata includes the mouth cues for integration. `song-route` does not actually start playback, and in single-bird mode intentionally fails. Existing songs should remain managed by your BirdPi main application and timing system.

## Next hardware/API integration

The existing `SquawkersMccaw` main controller / node firmware was not included in this ZIP. To synchronize physical beak motion and make shared physical main-bird playback safe, we still need to connect the Pi 5 service to the actual controller/song callbacks and implement an **exclusive audio-and-motor lock**. In 4-bird mode, a song and roast must not play simultaneously on the shared main bird. In 5-bird mode, Polly does not join the LMS singing schedule. Add a verified real-device-count source and a discovery UI after controller integration; do not infer count from stale registration.

### Concurrency and legacy CLI

`birdpi_bridge.py roast --play` serializes bridge-driven Polly audio using `data/birdpi-main-performance.lock`. This **does not yet prevent the existing BirdPi song engine** from starting a José song: the real song scheduler must acquire the same lock (or exchange explicit begin/end/busy events) in 4-bird mode. For now do not test concurrent songs and Polly comedy on the shared bird. Use `birdpi_bridge.py` instead of the legacy `chirp_engine.py select` CLI: the legacy CLI remains available for testing library entries and does **not** enforce new stage roles.
