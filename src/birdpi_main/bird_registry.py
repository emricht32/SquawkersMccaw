import time
import threading
import requests

import time
import threading
import requests

RESERVED_NAMES = ["Jose", "Michael", "Pierre", "Fritz"]

class BirdRegistry:
    def __init__(self):
        self.birds = {}         # name: { ip, id, status, last_seen, songs }
        self.name_map = {}      # ip: name

    def assign_name(self, requested_name, ip):
        used_names = set(self.birds.keys())

        # If requested name is valid and not taken
        if requested_name and requested_name in RESERVED_NAMES and requested_name not in used_names:
            return requested_name

        # Auto-assign next unused name
        for name in RESERVED_NAMES:
            if name not in used_names:
                return name

        return None  # All names taken

    def register(self, bird_id, ip, name):
        assigned_name = self.assign_name(name, ip)
        if not assigned_name:
            return None  # Reject if no names left

        self.birds[assigned_name] = {
            "ip": ip,
            "id": bird_id,
            "status": "Ready",
            "last_seen": time.time(),
        }
        self.name_map[ip] = assigned_name
        return assigned_name

    def update_status(self):
        while True:
            for name, data in self.birds.items():
                try:
                    r = requests.get(f"http://{data['ip']}:5001/status", timeout=1)
                    if r.ok:
                        data["status"] = "Ready"
                        data["last_seen"] = time.time()
                    else:
                        data["status"] = "Offline"
                except Exception:
                    data["status"] = "Offline"
            time.sleep(5)

    def get_birds(self):
        return self.birds
    
    def get_bird_names(self):
        return self.birds.keys


registry = BirdRegistry()

# Start background thread to keep statuses updated
threading.Thread(target=registry.update_status, daemon=True).start()
