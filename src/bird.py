import time
import threading
import random

try:
    from gpiozero import LED, Motor
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

class Bird:
    def __init__(self, name, beak_led_pin, eyes_led_pin, body_led_pin, spotlight_led_pin):
        print("Bird", name, beak_led_pin, eyes_led_pin, body_led_pin, spotlight_led_pin)
        self.name = name
        self.speech_intervals = []
        self.dancing_intervals = []
        # self.beak_led = LED(beak_led_pin) if GPIO_AVAILABLE else None
        # self.eyes_led = LED(eyes_led_pin) if GPIO_AVAILABLE else None
        self.head = Motor(forward=beak_led_pin, backward=eyes_led_pin)
        self.body_led = LED(body_led_pin) if GPIO_AVAILABLE else None
        self.spotlight_led = LED(spotlight_led_pin) if GPIO_AVAILABLE else None
        if self.spotlight_led is not None:
            self.spotlight_led.on()
        self.event = threading.Event()

    def prepare_song(self, song_dict):
        print("prepare_song")
        individual= [individual for individual in song_dict["individuals"] if individual["name"] == self.name][0]
        print("individual=",individual)
        speech_intervals = individual["singing"]
        dancing_intervals = individual["dancing"]
        speech_intervals += song_dict["all_singing"]
        dancing_intervals += song_dict["all_dancing"]
        self.speech_intervals = speech_intervals
        self.dancing_intervals = dancing_intervals

    def is_speaking(self, curr_time):
        return any(start <= curr_time <= end for start, end in self.speech_intervals)
    
    def is_dancing(self, curr_time):
        return any(start <= curr_time <= end for start, end in self.dancing_intervals)

    def start_moving(self, duration):
        if self.event.is_set():
            return
        self.event.set()
        self.start_dancing()

        if self.head:
            threading.Thread(target=oscillate_led, args=(self.event, duration, self.head)).start()
        else:
            threading.Thread(target=oscillate_logs, args=(self.event, duration, self.name)).start()
        
    def start_dancing(self):
        if self.spotlight_led:
            self.spotlight_led.off() #spotlight is reversed 
        # else:
        #     print(f"{self.name} Spotlight ON")
        if self.body_led:
            self.body_led.on() 
        #     print(f"{self.name} Body ON")
        # else:
        #     print(f"{self.name} Body ON")

    def stop_moving(self):
        self.event.clear()
        if self.spotlight_led:
            self.spotlight_led.on() #reversed
        # else:
            # print(f"{self.name} Spotlight OFF")
        if self.body_led:
            self.body_led.off()
            # print(f"{self.name} Body OFF")
        # else:
            # print(f"{self.name} Body OFF")
        if self.head:
            self.head.stop()
            
def oscillate_led(event, duration, head):
    on_time = 0.025
    off_time = duration - on_time
    while event.is_set():
        head.forward()
        time.sleep(on_time)
        head.stop()

        random_number = random.randint(1, 20)
        if random_number > 16:
            head.backward()
            time.sleep(1)
            head.stop()

        # led.off()
        time.sleep(off_time)

def oscillate_logs(event, duration, name):
    while event.is_set():
        print(f"{name} LED ON")
        time.sleep(duration/2)
        print(f"{name} LED OFF")
        time.sleep(duration/2)