# BirdPi AI → SquawkersMccaw: Wibey Implementation Handoff

**Prepared:** 2026-10-23
**Repo / branch:** `emricht32/SquawkersMccaw` @ `multipi-picoreplayer` (HEAD `189666f vision`)
**Working tree:** all work below is **uncommitted** (see §9). Unit tests: `85 passed` on macOS (Python 3.13).
**Predecessor doc:** `BIRDPI_CODEX_HANDOFF.md` (v10 starter handoff). This document supersedes its "status" sections.

> **Read first:** Nothing in this document has been run on a Raspberry Pi, a real LMS server, real GPIO, a mic, or speakers. Everything is unit-tested with fakes only. Do not claim hardware success without a hardware test.

---

## 0. Instructions to Wibey

You are continuing BirdPi AI integration in the existing repo. Inspect the files listed in §4 before changing anything. Preserve the hard invariants in §1, the pCP/LMS song system, and hardware safety (beak always off on exit). The user's immediate goals, in order:

1. **Polly running via voice commands on a Raspberry Pi 5** (1-bird mode).
2. **5-bird setup:** Polly on the Pi 5; José, Michael, Fritz, Pierre on Pi Zero 2 W running piCorePlayer (pCP).

Work incrementally, keep tests green (`python3 -m unittest discover -s tests` from `src/birdpi-ai-starter`), and report exactly what was verified on hardware vs. only in tests.

---

## 1. Product rules (unchanged, enforced in code)

| Physical birds | Layout | Comedy | Songs |
|---|---|---|---|
| **1** | Pi 5 bird = Polly | Polly roasts only | Disabled |
| **4** | Main bird = Polly (comedy) + José (singing), plus Michael/Fritz/Pierre | Polly only | José + 3 others |
| **5** | Polly and José on separate birds | Polly only, never sings | José + 3 others |

- Polly never sings; José never jokes/roasts. They never interact. No multi-bird comedy dialogue.
- Adult/profane roasts require **operator** `voice.adult_mode: true` (config) **and** a human challenge (`direct_insult`, `roast_request`, `roast_challenge`). Voice/vision only supply the challenge tag, never permission.
- `bird_count` is explicit config (1, 4, 5). Never inferred live from online devices.
- **First-come exclusivity (user requirement):** whichever of {Polly roast, José song} starts first plays; the other is queued, not dropped (except Polly gives up after `queue.polly_max_wait_s`).

Code gates: `birdpi_roles.route()` / `validate_comedy()`, `birdpi_bridge.roast()` tag check, `voice_service.VoiceService._roast()` adult_mode check (must be literal `true`).

---

## 2. Architecture (current design)

```
                 ┌────────────────────────── Pi 5 (hostname birdpi-main in 5-bird mode) ─────────────────────────┐
 USB mic ──► voice_service.py ──► voice_intents.parse_intent
                 │   roast ──► birdpi_bridge.play_roast ──► chirp_engine.select/render (Piper server.py :8081, localhost)
                 │                      │                         │
                 │                      │           lms_gate.LmsPerformanceGate (4/5 birds; NullGate for 1)
                 │                      │                         │
                 │                      └──► polly_performer.PollyPerformer ──► LmsSink: one-shot WAV URL → LMS
                 │                                    │                                   plays on player "birdpi-polly"
                 │                                    └──► beak GPIO (roast/body.BirdBody, gpiozero/lgpio)
                 │   song  ──► song_requests.request_song ──► LMS: titles search + playlistcontrol load/insert
                 │                                                on lms.song_player (e.g. birdpi-jose)
  Lyrion Music Server (LMS) :9000 JSON-RPC, :9090 CLI, :3483 slimproto
  squeezelite -n birdpi-polly (systemd: birdpi-squeezelite-polly)
 └────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
        │ LMS sync group (José, Michael, Fritz, Pierre — NOT Polly)
        ▼
 Pi Zero 2 W ×4 (pCP): squeezelite + src/bird_daemon.py (subscribes to LMS CLI, animates beak/body from song intervals)
```

Key decisions and why:

- **Polly has her own LMS player `birdpi-polly`** in every topology. Reusing José's player would broadcast Polly to every synced bird and wipe José's playlist. In 4-bird mode it would be a second squeezelite instance (unique `-m` MAC) on the shared host.
- **LMS is the single source of truth** for "is a song playing", so the gate works across hosts without modifying pCP nodes.
- **Gate is a first-come queue** (`lms_gate.py`):
  - Song first → Polly waits; when LMS moves to the next track (index change or time reset), that track is stopped and held; Polly speaks; held track restarts from the top (`play`) so all bird_daemons re-sync.
  - Polly first → any song start/resume (`newsong`, `open`, `pause 0`) on a relevant player is stopped and held until Polly finishes.
  - LMS unreachable → fail closed (Polly refused).
  - Polly's own player is excluded (`exclude_ids`).
- **bird_daemon changes:** ignores LMS events from any player whose name contains `polly` (env `BIRDPI_IGNORE_PLAYER`), and skips animating a song while Polly's player is playing. Without this, Polly's `playlist stop` would stop José's song on every bird.
- **Polly audio path:** `LmsSink` serves the cached WAV from a one-shot HTTP server (unguessable token path, bound to the local IP toward LMS, shut down after the performance) and tells LMS to play the URL on `birdpi-polly`. Beak timing follows LMS `status` `time` (re-anchored every 0.25 s). `AplaySink` (local ALSA) remains as fallback (`audio.output: "aplay"`).
- **Play history** is recorded only after confirmed full playback (not on preview, refusal, timeout, abort, early stop).
- **LMS on the Pi 5** (planned/scripted): Pi 5 takes hostname `birdpi-main` so pCP nodes and `bird_daemon` discovery need no changes; José's Zero is renamed `birdpi-jose`.

---

## 3. Status by area

| Area | Status |
|---|---|
| v10 starter files imported (roles, bridge, topology config, role tests, README_V10) | Done (no existing files overwritten; ZIP's test SQLite/pycache excluded) |
| Topology gate (1/4/5, role isolation) | Done + tests |
| Polly performer (beak from cues, safety, sinks) | Done + tests (fake GPIO/clock) |
| Polly audio via LMS (`birdpi-polly`) | Done + tests (fake LMS); **unverified on LMS** |
| First-come song/roast queue gate (4 and 5 birds) | Done + tests (fake LMS); **unverified on LMS** |
| bird_daemon ignores Polly / skips animation while Polly plays | Done (py_compile only; no unit tests possible—module does network discovery at import) |
| Voice triggers (Vosk) → Polly roasts / José songs | Done + tests (intent, catalog, service); **mic/Vosk unverified** |
| Pi 5 installer `pi5_setup.sh` (LMS, squeezelite, Piper, Vosk, systemd units, local config) | Written, `bash -n` OK; **never executed on a Pi** |
| Per-device config `config/birdpi_topology.local.json` (gitignored, preferred when present) | Done |
| LMS-registration bird-count `detect` command (latched) | **Not started** (design agreed; see §8) |
| 4-bird mode on Pi 5 (shared bird GPIO) | **Blocked** by bird.py issues (see §7) |
| Vision tags → joke tags | Not started (v9 vision preview untouched) |
| Legacy entrypoints routed through gate | Not started (see §7) |

---

## 4. File map (all paths relative to repo root)

### New / changed in `src/birdpi-ai-starter/`

| File | Purpose |
|---|---|
| `birdpi_roles.py` | (v10) `route(count, role, action)`, `validate_comedy()` |
| `birdpi_bridge.py` | CLI `status` / `song-route` / `roast [--play]`; `play_roast(cfg, db, tags, listeners, session, tts_url)` shared with voice service; `build_sink`, `build_performer`, `load_config`, `default_config_path()` (prefers `config/birdpi_topology.local.json`) |
| `lms_gate.py` | `LmsClient` (JSON-RPC + CLI subscribe, `find_player`, `status`, `track_state`, `play_url`, `local_ip`), `parse_song_start`, `NullGate`, `LmsPerformanceGate` (states idle/waiting/active; `acquire(max_wait_s)` / `release()`), `make_client`, `build_gate(count, lms_cfg, exclude_ids)` |
| `polly_performer.py` | `PollyPerformer(pins, sink, ...)`, `AplaySink`, `LmsSink`, `WavServer` |
| `voice_intents.py` | `parse_intent(transcript, catalog, polly_aliases, jose_aliases)` → `Intent(kind='roast'|'song', tags, song, random_song)` |
| `song_requests.py` | `SongCatalog` (match/pick_random over `config_multi_song_with_triggers.json`), `find_lms_track`, `request_song` (load if idle, insert-next if playing) |
| `voice_service.py` | `VoiceService.handle(transcript)`; mic via `roast.speech.Listener` (Vosk + arecord); `--console` to type transcripts |
| `chirp_engine.py` | Refactor only: new `render(db, speaker, text, url, chirp_id)` returns `(wav, meta, cache_key)`; `synth()` uses it. Cache key unchanged. |
| `config/birdpi_topology.json` | Repo defaults (bird_count 1, beak, queue, audio, voice, lms) |
| `pi5_setup.sh` | Pi 5 installer (see §5) |
| `.gitignore` | v10 ignores + `data/`, `config/*.local.json` |
| `tests/test_birdpi_roles.py`, `test_bridge_roast.py`, `test_lms_gate.py`, `test_polly_performer.py`, `test_voice.py` | New tests |

### Changed elsewhere
| File | Change |
|---|---|
| `src/bird_daemon.py` | `get_player_name`, `is_ignored_player`, `polly_is_playing`; subscribe loop skips Polly events; `start_song_from_status` skips animation while Polly plays |

### Reused, unchanged
`src/roast/body.py` (`BirdBody` GPIO wrapper), `src/roast/speech.py` (`Listener` Vosk), `server.py` (Piper HTTP on 127.0.0.1:8081), `config_single_bird.json` (Polly pins: beak 17, body 10, lights [24, 25]), `config_multi_song_with_triggers.json` (11 songs with `triggers`).

### Working-tree note
`src/birdpi-ai-starter/README_V8.md` and `README_V9.md` show as **deleted** in `git status`. This was not part of the documented changes; confirm with the user before committing.

---

## 5. Config reference (`config/birdpi_topology.json` → copy to `.local.json` per device)

| Key | Default | Meaning |
|---|---|---|
| `bird_count` | `1` | 1, 4, or 5; validated |
| `polly_pins_file` | `../../config_single_bird.json` | Relative to starter dir |
| `beak.audio_latency_s` | `0.0` | **Calibrate on hardware** (beak vs. heard audio) |
| `beak.max_open_s` / `min_closed_s` | `0.4` / `0.06` | Motor safety |
| `queue.polly_max_wait_s` | `300` | Polly's max wait behind a song |
| `audio.output` | `lms` | `lms` or `aplay` |
| `audio.serve_port` | `0` | WAV server port (0 = ephemeral) |
| `audio.lms_start_timeout_s` | `8.0` | Fail if LMS doesn't start Polly audio |
| `voice.adult_mode` | `false` | Operator permission; must be literal `true` |
| `voice.vosk_model` | `models/vosk-model-small-en-us-0.15` | Relative to repo root |
| `voice.mic_device` | `default` | ALSA capture device |
| `voice.cooldown_s` | `3.0` | Per-intent cooldown (roast cooldown counts from end of performance) |
| `voice.polly_aliases` / `jose_aliases` | see file | Add whatever Vosk actually transcribes |
| `lms.host` | `birdpi-main.local` | `pi5_setup.sh` sets `localhost` |
| `lms.polly_player` | `birdpi-polly` | Polly's squeezelite name |
| `lms.song_player` | `birdpi-main` | José's player; `pi5_setup.sh --birds 5` sets `birdpi-jose` |
| `lms.player_ids` | `[]` | Optional whitelist of song players for the gate (empty = all except Polly) |

Song entries may add `"lms_search": "<library title>"` if LMS titles don't match `name`/`display_name`/`audio_dir`.

---

## 6. Runbooks

### Tests (macOS or Pi)
```bash
cd src/birdpi-ai-starter
python3 -m unittest discover -s tests          # expect: Ran 85 tests ... OK
printf 'hey polly roast me\njose play wellerman\n' | python3 voice_service.py --console
```
macOS gotcha: corporate HTTP proxy env vars intercept 127.0.0.1; tests use `ProxyHandler({})`.

### Phase 1 — Polly by voice on Pi 5 (1 bird)
```bash
cd ~/SquawkersMccaw/src/birdpi-ai-starter
./pi5_setup.sh --birds 1 --lms-deb ~/lyrionmusicserver_<ver>_arm64.deb --adult-mode [--mic <ALSA dev>]
# LMS web UI :9000 → Settings → Basic → Media Folders: /srv/birdpi/music → Rescan
.venv/bin/python birdpi_bridge.py status
journalctl -u birdpi-voice -f      # say "Hey Polly, roast me"
```
`pi5_setup.sh` does: apt (squeezelite, alsa-utils, python3-gpiozero, python3-lgpio, numpy…), installs LMS from the provided .deb (download from lyrion.org/getting-started → Raspberry Pi), rsyncs `music/` to `/srv/birdpi/music` (LMS runs as its own user and can't read `~`), creates/updates `.venv` (system site packages enabled for gpiozero/lgpio), pip `piper-tts[alignment]` + `vosk`, Polly voice, Vosk model into `models/`, imports the comedy library, writes `config/birdpi_topology.local.json`, and installs systemd units `birdpi-squeezelite-polly`, `birdpi-tts`, `birdpi-voice`.

### Phase 2 — 5 birds (Pi 5 + 4 Zeros)
1. José's current main Zero (pCP): hostname → `birdpi-jose`, player name → `birdpi-jose`, **disable LMS**, Squeezelite LMS IP → Pi 5.
2. Pi 5: `./pi5_setup.sh --birds 5 --set-hostname` → reboot (becomes `birdpi-main`, `lms.song_player=birdpi-jose`).
3. Michael/Fritz/Pierre: if pCP "LMS IP" is a hostname, no change; if an IP, point at Pi 5.
4. **Deploy updated `src/bird_daemon.py` to all 4 Zeros** (`birdctl restart`). Required.
5. LMS UI: sync José/Michael/Fritz/Pierre. **Never sync `birdpi-polly`.**
6. Acceptance: "José, play Wellerman" animates all 4; "Polly, roast me" during a song waits for track end; a song started during Polly is held and restarts from the top.

---

## 7. Known gaps / risks (prioritized)

**P0 — needed for the user's two goals**
1. **Run `pi5_setup.sh` on real hardware** and fix what breaks. Unverified: LMS service name (`lyrionmusicserver` vs `logitechmediaserver`, both probed), squeezelite-as-service honoring `~/.asoundrc` (earlier `aplay ... Unknown error 524` was fixed via USB ALSA default), USB mic as ALSA `default`.
2. **Verify LMS behaviors the gate/sink rely on:** `playlist play <http wav url>` plays and ends with `mode: stop`; `serverstatus` `players_loop[].isplaying`; `status` `playlist_cur_index` / `time`; `stop` then `play` restarts the current track from the top; behavior with synced players (stop/play on one member).
3. **Vosk recognition** of "Polly"/"José"; tune alias lists from journal transcripts.
4. **Beak latency calibration** (`beak.audio_latency_s`) and Polly LMS start latency (~1–2 s expected).
5. **pCP Zeros must run the updated `bird_daemon.py`.**

**P1**
6. **Brief song blip windows:** (a) between Polly acquiring the gate and LMS reporting her player as playing (~1–2 s), a newly started song may animate briefly before being held; (b) the next track after the song Polly waited on can sound briefly before being stopped.
7. **Legacy entrypoints bypass the gate:** `chirp_engine.py select --play`, `server.py` `play:true`, `src/roast_daemon.py`. Route through `birdpi_bridge` or block in production.
8. **LMS CLI subscription drop** while Polly is queued/performing only logs; consider re-subscribe or falling back to polling.
9. **Latched `detect` command** (designed, not built): from LMS registered players — only `birdpi-polly` → 1; Polly + main/jose/michael/fritz/pierre with Polly IP == José IP → 4; different IPs → 5; otherwise error. Write `bird_count` to `.local.json` only on operator confirmation; never auto-change at runtime; `status` should show offline birds as warnings.

**P2 — 4-bird mode on Pi 5 (blocked)**
10. `src/bird.py` forces gpiozero `NativeFactory`, which does not support Pi 5 (RP1). Needs lgpio/default factory on Pi 5.
11. `bird_daemon` keeps beak/body pins open forever after first song; with lgpio's exclusive claims, Polly's performer can't open the shared bird's pins (reports `beak: unavailable`). Release pins after each song or share one owner.
12. Two squeezelite instances sharing one ALSA device (José + Polly) need `-C` idle-close on both or `dmix`.

**P2 — other**
13. Vision: v9 `vision_server` `tags` still empty; recognition never bypasses adult/challenge gates.
14. Seeking backward while Polly waits is treated as a new track (held).
15. No systemd hardening yet (e.g., `ProtectSystem`), and no log rotation beyond journald.

---

## 8. Suggested next steps for Wibey
1. Help the user run Phase 1 on the Pi 5; capture `journalctl -u birdpi-squeezelite-polly -u birdpi-tts -u birdpi-voice` and `birdpi_bridge.py status` output; fix issues found.
2. Add an LMS smoke-test command (e.g., `birdpi_bridge.py lms-check`) that lists players, plays a short Polly WAV on `birdpi-polly`, and prints observed `mode`/`time` transitions — to verify §7.2 quickly on hardware.
3. Phase 2 cut-over (§6), then acceptance tests for queueing in both orders.
4. Implement the latched `detect` command (§7.9).
5. Route/block legacy entrypoints (§7.7).
6. Commit in small milestones (suggested: v10 import; LMS gate + performer; voice; Pi 5 setup), update `CHANGELOG.md` and README; confirm the README_V8/V9 deletions with the user first.

---

## 9. Uncommitted changes (`git status --short` at handoff)
```
 M src/bird_daemon.py
 D src/birdpi-ai-starter/README_V8.md
 D src/birdpi-ai-starter/README_V9.md
 M src/birdpi-ai-starter/chirp_engine.py
?? src/birdpi-ai-starter/.gitignore
?? src/birdpi-ai-starter/README_V10.md
?? src/birdpi-ai-starter/birdpi_bridge.py
?? src/birdpi-ai-starter/birdpi_roles.py
?? src/birdpi-ai-starter/config/
?? src/birdpi-ai-starter/lms_gate.py
?? src/birdpi-ai-starter/pi5_setup.sh
?? src/birdpi-ai-starter/polly_performer.py
?? src/birdpi-ai-starter/song_requests.py
?? src/birdpi-ai-starter/tests/test_birdpi_roles.py
?? src/birdpi-ai-starter/tests/test_bridge_roast.py
?? src/birdpi-ai-starter/tests/test_lms_gate.py
?? src/birdpi-ai-starter/tests/test_polly_performer.py
?? src/birdpi-ai-starter/tests/test_voice.py
?? src/birdpi-ai-starter/voice_intents.py
?? src/birdpi-ai-starter/voice_service.py
```
