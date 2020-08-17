from dataclasses import dataclass
from pushpluck import constants
from pushpluck.component import MappedComponent, MappedComponentConfig
from pushpluck.config import Config, Layout
from pushpluck.fretboard import StringPos
from pushpluck.pos import Pos
from typing import Optional


@dataclass(frozen=True)
class ViewportConfig(MappedComponentConfig):
    num_strings: int
    layout: Layout
    str_offset: int
    fret_offset: int

    @classmethod
    def extract(cls, root_config: Config) -> 'ViewportConfig':
        return cls(
            num_strings=len(root_config.tuning),
            layout=root_config.layout,
            str_offset=root_config.str_offset,
            fret_offset=root_config.fret_offset
        )


class Viewport(MappedComponent[Config, ViewportConfig, None]):
    @classmethod
    def construct(cls, root_config: Config) -> 'Viewport':
        return cls(cls.extract_config(root_config))

    @classmethod
    def extract_config(cls, root_config: Config) -> ViewportConfig:
        return ViewportConfig.extract(root_config)

    def handle_mapped_config(self, config: ViewportConfig) -> None:
        self._config = config

    def str_pos_from_pad_pos(self, pos: Pos) -> Optional[StringPos]:
        # TODO support diff number of strings and orientation
        assert self._config.num_strings == 6
        assert self._config.layout == Layout.Horiz
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
        assert self._config.layout == Layout.Horiz
        assert self._config.str_offset == 0
        row = str_pos.str_index + 1 - self._config.str_offset
        col = str_pos.fret - self._config.fret_offset
        if row < 0 or row >= constants.NUM_PAD_ROWS:
            return None
        elif col < 0 or col >= constants.NUM_PAD_COLS:
            return None
        else:
            return Pos(row=row, col=col)
