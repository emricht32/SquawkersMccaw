import time
import threading
try:
    from gpiozero import LED
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

class Bird:
    def __init__(self, name, beak_led_pin, body_led_pin, spotlight_led_pin):
        print("Bird", name, beak_led_pin, body_led_pin, spotlight_led_pin)
        self.name = name
        self.speech_intervals = []
        self.dancing_intervals = []
        self.beak_led = LED(beak_led_pin) if GPIO_AVAILABLE else None
        self.body_led = LED(body_led_pin) if GPIO_AVAILABLE else None
        self.spotlight_led = LED(spotlight_led_pin) if GPIO_AVAILABLE else None
        if self.spotlight_led is not None:
            self.spotlight_led.on()
        self.event = threading.Event()

    def prepare_song(self, song_dict):
        print("prepare_song")
        if song_dict.get("individuals") is not None:
            individual = [individual for individual in song_dict["individuals"] if individual["name"] == self.name][0]
        else:
            # just passing singing and dancing for bird nodes
            individual = song_dict 
        print("individual=",individual)
        speech_intervals = individual.get("singing", [])
        dancing_intervals = individual.get("dancing", [])
        speech_intervals += song_dict.get("all_singing", [])
        dancing_intervals += song_dict.get("all_dancing", [])
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

        if self.beak_led:
            threading.Thread(target=oscillate_led, args=(self.event, duration, self.beak_led)).start()
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
        if self.beak_led:
            self.beak_led.off()
            
def oscillate_led(event, duration, led):
    on_time = 0.01
    off_time = duration - on_time
    while event.is_set():
        led.on()
        time.sleep(on_time)
        led.off()
        time.sleep(off_time)

def oscillate_logs(event, duration, name):
    while event.is_set():
        print(f"{name} LED ON")
        time.sleep(duration/2)
        print(f"{name} LED OFF")
        time.sleep(duration/2)

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