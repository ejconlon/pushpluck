from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from mido.frozen import FrozenMessage
from pushpluck import constants
from pushpluck.base import Closeable, Resettable
from pushpluck.color import COLORS, Color
from pushpluck.constants import ButtonCC, ButtonColor, ButtonIllum, KnobCC, KnobGroup, TimeDivCC
from pushpluck.midi import MidiInput, MidiOutput, is_note_msg
from pushpluck.pos import ChanSelPos, GridSelPos, Pos
from typing import Generator, List, Optional, Type, TypeVar

import logging
import time


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


E = TypeVar('E', bound='PushEvent')


class PushEvent(metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def match(cls: Type[E], msg: FrozenMessage) -> Optional[E]:
        raise NotImplementedError


@dataclass(frozen=True)
class KnobEvent(PushEvent):
    knob: KnobCC
    group: KnobGroup
    offset: int
    clockwise: bool

    @classmethod
    def match(cls, msg: FrozenMessage) -> Optional['KnobEvent']:
        if msg.type == 'control_change':
            knob = constants.KNOB_CC_VALUE_LOOKUP.get(msg.control)
            if knob is not None:
                group, offset = constants.knob_group_and_offset(knob)
                return cls(knob, group, offset, msg.value < 127)
        return None


@dataclass(frozen=True)
class ButtonEvent(PushEvent):
    button: ButtonCC
    pressed: bool

    @classmethod
    def match(cls, msg: FrozenMessage) -> Optional['ButtonEvent']:
        if msg.type == 'control_change':
            button = constants.BUTTON_CC_VALUE_LOOKUP.get(msg.control)
            if button is not None:
                return cls(button, msg.value > 0)
        return None


@dataclass(frozen=True)
class PadEvent(PushEvent):
    pos: Pos
    velocity: int

    @classmethod
    def match(cls, msg: FrozenMessage) -> Optional['PadEvent']:
        if is_note_msg(msg):
            pos = Pos.from_input_note(msg.note)
            if pos is not None:
                return PadEvent(pos, msg.velocity)
        return None


@dataclass(frozen=True)
class TimeDivEvent(PushEvent):
    time_div: constants.TimeDivCC
    pressed: bool

    @classmethod
    def match(cls, msg: FrozenMessage) -> Optional['TimeDivEvent']:
        if msg.type == 'control_change':
            time_div = constants.TIME_DIV_CC_VALUE_LOOKUP.get(msg.control)
            if time_div is not None:
                return cls(time_div, msg.value > 0)
        return None


@dataclass(frozen=True)
class GridSelEvent(PushEvent):
    gs_pos: GridSelPos
    pressed: bool

    @classmethod
    def match(cls, msg: FrozenMessage) -> Optional['GridSelEvent']:
        if msg.type == 'control_change':
            gs_pos = GridSelPos.from_input_control(msg.control)
            if gs_pos is not None:
                return cls(gs_pos, msg.value > 0)
        return None


@dataclass(frozen=True)
class ChanSelEvent(PushEvent):
    cs_pos: ChanSelPos
    pressed: bool

    @classmethod
    def match(cls, msg: FrozenMessage) -> Optional['ChanSelEvent']:
        if msg.type == 'control_change':
            cs_pos = ChanSelPos.from_input_control(msg.control)
            if cs_pos is not None:
                return cls(cs_pos, msg.value > 0)
        return None


def match_event(msg: FrozenMessage) -> Optional[PushEvent]:
    knob_event = KnobEvent.match(msg)
    if knob_event is not None:
        return knob_event
    button_event = ButtonEvent.match(msg)
    if button_event is not None:
        return button_event
    pad_event = PadEvent.match(msg)
    if pad_event is not None:
        return pad_event
    td_event = TimeDivEvent.match(msg)
    if td_event is not None:
        return td_event
    gs_event = GridSelEvent.match(msg)
    if gs_event is not None:
        return gs_event
    cs_event = ChanSelEvent.match(msg)
    if cs_event is not None:
        return cs_event
    # TODO polytouch and pitchwheel events
    return None


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


class PushOutput(Resettable):
    def __init__(self, midi_out: MidiOutput) -> None:
        self._midi_out = midi_out

    def pad_led_on(self, pos: Pos, value: int = 100) -> None:
        msg = make_led_msg(pos, value)
        self._midi_out.send_msg(msg)

    def pad_led_off(self, pos: Pos) -> None:
        self.pad_led_on(pos, 0)

    def pad_set_color(self, pos: Pos, color: Color) -> None:
        msg = make_color_msg(pos, color)
        self._midi_out.send_msg(msg)

    def pad_reset(self) -> None:
        for pos in Pos.iter_all():
            self.pad_led_off(pos)

    def lcd_display_line(self, row: int, text: str) -> None:
        text = text.ljust(constants.DISPLAY_MAX_LINE_LEN, ' ')
        self.lcd_display_raw(row, 0, text)

    def lcd_display_raw(self, row: int, line_col: int, text: str) -> None:
        assert row >= 0 and row < constants.DISPLAY_MAX_ROWS
        assert line_col >= 0
        assert len(text) + line_col <= constants.DISPLAY_MAX_LINE_LEN
        msg = make_lcd_msg(row, line_col, text)
        self._midi_out.send_msg(msg)

    def lcd_display_block(self, row: int, block_col: int, text: str) -> None:
        assert row >= 0 and row < constants.DISPLAY_MAX_ROWS
        assert block_col >= 0 and block_col < constants.DISPLAY_MAX_BLOCKS
        assert len(text) <= constants.DISPLAY_BLOCK_LEN
        text = text.ljust(constants.DISPLAY_BLOCK_LEN, ' ')
        line_col = constants.DISPLAY_BLOCK_LEN * block_col
        msg = make_lcd_msg(row, line_col, text)
        self._midi_out.send_msg(msg)

    def lcd_display_half_block(self, row: int, half_col: int, text: str) -> None:
        block_col = half_col // 2
        half = half_col % 2
        assert row >= 0 and row < constants.DISPLAY_MAX_ROWS
        assert block_col >= 0 and block_col < constants.DISPLAY_MAX_BLOCKS
        assert len(text) <= constants.DISPLAY_HALF_BLOCK_LEN
        offset: int
        just_text: str
        if half == 0:
            offset = 0
            just_text = text.ljust(constants.DISPLAY_HALF_BLOCK_LEN + 1, ' ')
        else:
            offset = constants.DISPLAY_HALF_BLOCK_LEN
            just_text = ' ' + text.ljust(constants.DISPLAY_HALF_BLOCK_LEN, ' ')
        line_col = constants.DISPLAY_BLOCK_LEN * block_col + offset
        msg = make_lcd_msg(row, line_col, just_text)
        self._midi_out.send_msg(msg)

    def lcd_reset(self) -> None:
        for row in range(constants.DISPLAY_MAX_ROWS):
            self.lcd_display_line(row, '')

    def button_set_illum(self, button: ButtonCC, illum: ButtonIllum) -> None:
        msg = FrozenMessage(type='control_change', control=button.value, value=illum.value)
        self._midi_out.send_msg(msg)

    def button_off(self, button: ButtonCC) -> None:
        msg = FrozenMessage(type='control_change', control=button.value, value=0)
        self._midi_out.send_msg(msg)

    def button_reset(self) -> None:
        for button in ButtonCC:
            self.button_off(button)

    def time_div_off(self, time_div: TimeDivCC) -> None:
        # TODO
        pass

    def time_div_reset(self) -> None:
        for time_div in TimeDivCC:
            self.time_div_off(time_div)

    def chan_sel_set_color(self, cs_pos: ChanSelPos, illum: ButtonIllum, color: ButtonColor) -> None:
        # TODO
        pass

    def chan_sel_off(self, cs_pos: ChanSelPos) -> None:
        # TODO
        pass

    def chan_sel_reset(self) -> None:
        for cs_pos in ChanSelPos.iter_all():
            self.chan_sel_off(cs_pos)

    def grid_sel_set_color(self, gs_pos: GridSelPos, color: Color) -> None:
        # TODO
        pass

    def grid_sel_off(self, gs_pos: GridSelPos) -> None:
        # TODO
        pass

    def grid_sel_reset(self) -> None:
        for gs_pos in GridSelPos.iter_all():
            self.grid_sel_off(gs_pos)

    def reset(self) -> None:
        logging.info('resetting push display')
        self.lcd_reset()

        logging.info('resetting push controls')
        self.pad_reset()
        self.grid_sel_reset()
        self.chan_sel_reset()
        self.button_reset()
        self.time_div_reset()


def rainbow(push: PushOutput) -> None:
    names = ['Red', 'Orange', 'Yellow', 'Green', 'Blue', 'Indigo', 'Violet']
    for name in names:
        color = COLORS[name]
        for pos in Pos.iter_all():
            push.pad_set_color(pos, color)
        time.sleep(1)
