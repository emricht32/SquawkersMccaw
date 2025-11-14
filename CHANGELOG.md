# Changelog

All notable changes to this project are documented here. Follow semantic versioning: MAJOR.MINOR.PATCH.

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