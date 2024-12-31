"""
Blocks until the sounddevice module is able to pick up all of the attached usb sound cards as seen by lsusb
"""

import subprocess

"""
python3 -m sounddevice
   0 bcm2835 Headphones: - (hw:0,0), ALSA (0 in, 8 out)
   1 Plugable USB Audio Device: - (hw:1,0), ALSA (2 in, 2 out)  <-- Bird
   2 Plugable USB Audio Device: - (hw:2,0), ALSA (2 in, 2 out)  <-- Bird
   3 Plugable USB Audio Device: - (hw:5,0), ALSA (2 in, 2 out)  <-- Bird
   4 USB Audio Device: - (hw:6,0), ALSA (1 in, 2 out)           <-- Use for all sound
   5 sysdefault, ALSA (0 in, 128 out)
   6 lavrate, ALSA (0 in, 128 out)
   7 samplerate, ALSA (0 in, 128 out)
   8 speexrate, ALSA (0 in, 128 out)
   9 pulse, ALSA (32 in, 32 out)
  10 upmix, ALSA (0 in, 8 out)
  11 vdownmix, ALSA (0 in, 6 out)
  12 dmix, ALSA (0 in, 2 out)
* 13 default, ALSA (32 in, 32 out)
"""
def num_sound_devices():
    """
    Use an external call to sounddevice to get the number of devices detected by the library.
    It's important to do this rather than just sounddevice.query_devices(),
    :return:
    """

    return str(subprocess.check_output(["python3", "-m", "sounddevice"])).count("USB Audio Device")

"""
lsusb
Bus 002 Device 003: ID 2109:0817 VIA Labs, Inc. USB3.0 Hub             
Bus 002 Device 002: ID 2109:0817 VIA Labs, Inc. USB3.0 Hub             
Bus 002 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub
Bus 001 Device 009: ID 0d8c:0014 C-Media Electronics, Inc. Audio Adapter (Unitek Y-247A) <-- Use for all sound
Bus 001 Device 007: ID 0c76:120b JMTek, LLC. Plugable USB Audio Device <-- Bird
Bus 001 Device 006: ID 0c76:120b JMTek, LLC. Plugable USB Audio Device <-- Bird
Bus 001 Device 005: ID 2109:2817 VIA Labs, Inc. USB2.0 Hub             
Bus 001 Device 004: ID 0c76:120b JMTek, LLC. Plugable USB Audio Device <-- Bird
Bus 001 Device 003: ID 2109:2817 VIA Labs, Inc. USB2.0 Hub             
Bus 001 Device 002: ID 2109:3431 VIA Labs, Inc. Hub
"""
def wait_for_usb_sound_devices_to_be_initialized():
    """
    Calling this function will block until the number of USB sound soundcard devices detected by lsusb matches
    the number initialized by the sound device backend.
    :return:
    """
    lsusb_str = str(subprocess.check_output(["lsusb"]))
    while num_sound_devices() != (lsusb_str.count("C-Media Electronics") + lsusb_str.count("USB Audio Device")):
        lsusb_str = str(subprocess.check_output(["lsusb"]))


if __name__ == "__main__":
    wait_for_usb_sound_devices_to_be_initialized()