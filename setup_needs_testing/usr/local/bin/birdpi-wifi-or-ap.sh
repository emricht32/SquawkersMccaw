#!/bin/bash

LOG_TAG="BirdPi WiFi Init"
AP_MODE_FLAG="/tmp/birdpi_ap_mode"

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

wait_for_wifi || enable_ap_mode
