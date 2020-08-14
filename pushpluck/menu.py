from dataclasses import dataclass
from pushpluck import constants
from pushpluck.component import NullConfigComponent
from pushpluck.push import PushEvent
from typing import List, Optional


@dataclass
class MenuState:
    @classmethod
    def default(cls) -> 'MenuState':
        return cls()


class MenuMessage:
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
    button: constants.ButtonCC
    illum: Optional[constants.ButtonIllum]


class Menu(NullConfigComponent[List[MenuMessage]]):
    def __init__(self):
        super().__init__()
        self._state = MenuState.default()

    def handle_reset(self) -> List[MenuMessage]:
        # TODO actually redraw screen
        menu_msgs: List[MenuMessage] = []
        for row in range(constants.DISPLAY_MAX_ROWS):
            for block_col in range(constants.DISPLAY_MAX_BLOCKS):
                menu_msgs.append(FullBlockMessage(row, block_col, '0123456789ABCDEF!'))
        return menu_msgs

    def handle_event(self, event: PushEvent) -> List[MenuMessage]:
        # TODO
        # print(event)
        return []
