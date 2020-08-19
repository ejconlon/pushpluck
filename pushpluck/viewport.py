from dataclasses import dataclass
from pushpluck import constants
from pushpluck.base import Unit
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


class Viewport(MappedComponent[Config, ViewportConfig, Unit]):
    @classmethod
    def construct(cls, root_config: Config) -> 'Viewport':
        return cls(cls.extract_config(root_config))

    @classmethod
    def extract_config(cls, root_config: Config) -> ViewportConfig:
        return ViewportConfig.extract(root_config)

    def handle_mapped_config(self, config: ViewportConfig) -> Unit:
        self._config = config
        return Unit.instance()

    def _total_str_offset(self) -> int:
        max_str_dim = constants.NUM_PAD_ROWS if self._config.layout == Layout.Horiz else constants.NUM_PAD_COLS
        offset = 0
        blanks = max_str_dim - self._config.num_strings
        if blanks > 0:
            offset -= blanks // 2
        return offset + self._config.str_offset

    def str_pos_from_pad_pos(self, pos: Pos) -> Optional[StringPos]:
        str_index: int
        fret: int
        if self._config.layout == Layout.Horiz:
            str_index = pos.row
            fret = pos.col
        else:
            str_index = pos.col
            fret = constants.NUM_PAD_ROWS - pos.row - 1
        str_index += self._total_str_offset()
        fret += self._config.fret_offset
        if str_index < 0 or str_index >= self._config.num_strings:
            return None
        else:
            return StringPos(str_index=str_index, fret=fret)

    def str_pos_from_input_note(self, note: int) -> Optional[StringPos]:
        pos = Pos.from_input_note(note)
        return self.str_pos_from_pad_pos(pos) if pos is not None else None

    def pad_pos_from_str_pos(self, str_pos: StringPos) -> Optional[Pos]:
        str_dim = str_pos.str_index - self._total_str_offset()
        fret_dim = str_pos.fret - self._config.fret_offset
        row: int
        col: int
        if self._config.layout == Layout.Horiz:
            row = str_dim
            col = fret_dim
        else:
            row = constants.NUM_PAD_ROWS - fret_dim - 1
            col = str_dim
        if row < 0 or row >= constants.NUM_PAD_ROWS:
            return None
        elif col < 0 or col >= constants.NUM_PAD_COLS:
            return None
        else:
            return Pos(row=row, col=col)
