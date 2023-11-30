from bird import Bird
import time
import threading
# from pydub import AudioSegment, playback
import json
import os
import pear
# import numpy

import sounddevice
# import soundfile

try:
    from gpiozero import MotionSensor, Button
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

LAST_MOTION, PIR = None, None

def manage_leds(birds, audio_duration):
    print("manage_leds")
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
                    print(bird.name, ".is_dancing")                   
                    bird.start_dancing()
        time.sleep(sleep_time)

def play_audio_with_speech_indicator(dir, birds):
    # audio = AudioSegment.from_mp3(audio_path)
    # # audio = audio 
    # audio_duration = audio.duration_seconds

    # playback_thread = threading.Thread(target=playback.play, args=(audio,))
    # playback_thread.start()

    # manage_leds(birds, audio_duration)
    # playback_thread.join()
    def good_filepath(path):
        """
        Macro for returning false if the file is not a non-hidden wav file
        :param path: path to the file
        :return: true if a non-hidden wav, false if not a wav or hidden
        """
        return str(path).endswith(".wav") and (not str(path).startswith("."))
    # sound_file_paths = [os.path.join(os.getcwd(), "EnchantedTikiRoom_Old/BJB_TR_InTRoomSong", path) for path in sorted(filter(lambda path: good_filepath(path),
    #                                                                            os.listdir(".")))]
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
    # print("threads.count=", len(threads))
    # print("streams.count=", len(streams))
    # print("files.count=", len(files))
    # print("usb_sound_card_indices.count=", len(usb_sound_card_indices))
    try:
        seconds = 0
        for thread in threads:
            thread.start()
        for data, stream in zip(files, streams):
            # print('data = {}'.format(data))
            # print('len(data[0]) = {}'.format(len(data[0])))
            # print('sample rate = {}'.format(data[1]))
            # print('stream = {}'.format(stream))
            seconds = len(data[0]) / data[1]
            # print('seconds = {}'.format(seconds))
        manage_leds(birds, seconds)
        for thread, device_index in zip(threads, usb_sound_card_indices):
            print("Waiting for device", device_index, "to finish")
            thread.join()

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
    if os.path.exists('config.json'):
        # Read the file and load it into a dictionary
        with open('config.json', 'r') as f:
            config_dict = json.load(f)
    else:
        raise ValueError("missing config")

    all_singing = config_dict["all_singing"] or []
    all_dancing = config_dict["all_dancing"] or []
    birds = []

    for dict in config_dict["birds"]:
        beak = dict["beak"]
        body = dict["body"]
        light = dict["light"]
        speaker = dict["speaker"]
        name = dict["name"]
        intervals = dict["singing"]
        audio_path = dict["audio_path"]
        bird = Bird(name, intervals + all_singing, all_dancing, beak, body, light, speaker, audio_path)
        birds.append(bird)

    # if GPIO_AVAILABLE:
    #     PIR = MotionSensor(4)
    #     playDefault = Button(2)

    #     while True:
    #         if playDefault.is_pressed:
    #             print("Button is pressed")
    #             audio_dir = config_dict["audio_dir"]
    #             play_audio_with_speech_indicator(audio_dir, birds)
    #         else:
    #             print("Button is not pressed")

    # else:
        # audio_dir = config_dict["audio_dir"]
        # play_audio_with_speech_indicator(audio_dir, birds)
    
    
    
    # while True:
    #     PIR.wait_for_motion()
        # while True:
        #     pir_thread = threading.Thread(target=motion_tracker)
        #     pir_thread.start()

        #     while True:
        #         cur_time = time.time()
        #         if LAST_MOTION is not None and cur_time - LAST_MOTION < 20:
        #             break
        #     # Motion detected
            
        #     audio_path = "EnchantedTikiRoom_Old/BJB_TR_InTRoomSong.mp3"
        #     play_audio_with_speech_indicator(audio_path, birds)

            
    audio_dir = config_dict["audio_dir"]
    play_audio_with_speech_indicator(audio_dir, birds)