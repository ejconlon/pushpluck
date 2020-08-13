from mido.frozen import FrozenMessage
from pushpluck import constants
from pushpluck.base import Resettable
from pushpluck.config import ColorScheme, Config
from pushpluck.fretboard import Fretboard, FretMessage
from pushpluck.menu import Menu, MenuMessage
from pushpluck.midi import is_note_msg, MidiSink
from pushpluck.pads import Pads, PadsMessage
from pushpluck.push import PushOutput
from pushpluck.viewport import Viewport
from typing import List

import logging


class Plucked(Resettable):
    def __init__(
        self,
        push: PushOutput,
        midi_processed: MidiSink,
        scheme: ColorScheme,
        config: Config,
    ) -> None:
        self._push = push
        self._midi_processed = midi_processed
        self._config = config
        self._fretboard = Fretboard.construct(config)
        self._viewport = Viewport.construct(config)
        self._pads = Pads(scheme, self._fretboard, self._viewport, config)
        self._menu = Menu.construct(config)

    def handle_config(self, config: Config) -> None:
        if config != self._config:
            self._config = config
            # Send note offs first to map back to pads correctly
            fret_msgs = self._fretboard.handle_root_config(config)
            if fret_msgs is not None:
                self._handle_fret_msgs(fret_msgs)
            self._viewport.handle_root_config(config)
            # Then reset screen
            menu_msgs = self._menu.handle_root_config(config)
            if menu_msgs is not None:
                self._handle_menu_msgs(menu_msgs)
            # And reset pads
            pads_msgs = self._pads.handle_root_config(config)
            if pads_msgs is not None:
                self._handle_pads_msgs(pads_msgs)

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
                pads_msgs = self._pads.set_pad_pressed(pad_pos, fret_msg.is_sounding())
                self._handle_pads_msgs(pads_msgs)
            self._midi_processed.send_msg(fret_msg.msg)

    def _handle_menu_msgs(self, menu_msgs: List[MenuMessage]) -> None:
        lcd = self._push.get_lcd()
        for menu_msg in menu_msgs:
            lcd.display_block(menu_msg.row, menu_msg.block_col, menu_msg.text)

    def _handle_pads_msgs(self, pads_msgs: List[PadsMessage]) -> None:
        for pads_msg in pads_msgs:
            pad = self._push.get_pad(pads_msg.pos)
            if pads_msg.color is None:
                pad.led_off()
            else:
                pad.set_color(pads_msg.color)

    def reset(self) -> None:
        # Send note offs
        logging.info('plucked resetting fretboard')
        fret_msgs = self._fretboard.handle_reset()
        self._handle_fret_msgs(fret_msgs)

        # Update LCD
        logging.info('plucked resetting controller lcd')
        menu_msgs = self._menu.handle_reset()
        self._handle_menu_msgs(menu_msgs)

        # Update pads
        logging.info('plucked resetting pads')
        pads_msgs = self._pads.handle_reset()
        self._handle_pads_msgs(pads_msgs)
