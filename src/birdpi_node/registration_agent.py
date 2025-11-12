"""
Node Registration Agent

This standalone script runs on each bird node. Its purpose is to:
1. Discover the master Pi's IP address.
2. Register itself with the master to appear in the bird registry.
3. Periodically re-register to signal it's still online.

Discovery Methods:
- Reads a master_ip.txt file (if present).
- (Future) mDNS/Zeroconf discovery for "_birdpi-master._http._tcp.local".
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

# Default master IP if not provided via args or discovery
DEFAULT_MASTER_IP = "192.168.1.100"
REGISTRATION_INTERVAL_S = 60  # seconds

def get_master_ip(master_ip_arg: str) -> str:
    """Determine master IP from arg, file, or default."""
    if master_ip_arg:
        return master_ip_arg
    
    # Check for a local file override
    if os.path.exists("master_ip.txt"):
        with open("master_ip.txt", "r") as f:
            ip = f.read().strip()
            if ip:
                print(f"Found master IP in master_ip.txt: {ip}")
                return ip

    # TODO: Add mDNS discovery here as a more robust method

    print(f"Falling back to default master IP: {DEFAULT_MASTER_IP}")
    return DEFAULT_MASTER_IP

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

def register(master_ip: str, bird_name: str = None):
    """Send a registration POST to the master, including MAC."""
    hostname = socket.gethostname()
    mac = get_mac_address()
    payload = {
        "id": hostname,
        "time": time.time(),
        "name": bird_name or hostname,  # Use explicit name if provided
        "mac": mac,
    }
    
    url = f"http://{master_ip}:8080/register"
    try:
        print(f"Attempting to register with {url}...")
        print(f"Payload: {payload}")
        r = requests.post(url, json=payload, timeout=5)
        r.raise_for_status()  # Raise an exception for bad status codes
        
        response_data = r.json()
        print(f"Successfully registered: {response_data}")
        if "player_map" in response_data:
            print("Current dynamic player map received from master:")
            for k,v in response_data["player_map"].items():
                print(f"  {k} -> {v}")
        
        # If master assigns a name, we could persist it locally
        assigned_name = response_data.get("name")
        if assigned_name and assigned_name != (bird_name or hostname):
            print(f"Master assigned name: {assigned_name}")

    except requests.exceptions.RequestException as e:
        print(f"Error registering with master: {e}")

def main():
    parser = argparse.ArgumentParser(description="BirdPi Node Registration Agent")
    parser.add_argument("--master-ip", help="Master Pi's IP address.")
    parser.add_argument("--name", help="Optional explicit name for this bird (e.g., 'Fritz').")
    parser.add_argument("--once", action="store_true", help="Run registration once and exit.")
    args = parser.parse_args()

    master_ip = get_master_ip(args.master_ip)

    if args.once:
        register(master_ip, args.name)
    else:
        while True:
            register(master_ip, args.name)
            print(f"Waiting {REGISTRATION_INTERVAL_S} seconds before next registration...")
            time.sleep(REGISTRATION_INTERVAL_S)

if __name__ == "__main__":
    main()
