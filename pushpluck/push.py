from contextlib import contextmanager
from enum import Enum, unique
from dataclasses import dataclass
from mido.frozen import FrozenMessage
from pushpluck import constants
from pushpluck.base import Closeable, Resettable
from pushpluck.color import COLORS, Color
from pushpluck.midi import MidiInput, MidiOutput
from typing import Generator, List, Optional

import logging
import time


@unique
class ButtonColor(Enum):
    Half = 1
    HalfBlinkSlow = 2
    HalfBlinkFast = 3
    Full = 4
    FullBlinkSlow = 5
    FullBlinkFast = 6
    Off = 0
    On = 127


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
        return constants.NUM_PAD_COLS * self.row + self.col

    def to_note(self) -> int:
        return constants.LOW_NOTE + self.to_index()


def pad_from_note(note: int) -> Optional[Pos]:
    if note < constants.LOW_NOTE or note >= constants.HIGH_NOTE:
        return None
    else:
        index = note - constants.LOW_NOTE
        row = index // constants.NUM_PAD_COLS
        col = index % constants.NUM_PAD_COLS
        return Pos(row=row, col=col)


def all_pos() -> Generator[Pos, None, None]:
    """ Iterator from lowest to highest pos """
    for row in range(constants.NUM_PAD_ROWS):
        for col in range(constants.NUM_PAD_COLS):
            yield Pos(row, col)


def frame_sysex(raw_data: List[int]) -> FrozenMessage:
    data: List[int] = []
    data.extend(constants.PUSH_SYSEX_PREFIX)
    data.extend(raw_data)
    return FrozenMessage('sysex', data=data)


def make_color_msg(pos: Pos, color: Color) -> FrozenMessage:
    index = pos.to_index()
    msb = [(x & 240) >> 4 for x in color]
    lsb = [x & 15 for x in color]
    raw_data = [4, 0, 8, index, 0, msb[0], lsb[0], msb[1], lsb[1], msb[2], lsb[2]]
    return frame_sysex(raw_data)


def make_led_msg(pos: Pos, value: int) -> FrozenMessage:
    note = pos.to_note()
    return FrozenMessage('note_on', note=note, velocity=value)


def make_lcd_msg(row: int, offset: int, text: str) -> FrozenMessage:
    raw_data = [27 - row, 0, len(text) + 1, offset]
    for c in text:
        raw_data.append(ord(c))
    return frame_sysex(raw_data)


@dataclass(frozen=True)
class PushPorts(Closeable):
    midi_in: MidiInput
    midi_out: MidiOutput
    midi_processed: MidiOutput

    @classmethod
    def open(
        cls,
        push_port_name: str,
        processed_port_name: str,
        delay: Optional[float]
    ) -> 'PushPorts':
        midi_in = MidiInput.open(push_port_name)
        midi_out = MidiOutput.open(push_port_name, delay=delay)
        midi_processed = MidiOutput.open(processed_port_name, virtual=True)
        return cls(midi_in=midi_in, midi_out=midi_out, midi_processed=midi_processed)

    def close(self) -> None:
        self.midi_in.close()
        self.midi_out.close()
        self.midi_processed.close()


@contextmanager
def push_ports_context(
    push_port_name: str,
    processed_port_name: str,
    delay: Optional[float]
) -> Generator[PushPorts, None, None]:
    logging.info('opening ports')
    ports = PushPorts.open(
        push_port_name=push_port_name,
        processed_port_name=processed_port_name,
        delay=delay
    )
    logging.info('opened ports')
    try:
        yield ports
    finally:
        logging.info('closing ports')
        ports.close()
        logging.info('closed ports')


class LcdOutput(Resettable):
    def __init__(self, midi_out: MidiOutput) -> None:
        self._midi_out = midi_out

    def display_line(self, row: int, text: str) -> None:
        text = text.ljust(constants.DISPLAY_MAX_LINE_LEN, ' ')
        self.display_raw(row, 0, text)

    def display_raw(self, row: int, line_col: int, text: str) -> None:
        assert row >= 0 and row < constants.DISPLAY_MAX_ROWS
        assert line_col >= 0
        assert len(text) + line_col <= constants.DISPLAY_MAX_LINE_LEN
        msg = make_lcd_msg(row, line_col, text)
        self._midi_out.send_msg(msg)

    def display_block(self, row: int, block_col: int, text: str) -> None:
        assert row >= 0 and row < constants.DISPLAY_MAX_ROWS
        assert block_col >= 0 and block_col < constants.DISPLAY_MAX_BLOCKS
        assert len(text) <= constants.DISPLAY_BLOCK_LEN
        text = text.ljust(constants.DISPLAY_BLOCK_LEN, ' ')
        line_col = constants.DISPLAY_BLOCK_LEN * block_col
        msg = make_lcd_msg(row, line_col, text)
        self._midi_out.send_msg(msg)

    def reset(self):
        for row in range(constants.DISPLAY_MAX_ROWS):
            self.display_line(row, '')


class PadOutput(Resettable):
    def __init__(self, pos: Pos, midi_out: MidiOutput) -> None:
        self._pos = pos
        self._midi_out = midi_out

    def led_on(self, value: int) -> None:
        msg = make_led_msg(self._pos, value)
        self._midi_out.send_msg(msg)

    def led_off(self) -> None:
        self.led_on(0)

    def set_color(self, color: Color) -> None:
        msg = make_color_msg(self._pos, color)
        self._midi_out.send_msg(msg)

    def reset(self) -> None:
        self.led_off()
        self.set_color(COLORS['Black'])


class PushOutput(Resettable):
    def __init__(self, midi_out: MidiOutput) -> None:
        self._midi_out = midi_out
        self._pads = {pos: PadOutput(pos, midi_out) for pos in all_pos()}
        self._lcd = LcdOutput(self._midi_out)

    def get_pad(self, pos: Pos) -> PadOutput:
        return self._pads[pos]

    def get_lcd(self) -> LcdOutput:
        return self._lcd

    def reset(self) -> None:
        logging.info('resetting push display')
        lcd = self.get_lcd()
        lcd.reset()

        logging.info('resetting push pads')
        for pos in all_pos():
            pad = self.get_pad(pos)
            pad.reset()


def rainbow(push: PushOutput) -> None:
    names = ['Red', 'Orange', 'Yellow', 'Green', 'Blue', 'Indigo', 'Violet']
    for name in names:
        color = COLORS[name]
        for pos in all_pos():
            pad = push.get_pad(pos)
            pad.set_color(color)
            pad.led_on(40)
            time.sleep(0.01)
        time.sleep(1)
