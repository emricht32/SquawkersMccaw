#!/usr/bin/env python3
"""Recognition development CLI. Uses system Python with Picamera2/OpenCV."""
import argparse
import json
import time
from pathlib import Path
from recognition import FaceEngine, enroll_folder, load_gallery, recognize_image

ROOT = Path(__file__).resolve().parent.parent

def main():
    p = argparse.ArgumentParser(description='BirdPi opt-in face recognition preview')
    p.add_argument('--friends', default=str(ROOT / 'friends'))
    p.add_argument('--gallery', default=str(ROOT / 'vision' / 'gallery.json'))
    p.add_argument('--threshold', type=float, default=0.42, help='Candidate cosine threshold; calibrate before announcements')
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('enroll', help='Build gallery from consented photo directories')
    r = sub.add_parser('recognize', help='Identify faces in a saved image')
    r.add_argument('image')
    c = sub.add_parser('capture', help='Capture one camera image for inspection or enrollment')
    c.add_argument('--output', default=str(ROOT / 'vision' / 'capture.jpg'))
    l = sub.add_parser('live', help='Run camera and local preview API on 127.0.0.1:8090')
    l.add_argument('--host', default='127.0.0.1')
    l.add_argument('--port', type=int, default=8090)
    l.add_argument('--fps', type=float, default=3)
    args = p.parse_args()
    if args.command == 'capture':
        from picamera2 import Picamera2
        camera = Picamera2()
        camera.configure(camera.create_still_configuration(main={'size': (1280, 720)}))
        camera.start()
        try:
            time.sleep(1.5)
            destination = Path(args.output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            camera.capture_file(str(destination))
            print(destination)
        finally:
            camera.stop()
        return
    engine = FaceEngine(match_threshold=args.threshold)
    if args.command == 'enroll':
        result = enroll_folder(engine, args.friends, args.gallery)
    elif args.command == 'recognize':
        result = {'faces': recognize_image(engine, args.image, load_gallery(args.gallery))}
    else:
        from vision_server import serve
        serve(engine, args.gallery, host=args.host, port=args.port, fps=args.fps)
        return
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
