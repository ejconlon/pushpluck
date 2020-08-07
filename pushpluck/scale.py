from dataclasses import dataclass
from enum import Enum, unique
from typing import Dict, List, Set


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


def add_step(base: NoteName, step: Step) -> NoteName:
    v = base.value + step.value
    if v >= MAX_NOTES:
        v -= MAX_NOTES
    return NOTE_LOOKUP[v]


@dataclass(frozen=True)
class Scale:
    root: NoteName
    intervals: List[Step]

    def check(self) -> None:
        base = self.root
        seen: Set[NoteName] = set()
        last = False
        for step in self.intervals:
            assert not last, f'Going beyond root {self.root} to {base}'
            seen.add(base)
            base = add_step(base, step)
            if base in seen:
                assert base == self.root, f'Already saw {base} but is not root {self.root}'
                last = True
        assert last, f'Scale does not end on root {self.root}'


MAJOR_INTERVALS = [Step.Whole, Step.Whole, Step.Half, Step.Whole, Step.Whole, Step.Whole, Step.Half]
CHROMATIC_INTERVALS = [Step.Half for i in range(MAX_NOTES)]


def major_scale(root: NoteName) -> Scale:
    return Scale(root=root, intervals=MAJOR_INTERVALS)
