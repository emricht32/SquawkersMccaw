import requests
import socket
import time

MAIN_PI_HOST = "http://birdpi.local:8080"
NAME_FILE = "/tmp/bird_name"
OFFSET_FILE = "/tmp/time_offset"

def register_bird(requested_name=None,completion=None):
    bird_id = socket.gethostname()
    local_time = time.time()

    payload = {
        "id": bird_id,
        "time": local_time,
    }

    if requested_name:
        payload["requested_name"] = requested_name

    try:
        r = requests.post(f"{MAIN_PI_HOST}/register", json=payload, timeout=5)
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
            print("Registered as", assigned_name)

        else:
            print("Register request failed:", r.status_code)
    except requests.RequestException:
        print("Failed to register")
    finally:
        if completion is not None:
            completion(assigned_name)

if __name__ == "__main__":
    # You can optionally pass the desired name as a command-line arg
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else None
    register_bird(name)
