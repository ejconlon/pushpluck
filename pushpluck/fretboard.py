from bisect import bisect_left
from dataclasses import dataclass
from mido.frozen import FrozenMessage
from pushpluck.base import ResetConfigurable
from pushpluck.config import Config
from typing import Callable, Dict, List, Optional, Tuple


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
    pre_fret: int


@dataclass(frozen=True)
class FretMessage:
    # Semitone offset from configured tuning
    semitones: int
    # Position on strings/frets
    str_pos: StringPos
    # If the note is making sound
    sounding: bool
    # An underlying message relevant to the fretted note (on, off, aftertouch)
    msg: FrozenMessage

    @property
    def fret(self) -> int:
        return self.str_pos.pre_fret + self.semitones


@dataclass(frozen=True)
class FretboardConfig:
    tuning: List[int]
    min_velocity: int

    @classmethod
    def extract(cls, config: Config) -> 'FretboardConfig':
        return FretboardConfig(
            tuning=config.profile.tuning,
            min_velocity=config.min_velocity
        )


class Fretboard(ResetConfigurable[FretboardConfig]):
    def __init__(
        self,
        fret_config: FretboardConfig,
        observer: Callable[[List[FretMessage]], None]
    ) -> None:
        super().__init__(fret_config)
        self._observer = observer
        self._semitones = 0
        self._fingered: List[ChokeGroup] = []
        # Initialize fingered
        self.post_reset()

    def get_note(self, str_pos: StringPos) -> int:
        return self._config.tuning[str_pos.str_index] + self._semitones + str_pos.pre_fret

    def _get_pre_fret(self, str_index: int, note: int) -> int:
        return note - self._config.tuning[str_index] - self._semitones

    def _emit_fret_msg(self, str_index: int, msg: FrozenMessage) -> FretMessage:
        assert msg.note is not None
        return FretMessage(
            semitones=self._semitones,
            str_pos=StringPos(
                str_index=str_index,
                pre_fret=self._get_pre_fret(str_index, msg.note)
            ),
            sounding=msg.type == 'note_on' and msg.velocity > 0,
            msg=msg
        )

    def _clamp_velocity(self, velocity: int):
        if velocity == 0:
            return 0
        else:
            return max(velocity, self._config.min_velocity)

    def shift_semitones(self, diff: int) -> None:
        self._semitones += diff

    def handle_note(self, str_pos: StringPos, velocity: int) -> None:
        # Find out note from fret
        fret_note = self.get_note(str_pos)

        # Lookup choke group and find prev max note
        group = self._fingered[str_pos.str_index]
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
        self._observer(out_msgs)

    def pre_reset(self) -> None:
        out_msgs: List[FretMessage] = []
        for str_index, group in enumerate(self._fingered):
            cur_note_and_info = group.max_note_and_info()
            if cur_note_and_info is not None:
                cur_note, _ = cur_note_and_info
                off_msg = FrozenMessage(type='note_on', note=cur_note, velocity=0)
                out_msgs.append(self._emit_fret_msg(str_index, off_msg))
        self._observer(out_msgs)

    def post_reset(self) -> None:
        self._semitones = 0
        self._fingered = [ChokeGroup.empty() for i in range(len(self._config.tuning))]

    def listen(self, version: int, config: Config) -> None:
        fret_config = FretboardConfig.extract(config)
        self.configure(fret_config)
