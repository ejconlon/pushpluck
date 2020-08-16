from dataclasses import dataclass
from pushpluck import constants
from pushpluck.component import Component, ComponentConfig, NullComponentMessage
from pushpluck.config import Config, Orientation
from pushpluck.fretboard import StringPos
from pushpluck.pos import Pos
from typing import List, Optional


@dataclass(frozen=True)
class ViewportConfig(ComponentConfig):
    num_strings: int
    orientation: Orientation
    str_offset: int
    fret_offset: int

    @classmethod
    def extract(cls, root_config: Config) -> 'ViewportConfig':
        return cls(
            num_strings=len(root_config.tuning),
            orientation=root_config.orientation,
            str_offset=root_config.str_offset,
            fret_offset=root_config.fret_offset
        )


class Viewport(Component[ViewportConfig, NullComponentMessage]):
    @classmethod
    def extract_config(cls, root_config: Config) -> ViewportConfig:
        return ViewportConfig.extract(root_config)

    def __init__(self, config: ViewportConfig) -> None:
        super().__init__(config)

    def internal_handle_config(self, config: ViewportConfig) -> List[NullComponentMessage]:
        self._config = config
        return []

    def str_pos_from_pad_pos(self, pos: Pos) -> Optional[StringPos]:
        # TODO support diff number of strings and orientation
        assert self._config.num_strings == 6
        assert self._config.orientation == Orientation.Left
        assert self._config.str_offset == 0
        if pos.row == 0 or pos.row == 7:
            return None
        else:
            str_index = pos.row - 1
            fret = pos.col + self._config.fret_offset
            return StringPos(str_index=str_index, fret=fret)

    def str_pos_from_input_note(self, note: int) -> Optional[StringPos]:
        pos = Pos.from_input_note(note)
        return self.str_pos_from_pad_pos(pos) if pos is not None else None

    def pad_pos_from_str_pos(self, str_pos: StringPos) -> Optional[Pos]:
        # TODO support diff number of strings and orientation
        assert self._config.num_strings == 6
        assert self._config.orientation == Orientation.Left
        assert self._config.str_offset == 0
        row = str_pos.str_index + 1 - self._config.str_offset
        col = str_pos.fret - self._config.fret_offset
        if row < 0 or row >= constants.NUM_PAD_ROWS:
            return None
        elif col < 0 or col >= constants.NUM_PAD_COLS:
            return None
        else:
            return Pos(row=row, col=col)
