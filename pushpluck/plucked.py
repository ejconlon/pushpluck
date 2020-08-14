from pushpluck import constants
from pushpluck.base import Resettable
from pushpluck.config import ColorScheme, Config
from pushpluck.fretboard import Fretboard, FretboardConfig, FretMessage
from pushpluck.menu import Menu, MenuMessage
from pushpluck.midi import MidiSink
from pushpluck.pads import Pads, PadsConfig, PadsMessage
from pushpluck.push import PadEvent, ButtonEvent, PushEvent, PushOutput
from pushpluck.viewport import Viewport, ViewportConfig
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
        self._fretboard = Fretboard(FretboardConfig.extract(config))
        self._viewport = Viewport(ViewportConfig.extract(config))
        self._pads = Pads(scheme, self._fretboard, self._viewport, PadsConfig.extract(config))
        self._menu = Menu()

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

    def handle_event(self, event: PushEvent) -> None:
        if isinstance(event, PadEvent):
            str_pos = self._viewport.str_pos_from_pad_pos(event.pos)
            if str_pos is not None:
                fret_msgs = self._fretboard.handle_note(str_pos, event.velocity)
                self._handle_fret_msgs(fret_msgs)
        elif isinstance(event, ButtonEvent) and event.button == constants.ButtonCC.Master:
            if event.pressed:
                self.reset()
        else:
            menu_msgs = self._menu.handle_event(event)
            self._handle_menu_msgs(menu_msgs)

    def _handle_fret_msgs(self, fret_msgs: List[FretMessage]) -> None:
        for fret_msg in fret_msgs:
            pad_pos = self._viewport.pad_pos_from_str_pos(fret_msg.str_pos)
            if pad_pos is not None:
                pads_msgs = self._pads.set_pad_pressed(pad_pos, fret_msg.is_sounding())
                self._handle_pads_msgs(pads_msgs)
            self._midi_processed.send_msg(fret_msg.msg)

    def _handle_menu_msgs(self, menu_msgs: List[MenuMessage]) -> None:
        for menu_msg in menu_msgs:
            pass
            # self._push.lcd_display_block(menu_msg.row, menu_msg.block_col, menu_msg.text)

    def _handle_pads_msgs(self, pads_msgs: List[PadsMessage]) -> None:
        for pads_msg in pads_msgs:
            if pads_msg.color is None:
                self._push.pad_led_off(pads_msg.pos)
            else:
                self._push.pad_set_color(pads_msg.pos, pads_msg.color)

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
