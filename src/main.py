import time
import threading
import json
import os
import pear
import evdev
import sounddevice
from vosk import Model, KaldiRecognizer
import pyaudio
from rapidfuzz import process


try:
    from gpiozero import MotionSensor, Button, LED
    GPIO_AVAILABLE = True
except ImportError:
    print("GPIO not available")
    GPIO_AVAILABLE = False

from bird import Bird

LAST_MOTION, PIR = None, None
playback_lock = threading.Lock()

def manage_leds(birds, audio_duration):
    print("manage_leds")
    print("audio_duration=", audio_duration)
    CLEAR = 16
    sleep_time = 0.3
    start_time = time.time()
    curr_time = time.time() - start_time
    index = 0
    while (curr_time < audio_duration):
        try:
            event = dev.read_one()
            print("Received commands =", event)
            if event and event.code == 4 and event.type == 4:
                index = remoteMap.get(event.value)
                print("index=", index)
                if index == CLEAR:
                    for bird in birds:
                        bird.stop_moving()
                    raise KeyboardInterrupt
        except IndexError:
            continue
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

def play_audio_with_speech_indicator(song, birds):
    if playback_lock.acquire(blocking=False):
        try:
            _play_audio_with_speech_indicator(song, birds)
        finally:
            playback_lock.release()
    else:
        print("⚠️ Playback already in progress, ignoring new voice command.")


def _play_audio_with_speech_indicator(song, birds):
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
            # Start all playback threads
            for thread in threads:
                thread.start()

            # Calculate the longest playback duration
            seconds = max(len(data[0]) / data[1] for data in files)

            # Manage LEDs during audio playback
            manage_leds(birds, seconds)

            # Wait for all threads to complete
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

# def voice_listener(songs, birds):
#     try:
#         print("🔊 Starting voice listener thread")
        
#         # Build trigger map first
#         trigger_map = {}
#         for song in songs:
#             for phrase in song.get("triggers", []):
#                 trigger_map[phrase.lower()] = song

#         def match_song(transcript):
#             transcript = transcript.lower()
#             for trigger, song in trigger_map.items():
#                 if trigger in transcript:
#                     return song

#             # fallback to fuzzy matching
#             best_match, score, _ = process.extractOne(transcript, list(trigger_map.keys()), score_cutoff=70)
#             if best_match:
#                 return trigger_map[best_match]

#             return None


#         print("Loading Vosk model...")
#         model = Model("models/vosk-model-small-en-us-0.15")
#         print("Model loaded")

#         recognizer = KaldiRecognizer(model, 16000)
#         print("Recognizer created")

#         print("Creating PyAudio object...")
#         p = pyaudio.PyAudio()
#         print("Opening stream...")
#         stream = p.open(
#             format=pyaudio.paInt16,        # 16-bit signed int
#             channels=1,                    # Mono channel
#             rate=16000,                    # Sample rate (Hz)
#             input=True,                    # Input stream
#             frames_per_buffer=8000         # Buffer size
#         )

#         print("Starting stream...")
#         stream.start_stream()
#         print("Stream started ✅")


#         while True:
#             try:
#                 data = stream.read(4000, exception_on_overflow=False)
#             except Exception as e:
#                 print("⚠️ Error reading audio stream:", e)
#                 continue

#             if recognizer.AcceptWaveform(data):
#                 result = recognizer.Result()
#                 print("Recognized:", result)
#                 # TODO: match and trigger birds
#                 song = match_song(result)
#                 if song:
#                     play_audio_with_speech_indicator(song, birds)
#             else:
#                 print("Partial:", recognizer.PartialResult())

#     except Exception as e:
#         print("❌ Exception in voice_listener thread:", e)
#         import traceback
#         traceback.print_exc()


# IR remote mapping
# remoteMap = {
#     69: 0, 70: 1, 71: 2, 68: 3, 64: 4, 67: 5,
#     7: 6, 21: 7, 9: 8, 25: 9, 22: 10, 13: 11,
#     24: 12, 82: 13, 8: 14, 90: 15, 28: 16,
# }

# def get_ir_device():
#     devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
#     for device in devices:
#         if device.name == "gpio_ir_recv":
#             print("Using device", device.path)
#             print("Device pins", device.capabilities(verbose=True))
#             return device
#     print("No device found!")
#     return None

# dev = get_ir_device()


# def remote_listener(songs, birds):

#     while True:
#         time.sleep(1)
#         song = None
#         event = None
#         try:
#             event = dev.read_one()
#             print("Received commands =", event)
#             if event and event.code == 4 and event.type == 4:
#                 index = remoteMap.get(event.value)
#                 if index is not None:
#                     song = songs[index]
#             # song = songs[5] happy bday
#             if song:
#                 play_audio_with_speech_indicator(song, birds)
#                 for event in dev.read():
#                     print("Clearing event:", event)
#         except IndexError:
#             continue
#         except BlockingIOError:
#             continue
#         except KeyError:
#             if event:
#                 print("KeyError: Received commands =", event.value)
#         except KeyboardInterrupt:
#             continue
#         except sounddevice.PortAudioError:
#             print("PortAudioError")
#             continue
    # for song in songs:
    #     if song["name"] == "Wellerman":
    #         play_audio_with_speech_indicator(song, birds)
    # for bird in birds:
    #     bird.stop_moving()
    # if POWER_LIGHT:
    #     print("POWER_LIGHT off")
    #     POWER_LIGHT.off()
    # dev.close()

from ble_song_selector import BLESongSelector
from voice_input import voice_listener
from remote_input import remote_listener

if __name__ == "__main__":
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

    # Example callback when app selects a song
    def on_song_selected(index):
        if index is not None:
            song = songs[index]
            name = song["name"]
            print(f"🎬 Playing song #{index}: {name}")
            # Trigger your play_audio_with_speech_indicator() logic here
            # song = songs[5] happy bday
            if song:
                play_audio_with_speech_indicator(song, birds)

    birds = [Bird(bird["name"], bird["beak"], bird["body"], bird["light"]) for bird in config_dict["birds"]]
    songs = config_dict["songs"]
    display_names = [song.get("display_name", song.get("name", "Unknown")) for song in songs]

    try:
        # your existing setup and run logic
        ble_handler = BLESongSelector(display_names, on_song_selected)
        ble_handler.start()

        threading.Thread(target=voice_listener, args=(songs, on_song_selected), daemon=False).start()
        threading.Thread(target=remote_listener, args=(on_song_selected), daemon=False).start()
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
