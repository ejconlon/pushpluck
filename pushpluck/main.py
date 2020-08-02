from abc import ABCMeta, abstractmethod
from bisect import bisect_left
from contextlib import contextmanager
from dataclasses import dataclass
from mido import Message
from mido.ports import BaseInput, BaseOutput
from pushpluck import constants
from queue import SimpleQueue
from typing import Dict, Generator, List, Optional

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

    @classmethod
    def from_note(self, note: int) -> 'Pos':
        if note < constants.LOW_NOTE or note >= constants.HIGH_NOTE:
            raise Exception(f'Note out of range: {note}')
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
        print('sending', msg)
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
    ports = Ports.open_push_ports(delay=delay)
    try:
        yield ports
    finally:
        ports.close()


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


class Guitar(MidiSink, Resettable):
    def __init__(self, push: PushOutput, midi_processed: MidiOutput, tuning: List[int]) -> None:
        self._push = push
        self._midi_processed = midi_processed
        self._tuning = tuning
        self._num_strings = len(self._tuning)
        # TODO handle different number of strings
        # assert self._num_strings > 0 and self._num_strings <= 8
        assert self._num_strings == 6
        self._capo = 0
        self._fingered: List[List[int]] = [[] for i in range(self._num_strings)]

    def send_msg(self, msg: Message) -> None:
        if msg.type == 'note_on' or msg.type == 'note_off':
            pos = Pos.from_note(msg.note)
            print('pos', pos)
            if pos.row >= 1 and pos.row <= 6:
                print('START FINGERED', self._fingered)
                str_index = pos.row - 1
                fret = self._capo + pos.col
                note_on = msg.type == 'note_on' and msg.velocity > 0
                str_fingered = self._fingered[str_index]
                last_fret: Optional[int] = str_fingered[-1] if len(str_fingered) > 0 else None
                fret_index = bisect_left(str_fingered, fret)
                fret_exists = len(str_fingered) > fret_index and fret_index >= 0 and str_fingered[fret_index] == fret
                fret_note = constants.STANDARD_TUNING[str_index] + fret
                if note_on:
                    print('fret index', fret_index)
                    if fret_exists:
                        pass
                    else:
                        str_fingered.insert(fret_index, fret)
                    max_fret = str_fingered[-1]
                    max_note = constants.STANDARD_TUNING[str_index] + max_fret
                    if last_fret is not None and max_fret > last_fret:
                        last_note = constants.STANDARD_TUNING[str_index] + last_fret
                        off_msg = Message(type='note_on', note=last_note, velocity=0)
                        self._midi_processed.send_msg(off_msg)
                    if last_fret is None or max_fret > last_fret:
                        on_msg = Message(type='note_on', note=max_note, velocity=msg.velocity)
                        self._midi_processed.send_msg(on_msg)
                else:
                    if fret_exists:
                        del str_fingered[fret_index]
                    if len(str_fingered) == 0:
                        off_msg = Message(type='note_on', note=fret_note, velocity=0)
                        self._midi_processed.send_msg(off_msg)
                    else:
                        max_fret = str_fingered[-1]
                        max_note = constants.STANDARD_TUNING[str_index] + max_fret
                        assert max_fret != fret
                        if max_fret < fret:
                            off_msg = Message(type='note_on', note=fret_note, velocity=0)
                            self._midi_processed.send_msg(off_msg)
                            on_msg = Message(type='note_on', note=max_note, velocity=msg.velocity)
                            self._midi_processed.send_msg(on_msg)
                print('END FINGERED', self._fingered)

    def reset(self) -> None:
        # TODO handle different number of strings
        for pos in all_pos():
            pad = self._push.get_pad(pos)
            if pos.row == 0 or pos.row == 7:
                pad.reset()
            else:
                pad.set_color(COLORS['Red'])
                pad.led_on(127)


def handle(ports: Ports) -> None:
    push = PushOutput(ports.midi_out)
    push.reset()
    try:
        guitar = Guitar(push, ports.midi_processed, tuning=constants.STANDARD_TUNING)
        guitar.reset()
        logging.info('guitar ready')
        while True:
            msg = ports.midi_in.recv_msg()
            print(msg)
            reset = msg.type == 'control_change' and msg.control == constants.ButtonCC.Master.value and msg.value == 0
            if reset:
                print('resetting')
                guitar.reset()
            else:
                guitar.send_msg(msg)
    finally:
        push.reset()


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        format='%(asctime)s %(levelname)s %(filename)s:%(lineno)d -- %(message)s',
        level=log_level
    )


def main():
    configure_logging('INFO')
    with push_ports_context(delay=constants.DEFAULT_SLEEP_SECS) as ports:
        logging.info('opened ports')
        handle(ports)


if __name__ == '__main__':
    main()
