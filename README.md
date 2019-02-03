# PGoTrader

This script does auto-trading between two simultaneous applications running on the same device (using Island, MIUI's Dual Apps, and so on).

Should work with other Dual App solutions as well, as long as the `switch_app()` co-routine is able to switch between both instances.

## Requirements

*You only need to perform this steps once*

- Download all the files from this repository.
- Install `adb`, make sure it's on your systems PATH, alternatively you can place adb in the same folder as ivcheck.py.
- Install [clipper](https://github.com/majido/clipper) in your device and start the service.
- Install Python >=3.7 (older versions will not work).
- Set up `config.yaml`, most of the options are documented there.

## How to use
- Open both apps.
- Go to Friends, and open the friend screen (in both apps).
- Run `python trade.py`.