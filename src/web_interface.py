from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os

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

    return app
