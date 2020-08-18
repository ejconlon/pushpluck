from enum import Enum, auto, unique
from typing import Dict, Tuple, Type, TypeVar

E = TypeVar('E', bound=Enum)


def make_enum_value_lookup(enum_type: Type[E]) -> Dict[int, E]:
    lookup: Dict[int, E] = {}
    for enum_val in enum_type.__members__.values():
        lookup[enum_val.value] = enum_val
    return lookup


# How long to sleep between midi output messages
# so we don't flood the push
DEFAULT_PUSH_DELAY = 0.0008


@unique
class ButtonIllum(Enum):
    Half = 1
    # HalfBlinkSlow = 2
    # HalfBlinkFast = 3
    Full = 4
    # FullBlinkSlow = 5
    # FullBlinkFast = 6
    Off = 0
    # TODO Use full?
    # On = 127


@unique
class ButtonColor(Enum):
    Orange = 7
    Red = 1
    Green = 19
    Yellow = 13


@unique
class KnobGroup(Enum):
    Left = auto()
    Center = auto()
    Right = auto()


@unique
class KnobCC(Enum):
    L0 = 14
    L1 = 15
    C0 = 71
    C1 = 72
    C2 = 73
    C3 = 74
    C4 = 75
    C5 = 76
    C6 = 77
    C7 = 78
    R0 = 79


KNOB_CC_VALUE_LOOKUP: Dict[int, KnobCC] = make_enum_value_lookup(KnobCC)


def knob_group_and_offset(knob: KnobCC) -> Tuple[KnobGroup, int]:
    if knob.value >= KnobCC.R0.value:
        return KnobGroup.Right, knob.value - KnobCC.R0.value
    elif knob.value >= KnobCC.C0.value:
        return KnobGroup.Center, knob.value - KnobCC.C0.value
    else:
        return KnobGroup.Left, knob.value - KnobCC.L0.value


@unique
class ButtonCC(Enum):
    TapTempo = 3
    Metronome = 9
    Undo = 119
    Delete = 118
    Double = 117
    Quantize = 116
    FixedLength = 90
    Automation = 89
    Duplicate = 88
    New = 87
    Rec = 86
    Play = 85
    Master = 28
    Stop = 29
    Left = 44
    Right = 45
    Up = 46
    Down = 47
    Volume = 114
    PanAndSend = 115
    Track = 112
    Clip = 113
    Device = 110
    Browse = 111
    StepIn = 62
    StepOut = 63
    Mute = 60
    Solo = 61
    Scales = 58
    User = 59
    Repeat = 56
    Accent = 57
    OctaveDown = 54
    OctaveUp = 55
    AddEffect = 52
    AddTrack = 53
    Note = 50
    Session = 51
    Select = 48
    Shift = 49


BUTTON_CC_VALUE_LOOKUP: Dict[int, ButtonCC] = make_enum_value_lookup(ButtonCC)


@unique
class TimeDivCC(Enum):
    TimeQuarter = 36
    TimeQuarterTriplet = 37
    TimeEighth = 38
    TimeEighthTriplet = 39
    TimeSixteenth = 40
    TimeSixteenthTriplet = 41
    TimeThirtysecond = 42
    TimeThirtysecondTriplet = 43


TIME_DIV_CC_VALUE_LOOKUP: Dict[int, TimeDivCC] = make_enum_value_lookup(TimeDivCC)


DEFAULT_PUSH_PORT_NAME = 'Ableton Push User Port'
DEFAULT_PROCESSED_PORT_NAME = 'pushpluck'
LOW_NOTE = 36
NUM_PAD_ROWS = 8
NUM_PAD_COLS = 8
NUM_PADS = NUM_PAD_ROWS * NUM_PAD_COLS
HIGH_NOTE = LOW_NOTE + NUM_PADS
PUSH_SYSEX_PREFIX = (71, 127, 21)
LOW_CHAN_CONTROL = 20
HIGH_CHAN_CONTROL = LOW_CHAN_CONTROL + NUM_PAD_COLS
LOW_GRID_CONTROL = 102
HIGH_GRID_CONTROL = LOW_GRID_CONTROL + NUM_PAD_COLS

DISPLAY_MAX_ROWS = 4
DISPLAY_MAX_BLOCKS = 4
DISPLAY_BLOCK_LEN = 17
DISPLAY_HALF_BLOCK_LEN = DISPLAY_BLOCK_LEN // 2
DISPLAY_MAX_LINE_LEN = DISPLAY_MAX_BLOCKS * DISPLAY_BLOCK_LEN
DISPLAY_BUFFER_LEN = DISPLAY_MAX_ROWS * DISPLAY_MAX_LINE_LEN

STANDARD_TUNING = [40, 45, 50, 55, 59, 64]
