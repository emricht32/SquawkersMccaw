# BirdPi AI v9 — AI Camera + opt-in face recognition (preview)

This is a **complete replacement ZIP** for v8. All Piper/chirp components, 991 production chirps, pre/post squawks, and Polly Poppy settings remain included.

## What's implemented
- `vision/vision_cli.py enroll`: import `friends/<id>/*.jpg` and `profile.json`, build a local OpenCV SFace embedding gallery. Only profiles explicitly declaring `consent_to_recognition: true` are included.
- `vision/vision_cli.py recognize IMAGE`: compare detected faces in a saved photo to the gallery.
- `vision/vision_cli.py capture`: capture one live IMX500 camera image to a file.
- `vision/vision_cli.py live`: locally hosted preview dashboard + `/api/vision/people` JSON with temporary track IDs and tentative recognition. Updates the gallery when you rerun `enroll`, without needing a server restart.
- Recognition is **preview only**: no automatic spoken names, no personal jokes, no automatic face snapshots, and no database writes on live view.

## Pi 5 installation
Run on a supported Raspberry Pi OS 64-bit installation, from the project root:

```sh
./vision/install_vision.sh
sudo reboot # first-time imx500 driver/firmware installation only
```

Check the camera:
```sh
rpicam-hello --list-cameras
```

**Important:** The system packages `python3-opencv` and `python3-picamera2` via `apt`. Use `/usr/bin/python3` for the vision commands below, **not** `.venv/bin/python`, unless the venv has `--system-site-packages` and matching OpenCV bindings. No camera and no models were available during packaging, so inference and recognition on Pi are **not yet hardware-verified**.

## Enroll your own photos first
1. Place 3–10 photos containing *only your face* in `friends/self/`, preferably different angles and lighting. Supported `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`.
2. Edit `friends/self/profile.json`: set `display_name` to the name you want shown, and change `consent_to_recognition` to `true`.
3. Build the gallery:
```sh
/usr/bin/python3 vision/vision_cli.py enroll
```
4. Test saved photo recognition (ideally use a test image not included in enrollment):
```sh
/usr/bin/python3 vision/vision_cli.py recognize /path/to/test-photo.jpg
```
If recognition is uncertain, the result will be `person_id: null`. Starting candidate threshold is 0.42, **not validated** on your camera; do not treat similarity as a calibrated probability.

## Capture from camera and preview live
```sh
/usr/bin/python3 vision/vision_cli.py capture --output vision/camera_test.jpg
/usr/bin/python3 vision/vision_cli.py live
```
From another machine use an SSH tunnel:
```sh
ssh -L 8090:127.0.0.1:8090 polly@YOUR_PI_IP
```
Then open `http://127.0.0.1:8090` in the other machine's browser. Endpoint: `http://127.0.0.1:8090/api/vision/people`.

## Updating / deleting friends
- Add `friends/alex/profile.json` and photos, with `consent_to_recognition: true` only after they agree.
- Re-run `enroll`. Gallery is rebuilt, and the live preview reloads it automatically.
- To remove: delete their folder, then rerun `enroll`. Existing gallery is replaced atomically, removing their saved embeddings.
- Keep `friends/` and `vision/gallery.json` private; these are biometric records. Avoid committing or sharing them. Do not add non-consenting people's photos. The samples include no actual faces.

## Current limits
- Uses Pi-side YuNet face detection and SFace recognition rather than onboard IMX500 inference. AI Camera serves as image source; its neural accelerator is **not yet used** by this v9 Python service. IMX500 object detection can be added later independently.
- Temporary tracking is lightweight frame-to-frame centroid association, not full re-identification across departures. Tracks may switch or reset.
- The `tags` dictionary in the live API is currently empty: clothing, hat, Hawaiian shirt, gestures, and other joke labels are **not implemented yet**.
- Person-level chirp history and automatic joke selection from camera observations remain separate future integration tasks.
- Browser preview is local only by default; don't set `--host 0.0.0.0` on an untrusted network.
- Offline model files are downloaded separately, because they are large; model distribution licenses apply.

## Tests
```sh
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s vision/tests -v
```
