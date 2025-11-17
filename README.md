````markdown
# Squawkers McCaw Tiki Room / BirdPi

Animatronic multi-Pi "Tiki Room" system powered by piCorePlayer, featuring:

- **piCorePlayer** for UI, configuration, and audio playback
- **Logitech Media Server (LMS)** for synchronized multi-room audio  
- **Squeezelite** players running on each Raspberry Pi  
- **LMS Event Trigger Plugin** to synchronize bird animations with music
- **Squawkers McCaw animatronic birds** with LED-controlled beaks, body lights, and spotlights
- A **Main Pi** running LMS and coordinating audio
- **Node Pis** controlling individual birds via GPIO

## Architecture Overview

This system uses an event-driven architecture where:
1. **piCorePlayer** provides the web UI and manages Squeezelite players
2. **LMS** handles audio playback and triggers events on song changes
3. **LMS Event Trigger Plugin** invokes `event_listener.py` on playlist events
4. **event_listener.py** calls `bird.py` with song metadata (name, time, duration)
5. **bird.py** controls GPIO LEDs based on song choreography intervals

## Quick Start

### 1. Deploy on piCorePlayer
On your piCorePlayer device (e.g., `birdpi-main.local`):

```bash
# Clone repository to persistent storage
cd /mnt/mmcblk0p2/tc
git clone https://github.com/emricht32/SquawkersMccaw.git

# Deploy event listener plugin
cd SquawkersMccaw/deployment
./setup_picoreplayer_event_listener.sh tc@birdpi-main.local:/mnt/mmcblk0p2/tc/SquawkersMccaw/deployment/picoreplayer_event_listener
```

### 2. Configure LMS Event Trigger
Copy the event trigger configuration:
```bash
sudo cp deployment/picoreplayer_event_listener/lmseventtrigger.json /etc/lmseventtrigger.json
sudo chmod 644 /etc/lmseventtrigger.json
sudo systemctl restart squeezeboxserver
```

### 3. Test
```bash
cd /mnt/mmcblk0p2/tc/SquawkersMccaw/deployment/picoreplayer_event_listener
./event_listener.py SONG_START tiki
```

Check logs:
```bash
tail -f /mnt/mmcblk0p2/tc/birdpi-logs/event_listener.log
```

## TinyCore / piCorePlayer Deployment Details

### Persistent Storage Layout
All persistent data lives on the SD card partition at `/mnt/mmcblk0p2`:
```
/mnt/mmcblk0p2/tc/
  ├── SquawkersMccaw/              (this repository)
  │   ├── deployment/
  │   │   └── picoreplayer_event_listener/
  │   │       ├── event_listener.py
  │   │       ├── bird.py (synced from src/common/)
  │   │       └── lmseventtrigger.json
  │   ├── config/
  │   ├── music/
  │   └── src/
  └── birdpi-logs/                 (event listener logs)
```

### Configuration Files

**Bird Hardware Config**: `config_single_bird.json` (per node)
```json
{
    "on_light": 5,
    "beak": 19,
    "body": 16,
    "light": 25,
    "on_time": 0.5
}
```

**Song Choreography**: `config_multi_song_with_triggers.json`
Defines singing and dancing intervals for each bird in each song.

**LMS Event Trigger**: `/etc/lmseventtrigger.json`
```json
{
    "enabled": true,
    "numStatusResults": 1,
    "events": [
        {
            "cmd": "/mnt/mmcblk0p2/tc/SquawkersMccaw/run_event_listener.sh",
            "event": [
                ["playlist"],
                ["newsong"]
            ]
        }
    ]
}
```

## Testing & Troubleshooting

### Validate Configuration
```bash
cd deployment/picoreplayer_event_listener
python3 validate_lms_config.py lmseventtrigger.json
```

### Run Full Test Suite
```bash
./test_event_trigger.sh local    # Local validation
./test_event_trigger.sh remote   # With LMS connectivity check
```

### Deploy & Test End-to-End
```bash
./deploy_and_test.sh tc@birdpi-main.local
```

### Common Issues

**Events Not Triggering:**
1. Check config location: `ls -la /etc/lmseventtrigger.json`
2. Verify script is executable: `chmod +x event_listener.py`
3. Check logs: `tail -f /mnt/mmcblk0p2/tc/birdpi-logs/event_listener.log`
4. Restart LMS: `sudo systemctl restart squeezeboxserver`

**reloadConfig Fails:**
- JSON syntax error (run validator)
- File permissions (must be readable by squeezeboxserver user)
- Wrong file location (must be `/etc/lmseventtrigger.json`)

See `deployment/picoreplayer_event_listener/README.md` for detailed troubleshooting.

## Bird Setup

### Roles & Hostnames
- Main: `birdpi-main` (runs LMS, plus runs Jose)
- Node: `birdpi-fritz`, `birdpi-pierre`, `birdpi-michael`, etc.

Each node runs Squeezelite and controls one physical bird via GPIO.

### GPIO Pin Mapping
Default pins (BCM numbering):
- Beak LED: GPIO 19
- Body LED: GPIO 16  
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
cd src/common
python3 bird.py --song tiki --config ../../config_single_bird.json
```

### Adding New Songs
1. Place audio files in `music/<song_name>/`
2. Add choreography to `config_multi_song_with_triggers.json`
3. Add song metadata to LMS library

### Updating bird.py
After editing `src/common/bird.py`:
```bash
cd deployment
./setup_picoreplayer_event_listener.sh tc@<hostname>:/mnt/mmcblk0p2/tc/SquawkersMccaw/deployment/picoreplayer_event_listener
```

## API & Health Monitoring

The system no longer includes a custom web interface. Use:
- **piCorePlayer Web UI**: `http://birdpi-main.local` (port 80)
- **LMS Web UI**: `http://birdpi-main.local:9000`
- **Event logs**: `/mnt/mmcblk0p2/tc/birdpi-logs/event_listener.log`

## Deprecated Features

The following components have been moved to `deprecated/` and are no longer actively maintained:
- Custom Python web interface (`web_interface.py`)
- Direct audio playback orchestration (`play_audio.py`)
- Bird registry and provisioning systems
- BLE song selector
- Voice input/speech recognition
- WiFi credential exchange

These are replaced by piCorePlayer's native UI and the LMS Event Trigger integration.

## Version History

See [CHANGELOG.md](CHANGELOG.md) for detailed release notes.

Current version: **0.11.0** (piCorePlayer Event Integration)

## License

See [LICENSE](LICENSE) file for details.

````
