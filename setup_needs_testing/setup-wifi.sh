#!/bin/bash
set -e

echo "== BirdPi WiFi Onboarding Setup =="

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$REPO_DIR/setup_needs_testing"

# 1. Install required packages
echo "-- Installing required packages..."
sudo apt-get update
sudo apt-get install -y lighttpd dnsmasq hostapd network-manager

# 2. Enable CGI in lighttpd
echo "-- Enabling CGI module for lighttpd..."
if ! sudo lighttpd-enable-mod cgi; then
    echo "lighttpd-enable-mod cgi failed, possibly already enabled. Continuing."
fi

# FIX: Reload lighttpd to actually enable the CGI module!
sudo service lighttpd force-reload

# 3. Copy all static files (except hostapd.conf) to the same location as in SRC
echo "-- Copying config, HTML, CGI, and service files..."
cd "$SRC"

find . \( -name hostapd.conf \) -prune -o -type f -print | while read FILE; do
    DEST="/${FILE#./}"    # strip the leading dot for absolute path
    DEST_DIR=$(dirname "$DEST")
    sudo mkdir -p "$DEST_DIR"
    sudo cp "$FILE" "$DEST"
done

# 4. Generate/persist BirdPi AP ID (random 4 alphanumeric chars)
echo "-- Ensuring BirdPi AP has a persistent unique ID..."
if [ ! -f /etc/birdpi_ap_id ]; then
  tr -dc 'A-Za-z0-9' </dev/urandom | head -c 4 | sudo tee /etc/birdpi_ap_id > /dev/null
fi
BIRDPI_AP_ID=$(cat /etc/birdpi_ap_id)

# 5. Copy hostapd.conf template with correct AP ID
echo "-- Setting up hostapd config with unique SSID..."
sudo sed "s/XXXX/$BIRDPI_AP_ID/" "$SRC/etc/hostapd/hostapd.conf" | sudo tee /etc/hostapd/hostapd.conf > /dev/null

sudo sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

# 6. Ensure scripts are executable
echo "-- Making scripts executable..."
sudo chmod +x /usr/lib/cgi-bin/submit.sh || true
sudo chmod +x /usr/local/bin/birdpi-wifi-or-ap.sh || true

# 7. Enable and restart services
echo "-- Enabling and restarting required services..."
sudo systemctl daemon-reload
sudo systemctl enable lighttpd
sudo systemctl restart lighttpd
sudo systemctl enable birdpi-ap.service
sudo systemctl enable birdpi-wifi.service

echo "== Setup complete! =="
echo "Reboot your Pi and connect to the 'BirdPi-$BIRDPI_AP_ID' WiFi if no network is configured."
echo "The captive portal will be available at http://192.168.4.1"
