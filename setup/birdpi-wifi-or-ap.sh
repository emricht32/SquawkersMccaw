#!/bin/bash

LOG_TAG="BirdPi WiFi Init"
TARGET_CONFIG="/etc/wpa_supplicant/wpa_supplicant.conf"
MOUNT_POINT="/mnt/birdpi_usb"
AP_MODE_FLAG="/tmp/birdpi_ap_mode"

function try_mount_usb_and_copy_wifi() {
    DEVICE=$(lsblk -o LABEL,NAME | grep BIRDPI | awk '{print $2}')
    if [ -z "$DEVICE" ]; then
        logger -t "$LOG_TAG" "No USB named BIRDPI found."
        return 1
    fi

    mkdir -p $MOUNT_POINT
    mount /dev/"$DEVICE"1 $MOUNT_POINT
    if [ $? -ne 0 ]; then
        logger -t "$LOG_TAG" "Failed to mount USB drive."
        return 1
    fi

    if [ -f "$MOUNT_POINT/wpa_supplicant.conf" ]; then
        cp "$MOUNT_POINT/wpa_supplicant.conf" "$TARGET_CONFIG"
        chmod 600 "$TARGET_CONFIG"
        logger -t "$LOG_TAG" "Copied wpa_supplicant.conf from USB. Reconfiguring Wi-Fi..."
        wpa_cli -i wlan0 reconfigure
    else
        logger -t "$LOG_TAG" "No config file found on USB."
    fi

    umount $MOUNT_POINT
    rmdir $MOUNT_POINT
    return 0
}

function wait_for_wifi() {
    logger -t "$LOG_TAG" "Waiting up to 15 seconds for Wi-Fi connection..."
    for i in {1..15}; do
        if hostname -I | grep -qE '([0-9]{1,3}\.){3}[0-9]{1,3}'; then
            logger -t "$LOG_TAG" "Wi-Fi connected!"
            return 0
        fi
        sleep 1
    done
    logger -t "$LOG_TAG" "No Wi-Fi connection after 15 seconds."
    return 1
}

function enable_ap_mode() {
    logger -t "$LOG_TAG" "Starting fallback AP mode..."
    touch "$AP_MODE_FLAG"
    systemctl start birdpi-ap.service
}

# === MAIN EXECUTION ===
try_mount_usb_and_copy_wifi
wait_for_wifi || enable_ap_mode
