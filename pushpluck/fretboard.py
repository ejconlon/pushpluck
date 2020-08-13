from abc import ABCMeta, abstractmethod
from bisect import bisect_left
from dataclasses import dataclass
from mido.frozen import FrozenMessage
from pushpluck.config import Config
from pushpluck.midi import is_note_on_msg
from pushpluck.component import Component, ComponentConfig
from typing import Dict, List, Optional, Tuple


@dataclass
class NoteInfo:
    velocity: int
    polytouch: Optional[int]

    @classmethod
    def pluck(cls, velocity: int) -> 'NoteInfo':
        return cls(velocity=velocity, polytouch=None)


@dataclass
class ChokeGroup:
    note_order: List[int]
    note_info: Dict[int, NoteInfo]

    @classmethod
    def empty(cls) -> 'ChokeGroup':
        return cls(note_order=[], note_info={})

    def max_note_and_info(self) -> Optional[Tuple[int, NoteInfo]]:
        max_note = self.note_order[-1] if len(self.note_order) > 0 else None
        return (max_note, self.note_info[max_note]) if max_note is not None else None

    def pluck(self, note: int, velocity: int):
        note_index = bisect_left(self.note_order, note)
        note_exists = len(self.note_order) > note_index and note_index >= 0 and self.note_order[note_index] == note
        if velocity > 0:
            if not note_exists:
                self.note_order.insert(note_index, note)
            self.note_info[note] = NoteInfo.pluck(velocity)
        else:
            if note_exists:
                del self.note_order[note_index]
            if note in self.note_info:
                del self.note_info[note]


@dataclass(frozen=True)
class StringPos:
    # Which string (0 to max strings in tuning)
    str_index: int
    # `pre_fret` here and below refer to the fret offset in semitones
    # from the visible part of the neck, not the whole neck.
    # For example, if semitones is zero, pre_fret and fret are equal.
    fret: int


@dataclass(frozen=True)
class FretMessage:
    # Position on strings/frets
    str_pos: StringPos
    # An underlying message relevant to the fretted note (on, off, aftertouch)
    msg: FrozenMessage

    def is_sounding(self) -> bool:
        return is_note_on_msg(self.msg)


@dataclass(frozen=True)
class FretboardConfig(ComponentConfig):
    tuning: List[int]
    min_velocity: int

    @classmethod
    def extract(cls, root_config: Config) -> 'FretboardConfig':
        return FretboardConfig(
            tuning=root_config.tuning,
            min_velocity=root_config.min_velocity
        )


@dataclass
class FretboardState:
    fingered: List[ChokeGroup]

    @classmethod
    def initialize(cls, config: FretboardConfig) -> 'FretboardState':
        return FretboardState(
            fingered=[ChokeGroup.empty() for i in range(len(config.tuning))]
        )


class FretboardQueries(metaclass=ABCMeta):
    @abstractmethod
    def get_note(self, str_pos: StringPos) -> int:
        raise NotImplementedError()


class Fretboard(Component[FretboardConfig, List[FretMessage]], FretboardQueries):
    @classmethod
    def extract_config(cls, root_config: Config) -> FretboardConfig:
        return FretboardConfig.extract(root_config)

    def __init__(self, config: FretboardConfig) -> None:
        super().__init__(config)
        self._state = FretboardState.initialize(config)

    def get_note(self, str_pos: StringPos) -> int:
        return self._config.tuning[str_pos.str_index] + str_pos.fret

    def _get_fret(self, str_index: int, note: int) -> int:
        return note - self._config.tuning[str_index]

    def _emit_fret_msg(self, str_index: int, msg: FrozenMessage) -> FretMessage:
        assert msg.note is not None
        return FretMessage(
            str_pos=StringPos(
                str_index=str_index,
                fret=self._get_fret(str_index, msg.note)
            ),
            msg=msg
        )

    def _clamp_velocity(self, velocity: int):
        if velocity == 0:
            return 0
        else:
            return max(velocity, self._config.min_velocity)

    def handle_note(self, str_pos: StringPos, velocity: int) -> List[FretMessage]:
        # Find out note from fret
        fret_note = self.get_note(str_pos)

        # Lookup choke group and find prev max note
        group = self._state.fingered[str_pos.str_index]
        prev_note_and_info = group.max_note_and_info()

        # Add note to group and find cur max note
        group.pluck(fret_note, velocity)
        cur_note_and_info = group.max_note_and_info()

        # Return control messages
        out_msgs: List[FretMessage] = []
        if cur_note_and_info is None:
            if prev_note_and_info is None:
                # No notes - huh? (ignore)
                pass
            else:
                # Single note mute - send off for prev
                prev_note, _ = prev_note_and_info
                off_msg = FrozenMessage(type='note_on', note=prev_note, velocity=0)
                out_msgs.append(self._emit_fret_msg(str_pos.str_index, off_msg))
        else:
            cur_note, cur_info = cur_note_and_info
            if prev_note_and_info is None:
                # Single note pluck - send on for cur
                velocity = self._clamp_velocity(cur_info.velocity)
                on_msg = FrozenMessage(type='note_on', note=cur_note, velocity=velocity)
                out_msgs.append(self._emit_fret_msg(str_pos.str_index, on_msg))
            else:
                prev_note, _ = prev_note_and_info
                if prev_note == cur_note:
                    # Movement above fretted string (ignore)
                    pass
                else:
                    # Hammer-on or pull-off
                    # Send on before off to maintain overlap for envelopes?
                    velocity = self._clamp_velocity(cur_info.velocity)
                    on_msg = FrozenMessage(type='note_on', note=cur_note, velocity=velocity)
                    out_msgs.append(self._emit_fret_msg(str_pos.str_index, on_msg))
                    off_msg = FrozenMessage(type='note_on', note=prev_note, velocity=0)
                    out_msgs.append(self._emit_fret_msg(str_pos.str_index, off_msg))
        return out_msgs

    def _note_offs(self) -> List[FretMessage]:
        out_msgs: List[FretMessage] = []
        for str_index, group in enumerate(self._state.fingered):
            cur_note_and_info = group.max_note_and_info()
            if cur_note_and_info is not None:
                cur_note, _ = cur_note_and_info
                off_msg = FrozenMessage(type='note_on', note=cur_note, velocity=0)
                out_msgs.append(self._emit_fret_msg(str_index, off_msg))
        return out_msgs

    def internal_handle_config(self, config: FretboardConfig) -> List[FretMessage]:
        out_msgs = self._note_offs()
        self._config = config
        self._state = FretboardState.initialize(config)
        return out_msgs

    def handle_reset(self) -> List[FretMessage]:
        out_msgs = self._note_offs()
        self._state = FretboardState.initialize(self._config)
        return out_msgs
