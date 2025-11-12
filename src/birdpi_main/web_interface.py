from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
from bird_registry import registry
import time
from provisioning import (
    load_credentials,
    save_credentials,
    has_credentials,
    get_wifi_status,
    apply_credentials,
    is_provisioning_active,
    deactivate_provisioning,
    stop_ap_services,
)
import time

def create_web_interface(songs, on_song_selected, cancel_current_song, get_queue):
    app = Flask(__name__, static_folder="static", static_url_path="")
    CORS(app)

    @app.route("/api/birds", methods=["GET"])
    def get_birds():
        # Example: registry.get_birds() returns {name: {"id":..., "ip":..., "status":..., "last_seen":...}}
        return jsonify(registry.get_birds())


    @app.route("/api/songs", methods=["GET"])
    def get_songs():
        return jsonify([
            {"index": i, "name": song.get("display_name", song.get("name", "Unknown"))}
            for i, song in enumerate(songs)
        ])

    @app.route("/api/wifi/status", methods=["GET"])
    def wifi_status():
        return jsonify(get_wifi_status())

    @app.route("/api/wifi/config", methods=["POST"])
    def wifi_config():
        data = request.get_json(force=True)
        ssid = data.get("ssid")
        password = data.get("password")
        if not ssid or not password:
            return jsonify({"status":"error","message":"Missing ssid or password"}), 400
        creds = save_credentials(ssid, password)
        applied = apply_credentials(creds)
        # After successful save, deactivate provisioning & attempt AP shutdown
        if applied:
            deactivate_provisioning()
            stop_ap_services()
        return jsonify({"status":"ok","applied":applied, "provisioning_active": is_provisioning_active()})

    @app.route("/api/wifi/credentials", methods=["GET"])
    def wifi_credentials_for_node():
        # Provide credentials to nodes lacking them only if still provisioning
        if not is_provisioning_active():
            return jsonify({"status":"disabled"}), 403
        creds = load_credentials()
        if not creds:
            return jsonify({"status":"unavailable"}), 404
        return jsonify({"status":"ok","ssid":creds["ssid"],"password":creds["password"]})

    @app.route("/api/provisioning/state", methods=["GET"])
    def provisioning_state():
        return jsonify({"provisioning_active": is_provisioning_active()})

    @app.route("/api/health", methods=["GET"])
    def health():
        birds = registry.get_birds()
        creds_present = has_credentials()
        return jsonify({
            "status": "ok",
            "provisioning_active": is_provisioning_active(),
            "credentials_present": creds_present,
            "bird_count": len(birds),
            "time": time.time()
        })

    @app.route("/api/volume_dry_run", methods=["POST"])
    def volume_dry_run():
        """Simulate volume schedule without sending commands to LMS.
        Expects JSON: {"song": <songName>}.
        Returns computed events list.
        """
        data = request.get_json(force=True)
        song_name = data.get("song")
        song_obj = next((s for s in songs if s.get("name") == song_name), None)
        if not song_obj:
            return jsonify({"status":"error","message":"Song not found"}), 404
        # Reuse parsing logic inline (duplicated small portion for isolation)
        individuals = song_obj.get("individuals", [])
        events = []
        for indiv in individuals:
            name = indiv.get("name")
            for rng in indiv.get("singing", []):
                if isinstance(rng, (list, tuple)) and len(rng) == 2:
                    try:
                        start, end = float(rng[0]), float(rng[1])
                        if end >= start:
                            events.append({"bird": name, "type": "start", "t": start})
                            events.append({"bird": name, "type": "end", "t": end})
                    except Exception:
                        continue
        events.sort(key=lambda e: e["t"])
        return jsonify({"status":"ok","song": song_name, "events": events})

    @app.route("/api/select", methods=["POST"])
    def select_song():
        data = request.json
        index = data.get("index")
        if index is not None and 0 <= index < len(songs):
            on_song_selected(index)
            return jsonify({"status": "ok", "queue": get_queue()})
        return jsonify({"status": "error", "message": "Invalid index"}), 400

    @app.route("/api/cancel", methods=["POST"])
    def cancel():
        # Implement this in your backend to stop playback and clear any queue as needed
        cancel_current_song()
        return jsonify({"status": "cancelled"})

    # Serve index.html for root
    @app.route("/")
    def serve_index():
        return send_from_directory(app.static_folder, "index.html")
    
    @app.route("/register", methods=["POST"])
    def register():
        data = request.get_json()
        bird_id = data.get("id")
        zero_time = data.get("time")
        requested_name = data.get("name")
        mac = data.get("mac")
        main_time = time.time()
        remote_ip = request.remote_addr

        if not bird_id or zero_time is None:
            return jsonify({"error": "Missing 'id' or 'time' in payload"}), 400

        time_offset = main_time - zero_time
        assigned_name = registry.register(bird_id, remote_ip, requested_name, mac=mac)
        print("/register assigned_name=", assigned_name, "mac=", mac)
        if assigned_name is None:
            return jsonify({"status": "failed", "message": "no name"}), 400

        # Build dynamic player map (name -> mac) for response convenience
        player_map = {n: b.get("mac") for n, b in registry.get_birds().items() if b.get("mac")}
        return jsonify({
            "status": "ok",
            "name": assigned_name,
            "time_offset": time_offset,
            "player_map": player_map,
        }), 200

    return app
