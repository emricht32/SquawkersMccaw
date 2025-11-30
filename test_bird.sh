#!/bin/sh

# Path to bird.py inside src/ (repo-local by default)
BIRD="$(cd "$(dirname "$0")" && pwd)/src/bird.py"

JSON='{
  "mixer volume": 50,
  "player_id": "2c:cf:67:f8:c7:15",
  "use_volume_control": 1,
  "signalstrength": 0,
  "seq_no": 0,
  "player_ip": "10.0.0.121:57982",
  "player_name": "birdpi-main",
  "waitingToPlay": 1,
  "playlist_cur_index": "0",
  "can_seek": 1,
  "playlist shuffle": 0,
  "playlist_tracks": 1,
  "randomplay": 0,
  "playlist_timestamp": 1763522444.85372,
  "power": 1,
  "rate": 1,
  "digital_volume_control": 1,
  "playlist mode": "off",
  "time": 0.301,
  "player_connected": 1,
  "duration": 14.661,
  "playlist repeat": 0,
  "mode": "play",
  "playlist_loop": [
    {
      "playlist index": 0,
      "id": 36,
      "title": "happy birthday",
      "genre": "No Genre",
      "artist": "No Artist",
      "album": "No Album",
      "duration": 14.661,
      "url": "file:///mnt/mmcblk0p2/tc/SquawkersMccaw/music/happy_birthday/happy_birthday.mp3",
      "year": "0"
    }
  ]
}'

# Simulate exactly what LMS Event Trigger sends:
# playlist newsong <JSON>
python3 "$BIRD" playlist newsong "$JSON"
