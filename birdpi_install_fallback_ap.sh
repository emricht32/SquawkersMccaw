#!/bin/sh
# birdpi_install_fallback_ap.sh
# Creates BirdPi fallback AP assets on piCorePlayer (BusyBox/TinyCore-friendly)
# - Writes hostapd.conf, dnsmasq.conf, birdpi-fallback-ap.sh into /mnt/mmcblk0p2/tc/birdpi-ap
# - Ensures bootlocal.sh runs the fallback script (idempotent)
# - Does NOT overwrite bootlocal.sh; appends only if missing
# - Jonathan Emrich / BirdPi

set -eu

AP_DIR="/mnt/mmcblk0p2/tc/birdpi-ap"
LOG_DIR="/mnt/mmcblk0p2/tc/birdpi-logs"
BOOTLOCAL="/opt/bootlocal.sh"

HOSTAPD_CONF="$AP_DIR/hostapd.conf"
DNSMASQ_CONF="$AP_DIR/dnsmasq.conf"
FALLBACK_SH="$AP_DIR/birdpi-fallback-ap.sh"

# BirdPi requested lines to append (must match exactly)
BOOT_MARKER="# BirdPi fallback AP if Wi-Fi does not connect"
BOOT_LINE="$FALLBACK_SH 20 &"

SSID="BirdPi"
PASSPHRASE="squawkers"
WLAN="wlan0"
AP_IP="192.168.4.1"
NETMASK="255.255.255.0"

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: run as root (use: sudo sh $0)" >&2
    exit 1
  fi
}

safe_mkdir() {
  mkdir -p "$1"
}

write_hostapd_conf() {
  cat > "$HOSTAPD_CONF" <<EOF
interface=$WLAN
driver=nl80211
ssid=$SSID
hw_mode=g
channel=6
wmm_enabled=0
auth_algs=1
ignore_broadcast_ssid=0

wpa=2
wpa_passphrase=$PASSPHRASE
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF
  chmod 644 "$HOSTAPD_CONF"
}

write_dnsmasq_conf() {
  cat > "$DNSMASQ_CONF" <<EOF
interface=$WLAN
bind-interfaces

dhcp-range=192.168.4.10,192.168.4.50,255.255.255.0,24h
dhcp-leasefile=/tmp/dnsmasq.leases
dhcp-authoritative

domain-needed
bogus-priv
EOF
  chmod 644 "$DNSMASQ_CONF"
}

write_fallback_script() {
  cat > "$FALLBACK_SH" <<'EOF'
#!/bin/sh
# BirdPi piCorePlayer fallback AP (BusyBox-safe)
# If Wi-Fi doesn't connect after TIMEOUT seconds, start an AP so user can reach pCP UI.
# UI should be reachable at http://192.168.4.1/ (BusyBox httpd runs on :80)

SSID="BirdPi"
AP_IP="192.168.4.1"
NETMASK="255.255.255.0"
WLAN="wlan0"

HOSTAPD_CONF="/mnt/mmcblk0p2/tc/birdpi-ap/hostapd.conf"
DNSMASQ_CONF="/mnt/mmcblk0p2/tc/birdpi-ap/dnsmasq.conf"

PID_HOSTAPD="/var/run/birdpi_hostapd.pid"
PID_DNSMASQ="/var/run/birdpi_dnsmasq.pid"

LOG="/mnt/mmcblk0p2/tc/birdpi-logs/fallback_ap.log"
mkdir -p "$(dirname "$LOG")" 2>/dev/null

log() { echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] $*" >> "$LOG"; }

iface_exists() {
  ifconfig "$WLAN" >/dev/null 2>&1
}

wait_for_iface() {
  # wait up to 15s for wlan0 to exist
  i=0
  while [ $i -lt 15 ]; do
    iface_exists && return 0
    sleep 1
    i=$((i+1))
  done
  return 1
}

wifi_connected() {
  # Prefer wpa_cli if present
  if command -v wpa_cli >/dev/null 2>&1; then
    wpa_cli -i "$WLAN" status 2>/dev/null | grep -q "wpa_state=COMPLETED" && return 0
  fi
  # Fallback: iwgetid if present
  if command -v iwgetid >/dev/null 2>&1; then
    iwgetid -r 2>/dev/null | grep -q . && return 0
  fi
  return 1
}

stop_ap() {
  log "Stopping AP components (if running)"
  if [ -f "$PID_DNSMASQ" ]; then
    kill "$(cat "$PID_DNSMASQ")" 2>/dev/null
    rm -f "$PID_DNSMASQ"
  fi
  if [ -f "$PID_HOSTAPD" ]; then
    kill "$(cat "$PID_HOSTAPD")" 2>/dev/null
    rm -f "$PID_HOSTAPD"
  fi
  killall dnsmasq 2>/dev/null
  killall hostapd 2>/dev/null
}

stop_wifi_client() {
  # Stop client mode so hostapd can own wlan0
  log "Stopping Wi-Fi client (wpa_supplicant/udhcpc)"
  killall wpa_supplicant 2>/dev/null
  killall udhcpc 2>/dev/null
}

configure_wlan_ap_ip() {
  # Bring interface up and assign static IP
  ifconfig "$WLAN" up 2>/dev/null
  ifconfig "$WLAN" "$AP_IP" netmask "$NETMASK" up 2>/dev/null

  # Ensure route to the AP subnet (some builds need it)
  if command -v route >/dev/null 2>&1; then
    route add -net 192.168.4.0 netmask "$NETMASK" dev "$WLAN" 2>/dev/null
  fi
}

start_dnsmasq() {
  dnsmasq -C "$DNSMASQ_CONF" -x "$PID_DNSMASQ"
  return $?
}

start_hostapd() {
  hostapd -B -P "$PID_HOSTAPD" "$HOSTAPD_CONF"
  return $?
}

start_ap() {
  log "Starting fallback AP SSID=$SSID"

  if ! wait_for_iface; then
    log "ERROR: interface $WLAN not found after waiting; cannot start AP"
    return 1
  fi

  stop_wifi_client
  stop_ap

  configure_wlan_ap_ip

  # Start DHCP first so clients get an IP quickly
  start_dnsmasq
  if [ $? -ne 0 ]; then
    log "ERROR: dnsmasq failed to start. Check $DNSMASQ_CONF"
    return 1
  fi

  # Start AP beacon
  start_hostapd
  if [ $? -ne 0 ]; then
    log "ERROR: hostapd failed to start. Check $HOSTAPD_CONF"
    return 1
  fi

  log "AP active. Connect to Wi-Fi '$SSID' and open: http://$AP_IP/"
  return 0
}

main() {
  TIMEOUT="${1:-35}"

  # If AP already running, do nothing
  if [ -f "$PID_HOSTAPD" ] && kill -0 "$(cat "$PID_HOSTAPD")" 2>/dev/null; then
    log "AP already running; exiting"
    exit 0
  fi

  log "Checking Wi-Fi connectivity for up to ${TIMEOUT}s..."
  i=0
  while [ $i -lt "$TIMEOUT" ]; do
    if wifi_connected; then
      log "Wi-Fi connected; not starting AP"
      exit 0
    fi
    sleep 1
    i=$((i+1))
  done

  log "Wi-Fi not connected after ${TIMEOUT}s; enabling AP"
  start_ap
}

main "$@"
EOF
  chmod +x "$FALLBACK_SH"
}

ensure_bootlocal_has_lines() {
  if [ ! -f "$BOOTLOCAL" ]; then
    echo "ERROR: $BOOTLOCAL not found" >&2
    exit 1
  fi

  # Ensure executable
  chmod +x "$BOOTLOCAL" 2>/dev/null || true

  # Idempotent append:
  # If the marker is missing OR the command line is missing, append both at end.
  HAS_MARKER=0
  HAS_LINE=0

  # BusyBox grep compatible checks
  grep -F "$BOOT_MARKER" "$BOOTLOCAL" >/dev/null 2>&1 && HAS_MARKER=1 || true
  grep -F "$BOOT_LINE" "$BOOTLOCAL" >/dev/null 2>&1 && HAS_LINE=1 || true

  if [ "$HAS_MARKER" -eq 1 ] && [ "$HAS_LINE" -eq 1 ]; then
    echo "bootlocal.sh already contains BirdPi fallback AP lines."
    return 0
  fi

  echo "Appending BirdPi fallback AP lines to $BOOTLOCAL"
  {
    echo ""
    echo "$BOOT_MARKER"
    echo "$BOOT_LINE"
  } >> "$BOOTLOCAL"
}

print_summary() {
  echo ""
  echo "Installed BirdPi fallback AP assets:"
  echo "  - $HOSTAPD_CONF"
  echo "  - $DNSMASQ_CONF"
  echo "  - $FALLBACK_SH"
  echo "Updated:"
  echo "  - $BOOTLOCAL (appended lines if missing)"
  echo ""
  echo "Persisting changes (pcp bu)..."
  pcp bu
  echo ""
  echo "Reboot recommended."
}

main() {
  require_root
  safe_mkdir "$AP_DIR"
  safe_mkdir "$LOG_DIR"

  write_hostapd_conf
  write_dnsmasq_conf
  write_fallback_script
  ensure_bootlocal_has_lines

  print_summary
}

main "$@"
