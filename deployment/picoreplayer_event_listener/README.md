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

## Notes
- The setup script bundles a fresh copy of `bird.py` each run; rerun after updates.
- If Python 3 isn't available on piCorePlayer, install the appropriate extension or invoke via `python` if aliased.
- Directory must persist across reboots; ensure it's under a persistent TCE path.
- Extend `event_listener.py` to map additional events as needed.
