from dataclasses import dataclass
from pushpluck.config import Config, Orientation
from pushpluck.fretboard import StringPos
from pushpluck.pos import Pos
from typing import Optional


@dataclass(frozen=True)
class ViewportConfig:
    num_strings: int
    orientation: Orientation

    @classmethod
    def extract(cls, root_config: Config) -> 'ViewportConfig':
        return ViewportConfig(
            num_strings=len(root_config.tuning),
            orientation=root_config.orientation
        )


@dataclass
class ViewportState:
    str_offset: int
    fret_offset: int

    @classmethod
    def initialize(cls, config: ViewportConfig) -> 'ViewportState':
        return ViewportState(
            str_offset=0,
            fret_offset=0
        )


class Viewport:
    @classmethod
    def construct(cls, root_config: Config) -> 'Viewport':
        config = ViewportConfig.extract(root_config)
        return cls(config)

    def __init__(self, config: ViewportConfig) -> None:
        self._config = config
        self._state = ViewportState.initialize(config)

    def handle_config(self, config: ViewportConfig) -> None:
        if config != self._config:
            self._config = config
            self.handle_reset()

    def handle_root_config(self, root_config: Config) -> None:
        config = ViewportConfig.extract(root_config)
        self.handle_config(config)

    def handle_reset(self) -> None:
        self._state = ViewportState.initialize(self._config)

    def shift_str_offset(self, diff: int) -> None:
        self._state.str_offset += diff

    def shift_fret_offset(self, diff: int) -> None:
        self._state.fret_offset += diff

    def str_pos_from_pad_pos(self, pos: Pos) -> Optional[StringPos]:
        # TODO support diff number of strings and orientation
        assert self._config.num_strings == 6
        assert self._config.orientation == Orientation.Left
        assert self._state.str_offset == 0
        assert self._state.fret_offset == 0
        if pos.row == 0 or pos.row == 7:
            return None
        else:
            return StringPos(str_index=pos.row - 1, fret=pos.col)

    def str_pos_from_input_note(self, note: int) -> Optional[StringPos]:
        pos = Pos.from_input_note(note)
        return self.str_pos_from_pad_pos(pos) if pos is not None else None

    def pad_pos_from_str_pos(self, str_pos: StringPos) -> Optional[Pos]:
        # TODO support diff number of strings and orientation
        assert self._config.num_strings == 6
        assert self._config.orientation == Orientation.Left
        assert self._state.str_offset == 0
        assert self._state.fret_offset == 0
        return Pos(row=str_pos.str_index + 1, col=str_pos.fret)
