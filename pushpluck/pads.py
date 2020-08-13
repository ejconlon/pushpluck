from dataclasses import dataclass
from pushpluck.component import Component, ComponentConfig, ComponentState
from pushpluck.config import ColorScheme, Config, NoteType, PadColor
from pushpluck.color import Color
from pushpluck.fretboard import FretboardQueries
from pushpluck.pos import Pos
from pushpluck.scale import NoteName, Scale, ScaleClassifier, name_and_octave_from_note
from pushpluck.viewport import ViewportQueries
from typing import Dict, List, Optional


@dataclass(frozen=True)
class PadsConfig(ComponentConfig):
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
class PadsState(ComponentState[PadsConfig]):
    lookup: Dict[Pos, SinglePadState]

    @classmethod
    def initialize(cls, config: PadsConfig) -> 'PadsState':
        return cls({pos: SinglePadState(PadColor.misc(False), False) for pos in Pos.iter_all()})


@dataclass(frozen=True)
class PadsMessage:
    pos: Pos
    color: Optional[Color]


class Pads(Component[PadsConfig, PadsState, List[PadsMessage]]):
    @classmethod
    def extract_config(cls, root_config: Config) -> PadsConfig:
        return PadsConfig.extract(root_config)

    @classmethod
    def initialize_state(cls, config: PadsConfig) -> PadsState:
        return PadsState.initialize(config)

    def __init__(
        self,
        scheme: ColorScheme,
        fretboard: FretboardQueries,
        viewport: ViewportQueries,
        root_config: Config
    ) -> None:
        config = PadsConfig.extract(root_config)
        super().__init__(config)
        self._scheme = scheme
        self._fretboard = fretboard
        self._viewport = viewport

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
            self._state.lookup[pos].color = self._make_pad_color(classifier, pos)

    def set_pad_pressed(self, pos: Pos, pressed: bool) -> None:
        self._state.lookup[pos].pressed = pressed

    def get_pad_color(self, pos: Pos) -> Optional[Color]:
        pad = self._state.lookup[pos]
        return pad.color.get_color(self._scheme, pad.pressed)

    def internal_handle_config(self, config: PadsConfig) -> List[PadsMessage]:
        self._config = config
        self._reset_pad_colors()
        return self.handle_reset()

    def handle_reset(self) -> List[PadsMessage]:
        pads_msgs: List[PadsMessage] = []
        for pos in Pos.iter_all():
            pads_msgs.append(PadsMessage(pos, self.get_pad_color(pos)))
        return pads_msgs
