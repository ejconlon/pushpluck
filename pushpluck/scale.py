from dataclasses import dataclass
from enum import Enum, unique
from typing import Dict, List, Set, Tuple


@unique
class NoteName(Enum):
    C = 0
    Db = 1
    D = 2
    Eb = 3
    E = 4
    F = 5
    Gb = 6
    G = 7
    Ab = 8
    A = 9
    Bb = 10
    B = 11

    def add_steps(self, steps: int) -> 'NoteName':
        v = self.value + steps
        while v < 0:
            v += MAX_NOTES
        while v >= MAX_NOTES:
            v -= MAX_NOTES
        return NOTE_LOOKUP[v]


MAX_NOTES = 12
CIRCLE_OF_FIFTHS = [NoteName[x] for x in [
    'C', 'G', 'D', 'A', 'E', 'B',
    'Gb', 'Db', 'Ab', 'Eb', 'Bb', 'F'
]]


def _build_note_lookup() -> Dict[int, NoteName]:
    d: Dict[int, NoteName] = {}
    for n in NoteName:
        d[n.value] = n
    assert len(d) == MAX_NOTES
    return d


NOTE_LOOKUP = _build_note_lookup()


def name_and_octave_from_note(note: int) -> Tuple[NoteName, int]:
    offset = note % 12
    name = NOTE_LOOKUP[offset]
    octave = note // 12 - 2
    return name, octave


class ScaleClassifier:
    def __init__(self, root: NoteName, members: Set[NoteName]) -> None:
        self._root = root
        self._members = members

    def is_root(self, name: NoteName) -> bool:
        return self._root == name

    def is_member(self, name: NoteName) -> bool:
        return name in self._members


@dataclass(frozen=True)
class Scale:
    name: str
    intervals: List[int]

    def to_classifier(self, root: NoteName) -> ScaleClassifier:
        members: Set[NoteName] = set()
        assert self.intervals[0] == 0
        last_steps = -1
        for steps in self.intervals:
            assert steps >= 0 and steps < MAX_NOTES
            assert steps > last_steps
            last_steps = steps
            note = root.add_steps(steps)
            assert note not in members
            members.add(note)
        return ScaleClassifier(root, members)


SCALES: List[Scale] = [
    Scale('Major', [0, 2, 4, 5, 7, 9, 11]),
    Scale('Minor', [0, 2, 3, 5, 7, 8, 10]),
    Scale('Dorian', [0, 2, 3, 5, 7, 9, 10]),
    Scale('Mixolydian', [0, 2, 4, 5, 7, 9, 10]),
    Scale('Lydian', [0, 2, 4, 6, 7, 9, 11]),
    Scale('Phrygian', [0, 1, 3, 5, 7, 8, 10]),
    Scale('Locrian', [0, 1, 3, 4, 7, 8, 10]),
    Scale('Diminished', [0, 1, 3, 4, 6, 7, 9, 10]),
    Scale('Whole-half', [0, 2, 3, 5, 6, 8, 9, 11]),
    Scale('Whole Tone', [0, 2, 4, 6, 8, 10]),
    Scale('Minor Blues', [0, 3, 5, 6, 7, 10]),
    Scale('Minor Pentatonic', [0, 3, 5, 7, 10]),
    Scale('Major Pentatonic', [0, 2, 4, 7, 9]),
    Scale('Harmonic Minor', [0, 2, 3, 5, 7, 8, 11]),
    Scale('Melodic Minor', [0, 2, 3, 5, 7, 9, 11]),
    Scale('Super Locrian', [0, 1, 3, 4, 6, 8, 10]),
    Scale('Bhairav', [0, 1, 4, 5, 7, 8, 11]),
    Scale('Hungarian Minor', [0, 2, 3, 6, 7, 8, 11]),
    Scale('Minor Gypsy', [0, 1, 4, 5, 7, 8, 10]),
    Scale('Hirojoshi', [0, 2, 3, 7, 8]),
    Scale('In-Sen', [0, 1, 5, 7, 10]),
    Scale('Iwato', [0, 1, 5, 6, 10]),
    Scale('Kumoi', [0, 2, 3, 7, 9]),
    Scale('Pelog', [0, 1, 3, 4, 7, 8]),
    Scale('Spanish', [0, 1, 3, 4, 5, 6, 8, 10]),
    Scale('Chromatic', [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
]

SCALE_LOOKUP: Dict[str, Scale] = {s.name: s for s in SCALES}
