from dataclasses import dataclass
from enum import Enum, unique
from typing import Dict, List, Set, Tuple


@unique
class Step(Enum):
    Half = 1
    Whole = 2


@unique
class NoteName(Enum):
    C = 0
    Cs = 1
    D = 2
    Ds = 3
    E = 4
    F = 5
    Fs = 6
    G = 7
    Gs = 8
    A = 9
    As = 10
    B = 11


MAX_NOTES = 12


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


def add_step(base: NoteName, step: Step) -> NoteName:
    v = base.value + step.value
    if v >= MAX_NOTES:
        v -= MAX_NOTES
    return NOTE_LOOKUP[v]


class ScaleLookup:
    def __init__(self, root: NoteName, members: Set[NoteName]) -> None:
        self._root = root
        self._members = members

    def is_root(self, name: NoteName) -> bool:
        return self._root == name

    def is_member(self, name: NoteName) -> bool:
        return name in self._members


@dataclass(frozen=True)
class Scale:
    root: NoteName
    intervals: List[Step]

    def to_lookup(self) -> ScaleLookup:
        base = self.root
        members: Set[NoteName] = set()
        last = False
        for step in self.intervals:
            assert not last, f'Going beyond root {self.root} to {base}'
            members.add(base)
            base = add_step(base, step)
            if base in members:
                assert base == self.root, f'Already saw {base} but is not root {self.root}'
                last = True
        assert last, f'Scale does not end on root {self.root}'
        return ScaleLookup(self.root, members)


MAJOR_INTERVALS = [Step.Whole, Step.Whole, Step.Half, Step.Whole, Step.Whole, Step.Whole, Step.Half]
CHROMATIC_INTERVALS = [Step.Half for i in range(MAX_NOTES)]


def major_scale(root: NoteName) -> Scale:
    return Scale(root=root, intervals=MAJOR_INTERVALS)


def chromatic_scale(root: NoteName) -> Scale:
    return Scale(root=root, intervals=CHROMATIC_INTERVALS)


@unique
class ScaleMode(Enum):
    Ionian = 0
    Dorian = 1
    Phyrigian = 2
    Lydian = 3
    Mixolydian = 4
    Aeolian = 5
    Locrian = 6


def _rotate(elems: List[Step], places: int) -> List[Step]:
    return elems[places:] + elems[:places]


def mode_scale(root: NoteName, mode: ScaleMode) -> Scale:
    intervals = _rotate(MAJOR_INTERVALS, mode.value)
    return Scale(root, intervals)
