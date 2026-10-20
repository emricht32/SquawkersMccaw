"""Headless browser preview, anonymized tracking, and JSON endpoint.
No automatic names, jokes, face retention, or network exposure by default.
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HTML = '''<!doctype html><html lang="en"><meta charset="utf-8"><title>BirdPi Vision Preview</title>
<style>body{background:#101820;color:#f1f5f9;font:16px system-ui;margin:3vw}img{max-width:100%;border-radius:12px}pre{white-space:pre-wrap;background:#1d2935;padding:1em;border-radius:12px} .hint{color:#9fb1c3}</style>
<h1>BirdPi Vision · Preview Mode</h1><p class="hint">Local-only. Recognition is tentative and no names are spoken. No photos are saved by the preview.</p>
<img id="frame" alt="Live camera preview"><h2>Latest detections</h2><pre id="result">Starting camera…</pre>
<script>setInterval(()=>{document.getElementById('frame').src='/frame.jpg?t='+Date.now();fetch('/api/vision/people').then(r=>r.json()).then(j=>document.getElementById('result').textContent=JSON.stringify(j,null,2)).catch(e=>document.getElementById('result').textContent=e.message)},700)</script></html>'''


def serve(engine, gallery_path, host='127.0.0.1', port=8090, fps=3):
    from picamera2 import Picamera2
    import cv2
    if fps <= 0 or fps > 10:
        raise ValueError('fps must be between 0 and 10')
    camera = Picamera2()
    camera.configure(camera.create_preview_configuration(main={'size': (960, 540), 'format': 'RGB888'}))
    camera.start()
    gallery = {}
    gallery_mtime = None
    state = {'timestamp': None, 'people': [], 'audience_count': 0, 'preview_only': True, 'source': 'camera', 'visual_tags_available': False}
    jpeg = b''
    lock = threading.Lock()
    tracker = {}
    next_id = 1
    stop = threading.Event()

    def loop():
        nonlocal jpeg, gallery, gallery_mtime, next_id
        while not stop.is_set():
            started = time.monotonic()
            try:
                path = Path(gallery_path)
                mtime = path.stat().st_mtime_ns if path.is_file() else None
                if mtime != gallery_mtime:
                    gallery = load_gallery(path)
                    gallery_mtime = mtime
                frame = camera.capture_array()
                # RGB888 Picamera2 format as observed by OpenCV is usually BGR for these capture APIs.
                faces = engine.faces(frame)
                seen = set()
                people = []
                for face in faces:
                    x, y, w, h = [int(i) for i in face[:4]]
                    cx, cy = x + w / 2, y + h / 2
                    choices = sorted((abs(cx - t['cx']) + abs(cy - t['cy']), tid) for tid,t in tracker.items() if tid not in seen and started - t['seen'] < 2.5)
                    if choices and choices[0][0] < max(w, h) * 0.65:
                        tid = choices[0][1]
                    else:
                        tid = f'guest_{next_id:04d}'
                        next_id += 1
                    tracker[tid] = {'cx': cx, 'cy': cy, 'seen': started}
                    seen.add(tid)
                    guess = engine.best_match(engine.embedding(frame, face), gallery)
                    label = gallery[guess['person_id']]['display_name'] if guess['recognized'] else 'Unknown'
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (50, 220, 120), 2)
                    cv2.putText(frame, f'{tid} | {label} [preview]', (x, max(22,y-8)), cv2.FONT_HERSHEY_SIMPLEX, .55, (50,220,120),2)
                    people.append({'track_id': tid, 'person_id': guess['person_id'], 'display_name': label if guess['recognized'] else None, 'similarity': guess['similarity'], 'bbox': [x,y,w,h], 'tags': {}, 'recognition_preview': True})
                tracker = {k:v for k,v in tracker.items() if started - v['seen'] < 2.5}
                ok, compressed = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
                if ok:
                    with lock:
                        jpeg = compressed.tobytes()
                        state.update({'timestamp': time.time(), 'people': people, 'audience_count': len(people)})
            except Exception as exc:
                with lock:
                    state['error'] = str(exc)
            stop.wait(max(0.02, 1/fps - (time.monotonic()-started)))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            route = urlparse(self.path).path
            if route == '/':
                body, mime = HTML.encode(), 'text/html; charset=utf-8'
            elif route == '/api/vision/people':
                with lock:
                    body = json.dumps(state).encode()
                mime = 'application/json'
            elif route == '/frame.jpg':
                with lock:
                    body = jpeg
                mime = 'image/jpeg'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    print(f'BirdPi vision at http://{host}:{port} (preview only; Ctrl+C to stop)', flush=True)
    try:
        ThreadingHTTPServer((host, port), Handler).serve_forever()
    finally:
        stop.set()
        thread.join(timeout=2)
        camera.stop()
