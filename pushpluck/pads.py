from dataclasses import dataclass
from pushpluck.config import ColorScheme, Config, NoteType, PadColorMapper
from pushpluck.color import Color
from pushpluck.fretboard import Fretboard, FretboardMessage, TriggerEvent
from pushpluck.pos import Pos
from pushpluck.push import PadEvent, PushOutput
from pushpluck.midi import MidiSink
from pushpluck.scale import NoteName, Scale, ScaleClassifier, name_and_octave_from_note
from pushpluck.viewport import Viewport
from typing import Dict, Optional


@dataclass(frozen=True)
class PadsConfig:
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
    mapper: PadColorMapper
    pressed: bool

    def color(self, scheme: ColorScheme) -> Optional[Color]:
        return self.mapper.get_color(scheme, self.pressed)


@dataclass
class PadsState:
    lookup: Dict[Pos, SinglePadState]

    @classmethod
    def default(cls) -> 'PadsState':
        return cls({pos: SinglePadState(PadColorMapper.misc(False), False) for pos in Pos.iter_all()})


class Pads:
    @classmethod
    def construct(
        cls,
        scheme: ColorScheme,
        root_config: Config,
        push: PushOutput,
        sink: MidiSink
    ) -> 'Pads':
        config = PadsConfig.extract(root_config)
        fretboard = Fretboard.construct(root_config)
        viewport = Viewport.construct(root_config)
        return cls(scheme, config, fretboard, viewport, push, sink)

    def __init__(
        self,
        scheme: ColorScheme,
        config: PadsConfig,
        fretboard: Fretboard,
        viewport: Viewport,
        push: PushOutput,
        sink: MidiSink
    ) -> None:
        self._scheme = scheme
        self._config = config
        self._fretboard = fretboard
        self._viewport = viewport
        self._state = PadsState.default()
        self._push = push
        self._sink = sink

    def _get_pad_color(self, pos: Pos) -> Optional[Color]:
        pad = self._state.lookup[pos]
        return pad.color(self._scheme)

    def _redraw_pos(self, pos: Pos):
        color = self._get_pad_color(pos)
        if color is None:
            self._push.pad_led_off(pos)
        else:
            self._push.pad_set_color(pos, color)

    def _redraw(self) -> None:
        for pos in Pos.iter_all():
            self._redraw_pos(pos)

    def _make_pad_color_mapper(self, classifier: ScaleClassifier, pos: Pos) -> PadColorMapper:
        mapper: PadColorMapper
        str_pos = self._viewport.str_pos_from_pad_pos(pos)
        if str_pos is None:
            return PadColorMapper.misc(False)
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
            return PadColorMapper.note(note_type)

    def _reset_pad_colors(self) -> None:
        classifier = self._config.scale.to_classifier(self._config.root)
        for pos in Pos.iter_all():
            mapper = self._make_pad_color_mapper(classifier, pos)
            self._state.lookup[pos].mapper = mapper

    def handle_event(self, event: PadEvent) -> None:
        str_pos = self._viewport.str_pos_from_pad_pos(event.pos)
        if str_pos is not None:
            trigger_event = TriggerEvent(str_pos, event.velocity)
            fret_msgs = self._fretboard.handle_event(trigger_event)
            for fret_msg in fret_msgs:
                self._handle_fret_msg(fret_msg)

    def handle_config(self, root_config: Config) -> None:
        reset_pads = False
        fret_msgs = self._fretboard.handle_config(root_config)
        if fret_msgs is not None:
            for fret_msg in fret_msgs:
                self._handle_fret_msg(fret_msg)
            reset_pads = True
        view_msgs = self._viewport.handle_config(root_config)
        assert not view_msgs
        config = PadsConfig.extract(root_config)
        if config != self._config or reset_pads:
            self._config = config
            self._redraw()

    def _handle_fret_msg(self, msg: FretboardMessage) -> None:
        self._sink.send_msg(msg.msg)
        pad_pos = self._viewport.pad_pos_from_str_pos(msg.str_pos)
        if pad_pos is not None:
            pressed = msg.is_sounding()
            self._state.lookup[pad_pos].pressed = pressed
            self._redraw_pos(pad_pos)

    def handle_reset(self) -> None:
        fret_msgs = self._fretboard.handle_reset()
        for fret_msg in fret_msgs:
            self._handle_fret_msg(fret_msg)
        view_msgs = self._viewport.handle_reset()
        assert not view_msgs
        self._reset_pad_colors()
        self._redraw()
