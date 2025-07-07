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

        # ✅ If the requested name is valid and not taken
        if requested_name and requested_name in RESERVED_NAMES and requested_name not in used_names:
            return requested_name

        # ✅ If a bird with that name is already registered, but the IP matches (e.g. reconnect/reboot)
        for name in RESERVED_NAMES:
            bird = self.birds.get(name)
            if bird and bird["ip"] == ip:
                # Reuse the existing name for this IP
                return name

        # 🔄 Auto-assign next unused name
        for name in RESERVED_NAMES:
            if name not in used_names:
                return name

        return None  # All names taken


    def register(self, bird_id, ip, name):
        assigned_name = self.assign_name(name, ip)
        if not assigned_name:
            return None  # Reject if no names left
    
        time.sleep(2)

        self.birds[assigned_name] = {
            "ip": ip,
            "id": bird_id,
            "status": "Pending",
            "last_seen": time.time(),
        }
        self.name_map[ip] = assigned_name
        return assigned_name

    def update_status(self):
        while True:
            for name, data in self.birds.items():
                try:
                    r = requests.get(f"http://{data['ip']}:5001/status", timeout=1)
                    self._handleResponse(r,name,data)
                except Exception as e:
                    time.sleep(0.5)
                    try:
                        r = requests.get(f"http://{data['ip']}:5001/status", timeout=1)
                        self._handleResponse(r,name,data)
                    except Exception:
                        self.birds[name]["status"] = "Offline"
                    print(f"{name} Exception: {e}.  Disconnecting.")

                    data["status"] = "Offline"
            time.sleep(5)

    def get_birds(self):
        return self.birds
    
    def get_bird_names(self):
        return self.birds.keys
     
    def _handleResponse(self, r, name, data):
        if r.ok:
            if data["status"] == "Offline":
                print(f"{name} back online.")
            data["status"] = "Ready"
            data["last_seen"] = time.time()
        else:
            if data["status"] == "Ready":
                print(f"{name} no longer online.  Disconnecting.")
            data["status"] = "Offline"

registry = BirdRegistry()

# Start background thread to keep statuses updated
threading.Thread(target=registry.update_status, daemon=True).start()
