from dataclasses import dataclass
from mido.frozen import FrozenMessage
from pushpluck import constants
from pushpluck.base import Resettable
from pushpluck.fretboard import Fretboard
from pushpluck.push import PushOutput, all_pos, get_color, pad_from_note
from pushpluck.midi import MidiSink, is_note_msg
from typing import List

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
        profile: Profile,
    ) -> None:
        self._push = push
        self._midi_processed = midi_processed
        self._fretboard = Fretboard(profile.tuning)

    def send_msg(self, msg: FrozenMessage) -> None:
        if is_note_msg(msg):
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
                pad.set_color(get_color('Red'))
                pad.led_on(127)


class Controller(MidiSink, Resettable):
    def __init__(
        self,
        push: PushOutput,
        midi_processed: MidiSink,
        profile: Profile
    ) -> None:
        self._push = push
        self._midi_processed = midi_processed
        self._plucked = Plucked(self._push, self._midi_processed, profile)

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
