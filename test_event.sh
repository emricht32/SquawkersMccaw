#!/bin/sh

# Hard-coded player status JSON to simulate LMS payload
JSON='{"mixer volume":50,"player_id":"2c:cf:67:f8:c7:15","use_volume_control":1,"signalstrength":0,"seq_no":0,"player_ip":"10.0.0.121:57982","player_name":"birdpi-main","waitingToPlay":1,"playlist_cur_index":"0","can_seek":1,"playlist shuffle":0,"playlist_tracks":1,"randomplay":0,"playlist_timestamp":1763522444.85372,"power":1,"rate":1,"digital_volume_control":1,"playlist mode":"off","time":0.301,"player_connected":1,"duration":14.661,"playlist repeat":0,"mode":"play","playlist_loop":[{"playlist index":0,"id":36,"title":"happy birthday","genre":"No Genre","artist":"No Artist","album":"No Album","duration":14.661,"url":"file:///mnt/mmcblk0p2/tc/SquawkersMccaw/music/happy_birthday/happy_birthday.mp3","year":"0"}]}'

# Call your existing wrapper, passing a dummy event type + JSON payload
# event_listener.py will see raw_args = ["JSON", "<payload>"]
# build_args_from_event() will return ["<payload>"], which parseArgs() understands
/mnt/mmcblk0p2/tc/SquawkersMccaw/run_event_listener.sh JSON "$JSON"
