from dataclasses import dataclass
from enum import Enum, auto, unique
from pushpluck.base import Void
from pushpluck.constants import ButtonCC, ButtonIllum
from pushpluck.component import Component, ComponentMessage
from pushpluck.push import PushEvent, ButtonEvent
from typing import List, Optional


@unique
class Page(Enum):
    Device = auto()
    Scales = auto()
    Browse = auto()

    def to_button(self) -> ButtonCC:
        if self == Page.Device:
            return ButtonCC.Device
        elif self == Page.Browse:
            return ButtonCC.Browse
        elif self == Page.Scales:
            return ButtonCC.Scales
        else:
            raise ValueError()

    @staticmethod
    def from_input_button(button: ButtonCC) -> Optional['Page']:
        if button == ButtonCC.Device:
            return Page.Device
        elif button == ButtonCC.Browse:
            return Page.Browse
        elif button == ButtonCC.Scales:
            return Page.Scales
        else:
            return None


class MenuMessage(ComponentMessage):
    pass


@dataclass(frozen=True)
class ClearMessage(MenuMessage):
    pass


@dataclass(frozen=True)
class HalfBlockMessage(MenuMessage):
    row: int
    block_col: int
    sub_block: int
    text: str


@dataclass(frozen=True)
class FullBlockMessage(MenuMessage):
    row: int
    block_col: int
    text: str


@dataclass(frozen=True)
class ButtonLedMessage(MenuMessage):
    button: ButtonCC
    illum: Optional[ButtonIllum]


@dataclass(frozen=True)
class SemitoneShiftMessage(MenuMessage):
    diff: int


@dataclass(frozen=True)
class StringShiftMessage(MenuMessage):
    diff: int


ACTIVE_BUTTONS: List[ButtonCC] = [
    ButtonCC.Undo,
    ButtonCC.Left,
    ButtonCC.Right,
    ButtonCC.Up,
    ButtonCC.Down,
    ButtonCC.OctaveDown,
    ButtonCC.OctaveUp
]


@dataclass
class MenuState:
    cur_page: Page

    def redraw(self) -> List[MenuMessage]:
        msgs: List[MenuMessage] = []
        msgs.append(ClearMessage())
        for page in Page:
            illum = ButtonIllum.Full if page == self.cur_page else ButtonIllum.Half
            msgs.append(ButtonLedMessage(page.to_button(), illum))
        for button in ACTIVE_BUTTONS:
            msgs.append(ButtonLedMessage(button, ButtonIllum.Half))
        return msgs

    def transition(self, new_page: Page) -> List[MenuMessage]:
        self.cur_page = new_page
        return self.redraw()

    @classmethod
    def default(cls) -> 'MenuState':
        return cls(Page.Device)


class Menu(Component[Void, PushEvent, MenuMessage]):
    def __init__(self):
        self._state = MenuState.default()

    def handle_reset(self) -> List[MenuMessage]:
        self._state = MenuState.default()
        return self._state.redraw()

    def handle_event(self, event: PushEvent) -> List[MenuMessage]:
        if isinstance(event, ButtonEvent):
            if event.pressed:
                page = Page.from_input_button(event.button)
                if page is not None:
                    return self._state.transition(page)
                elif event.button == ButtonCC.OctaveDown:
                    return [SemitoneShiftMessage(-12)]
                elif event.button == ButtonCC.OctaveUp:
                    return [SemitoneShiftMessage(12)]
                elif event.button == ButtonCC.Left:
                    return [SemitoneShiftMessage(-1)]
                elif event.button == ButtonCC.Right:
                    return [SemitoneShiftMessage(1)]
                elif event.button == ButtonCC.Up:
                    return [StringShiftMessage(1)]
                elif event.button == ButtonCC.Down:
                    return [StringShiftMessage(-1)]
            else:
                return []
        return []

    def handle_config(self, config: Void) -> List[MenuMessage]:
        return config.absurd()
