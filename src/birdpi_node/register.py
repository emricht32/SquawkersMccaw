import requests
import socket
import time

MAIN_PI_HOST = "http://birdpi.local:8080"
NAME_FILE = "/tmp/bird_name"
OFFSET_FILE = "/tmp/time_offset"
MAIN_IP_FILE = "/tmp/main_ip"

def try_register(host, bird_id, local_time, requested_name):
    payload = {
        "id": bird_id,
        "time": local_time
    }
    if requested_name:
        payload["requested_name"] = requested_name

    try:
        r = requests.post(f"{host}/register", json=payload, timeout=2)
        if r.ok:
            response = r.json()
            offset = response.get("time_offset")
            assigned_name = response.get("name", bird_id)

            if offset is not None:
                with open(OFFSET_FILE, "w") as f:
                    f.write(str(offset))
                print(f"Time offset saved: {offset:.6f} sec")

            with open(NAME_FILE, "w") as f:
                f.write(assigned_name)

            # Optionally save working main IP for future use
            with open(MAIN_IP_FILE, "w") as f:
                f.write(host)

            print(f"✅ Registered with {host} as {assigned_name}")
            return assigned_name
    except requests.RequestException:
        pass

    return None

def discover_and_register(requested_name=None, completion=None):
    bird_id = socket.gethostname()
    local_time = time.time()

    print(f"🔍 Attempting to register with {MAIN_PI_HOST}...")
    assigned_name = try_register(MAIN_PI_HOST, bird_id, local_time, requested_name)

    if assigned_name:
        if completion:
            completion(assigned_name)
        return

    print("❌ Failed to register with birdpi.local. Scanning local network...")

    # Get local subnet prefix
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]  # e.g., 192.168.1.34
        s.close()
    except Exception:
        local_ip = "192.168.1.100"

    subnet_prefix = ".".join(local_ip.split(".")[:3])  # e.g., 192.168.1

    for i in range(2, 255):
        ip = f"{subnet_prefix}.{i}"
        host = f"http://{ip}:8080"
        print(f"🔁 Trying {host}...")
        assigned_name = try_register(host, bird_id, local_time, requested_name)
        if assigned_name:
            break

    if not assigned_name:
        print("❌ Could not find main Pi on the network.")
    if completion:
        completion(assigned_name or None)

if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else None
    discover_and_register(name)
