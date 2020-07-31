from contextlib import contextmanager
from dataclasses import dataclass
from mido.ports import BaseInput, BaseOutput
from typing import Dict, Generator

import mido


BUTTON_TO_CC: Dict[str, int] = {
    'TapTempo': 3,
    'Metronome': 9,
    'Undo': 119,
    'Delete': 118,
    'Double': 117,
    'Quantize': 116,
    'FixedLength': 90,
    'Automation': 89,
    'Duplicate': 88,
    'New': 87,
    'Rec': 86,
    'Play': 85,
    'Master': 28,
    'Stop': 29,
    'Left': 44,
    'Right': 45,
    'Up': 46,
    'Down': 47,
    'Volume': 114,
    'Pan&Send': 115,
    'Track': 112,
    'Clip': 113,
    'Device': 110,
    'Browse': 111,
    'StepIn': 62,
    'StepOut': 63,
    'Mute': 60,
    'Solo': 61,
    'Scales': 58,
    'User': 59,
    'Repeat': 56,
    'Accent': 57,
    'OctaveDown': 54,
    'OctaveUp': 55,
    'AddEffect': 52,
    'AddTrack': 53,
    'Note': 50,
    'Session': 51,
    'Select': 48,
    'Shift': 49
}

TIME_DIV_BUTTON_TO_CC: Dict[str, int] = {
    '1/4': 36,
    '1/4t': 37,
    '1/8': 38,
    '1/8t': 39,
    '1/16': 40,
    '1/16t': 41,
    '1/32': 42,
    '1/32t': 43
}


PUSH_PORT_NAME = 'Ableton Push User Port'


@dataclass(frozen=True)
class Ports:
    in_port: BaseInput
    out_port: BaseOutput

    @staticmethod
    def open_push_ports() -> 'Ports':
        in_port = mido.open_input(PUSH_PORT_NAME)
        out_port = mido.open_output(PUSH_PORT_NAME)
        return Ports(in_port=in_port, out_port=out_port)

    def close(self) -> None:
        self.in_port.close()
        self.out_port.close()


@contextmanager
def push_ports_context() -> Generator[Ports, None, None]:
    ports = Ports.open_push_ports()
    try:
        yield ports
    finally:
        ports.close()


def main():
    with push_ports_context() as ports:
        assert ports is not None


if __name__ == '__main__':
    main()
