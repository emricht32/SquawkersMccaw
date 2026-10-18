import json
import logging
import os
import queue
import subprocess
import tempfile
import threading
import time
import wave

import numpy as np

log = logging.getLogger("roast.speech")

SAMPLE_RATE = 16000


class Listener(threading.Thread):
    """Streams mic audio (arecord) into Vosk and posts ("speech", text) events."""

    def __init__(self, stt_cfg: dict, events: queue.Queue):
        super().__init__(daemon=True, name="listener")
        self.model_path = stt_cfg["vosk_model"]
        self.device = stt_cfg.get("device", "default")
        self.min_chars = int(stt_cfg.get("min_chars", 3))
        self.ignore = {w.lower() for w in stt_cfg.get("ignore_phrases", ["the", "huh", "uh", "um"])}
        self.events = events
        self._muted = threading.Event()
        self._reset = False

    def mute(self):
        """Stop transcribing (e.g. while the bird is thinking/talking so it can't hear itself)."""
        self._muted.set()

    def unmute(self):
        self._reset = True
        self._muted.clear()

    def run(self):
        from vosk import KaldiRecognizer, Model, SetLogLevel

        SetLogLevel(-1)
        rec = KaldiRecognizer(Model(self.model_path), SAMPLE_RATE)
        cmd = ["arecord", "-D", self.device, "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1", "-t", "raw", "-q"]
        while True:
            log.info("Starting mic capture: %s", " ".join(cmd))
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            try:
                while True:
                    data = proc.stdout.read(4000)
                    if not data:
                        break
                    if self._muted.is_set():
                        continue
                    if self._reset:
                        rec.Reset()
                        self._reset = False
                    if rec.AcceptWaveform(data):
                        text = json.loads(rec.Result()).get("text", "").strip()
                        if len(text) >= self.min_chars and text.lower() not in self.ignore:
                            log.info("STT: %r", text)
                            self.events.put(("speech", text))
            except Exception as e:
                log.error("Listener error: %s", e)
            finally:
                proc.kill()
            log.warning("Mic capture ended; restarting in 2s")
            time.sleep(2)


def mouth_envelope(wav_path: str, frame_s: float, open_ratio: float) -> list[bool]:
    """Per-frame open/closed beak states from the loudness of a 16-bit wav."""
    with wave.open(wav_path, "rb") as w:
        rate = w.getframerate()
        channels = w.getnchannels()
        raw = w.readframes(w.getnframes())
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    hop = max(1, int(rate * frame_s))
    n = len(samples) // hop
    if n == 0:
        return []
    rms = np.sqrt((samples[: n * hop].reshape(n, hop) ** 2).mean(axis=1))
    peak = float(rms.max()) or 1.0
    return (rms > peak * open_ratio).tolist()


class Speaker:
    """Piper TTS -> aplay, with beak flapping synced to the audio envelope."""

    def __init__(self, tts_cfg: dict, body, listener: Listener | None):
        self.piper_bin = tts_cfg.get("piper_bin", "piper")
        self.voice = tts_cfg["voice"]
        self.extra_args = [str(a) for a in tts_cfg.get("piper_args", [])]
        self.device = tts_cfg.get("playback_device", "default")
        self.frame_s = float(tts_cfg.get("beak_frame_ms", 100)) / 1000.0
        self.open_ratio = float(tts_cfg.get("beak_open_ratio", 0.2))
        self.body = body
        self.listener = listener

    def say(self, text: str):
        fd, wav_path = tempfile.mkstemp(suffix=".wav", prefix="roast_")
        os.close(fd)
        try:
            subprocess.run(
                [self.piper_bin, "--model", self.voice, "--output_file", wav_path, *self.extra_args],
                input=text.encode("utf-8"),
                capture_output=True,
                check=True,
                timeout=60,
            )
            envelope = mouth_envelope(wav_path, self.frame_s, self.open_ratio)
            if self.listener:
                self.listener.mute()
            player = subprocess.Popen(["aplay", "-q", "-D", self.device, wav_path])
            self.body.animate_beak(envelope, self.frame_s, player)
            player.wait(timeout=120)
        except Exception as e:
            log.error("TTS/playback failed: %s", e)
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass
            if self.listener:
                time.sleep(0.3)  # let the room echo die before listening again
                self.listener.unmute()
