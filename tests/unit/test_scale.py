from pushpluck.scale import (chromatic_scale, major_scale, mode_scale, name_and_octave_from_note, NoteName, Scale,
                             ScaleMode)

import pytest


@pytest.mark.parametrize(
    "note, name, octave",
    [
        (0, NoteName.C, -2),
        (24, NoteName.C, 0),
        (60, NoteName.C, 3),
        (127, NoteName.G, 8)
    ]
)
def test_note_conversion(note: int, name: NoteName, octave: int) -> None:
    actual_name, actual_octave = name_and_octave_from_note(note)
    assert actual_name == name
    assert actual_octave == octave


@pytest.mark.parametrize(
    "scale, name, is_root, is_member",
    [
        (major_scale(NoteName.C), NoteName.C, True, True),
        (major_scale(NoteName.C), NoteName.A, False, True),
        (major_scale(NoteName.C), NoteName.As, False, False),
        (chromatic_scale(NoteName.C), NoteName.C, True, True),
        (chromatic_scale(NoteName.C), NoteName.A, False, True),
        (chromatic_scale(NoteName.C), NoteName.As, False, True),
        (mode_scale(NoteName.A, ScaleMode.Aeolian), NoteName.C, False, True),
        (mode_scale(NoteName.A, ScaleMode.Aeolian), NoteName.A, True, True),
        (mode_scale(NoteName.A, ScaleMode.Aeolian), NoteName.As, False, False)
    ]
)
def test_scale(scale: Scale, name: NoteName, is_root: bool, is_member: bool) -> None:
    lookup = scale.to_lookup()
    assert is_root == lookup.is_root(name)
    assert is_member == lookup.is_member(name)
