# import time
# import threading
# from pydub import AudioSegment, playback

# try:
#     from gpiozero import LED
#     GPIO_AVAILABLE = True
# except ImportError:
#     GPIO_AVAILABLE = False

# Speech intervals for José and Michael
jose_intervals = [
    (2.7,5.2),(11,12.2),(16.5,26),(32.25,33.75),(42,44.2),(57.75,64.5),
    (67,68.5),(80,91),(96.2,97.6),(117.5,119),(123,133.5)
] 
michael_intervals = [
    (12.5, 13.5), (34.0, 35.0), (38.0, 42.0), (64.3, 67.2), (68.2, 75.0),
    (97.8, 98.8), (101.5, 112.4), (119.0, 120.2)
] 
pierre_intervals = [
    (44.2, 49)
]
# pierre_intervals =[
#     (2.9,5.2),(10,12.2),(16.5,26),(32.25,33.75),(42,44.2),(57.75,64.5),
#     (67,68.5),(80,91),(96.2,97.6),(117.5,119),(123,133.5)
# ]

fritz_intervals = [
    (49, 57.5),(144.1, 145.3)
]

all_intervals = [
    (5.8, 11),(13.75, 16),(26, 32),(35,37.5),(91, 96),(99, 101.6),
    (112.2, 117.5),(120.4, 123),(133.5, 139),(139, 144),(144.5, 155)
]

from bird import Bird
import time
import threading
from pydub import AudioSegment, playback

try:
    from gpiozero import MotionSensor
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

LAST_MOTION, PIR = None, None

def manage_leds(birds, audio_duration):
    sleep_time = 0.3
    start_time = time.time()
    while time.time() - start_time < audio_duration:
        curr_time = time.time() - start_time
        for bird in birds:
            if bird.is_speaking(curr_time):
                bird.start_moving(sleep_time)
            else:
                bird.stop_moving()
        time.sleep(sleep_time)

def play_audio_with_speech_indicator(audio_path, birds):
    audio = AudioSegment.from_mp3(audio_path)
    audio = audio + 40
    audio_duration = audio.duration_seconds

    playback_thread = threading.Thread(target=playback.play, args=(audio,))
    playback_thread.start()

    manage_leds(birds, audio_duration)
    playback_thread.join()

def motion_tracker():
    global LAST_MOTION, PIR
    while True:
        PIR.wait_for_motion()
        LAST_MOTION = time.time()
        time.sleep(1)

if __name__ == "__main__":
    # Pierre: GPIO25 (pin 22) and GPIO24 (pin 18)
    # Jose: GPIO23 (pin 16) and GPIO22 (pin 15)
    # Michael: GPIO27 (pin 13) and GPIO18 (pin 12)
    # Fritz: GPIO17 (pin 11) and GPIO4 (pin 7)
    # jose = Bird("Jose", jose_intervals + all_intervals, 17x, 24, 25)
    # michael = Bird("Michael", michael_intervals + all_intervals, 18x, 22, 23)
    # pierre = Bird("Pierre", pierre_intervals + all_intervals, 19x, 18, 27)
    # fritz = Bird("Fritz", fritz_intervals + all_intervals, 20x, 4, 17)

    pierre = Bird("Pierre", pierre_intervals + all_intervals, 17, 21, 26, 10)
    jose = Bird("Jose", jose_intervals + all_intervals, 22, 24, 23, 9)
    michael = Bird("Michael", michael_intervals + all_intervals, 19, 27, 5, 11)
    fritz = Bird("Fritz", fritz_intervals + all_intervals, 20, 6, 13, 0)

    birds = [pierre, jose, michael, fritz]
    PIR = MotionSensor(4)
    while True:
        PIR.wait_for_motion()
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

            
        audio_path = "EnchantedTikiRoom_Old/BJB_TR_InTRoomSong.final.mp3"
        play_audio_with_speech_indicator(audio_path, birds)