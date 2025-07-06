from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
from bird_registry import registry
import time

def create_web_interface(songs, on_song_selected):
    app = Flask(__name__, static_folder="static", static_url_path="")
    CORS(app)

    @app.route("/api/songs", methods=["GET"])
    def get_songs():
        return jsonify([
            {"index": i, "name": song.get("display_name", song.get("name", "Unknown"))}
            for i, song in enumerate(songs)
        ])

    @app.route("/api/select", methods=["POST"])
    def select_song():
        data = request.json
        index = data.get("index")
        if index is not None and 0 <= index < len(songs):
            on_song_selected(index)
            return jsonify({"status": "ok"})
        return jsonify({"status": "error", "message": "Invalid index"}), 400

    # Serve index.html for root
    @app.route("/")
    def serve_index():
        return send_from_directory(app.static_folder, "index.html")
    
    @app.route("/register", methods=["POST"])
    def register():
        data = request.get_json()
        bird_id = data.get("id")
        zero_time = data.get("time")  # This is the Zero Pi's reported time
        bird_name = data.get("name")
        main_time = time.time()
        remote_ip = request.remote_addr

        if not bird_id or zero_time is None:
            return jsonify({"error": "Missing 'id' or 'time' in payload"}), 400

        time_offset = main_time - zero_time  # How far ahead the main Pi is

        registry.register(bird_id, remote_ip, bird_name)  # Store bird info

        return jsonify({
            "status": "ok",
            "name": bird_id,
            "time_offset": time_offset
        })

    return app
