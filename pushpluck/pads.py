from dataclasses import dataclass
from mido.frozen import FrozenMessage
from pushpluck.component import Component, ComponentMessage, MappedComponentConfig
from pushpluck.config import ColorScheme, Config, NoteType, PadColor
from pushpluck.color import Color
from pushpluck.fretboard import Fretboard, FretboardMessage, TriggerEvent
from pushpluck.pos import Pos
from pushpluck.push import PadEvent
from pushpluck.scale import NoteName, Scale, ScaleClassifier, name_and_octave_from_note
from pushpluck.viewport import Viewport
from typing import Dict, List, Optional


@dataclass(frozen=True)
class PadsConfig(MappedComponentConfig):
    scale: Scale
    root: NoteName

    @classmethod
    def extract(cls, root_config: Config) -> 'PadsConfig':
        return PadsConfig(
            scale=root_config.scale,
            root=root_config.root
        )


@dataclass
class SinglePadState:
    color: PadColor
    pressed: bool


@dataclass
class PadsState:
    lookup: Dict[Pos, SinglePadState]

    @classmethod
    def default(cls) -> 'PadsState':
        return cls({pos: SinglePadState(PadColor.misc(False), False) for pos in Pos.iter_all()})


@dataclass(frozen=True)
class PadsMessage(ComponentMessage):
    pass


@dataclass(frozen=True)
class PadColorMessage(PadsMessage):
    pos: Pos
    color: Optional[Color]


@dataclass(frozen=True)
class MidiMessage(PadsMessage):
    msg: FrozenMessage


class Pads(Component[Config, PadEvent, PadsMessage]):
    @classmethod
    def construct(cls, scheme: ColorScheme, root_config: Config) -> 'Pads':
        config = PadsConfig.extract(root_config)
        fretboard = Fretboard.construct(root_config)
        viewport = Viewport.construct(root_config)
        return cls(scheme, config, fretboard, viewport)

    def __init__(
        self,
        scheme: ColorScheme,
        config: PadsConfig,
        fretboard: Fretboard,
        viewport: Viewport
    ) -> None:
        self._scheme = scheme
        self._config = config
        self._fretboard = fretboard
        self._viewport = viewport
        self._state = PadsState.default()

    def _make_pad_color(self, classifier: ScaleClassifier, pos: Pos) -> PadColor:
        pad_color: PadColor
        str_pos = self._viewport.str_pos_from_pad_pos(pos)
        if str_pos is None:
            return PadColor.misc(False)
        else:
            note = self._fretboard.get_note(str_pos)
            name, _ = name_and_octave_from_note(note)
            note_type: NoteType
            if classifier.is_root(name):
                note_type = NoteType.Root
            elif classifier.is_member(name):
                note_type = NoteType.Member
            else:
                note_type = NoteType.Other
            return PadColor.note(note_type)

    def _reset_pad_colors(self) -> None:
        classifier = self._config.scale.to_classifier(self._config.root)
        for pos in Pos.iter_all():
            color = self._make_pad_color(classifier, pos)
            self._state.lookup[pos].color = color

    def _set_pad_pressed(self, pos: Pos, pressed: bool) -> PadsMessage:
        self._state.lookup[pos].pressed = pressed
        return PadColorMessage(pos, self._get_pad_color(pos))

    def handle_event(self, event: PadEvent) -> List[PadsMessage]:
        msgs: List[PadsMessage] = []
        str_pos = self._viewport.str_pos_from_pad_pos(event.pos)
        if str_pos is not None:
            trigger_event = TriggerEvent(str_pos, event.velocity)
            fret_msgs = self._fretboard.handle_event(trigger_event)
            for fret_msg in fret_msgs:
                msgs.extend(self._handle_fret_msg(fret_msg))
        return msgs

    def _get_pad_color(self, pos: Pos) -> Optional[Color]:
        pad = self._state.lookup[pos]
        return pad.color.get_color(self._scheme, pad.pressed)

    def handle_config(self, root_config: Config) -> List[PadsMessage]:
        reset_pads = False
        msgs: List[PadsMessage] = []
        fret_msgs = self._fretboard.handle_config(root_config)
        if fret_msgs is not None:
            for fret_msg in fret_msgs:
                msgs.extend(self._handle_fret_msg(fret_msg))
            reset_pads = True
        view_msgs = self._viewport.handle_config(root_config)
        assert not view_msgs
        config = PadsConfig.extract(root_config)
        if config != self._config or reset_pads:
            self._config = config
            msgs.extend(self._pads_reset())
        return msgs

    def _pads_reset(self) -> List[PadsMessage]:
        self._reset_pad_colors()
        return [PadColorMessage(pos, self._get_pad_color(pos)) for pos in Pos.iter_all()]

    def _handle_fret_msg(self, msg: FretboardMessage) -> List[PadsMessage]:
        msgs: List[PadsMessage] = [MidiMessage(msg.msg)]
        pad_pos = self._viewport.pad_pos_from_str_pos(msg.str_pos)
        if pad_pos is not None:
            msgs.append(self._set_pad_pressed(pad_pos, msg.is_sounding()))
        return msgs

    def handle_reset(self) -> List[PadsMessage]:
        msgs: List[PadsMessage] = []
        fret_msgs = self._fretboard.handle_reset()
        for fret_msg in fret_msgs:
            msgs.extend(self._handle_fret_msg(fret_msg))
        view_msgs = self._viewport.handle_reset()
        assert not view_msgs
        msgs.extend(self._pads_reset())
        return msgs
