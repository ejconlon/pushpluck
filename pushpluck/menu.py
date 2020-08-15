from dataclasses import dataclass
from enum import Enum, auto, unique
from pushpluck.constants import ButtonCC, ButtonIllum
from pushpluck.component import NullConfigComponent
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


class MenuMessage:
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


@dataclass
class MenuState:
    cur_page: Page

    def redraw(self) -> List[MenuMessage]:
        msgs: List[MenuMessage] = []
        msgs.append(ClearMessage())
        msgs.append(ButtonLedMessage(ButtonCC.Master, ButtonIllum.Half))
        for page in Page:
            illum = ButtonIllum.Full if page == self.cur_page else ButtonIllum.Half
            msgs.append(ButtonLedMessage(page.to_button(), illum))
        return msgs

    def transition(self, new_page: Page) -> List[MenuMessage]:
        self.cur_page = new_page
        return self.redraw()

    @classmethod
    def default(cls) -> 'MenuState':
        return cls(Page.Device)


class Menu(NullConfigComponent[List[MenuMessage]]):
    def __init__(self):
        super().__init__()
        self._state = MenuState.default()

    def handle_reset(self) -> List[MenuMessage]:
        self._state = MenuState.default()
        return self._state.redraw()

    def handle_event(self, event: PushEvent) -> List[MenuMessage]:
        # TODO
        if isinstance(event, ButtonEvent):
            page = Page.from_input_button(event.button)
            if page is not None:
                if event.pressed:
                    return self._state.transition(page)
        print('TODO unhandled event', event)
        return []
