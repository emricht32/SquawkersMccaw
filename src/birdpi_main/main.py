import threading
import json
import os
from common.bird import Bird
from send_song_start import send_song_start
from bird_registry import registry
from play_audio import play_audio_with_speech_indicator
import utils

try:
    from gpiozero import MotionSensor, Button, LED
    GPIO_AVAILABLE = True
except ImportError:
    print("GPIO not available")
    GPIO_AVAILABLE = False

LAST_MOTION, PIR = None, None

CONFIG_FILE = 'config_multi_song_with_triggers.json'

# from ble_song_selector import BLESongSelector
# from voice_input import voice_listener
# from remote_input import remote_listener
from web_interface import create_web_interface
import qrcode
import socket
import os

def generate_qr_code(output_path="static/birds_qr.png", port=8080):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        print("s.getsockname()=", socket.gethostname())
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()

    url = f"http://{ip}:{port}/"
    print(f"🌐 Generating QR for: {url}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    qr = qrcode.make(url)
    qr.save(output_path)
    print(f"✅ Saved QR to {output_path}")


    # Start Flask server
def start_web_server(songs):
    print("Start Flask server")
    app = create_web_interface(songs, on_song_selected)
    app.run(host="0.0.0.0", port=8080)

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def get_mdns_name():
    return f"{socket.gethostname()}.local"

import signal
import sys

POWER_LIGHT = LED(5) if GPIO_AVAILABLE else None
def cleanup_and_exit(signum=None, frame=None):
    global POWER_LIGHT
    print("Turning off light and cleaning up...")
    if POWER_LIGHT:
        POWER_LIGHT.off()
        POWER_LIGHT.close()
        sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, cleanup_and_exit)   # Ctrl+C
signal.signal(signal.SIGTERM, cleanup_and_exit)  # kill

if __name__ == "__main__":
    def song_completion(song):
        global current_index
        current_index = None

    # Example callback when app selects a song
    def on_song_selected(index):
        global current_index
        if index is not None:
            song = songs[index] if 0 <= index < len(songs) else None

            # Trigger your play_audio_with_speech_indicator() logic here
            # song = songs[5] happy bday
            if song:
                name = song.get("name")
                print(f"🎬 Playing song #{index}: {name}")
                current_index = index
                # {
                #     "song": song_name,
                #     "start_time": start_time,
                #     "triggered": success,
                #     "failed": failed
                # }
                send_dict = send_song_start(song)
                start_time = send_dict["start_time"]
                filtered_birds = [bird for bird in birds if bird.name not in registry.get_bird_names()]
                play_audio_with_speech_indicator(song, filtered_birds, start_time, completion=song_completion)

###################START###################
    current_index = None

    generate_qr_code()
    config_dict = utils.load_and_union_configs()
    songs = utils.resolve_song_audio_dirs(config_dict["songs"])
    
    pwr_lt = config_dict.get("on_light")

    if pwr_lt is not None:
        POWER_LIGHT = LED(int(pwr_lt))
        print("POWER_LIGHT on")
        POWER_LIGHT.on()

    print("Starting main")

    birds = [Bird(bird["name"], bird["beak"], bird["body"], bird["light"]) for bird in config_dict["birds"]]
    display_names = [song.get("display_name", song.get("name", "Unknown")) for song in songs]

    try:
        # Start Flask server in a thread
        web_thread = threading.Thread(target=start_web_server, args=(songs,), daemon=True)
        web_thread.start()

        while True:
            continue

    except Exception as e:
        print("❌ Exception occurred:", e)
    finally:
        for bird in birds:
            bird.stop_moving()
        cleanup_and_exit()
