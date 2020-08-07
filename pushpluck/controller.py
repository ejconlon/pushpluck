from dataclasses import dataclass
from mido.frozen import FrozenMessage
from pushpluck import constants
from pushpluck.base import Resettable
from pushpluck.fretboard import Fretboard
from pushpluck.push import Color, Pos, PushOutput, all_pos, get_color, pad_from_note
from pushpluck.midi import MidiSink, is_note_msg, is_note_on_msg
from pushpluck.scale import Scale
from typing import List, Optional

import logging


@dataclass(frozen=True)
class Profile:
    instrument_name: str
    tuning_name: str
    tuning: List[int]


class Plucked(MidiSink, Resettable):
    def __init__(
        self,
        push: PushOutput,
        midi_processed: MidiSink,
        min_velocity: int,
        profile: Profile,
        scale: Scale
    ) -> None:
        self._push = push
        self._midi_processed = midi_processed
        self._fretboard = Fretboard(profile.tuning, min_velocity)
        self._scale = scale

    def _pad_from_note(self, note: int) -> Optional[Pos]:
        # TODO account for orientation
        return pad_from_note(note)

    def _pad_from_pre_fret(self, str_index: int, pre_fret: int) -> Optional[Pos]:
        # TODO account for orientation
        return Pos(row=str_index + 1, col=pre_fret)

    def send_msg(self, msg: FrozenMessage) -> None:
        if is_note_msg(msg):
            pos = self._pad_from_note(msg.note)
            if pos is not None and pos.row >= 1 and pos.row <= 6:
                str_index = pos.row - 1
                fret_msgs = self._fretboard.handle_note(str_index, pos.col, msg.velocity)
                for fret_msg in fret_msgs:
                    msg = fret_msg.msg
                    fret_pos = self._pad_from_pre_fret(fret_msg.str_index, fret_msg.pre_fret)
                    if fret_pos is not None:
                        color: Color
                        if is_note_on_msg(msg):
                            color = get_color('Green')
                        else:
                            color = get_color('Red')
                        self._push.get_pad(fret_pos).set_color(color)
                    self._midi_processed.send_msg(msg)
        elif msg.type == 'polytouch':
            # TODO send polytouch
            # pos = pad_from_note(msg.note)
            pass

    def reset(self) -> None:
        # Send note offs
        logging.info('plucked sending note offs')
        fret_msgs = self._fretboard.handle_reset()
        for fret_msg in fret_msgs:
            self._midi_processed.send_msg(fret_msg.msg)

        # Update UI
        # TODO handle different number of strings
        logging.info('plucked resetting ui')
        for pos in all_pos():
            pad = self._push.get_pad(pos)
            if pos.row == 0 or pos.row == 7:
                pad.reset()
            else:
                pad.set_color(get_color('Red'))


class Controller(MidiSink, Resettable):
    def __init__(
        self,
        push: PushOutput,
        midi_processed: MidiSink,
        min_velocity: int,
        profile: Profile,
        scale: Scale
    ) -> None:
        self._push = push
        self._midi_processed = midi_processed
        self._plucked = Plucked(self._push, self._midi_processed, min_velocity, profile, scale)

    def send_msg(self, msg: FrozenMessage) -> None:
        reset = msg.type == 'control_change' \
                and msg.control == constants.ButtonCC.Master.value \
                and msg.value == 0
        if reset:
            self.reset()
        else:
            self._plucked.send_msg(msg)

    def reset(self):
        logging.info('resetting controller lcd')
        lcd = self._push.get_lcd()
        for row in range(constants.DISPLAY_MAX_ROWS):
            for block_col in range(constants.DISPLAY_MAX_BLOCKS):
                lcd.display_block(row, block_col, '0123456789ABCDEF!')

        logging.info('resetting controller plucked')
        self._plucked.reset()
