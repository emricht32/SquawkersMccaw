# Squawkers McCaw Tiki Room / BirdPi

Animatronic multi-Pi “Tiki Room” system built around:

- **Logitech Media Server (LMS)** for synchronized multi-room audio  
- **Squeezelite** players running on each Raspberry Pi  
- **Squawkers McCaw animatronic birds**  
- A **Main Pi** orchestrating songs, timing, animations, and per-bird mic-style volume control  
- **Node Pis** responding to commands and providing individual audio + movement  

## TinyCore / piCorePlayer Deployment

This branch is optimized for running entirely on piCorePlayer (TinyCore Linux). Root FS is a RAM tmpfs; all persistent data lives on the mounted SD card partition at `/mnt/mmcblk0p2`.

### Roles & Hostnames
Use static hostnames so the main controller can coordinate without provisioning:
- Main: `birdpi-main`
- Nodes: `birdpi-fritz`, `birdpi-pierre`, `birdpi-michael` (Jose is driven by master audio channel)

Each Pi runs a Squeezelite player registered to LMS. The master adjusts per-bird volumes to create a “mic” presence effect.

### Persistent Layout
Runtime scripts place caches and installed packages under:
```
 /mnt/mmcblk0p2/birdpi/
	 ├── venv/              (optional virtualenv)
	 ├── python-packages/   (--target installs if venv unavailable)
	 ├── pip-cache/         (pip download cache)
	 ├── tmp/               (TMPDIR for builds)
	 ├── log/               (master.log, node-*.log, boot.log)
```

### Installation
On first boot (or after clearing), run with the `--install` flag to pull Python dependencies to persistent storage.
Main example (from repo root on `birdpi-main`):
```
./run_main.sh --install
```
Node example (on e.g. `birdpi-fritz`):
```
./run_node.sh --install
```
Subsequent boots can omit the flag for faster start.

### Automatic Startup (bootlocal)
Copy or move the repository to the persistent partition (example path: `/mnt/mmcblk0p2/SquawkersMccaw`). Then install the provided `bootlocal.sh` into TinyCore’s persistent boot script location:
```
sudo cp /mnt/mmcblk0p2/SquawkersMccaw/bootlocal.sh /opt/bootlocal.sh
```
Run TinyCore’s backup to persist:
```
pcp bu
```
On next reboot, `bootlocal.sh` waits briefly for network/LMS and launches `run_main.sh` if hostname == `birdpi-main` else `run_node.sh`.

### Configuration
System config lives in `config/system.json` and now uses a static `birds` mapping plus `main` player definition. Validation timings:
- `startup_validation_delay`: seconds after launch to perform initial bird presence check.
- `periodic_validation_interval`: interval for recurring checks.

### Health Endpoint
`/api/health` returns: status, version, uptime time, bird count and list of registered birds. See `tests/test_health.py` for assertions.

### Removed / Deprecated Features
Provisioning (WiFi credential exchange), BLE song selector, and voice input (Vosk) have been removed to slim dependencies and footprint. README sections and code relating to these features were deleted.

### Space & Memory Notes
TinyCore’s RAM is limited; avoid compiling large wheels in tmpfs. The scripts set `TMPDIR` and `PIP_CACHE_DIR` to persistent storage to mitigate “No space left on device” errors.

### Updating Dependencies
If you need to refresh or force a clean install:
```
./run_main.sh --force-reinstall --install
./run_node.sh --force-reinstall --install
```

### Logs
Main orchestrator: `/mnt/mmcblk0p2/birdpi/log/main.log`
Nodes: `/mnt/mmcblk0p2/birdpi/log/node-<name>.log`
Boot events: `/mnt/mmcblk0p2/birdpi/log/boot.log`

### Next Steps / Optional Slimming
Consider removing `pyaudio` or `evdev` from `pi-requirements.txt` if not required for current hardware to further reduce install size.

---
For historical provisioning documentation and deprecated modules, consult previous tags or branches (pre 0.9.x).
