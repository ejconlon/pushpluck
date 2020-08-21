from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto, unique
from pushpluck import constants
from pushpluck.base import MatchException
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
    primary_note: Color
    disabled_note: Color
    linked_note: Color
    misc_pressed: Color
    control: Color
    control_pressed: Color


@unique
class VisState(Enum):
    Off = auto()
    OnPrimary = auto()
    OnDisabled = auto()
    OnLinked = auto()

    @property
    def primary(self) -> bool:
        return self == VisState.OnPrimary

    @property
    def active(self) -> bool:
        return self != VisState.Off

    @property
    def enabled(self) -> bool:
        return self != VisState.OnDisabled


class PadColorMapper(metaclass=ABCMeta):
    @abstractmethod
    def get_color(self, scheme: ColorScheme, vis: VisState) -> Optional[Color]:
        raise NotImplementedError()

    @staticmethod
    def note(note_type: NoteType) -> 'NotePadColorMapper':
        return NotePadColorMapper(note_type)

    @staticmethod
    def misc(pressable: bool) -> 'MiscPadColorMapper':
        return MiscPadColorMapper(pressable)

    @staticmethod
    def control() -> 'ControlPadColorMapper':
        return ControlPadColorMapper()


@dataclass(frozen=True)
class NotePadColorMapper(PadColorMapper):
    note_type: NoteType

    def get_color(self, scheme: ColorScheme, vis: VisState) -> Optional[Color]:
        if vis == VisState.OnPrimary:
            return scheme.primary_note
        elif vis == VisState.OnDisabled:
            return scheme.disabled_note
        elif vis == VisState.OnLinked:
            return scheme.linked_note
        else:
            if self.note_type == NoteType.Root:
                return scheme.root_note
            elif self.note_type == NoteType.Member:
                return scheme.member_note
            elif self.note_type == NoteType.Other:
                return scheme.other_note
            else:
                raise MatchException(self.note_type)


@dataclass(frozen=True)
class MiscPadColorMapper(PadColorMapper):
    pressable: bool

    def get_color(self, scheme: ColorScheme, vis: VisState) -> Optional[Color]:
        return scheme.misc_pressed if vis.active and self.pressable else None


@dataclass(frozen=True)
class ControlPadColorMapper(PadColorMapper):
    def get_color(self, scheme: ColorScheme, vis: VisState) -> Optional[Color]:
        return scheme.control_pressed if vis.active else scheme.control


@unique
class Layout(Enum):
    Horiz = auto()
    Vert = auto()


@unique
class PlayMode(Enum):
    Tap = auto()
    # Pick = auto()
    Poly = auto()
    Mono = auto()


@unique
class ChannelMode(Enum):
    Single = auto()
    Multi = auto()


# TODO This needs to be hierarchical
# Each instrument has a default orientation and tuning
# As well as multiple possible tunings
# @dataclass(frozen=True)
# class Profile:
#     instrument_name: str
#     tuning_name: str
#     tuning: List[int]
#     orientation: Orientation


@dataclass(frozen=True)
class Config:
    instrument_name: str
    tuning_name: str
    tuning: List[int]
    layout: Layout
    play_mode: PlayMode
    chan_mode: ChannelMode
    scale: Scale
    root: NoteName
    min_velocity: int
    str_offset: int
    fret_offset: int


def init_config(min_velocity: int) -> Config:
    return Config(
        instrument_name='Guitar',
        tuning_name='Standard',
        tuning=constants.STANDARD_TUNING,
        layout=Layout.Horiz,
        play_mode=PlayMode.Tap,
        chan_mode=ChannelMode.Single,
        scale=SCALE_LOOKUP['Major'],
        root=NoteName.C,
        min_velocity=min_velocity,
        str_offset=0,
        fret_offset=0
    )


def default_scheme() -> ColorScheme:
    return ColorScheme(
        root_note=COLORS['Blue'],
        member_note=COLORS['White'],
        other_note=COLORS['Black'],
        primary_note=COLORS['Green'],
        disabled_note=COLORS['Red'],
        linked_note=COLORS['Lime'],
        misc_pressed=COLORS['Sky'],
        control=COLORS['Yellow'],
        control_pressed=COLORS['Pink']
    )
