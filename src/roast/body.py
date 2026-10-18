import logging
import time

log = logging.getLogger("roast.body")

try:
    from gpiozero import LED
except ImportError:
    LED = None


def _make_led(pin):
    if LED is None or pin is None:
        return None
    try:
        return LED(pin)
    except Exception as e:
        log.warning("Could not open GPIO %s: %s", pin, e)
        return None


class BirdBody:
    """Beak / body / spotlight outputs. Degrades to no-ops without gpiozero."""

    def __init__(self, pins: dict):
        self.beak = _make_led(pins.get("beak"))
        self.body = _make_led(pins.get("body"))
        lights = pins.get("lights", pins.get("light"))
        if lights is None:
            lights = []
        elif not isinstance(lights, (list, tuple)):
            lights = [lights]
        self.lights = [led for led in (_make_led(p) for p in lights) if led]
        log.info("BirdBody beak=%s body=%s lights=%s", self.beak, self.body, self.lights)

    def set_lights(self, on: bool):
        for led in self.lights:
            led.on() if on else led.off()

    def animate_beak(self, mouth_open: list[bool], frame_s: float, player):
        """Flap the beak following a precomputed open/closed envelope while `player` runs."""
        if self.body:
            self.body.on()
        start = time.monotonic()
        try:
            while player.poll() is None:
                i = int((time.monotonic() - start) / frame_s)
                if i >= len(mouth_open):
                    break
                if self.beak:
                    self.beak.on() if mouth_open[i] else self.beak.off()
                time.sleep(frame_s / 2)
        finally:
            if self.beak:
                self.beak.off()
            if self.body:
                self.body.off()
