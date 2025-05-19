import time
import threading
import json
import os
import pear
import evdev
import sounddevice
from bird import Bird


try:
    from gpiozero import MotionSensor, Button, LED
    GPIO_AVAILABLE = True
except ImportError:
    print("GPIO not available")
    GPIO_AVAILABLE = False

LAST_MOTION, PIR = None, None
playback_lock = threading.Lock()

def manage_leds(birds, audio_duration):
    print("manage_leds")
    print("audio_duration=", audio_duration)
    sleep_time = 0.3
    start_time = time.time()
    curr_time = time.time() - start_time
    while (curr_time < audio_duration):
        curr_time = time.time() - start_time
        print("curr_time=", curr_time)
        for bird in birds:
            if bird.is_speaking(curr_time):
                bird.start_moving(sleep_time)
            else:
                bird.stop_moving()
                if bird.is_dancing(curr_time):
                    bird.start_dancing()
        time.sleep(sleep_time)
    for bird in birds:
        print("STOPPING Bird:", bird.name)
        bird.stop_moving()

def play_audio_with_speech_indicator(song, birds, completion=None):
    if playback_lock.acquire(blocking=False):
        try:
            _play_audio_with_speech_indicator(song, birds, completion=completion)
        finally:
            playback_lock.release()
    else:
        print("⚠️ Playback already in progress, ignoring new voice command.")


def _play_audio_with_speech_indicator(song, birds, completion):
    def good_filepath(path):
        return str(path).endswith(".wav") and not str(path).startswith(".")

    for bird in birds:
        bird.prepare_song(song)
    audio_dir = song["audio_dir"]
    sound_file_paths = [os.path.join(audio_dir, path) for path in sorted(filter(good_filepath, os.listdir(audio_dir)))]
    print("sound_file_paths=", sound_file_paths)
    # files = [pear.load_sound_file_into_memory(path) for path in sound_file_paths]
    # Separate master file and other files
    master_file_path = next(
        (path for path in sound_file_paths if os.path.basename(path).startswith("0")),
        None
    )
    print("master_file_path=", master_file_path)
    non_master_file_paths = [path for path in sound_file_paths if not os.path.basename(path).startswith("0")]
    files = [pear.load_sound_file_into_memory(path) for path in non_master_file_paths]

    print("non_master_file_paths=", non_master_file_paths)

    # Ensure there is only one master file
    master_file = None
    if master_file_path:
        master_file = pear.load_sound_file_into_memory(master_file_path)  # Take the first master file
        print("master_file=", master_file)

    usb_sound_card_indices_touple = list(filter(lambda x: x is not False and x[1] is False,
                                         map(pear.get_device_number_if_usb_soundcard,
                                             [index_info for index_info in enumerate(sounddevice.query_devices())])))
    print("usb_sound_card_indices_touple=", usb_sound_card_indices_touple)
    master_card_touple = next(
        (x for x in map(pear.get_device_number_if_usb_soundcard, 
                        enumerate(sounddevice.query_devices())) 
        if x and x[1] is True), 
        None
    )
    print("master_card_touple=",master_card_touple)

    # Create non-master streams
    streams = [
        pear.create_running_output_stream(index)
        for (index, isMaster) in usb_sound_card_indices_touple
        if not isMaster
    ]

    # Create the master stream 
    master_stream = pear.create_running_output_stream(master_card_touple[0])  
    print("master_stream=",master_stream)

    # uncomment thread list if having bird audio
    threads = [] #[threading.Thread(target=pear.play_wav_on_index, args=[data[0], stream])
               # for data, stream in zip(files, streams)]

    # Create the master thread (assuming master_stream and master_file are defined)
    if master_stream is not None and master_file is not None:
        print("master_stream is not None and master_file is not None")
        master_thread = threading.Thread(
            target=pear.play_wav_on_index,
            args=[master_file[0], master_stream]
        )
        threads.append(master_thread)
    else:
        print("Master not running")

    try:
        try:
            print("# Start all playback threads")
            for thread in threads:
                thread.start()

            print("# Calculate the longest playback duration")
            seconds = max(len(data[0]) / data[1] for data in files)

            print("# Manage LEDs during audio playback")
            manage_leds(birds, seconds)

            print("# Wait for all threads to complete")
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            print("Playback interrupted by user")
            for stream in streams:
                stream.abort(ignore_errors=True)
                stream.close()
        except Exception as e:
            print(f"An error occurred during playback: {e}")
    finally:
        # Ensure all streams are properly stopped and closed
        for stream in streams:
            if not stream.closed:
                stream.stop(ignore_errors=True)
                stream.close()
        if master_stream and not master_stream.closed:
            master_stream.stop(ignore_errors=True)
            master_stream.close()

        for bird in birds:
            print("STOPPING Bird:", bird.name)
            bird.stop_moving()

        if completion is not None:
            completion(song)


from ble_song_selector import BLESongSelector
from voice_input import voice_listener
from remote_input import remote_listener
from web_interface import create_web_interface

    # Start Flask server
def start_web_server(songs):
    print("Start Flask server")
    app = create_web_interface(songs, on_song_selected)
    app.run(host="0.0.0.0", port=8080)



if __name__ == "__main__":
    current_index = None

    print("Starting main")
    POWER_LIGHT = LED(5) if GPIO_AVAILABLE else None
    if POWER_LIGHT:
        print("POWER_LIGHT on")
        POWER_LIGHT.on()

    if os.path.exists('config_multi_song_with_triggers.json'):
        with open('config_multi_song_with_triggers.json', 'r') as f:
            config_dict = json.load(f)
    else:
        raise ValueError("Missing config")
    print("sounddevice.query_devices()=",sounddevice.query_devices())

    def song_completion(song):
        current_index = None
        if ble_handler:
            ble_handler.send_playback_status("finished")

    # Example callback when app selects a song
    def on_song_selected(index):
        if current_index is not None: 
            ble_handler.send_playback_status(status="playing", index=current_index)
            return
        if index is not None:
            song = songs.get(index)
            name = song["name"]
            print(f"🎬 Playing song #{index}: {name}")
            # Trigger your play_audio_with_speech_indicator() logic here
            # song = songs[5] happy bday
            if song:
                current_index = index
                ble_handler.send_playback_status(status="playing", index=current_index)
                play_audio_with_speech_indicator(song, birds, completion=song_completion)

    birds = [Bird(bird["name"], bird["beak"], bird["body"], bird["light"]) for bird in config_dict["birds"]]
    songs = config_dict["songs"]
    display_names = [song.get("display_name", song.get("name", "Unknown")) for song in songs]

    # Start Flask server in a thread
    web_thread = threading.Thread(target=start_web_server, args=(songs,), daemon=True)
    web_thread.start()
    print("🌐 Web interface started at http://<raspberry-pi-ip>:8080")
    


    try:

        # threading.Thread(target=voice_listener, args=(songs, on_song_selected), daemon=False).start()
        # threading.Thread(target=remote_listener, args=(on_song_selected), daemon=False).start()

        # your existing setup and run logic
        ble_handler = BLESongSelector(display_names, on_song_selected)
        ble_handler.start()

        # ... other logic
        while True:
            continue

    except Exception as e:
        print("❌ Exception occurred:", e)
    finally:
        for bird in birds:
            bird.stop_moving()
        if POWER_LIGHT:
            print("POWER_LIGHT off")
            POWER_LIGHT.off()
        if ble_handler:
            ble_handler.stop()
