# Changelog

All notable changes to this project are documented here. Follow semantic versioning: MAJOR.MINOR.PATCH.

## 0.12.1 - 2025-12-27
### Added
- **Fallback Wi-Fi Access Point (AP) Installer**: Added `birdpi_install_fallback_ap.sh` for piCorePlayer-based BirdPis.
  - Installs `hostapd.conf` and `dnsmasq.conf` under `/mnt/mmcblk0p2/tc/birdpi-ap/`.
  - Writes `birdpi-fallback-ap.sh` and appends a small hook to `/opt/bootlocal.sh` so that, if Wi-Fi does not connect within a timeout, the Pi starts an AP with SSID `BirdPi` (passphrase `squawkers`).
  - Logs activity to `/mnt/mmcblk0p2/tc/birdpi-logs/fallback_ap.log`.

## 0.12.0 - 2025-11-29
### Changed
- **Architecture**: Removed dependency on the LMS Event Trigger / `event_listener.py` flow in favor of a persistent `bird_daemon.py` process.
- **Startup**: All BirdPis now auto-start `bird_daemon.py` on boot (role determined by hostname).
- **Connectivity**: All node BirdPis automatically discover and connect to the `birdpi-main` instance.
- **Docs**: Updated `README.md` to describe the new bird_daemon-based architecture and startup behavior.

## 0.11.0 - 2025-11-16
### Added
- **piCorePlayer Event Listener Integration**: Added LMS Event Trigger plugin support for bird movement triggers via `deployment/picoreplayer_event_listener/`.
  - `event_listener.py`: Receives LMS playlist events and invokes `bird.py` with song metadata.
  - `lmseventtrigger.json`: Configuration file for LMS Event Trigger plugin.
  - `bird.py` now accepts `--time` and `--duration` arguments for mid-song sync.
  - Comprehensive testing suite: `validate_lms_config.py`, `test_event_trigger.sh`, `deploy_and_test.sh`.
- Event listener logging to persistent storage: `/mnt/mmcblk0p2/tc/birdpi-logs/event_listener.log`.
- Setup script with remote deployment support via scp: `setup_picoreplayer_event_listener.sh`.

### Changed
- **Architecture Shift**: System now relies on piCorePlayer for UI, audio playback, and bird movement triggers instead of custom Python web interface.
- `bird.py` refactored with improved error handling, standalone operation without `utils` module, and better hostname parsing.
- Moved deprecated/unused files to `deprecated/` folder for cleaner project structure.
- Updated deployment documentation with piCorePlayer-specific paths and troubleshooting.

### Removed
- Custom web UI components (now handled by piCorePlayer/LMS web interface).
- Python-based audio playback orchestration (delegated to LMS/Squeezelite).
- Direct bird registry and provisioning systems (simplified to event-driven model).

### Fixed
- Corrected `.lowercase()` to `.lower()` in `bird.py`.
- Fixed hostname parsing to properly handle `birdpi-*` prefix and `.local` suffix.
- Prevented negative LED oscillation durations.
- Added defensive handling for missing configs and song data.

### Internal
- Enhanced testing infrastructure for LMS integration validation.
- Added JSON validation tools for event trigger configuration.

## 0.10.1 - 2025-11-14
### Changed
- Renamed role terminology from 'master' to 'main' across scripts, config, and docs.
- Added backward compatibility for legacy 'master' key ('main' now preferred).

### Internal
- Log file names updated (master.log -> main.log).

## 0.10.0 - 2025-11-13
### Added
- TinyCore / piCorePlayer deployment documentation (persistent layout, bootlocal usage).
- `bootlocal.sh` automatic role-based startup script.

### Changed
- Rewrote `run_main.sh` and `run_node.sh` for TinyCore persistent storage strategy, eliminating apt-based steps.
- Updated README to reflect static hostname mapping and validation timings.

### Removed
- Legacy provisioning flow (WiFi credential exchange).
- BLE song selector (bluezero dependency).
- Voice input / speech recognition (vosk + pyaudio usage).
- Remote input experimental module (`remote_input.py`) and `evdev` dependency to slim footprint.

### Internal
- Version bump to 0.10.0 surfaced via `/api/health`.

## 0.9.0 - 2025-11 (previous)
- Initial removal of provisioning and BLE + voice features; introduced startup/periodic validation; added version reporting.

---
Older history available in prior branches/tags.