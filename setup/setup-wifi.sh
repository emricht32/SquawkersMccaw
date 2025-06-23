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

### 7. Setup captive portal (redirect)
echo "-> Configuring captive portal redirect..."
sudo sed -i '/server.document-root/a \
$HTTP["host"] =~ ".*" {\n\
  url.redirect = (\n\
    "^/generate_204" => "/",\n\
    "^/hotspot-detect.html" => "/",\n\
    "^/ncsi.txt" => "/",\n\
    "^/connecttest.txt" => "/",\n\
    "^/.*" => "/" )\n\
}' /etc/lighttpd/lighttpd.conf

### 8. Create Wi-Fi form and CGI
echo "-> Setting up CGI and form handler..."

sudo mkdir -p /var/www/cgi-bin
cat <<EOF | sudo tee /var/www/cgi-bin/submit.sh > /dev/null
#!/bin/bash

echo "Content-type: text/html"
echo ""

read POST_STRING

SSID=\$(echo "\$POST_STRING" | sed -n 's/.*ssid=\([^&]*\).*/\1/p' | sed 's/%20/ /g')
PASS=\$(echo "\$POST_STRING" | sed -n 's/.*password=\([^&]*\).*/\1/p' | sed 's/%20/ /g')

SSID=\$(printf "%b" "\${SSID//%/\\x}")
PASS=\$(printf "%b" "\${PASS//%/\\x}")

echo "<html><body><h1>Connecting to \$SSID...</h1>"

if [[ -n "\$SSID" && -n "\$PASS" ]]; then
    cat <<WPA > /etc/wpa_supplicant/wpa_supplicant.conf
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

network={
    ssid="\$SSID"
    psk="\$PASS"
}
WPA

    chmod 600 /etc/wpa_supplicant/wpa_supplicant.conf
    echo "<p>Wi-Fi config saved. Rebooting...</p></body></html>"
    sleep 3
    reboot
else
    echo "<p>Error: SSID or password missing.</p></body></html>"
fi
EOF

sudo chmod +x /var/www/cgi-bin/submit.sh

sudo tee /var/www/html/index.html > /dev/null <<EOF
<!DOCTYPE html>
<html>
<head><title>BirdPi Wi-Fi Setup</title></head>
<body>
  <h1>Connect BirdPi to Wi-Fi</h1>
  <form method="POST" action="/submit">
    <label>Wi-Fi Name (SSID):</label><br/>
    <input type="text" name="ssid"><br/>
    <label>Password:</label><br/>
    <input type="password" name="password"><br/><br/>
    <input type="submit" value="Connect">
  </form>
</body>
</html>
EOF

### 9. Lighttpd config for CGI
sudo sed -i '/server.modules/ s|)|, "mod_cgi")|' /etc/lighttpd/lighttpd.conf
sudo tee -a /etc/lighttpd/lighttpd.conf > /dev/null <<EOF

cgi.assign = (
    ".sh" => "/bin/bash"
)

alias.url += ( "/submit" => "/var/www/cgi-bin/submit.sh" )
EOF

### 10. Optional: GPIO LED status (GPIO17)
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

### 11. Enable all services
sudo systemctl daemon-reexec
sudo systemctl enable birdpi-wifi.service
sudo systemctl enable birdpi-led.service

echo "== Setup Complete! Reboot to test =="
