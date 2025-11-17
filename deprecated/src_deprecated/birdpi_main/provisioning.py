"""WiFi provisioning support for headless master + nodes.

This module abstracts storing and retrieving WiFi credentials and exposes
helper functions to (eventually) apply them at the OS level. Actual OS
integration (writing wpa_supplicant.conf, restarting services) is left as
TODOs because piCorePlayer vs Raspberry Pi OS differ.

Data file: credentials stored as JSON in `wifi_credentials.json` in the
project root (can move to /etc/birdpi later).

Structure:
    {
        "ssid": "MyNetwork",
        "password": "SuperSecret",
        "last_updated": 1731250000.123
    }

Master Flow:
    1. Boot in AP mode (e.g., SSID BirdMasterSetup) if no credentials file.
    2. Host web form -> POST /api/wifi/config -> save credentials.
    3. Apply credentials (write system config) -> reboot networking -> join target.
    4. Once online, serve credentials to nodes that lack them via /api/wifi/credentials.

Node Flow:
    1. On boot, attempt to load credentials file. If present -> connect.
    2. If absent and can't reach target AP, scan for BirdMasterSetup, connect to AP.
    3. GET /api/wifi/credentials from master, save, connect to real network.
    4. Register with master for normal operation.

Security Notes:
    - Password currently stored and transmitted in plaintext over HTTP.
    - For production, add at least a provisioning token, optional short-lived
      symmetric encryption, or WPA3 SAE + local TLS termination.
    - Avoid exposing /api/wifi/credentials once nodes are provisioned (feature flag).
"""

from __future__ import annotations
import json
import time
import os
import subprocess
from typing import Optional, Dict

# State file tracking provisioning mode
PROVISIONING_STATE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "provisioning_state.json"))

def _load_state() -> Dict[str, bool]:
    if not os.path.exists(PROVISIONING_STATE_PATH):
        return {"provisioning_active": True}  # default to active until first credentials applied
    try:
        with open(PROVISIONING_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "provisioning_active" not in data:
            data["provisioning_active"] = True
        return data
    except Exception:
        return {"provisioning_active": True}

def _save_state(active: bool) -> None:
    try:
        with open(PROVISIONING_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump({"provisioning_active": active, "updated": time.time()}, f)
    except Exception as e:
        print(f"[provisioning] Failed saving state: {e}")

def is_provisioning_active() -> bool:
    return _load_state().get("provisioning_active", True)

def deactivate_provisioning():
    print("[provisioning] Deactivating provisioning mode.")
    _save_state(False)

def stop_ap_services():
    """Attempt to stop hostapd/dnsmasq and remove AP interface if present.
    Non-fatal on failure (may lack permissions)."""
    commands = [
        ["systemctl", "stop", "hostapd"],
        ["systemctl", "stop", "dnsmasq"],
        ["ip", "link", "set", "uap0", "down"],
        ["iw", "dev", "uap0", "del"],
    ]
    for cmd in commands:
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=4)
            if result.returncode == 0:
                print(f"[provisioning] Ran: {' '.join(cmd)}")
            else:
                stderr = result.stderr.decode(errors='ignore')
                print(f"[provisioning] Command failed ({' '.join(cmd)}): {stderr}")
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"[provisioning] Error executing {' '.join(cmd)}: {e}")

CREDENTIALS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "wifi_credentials.json"))


def load_credentials() -> Optional[Dict[str, str]]:
    if not os.path.exists(CREDENTIALS_PATH):
        return None
    try:
        with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "ssid" in data and "password" in data:
            return data
        return None
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None


def save_credentials(ssid: str, password: str) -> Dict[str, str]:
    payload = {
        "ssid": ssid,
        "password": password,
        "last_updated": time.time()
    }
    try:
        with open(CREDENTIALS_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception as e:
        print(f"Error saving credentials: {e}")
    return payload


def has_credentials() -> bool:
    return load_credentials() is not None


def get_wifi_status() -> Dict[str, str]:
    """Return a minimal status snapshot.
    NOTE: Placeholder. Extend with subprocess calls:
        - `iwgetid -r` for current SSID
        - `ip addr show wlan0` for IP
    For piCorePlayer, adapt to its busybox utilities.
    """
    ssid = None
    creds = load_credentials()
    if creds:
        ssid = creds.get("ssid")
    return {
        "configured_ssid": ssid or "<none>",
        "connected_ssid": ssid or "<unknown>",  # Replace with actual query
        "ip": "<unknown>"  # Replace with actual query
    }


def apply_credentials(creds: Dict[str, str], interface: str = "wlan0", country: str = "US") -> bool:
    """Apply credentials at OS level.

    Strategy:
    1. Detect platform (Raspberry Pi OS vs piCorePlayer TinyCore vs other).
    2. Choose target wpa_supplicant.conf path.
    3. Write minimal config (preserve existing non-network directives if present).
    4. Invoke `wpa_cli -i <interface> reconfigure`; if unavailable, try systemctl restart.
    5. Return True if file written and reconfigure attempted.

    This requires appropriate permissions (likely root). If not running as root,
    we fall back to printing manual instructions.

    For piCorePlayer (TinyCore), persistence requires running its backup process.
    We detect by checking /etc/os-release for 'piCore' or 'TinyCore'. If detected,
    we write the file and warn about performing backup (e.g., `pcp bu`).
    """
    ssid = creds.get("ssid")
    password = creds.get("password")
    if not ssid or not password:
        print("[provisioning] Missing SSID or password; abort apply.")
        return False

    # Detect platform
    os_release = {}
    try:
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    os_release[k] = v.strip('"')
    except FileNotFoundError:
        pass

    distro_id = os_release.get("ID", "")
    distro_name = os_release.get("NAME", "")
    is_picore = any(x in (distro_id + distro_name).lower() for x in ["picore", "tinycore"])

    # Choose target path
    if is_picore:
        # piCorePlayer typically stores config in /usr/local/etc/ or a pCP-specific path.
        target_path = "/usr/local/etc/wpa_supplicant.conf"
    else:
        target_path = "/etc/wpa_supplicant/wpa_supplicant.conf"

    base_config_lines = [
        f"country={country}",
        "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev",
        "update_config=1",
        "",  # spacer
    ]
    network_block = [
        "network= {",  # space intentional to allow simple grep distinction later if needed
        f"    ssid=\"{ssid}\"",
        f"    psk=\"{password}\"",
        "    key_mgmt=WPA-PSK",
        "}",
        "",  # spacer
    ]

    # Attempt to read existing file to preserve lines that are not network blocks
    existing_lines: list[str] = []
    if os.path.exists(target_path):
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                existing_lines = f.read().splitlines()
        except Exception as e:
            print(f"[provisioning] Could not read existing config: {e}")

    def is_network_line(line: str) -> bool:
        return line.strip().startswith("network=")

    preserved = [ln for ln in existing_lines if not is_network_line(ln)]
    # Ensure base directives are present (avoid duplicates)
    # If an existing line starts with one of our base keys, skip adding duplicate.
    def has_prefix(prefix: str) -> bool:
        return any(l.startswith(prefix) for l in preserved)
    final_lines = []
    for bl in base_config_lines:
        key = bl.split("=")[0]
        if key and has_prefix(key):
            continue
        final_lines.append(bl)
    final_lines.extend(preserved)
    final_lines.extend(network_block)

    wrote = False
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write("\n".join(final_lines))
        wrote = True
        # Restrict permissions
        try:
            os.chmod(target_path, 0o600)
        except Exception:
            pass
        print(f"[provisioning] Wrote WiFi config to {target_path}")
    except PermissionError:
        print(f"[provisioning] Permission denied writing {target_path}. Run as root or apply manually:")
        print("---BEGIN MANUAL CONTENT---")
        print("\n".join(final_lines))
        print("---END MANUAL CONTENT---")
        return False
    except Exception as e:
        print(f"[provisioning] Failed writing WiFi config: {e}")
        return False

    if not wrote:
        return False

    # Attempt reconfigure
    reconfigured = False
    cmd_sequence = [
        ["wpa_cli", "-i", interface, "reconfigure"],
        ["systemctl", "restart", "wpa_supplicant.service"],
    ]
    for cmd in cmd_sequence:
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            if result.returncode == 0:
                print(f"[provisioning] Applied credentials via: {' '.join(cmd)}")
                reconfigured = True
                break
            else:
                print(f"[provisioning] Command failed ({' '.join(cmd)}): {result.stderr.decode(errors='ignore')}")
        except FileNotFoundError:
            # Tool not available; continue
            continue
        except Exception as e:
            print(f"[provisioning] Error running {' '.join(cmd)}: {e}")

    if is_picore:
        print("[provisioning] Detected piCorePlayer/TinyCore; remember to create a backup to persist changes (e.g., run pcp bu).")

    if not reconfigured:
        print("[provisioning] Could not auto-reconfigure; a reboot or manual service restart may be required.")
    return wrote


__all__ = [
    "load_credentials",
    "save_credentials",
    "has_credentials",
    "get_wifi_status",
    "apply_credentials",
    "is_provisioning_active",
    "deactivate_provisioning",
    "stop_ap_services",
]
