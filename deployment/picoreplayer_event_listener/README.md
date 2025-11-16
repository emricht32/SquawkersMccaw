# piCorePlayer Event Listener Plugin Integration

This directory contains files to integrate the SquawkersMccaw Bird.py logic with piCorePlayer's Event Listener plugin system.

## Files
- `event_listener.py`: Python script to be called by piCorePlayer event actions. It invokes `bird.py` with translated event arguments.
- `bird.py`: Synchronized copy of your main bird logic from `src/common/bird.py` (lowercase preserved).
- `setup_picoreplayer_event_listener.sh`: Deployment script; supports local path copy or remote `scp` to a piCorePlayer host.

## Setup Instructions
1. Make/commit any changes to `src/common/bird.py`.
2. Deploy locally OR remotely:
    - Local copy:
       ```sh
       cd deployment
       ./setup_picoreplayer_event_listener.sh /mnt/mmcblk0p2/tce/userplugins/eventlistener
       ```
    - Remote deploy via scp:
       ```sh
       cd deployment
       ./setup_picoreplayer_event_listener.sh tc@birdpi-node.local:/mnt/mmcblk0p2/tce/userplugins/eventlistener
       ```
       (Adjust user/host/path to match your device.)
3. Configure piCorePlayer Event Listener actions in the web UI:
    - Example start event:
       ```sh
       python3 /mnt/mmcblk0p2/tce/userplugins/eventlistener/event_listener.py SONG_START tiki
       ```
    - Example stop event:
       ```sh
       python3 /mnt/mmcblk0p2/tce/userplugins/eventlistener/event_listener.py SONG_STOP
       ```
    - You can also pass `--song <name>` instead of a bare song name: `SONG_START --song tiki`.

## Testing

### Local Validation
Before deploying, validate your config:
```sh
cd deployment/picoreplayer_event_listener
python3 validate_lms_config.py lmseventtrigger.json
```

### Full Deployment & Test
Deploy everything and run diagnostics:
```sh
cd deployment/picoreplayer_event_listener
./deploy_and_test.sh tc@birdpi-main.local
```

### Manual Testing
Test individual components:
```sh
cd deployment/picoreplayer_event_listener
./test_event_trigger.sh local   # Local validation
./test_event_trigger.sh remote  # With remote LMS checks
```

## Troubleshooting

### reloadConfig Fails
Common causes:
1. **JSON syntax error** - Run validator: `python3 validate_lms_config.py lmseventtrigger.json`
2. **File permissions** - Config must be readable: `sudo chmod 644 /etc/lmseventtrigger.json`
3. **Wrong location** - Must be at `/etc/lmseventtrigger.json` (not `/etc/lmseventtrigger.conf`)
4. **LMS cache** - Restart LMS: `sudo systemctl restart squeezeboxserver`

### Events Not Triggering
Check in order:
1. **Config deployed?** `ls -la /etc/lmseventtrigger.json`
2. **Plugin enabled?** `curl http://birdpi-main:9000/plugins/LMSeventTrigger/js.html?cmd=enable`
3. **Script exists?** `ls -la /mnt/mmcblk0p2/tc/SquawkersMccaw/deployment/picoreplayer_event_listener/event_listener.py`
4. **Script executable?** `chmod +x event_listener.py`
5. **Check logs:** `tail -f /mnt/mmcblk0p2/tc/birdpi-logs/event_listener.log`
6. **LMS logs:** `journalctl -u squeezeboxserver -f` or check `/var/log/squeezeboxserver/server.log`

### Test Manual Trigger
```sh
ssh tc@birdpi-main.local
cd /mnt/mmcblk0p2/tc/SquawkersMccaw/deployment/picoreplayer_event_listener
./event_listener.py SONG_START test_song
```

## Notes
- The setup script bundles a fresh copy of `bird.py` each run; rerun after updates.
- If Python 3 isn't available on piCorePlayer, install the appropriate extension or invoke via `python` if aliased.
- Directory must persist across reboots; ensure it's under a persistent TCE path.
- Extend `event_listener.py` to map additional events as needed.
- LMSeventTrigger.json location MUST be `/etc/lmseventtrigger.json` (case-sensitive)
