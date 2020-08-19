from pushpluck.base import Resettable
from pushpluck.config import ColorScheme, Config
from pushpluck.constants import ButtonCC
from pushpluck.menu import Menu, MenuLayout
from pushpluck.midi import MidiSink
from pushpluck.pads import Pads
from pushpluck.push import ButtonEvent, PadEvent, PushEvent
from pushpluck.shadow import PushShadow

import logging


class Plucked(Resettable):
    def __init__(
        self,
        shadow: PushShadow,
        midi_processed: MidiSink,
        scheme: ColorScheme,
        layout: MenuLayout,
        config: Config,
    ) -> None:
        self._shadow = shadow
        self._midi_processed = midi_processed
        self._pads = Pads.construct(scheme, config)
        self._menu = Menu(layout, config)

    def handle_event(self, event: PushEvent) -> None:
        with self._shadow.context() as push:
            if isinstance(event, PadEvent):
                self._pads.handle_event(push, self._midi_processed, event)
            elif isinstance(event, ButtonEvent) and event.button == ButtonCC.Undo:
                if event.pressed:
                    self.reset()
            else:
                config = self._menu.handle_event(push, event)
                if config is not None:
                    self._pads.handle_config(push, self._midi_processed, config, reset=False)

    def reset(self) -> None:
        logging.info('plucked resetting')
        self._shadow.reset()
        with self._shadow.context() as push:
            config = self._menu.handle_reset(push)
            self._pads.handle_config(push, self._midi_processed, config, reset=True)
