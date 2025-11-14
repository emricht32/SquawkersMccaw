"""
Node Registration Agent

This standalone script runs on each bird node. Its purpose is to:
1. Discover the main Pi's IP address.
2. Register itself with the main to appear in the bird registry.
3. Periodically re-register to signal it's still online.

Discovery Methods:
- Reads a main_ip.txt file (if present).
- (Future) mDNS/Zeroconf discovery for "_birdpi-main._http._tcp.local".
- (Future) Falls back to scanning the local network.

Run this script on boot. For systemd, see the birdpi-node.service template.
"""

import requests
import time
import socket
import argparse
import os
import uuid
from pathlib import Path

# Default main IP if not provided via args or discovery
DEFAULT_MAIN_IP = "192.168.1.100"
REGISTRATION_INTERVAL_S = 60  # seconds

def get_main_ip(main_ip_arg: str) -> str:
    """Determine main IP from arg, file, or default. Supports legacy master_ip.txt."""
    if main_ip_arg:
        return main_ip_arg

    # Check for a local file override (new name)
    if os.path.exists("main_ip.txt"):
        with open("main_ip.txt", "r") as f:
            ip = f.read().strip()
            if ip:
                print(f"Found main IP in main_ip.txt: {ip}")
                return ip
    # Legacy support
    if os.path.exists("master_ip.txt"):
        with open("master_ip.txt", "r") as f:
            ip = f.read().strip()
            if ip:
                print(f"(Legacy) Found master IP in master_ip.txt: {ip}")
                return ip

    # TODO: Add mDNS discovery here as a more robust method

    print(f"Falling back to default main IP: {DEFAULT_MAIN_IP}")
    return DEFAULT_MAIN_IP

def get_mac_address() -> str:
    """Return a MAC address suitable for LMS player identification.
    Preference order: wlan0, eth0, fallback to uuid.getnode()."""
    candidates = ["wlan0", "eth0"]
    for iface in candidates:
        addr_path = Path(f"/sys/class/net/{iface}/address")
        if addr_path.exists():
            mac = addr_path.read_text().strip().lower()
            if mac and mac != "00:00:00:00:00:00":
                return mac
    # Fallback
    mac_int = uuid.getnode()
    mac = ":".join(f"{(mac_int >> ele) & 0xff:02x}" for ele in range(40, -1, -8))
    return mac.lower()

def register(main_ip: str, bird_name: str = None):
    """Send a registration POST to the main controller, including MAC."""
    hostname = socket.gethostname()
    mac = get_mac_address()
    payload = {
        "id": hostname,
        "time": time.time(),
        "name": bird_name or hostname,  # Use explicit name if provided
        "mac": mac,
    }
    
    url = f"http://{main_ip}:8080/register"
    try:
        print(f"Attempting to register with {url}...")
        print(f"Payload: {payload}")
        r = requests.post(url, json=payload, timeout=5)
        r.raise_for_status()  # Raise an exception for bad status codes
        
        response_data = r.json()
        print(f"Successfully registered: {response_data}")
        if "player_map" in response_data:
            print("Current dynamic player map received from main:")
            for k,v in response_data["player_map"].items():
                print(f"  {k} -> {v}")
        
    # If main assigns a name, we could persist it locally
        assigned_name = response_data.get("name")
        if assigned_name and assigned_name != (bird_name or hostname):
            print(f"Main assigned name: {assigned_name}")

    except requests.exceptions.RequestException as e:
        print(f"Error registering with main: {e}")

def main():
    parser = argparse.ArgumentParser(description="BirdPi Node Registration Agent")
    parser.add_argument("--main-ip", help="Main Pi's IP address.")
    parser.add_argument("--name", help="Optional explicit name for this bird (e.g., 'Fritz').")
    parser.add_argument("--once", action="store_true", help="Run registration once and exit.")
    args = parser.parse_args()

    main_ip = get_main_ip(args.main_ip)

    if args.once:
        register(main_ip, args.name)
    else:
        while True:
            register(main_ip, args.name)
            print(f"Waiting {REGISTRATION_INTERVAL_S} seconds before next registration...")
            time.sleep(REGISTRATION_INTERVAL_S)

if __name__ == "__main__":
    main()
