import threading
import json
import os
from src.common import bird
from src.common.bird import Bird
from send_song_start_stop import send_song_start, post_cancel_to_bird
from bird_registry import registry
from play_audio import play_audio_with_speech_indicator, is_playing_song
from queue import Queue
import src.common.utils as utils
from src.common.utils import load_system_config
from lms_control import play_song_with_volume_schedule

try:
    from gpiozero import MotionSensor, Button, LED
    GPIO_AVAILABLE = True
except ImportError:
    print("GPIO not available")
    GPIO_AVAILABLE = False

LAST_MOTION, PIR = None, None

# Removed unused CONFIG_FILE constant; config loading handled via utils.load_and_union_configs()

# from ble_song_selector import BLESongSelector
# Voice input (vosk) removed; dependency pruned.
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
    app = create_web_interface(songs, on_song_selected, cancel_current_song, get_queue)
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
        if not queue.empty():
            on_song_selected(queue.get()) 


    # Example callback when app selects a song
    # TODO: Handle queue
    # Load centralized system config (LMS host/port, optional static birds/master metadata)
    system_cfg = load_system_config()
    USE_LMS = True  # still feature flag; could be system_cfg.get('lms', {}).get('enabled', True)
    validation_delay = system_cfg.get("startup_validation_delay", 30)
    periodic_interval = system_cfg.get("periodic_validation_interval", 300)
    # Dynamic player map (bird name -> MAC) built from registry; static map deprecated.
    def get_dynamic_player_map():
        return {name: info.get("mac") for name, info in registry.get_birds().items() if info.get("mac")}

    def on_song_selected(index, queue=False):
        global current_index, registry
        if index is not None:
            song = songs[index] if 0 <= index < len(songs) else None
            if song:
                if is_playing_song():
                    add_to_queue(index)
                else:
                    current_index = index
                    send_dict = send_song_start(song)
                    start_time = send_dict["start_time"]
                    active_map = get_dynamic_player_map()
                    if USE_LMS and "lms_track" in song and active_map:
                        print("Using LMS playback path (map size=", len(active_map), ")")
                        play_song_with_volume_schedule(
                            song,
                            start_time,
                            active_map,
                            speaking_volume=80,
                            background_volume=15,
                            muted_volume=0,
                            use_background=True,
                        )
                    else:
                        print("Falling back to local audio playback.")
                        filtered_birds = [bird for bird in birds if bird.name not in registry.get_bird_names()]
                        play_audio_with_speech_indicator(song, filtered_birds, start_time, completion=song_completion)
    
    def add_to_queue(index):
        queue.put(index)


    def cancel_current_song():
        global current_index
        if current_index is not None:
            song = songs[current_index]
            song_name = song.get("name")
            for b in registry.get_birds().values():
                print("cancel_current_song.birds[].bird=",b)
                post_cancel_to_bird(b, song_name)
        bird.cancel_current_song()

    def get_queue():
        return list(queue.queue)

###################START###################
    current_index = None
    queue = Queue()

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

    # Startup validation: ensure expected birds register within a grace window.
    def schedule_startup_validation(expected_names, delay_seconds=30):
        def _validate():
            current = set(registry.get_birds().keys())
            missing = [n for n in expected_names if n not in current]
            if missing:
                print(f"[startup-validation] Missing birds after {delay_seconds}s: {', '.join(missing)}")
            else:
                print(f"[startup-validation] All expected birds registered ({len(expected_names)}) within {delay_seconds}s.")
        threading.Timer(delay_seconds, _validate).start()

    def schedule_periodic_validation(expected_names, interval_seconds=300):
        previous_missing = set()
        def _periodic():
            current = set(registry.get_birds().keys())
            missing = {n for n in expected_names if n not in current}
            recovered = previous_missing - missing
            newly_missing = missing - previous_missing
            if newly_missing:
                print(f"[periodic-validation] Newly missing: {', '.join(sorted(newly_missing))}")
            if recovered:
                print(f"[periodic-validation] Recovered: {', '.join(sorted(recovered))}")
            if not missing and not newly_missing and not recovered:
                print(f"[periodic-validation] All expected birds present ({len(expected_names)})")
            # update and reschedule
            previous_missing.clear()
            previous_missing.update(missing)
            threading.Timer(interval_seconds, _periodic).start()
        threading.Timer(interval_seconds, _periodic).start()

    expected_bird_names = [b.name for b in birds]
    schedule_startup_validation(expected_bird_names, delay_seconds=validation_delay)
    schedule_periodic_validation(expected_bird_names, interval_seconds=periodic_interval)

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
