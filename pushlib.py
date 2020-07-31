from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from mido import Message
from mido.ports import BaseInput, BaseOutput
from typing import Dict, Generator, List

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
PROCESSED_PORT_NAME = 'Ableton Push Processed Port'
LOW_NOTE = 36
NUM_PAD_ROWS = 8
NUM_PAD_COLS = 8
NUM_PADS = NUM_PAD_ROWS * NUM_PAD_COLS
HIGH_NOTE = LOW_NOTE + NUM_PADS
ABLETON_SYSEX_PREFIX = (71, 127, 21)


@dataclass(frozen=True)
class Ports:
    in_port: BaseInput
    out_port: BaseOutput
    processed_port: BaseOutput

    @staticmethod
    def open_push_ports() -> 'Ports':
        in_port = mido.open_input(PUSH_PORT_NAME)
        out_port = mido.open_output(PUSH_PORT_NAME)
        processed_port = mido.open_output(PROCESSED_PORT_NAME, virtual=True)
        return Ports(in_port=in_port, out_port=out_port, processed_port=processed_port)

    def close(self) -> None:
        self.in_port.close()
        self.out_port.close()
        self.processed_port.close()


@dataclass(frozen=True)
class Color:
    red: int
    green: int
    blue: int

    def __iter__(self) -> Generator[int, None, None]:
        yield self.red
        yield self.green
        yield self.blue


BLACK = Color(0, 0, 0)


@dataclass(frozen=True)
class Pos:
    """
    (0,0) is bottom left corner (lowest note)
    (7,7) is top right corner (highest note)
    """

    row: int
    col: int

    def __iter__(self) -> Generator[int, None, None]:
        yield self.row
        yield self.col

    def to_index(self) -> int:
        return NUM_PAD_COLS * self.row + self.col

    def to_note(self) -> int:
        return LOW_NOTE + self.to_index()

    @classmethod
    def from_note(self, note: int) -> 'Pos':
        if note < LOW_NOTE or note >= HIGH_NOTE:
            raise Exception(f'Note out of range: {note}')
        else:
            index = note - LOW_NOTE
            row = index // NUM_PAD_COLS
            col = index % NUM_PAD_COLS
            return Pos(row=row, col=col)


def all_pos() -> Generator[Pos, None, None]:
    """ Iterator from lowest to highest pos """
    for row in range(NUM_PAD_ROWS):
        for col in range(NUM_PAD_COLS):
            yield Pos(row, col)


def frame_sysex(raw_data: List[int]) -> Message:
    data: List[int] = []
    data.extend(ABLETON_SYSEX_PREFIX)
    data.extend(raw_data)
    return Message('sysex', data=data)


# https://github.com/crosslandwa/push-wrapper/blob/master/push.js
def make_color_message(pos: Pos, color: Color) -> Message:
    index = pos.to_index()
    msb = [(x & 240) >> 4 for x in color]
    lsb = [x & 15 for x in color]
    raw_data = [4, 0, 8, index, 0, msb[0], lsb[0], msb[1], lsb[1], msb[2], lsb[2]]
    return frame_sysex(raw_data)


def make_led_message(pos: Pos, value: int) -> Message:
    note = pos.to_note()
    return Message('note_on', note=note, velocity=value)


@contextmanager
def push_ports_context() -> Generator[Ports, None, None]:
    ports = Ports.open_push_ports()
    try:
        yield ports
    finally:
        ports.close()


class Resettable(metaclass=ABCMeta):
    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError()


class ButtonOutput(Resettable):
    def __init__(self, pos: Pos, out_port: BaseOutput) -> None:
        self._pos = pos
        self._out_port = out_port

    def led_on(self, value: int) -> None:
        message = make_led_message(self._pos, value)
        self._out_port.send(message)

    def led_off(self) -> None:
        self.led_on(0)

    def set_color(self, color: Color) -> None:
        message = make_color_message(self._pos, color)
        self._out_port.send(message)

    def reset(self) -> None:
        self.led_off()
        self.set_color(BLACK)


class PushOutput(Resettable):
    def __init__(self, out_port: BaseOutput) -> None:
        self._out_port = out_port

    def reset(self) -> None:
        for pos in all_pos():
            button = ButtonOutput(pos, self._out_port)
            button.reset()


def handle(ports: Ports) -> None:
    push = PushOutput(ports.out_port)
    push.reset()
    for msg in ports.in_port:
        print(msg)
        if msg.type == 'note_on':
            pos = Pos.from_note(msg.note)
            print(pos)
        ports.processed_port.send(msg)


def main():
    with push_ports_context() as ports:
        handle(ports)


if __name__ == '__main__':
    main()
