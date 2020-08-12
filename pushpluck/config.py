from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto, unique
from pushpluck import constants
from pushpluck.color import COLORS, Color
from pushpluck.scale import SCALE_LOOKUP, NoteName, Scale
from typing import List, Optional, TypeVar

T = TypeVar('T')


@unique
class NoteType(Enum):
    Root = auto()
    Member = auto()
    Other = auto()


@dataclass(frozen=True)
class ColorScheme:
    root_note: Color
    member_note: Color
    other_note: Color
    pressed_note: Color
    misc_pressed: Color
    control: Color
    control_pressed: Color


class PadColor(metaclass=ABCMeta):
    @abstractmethod
    def get_color(self, scheme: ColorScheme, pressed: bool) -> Optional[Color]:
        raise NotImplementedError()

    @staticmethod
    def note(note_type: NoteType) -> 'PadColor':
        return NotePadColor(note_type)

    @staticmethod
    def misc(pressable: bool) -> 'PadColor':
        return MiscPadColor(pressable)

    @staticmethod
    def control() -> 'PadColor':
        return ControlPadColor()


@dataclass(frozen=True)
class NotePadColor(PadColor):
    note_type: NoteType

    def get_color(self, scheme: ColorScheme, pressed: bool) -> Optional[Color]:
        if pressed:
            return scheme.pressed_note
        else:
            if self.note_type == NoteType.Root:
                return scheme.root_note
            elif self.note_type == NoteType.Member:
                return scheme.member_note
            elif self.note_type == NoteType.Other:
                return scheme.other_note
            else:
                raise ValueError()


@dataclass(frozen=True)
class MiscPadColor(PadColor):
    pressable: bool

    def get_color(self, scheme: ColorScheme, pressed: bool) -> Optional[Color]:
        return scheme.misc_pressed if pressed and self.pressable else None


@dataclass(frozen=True)
class ControlPadColor(PadColor):
    def get_color(self, scheme: ColorScheme, pressed: bool) -> Optional[Color]:
        return scheme.control_pressed if pressed else scheme.control


@unique
class Orientation(Enum):
    Left = auto()
    Up = auto()


@dataclass(frozen=True)
class Profile:
    instrument_name: str
    tuning_name: str
    tuning: List[int]
    orientation: Orientation


@dataclass(frozen=True)
class Config:
    instrument_name: str
    tuning_name: str
    tuning: List[int]
    orientation: Orientation
    scale: Scale
    root: NoteName
    scheme: ColorScheme
    min_velocity: int


def init_config(min_velocity: int) -> Config:
    return Config(
        instrument_name='Guitar',
        tuning_name='Standard',
        tuning=constants.STANDARD_TUNING,
        orientation=Orientation.Left,
        scale=SCALE_LOOKUP['Major'],
        root=NoteName.C,
        scheme=ColorScheme(
            root_note=COLORS['Blue'],
            member_note=COLORS['White'],
            other_note=COLORS['Gray'],
            pressed_note=COLORS['Green'],
            misc_pressed=COLORS['Sky'],
            control=COLORS['Yellow'],
            control_pressed=COLORS['Green']
        ),
        min_velocity=min_velocity
    )
