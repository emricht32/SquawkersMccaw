import time
import requests
from bird_registry import registry

# @app.route("/perform", methods=["POST"])
def send_song_start(song) -> dict:
    song_name = song.get("name")

    if not song_name:
        return {"error": "Missing song"}, 400

    birds = registry.get_birds()
    delay = 3.0  # Seconds until showtime
    start_time = time.time() + delay
    success, failed = [], []

    # only names in registry
    for bird_name, bird in birds.items():
        song_data_for_bird = get_bird_timings(song_name, song)

            
        payload = {
            "singing": song_data_for_bird.get("singing", []),
            "dancing": song_data_for_bird.get("dancing", []),
            "start_time": start_time
        }

        try:
            r = requests.post(f"http://{bird['ip']}:5001/perform", json=payload, timeout=2)
            if r.ok:
                success.append(bird_name)
            else:
                failed.append(bird_name)
        except Exception as e:
            print(f"Error sending to {bird_name}: {e}")
            failed.append(bird_name)

    return {
        "song": song_name,
        "start_time": start_time,
        "triggered": success,
        "failed": failed
    }

def get_bird_timings(bird_name: str, song_data: dict) -> dict:
    # Find the individual entry for the bird
    individual = next((b for b in song_data["individuals"] if b["name"] == bird_name), None)
    
    # If the bird isn't found, return only the "all" timings
    if not individual:
        return {
            "singing": song_data.get("all_singing", []),
            "dancing": song_data.get("all_dancing", [])
        }

    # Combine bird-specific and all timings
    singing = individual.get("singing", []) + song_data.get("all_singing", [])
    dancing = individual.get("dancing", []) + song_data.get("all_dancing", [])

    return {
        "singing": singing,
        "dancing": dancing
    }
