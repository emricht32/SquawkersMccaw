# Squawkers McCaw Tiki Room

## Overview

This project aims to recreate Disney's Enchanted Tiki Room using Squawkers McCaw birds, a Raspberry Pi, and additional hardware. Create your own automated bird orchestra and bring the magic into your living room!

## Table of Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Hardware Setup](#hardware-setup)
5. [Usage](#usage)
6. [Contributing](#contributing)
7. [License](#license)

## Requirements

- Raspberry Pi 4 Model B (Im guessing an older Pi3 could work fine but I havent tested it)
- Squawkers McCaw birds (x4)
- [Wires](https://www.amazon.com/dp/B01EV70C78)
- [4 x 2-channel Solid State Relay](https://www.amazon.com/dp/B072Z3SWDR)
- [4-channel Relay](https://www.amazon.com/dp/B00E0NSORY)
- [3 x 3.5mm Male to Male Auxiliary Audio Cable](https://www.amazon.com/dp/B07TCFQ3MG) (there are 6 in this)
- [3 X Plugable USB Audio Adapter](https://www.amazon.com/dp/B00NMXY2MO)
- [Anker 7-Port USB 3.0 Data Hub with 36W Power Adapter](https://www.amazon.com/dp/B014ZQ07NE)
- [3 Pieces Audio Amplifier Board](https://www.amazon.com/dp/B08RDN58SZ)
- [IR motion sensor](https://www.amazon.com/dp/B07KZW86YR)
- [Mini spotlights](https://www.amazon.com/dp/B0BLVBQVKS)
- [Waterproof Outdoor Electrical Box](https://www.amazon.com/dp/B0BHVHSNY6)
- [8-Pin Waterproof DT Connector](https://www.amazon.com/dp/B0C3XG8MVZ)(for easily conecting cables to box)
- [Servo Motor Hat](https://www.amazon.com/dp/B07H9ZTWNC) (for Drummers which is not yet implemented)
- [Servo motors](https://www.amazon.com/dp/B0C7KQKH68) (for Drummers which is not yet implemented)
- other basic electronics tools
- Python 3.x
- [Git](https://git-scm.com/)

## Installation

1. Install libs for the Pi
```bash
sudo apt update
sudo apt upgrade

sudo apt-get install git-lfs
sudo apt-get install python3-pip python3-numpy libportaudio2 libsndfile1 screen git

```
2. Clone this repository.
```bash
git clone https://github.com/emricht32/SquawkersMccaw.git
```

3. Navigate to the project directory.
```bash
cd SquawkersMccaw
```

4. Install the required Python packages.  If you are developing on Mac or Linux machine and then transfering files to the Pi you can use:
```bash
pip3 install -r requirements.txt
```
But either way on, the Pi run:
```bash
pip3 install -r pi-requirements.txt
```
5.  (Optional) If you want this to run on startup, you need to edit the /etc/rc.local file.

```bash
nano /etc/rc.local
```
Add the run script before the `exit 0` line

```bash
cd /path/to/SquawkersMccaw && bash -c '/usr/bin/bash run.sh > ~/squawker.log 2>&1' &
```
This will run the run.sh script and output the logs to ~/squawker.log

6.  (Optional) IR Remote Receiver setup (taken from [https://www.ignorantofthings.com/2022/03/receiving-infrared-on-raspberry-pi-with.html](https://www.ignorantofthings.com/2022/03/receiving-infrared-on-raspberry-pi-with.html))
Enabling IR communication on the Raspberry Pi

Before we start, as always it's best to update everything using `sudo apt-get update && sudo apt-get upgrade`

There are four main tasks we need to achieve:

Enable Device Tree overlays (dtoverlay) to enable the kernel to talk to the IR receiver:

Edit the Raspberry Pi config file:

```bash
sudo nano /boot/config.txt
```

Uncomment this to enable infrared communication. Change the pin to suit your configuration if required.

```
dtoverlay=gpio-ir,gpio_pin=4
```
    
Reboot when finished:

```bash
sudo reboot
```
   
Install ir-keytable to receive IR scancodes via the sensor:

Install the ir-keytable package and temporarily enable all protocols: 

```bash
sudo apt-get install ir-keytable
sudo ir-keytable -p all
```

Note that the last command will not persist a reboot and is for testing only (we'll take care of this later!)

## Hardware Setup

1. **Squawkers McCaw**: Disassemble the bird carefully and identify the control wires for the servo motors. Pic examples in docs/media.

![](docs/media/Screenshot%202023-08-28%20at%2011.34.42%20AM.png)
![](docs/media/Screenshot%202023-08-28%20at%2011.34.57%20AM.png)
![](docs/media/Screenshot%202023-08-28%20at%2011.35.16%20AM.png)
![](docs/media/Screenshot%202023-08-28%20at%2011.35.33%20AM.png)
   
2. **Wiring**: Use the diagram provided in the `/hardware` folder for reference. 

![V3](docs/hardware/TikiBirds_v3.3.png)

3. **Servo Motors**: Connect the servo motors to the Raspberry Pi's GPIO pins.  (For the Drummers which is a TODO)

## Using a thumb drive

1. Create a folder called BIRDS in your thumb drive.

2. Edit the `config_multi_song.json` file to set up GPIO pins, timers, and other settings and store it in the BIRDS folder.

3. Create a music folder and store the music files in the same path denoted in the config_multi_song.json file.

The folder and files should have the following structure:

music
├── mele-kalikimaka
│   ├── 1_Bing-Crosby-Ft-The-Andrews-Sisters-Mele-Kalikimaka-dp.mp3
│   ├── 2_Bing-Crosby-Ft-The-Andrews-Sisters-Mele-Kalikimaka-dp.mp3
│   └── 3_Bing-Crosby-Ft-The-Andrews-Sisters-Mele-Kalikimaka-dp.mp3
├── the_seasons_upon_us
│   ├── 1_the_seasons_upon_us_main_L_second_R.mp3
│   ├── 2_the_seasons_upon_us_backup.mp3
│   └── 3_the_seasons_upon_us_instrumental.mp3
├── tiki
│   ├── 1_Jose_L_Michael_R_48.mp3
│   ├── 2_Fritz_L_Pierre_R_48.mp3
│   └── 3_Instrumental_48.mp3
└── wellerman
    ├── 1_wellerman_main_L_bass_R.mp3
    └── 2_wellerman_backup.mp3

## Usage

To start the Enchanted Tiki Room experience, run:

```bash
./run.sh
```

## Notes/Thoughts

1. The music folder needs to have songs that have a samplerate of 48k.  I had to use ffmpg to convert the files from 44.1k.  This is due to the fact that the usb audio adapter seem to not support 44.1k.  My music was playing slightly too fast.

2. I used https://vocalremover.org/ to split vocals and music into separate files so the singing could be piped to the speakers in the birds with the rest of the instruments going to a separate speaker.  For the vocals, I also duplicated the files into two files and then separated the right and left channels to make different bird audio.  File1 is Jose and Michael and File2 is Fritz and Pierre.  To do this I used Audacity.

3. Id love to make a service/app that a non-technical person (aka my father-in-law who im building this for) could use to update/add songs to the birds.  Im thinking a user could upload songs and config params via some UI.  Im an iOS app developer with some go, java, python and c++ sprinkled in throughout the years in the real world and would love to discuss thoughts or suggestions with anyone who has any.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

!!!NOTE!!!
I have ZERO professional experience with circuits and hardware.  Im sure that there are things I missed (especially safetywise) when it comes to electricity and best practices.  It would not have surprised me if I blew out my Pi or caused a mini fire during this process.  Repeat my steps at your own risk.

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Acknowledgements

I started this project a couple years ago.  First I bought a [Squawker Talker](https://www.halloweenforum.com/threads/new-all-in-one-board-for-hacking-squawkers-mccaw.167858/page-4) from J-Man. If you are only looking for a single bird setup I highly recommend and suggest using this.  If I remember correctly it was about $80 and came with super easy to use instructions.  You can email him at info@audioservocontroller.com.  I also **borrowed** his images for disassembaling the bird and how to get access to the needed wires.
