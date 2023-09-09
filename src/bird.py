import time
import threading
try:
    from gpiozero import LED
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

class Bird:
    # jose = Bird("Jose", jose_intervals + all_intervals, 17, 21, 23)
    # michael = Bird("Michael", michael_intervals + all_intervals, 18, 24, 26)
    # pierre = Bird("Pierre", pierre_intervals + all_intervals, 19, 27, 5)
    # fritz = Bird("Fritz", fritz_intervals + all_intervals, 20, 6, 13)
    def __init__(self, name, speech_intervals, dancing_intervals, beak_led_pin, body_led_pin, spotlight_led_pin, speaker_led_pin):
        self.name = name
        self.speech_intervals = speech_intervals
        self.dancing_intervals = dancing_intervals
        self.beak_led = LED(beak_led_pin) if GPIO_AVAILABLE else None
        self.body_led = LED(body_led_pin) if GPIO_AVAILABLE else None
        self.spotlight_led = LED(spotlight_led_pin) if GPIO_AVAILABLE else None
        self.spotlight_led.on()
        self.speeker_led = LED(speaker_led_pin) if GPIO_AVAILABLE else None

        self.event = threading.Event()

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
        if self.speeker_led:
            self.speeker_led.on() 
        else:
            print(f"{self.name} Speaker ON")
        
    def start_dancing(self):
        if self.spotlight_led:
            self.spotlight_led.off() #spotlight is reversed 
        else:
            print(f"{self.name} Spotlight ON")
        if self.body_led:
            self.body_led.on() 
        else:
            print(f"{self.name} Body ON")

    def stop_moving(self):
        # if not self.event.is_set():
        #     return
        self.event.clear()
        if self.spotlight_led:
            self.spotlight_led.on() #reversed
        else:
            print(f"{self.name} Spotlight OFF")
        if self.body_led:
            self.body_led.off()
        else:
            print(f"{self.name} Body ON")
        if self.speeker_led:
            self.speeker_led.off() 
        else:
            print(f"{self.name} Body ON")
            
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