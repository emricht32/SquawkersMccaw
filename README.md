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

- Raspberry Pi 4 Model B (or newer)
- Squawkers McCaw birds
- Wires, 8-channel Solid State Relay, 4-channel Solid State Relay, IR motion sensor, Servo Motor Hat (for Drummers which is not yet implemented) and other basic electronics tools
- Python 3.x
- [Git](https://git-scm.com/)

## Installation

1. Clone this repository.
```bash
git clone https://github.com/emricht32/SquawkersMccaw.git
```

2. Navigate to the project directory.
```bash
cd SquawkersMccaw
```

3. Install the required Python packages.  If you are developing on Mac or Linux machine and then transfering files to the Pi you can use:
```bash
pip3 install -r requirements.txt
```
But either way on, the Pi run:
```bash
pip3 install -r pi-requirements.txt
```
## Hardware Setup

1. **Squawkers McCaw**: Disassemble the bird carefully and identify the control wires for the servo motors. Pic examples in docs/media.
   
2. **Wiring**: Use the diagram provided in the `/hardware` folder for reference.  There are two versions of the diagram so far.  I am in the middle of updating the display to only use Solid State Relays and V2 has been updated for this.

3. **Servo Motors**: Connect the servo motors to the Raspberry Pi's GPIO pins.  (For the Drummers which is a TODO)


## Software Configuration __(I plan on creating a config file to allow any song and customizing pins but this is not yet implemented)__

1. Edit the `config.yaml` file to set up GPIO pins, timers, and other settings.

## Usage

To start the Enchanted Tiki Room experience, run:

```bash
python main.py
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

!!!NOTE!!!
I have ZERO professional experience with circuits and hardware.  Im sure that there are things I missed (especially safetywise) when it comes to electricity and best practices.  It would not have surprised me if I blew out my Pi or caused a mini fire during this process.  Repeat my steps at your own risk.

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Acknolagements

I started this project a couple years ago.  First I bought a [Squawker Talker](https://www.halloweenforum.com/threads/new-all-in-one-board-for-hacking-squawkers-mccaw.167858/page-4) from J-Man. If you are only looking for a single bird setup I highly recommend and suggest using this.  If I remember correctly it was about $80 and came with super easy to use instructions.  You can email him at info@audioservocontroller.com.  I also **borrowed** his images for disassembaling the birdand how to get access to the needed wires.