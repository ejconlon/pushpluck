from abc import ABCMeta, abstractmethod
from bisect import bisect_left
from contextlib import contextmanager
from dataclasses import dataclass
from mido import Message
from mido.ports import BaseInput, BaseOutput
from pushpluck import constants
from queue import SimpleQueue
from typing import Dict, Generator, List, Optional, Tuple

import logging
import mido
import time


@dataclass(frozen=True)
class Color:
    red: int
    green: int
    blue: int

    def __iter__(self) -> Generator[int, None, None]:
        yield self.red
        yield self.green
        yield self.blue

    def to_code(self) -> str:
        nums = ''.join(f'{x:02x}' for x in self)
        return f'#{nums.upper()}'

    @classmethod
    def from_code(cls, code: str) -> 'Color':
        assert code[0] == '#'
        red = int(code[1:3], 16)
        green = int(code[3:5], 16)
        blue = int(code[5:7], 16)
        return cls(red, green, blue)


def load_colors() -> Dict[str, Color]:
    with open('colors.txt') as f:
        val: Optional[Color] = None
        out: Dict[str, Color] = {}
        for line in f.readlines():
            line = line.strip()
            if val is None:
                val = Color.from_code(line)
                assert val.to_code() == line
            else:
                out[line] = val
                val = None
        return out


COLORS = load_colors()


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


def frame_sysex(raw_data: List[int]) -> Message:
    data: List[int] = []
    data.extend(constants.ABLETON_SYSEX_PREFIX)
    data.extend(raw_data)
    return Message('sysex', data=data)


# https://github.com/crosslandwa/push-wrapper/blob/master/push.js
def make_color_msg(pos: Pos, color: Color) -> Message:
    index = pos.to_index()
    msb = [(x & 240) >> 4 for x in color]
    lsb = [x & 15 for x in color]
    raw_data = [4, 0, 8, index, 0, msb[0], lsb[0], msb[1], lsb[1], msb[2], lsb[2]]
    return frame_sysex(raw_data)


def make_led_msg(pos: Pos, value: int) -> Message:
    note = pos.to_note()
    return Message('note_on', note=note, velocity=value)


def make_lcd_msg(row: int, offset: int, text: str) -> Message:
    #   const lcdSegmentSysex = (x, y, data) =>
    # sendSysex([27 - y, 0, 9, lcdOffsets[x], ...eigthCharLcdData(data)]
    # clearLCD: () => { [27, 26, 25, 24].forEach(row => { sendSysex([row, 0, 69, 0, ...new Array(68).fill(32)]) }) },
    raw_data = [27 - row, 0, len(text) + 1, offset]
    for c in text:
        raw_data.append(ord(c))
    return frame_sysex(raw_data)


class Resettable(metaclass=ABCMeta):
    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError()


class MidiSource(metaclass=ABCMeta):
    @abstractmethod
    def recv_msg(self) -> Message:
        raise NotImplementedError()


class MidiSink(metaclass=ABCMeta):
    @abstractmethod
    def send_msg(self, msg: Message) -> None:
        raise NotImplementedError()


class Closeable(metaclass=ABCMeta):
    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError()


class MidiInput(MidiSource, Closeable):
    @classmethod
    def open(cls, in_port_name: str) -> 'MidiInput':
        queue: SimpleQueue[Message] = SimpleQueue()
        in_port = mido.open_input(in_port_name, callback=queue.put_nowait)
        return cls(in_port=in_port, queue=queue)

    def __init__(self, in_port: BaseInput, queue: 'SimpleQueue[Message]') -> None:
        self._in_port = in_port
        self._queue = queue

    def close(self) -> None:
        self._in_port.close()

    def recv_msg(self) -> Message:
        return self._queue.get()


class MidiOutput(MidiSink, Closeable):
    @classmethod
    def open(cls, out_port_name: str, virtual: bool = False, delay: Optional[float] = None) -> 'MidiOutput':
        out_port = mido.open_output(out_port_name, virtual=virtual)
        return cls(out_port=out_port, delay=delay)

    def __init__(self, out_port: BaseOutput, delay: Optional[float] = None) -> None:
        self._out_port = out_port
        self._delay = delay
        self._last_sent = 0.0

    def close(self) -> None:
        self._out_port.close()

    def send_msg(self, msg: Message) -> None:
        if self._delay is not None:
            now = time.monotonic()
            lim = self._last_sent + self._delay
            diff = lim - now
            if diff > 0:
                time.sleep(diff)
                self._last_sent = lim
            else:
                self._last_sent = now
        self._out_port.send(msg)


@dataclass(frozen=True)
class Ports(Closeable):
    midi_in: BaseInput
    midi_out: BaseOutput
    midi_processed: BaseOutput

    @classmethod
    def open_push_ports(cls, delay: Optional[float] = None) -> 'Ports':
        midi_in = MidiInput.open(constants.DEFAULT_PUSH_PORT_NAME)
        midi_out = MidiOutput.open(constants.DEFAULT_PUSH_PORT_NAME, delay=delay)
        midi_processed = MidiOutput.open(constants.DEFAULT_PROCESSED_PORT_NAME, virtual=True)
        return cls(midi_in=midi_in, midi_out=midi_out, midi_processed=midi_processed)

    def close(self) -> None:
        self.midi_in.close()
        self.midi_out.close()
        self.midi_processed.close()


@contextmanager
def push_ports_context(delay: Optional[float] = None) -> Generator[Ports, None, None]:
    logging.info('opening ports')
    ports = Ports.open_push_ports(delay=delay)
    logging.info('opened ports')
    try:
        yield ports
    finally:
        logging.info('closing ports')
        ports.close()
        logging.info('closed ports')


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

    def get_pad(self, pos: Pos) -> PadOutput:
        return PadOutput(pos, self._midi_out)

    def display_lcd(self, row: int, offset: int, text: str) -> None:
        assert len(text) + offset <= constants.MAX_LINE_LEN
        msg = make_lcd_msg(row, 0, text)
        self._midi_out.send_msg(msg)

    def reset(self) -> None:
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


@dataclass
class NoteInfo:
    velocity: int
    polytouch: Optional[int]

    @classmethod
    def pluck(cls, velocity: int) -> 'NoteInfo':
        return cls(velocity=velocity, polytouch=None)


@dataclass
class ChokeGroup:
    note_order: List[int]
    note_info: Dict[int, NoteInfo]

    @classmethod
    def empty(cls) -> 'ChokeGroup':
        return cls(note_order=[], note_info={})

    def max_note_and_info(self) -> Optional[Tuple[int, NoteInfo]]:
        max_note = self.note_order[-1] if len(self.note_order) > 0 else None
        return (max_note, self.note_info[max_note]) if max_note is not None else None

    def pluck(self, note: int, velocity: int):
        note_index = bisect_left(self.note_order, note)
        note_exists = len(self.note_order) > note_index and note_index >= 0 and self.note_order[note_index] == note
        if velocity > 0:
            if not note_exists:
                self.note_order.insert(note_index, note)
            self.note_info[note] = NoteInfo.pluck(velocity)
        else:
            if note_exists:
                del self.note_order[note_index]
            if note in self.note_info:
                del self.note_info[note]


class Fretboard:
    def __init__(self, tuning: List[int]) -> None:
        self._tuning = tuning
        self._capo_semitones = 0
        num_strings = len(self._tuning)
        self._fingered: List[ChokeGroup] = \
            [ChokeGroup.empty() for i in range(num_strings)]

    def _get_note(self, str_index: int, pre_fret: int) -> int:
        return self._tuning[str_index] + self._capo_semitones + pre_fret

    def shift_capo(self, semitones: int) -> None:
        self._capo_semitones += semitones

    def handle_note(self, str_index: int, pre_fret: int, velocity: int) -> List[Message]:
        # Find out note from fret
        fret_note = self._get_note(str_index, pre_fret)

        # Lookup choke group and find prev max note
        group = self._fingered[str_index]
        prev_note_and_info = group.max_note_and_info()

        # Add note to group and find cur max note
        group.pluck(fret_note, velocity)
        cur_note_and_info = group.max_note_and_info()

        # Return control messages
        out_msgs: List[Message] = []
        if cur_note_and_info is None:
            if prev_note_and_info is None:
                # No notes - huh? (ignore)
                pass
            else:
                # Single note mute - send off for prev
                prev_note, _ = prev_note_and_info
                off_msg = Message(type='note_on', note=prev_note, velocity=0)
                out_msgs.append(off_msg)
        else:
            cur_note, cur_info = cur_note_and_info
            if prev_note_and_info is None:
                # Single note pluck - send on for cur
                on_msg = Message(type='note_on', note=cur_note, velocity=cur_info.velocity)
                out_msgs.append(on_msg)
            else:
                prev_note, _ = prev_note_and_info
                if prev_note == cur_note:
                    # Movement above fretted string (ignore)
                    pass
                else:
                    # Hammer-on or pull-off
                    # Send on before off to maintain overlap for envelopes?
                    on_msg = Message(type='note_on', note=cur_note, velocity=cur_info.velocity)
                    out_msgs.append(on_msg)
                    off_msg = Message(type='note_on', note=prev_note, velocity=0)
                    out_msgs.append(off_msg)
        return out_msgs

    def handle_reset(self) -> List[Message]:
        out_msgs: List[Message] = []
        for str_index, group in enumerate(self._fingered):
            cur_note_and_info = group.max_note_and_info()
            if cur_note_and_info is not None:
                cur_note, _ = cur_note_and_info
                off_msg = Message(type='note_on', note=cur_note, velocity=0)
                out_msgs.append(off_msg)
        self._fingered = [ChokeGroup.empty() for i in range(len(self._tuning))]
        return out_msgs


@dataclass(frozen=True)
class Profile:
    instrument_name: str
    tuning_name: str
    tuning: List[int]


class Plucked(MidiSink, Resettable):
    def __init__(
        self,
        push: PushOutput,
        midi_processed: MidiOutput,
        profile: Profile,
    ) -> None:
        self._push = push
        self._midi_processed = midi_processed
        self._fretboard = Fretboard(profile.tuning)

    def send_msg(self, msg: Message) -> None:
        if msg.type == 'note_on' or msg.type == 'note_off':
            pos = pad_from_note(msg.note)
            if pos is not None and pos.row >= 1 and pos.row <= 6:
                str_index = pos.row - 1
                processed_msgs = self._fretboard.handle_note(str_index, pos.col, msg.velocity)
                for processed_msg in processed_msgs:
                    self._midi_processed.send_msg(processed_msg)
        elif msg.type == 'polytouch':
            # TODO send polytouch
            # pos = pad_from_note(msg.note)
            pass

    def reset(self) -> None:
        # Send note offs
        logging.info('plucked sending note offs')
        note_offs = self._fretboard.handle_reset()
        for note_off in note_offs:
            self._midi_processed.send_msg(note_off)

        # Update UI
        # TODO handle different number of strings
        logging.info('plucked resetting ui')
        for pos in all_pos():
            pad = self._push.get_pad(pos)
            if pos.row == 0 or pos.row == 7:
                pad.reset()
            else:
                pad.set_color(COLORS['Red'])
                pad.led_on(127)


class Controller(MidiSink, Resettable):
    def __init__(
        self,
        push: PushOutput,
        midi_processed: MidiOutput,
        profile: Profile
    ) -> None:
        self._push = push
        self._midi_processed = midi_processed
        self._plucked = Plucked(self._push, self._midi_processed, profile)

    def send_msg(self, msg: Message) -> None:
        reset = msg.type == 'control_change' \
                and msg.control == constants.ButtonCC.Master.value \
                and msg.value == 0
        if reset:
            self.reset()
        else:
            self._plucked.send_msg(msg)

    def reset(self):
        logging.info('controller resetting')
        for row in range(4):
            text = f'{row} - 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
            self._push.display_lcd(row, 0, text)
        self._plucked.reset()


def main_with_ports(ports: Ports) -> None:
    profile = Profile(
        instrument_name='Guitar',
        tuning_name='Standard',
        tuning=constants.STANDARD_TUNING
    )
    push = PushOutput(ports.midi_out)
    # Start with a clean slate
    logging.info('resetting push')
    push.reset()
    try:
        controller = Controller(push, ports.midi_processed, profile)
        logging.info('resetting controller')
        controller.reset()
        logging.info('controller ready')
        while True:
            msg = ports.midi_in.recv_msg()
            controller.send_msg(msg)
    finally:
        # End with a clean slate
        logging.info('final reset of push')
        push.reset()


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        format='%(asctime)s %(levelname)s %(filename)s:%(lineno)d -- %(message)s',
        level=log_level
    )


def main():
    configure_logging('INFO')
    with push_ports_context(delay=constants.DEFAULT_SLEEP_SECS) as ports:
        main_with_ports(ports)
    logging.info('done')


if __name__ == '__main__':
    main()
