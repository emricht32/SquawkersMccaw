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

- Raspberry Pi 4 Model B
- Squawkers McCaw birds (x4)
- USB sound cards (1 per bird + 1 master audio)
- GPIO-controlled SSR/relays for body movement and lighting
- Motion sensor (optional)
- IR receiver (optional)
- Python 3.x
- Mobile phone or browser

---

## Installation

```bash
sudo apt update && sudo apt upgrade
sudo apt install -y git-lfs python3-pip libportaudio2 libsndfile1 screen git ffmpeg
```

Clone the repo and install dependencies:

```bash
git clone https://github.com/emricht32/SquawkersMccaw.git
cd SquawkersMccaw
python3 -m venv birdpi-venv
source birdpi-venv/bin/activate
pip install -r pi-requirements.txt
```

---

## Hardware Setup

See the `docs/` and `/hardware` folder for images and wiring diagrams. Birds are triggered using GPIO pins via solid-state relays, and audio plays through dedicated USB soundcards.

---

## Usage

Run locally from the Pi:

```bash
./run.sh
```

This will:
- Convert MP3s to 48kHz WAV if needed
- Load config from `/media/BIRDS/` if present
- Start the BLE server
- Start the web server at `http://<pi-ip>:8080/`
- Generate a QR code with the Pi's IP

---

## Web UI + QR Access

A mobile-optimized web UI is served from the Raspberry Pi. On startup, the app automatically generates a QR code that links to the Pi’s web interface.

- Visit: `http://<pi-ip>:8080/`
- Or scan the displayed QR code on another device

The image is saved to `static/birds_qr.png` and displayed automatically in the web UI.

---

## Auto-Start on Boot (systemd)

Create a systemd unit to launch your `run.sh` script:

```bash
sudo nano /etc/systemd/system/birdpi.service
```

Paste:

```ini
[Unit]
Description=BirdPi App Service
After=network.target bluetooth.target

[Service]
ExecStart=/home/pi/code/SquawkersMccaw/run.sh
Restart=always
User=pi
WorkingDirectory=/home/pi/code/SquawkersMccaw
StandardOutput=append:/home/pi/birdpi.log
StandardError=append:/home/pi/birdpi.log
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

- BLE notifications are sent when songs start and finish
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