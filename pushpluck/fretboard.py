from bisect import bisect_left
from dataclasses import dataclass
from mido import Message
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


class Fretboard:
    def __init__(self, tuning: List[int]) -> None:
        self._tuning = tuning
        self._capo_semitones = 0
        num_strings = len(self._tuning)
        self._fingered: List[ChokeGroup] = \
            [ChokeGroup.empty() for i in range(num_strings)]

    def _get_note(self, str_index: int, pre_fret: int) -> int:
        return self._tuning[str_index] + self._capo_semitones + pre_fret

    def shift_capo(self, semitones: int) -> None:
        self._capo_semitones += semitones

    def handle_note(self, str_index: int, pre_fret: int, velocity: int) -> List[Message]:
        # Find out note from fret
        fret_note = self._get_note(str_index, pre_fret)

        # Lookup choke group and find prev max note
        group = self._fingered[str_index]
        prev_note_and_info = group.max_note_and_info()

        # Add note to group and find cur max note
        group.pluck(fret_note, velocity)
        cur_note_and_info = group.max_note_and_info()

        # Return control messages
        out_msgs: List[Message] = []
        if cur_note_and_info is None:
            if prev_note_and_info is None:
                # No notes - huh? (ignore)
                pass
            else:
                # Single note mute - send off for prev
                prev_note, _ = prev_note_and_info
                off_msg = Message(type='note_on', note=prev_note, velocity=0)
                out_msgs.append(off_msg)
        else:
            cur_note, cur_info = cur_note_and_info
            if prev_note_and_info is None:
                # Single note pluck - send on for cur
                on_msg = Message(type='note_on', note=cur_note, velocity=cur_info.velocity)
                out_msgs.append(on_msg)
            else:
                prev_note, _ = prev_note_and_info
                if prev_note == cur_note:
                    # Movement above fretted string (ignore)
                    pass
                else:
                    # Hammer-on or pull-off
                    # Send on before off to maintain overlap for envelopes?
                    on_msg = Message(type='note_on', note=cur_note, velocity=cur_info.velocity)
                    out_msgs.append(on_msg)
                    off_msg = Message(type='note_on', note=prev_note, velocity=0)
                    out_msgs.append(off_msg)
        return out_msgs

    def handle_reset(self) -> List[Message]:
        out_msgs: List[Message] = []
        for str_index, group in enumerate(self._fingered):
            cur_note_and_info = group.max_note_and_info()
            if cur_note_and_info is not None:
                cur_note, _ = cur_note_and_info
                off_msg = Message(type='note_on', note=cur_note, velocity=0)
                out_msgs.append(off_msg)
        self._fingered = [ChokeGroup.empty() for i in range(len(self._tuning))]
        return out_msgs
