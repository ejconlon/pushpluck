from dataclasses import dataclass
from pushpluck import constants
from pushpluck.component import NullConfigComponent
from typing import List


@dataclass
class MenuState:
    @classmethod
    def default(cls) -> 'MenuState':
        return cls()


@dataclass(frozen=True)
class MenuMessage:
    row: int
    block_col: int
    text: str


class Menu(NullConfigComponent[List[MenuMessage]]):
    def __init__(self):
        super().__init__()
        self._state = MenuState.default()

    def handle_reset(self) -> List[MenuMessage]:
        # TODO actually redraw screen
        menu_msgs: List[MenuMessage] = []
        for row in range(constants.DISPLAY_MAX_ROWS):
            for block_col in range(constants.DISPLAY_MAX_BLOCKS):
                menu_msgs.append(MenuMessage(row, block_col, '0123456789ABCDEF!'))
        return menu_msgs
