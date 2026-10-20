"""Local, opt-in OpenCV YuNet/SFace recognition. No network or identity guesses."""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
DETECTOR = BASE / 'models' / 'face_detection_yunet_2023mar.onnx'
RECOGNIZER = BASE / 'models' / 'face_recognition_sface_2021dec.onnx'
IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,48}$')


def validate_person_id(value):
    if not ID_PATTERN.fullmatch(value):
        raise ValueError('Person directory names must use letters, numbers, _ or - (max 48)')
    return value


def models_ready():
    return DETECTOR.is_file() and RECOGNIZER.is_file() and DETECTOR.stat().st_size > 100_000 and RECOGNIZER.stat().st_size > 1_000_000


class FaceEngine:
    def __init__(self, score_threshold=0.9, match_threshold=0.42):
        if not models_ready():
            raise RuntimeError('Face models missing. Run: ./vision/install_vision.sh')
        import cv2
        self.cv2 = cv2
        self.detector = cv2.FaceDetectorYN.create(str(DETECTOR), '', (320, 320), score_threshold)
        self.recognizer = cv2.FaceRecognizerSF.create(str(RECOGNIZER), '')
        self.match_threshold = match_threshold  # conservative starting point; calibrate on own data

    def faces(self, bgr):
        h, w = bgr.shape[:2]
        self.detector.setInputSize((w, h))
        _, detections = self.detector.detect(bgr)
        return [] if detections is None else list(detections)

    def embedding(self, image, face):
        aligned = self.recognizer.alignCrop(image, face)
        return self.recognizer.feature(aligned).flatten().astype('float32')

    def best_match(self, feature, gallery):
        import numpy as np
        scores = []
        for pid, info in gallery.items():
            for entry in info['embeddings']:
                candidate = np.asarray(entry, dtype='float32')
                score = float(self.recognizer.match(feature.reshape(1, -1), candidate.reshape(1, -1), self.cv2.FaceRecognizerSF_FR_COSINE))
                scores.append((score, pid))
        if not scores:
            return {'person_id': None, 'similarity': None, 'recognized': False}
        scores.sort(reverse=True)
        score, pid = scores[0]
        # Require separation from the strongest different-identity match.
        other = next((s for s, name in scores if name != pid), None)
        recognized = score >= self.match_threshold and (other is None or score - other >= 0.06)
        return {'person_id': pid if recognized else None, 'similarity': round(score, 4), 'recognized': recognized}


def load_gallery(path):
    path = Path(path)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding='utf-8'))
    if raw.get('version') != 1 or not isinstance(raw.get('people'), dict):
        raise ValueError('Invalid face gallery format')
    return raw['people']


def enroll_folder(engine, source, output, *, consent_required=True):
    """Build from image folders. Only opted-in profiles are included."""
    source, output = Path(source), Path(output)
    if not source.is_dir():
        raise FileNotFoundError(source)
    people, issues = {}, []
    for folder in sorted(x for x in source.iterdir() if x.is_dir() and not x.is_symlink()):
        try:
            pid = validate_person_id(folder.name)
        except ValueError as exc:
            issues.append(f'{folder.name}: {exc}')
            continue
        metadata_file = folder / 'profile.json'
        if not metadata_file.is_file():
            issues.append(f'{pid}: missing profile.json, skipped')
            continue
        profile = json.loads(metadata_file.read_text(encoding='utf-8'))
        if consent_required and profile.get('consent_to_recognition') is not True:
            issues.append(f'{pid}: consent_to_recognition not true, skipped')
            continue
        embeddings = []
        for image_file in sorted(folder.iterdir()):
            if image_file.is_symlink() or image_file.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            image = engine.cv2.imread(str(image_file))
            if image is None:
                issues.append(f'{pid}/{image_file.name}: cannot read image')
                continue
            faces = engine.faces(image)
            if len(faces) != 1:
                issues.append(f'{pid}/{image_file.name}: found {len(faces)} faces (need exactly 1)')
                continue
            embeddings.append(engine.embedding(image, faces[0]).tolist())
        if embeddings:
            people[pid] = {'display_name': str(profile.get('display_name', pid))[:70], 'embeddings': embeddings}
        else:
            issues.append(f'{pid}: no usable single-face photos')
    # Atomic replacement; never write partial JSON on an error.
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + '.tmp')
    tmp.write_text(json.dumps({'version': 1, 'people': people}, indent=2), encoding='utf-8')
    tmp.replace(output)
    return {'enrolled': {pid: len(info['embeddings']) for pid, info in people.items()}, 'warnings': issues, 'gallery': str(output)}


def recognize_image(engine, image_path, gallery):
    image = engine.cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f'Cannot read image: {image_path}')
    results = []
    for face in engine.faces(image):
        x, y, w, h = [int(v) for v in face[:4]]
        result = engine.best_match(engine.embedding(image, face), gallery)
        result['bbox'] = [x, y, w, h]
        if result['person_id']:
            result['display_name'] = gallery[result['person_id']]['display_name']
        results.append(result)
    return results
