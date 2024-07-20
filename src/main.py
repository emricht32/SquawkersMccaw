import time
import threading
import json
import os
import pear
import evdev
import sounddevice

try:
    from gpiozero import MotionSensor, Button, LED
    GPIO_AVAILABLE = True
except ImportError:
    print("GPIO not available")
    GPIO_AVAILABLE = False

from bird import Bird

LAST_MOTION, PIR = None, None

# Button setup
YELLOW = Button(0)
GREEN = Button(5)
BLUE = Button(6)
RED = Button(13)

# IR remote mapping
remoteMap = {
    69: 0, 70: 1, 71: 2, 68: 3, 64: 4, 67: 5,
    7: 6, 21: 7, 9: 8, 25: 9, 22: 10, 13: 11,
    24: 12, 82: 13, 8: 14, 90: 15, 28: 16,
}

CLEAR = 16
stop_flag = threading.Event()

def get_ir_device():
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for device in devices:
        if device.name == "gpio_ir_recv":
            print("Using device", device.path)
            print("Device pins", device.capabilities(verbose=True))
            return device
    print("No device found!")
    return None

dev = get_ir_device()

def manage_leds(birds, audio_duration):
    print("manage_leds")
    print("audio_duration=", audio_duration)
    sleep_time = 0.3
    start_time = time.time()
    index = 0
    while (time.time() - start_time < audio_duration):
        if stop_flag.is_set():
            break
        try:
            event = dev.read_one()
            if event and event.code == 4 and event.type == 4:
                index = remoteMap.get(event.value)
                if index == CLEAR:
                    stop_flag.set()
                    break
        except IndexError:
            continue
        curr_time = time.time() - start_time
        for bird in birds:
            if bird.is_speaking(curr_time):
                bird.start_moving(sleep_time)
            else:
                bird.stop_moving()
                if bird.is_dancing(curr_time):
                    bird.start_dancing()
        time.sleep(sleep_time)
    for bird in birds:
        bird.stop_moving()

def play_audio_with_speech_indicator(song, birds):
    def good_filepath(path):
        return str(path).endswith(".wav") and not str(path).startswith(".")

    for bird in birds:
        bird.prepare_song(song)
    dir = song["audio_dir"]
    sound_file_paths = [os.path.join(dir, path) for path in sorted(filter(good_filepath, os.listdir(dir)))]

    files = [pear.load_sound_file_into_memory(path) for path in sound_file_paths]

    usb_sound_card_indices = list(filter(lambda x: x is not False,
                                         map(pear.get_device_number_if_usb_soundcard,
                                             [index_info for index_info in enumerate(sounddevice.query_devices())])))

    streams = [pear.create_running_output_stream(index) for index in usb_sound_card_indices]

    threads = [threading.Thread(target=pear.play_wav_on_index, args=[data[0], stream, stop_flag])
               for data, stream in zip(files, streams)]

    AUDIO_POWER = LED(20) if GPIO_AVAILABLE else None
    try:
        for thread in threads:
            thread.start()
        seconds = max(len(data[0]) / data[1] for data in files)
        if GPIO_AVAILABLE:
            AUDIO_POWER.on()
        manage_leds(birds, seconds)
        stop_flag.set()  # Signal threads to stop
        for thread in threads:
            thread.join()
        if GPIO_AVAILABLE:
            AUDIO_POWER.off()
        for stream in streams:
            stream.stop(ignore_errors=True)
            stream.close()
    except KeyboardInterrupt:
        stop_flag.set()
        for stream in streams:
            stream.abort(ignore_errors=True)
            stream.close()

def motion_tracker():
    global LAST_MOTION, PIR
    while True:
        PIR.wait_for_motion()
        LAST_MOTION = time.time()
        time.sleep(1)

if __name__ == "__main__":
    print("Starting main")
    POWER_LIGHT = LED(21) if GPIO_AVAILABLE else None
    if POWER_LIGHT:
        print("POWER_LIGHT on")
        POWER_LIGHT.on()

    if os.path.exists('config_multi_song.json'):
        with open('config_multi_song.json', 'r') as f:
            config_dict = json.load(f)
    else:
        raise ValueError("Missing config")

    usb_sound_card_indices = list(filter(lambda x: x is not False,
                                         map(pear.get_device_number_if_usb_soundcard,
                                             [index_info for index_info in enumerate(sounddevice.query_devices())])))

    if len(usb_sound_card_indices) == 0:
        raise ValueError("No USB sound card found")

    birds = [Bird(bird["name"], bird["beak"], bird["body"], bird["light"]) for bird in config_dict["birds"]]
    songs = config_dict["songs"]

    while True:
        time.sleep(1)
        song = None
        event = None
        try:
            event = dev.read_one()
            if event and event.code == 4 and event.type == 4:
                index = remoteMap.get(event.value)
                if index is not None:
                    song = songs[index]
            elif YELLOW.is_pressed:
                song = songs[0]
            elif GREEN.is_pressed:
                song = songs[1]
            elif BLUE.is_pressed:
                song = songs[2]
            elif RED.is_pressed:
                song = songs[3]

            if song:
                stop_flag.clear()
                play_audio_with_speech_indicator(song, birds)
                for event in dev.read():
                    print("Clearing event:", event)
        except IndexError:
            continue
        except BlockingIOError:
            continue
        except KeyError:
            if event:
                print("KeyError: Received commands =", event.value)
        except KeyboardInterrupt:
            continue
        except sounddevice.PortAudioError:
            print("PortAudioError")
            continue
    for bird in birds:
        bird.stop_moving()
    if POWER_LIGHT:
        print("POWER_LIGHT off")
        POWER_LIGHT.off()
    dev.close()
