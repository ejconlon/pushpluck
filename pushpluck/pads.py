from dataclasses import dataclass
from pushpluck.config import ColorScheme, Config, NoteType, PadColorMapper
from pushpluck.color import Color
from pushpluck.fretboard import Fretboard, FretboardMessage, TriggerEvent
from pushpluck.pos import Pos
from pushpluck.push import PadEvent, PushInterface
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
        root_config: Config
    ) -> 'Pads':
        config = PadsConfig.extract(root_config)
        fretboard = Fretboard.construct(root_config)
        viewport = Viewport.construct(root_config)
        return cls(scheme, config, fretboard, viewport)

    def __init__(
        self,
        scheme: ColorScheme,
        config: PadsConfig,
        fretboard: Fretboard,
        viewport: Viewport,
    ) -> None:
        self._scheme = scheme
        self._config = config
        self._fretboard = fretboard
        self._viewport = viewport
        self._state = PadsState.default()
        self._reset_pad_colors()

    def _get_pad_color(self, pos: Pos) -> Optional[Color]:
        pad = self._state.lookup[pos]
        return pad.color(self._scheme)

    def _redraw_pos(self, push: PushInterface, pos: Pos):
        color = self._get_pad_color(pos)
        if color is None:
            push.pad_led_off(pos)
        else:
            push.pad_set_color(pos, color)

    def _redraw(self, push: PushInterface) -> None:
        for pos in Pos.iter_all():
            self._redraw_pos(push, pos)

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

    def handle_event(self, push: PushInterface, sink: MidiSink, event: PadEvent) -> None:
        str_pos = self._viewport.str_pos_from_pad_pos(event.pos)
        if str_pos is not None:
            trigger_event = TriggerEvent(str_pos, event.velocity)
            fret_msgs = self._fretboard.handle_event(trigger_event)
            for fret_msg in fret_msgs:
                self._handle_fret_msg(push, sink, fret_msg)

    def handle_config(self, push: PushInterface, sink: MidiSink, root_config: Config, reset: bool) -> None:
        fret_msgs = self._fretboard.handle_config(root_config, reset)
        if fret_msgs is not None:
            for fret_msg in fret_msgs:
                self._handle_fret_msg(push, sink, fret_msg)
            # If there are note-offs or updated config, force reset and redraw of pads
            reset = True
        unit = self._viewport.handle_config(root_config, reset)
        if unit is not None:
            # Likewise for viewport changes
            reset = True
        config = PadsConfig.extract(root_config)
        if config != self._config or reset:
            self._config = config
            self._reset_pad_colors()
            self._redraw(push)

    def _handle_fret_msg(self, push: PushInterface, sink: MidiSink, msg: FretboardMessage) -> None:
        sink.send_msg(msg.msg)
        pad_pos = self._viewport.pad_pos_from_str_pos(msg.str_pos)
        if pad_pos is not None:
            pressed = msg.is_sounding()
            self._state.lookup[pad_pos].pressed = pressed
            self._redraw_pos(push, pad_pos)
