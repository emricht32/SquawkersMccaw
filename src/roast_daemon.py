#!/usr/bin/env python3
"""
roast_daemon.py - Roast Master mode for a single bird.

Pipeline:
  IMX500 AI Camera (person detect, on-sensor) -> optional face ID (OpenCV SFace)
  -> LLM roast via Ollama -> Piper TTS + beak sync -> Vosk STT for comebacks.

Usage:
  python3 src/roast_daemon.py                       # run the bird
  python3 src/roast_daemon.py --console             # type instead of talk (no mic/camera/GPIO audio)
  python3 src/roast_daemon.py --enroll "Jonathan"   # teach it a face (stop the daemon first)
"""
import argparse
import json
import logging
import os
import queue
import socket
import sys
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from roast.body import BirdBody  # noqa: E402
from roast.brain import RoastBrain  # noqa: E402

log = logging.getLogger("roast")

SCENE_SILENT = "[SCENE: They have gone quiet and won't talk back. Mock them for it in one line and say goodbye.]"
SCENE_LEAVING = "[SCENE: They are walking away. Give them a one-line parting shot.]"


def bird_name_from_host() -> str:
    host = socket.gethostname().split(".")[0]
    return host[len("birdpi-"):].capitalize() if host.startswith("birdpi-") else "Jose"


class ConsoleSpeaker:
    """Prints replies instead of speaking; used with --console for persona tuning."""

    def say(self, text: str):
        print(f"\nPARROT: {text}\n> ", end="", flush=True)


def stdin_reader(events: queue.Queue):
    print("Console mode. Type to talk, '/arrive Name' or '/arrive' to simulate a visitor, '/leave' to walk off.")
    print("> ", end="", flush=True)
    for line in sys.stdin:
        line = line.strip()
        if line == "/leave":
            events.put(("leave", None))
        elif line.startswith("/arrive"):
            events.put(("arrive", line[len("/arrive"):].strip() or None))
        elif line:
            events.put(("speech", line))


class RoastMaster:
    def __init__(self, cfg: dict, events: queue.Queue, brain: RoastBrain, speaker, body: BirdBody, listener):
        self.events = events
        self.brain = brain
        self.speaker = speaker
        self.body = body
        self.listener = listener
        self.cooldown = float(cfg.get("cooldown_seconds", 20))
        self.idle_timeout = float(cfg.get("conversation_idle_timeout", 15))
        self.max_turns = int(cfg.get("max_turns", 12))

    def _respond(self, prompt: str):
        if self.listener:
            self.listener.mute()
        self.speaker.say(self.brain.respond(prompt))

    def converse(self, kind: str, payload):
        self.body.set_lights(True)
        self.brain.new_conversation()
        prompt = self.brain.arrival_prompt(payload) if kind == "arrive" else payload
        try:
            for _ in range(self.max_turns):
                self._respond(prompt)
                try:
                    kind, payload = self.events.get(timeout=self.idle_timeout)
                except queue.Empty:
                    self._respond(SCENE_SILENT)
                    return
                if kind == "leave":
                    self._respond(SCENE_LEAVING)
                    return
                # A new "arrive" mid-conversation is just more audience; keep roasting.
                prompt = payload if kind == "speech" else self.brain.arrival_prompt(payload)
        finally:
            self.body.set_lights(False)

    def run(self):
        last_end = 0.0
        while True:
            kind, payload = self.events.get()
            if kind == "leave":
                continue
            if kind == "arrive" and time.monotonic() - last_end < self.cooldown:
                log.info("Arrival ignored (cooldown)")
                continue
            self.converse(kind, payload)
            last_end = time.monotonic()


def main():
    parser = argparse.ArgumentParser(description="Roast Master parrot")
    parser.add_argument("--config", default=os.path.join(REPO_DIR, "config_roast_bird.json"))
    parser.add_argument("--console", action="store_true", help="Text in/out only; for tuning the persona")
    parser.add_argument("--no-vision", action="store_true", help="Run without the AI camera")
    parser.add_argument("--enroll", metavar="NAME", help="Capture face samples for NAME and exit")
    parser.add_argument("--samples", type=int, default=5)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(name)s %(levelname)s: %(message)s")

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    os.chdir(REPO_DIR)  # model paths in the config are relative to the repo

    if args.enroll:
        from roast.vision import enroll

        enroll(cfg["vision"], REPO_DIR, args.enroll, args.samples)
        return

    events: queue.Queue = queue.Queue()
    body = BirdBody(cfg.get("pins", {}))
    brain = RoastBrain(cfg["llm"], cfg["persona"], cfg.get("name") or bird_name_from_host(), cfg.get("roast_notes", {}))
    threading.Thread(target=brain.warm_up, daemon=True).start()

    if args.console:
        listener = None
        speaker = ConsoleSpeaker()
        threading.Thread(target=stdin_reader, args=(events,), daemon=True).start()
    else:
        from roast.speech import Listener, Speaker

        listener = Listener(cfg["stt"], events)
        listener.start()
        speaker = Speaker(cfg["tts"], body, listener)

        vision_cfg = cfg.get("vision", {})
        if vision_cfg.get("enabled", True) and not args.no_vision:
            from roast.vision import FaceIdentifier, PersonWatcher

            identifier = None
            rec_cfg = vision_cfg.get("recognition", {})
            if rec_cfg.get("enabled", False):
                identifier = FaceIdentifier(rec_cfg, REPO_DIR)
            PersonWatcher(vision_cfg, events, identifier).start()

    log.info("Roast Master ready")
    try:
        RoastMaster(cfg, events, brain, speaker, body, listener).run()
    except KeyboardInterrupt:
        log.info("Interrupted")


if __name__ == "__main__":
    main()
