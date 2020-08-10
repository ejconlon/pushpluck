from dataclasses import dataclass
from mido.frozen import FrozenMessage
from pushpluck import constants
from pushpluck.base import ResetConfigurable, Resettable, Ref
# from pushpluck.color import COLORS, Color
from pushpluck.config import Config, PadColor
from pushpluck.fretboard import Fretboard, FretboardConfig, FretMessage
from pushpluck.midi import is_note_msg, MidiSink
from pushpluck.push import all_pos, pad_from_note, Pos, LcdOutput, PadOutput, PushOutput
# from pushpluck.scale import NoteName, Scale
# from pushpluck.pads import ColorScheme
from typing import Dict, List, Optional

import logging


@dataclass
class PadState:
    pad_color: PadColor
    pad_output: PadOutput
    pressed: bool


# TODO should be reset when config changes
class PushPluckOutput(ResetConfigurable[Config]):
    def __init__(self, push: PushOutput, config: Config) -> None:
        super().__init__(config)
        self._pads: Dict[Pos, PadState] = {
            pos: PadState(self._make_pad_color(pos), push.get_pad(pos), False) for pos in all_pos()
        }
        self._lcd = push.get_lcd()

    def set_pad_pressed(self, pos: Pos, pressed: bool) -> None:
        config = self.get_config()
        pad_state = self._pads[pos]
        color = pad_state.pad_color.get_color(config.scheme, pressed)
        if color is None:
            pad_state.pad_output.led_off()
        else:
            pad_state.pad_output.set_color(color)
            pad_state.pad_output.led_on_max()

    def get_lcd(self) -> LcdOutput:
        return self._lcd

    def pre_reset(self) -> None:
        pass

    def _make_pad_color(self, pos: Pos) -> PadColor:
        pad_color: PadColor
        if pos.row == 0 or pos.row == 7:
            return PadColor.misc(False)
        else:
            return PadColor.misc(True)

    def post_reset(self) -> None:
        for pos in all_pos():
            pad_color = self._make_pad_color(pos)
            self._pads[pos].pad_color = pad_color


class Plucked(MidiSink, Resettable):
    # TODO split into create and init
    # This is really horrible
    def __init__(
        self,
        output: PushPluckOutput,
        midi_processed: MidiSink,
        config_ref: Ref[Config]
    ) -> None:
        self._output = output
        self._midi_processed = midi_processed
        fret_config = FretboardConfig.extract(config_ref.get_value())
        self._fretboard = Fretboard(fret_config, self.handle_fret_msgs)
        config_ref.add_listener(lambda _, config: self._fretboard.configure(FretboardConfig.extract(config)))

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
                self._fretboard.handle_note(
                    str_index=pos.row - 1,
                    pre_fret=pos.col,
                    velocity=msg.velocity
                )
        elif msg.type == 'polytouch':
            # TODO send polytouch
            # pos = pad_from_note(msg.note)
            pass

    def handle_fret_msgs(self, fret_msgs: List[FretMessage]) -> None:
        for fret_msg in fret_msgs:
            fret_pos = self._pad_from_pre_fret(fret_msg.str_index, fret_msg.pre_fret)
            if fret_pos is not None:
                self._output.set_pad_pressed(fret_pos, fret_msg.sounding)
            self._midi_processed.send_msg(fret_msg.msg)

    def reset(self) -> None:
        # Send note offs
        logging.info('plucked resetting fretboard')
        self._fretboard.reset()

        # Update LCD
        logging.info('plucked resetting controller lcd')
        lcd = self._output.get_lcd()
        for row in range(constants.DISPLAY_MAX_ROWS):
            for block_col in range(constants.DISPLAY_MAX_BLOCKS):
                lcd.display_block(row, block_col, '0123456789ABCDEF!')

        # Update pads
        # # TODO handle different number of strings
        # logging.info('plucked resetting ui')
        # for pos in all_pos():
        #     pad = self._push.get_pad(pos)
        #     if pos.row == 0 or pos.row == 7:
        #         pad.reset()
        #     else:
        #         pad.set_color(COLORS['Red'])


class Controller(MidiSink, Resettable):
    def __init__(
        self,
        push: PushOutput,
        midi_processed: MidiSink,
        config: Config
    ) -> None:
        self._config_ref = Ref(config)
        self._output = PushPluckOutput(push, config)
        self._plucked = Plucked(self._output, midi_processed, self._config_ref)

    def send_msg(self, msg: FrozenMessage) -> None:
        reset = msg.type == 'control_change' \
                and msg.control == constants.ButtonCC.Master.value \
                and msg.value == 0
        if reset:
            self.reset()
        else:
            self._plucked.send_msg(msg)

    def reset(self):
        self._plucked.reset()
