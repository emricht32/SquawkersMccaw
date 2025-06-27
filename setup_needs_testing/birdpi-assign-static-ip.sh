#!/bin/bash
set -e

# /usr/local/bin/birdpi-assign-static-ip.sh

echo "[BirdPi] Attempting static IP assignment..."

WLAN_DEV="wlan0"
SUBNET=$(ip route | grep -m 1 default | awk '{print $3}')

if [[ -z "$SUBNET" ]]; then
  echo "[BirdPi] No default route found — skipping static IP."
  exit 1
fi

PREFIX=$(echo "$SUBNET" | cut -d'.' -f1,2)

case "$PREFIX" in
  10.0)
    STATIC_IP="10.0.4.2"
    GATEWAY="10.0.0.1"
    ;;
  172.16)
    STATIC_IP="172.16.4.2"
    GATEWAY="172.16.0.1"
    ;;
  192.168)
    STATIC_IP="192.168.4.2"
    GATEWAY="192.168.0.1"
    ;;
  *)
    echo "[BirdPi] Unknown network prefix: $PREFIX — skipping static IP."
    exit 0
    ;;
esac

echo "[BirdPi] Assigning static IP: $STATIC_IP with gateway $GATEWAY"

sudo ip addr flush dev "$WLAN_DEV"
sudo ip addr add "$STATIC_IP/24" dev "$WLAN_DEV"
sudo ip route add default via "$GATEWAY" dev "$WLAN_DEV"

echo "[BirdPi] Static IP configured: $STATIC_IP"
