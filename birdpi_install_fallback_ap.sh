#!/bin/sh
# birdpi_install_fallback_ap.sh
# One-shot fallback AP installer for fresh piCorePlayer systems.
# Safe to copy via USB and run directly.

set -eu

AP_DIR="/mnt/mmcblk0p2/tc/birdpi-ap"
LOG_DIR="/mnt/mmcblk0p2/tc/birdpi-logs"
BOOTLOCAL="/opt/bootlocal.sh"
ONBOOT_LIST="/mnt/mmcblk0p2/tce/onboot.lst"

HOSTAPD_CONF="$AP_DIR/hostapd.conf"
DNSMASQ_CONF="$AP_DIR/dnsmasq.conf"
FALLBACK_SH="$AP_DIR/birdpi-fallback-ap.sh"

BOOT_MARKER="# BirdPi fallback AP if Wi-Fi does not connect"
BOOT_LINE="$FALLBACK_SH 20 &"

SSID="BirdPi"
PASSPHRASE="squawkers"
WLAN="wlan0"
AP_IP="192.168.4.1"
NETMASK="255.255.255.0"

say() {
  echo "[birdpi-ap-installer] $*"
}

warn() {
  echo "[birdpi-ap-installer][WARN] $*" >&2
}

die() {
  echo "[birdpi-ap-installer][ERROR] $*" >&2
  exit 1
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    die "Run as root (example: sudo sh $0)"
  fi
}

safe_mkdir() {
  mkdir -p "$1"
}

ensure_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"
}

append_line_if_missing() {
  file="$1"
  line="$2"
  grep -F "$line" "$file" >/dev/null 2>&1 || echo "$line" >> "$file"
}

ensure_pkg_onboot() {
  pkg="$1"
  [ -f "$ONBOOT_LIST" ] || die "Missing onboot list: $ONBOOT_LIST"
  grep -qxF "$pkg" "$ONBOOT_LIST" || echo "$pkg" >> "$ONBOOT_LIST"
}

install_package_if_needed() {
  pkg="$1"
  bin="$2"

  if command -v "$bin" >/dev/null 2>&1; then
    say "$pkg already available ($bin found)"
    return 0
  fi

  if ! command -v tce-load >/dev/null 2>&1; then
    die "tce-load is not available; cannot install $pkg"
  fi

  say "Installing $pkg (requires internet access)"

  # piCorePlayer/TinyCore expects extension installs as user 'tc'.
  # Use warn (not die) so configs are still written when there is no internet.
  if [ "$(id -u)" -eq 0 ] && id tc >/dev/null 2>&1; then
    su tc -c "tce-load -wi '$pkg'" || { warn "Failed installing $pkg (no internet?). Configs will still be written."; return 1; }
  else
    tce-load -wi "$pkg" || { warn "Failed installing $pkg (no internet?). Configs will still be written."; return 1; }
  fi
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
  i=0
  while [ $i -lt 20 ]; do
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
    kill "$(cat "$PID_DNSMASQ")" 2>/dev/null || true
    rm -f "$PID_DNSMASQ"
  fi
  if [ -f "$PID_HOSTAPD" ]; then
    kill "$(cat "$PID_HOSTAPD")" 2>/dev/null || true
    rm -f "$PID_HOSTAPD"
  fi
  killall dnsmasq 2>/dev/null || true
  killall hostapd 2>/dev/null || true
}

stop_wifi_client() {
  log "Stopping Wi-Fi client (wpa_supplicant/udhcpc)"
  killall wpa_supplicant 2>/dev/null || true
  killall udhcpc 2>/dev/null || true
}

configure_wlan_ap_ip() {
  ifconfig "$WLAN" up 2>/dev/null || true
  ifconfig "$WLAN" "$AP_IP" netmask "$NETMASK" up 2>/dev/null || true
  if command -v route >/dev/null 2>&1; then
    route add -net 192.168.4.0 netmask "$NETMASK" dev "$WLAN" 2>/dev/null || true
  fi
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

  dnsmasq -C "$DNSMASQ_CONF" -x "$PID_DNSMASQ" || {
    log "ERROR: dnsmasq failed to start. Check $DNSMASQ_CONF"
    return 1
  }

  hostapd -B -P "$PID_HOSTAPD" "$HOSTAPD_CONF" || {
    log "ERROR: hostapd failed to start. Check $HOSTAPD_CONF"
    return 1
  }

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
  [ -f "$BOOTLOCAL" ] || die "Missing bootlocal script: $BOOTLOCAL"
  chmod +x "$BOOTLOCAL" 2>/dev/null || true

  append_line_if_missing "$BOOTLOCAL" ""
  append_line_if_missing "$BOOTLOCAL" "$BOOT_MARKER"
  append_line_if_missing "$BOOTLOCAL" "$BOOT_LINE"
}

ensure_filetool_persists_bootlocal() {
  # Ensure /opt/bootlocal.sh is in filetool backup list so pcp bu saves it.
  FILETOOL_LIST="/opt/.filetool.lst"
  if [ -f "$FILETOOL_LIST" ]; then
    grep -qxF "opt/bootlocal.sh" "$FILETOOL_LIST" || echo "opt/bootlocal.sh" >> "$FILETOOL_LIST"
  else
    warn "$FILETOOL_LIST not found; bootlocal.sh backup list entry skipped"
  fi
}

persist_backup_if_possible() {
  if command -v pcp >/dev/null 2>&1; then
    say "Persisting changes with: pcp bu"
    pcp bu || warn "pcp bu failed; changes may not persist after reboot"
  else
    warn "pcp command not found; changes may not persist after reboot"
  fi
}

smoke_test_now() {
  say "Running fallback AP script immediately (1s timeout)"
  sh "$FALLBACK_SH" 1 || warn "Immediate AP start attempt failed; inspect fallback log"
}

main() {
  require_root

  ensure_cmd grep
  ensure_cmd ifconfig

  safe_mkdir "$AP_DIR"
  safe_mkdir "$LOG_DIR"

  install_package_if_needed hostapd hostapd
  install_package_if_needed dnsmasq dnsmasq

  if ! command -v iwgetid >/dev/null 2>&1; then
    if command -v tce-load >/dev/null 2>&1; then
      say "Installing optional wireless_tools for iwgetid"
      if [ "$(id -u)" -eq 0 ] && id tc >/dev/null 2>&1; then
        su tc -c "tce-load -wi wireless_tools" || warn "wireless_tools install failed; continuing"
      else
        tce-load -wi wireless_tools || warn "wireless_tools install failed; continuing"
      fi
    fi
  fi

  [ -f "$ONBOOT_LIST" ] || die "Expected onboot list not found: $ONBOOT_LIST"
  ensure_pkg_onboot "hostapd.tcz"
  ensure_pkg_onboot "dnsmasq.tcz"
  if command -v iwgetid >/dev/null 2>&1; then
    ensure_pkg_onboot "wireless_tools.tcz"
  fi

  write_hostapd_conf
  write_dnsmasq_conf
  write_fallback_script
  ensure_bootlocal_has_lines
  ensure_filetool_persists_bootlocal

  smoke_test_now
  persist_backup_if_possible

  say ""
  say "Install complete."
  say "  Fallback AP SSID     : $SSID"
  say "  Fallback AP password : $PASSPHRASE"
  say "  Fallback AP URL      : http://$AP_IP/"
  say "  Log file             : $LOG_DIR/fallback_ap.log"
  say ""
  if ! command -v hostapd >/dev/null 2>&1 || ! command -v dnsmasq >/dev/null 2>&1; then
    warn "hostapd or dnsmasq not installed (no internet during install)."
    warn "To install manually once internet is available:"
    warn "  sudo -u tc tce-load -wi hostapd dnsmasq"
    warn "  sudo reboot"
    warn "Or copy hostapd.tcz and dnsmasq.tcz to the USB and run this script again."
  else
    say "Reboot to activate fallback AP."
  fi
}

main "$@"
