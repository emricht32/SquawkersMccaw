````markdown
# Squawkers McCaw Tiki Room / BirdPi (Refactor in progress)

Animatronic multi-Pi "Tiki Room" system powered by piCorePlayer, featuring:

- **piCorePlayer** for UI, configuration, and audio playback
- **Logitech Media Server (LMS)** for synchronized multi-room audio  
- **Squeezelite** players running on each Raspberry Pi  
- **Squawkers McCaw animatronic birds** with LED-controlled beaks, body lights, and spotlights
- A **Main Pi** running LMS, coordinating audio, and hosting the **birdpi-main** service
- **Node Pis** running `bird_daemon.py` and controlling individual birds via GPIO

## Architecture Overview

This system uses a client/server architecture where:
1. **piCorePlayer + LMS** provide the web UI and manage synchronized audio playback
2. A **Main BirdPi** (`birdpi-main`) runs `bird_daemon.py` in "main" mode and coordinates choreography
3. **Node BirdPis** (`birdpi-*`) each auto-start `bird_daemon.py` on boot in "node" mode
4. On startup, all node BirdPis automatically connect to the main BirdPi
5. The main BirdPi drives GPIO patterns across nodes based on song choreography intervals

## Quick Start

### 1. Deploy on piCorePlayer
On your main piCorePlayer device (e.g., `birdpi-main.local`):

```bash
# Clone repository to persistent storage
cd /mnt/mmcblk0p2/tc
git clone https://github.com/emricht32/SquawkersMccaw.git
```

Repeat the clone step on each node BirdPi (`birdpi-fritz`, `birdpi-pierre`, etc.).

### 2. Configure Bird Roles and Auto-start
- Configure hostnames so one Pi is `birdpi-main` and the rest are `birdpi-*` nodes.
- Configure per-bird GPIO and choreography in `config_single_bird.json` and `config_multi_song_with_triggers.json`.
- Ensure your TinyCore/piCorePlayer boot configuration starts `bird_daemon.py` on boot on all Pis.

On each Pi, `bird_daemon.py` will detect whether it is the main or a node (based on hostname) and behave accordingly. Nodes will automatically connect to the main.

### 3. Test
From the main BirdPi:
```bash
cd /mnt/mmcblk0p2/tc/SquawkersMccaw
./birdctl status
```

You should see all node BirdPis reported as connected. Start a song via LMS and observe the birds.

## TinyCore / piCorePlayer Deployment Details

### Persistent Storage Layout
All persistent data lives on the SD card partition at `/mnt/mmcblk0p2`:
```
/mnt/mmcblk0p2/tc/
  ├── SquawkersMccaw/              (this repository)
  │   ├── music/
  │   └── src/
  └── birdpi-logs/                 (daemon and system logs)
```

### Configuration Files

**Bird Hardware Config**: `config_single_bird.json` (per node)
```json
{
  "on_light": 5,
  "beak": 17,
  "body": 10,
  "lights": [24,25],
  "on_time": 0.5
}
```

`lights` may be a single GPIO number (e.g. `25`) or a list of GPIO numbers (e.g. `[24,25]`); all configured spotlight LEDs will turn on/off together when the bird is dancing.

**Song Choreography**: `config_multi_song_with_triggers.json`
Defines singing and dancing intervals for each bird in each song.

## Testing & Troubleshooting

### Check Daemon Status
```bash
cd /mnt/mmcblk0p2/tc/SquawkersMccaw
./birdctl status
```

### View Logs
```bash
tail -f /mnt/mmcblk0p2/tc/birdpi-logs/daemon.log
```

If nodes do not appear as connected, verify hostname configuration and network connectivity between Pis.

## Bird Setup

### Roles & Hostnames
- Main: `birdpi-main` (runs LMS, plus runs Jose)
- Node: `birdpi-fritz`, `birdpi-pierre`, `birdpi-michael`, etc.

Each node runs Squeezelite and controls one physical bird via GPIO.

### GPIO Pin Mapping
Default pins (BCM numbering):
- Beak LED: GPIO 17
- Body LED: GPIO 10  
- Spotlight: GPIO 25

Configure per-node in `config_single_bird.json`.

### Song Choreography Format
```json
{
  "name": "tiki",
  "individuals": [
    {
      "name": "Fritz",
      "singing": [[0, 5], [10, 15]],
      "dancing": [[5, 10]]
    }
  ]
}
```
- `singing`: Beak moves, body/spotlight on
- `dancing`: Body/spotlight on only

## Development

### Local Testing (Without GPIO)
The system gracefully degrades without `gpiozero`:
```bash
cd src
python3 -c "import bird; print('bird module imported successfully')"
```

### Adding New Songs
1. Place audio files in `music/<song_name>/`
2. Add choreography to `config_multi_song_with_triggers.json`
3. Add song metadata to LMS library

### Updating bird_daemon or bird.py
After editing `src/bird_daemon.py` or `src/bird.py`, redeploy your changes by pulling the latest code on each Pi and rebooting so `bird_daemon.py` is restarted with the new logic.

## API & Health Monitoring

The system no longer includes a custom web interface. Use:
- **piCorePlayer Web UI**: `http://birdpi-main.local` (port 80)
- **LMS Web UI**: `http://birdpi-main.local:9000`
- **Daemon logs**: `/mnt/mmcblk0p2/tc/birdpi-logs/daemon.log`

## Deprecated Features

The following components have been moved to `deprecated/` and are no longer actively maintained:
- Custom Python web interface (`web_interface.py`)
- Direct audio playback orchestration (`play_audio.py`)
- Bird registry and provisioning systems
- BLE song selector
- Voice input/speech recognition
- WiFi credential exchange

These are replaced by piCorePlayer's native UI and the `bird_daemon.py`-based architecture.

## Version History

See [CHANGELOG.md](CHANGELOG.md) for detailed release notes.

Current version: **0.12.0** (bird_daemon-based multi-Pi architecture)

## License

See [LICENSE](LICENSE) file for details.

````
