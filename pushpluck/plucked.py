from collections import deque
from dataclasses import replace
from pushpluck.base import Resettable
from pushpluck.config import ColorScheme, Config
from pushpluck.component import ComponentMessage
from pushpluck.constants import ButtonCC
from pushpluck.menu import ClearMessage, Menu, MenuMessage, ButtonLedMessage, SemitoneShiftMessage, StringShiftMessage
from pushpluck.midi import MidiSink
from pushpluck.pads import CompositePadsConfig, Pads, PadsMessage, PadColorMessage, MidiMessage
from pushpluck.push import ButtonEvent, PadEvent, PushEvent, PushOutput
from typing import List, Optional, Sequence

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
        self._pads = Pads(scheme, CompositePadsConfig.extract(config))
        self._menu = Menu()

    def _handle_config(self, config: Config) -> List[ComponentMessage]:
        msgs: List[ComponentMessage] = []
        if config != self._config:
            self._config = config
            # First reset pads to send note offs
            pads_msgs = self._pads.handle_root_config(self._config)
            if pads_msgs is not None:
                msgs.extend(pads_msgs)
            # Then reset screen
            menu_msgs = self._menu.handle_root_config(self._config)
            if menu_msgs is not None:
                msgs.extend(menu_msgs)
        return msgs

    def handle_event(self, event: PushEvent) -> None:
        if isinstance(event, PadEvent):
            pad_msgs = self._pads.handle_event(event)
            self._handle_msgs(pad_msgs)
        elif isinstance(event, ButtonEvent) and event.button == ButtonCC.Undo:
            if event.pressed:
                self.reset()
        else:
            menu_msgs = self._menu.handle_event(event)
            self._handle_msgs(menu_msgs)

    def _handle_msgs(self, msgs: Optional[Sequence[ComponentMessage]]) -> None:
        if msgs is not None:
            work = deque(msgs)
            next_msgs: List[ComponentMessage] = []
            while len(work) > 0:
                msg = work.popleft()
                self._handle_msg(msg, next_msgs)
                work.extendleft(next_msgs)
                next_msgs.clear()

    def _handle_msg(self, msg: ComponentMessage, next_msgs: List[ComponentMessage]) -> None:
        logging.info('message %s', msg)
        if isinstance(msg, PadsMessage):
            if isinstance(msg, MidiMessage):
                self._midi_processed.send_msg(msg.msg)
            elif isinstance(msg, PadColorMessage):
                if msg.color is None:
                    self._push.pad_led_off(msg.pos)
                else:
                    self._push.pad_set_color(msg.pos, msg.color)
            else:
                raise ValueError(f'Unhandled pads message type: {msg}')
        elif isinstance(msg, MenuMessage):
            if isinstance(msg, ClearMessage):
                self._push.lcd_reset()
                self._push.chan_sel_reset()
                self._push.grid_sel_reset()
                self._push.button_reset()
            elif isinstance(msg, ButtonLedMessage):
                if msg.illum is None:
                    raise Exception(f'BUTTON OFF {msg}')
                    self._push.button_off(msg.button)
                else:
                    self._push.button_set_illum(msg.button, msg.illum)
            elif isinstance(msg, SemitoneShiftMessage):
                fret_offset = self._config.fret_offset + msg.diff
                config = replace(self._config, fret_offset=fret_offset)
                next_msgs.extend(self._handle_config(config))
            elif isinstance(msg, StringShiftMessage):
                str_offset = self._config.str_offset + msg.diff
                config = replace(self._config, str_offset=str_offset)
                next_msgs.extend(self._handle_config(config))
            else:
                print('TODO unahandled menu msg', msg)
                pass
        else:
            raise ValueError(f'Unhandled message type: {msg}')

    def reset(self) -> None:
        # Update notes and pads
        logging.info('plucked resetting notes pads')
        pads_msgs = self._pads.handle_reset()
        self._handle_msgs(pads_msgs)

        # Update menu (LCD and buttons)
        logging.info('plucked resetting lcd and buttons')
        menu_msgs = self._menu.handle_reset()
        self._handle_msgs(menu_msgs)
