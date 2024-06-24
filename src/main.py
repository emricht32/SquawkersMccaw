from bird import Bird
import time
import threading
# from pydub import AudioSegment, playback
import json
import os
import pear
import evdev

# import numpy

import sounddevice
# import soundfile

try:
    from gpiozero import MotionSensor, Button, LED
    import pigpio
    GPIO_AVAILABLE = True
except ImportError:
    print("GPIO not available")
    GPIO_AVAILABLE = False

LAST_MOTION, PIR = None, None

import RPi.GPIO as GPIO

def check_gpio_pins():
    GPIO.setmode(GPIO.BCM)  # Use BCM GPIO numbering
    pins_in_use = []
    for pin in range(2, 28):  # Check GPIO pins from 2 to 27
        try:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_OFF)  # Set pin to input with no pull-up/down
            status = GPIO.input(pin)
            if status is not None:
                pins_in_use.append(pin)
        except RuntimeError as e:
            print(f"GPIO {pin} is in use: {e}")
    
    GPIO.cleanup()  # Reset all GPIO pins
    
    if pins_in_use:
        print("Pins in use:", pins_in_use)
    else:
        print("No GPIO pins are currently in use.")

check_gpio_pins()

# YELLOW = Button(0)
# GREEN = Button(5)
# BLUE = Button(6)
# RED = Button(13)

remoteMap = {
    69:0,
    70:1,
    71:2,
    68:3,
    64:4,
    67:5,
    7:6,
    21:7,
    9:8,
    25:9,
    22:10,
    13:11,
    24:12,
    82:13,
    8:14,
    90:15,
    28:16,
    # "16":"*",
    # "0d":"#",
    # "18":"UP",
    # "52":"DOWN",
    # "08":"LEFT",
    # "5a":"RIGHT",
    # "1c":"OK",
}

def get_ir_device():
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for device in devices:
        if (device.name == "gpio_ir_recv"):
            print("Using device", device.path, "\n")
            print("device pins", device.capabilities(verbose=True))
            return device
    print("No device found!")

dev = get_ir_device()

def manage_leds(birds, audio_duration):
    print("manage_leds")
    print("audio_duration=",audio_duration)
    sleep_time = 0.3
    start_time = time.time()
    while time.time() - start_time < audio_duration:
        curr_time = time.time() - start_time
        for bird in birds:
            if bird.is_speaking(curr_time):
                print(bird.name, ".is_speaking")
                bird.start_moving(sleep_time)
            else:
                print(bird.name, ".stop_moving")
                bird.stop_moving()
                if bird.is_dancing(curr_time):     
                    # print(bird.name, ".is_dancing")                   
                    bird.start_dancing()
        time.sleep(sleep_time)
    for bird in birds:
        bird.stop_moving()

def play_audio_with_speech_indicator(song, birds):
    def good_filepath(path):
        """
        Macro for returning false if the file is not a non-hidden wav file
        :param path: path to the file
        :return: true if a non-hidden wav, false if not a wav or hidden
        """
        return str(path).endswith(".wav")  and (not str(path).startswith("."))
    
    for bird in birds:
        bird.prepare_song(song)
    dir = song["audio_dir"]
    sound_file_paths = [os.path.join(dir, path) for path in sorted(filter(lambda path: good_filepath(path),
                                                                               os.listdir(dir)))]
    print("sound_file_paths=",sound_file_paths)
    # print("pwd=",os.getcwd())
    files = [pear.load_sound_file_into_memory(path) for path in sound_file_paths]

    print("Files loaded into memory:", files)

    usb_sound_card_indices = list(filter(lambda x: x is not False,
                                         map(pear.get_device_number_if_usb_soundcard,
                                             [index_info for index_info in enumerate(sounddevice.query_devices())])))

    print("Discovered the following usb sound devices", usb_sound_card_indices)

    streams = [pear.create_running_output_stream(index) for index in usb_sound_card_indices]

    print("Playing files")

    threads = [threading.Thread(target=pear.play_wav_on_index, args=[data[0], stream])
                for data, stream in zip(files, streams)]
    
    AUDIO_POWER = LED(21)
    try:
        seconds = 0
        for thread in threads:
            thread.start()
        for data, stream in zip(files, streams):
            seconds = len(data[0]) / data[1]
            print('seconds = {}'.format(seconds))
        if GPIO_AVAILABLE:
            AUDIO_POWER.on()
        manage_leds(birds, seconds)
        for thread, device_index in zip(threads, usb_sound_card_indices):
            print("Waiting for device", device_index, "to finish")
            bird.stop_moving()
            thread.join()
        if not GPIO_AVAILABLE:
            AUDIO_POWER.off()
        print("Stopping stream")
        for stream in streams:
            stream.stop(ignore_errors=True)
            stream.close()
        print("Streams stopped")

    except KeyboardInterrupt:
        print("Stopping stream")
        for stream in streams:
            stream.abort(ignore_errors=True)
            stream.close()
        print("Streams stopped")

    print("Bye.")

def motion_tracker():
    global LAST_MOTION, PIR
    while True:
        PIR.wait_for_motion()
        LAST_MOTION = time.time()
        time.sleep(1)

if __name__ == "__main__":
    # Check if the file exists
    # config_multi_song
    if os.path.exists('config_multi_song.json'):
        # Read the file and load it into a dictionary
        with open('config_multi_song.json', 'r') as f:
            config_dict = json.load(f)
    else:
        raise ValueError("missing config")
    
    usb_sound_card_indices = list(filter(lambda x: x is not False,
                                         map(pear.get_device_number_if_usb_soundcard,
                                             [index_info for index_info in enumerate(sounddevice.query_devices())])))

    print("Discovered the following usb sound devices", usb_sound_card_indices)
    if len(usb_sound_card_indices) == 0:
        raise ValueError("No USB sound card found")

    # all_singing = config_dict["all_singing"] or []
    # all_dancing = config_dict["all_dancing"] or []
    birds = []

    for dict in config_dict["birds"]:
        beak = dict["beak"]
        body = dict["body"]
        light = dict["light"]
        name = dict["name"]
        bird = Bird(name, beak, body, light)
        birds.append(bird)

    songs = config_dict["songs"]
    while True:
        song = None
        event = None
        try:
            event = dev.read_one()
            if (event):
                print("Received event = ", event)
                print("Mapped Value      = ", remoteMap[event.value])
                if event.code == 4 and event.type == 4:
                    index = remoteMap[event.value]
                    song = songs[index]
                

            if True or YELLOW.is_pressed or True:
                song = songs[0]
            elif GREEN.is_pressed:
                song = songs[1]
            elif BLUE.is_pressed:
                song = songs[2]
            elif RED.is_pressed:
                song = songs[3]

            if song is not None:
                play_audio_with_speech_indicator(song, birds)
                for event in dev.read():
                    print("clearing event:", event)
        except IndexError:
            continue
        except BlockingIOError:
            continue
        except KeyError:
            if (event):
                print("KeyError: Received commands = ", event.value)
    
    dev.close()
    # for song in config_dict["songs"]:
    #     # if song["name"] == "Wellerman":
    #     play_audio_with_speech_indicator(song, birds)