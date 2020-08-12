from dataclasses import dataclass
from pushpluck import constants
from typing import Generator, Optional


@dataclass(frozen=True)
class Pos:
    """
    (0,0) is bottom left corner (lowest note)
    (7,7) is top right corner (highest note)
    """

    row: int
    col: int

    def __iter__(self) -> Generator[int, None, None]:
        yield self.row
        yield self.col

    def to_index(self) -> int:
        return constants.NUM_PAD_COLS * self.row + self.col

    def to_note(self) -> int:
        return constants.LOW_NOTE + self.to_index()

    @staticmethod
    def from_input_note(note: int) -> 'Optional[Pos]':
        if note < constants.LOW_NOTE or note >= constants.HIGH_NOTE:
            return None
        else:
            index = note - constants.LOW_NOTE
            row = index // constants.NUM_PAD_COLS
            col = index % constants.NUM_PAD_COLS
            return Pos(row=row, col=col)

    @staticmethod
    def iter_all() -> 'Generator[Pos, None, None]':
        """ Iterator from lowest to highest pos """
        for row in range(constants.NUM_PAD_ROWS):
            for col in range(constants.NUM_PAD_COLS):
                yield Pos(row, col)
