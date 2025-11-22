#!/usr/bin/env python3
"""bird.py

Controls LED behavior for a single Bird instance based on song interval data.
Can be invoked directly via CLI, intended for integration with piCorePlayer event listener.

Enhancements added:
 - Fixed incorrect use of .lowercase() -> .lower()
 - Defensive handling of missing config, song name, or intervals
 - Correct hostname parsing without misuse of strip()
 - Safer LED oscillation (no negative sleep times)
 - Standalone fallback if utils module unavailable
 - Support for --time and --duration from player status JSON
"""

import time
import threading
try:  # GPIO optional environment
    from gpiozero import LED
    GPIO_AVAILABLE = True
    print("GPIO_AVAILABLE")
except ImportError:
    import sys
    GPIO_AVAILABLE = False
    print("GPIO_NOT_AVAILABLE")
    print("sys.executable =", sys.executable)
    print("sys.path =", sys.path)

keep_playing = True

class Bird:
    def __init__(self, name, beak_led_pin, body_led_pin, spotlight_led_pin):
        print("Bird", name, " beak:", beak_led_pin, " body:", body_led_pin, " light:", spotlight_led_pin)
        self.name = name
        self.speech_intervals = []  # list[tuple[float,float]]
        self.dancing_intervals = []  # list[tuple[float,float]]
        self.beak_led = LED(beak_led_pin) if (GPIO_AVAILABLE and beak_led_pin is not None) else None
        self.body_led = LED(body_led_pin) if (GPIO_AVAILABLE and body_led_pin is not None) else None
        self.spotlight_led = LED(spotlight_led_pin) if (GPIO_AVAILABLE and spotlight_led_pin is not None) else None
        if self.spotlight_led is not None:
            self.spotlight_led.on()
        self.event = threading.Event()
        print("BirdInternal", self.name, " beak:", self.beak_led, " body:", self.body_led, " light:", self.spotlight_led)


    def prepare_song(self, song_dict):
        """Load intervals from song dictionary.
        song_dict must contain either top-level 'singing'/'dancing' or 'individuals'.
        """
        if not song_dict:
            print("No song data provided; bird will remain idle.")
            self.speech_intervals = []
            self.dancing_intervals = []
            return
        print("prepare_song")
        individual = None
        try:
            if song_dict.get("individuals") is not None:
                matches = [ind for ind in song_dict["individuals"] if ind.get("name") == self.name]
                if matches:
                    individual = matches[0]
            if individual is None:
                # fallback to whole dict (already per-node or broadcast)
                individual = song_dict
        except Exception as e:
            print(f"Error selecting individual data: {e}")
            individual = song_dict
        print("individual=", individual)
        speech_intervals = list(individual.get("singing", []))
        dancing_intervals = list(individual.get("dancing", []))
        # Merge global intervals
        speech_intervals.extend(song_dict.get("all_singing", []))
        dancing_intervals.extend(song_dict.get("all_dancing", []))
        self.speech_intervals = speech_intervals
        self.dancing_intervals = dancing_intervals

    def is_speaking(self, curr_time):
        print("is_speaking")
        tbr = any(start <= curr_time <= end for start, end in self.speech_intervals)
        print("is_speaking:", tbr)
        return tbr
    
    def is_dancing(self, curr_time):
        print("is_dancing")
        tbr = any(start <= curr_time <= end for start, end in self.dancing_intervals)
        print("is_dancin:g", tbr)
        return tbr

    
    # def start_speaking(self):
    #     try:
    #         # Called when bird should be "speaking" at this time slice
    #         if self.spotlight_led:
    #             print("self.spotlight_led.off() START")
    #             self.spotlight_led.off()  # reversed
    #             print("self.spotlight_led.off() END")
    #         if self.body_led:
    #             self.body_led.on()
    #             print("self.body_led.on()")
    #         if self.beak_led:
    #             self.beak_led.on()
    #             print("self.beak_led.on()")
    #         else:
    #             print(f"{self.name} SPEAKING")
    #     except Exception as e:
    #         print(f"Cant start start_speaking: {e}")
    def start_speaking(self, duration):
        if self.event.is_set():
            return
        self.event.set()
        self.start_dancing()

        if self.beak_led:
            threading.Thread(target=oscillate_led, args=(self.event, duration, self.beak_led)).start()
        else:
            threading.Thread(target=oscillate_logs, args=(self.event, duration, self.name)).start()
        

    def start_dancing(self):
        if self.spotlight_led:
            self.spotlight_led.off()  # reversed
        if self.body_led:
            self.body_led.on()
        # Beak stays whatever it was

    def stop_moving(self):
        self.event.clear()
        if self.spotlight_led:
            self.spotlight_led.on()  # reversed
        if self.body_led:
            self.body_led.off()
            print("self.beak_led.off()")
        if self.beak_led:
            self.beak_led.off()
            print("self.beak_led.off()")
            
def oscillate_led(event, duration, led):
    """Blink an LED with given cycle duration (one on + one off)."""
    on_time = 0.05
    off_time = max(duration - on_time, 0.0)
    while event.is_set():
        led.on()
        time.sleep(on_time)
        led.off()
        if off_time > 0:
            time.sleep(off_time)

def oscillate_logs(event, duration, name):
    while event.is_set():
        print(f"{name} LED ON")
        time.sleep(duration/2)
        print(f"{name} LED OFF")
        time.sleep(duration/2)

def manage_leds(birds, audio_duration, start_offset=0.0):  # <-- UPDATED SIGNATURE
    """Drive LED behavior over the approximate audio duration.
    Stops early if cancel_current_song() called.

    audio_duration: total track length in seconds (from LMS or interval data)
    start_offset: current playback position within the track, in seconds.
                  Allows LED timing to sync even if we start late.
    """
    global keep_playing
    print("manage_leds")
    print("audio_duration=", audio_duration, "start_offset=", start_offset)
    if audio_duration <= 0:
        print("No positive audio duration; skipping LED management.")
        for bird in birds:
            bird.stop_moving()
        return
    sleep_time = 0.3
    start_time_wall = time.time()
    while keep_playing and (time.time() - start_time_wall + start_offset) < audio_duration:
        curr_time = (time.time() - start_time_wall) + start_offset  # <-- track-time, not wall-time
        print("curr_time=", curr_time)
        for bird in birds:
            if bird.is_speaking(curr_time):
                bird.start_speaking(sleep_time)
            elif bird.is_dancing(curr_time):
                bird.start_dancing()
            else:
                bird.stop_moving()
        time.sleep(sleep_time)
    keep_playing = True
    for bird in birds:
        print("STOPPING Bird:", bird.name)
        bird.stop_moving()

def cancel_current_song():
    global keep_playing
    keep_playing = False

def load_config(path):
    if not path:
        return None
    if not isinstance(path, str):
        return None
    import os, json
    if not os.path.exists(path):
        print(f"Config file not found: {path}")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return None
    
import json  # you already have this imported at the top

def parse_lms_status(status_json: str):
    """
    Parse LMS player status JSON and extract:
    - song title (spaces -> underscores)
    - current time (float or None)
    - duration (float or None)

    Returns (song_name_or_None, time_or_None, duration_or_None).
    """
    if not status_json:
        return None, None, None

    try:
        d = json.loads(status_json)
    except Exception as e:
        print(f"⚠️ Failed to parse LMS status JSON: {e}")
        return None, None, None

    # Title from playlist_loop[0].title
    title = ""
    playlist = d.get("playlist_loop", [])
    if playlist and isinstance(playlist, list):
        title = str(playlist[0].get("title", "") or "")
    title_norm = title.replace(" ", "_") if title else None

    # Time + duration
    def to_float(val):
        if val is None or val == "":
            return None
        try:
            return float(val)
        except Exception:
            return None

    time_val = to_float(d.get("time"))
    duration_val = to_float(d.get("duration"))

    return title_norm, time_val, duration_val


def _derive_bird_name(hostname: str) -> str:
    name = hostname
    if name.startswith("birdpi-"):
        name = name[len("birdpi-") :]
    if name.endswith(".local"):
        name = name[: -len(".local")]
    return name.capitalize() if name != "main" else "Jose"

def main():
    import sys
    import socket
    import os
    # parser = argparse.ArgumentParser(description="Bird LED controller")
    default_config = os.path.join(os.path.dirname(__file__), "../config_single_bird.json")
    songs_path = os.path.join(os.path.dirname(__file__), "../config_multi_song_with_triggers.json")
    # parser.add_argument("--config", help="Path to bird node config", default=default_config)
    # parser.add_argument("--song", help="Song name (optional)")
    # parser.add_argument(
    #     "--time", help="Current playback time in seconds (from LMS status)",  # <-- NEW
    #     type=float, default=0.0
    # )
    # parser.add_argument(
    #     "--duration", help="Total track duration in seconds (from LMS status)",  # <-- NEW
    #     type=float, default=0.0
    # )
    # args = parser.parse_args()
    if len(sys.argv) < 3:
        print("No LMS JSON provided.")
        print("sys.argv=", sys.argv)
        return
    raw_args = sys.argv[2]
    title_norm, time_val, duration_val = parse_lms_status(raw_args)
    pins_config = load_config(default_config)
    songs_config = load_config(songs_path)
    if pins_config is None:
        print("Warning: No config loaded; GPIO pins may be undefined.")

    song_name = title_norm
    selected_song_dict = None
    if song_name:
        try:
            songs = songs_config.get("songs", [])
            matches = [s for s in songs if s.get("name", "").lower() == song_name.lower()]
            if matches:
                selected_song_dict = matches[0]
            else:
                print(f"Song '{song_name}' not found; continuing without intervals.")
        except Exception as e:
            print(f"Error loading songs: {e}")
    elif song_name:
        print("utils not available; cannot resolve song intervals.")

    hostname = socket.gethostname()
    bird_name = _derive_bird_name(hostname)

    # GPIO pin mappings
    beak_pin = pins_config.get("beak") if pins_config else None
    body_pin = pins_config.get("body") if pins_config else None
    spotlight_pin = pins_config.get("light") if pins_config else None

    bird_instance = Bird(
        name=bird_name,
        beak_led_pin=beak_pin,
        body_led_pin=body_pin,
        spotlight_led_pin=spotlight_pin,
    )

    bird_instance.prepare_song(selected_song_dict)

    # Compute max interval length (fallback if --duration not given)
    if bird_instance.speech_intervals or bird_instance.dancing_intervals:
        max_singing = max((num for pair in bird_instance.speech_intervals for num in pair), default=0)
        max_dancing = max((num for pair in bird_instance.dancing_intervals for num in pair), default=0)
        seconds = max(max_singing, max_dancing)
    else:
        seconds = 0

    # Prefer explicit duration from LMS; fall back to interval-derived length
    audio_duration = duration_val if duration_val > 0 else seconds  # <-- NEW
    start_offset = time_val if time_val > 0 else 0.0               # <-- NEW

    # manage_leds([bird_instance], audio_duration, start_offset=start_offset)

    threading.Thread(
        target=manage_leds,
        args=([bird_instance], audio_duration),
        kwargs={"start_offset": start_offset},
        daemon=False
    ).start()
    # manage_leds([bird_instance], audio_duration, start_offset=start_offset)  # <-- UPDATED CALL

if __name__ == "__main__":
    main()
