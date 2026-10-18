"""Presence detection on the Raspberry Pi AI Camera (IMX500) + optional face ID on the CPU.

The IMX500 runs an object-detection network on-sensor, so the Pi only receives
bounding boxes. We watch for the "person" class to decide when someone walks up
or leaves. Only once per arrival do we grab a frame and run YuNet + SFace
(OpenCV) on the CPU to put a name to the face.
"""
import logging
import os
import queue
import re
import threading
import time

import numpy as np

log = logging.getLogger("roast.vision")

DEFAULT_IMX500_MODEL = "/usr/share/imx500-models/imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk"
COCO_PERSON_CLASS = 0
FRAME_SIZE = (640, 480)


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 _-]", "", name).strip()
    if not cleaned:
        raise ValueError(f"Invalid person name: {name!r}")
    return cleaned


class FaceIdentifier:
    def __init__(self, rec_cfg: dict, base_dir: str):
        import cv2

        self.cv2 = cv2
        self.faces_dir = os.path.join(base_dir, rec_cfg.get("faces_dir", "faces"))
        self.threshold = float(rec_cfg.get("match_threshold", 0.363))
        self.detector = cv2.FaceDetectorYN.create(rec_cfg["yunet_model"], "", (320, 320), 0.8)
        self.recognizer = cv2.FaceRecognizerSF.create(rec_cfg["sface_model"], "")
        self.known: dict[str, np.ndarray] = {}
        self.reload()

    def reload(self):
        self.known = {}
        if not os.path.isdir(self.faces_dir):
            return
        for fname in os.listdir(self.faces_dir):
            if fname.endswith(".npy"):
                self.known[fname[:-4]] = np.load(os.path.join(self.faces_dir, fname))
        log.info("Loaded %d known faces: %s", len(self.known), sorted(self.known))

    def embed(self, bgr: np.ndarray) -> np.ndarray | None:
        h, w = bgr.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(bgr)
        if faces is None or len(faces) == 0:
            return None
        face = max(faces, key=lambda f: f[2] * f[3])
        aligned = self.recognizer.alignCrop(bgr, face)
        return self.recognizer.feature(aligned)

    def identify(self, bgr: np.ndarray) -> tuple[bool, str | None]:
        """Returns (face_found, name_or_None)."""
        feat = self.embed(bgr)
        if feat is None:
            return False, None
        best_name, best_score = None, self.threshold
        for name, samples in self.known.items():
            for sample in samples:
                score = self.recognizer.match(
                    feat, sample.reshape(1, -1), self.cv2.FaceRecognizerSF_FR_COSINE
                )
                if score > best_score:
                    best_name, best_score = name, score
        log.info("Face identified as %s (score=%.3f)", best_name, best_score)
        return True, best_name

    def save(self, name: str, feats: list[np.ndarray]):
        os.makedirs(self.faces_dir, exist_ok=True)
        path = os.path.join(self.faces_dir, f"{_safe_name(name)}.npy")
        np.save(path, np.vstack(feats))
        log.info("Saved %d face samples to %s", len(feats), path)


class PersonWatcher(threading.Thread):
    """Posts ("arrive", name_or_None) and ("leave", None) events."""

    def __init__(self, vision_cfg: dict, events: queue.Queue, identifier: FaceIdentifier | None):
        super().__init__(daemon=True, name="vision")
        self.model = vision_cfg.get("imx500_model", DEFAULT_IMX500_MODEL)
        self.threshold = float(vision_cfg.get("person_threshold", 0.55))
        self.frames_to_confirm = int(vision_cfg.get("frames_to_confirm", 3))
        self.frames_to_leave = int(vision_cfg.get("frames_to_leave", 20))
        self.face_attempts = int(vision_cfg.get("face_attempts", 15))
        self.events = events
        self.identifier = identifier

    def _count_people(self, imx500, metadata) -> int | None:
        outputs = imx500.get_outputs(metadata, add_batch=True)
        if outputs is None:
            return None  # no fresh inference on this frame
        scores, classes = outputs[1][0], outputs[2][0]
        return int(np.sum((classes.astype(int) == COCO_PERSON_CLASS) & (scores >= self.threshold)))

    def run(self):
        try:
            self._run()
        except Exception as e:
            log.exception("Vision thread died: %s", e)

    def _run(self):
        from picamera2 import Picamera2
        from picamera2.devices import IMX500
        from picamera2.devices.imx500 import NetworkIntrinsics

        imx500 = IMX500(self.model)
        intrinsics = imx500.network_intrinsics
        if not intrinsics:
            intrinsics = NetworkIntrinsics()
            intrinsics.task = "object detection"
        intrinsics.update_with_defaults()

        picam2 = Picamera2(imx500.camera_num)
        config = picam2.create_preview_configuration(
            main={"format": "RGB888", "size": FRAME_SIZE},
            controls={"FrameRate": intrinsics.inference_rate},
            buffer_count=12,
        )
        log.info("Loading IMX500 network %s (first boot can take a minute)", self.model)
        picam2.start(config)
        if intrinsics.preserve_aspect_ratio:
            imx500.set_auto_aspect_ratio()

        present = False
        seen, unseen = 0, 0
        while True:
            request = picam2.capture_request()
            try:
                count = self._count_people(imx500, request.get_metadata())
            finally:
                request.release()
            if count is None:
                continue

            if count > 0:
                seen, unseen = seen + 1, 0
            else:
                seen, unseen = 0, unseen + 1

            if not present and seen >= self.frames_to_confirm:
                present = True
                name = self._identify(picam2)
                log.info("Person arrived (name=%s)", name)
                self.events.put(("arrive", name))
            elif present and unseen >= self.frames_to_leave:
                present = False
                log.info("Person left")
                self.events.put(("leave", None))

    def _identify(self, picam2) -> str | None:
        if not self.identifier:
            return None
        for _ in range(self.face_attempts):
            frame = picam2.capture_array("main")  # RGB888 is BGR-ordered, as OpenCV expects
            found, name = self.identifier.identify(frame)
            if found:
                return name
        return None


def enroll(vision_cfg: dict, base_dir: str, name: str, samples: int):
    """Capture `samples` face embeddings for `name`. The daemon must be stopped (camera is exclusive)."""
    from picamera2 import Picamera2

    identifier = FaceIdentifier(vision_cfg["recognition"], base_dir)
    picam2 = Picamera2()
    picam2.configure(picam2.create_preview_configuration(main={"format": "RGB888", "size": FRAME_SIZE}))
    picam2.start()
    feats: list[np.ndarray] = []
    print(f"Look at the camera, {name}. Move your head a little between samples.")
    try:
        while len(feats) < samples:
            feat = identifier.embed(picam2.capture_array("main"))
            if feat is not None:
                feats.append(feat)
                print(f"  captured {len(feats)}/{samples}")
                time.sleep(0.7)
    finally:
        picam2.stop()
    identifier.save(name, feats)
