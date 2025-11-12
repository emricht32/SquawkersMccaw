# SquawkersMccaw

## Multi-Room Audio & Bird Synchronization

This project coordinates animatronic bird movements with synchronized audio playback across multiple Raspberry Pis. Audio synchronization uses Logitech Media Server (LMS) with Squeezelite (provided by piCorePlayer). Each bird Pi runs piCorePlayer and has a dedicated speaker. A single master audio track plays on all speakers; per-bird speaking moments are created by dynamically adjusting each player's volume (mute/unmute or background vs speaking level).

### LMS Integration Fields

Each song can include an `lms_track` entry pointing to a file or URL accessible by LMS:

```json
{
	"name": "tiki_intro",
	"display_name": "Tiki Room Intro",
	"lms_track": "/music/TikiRoom/intro.mp3",
	"individuals": [
		{ "name": "Fritz", "singing": [[0.0, 4.2], [10.0, 12.5]] },
		{ "name": "Pierre", "singing": [[4.3, 9.9]] }
	],
	"all_singing": [],
	"all_dancing": []
}
```

Dynamic Player Mapping (Headless): Bird nodes now self-register with their MAC addresses via the `/register` endpoint. The master builds a dynamic map (bird name → MAC) automatically—no manual `bird_player_map` section required. If a static map is omitted (recommended), the system uses the dynamic map for volume scheduling.

## Provisioning Access Point (AP) Strategy

The master Pi exposes a temporary WiFi Access Point ONLY during provisioning. Multi-room streaming afterwards relies on the regular house WiFi (STA mode) for all players.

### Master Boot Logic
1. Check for stored credentials (`wifi_credentials.json`).
2. If absent: start AP (e.g., SSID `BirdMasterSetup`) + Flask web UI.
3. User connects to AP, submits SSID/password via form calling `POST /api/wifi/config`.
4. Credentials saved; system applies them and switches to house WiFi.
5. AP is stopped to reclaim bandwidth and reduce interference.

### Node Boot Logic
1. Attempt to load credentials locally.
2. If credentials exist, connect to house WiFi; then register with master (`/register`).
3. If credentials missing, scan for provisioning SSID and connect to master AP.
4. Retrieve credentials via `GET /api/wifi/credentials`.
5. Save, apply, reconnect to house WiFi, then register.

### WiFi API Endpoints
Implemented in `web_interface.py`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/wifi/status` | GET | Basic configured/connected info (placeholder values) |
| `/api/wifi/config` | POST | Accept `{ssid,password}` and store/apply credentials |
| `/api/wifi/credentials` | GET | Nodes pull credentials if not provisioned |

Credential management logic resides in `provisioning.py`.

### Security Considerations
Current implementation sends and stores passwords in plaintext:

| Risk | Mitigation Options |
|------|--------------------|
| Plaintext over HTTP | Serve provisioning UI via HTTPS (self-signed cert) |
| Unrestricted credential endpoint | Disable `/api/wifi/credentials` after provisioning completes |
| Password at rest readable | Restrict file perms (chmod 600) or move to root-owned path |
| Replay of provisioning requests | Use one-time token or short-lived signed JWT for credential POST |
| Exposure during AP phase | Limit AP broadcast window; auto-shutdown after N minutes |

Future hardening steps can include encrypting the stored password (key derivation from hardware ID) or using WPA3 SAE handshake only (no need to transmit password again after initial entry).

### Optional BLE Fallback
If a node cannot see the provisioning AP, a BLE GATT service could advertise a custom characteristic for encrypted credential exchange. This is not implemented yet; `bleak` can be used for Python-based BLE.

## Developer Notes

Relevant modules:
* `lms_control.py` – LMS telnet control + volume scheduling.
* `provisioning.py` – WiFi credential storage & placeholder application.
* `web_interface.py` – REST endpoints for birds, songs, provisioning.

## Running Provisioning (Manual Example)

On fresh master with no credentials file:
1. Master starts AP & web server (implement AP startup script separately).
2. User connects to AP and opens root page → enters WiFi details.
3. Master saves credentials and switches to house WiFi.
4. Nodes boot, pull credentials if needed.

## Next Improvements
* Implement real WiFi application (edit system config, restart services).
* Add a `PROVISIONING_ACTIVE` flag to disable credential endpoint post-setup.
* Centralize `bird_player_map` + WiFi initial state in a single JSON config.
* Add test harness to simulate song and volume changes.

## Fresh Multi-Bird Deployment (piCorePlayer OS)

The following checklist gets a master plus multiple bird nodes running from scratch using piCorePlayer (pCP) images.

### 1. Prepare LMS (Logitech Media Server)
Install LMS on a stable device (can be the master Pi if resources allow):
* Raspberry Pi OS: `sudo apt install logitechmediaserver` (or use official deb)
* Docker: run an LMS container exposing port 9090 (CLI) and 9000 (web UI)
* Confirm reachable at `http://<lms-host>:9000` and CLI on port 9090.

### 2. Flash piCorePlayer Images
For each bird and the master:
1. Download latest piCorePlayer image.
2. Flash to SD card.
3. Boot. Use the pCP web UI (http://pcp.local or discovered IP) to:
	 * Set unique hostname (e.g. `bird-fritz`, `bird-pierre`, `bird-michael`, `bird-jose`, `bird-master`).
	 * Enable SSH.
	 * Enable WiFi (initially can use Ethernet for master if available).

### 3. Install Required Extensions on Master
Master needs Python + Git + AP tooling:
* Via pCP web UI Extensions page OR SSH:
	```bash
	tce-load -wi python3 git hostapd dnsmasq
	```
Persist with pCP backup after install (UI button or `pcp bu`).

### 4. Clone This Repository on Master
```bash
git clone https://github.com/emricht32/SquawkersMccaw.git
cd SquawkersMccaw
# (Optional) create a virtual environment if python3-venv available
python3 -m venv .venv && source .venv/bin/activate || true
pip install -r requirements.txt || true
```

### 5. Configure System Settings
Edit `config/system.json` (or create `/boot/BIRDPI/system.json`):
```json
{
	"lms": { "host": "<lms-ip>", "port": 9090 },
	"provisioning": { "force_ap": false }
}
```
No bird mapping needed—the registration agent sends each node's MAC automatically. Ensure each Squeezelite player name matches the desired bird name so assignment logic remains consistent.

### 6. Start Backend
From repo root:
```bash
python3 -m src.birdpi_main.main
```
If no `wifi_credentials.json` exists the master provisioning AP should be started manually (see next step) until credentials are saved.

### 7. Provisioning Access Point (Master Only)
If you need the AP (first-time WiFi setup):
```bash
# Create AP interface
iw dev wlan0 interface add uap0 type __ap
ip addr add 192.168.50.1/24 dev uap0
ip link set uap0 up

# hostapd.conf example
cat > /tmp/hostapd.conf <<EOF
interface=uap0
driver=nl80211
ssid=BirdMasterSetup
hw_mode=g
channel=6
country_code=US
auth_algs=1
ieee80211n=1
wmm_enabled=1
EOF

# dnsmasq.conf example
cat > /tmp/dnsmasq.conf <<EOF
interface=uap0
bind-interfaces
dhcp-range=192.168.50.10,192.168.50.50,12h
EOF

hostapd /tmp/hostapd.conf &
dnsmasq -C /tmp/dnsmasq.conf &
```
Browse to `http://192.168.50.1:8080` (Flask server) → enter SSID & password in WiFi panel. On success:
* Credentials saved to `wifi_credentials.json`.
* `apply_credentials()` writes wpa_supplicant config and attempts reconfigure.
* Provisioning deactivates and AP shutdown logic runs.

### 8. Bird Nodes Setup
On each bird Pi (nodes):
1. In pCP web UI, configure Squeezelite with a unique name matching bird name (e.g., Fritz). This name will appear in LMS aiding player identification.
2. Ensure audio DAC recognized (USB / HAT). Test playback from LMS.
3. If node lacks credentials and master AP is active, connect manually or run a lightweight fetch script (future automation):
	 ```bash
	 curl http://192.168.50.1:8080/api/wifi/credentials -o creds.json
	 jq -r '.ssid' creds.json
	 jq -r '.password' creds.json
	 # Manually add to node's wpa_supplicant and reboot WiFi
	 ```
4. Nodes register automatically via existing `/register` call when their local client script (to be deployed) starts. (You can adapt a minimal registration agent based on current `web_interface` expectations.)

### 9. Verify LMS & Volume Scheduling
* In LMS UI, group (synchronize) bird players if needed (single master track on all speakers).
* Bird names and MACs appear dynamically after registration; confirm via `/register` responses or `/api/birds`.
* Trigger a song from web UI. Check `/api/volume_dry_run` first:
	```bash
	curl -X POST -H 'Content-Type: application/json' -d '{"song":"tiki_intro"}' http://<master-ip>:8080/api/volume_dry_run
	```
* Observe volumes change on players (LMS settings or logs) during speaking intervals.

### 10. Health Checks
```bash
curl http://<master-ip>:8080/api/health
```
Returns provisioning state, bird count, credential presence.

### 11. Persistence on piCorePlayer
After changes (repo clone, config edits), run pCP backup so they survive reboot:
```bash
pcp bu
```

### 12. Optional Hardening
* Replace HTTP with HTTPS (Caddy/nginx reverse proxy + self-signed cert).
* Disable `/api/wifi/credentials` permanently once all nodes provisioned (already auto-disabled when provisioning ends).
* Restrict file permissions: `chmod 600 wifi_credentials.json`.

## Node Registration Agent (Future Suggestion)
Implement a small Python script on each bird node:
```python
import requests, time, socket
def register(master_ip, name=None):
		payload={"id": socket.gethostname(), "time": time.time(), "name": name}
		r=requests.post(f"http://{master_ip}:8080/register", json=payload, timeout=2)
		print(r.json())
```
Schedule on boot (cron @reboot or systemd service). This lets the master track nodes without manual intervention.

## Summary of Endpoints
| Endpoint | Purpose |
|----------|---------|
| `/api/songs` | List selectable songs |
| `/api/select` | Start song (schedule audio + movement) |
| `/api/cancel` | Cancel current song |
| `/register` | Node registration (id, time, optional name, mac) |
| `/api/birds` | Current bird registry with MACs |
| `/api/wifi/status` | WiFi configured/connected snapshot |
| `/api/wifi/config` | Store & apply credentials (provisioning) |
| `/api/wifi/credentials` | Node credential fetch (disabled after provisioning) |
| `/api/provisioning/state` | Provisioning active flag |
| `/api/health` | System health summary |
| `/api/volume_dry_run` | Simulated per-bird volume events |


# Squawkers McCaw Tiki Room

## Overview

This project recreates Disney's Enchanted Tiki Room using Squawkers McCaw animatronic birds, a Raspberry Pi, and custom software/hardware. It features BLE, remote control, and a mobile-friendly web interface — allowing users to trigger music and animations wirelessly.

## Table of Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Hardware Setup](#hardware-setup)
4. [Usage](#usage)
5. [Web UI + QR Access](#web-ui--qr-access)
6. [Auto-Start on Boot (systemd)](#auto-start-on-boot-systemd)
7. [Contributing](#contributing)
8. [License](#license)

---

## Requirements

- Raspberry Pi Zero 2W (Main)
- Raspberry Pi Zero 2W (1 per node)
- Squawkers McCaw birds (x4)
- USB sound cards (1 per bird + 1 master audio)
- GPIO-controlled SSR/relays for body movement and lighting
- ~~Motion sensor (optional)~~
- IR receiver (optional)
- Python 3.x
- Mobile phone or browser

---

## Installation

```bash
sudo apt update && sudo apt upgrade
sudo apt install -y git-lfs python3-pip libportaudio2 libsndfile1 screen git ffmpeg libcairo2-dev pkg-config python3-dev libgirepository1.0-dev gir1.2-glib-2.0
```

(Optional) If you want the Pi to broadcast its own Access Point rather then use your WiFi
```bash
curl "https://www.raspberryconnect.com/images/scripts/AccessPopup.tar.gz" -o AccessPopup.tar.gz
tar -xvf ./AccessPopup.tar.gz
cd AccessPopup
sudo ./installconfig.sh
```

Clone the repo and install dependencies:

```bash
git clone https://github.com/emricht32/SquawkersMccaw.git
cd SquawkersMccaw
./run.sh --install
# python3 -m venv birdpi-venv
# source birdpi-venv/bin/activate
# pip install -r pi-requirements.txt
```

---

## Hardware Setup

See the `/docs` and `/hardware` folder for images and wiring diagrams. Birds are triggered using GPIO pins via solid-state relays, and audio plays through dedicated USB soundcards.

---

## Usage

Run locally from the Pi:

```bash
./run_main.sh (--install)
```
This will:
- (optional with --install flag) install dependencies 
- Convert MP3s to 48kHz WAV if needed
- Load config and music from `/Volumes/BIRDPI/` or `/boot/BIRDPI` if present
- ~~Start the BLE server~~
- Start the web server at `http://birdpi.local:8080/`
- Generate a QR code with the Pi's IP

or

```bash
./run_node.sh (--install)
```

This will:
- (optional with --install flag) install dependencies 
- Register the node`s local IP address with the main (optionally as one of four bird profiles)

---

## Web UI + QR Access

A mobile-optimized web UI is served from the Raspberry Pi. On startup, the app automatically generates a QR code that links to the Pi’s web interface.

- Visit: `http://birdpi.local:8080/`
- Or `192.168.50.5`
- Or scan the displayed QR code on another device

The image is saved to `static/birds_qr.png` and displayed automatically in the web UI.

---

## Auto-Start on Boot (systemd)

Create a systemd unit to launch your `run<main|node>.sh` script:

```bash
sudo nano /etc/systemd/system/birdpi.service
```

Paste (replacing all occurences of `birdpi` with your user name):

```ini
[Unit]
Description=BirdPi App Service
After=network.target bluetooth.target

[Service]
ExecStart=/home/birdpi/code/SquawkersMccaw/run_main.sh
Restart=always
User=birdpi
WorkingDirectory=/home/birdpi/code/SquawkersMccaw
StandardOutput=append:/home/birdpi/birdpi.log
StandardError=append:/home/birdpi/birdpi.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Enable the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable birdpi.service
sudo systemctl start birdpi.service
```

---

## Notes

- ~~BLE notifications are sent when songs start and finish~~
- Songs must be sampled at 48kHz due to USB audio device limitations
- Audio separation and editing can be done using Audacity and [vocalremover.org](https://vocalremover.org)

---

## Contributing

Pull requests are welcome. Open an issue first to discuss improvements or ideas.

---

## License & Safety

> ⚠️ This project involves power control and exposed electronics. Exercise caution and only proceed if you're confident with hardware setups.

MIT License. See `LICENSE` for details.

---

## Acknowledgements

Thanks to J-Man for the original Squawker Talker board inspiration. Special thanks to Disney’s Enchanted Tiki Room for lifelong inspiration.