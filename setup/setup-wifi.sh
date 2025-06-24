#!/bin/bash

set -e

LOG_TAG="BirdPi Setup"

echo "== BirdPi WiFi + AP Setup =="

### 1. Copy service and boot script
echo "-> Copying system files..."
sudo cp setup/birdpi-wifi-or-ap.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/birdpi-wifi-or-ap.sh

sudo cp setup/birdpi-wifi.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/birdpi-wifi.service

### 2. Install needed packages
echo "-> Installing dependencies..."
sudo apt-get update
sudo apt-get install -y hostapd dnsmasq lighttpd python3-gpiozero

### 3. Disable default daemons
sudo systemctl disable hostapd
sudo systemctl disable dnsmasq

### 4. Configure dnsmasq
echo "-> Configuring dnsmasq..."
cat <<EOF | sudo tee /etc/dnsmasq.conf > /dev/null
interface=wlan0
dhcp-range=192.168.4.10,192.168.4.50,12h
address=/#/192.168.4.1
EOF

### 5. Configure hostapd
echo "-> Configuring hostapd..."
cat <<EOF | sudo tee /etc/hostapd/hostapd.conf > /dev/null
interface=wlan0
ssid=BirdPi-\$(hostname)
hw_mode=g
channel=7
wmm_enabled=0
auth_algs=1
wpa=2
wpa_passphrase=moailanai
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF

sudo sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

### 6. Create AP fallback service
echo "-> Creating birdpi-ap.service..."
cat <<EOF | sudo tee /etc/systemd/system/birdpi-ap.service > /dev/null
[Unit]
Description=BirdPi AP fallback
After=network.target

[Service]
ExecStartPre=/sbin/ifconfig wlan0 192.168.4.1 netmask 255.255.255.0
ExecStart=/usr/sbin/hostapd /etc/hostapd/hostapd.conf
ExecStartPost=/usr/sbin/dnsmasq -C /etc/dnsmasq.conf
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

### 7. Optional: GPIO LED status (GPIO17)
echo "-> Setting up status LED script (GPIO17)..."
cat <<EOF | sudo tee /usr/local/bin/birdpi-led-status.py > /dev/null
from gpiozero import LED
from time import sleep
import subprocess

led = LED(17)

def is_wifi_connected():
    try:
        ip = subprocess.check_output(["hostname", "-I"]).decode().strip()
        return len(ip) > 0
    except:
        return False

while True:
    if is_wifi_connected():
        led.on()
    else:
        led.blink(on_time=0.5, off_time=0.5)
    sleep(5)
EOF

sudo tee /etc/systemd/system/birdpi-led.service > /dev/null <<EOF
[Unit]
Description=BirdPi LED Wi-Fi Indicator
After=network.target

[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/birdpi-led-status.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

### 8. Enable all services
sudo systemctl daemon-reexec
sudo systemctl enable birdpi-wifi.service
sudo systemctl enable birdpi-led.service

echo "== Setup Complete! Reboot to test =="
