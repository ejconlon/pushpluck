from pushpluck.scale import SCALE_LOOKUP, name_and_octave_from_note, NoteName

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
    "scale_name, root_name, cand_name, is_root, is_member",
    [
        ('Major', NoteName.C, NoteName.C, True, True),
        ('Major', NoteName.C, NoteName.A, False, True),
        ('Major', NoteName.C, NoteName.Bb, False, False),
        ('Chromatic', NoteName.C, NoteName.C, True, True),
        ('Chromatic', NoteName.C, NoteName.A, False, True),
        ('Chromatic', NoteName.C, NoteName.Bb, False, True),
        ('Minor', NoteName.A, NoteName.C, False, True),
        ('Minor', NoteName.A, NoteName.A, True, True),
        ('Minor', NoteName.A, NoteName.Bb, False, False)
    ]
)
def test_scale(
    scale_name: str,
    root_name: NoteName,
    cand_name: NoteName,
    is_root: bool,
    is_member: bool
) -> None:
    scale = SCALE_LOOKUP[scale_name]
    classifier = scale.to_classifier(root_name)
    assert is_root == classifier.is_root(cand_name)
    assert is_member == classifier.is_member(cand_name)
