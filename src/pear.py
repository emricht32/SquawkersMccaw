"""
See README.md for usage and installation
Written by Devon Bray (dev@esologic.com)
Adopted from: https://github.com/esologic/pear/blob/master/pear.py
"""

import sounddevice
import soundfile
import pathlib
from math import sqrt
import numpy as np

DATA_TYPE = "float32"

def load_sound_file_into_memory(path):
    """
    Get the in-memory version of a given path to a wav file
    :param path: wav file to be loaded
    :return: (audio_data, samplerate), a 2D numpy array, the samplerate of the audiofile
    """
    with soundfile.SoundFile(path) as sf:
        nparray = sf.read(dtype='float32')
        print("sounddevice.default.samplerate=",sounddevice.default.samplerate)
        sounddevice.default.samplerate = sf.samplerate
        if "instrumental" in path.lower():
            print("upping volume")
            # https://stackoverflow.com/questions/60969400/how-can-i-increase-the-volume-of-a-byte-array-which-is-from-pyaudio-in-python
            volumeFactor = 2
            multiplier = pow(2, (sqrt(sqrt(sqrt(volumeFactor))) * 192 - 192)/6)
            np.multiply(nparray, multiplier, 
                out=nparray, casting="unsafe")
        return nparray, sf.samplerate


def dir_path(path):
    """
    Checks to see if the given path is actually a directory
    :param path: a path to a directory
    :return: path if it's a directory, raises an error if otherwise
    """

    p = pathlib.Path(path)
    if p.is_dir():
        return path
    else:
        raise NotADirectoryError(path)


def get_device_number_if_usb_soundcard(index_info):
    """
    Given a device dict, return True if the device is one of our USB sound cards and False if otherwise
    :param index_info: a device info dict from PyAudio.
    :return: True if usb sound card, False if otherwise
    """

    index, info = index_info

    if "USB Audio Device" in info["name"]:
        return index
    return False


def play_wav_on_index(audio_data, stream_object):
    """
    Play an audio file given as the result of `load_sound_file_into_memory`
    :param audio_data: A two-dimensional NumPy array
    :param stream_object: a sounddevice.OutputStream object that will immediately start playing any data written to it.
    :return: None, returns when the data has all been consumed
    """

    stream_object.write(audio_data)


def create_running_output_stream(index):
    """
    Create an sounddevice.OutputStream that writes to the device specified by index that is ready to be written to.
    You can immediately call `write` on this object with data and it will play on the device.
    :param index: the device index of the audio device to write to
    :return: a started sounddevice.OutputStream object ready to be written to
    """

    output = sounddevice.OutputStream(
        device=index,
        dtype=DATA_TYPE
    )

    output.start()
    return output
