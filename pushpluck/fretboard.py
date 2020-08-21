from abc import ABCMeta, abstractmethod
from bisect import bisect_left
from dataclasses import dataclass
from mido.frozen import FrozenMessage
from pushpluck import constants
from pushpluck.base import MatchException
from pushpluck.config import ChannelMode, Config, PlayMode, VisState
from pushpluck.midi import is_note_on_msg, is_note_off_msg, is_note_msg
from pushpluck.component import MappedComponent, MappedComponentConfig
from typing import Dict, Generator, List, Optional, Set


@dataclass(frozen=True)
class StringPos:
    # Which string (0 to max strings in tuning)
    str_index: int
    # Which fret (equivalently, semitone offset from base string tuning)
    # N.B. Negative frets make sense in this world.
    fret: int


@dataclass(frozen=True)
class NoteGroup:
    note: int
    primary: Optional[StringPos]
    equivs: List[StringPos]


@dataclass(frozen=True)
class FretboardMessage:
    # Position on strings/frets
    str_pos: StringPos
    # Equivalent positions in the note group
    # NOTE: Not necessarily on the same channel!
    equivs: List[StringPos]
    # An underlying message relevant to the fretted note (on, off, aftertouch)
    msg: FrozenMessage

    @property
    def channel(self) -> int:
        return self.msg.channel

    @property
    def note(self) -> int:
        return self.msg.note

    @property
    def velocity(self) -> Optional[int]:
        if self.is_note():
            return self.msg.velocity
        else:
            return None

    def is_note_on(self) -> bool:
        return is_note_on_msg(self.msg)

    def is_note_off(self) -> bool:
        return is_note_off_msg(self.msg)

    def is_note(self) -> bool:
        return is_note_msg(self.msg)

    def make_note_msg(self, velocity: int) -> 'FretboardMessage':
        return FretboardMessage(
            self.str_pos,
            self.equivs,
            FrozenMessage(
                type='note_on',
                channel=self.channel,
                note=self.note,
                velocity=velocity
            )
        )

    def make_note_off_msg(self) -> 'FretboardMessage':
        return self.make_note_msg(0)


@dataclass(frozen=True)
class StringBounds:
    low: StringPos
    high: StringPos

    def __iter__(self) -> Generator[StringPos, None, None]:
        for str_index in range(self.low.str_index, self.high.str_index + 1):
            for fret in range(self.low.fret, self.high.fret + 1):
                yield StringPos(str_index=str_index, fret=fret)

    def __contains__(self, cand: StringPos) -> bool:
        return cand.str_index >= self.low.str_index \
            and cand.str_index <= self.high.str_index \
            and cand.fret >= self.low.fret \
            and cand.fret <= self.high.fret


@dataclass(frozen=True)
class NoteEffects:
    vis: Dict[StringPos, VisState]
    msgs: List[FrozenMessage]

    @classmethod
    def empty(cls) -> 'NoteEffects':
        return cls({}, [])

    def is_empty(self) -> bool:
        return len(self.vis) == 0 and len(self.msgs) == 0


class ChannelMapper(metaclass=ABCMeta):
    @abstractmethod
    def map_channel(self, str_pos: StringPos) -> Optional[int]:
        raise NotImplementedError()


class SingleChannelMapper(ChannelMapper):
    def __init__(self, channel: int) -> None:
        self._channel = channel

    def map_channel(self, str_pos: StringPos) -> Optional[int]:
        return self._channel


class MultiChannelMapper(ChannelMapper):
    def __init__(
        self,
        base_channel: int,
        min_channel: int,
        max_channel: int
    ) -> None:
        self._base_channel = base_channel
        self._min_channel = min_channel
        self._max_channel = max_channel

    def map_channel(self, str_pos: StringPos) -> Optional[int]:
        channel = str_pos.str_index + self._base_channel
        if channel < self._min_channel or channel > self._max_channel:
            return None
        else:
            return channel


class Tuner(metaclass=ABCMeta):
    @abstractmethod
    def get_note(self, str_pos: StringPos) -> Optional[int]:
        raise NotImplementedError()

    @abstractmethod
    def get_note_group(self, str_pos: StringPos) -> Optional[NoteGroup]:
        raise NotImplementedError()


# This tuner is is defined by a finite number of strings.
# (An alternative may be defined by differences between strings,
# supporting an "infinite" number of strings.)
class FixedTuner(Tuner):
    def __init__(self, tuning: List[int], bounds: Optional[StringBounds]) -> None:
        self._tuning = tuning
        self._bounds = bounds
        self._note_lookup = self._make_note_lookup()
        self._equivs_lookup = self._make_equivs_lookup()

    def _make_note_lookup(self) -> Dict[StringPos, int]:
        lookup: Dict[StringPos, int] = {}
        if self._bounds is not None:
            for str_pos in self._bounds:
                if str_pos.str_index < 0 or str_pos.str_index >= len(self._tuning):
                    pass
                else:
                    lookup[str_pos] = self._tuning[str_pos.str_index] + str_pos.fret
        return lookup

    def _make_equivs_lookup(self) -> Dict[int, List[StringPos]]:
        lookup: Dict[int, List[StringPos]] = {}
        if self._bounds is not None:
            for str_pos in self._bounds:
                note = self.get_note(str_pos)
                if note is not None:
                    if note in lookup:
                        lookup[note].append(str_pos)
                    else:
                        lookup[note] = [str_pos]
        return lookup

    def get_note(self, str_pos: StringPos) -> Optional[int]:
        return self._note_lookup.get(str_pos)

    def get_note_group(self, str_pos: StringPos) -> Optional[NoteGroup]:
        note = self.get_note(str_pos)
        if note is None:
            return None
        else:
            primary = str_pos if self._bounds is not None and str_pos in self._bounds else None
            equivs = self._equivs_lookup[note] if note is not None and note in self._equivs_lookup else []
            return NoteGroup(note, primary, equivs)


class NoteHandler(metaclass=ABCMeta):
    @abstractmethod
    def trigger(self, fret_msg: FretboardMessage) -> List[FretboardMessage]:
        """
        Finger the given note and emit note on/offs.
        velocity == 0 <=> note off
        """
        raise NotImplementedError()


class NoteTracker:
    def __init__(self, chan_mapper: ChannelMapper) -> None:
        self._chan_mapper = chan_mapper
        # Map from channel to set of notes
        self._notemap: Dict[int, Set[int]] = {}
        self._vis: Dict[StringPos, VisState] = {}

    def is_enabled(self, str_pos: StringPos) -> bool:
        return self.get_vis(str_pos).enabled

    def get_vis(self, str_pos: StringPos) -> VisState:
        vs = self._vis.get(str_pos)
        if vs is None:
            vs = VisState.Off
            self._vis[str_pos] = vs
        return vs

    def _record_note(self, msg: FrozenMessage) -> None:
        if is_note_on_msg(msg):
            if msg.channel not in self._notemap:
                self._notemap[msg.channel] = set()
            self._notemap[msg.channel].add(msg.note)
        elif is_note_off_msg(msg):
            notes = self._notemap.get(msg.channel)
            if notes is not None:
                notes.remove(msg.note)

    def record_fx(self, msgs: List[FretboardMessage]) -> NoteEffects:
        dirty: Set[StringPos] = set()
        for msg in msgs:
            dirty.add(msg.str_pos)
            active = msg.is_note_on()
            vs = VisState.OnPrimary if active else VisState.Off
            self._vis[msg.str_pos] = vs
            for equiv in msg.equivs:
                if equiv == msg.str_pos:
                    continue
                dirty.add(equiv)
                channel = self._chan_mapper.map_channel(equiv)
                if channel is not None:
                    cur_vis = self.get_vis(equiv)
                    if not cur_vis.primary:
                        ws: VisState
                        if active:
                            if channel == msg.channel:
                                ws = VisState.OnDisabled
                            else:
                                ws = VisState.OnLinked
                        else:
                            ws = VisState.Off
                        self._vis[equiv] = ws
            self._record_note(msg.msg)
        vis = {sp: vs for sp, vs in self._vis.items() if sp in dirty}
        return NoteEffects(vis, msgs)

    def clean_fx(self) -> NoteEffects:
        default = VisState.Off
        vis = {sp: default for sp, vs in self._vis.items() if not vs == VisState.Off}
        msgs = [
            FrozenMessage(type='note_on', channel=chan, note=note, velocity=0)
            for chan, notes in self._notemap.items() for note in notes
        ]
        return NoteEffects(vis, msgs)


class PolyNoteHandler(NoteHandler):
    def trigger(self, fret_msg: FretboardMessage) -> List[FretboardMessage]:
        return [fret_msg]


class MonoNoteHandler(NoteHandler):
    def __init__(self) -> None:
        self._last_off: Optional[FretboardMessage] = None

    def trigger(self, fret_msg: FretboardMessage) -> List[FretboardMessage]:
        msgs: List[FretboardMessage] = []
        if fret_msg.is_note_off():
            if self._last_off is not None and self._last_off == fret_msg:
                msgs.append(self._last_off)
                self._last_off = None
        else:
            if self._last_off is not None:
                msgs.append(self._last_off)
            msgs.append(fret_msg)
            self._last_off = fret_msg.make_note_off_msg()
        return msgs


@dataclass(frozen=True)
class ChokeGroup:
    note_order: List[int]
    note_info: Dict[int, FretboardMessage]

    @classmethod
    def empty(cls) -> 'ChokeGroup':
        return cls(note_order=[], note_info={})

    def max_msg(self) -> Optional[FretboardMessage]:
        max_note = self.note_order[-1] if len(self.note_order) > 0 else None
        return self.note_info[max_note] if max_note is not None else None

    def trigger(self, fret_msg: FretboardMessage) -> None:
        note_index = bisect_left(self.note_order, fret_msg.note)
        note_exists = len(self.note_order) > note_index and note_index >= 0 and self.note_order[note_index] == fret_msg.note
        if fret_msg.is_note_on():
            if not note_exists:
                self.note_order.insert(note_index, fret_msg.note)
            self.note_info[fret_msg.note] = fret_msg
        else:
            if note_exists:
                del self.note_order[note_index]
            if fret_msg.note in self.note_info:
                del self.note_info[fret_msg.note]


class ChokeNoteHandler(NoteHandler):
    def __init__(self, num_strings: int) -> None:
        self._fingered = [ChokeGroup.empty() for i in range(num_strings)]

    def trigger(self, fret_msg: FretboardMessage) -> List[FretboardMessage]:
        # Lookup choke group and find prev max note
        group = self._fingered[fret_msg.str_pos.str_index]
        prev_msg = group.max_msg()

        # Add note to group and find cur max note
        group.trigger(fret_msg)
        cur_msg = group.max_msg()

        # Return note on/offs
        out_msgs: List[FretboardMessage] = []
        if cur_msg is None:
            if prev_msg is None:
                # No notes - huh? (ignore)
                pass
            else:
                # Single note mute - send off for prev
                out_msgs.append(prev_msg.make_note_off_msg())
        else:
            if prev_msg is None:
                # Single note pluck - send on for cur
                out_msgs.append(cur_msg)
            else:
                if prev_msg == cur_msg:
                    # Movement above fretted string (ignore)
                    pass
                else:
                    # Hammer-on or pull-off
                    # Send on before off to maintain overlap for envelopes?
                    out_msgs.append(cur_msg)
                    out_msgs.append(prev_msg.make_note_off_msg())
        return out_msgs


@dataclass(frozen=True)
class BoundedConfig:
    bounds: Optional[StringBounds]
    config: Config


@dataclass(frozen=True)
class FretboardConfig(MappedComponentConfig[BoundedConfig]):
    chan_mode: ChannelMode
    play_mode: PlayMode
    tuning: List[int]
    min_velocity: int
    bounds: Optional[StringBounds]

    @classmethod
    def extract(cls, root_config: BoundedConfig) -> 'FretboardConfig':
        return FretboardConfig(
            chan_mode=root_config.config.chan_mode,
            play_mode=root_config.config.play_mode,
            tuning=root_config.config.tuning,
            min_velocity=root_config.config.min_velocity,
            bounds=root_config.bounds
        )


def create_tuner(config: FretboardConfig) -> Tuner:
    return FixedTuner(config.tuning, config.bounds)


def create_chan_mapper(config: FretboardConfig) -> ChannelMapper:
    if config.chan_mode == ChannelMode.Single:
        return SingleChannelMapper(
            channel=constants.MIDI_BASE_CHANNEL
        )
    else:
        return MultiChannelMapper(
            base_channel=constants.MIDI_BASE_CHANNEL,
            min_channel=constants.MIDI_MIN_CHANNEL,
            max_channel=constants.MIDI_MAX_CHANNEL
        )


def create_handler(config: FretboardConfig, tuner: Tuner) -> NoteHandler:
    if config.play_mode == PlayMode.Tap:  # or config.play_mode == PlayMode.Pick:
        return ChokeNoteHandler(num_strings=len(config.tuning))
    elif config.play_mode == PlayMode.Poly:
        return PolyNoteHandler()
    elif config.play_mode == PlayMode.Mono:
        return MonoNoteHandler()
    else:
        raise MatchException(config.play_mode)


class Fretboard(MappedComponent[BoundedConfig, FretboardConfig, NoteEffects]):
    @classmethod
    def construct(cls, root_config: BoundedConfig) -> 'Fretboard':
        return cls(cls.extract_config(root_config))

    @classmethod
    def extract_config(cls, root_config: BoundedConfig) -> FretboardConfig:
        return FretboardConfig.extract(root_config)

    def __init__(self, config: FretboardConfig) -> None:
        super().__init__(config)
        self._mapper = create_chan_mapper(config)
        self._tracker = NoteTracker(self._mapper)
        self._tuner = create_tuner(config)
        self._handler = create_handler(config, self._tuner)

    def _clamp_velocity(self, velocity: int) -> int:
        if velocity == 0:
            return 0
        else:
            return max(velocity, self._config.min_velocity)

    def get_note(self, str_pos: StringPos) -> Optional[int]:
        return self._tuner.get_note(str_pos)

    def get_vis(self, str_pos: StringPos) -> VisState:
        return self._tracker.get_vis(str_pos)

    def trigger(self, str_pos: StringPos, velocity: int) -> NoteEffects:
        if self._tracker.is_enabled(str_pos):
            note_group = self._tuner.get_note_group(str_pos)
            channel = self._mapper.map_channel(str_pos)
            if note_group is not None and channel is not None:
                velocity = self._clamp_velocity(velocity)
                fret_msg = FretboardMessage(
                    str_pos=str_pos,
                    equivs=note_group.equivs,
                    msg=FrozenMessage(
                        type='note_on',
                        channel=channel,
                        note=note_group.note,
                        velocity=velocity
                    )
                )
                out_msgs = self._handler.trigger(fret_msg)
                return self._tracker.record_fx(out_msgs)
        return NoteEffects.empty()

    def handle_mapped_config(self, config: FretboardConfig) -> NoteEffects:
        fx = self._tracker.clean_fx()
        self._mapper = create_chan_mapper(config)
        self._tracker = NoteTracker(self._mapper)
        self._tuner = create_tuner(config)
        self._handler = create_handler(config, self._tuner)
        return fx
