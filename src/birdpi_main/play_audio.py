import common.pear as pear
from common.bird import manage_leds
import threading
import sounddevice
import time
import os

playback_lock = threading.Lock()

def play_audio_with_speech_indicator(song, birds, startTime = 0, completion=None):
    if playback_lock.acquire(blocking=False):
        try:
            _play_audio_with_speech_indicator(song, birds, startTime, completion=completion)
        finally:
            playback_lock.release()
    else:
        print("⚠️ Playback already in progress, ignoring new voice command.")

def _prepare_streams_and_threads(song, birds):
    def good_filepath(path):
        return str(path).endswith(".wav") and not str(path).startswith(".")

    for bird in birds:
        bird.prepare_song(song)
    audio_dir = song["audio_dir"]
    sound_file_paths = [os.path.join(audio_dir, path) for path in sorted(filter(good_filepath, os.listdir(audio_dir)))]
    print("sound_file_paths=", sound_file_paths)
    # files = [pear.load_sound_file_into_memory(path) for path in sound_file_paths]
    # Separate master file and other files
    master_file_path = next(
        (path for path in sound_file_paths if os.path.basename(path).startswith("0")),
        None
    )
    print("master_file_path=", master_file_path)
    non_master_file_paths = [path for path in sound_file_paths if not os.path.basename(path).startswith("0")]
    files = [pear.load_sound_file_into_memory(path) for path in non_master_file_paths]

    print("non_master_file_paths=", non_master_file_paths)

    # Ensure there is only one master file
    master_file = None
    if master_file_path:
        master_file = pear.load_sound_file_into_memory(master_file_path)  # Take the first master file
        print("master_file=", master_file)

    print("# Calculate the longest playback duration")
    if master_file is not None:
        seconds = len(master_file[0]) / master_file[1] 
    else:
        seconds = max(len(data[0]) / data[1] for data in files)
       
    print("sounddevice.query_devices()=",sounddevice.query_devices())

    usb_sound_card_indices_touple = list(filter(lambda x: x is not False and x[1] is False,
                                         map(pear.get_device_number_if_usb_soundcard,
                                             [index_info for index_info in enumerate(sounddevice.query_devices())])))
    print("usb_sound_card_indices_touple=", usb_sound_card_indices_touple)
    master_card_touple = next(
        (x for x in map(pear.get_device_number_if_usb_soundcard, 
                        enumerate(sounddevice.query_devices())) 
        if x and x[1] is True), 
        None
    )
    print("master_card_touple=",master_card_touple)

    # Create the master stream 
    master_stream = pear.create_running_output_stream(master_card_touple[0])  
    print("master_stream=",master_stream)
    threads = []
    # Create non-master streams
    streams = [
        pear.create_running_output_stream(index)
        for (index, isMaster) in usb_sound_card_indices_touple
        if not isMaster
    ]
    
    # uncomment thread list if having bird audio
    # threads = [threading.Thread(target=pear.play_wav_on_index, args=[data[0], stream]) 
    #            for data, stream in zip(files, streams)]

    # Create the master thread (assuming master_stream and master_file are defined)
    if master_stream is not None and master_file is not None:
        print("master_stream is not None and master_file is not None")
        print("master_stream: ", master_stream)
        print("master_file: ", master_file)
        master_thread = threading.Thread(
            target=pear.play_wav_on_index,
            args=[master_file[0], master_stream]
        )
        threads.append(master_thread)
    else:
        print("Master not running")
    return seconds, streams, master_stream, threads


def _play_audio_with_speech_indicator(song, birds, startTime, completion):
    seconds, streams, master_stream, threads = _prepare_streams_and_threads(song, birds)
    try:
        try:
            curr_time = time.time()
            delay = startTime - curr_time
            if delay < 0:
                delay = 0
            time.sleep(delay)
            print("# Start all playback threads")
            print("threads: ", threads)
            for thread in threads:
                thread.start()

            print("# Manage LEDs during audio playback")
            manage_leds(birds, seconds)

            print("# Wait for all threads to complete")
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            print("Playback interrupted by user")
            for stream in streams:
                stream.abort(ignore_errors=True)
                stream.close()
        except Exception as e:
            print(f"An error occurred during playback: {e}")
    finally:
        # Ensure all streams are properly stopped and closed
        for stream in streams:
            if not stream.closed:
                stream.stop(ignore_errors=True)
                stream.close()
        if master_stream and not master_stream.closed:
            master_stream.stop(ignore_errors=True)
            master_stream.close()

        for bird in birds:
            print("STOPPING Bird:", bird.name)
            bird.stop_moving()

        if completion is not None:
            completion(song)

