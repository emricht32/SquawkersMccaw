from pathlib import Path
import glob
import json
import os


CONFIG_LOCATIONS = [
    "/Volumes/BIRDPI/config.json",          # USB
    "/boot/BIRDPI/config.json",             # Boot partition
    "config_multi_song_with_triggers.json"  # Local fallback
]

def load_and_union_configs():
    """Load config JSONs from all possible locations, union their bird and song lists."""
    union_config = {"birds": [], "songs": []}
    seen_birds = set()
    seen_songs = set()
    for config_path in CONFIG_LOCATIONS:
        f = Path(config_path)
        if f.exists():
            with open(f, 'r') as src:
                data = json.load(src)
                # Add unique birds
                for bird in data.get("birds", []):
                    name = bird.get("name")
                    if name and name not in seen_birds:
                        union_config["birds"].append(bird)
                        seen_birds.add(name)
                # Add unique songs (by 'name')
                for song in data.get("songs", []):
                    name = song.get("name")
                    if name and name not in seen_songs:
                        union_config["songs"].append(song)
                        seen_songs.add(name)
    if not union_config["birds"] or not union_config["songs"]:
        raise ValueError("No valid config found in any location!")
    return union_config

def resolve_song_audio_dirs(songs):
    """
    For each song, finds the first location (by priority) where a folder named <song_name> exists
    and contains at least one file starting with 0_ or 0- (any extension).
    Sets song['audio_dir'] to the relative path where found.
    """
    music_locations = [
        "/Volumes/BIRDPI/",
        "/boot/BIRDPI/",
        "./"
    ]
    for song in songs:
        song_name = song["name"]
        folder_name = song["audio_dir"]
        found = False
        for base_dir in music_locations:
            candidate_dir = os.path.join(base_dir, folder_name)
            if os.path.isdir(candidate_dir):
                files_underscore = glob.glob(os.path.join(candidate_dir, "0_*"))
                files_dash = glob.glob(os.path.join(candidate_dir, "0-*"))
                audio_files = files_underscore + files_dash
                if audio_files:
                    song["audio_dir"] = os.path.relpath(candidate_dir, ".")
                    found = True
                    break
        if not found:
            print(f"⚠️  Music directory not found (or no 0_ or 0- file) for song: {song_name}, dir: {folder_name}")
    return [song for song in songs if "audio_dir" in song]


