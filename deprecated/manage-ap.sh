#!/bin/bash
#
# manage-ap.sh
#
# Starts or stops the provisioning Access Point on the master Pi.
# This script is intended for Raspberry Pi OS or similar Debian-based systems.
#
# Usage:
#   sudo ./manage-ap.sh start
#   sudo ./manage-ap.sh stop
#
# Prerequisites:
#   - hostapd
#   - dnsmasq
#   - iw
#

set -e

# --- Configuration ---
INTERFACE="wlan0"       # Physical wireless interface
AP_INTERFACE="uap0"     # Virtual AP interface
AP_IP="192.168.50.1"
AP_SUBNET="192.168.50.0/24"
AP_SSID="BirdMasterSetup"
AP_CHANNEL=6
COUNTRY_CODE="US"
DHCP_RANGE="192.168.50.10,192.168.50.50,12h"

HOSTAPD_CONF="/tmp/hostapd.conf"
DNSMASQ_CONF="/tmp/dnsmasq.conf"

# --- Functions ---

function start_ap() {
    echo "Starting provisioning AP..."

    # 1. Create virtual AP interface
    if ! iw dev "$AP_INTERFACE" info >/dev/null 2>&1; then
        echo "Creating virtual AP interface ($AP_INTERFACE)..."
        iw dev "$INTERFACE" interface add "$AP_INTERFACE" type __ap
    else
        echo "Virtual AP interface ($AP_INTERFACE) already exists."
    fi

    # 2. Configure and bring up the interface
    ip addr add "$AP_IP/24" dev "$AP_INTERFACE" || echo "IP address already assigned."
    ip link set "$AP_INTERFACE" up

    # 3. Create hostapd config
    cat > "$HOSTAPD_CONF" <<EOF
interface=$AP_INTERFACE
driver=nl80211
ssid=$AP_SSID
hw_mode=g
channel=$AP_CHANNEL
country_code=$COUNTRY_CODE
auth_algs=1
wpa=2
wpa_passphrase=squawkers
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
ieee80211n=1
wmm_enabled=1
EOF

    # 4. Create dnsmasq config
    cat > "$DNSMASQ_CONF" <<EOF
interface=$AP_INTERFACE
bind-interfaces
dhcp-range=$DHCP_RANGE
EOF

    # 5. Start services
    echo "Starting hostapd..."
    hostapd -B "$HOSTAPD_CONF"
    
    echo "Starting dnsmasq..."
    dnsmasq -C "$DNSMASQ_CONF"

    echo "Provisioning AP started on $AP_IP"
    echo "SSID: $AP_SSID"
}

function stop_ap() {
    echo "Stopping provisioning AP..."

    # 1. Stop services
    pkill -f "hostapd -B $HOSTAPD_CONF" || echo "hostapd not running."
    pkill -f "dnsmasq -C $DNSMASQ_CONF" || echo "dnsmasq not running."

    # 2. Remove virtual interface
    if iw dev "$AP_INTERFACE" info >/dev/null 2>&1; then
        echo "Removing virtual AP interface ($AP_INTERFACE)..."
        iw dev "$AP_INTERFACE" del
    else
        echo "Virtual AP interface ($AP_INTERFACE) not found."
    fi

    echo "Provisioning AP stopped."
}

# --- Main Logic ---

if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root. Use sudo." >&2
  exit 1
fi

case "$1" in
    start)
        stop_ap # Ensure clean state
        start_ap
        ;;
    stop)
        stop_ap
        ;;
    *)
        echo "Usage: $0 {start|stop}"
        exit 1
        ;;
esac

exit 0
