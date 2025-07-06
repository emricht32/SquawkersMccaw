# src/birdpi_node/main.py

from flask import Flask, request, jsonify
import time
import threading
import socket
import os
import json
from pathlib import Path
from common.bird import Bird, manage_leds
from register import register_bird
try:
    from gpiozero import LED
    GPIO_AVAILABLE = True
except ImportError:
    print("GPIO not available")
    GPIO_AVAILABLE = False

app = Flask(__name__)

CONFIG_FILES = [
    "/Volumes/BIRDPI/config_single_bird.json",  # Highest priority
    "config_single_bird_jose.json",
    "config_single_bird_michael.json",
    "config_single_bird_fritz.json",
    "config_single_bird_pierre.json"
]

BIRD_NAME_FILE = "/tmp/bird_name"

def load_config():
    for path in CONFIG_FILES:
        file = Path(path)
        if file.exists():
            with open(file, "r") as f:
                print(f"Loaded config from {path}")
                return json.load(f)
    raise FileNotFoundError("No valid config_single_bird JSON file found.")

# Load config
config = load_config()
if GPIO_AVAILABLE:
    STATUS_LIGHT = LED(config["on_light"])
# Determine bird name (priority: saved name > config > hostname)
if Path(BIRD_NAME_FILE).exists():
    with open(BIRD_NAME_FILE) as f:
        BIRD_NAME = f.read().strip()
else:
    BIRD_NAME = config.get("name") or socket.gethostname()

# GPIO pin mappings from config
BEAK_PIN = config.get("beak")
BODY_PIN = config.get("body")
SPOTLIGHT_PIN = config.get("light")
ON_TIME = config.get("on_time", 0.05)  # Use default if not present

DEFAULT_ON_TIME = ON_TIME  # if your `oscillate_led` uses this global

# Create bird instance
bird_instance = Bird(
    name=BIRD_NAME,
    beak_led_pin=BEAK_PIN,
    body_led_pin=BODY_PIN,
    spotlight_led_pin=SPOTLIGHT_PIN
)

@app.route("/perform", methods=["POST"])
def perform():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    start_time = data.get("start_time")
    if start_time is None:
        return jsonify({"error": "Missing start_time"}), 400

    bird_instance.prepare_song(data)

    delay = start_time - time.time()
    if delay < 0:
        delay = 0

    threading.Timer(delay, lambda: manage_leds([bird_instance], ON_TIME)).start()

    return jsonify({
        "status": "scheduled",
        "start_time": start_time,
        "delay": delay,
        "bird": BIRD_NAME
    }), 200

@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "status":"success"
    }), 200

def didRegister(name: str):
    global BIRD_NAME, bird_instance 
    if name is not BIRD_NAME:
        BIRD_NAME = name
        bird_instance.name = name
        blink(5)
    STATUS_LIGHT.on()

def blink(count: int):
    for _ in range(count):
        STATUS_LIGHT.on()
        time.sleep(1)
        STATUS_LIGHT.off()
        time.sleep(1)

if __name__ == "__main__":
    try:
        register_bird(requested_name=BIRD_NAME,completion=didRegister)
        app.run(host="0.0.0.0", port=5001)
    except:
        exit(0)
    finally:
        if STATUS_LIGHT is not None:
            STATUS_LIGHT.off()

