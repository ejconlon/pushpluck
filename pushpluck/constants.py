from enum import Enum, unique
from typing import Dict, Type, TypeVar


E = TypeVar('E', bound=Enum)


def make_enum_value_lookup(enum_type: Type[E]) -> Dict[int, E]:
    lookup: Dict[int, E] = {}
    for enum_val in enum_type.__members__.values():
        lookup[enum_val.value] = enum_val
    return lookup


# How long to sleep between midi output messages
# so we don't flood the push
DEFAULT_SLEEP_SECS = 0.0008


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
    TimeQuarter = 36
    TimeQuarterTriplet = 37
    TimeEighth = 38
    TimeEighthTriplet = 39
    TimeSixteenth = 40
    TimeSixteenthTriplet = 41
    TimeThirtysecond = 42
    TimeThirtysecondTriplet = 43


BUTTON_CC_VALUE_LOOKUP: Dict[int, ButtonCC] = make_enum_value_lookup(ButtonCC)


DEFAULT_PUSH_PORT_NAME = 'Ableton Push User Port'
DEFAULT_PROCESSED_PORT_NAME = 'pushpluck'
LOW_NOTE = 36
NUM_PAD_ROWS = 8
NUM_PAD_COLS = 8
NUM_PADS = NUM_PAD_ROWS * NUM_PAD_COLS
HIGH_NOTE = LOW_NOTE + NUM_PADS
ABLETON_SYSEX_PREFIX = (71, 127, 21)
MAX_LINE_LEN = 68

STANDARD_TUNING = [40, 45, 50, 55, 59, 64]
