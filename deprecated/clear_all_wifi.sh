#!/bin/bash
set -e

# --- WPA Supplicant Cleanup ---
WPA_CONF="/etc/wpa_supplicant/wpa_supplicant.conf"
if [ -f "$WPA_CONF" ]; then
    sudo cp "$WPA_CONF" "$WPA_CONF.bak.$(date +%s)"
    sudo tee "$WPA_CONF" > /dev/null <<EOF
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US
EOF
    sudo chmod 600 "$WPA_CONF"
    echo "✅ Cleared $WPA_CONF"
else
    echo "ℹ️ $WPA_CONF not found. Skipping."
fi

# --- NetworkManager Cleanup ---
if command -v nmcli >/dev/null 2>&1; then
    WIFI_CONS=$(nmcli -t -f NAME,TYPE connection show | grep ':wifi$' | cut -d: -f1)
    if [ -n "$WIFI_CONS" ]; then
        # shellcheck disable=SC2086
        for con in $WIFI_CONS; do
            echo "Removing NetworkManager connection: $con"
            sudo nmcli connection delete "$con"
        done
        echo "✅ Removed all NetworkManager WiFi connections"
    else
        echo "ℹ️ No NetworkManager WiFi connections found"
    fi
else
    echo "ℹ️ nmcli not found; NetworkManager not in use"
fi

sudo rm -f /etc/NetworkManager/system-connections/*
sudo rm -f /etc/wpa_supplicant/wpa_supplicant.conf
sudo rm -rf /var/lib/connman/*
sudo systemctl restart NetworkManager
sudo reboot

echo "🚨 All WiFi credentials cleared. Please reboot if testing onboarding. 🚨"
