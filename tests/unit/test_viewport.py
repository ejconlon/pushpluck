from dataclasses import replace
from enum import Enum, auto
from pushpluck.config import Layout
from pushpluck.fretboard import StringPos
from pushpluck.pos import Pos
from pushpluck.viewport import Viewport, ViewportConfig
from typing import Optional

import pytest


DEFAULT_CONFIG = ViewportConfig(6, Layout.Horiz, 0, 0)
SHIFT_CONFIG = replace(DEFAULT_CONFIG, str_offset=1, fret_offset=1)
VERT_CONFIG = replace(DEFAULT_CONFIG, layout=Layout.Vert)


class Direction(Enum):
    Forward = auto()
    Backward = auto()
    Both = auto()


@pytest.mark.parametrize(
    'config, pad_pos, str_pos, direction',
    [
        (DEFAULT_CONFIG, Pos(0, 0), None, Direction.Forward),
        (DEFAULT_CONFIG, Pos(1, 1), StringPos(0, 1), Direction.Both),
        (DEFAULT_CONFIG, Pos(1, -1), StringPos(0, -1), Direction.Forward),
        (DEFAULT_CONFIG, Pos(6, 2), StringPos(5, 2), Direction.Both),
        (DEFAULT_CONFIG, Pos(7, 1), None, Direction.Forward),
        (SHIFT_CONFIG, Pos(0, 0), StringPos(0, 1), Direction.Both),
        (VERT_CONFIG, Pos(0, 0), None, Direction.Forward),
        (VERT_CONFIG, Pos(1, 1), StringPos(0, 6), Direction.Both),
    ]
)
def test_viewport(
    config: ViewportConfig,
    pad_pos: Optional[Pos],
    str_pos: Optional[StringPos],
    direction: Direction
) -> None:
    viewport = Viewport(config)
    # Validate inputs
    if direction == Direction.Forward:
        assert pad_pos is not None
    elif direction == Direction.Backward:
        assert str_pos is not None
    else:
        assert pad_pos is not None
        assert str_pos is not None
    # Test forward
    if pad_pos is not None and direction != Direction.Backward:
        actual_str_pos = viewport.str_pos_from_pad_pos(pad_pos)
        assert actual_str_pos == str_pos
    # Test backward
    if str_pos is not None and direction != Direction.Forward:
        actual_pad_pos = viewport.pad_pos_from_str_pos(str_pos)
        assert actual_pad_pos == pad_pos
