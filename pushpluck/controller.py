from mido.frozen import FrozenMessage
from pushpluck import constants
from pushpluck.base import Resettable, Ref
from pushpluck.config import Config, NoteType, PadColor
from pushpluck.fretboard import Fretboard, FretboardConfig, FretMessage, StringPos
from pushpluck.midi import is_note_msg, MidiSink
from pushpluck.push import all_pos, pad_from_note, Pos, PushOutput
from pushpluck.scale import ScaleClassifier, name_and_octave_from_note
from typing import Dict, List, Optional

import logging


class Plucked(MidiSink, Resettable):
    # TODO split into create and init
    # This is really horrible
    def __init__(
        self,
        push: PushOutput,
        midi_processed: MidiSink,
        config: Config,
    ) -> None:
        self._push = push
        self._midi_processed = midi_processed
        self._config_ref = Ref(config)
        fret_config = FretboardConfig.extract(config)
        self._fretboard = Fretboard(fret_config, self.handle_fret_msgs)
        self._config_ref.add_listener(self._fretboard.listen)
        self._pad_colors: Dict[Pos, PadColor] = {}
        # Fill in initial pad colors
        self._reset_pad_colors()

    def _str_pos_from_pad(self, pos: Pos) -> Optional[StringPos]:
        # TODO support diff number of strings and orientation
        if pos.row == 0 or pos.row == 7:
            return None
        else:
            return StringPos(str_index=pos.row - 1, pre_fret=pos.col)

    def _str_pos_from_note(self, note: int) -> Optional[StringPos]:
        pos = pad_from_note(note)
        return self._str_pos_from_pad(pos) if pos is not None else None

    def _make_pad_color(self, classifier: ScaleClassifier, pos: Pos) -> PadColor:
        pad_color: PadColor
        str_pos = self._str_pos_from_pad(pos)
        if str_pos is None:
            return PadColor.misc(False)
        else:
            # TODO make real pad color
            note = self._fretboard.get_note(str_pos)
            name, _ = name_and_octave_from_note(note)
            note_type: NoteType
            if classifier.is_root(name):
                note_type = NoteType.Root
            elif classifier.is_member(name):
                note_type = NoteType.Member
            else:
                note_type = NoteType.Other
            return PadColor.note(note_type)

    def _reset_pad_colors(self) -> None:
        config = self._config_ref.get_value()
        classifier = config.scale.to_classifier(config.root)
        self._pad_colors = {
            pos: self._make_pad_color(classifier, pos) for pos in all_pos()
        }

    def _pad_from_str_pos(self, str_pos: StringPos) -> Optional[Pos]:
        # TODO account for diff num of strings and orientation
        return Pos(row=str_pos.str_index + 1, col=str_pos.pre_fret)

    def _set_pad_pressed(self, pos: Pos, pressed: bool) -> None:
        config = self._config_ref.get_value()
        pad_color = self._pad_colors[pos]
        color = pad_color.get_color(config.scheme, pressed)
        pad_output = self._push.get_pad(pos)
        if color is None:
            pad_output.led_off()
        else:
            pad_output.set_color(color)
            pad_output.led_on_max()

    def send_msg(self, msg: FrozenMessage) -> None:
        reset = msg.type == 'control_change' \
                and msg.control == constants.ButtonCC.Master.value \
                and msg.value == 0
        if reset:
            self.reset()
        elif is_note_msg(msg):
            str_pos = self._str_pos_from_note(msg.note)
            if str_pos is not None:
                self._fretboard.handle_note(str_pos, msg.velocity)
        elif msg.type == 'polytouch':
            # TODO send polytouch
            pass

    def handle_fret_msgs(self, fret_msgs: List[FretMessage]) -> None:
        for fret_msg in fret_msgs:
            fret_pos = self._pad_from_str_pos(fret_msg.str_pos)
            if fret_pos is not None:
                self._set_pad_pressed(fret_pos, fret_msg.sounding)
            self._midi_processed.send_msg(fret_msg.msg)

    def reset(self) -> None:
        # Send note offs
        logging.info('plucked resetting fretboard')
        self._fretboard.reset()

        # Update LCD
        logging.info('plucked resetting controller lcd')
        lcd = self._push.get_lcd()
        for row in range(constants.DISPLAY_MAX_ROWS):
            for block_col in range(constants.DISPLAY_MAX_BLOCKS):
                lcd.display_block(row, block_col, '0123456789ABCDEF!')

        logging.info('plucked resetting pads')
        for pos in all_pos():
            self._set_pad_pressed(pos, False)
