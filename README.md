# pushpluck

UNDER CONSTRUCTION

A "plucked-string" controller for the User Mode of the Ableton Push 1.

This program reads and writes to the user midi ports of the Push and emits a stream of derived midi notes and controls to a virtual midi port. Typically you will have to start this manually from the terminal with your Push connected. You don't need Live running, but if it is, be aware that you will have to manually press the `User` button to enter User Mode, and possibly press the `Master` button to refresh the display.

## Installation and Execution

To run this, you'll need a recent version of Python 3, `rtmidi`, and some Python libraries you can install with `pip`. On OSX you can run `./brewstrap.sh && make venv` to install a known good interpreter version and all dependencies.

You can run the `pushpluck.main` module or simply run `./run.sh` to run the thing. The default options should be fine, but if needed you can explore them with `./run.sh --help`.

## Thanks

Thanks to [push-wrapper](https://github.com/crosslandwa/push-wrapper) (MIT license) for the examples!
Thanks to [Julien Bayle](https://julienbayle.studio/ableton-live-push/) for the info/graphics!
