from pushpluck.base import Resettable
from pushpluck.config import ColorScheme, Config
from pushpluck.constants import ButtonCC
from pushpluck.menu import Menu, MenuLayout
from pushpluck.midi import MidiSink
from pushpluck.pads import Pads
from pushpluck.push import ButtonEvent, PadEvent, PushEvent, PushOutput

import logging


class Plucked(Resettable):
    def __init__(
        self,
        push: PushOutput,
        midi_processed: MidiSink,
        scheme: ColorScheme,
        layout: MenuLayout,
        config: Config,
    ) -> None:
        self._push = push
        self._midi_processed = midi_processed
        self._pads = Pads.construct(scheme, config, push, midi_processed)
        self._menu = Menu(layout, config, push)

    def handle_event(self, event: PushEvent) -> None:
        if isinstance(event, PadEvent):
            self._pads.handle_event(event)
        elif isinstance(event, ButtonEvent) and event.button == ButtonCC.Undo:
            if event.pressed:
                self.reset()
        else:
            config = self._menu.handle_event(event)
            if config is not None:
                self._pads.handle_config(config)

    def reset(self) -> None:
        logging.info('plucked resetting')
        config = self._menu.handle_reset()
        self._pads.handle_config(config)
