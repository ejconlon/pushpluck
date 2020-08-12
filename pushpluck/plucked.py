from mido.frozen import FrozenMessage
from pushpluck import constants
from pushpluck.base import Resettable
from pushpluck.config import Config, NoteType, PadColor
from pushpluck.fretboard import Fretboard, FretMessage
from pushpluck.midi import is_note_msg, MidiSink
from pushpluck.pos import Pos
from pushpluck.push import PushOutput
from pushpluck.scale import ScaleClassifier, name_and_octave_from_note
from pushpluck.viewport import Viewport
from typing import Dict, List

import logging


class Plucked(Resettable):
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
        self._config = config
        self._pad_colors: Dict[Pos, PadColor] = {}
        self._fretboard = Fretboard.construct(config)
        self._viewport = Viewport.construct(config)
        self._reset_pad_colors()

    def handle_config(self, config: Config) -> None:
        if config != self._config:
            self._config = config
            # Send note offs first to map back to pads correctly
            fret_msgs = self._fretboard.handle_root_config(config)
            self._handle_fret_msgs(fret_msgs)
            self._viewport.handle_root_config(config)
            # Then reset pads
            self._reset_pad_colors()

    def _make_pad_color(self, classifier: ScaleClassifier, pos: Pos) -> PadColor:
        pad_color: PadColor
        str_pos = self._viewport.str_pos_from_pad_pos(pos)
        if str_pos is None:
            return PadColor.misc(False)
        else:
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
        classifier = self._config.scale.to_classifier(self._config.root)
        self._pad_colors = {
            pos: self._make_pad_color(classifier, pos) for pos in Pos.iter_all()
        }

    def _set_pad_pressed(self, pos: Pos, pressed: bool) -> None:
        pad_color = self._pad_colors[pos]
        color = pad_color.get_color(self._config.scheme, pressed)
        pad_output = self._push.get_pad(pos)
        if color is None:
            pad_output.led_off()
        else:
            pad_output.set_color(color)
            # Apparently color and led on are incompatible
            # pad_output.led_on_max()

    def handle_msg(self, msg: FrozenMessage) -> None:
        reset = msg.type == 'control_change' \
                and msg.control == constants.ButtonCC.Master.value \
                and msg.value == 0
        if reset:
            self.reset()
        elif is_note_msg(msg):
            str_pos = self._viewport.str_pos_from_input_note(msg.note)
            if str_pos is not None:
                fret_msgs = self._fretboard.handle_note(str_pos, msg.velocity)
                self._handle_fret_msgs(fret_msgs)
        elif msg.type == 'polytouch':
            # TODO send polytouch
            pass

    def _handle_fret_msgs(self, fret_msgs: List[FretMessage]) -> None:
        for fret_msg in fret_msgs:
            pad_pos = self._viewport.pad_pos_from_str_pos(fret_msg.str_pos)
            if pad_pos is not None:
                self._set_pad_pressed(pad_pos, fret_msg.is_sounding())
            self._midi_processed.send_msg(fret_msg.msg)

    def reset(self) -> None:
        # Send note offs
        logging.info('plucked resetting fretboard')
        fret_msgs = self._fretboard.handle_reset()
        self._handle_fret_msgs(fret_msgs)

        # Update LCD
        logging.info('plucked resetting controller lcd')
        lcd = self._push.get_lcd()
        for row in range(constants.DISPLAY_MAX_ROWS):
            for block_col in range(constants.DISPLAY_MAX_BLOCKS):
                lcd.display_block(row, block_col, '0123456789ABCDEF!')

        logging.info('plucked resetting pads')
        for pos in Pos.iter_all():
            self._set_pad_pressed(pos, False)
