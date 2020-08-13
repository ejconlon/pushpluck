from dataclasses import dataclass
from pushpluck import constants
from pushpluck.component import ComponentState, NullConfig, NullConfigComponent
from typing import List


class Profiles:
    pass


@dataclass
class MenuState(ComponentState[NullConfig]):
    pass

    @classmethod
    def initialize(cls, config: NullConfig) -> 'MenuState':
        return cls()


@dataclass(frozen=True)
class MenuMessage:
    row: int
    block_col: int
    text: str


class Menu(NullConfigComponent[MenuState, List[MenuMessage]]):
    @classmethod
    def initialize_state(cls, config: NullConfig) -> MenuState:
        return MenuState.initialize(config)

    def handle_reset(self) -> List[MenuMessage]:
        # TODO actually redraw screen
        menu_msgs: List[MenuMessage] = []
        for row in range(constants.DISPLAY_MAX_ROWS):
            for block_col in range(constants.DISPLAY_MAX_BLOCKS):
                menu_msgs.append(MenuMessage(row, block_col, '0123456789ABCDEF!'))
        return menu_msgs
