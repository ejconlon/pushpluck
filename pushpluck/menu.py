from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, replace
from enum import Enum, auto, unique
from pushpluck import constants
from pushpluck.config import Config, Layout
from pushpluck.constants import ButtonCC, ButtonIllum, KnobGroup
from pushpluck.push import PushEvent, ButtonEvent, KnobEvent, PushInterface
# from pushpluck.scale import SCALES, NoteName
from typing import Any, Callable, Dict, Generic, List, Optional, Tuple, TypeVar


N = TypeVar('N')
Y = TypeVar('Y')


@unique
class Page(Enum):
    Device = auto()
    Scales = auto()
    Browse = auto()

    def to_button(self) -> ButtonCC:
        if self == Page.Device:
            return ButtonCC.Device
        elif self == Page.Browse:
            return ButtonCC.Browse
        elif self == Page.Scales:
            return ButtonCC.Scales
        else:
            raise ValueError()

    @staticmethod
    def from_input_button(button: ButtonCC) -> Optional['Page']:
        if button == ButtonCC.Device:
            return Page.Device
        elif button == ButtonCC.Browse:
            return Page.Browse
        elif button == ButtonCC.Scales:
            return Page.Scales
        else:
            return None


ACTIVE_BUTTONS: List[ButtonCC] = [
    ButtonCC.Undo,
    ButtonCC.Left,
    ButtonCC.Right,
    ButtonCC.Up,
    ButtonCC.Down,
    ButtonCC.OctaveDown,
    ButtonCC.OctaveUp
]


class ValRange(Generic[N], metaclass=ABCMeta):
    @abstractmethod
    def render(self, value: N) -> str:
        raise NotImplementedError()

    @abstractmethod
    def set_value(self, value: N) -> Optional[int]:
        raise NotImplementedError()

    @abstractmethod
    def succ(self, index: int) -> Optional[Tuple[int, N]]:
        raise NotImplementedError()

    @abstractmethod
    def pred(self, index: int) -> Optional[Tuple[int, N]]:
        raise NotImplementedError()


@dataclass(frozen=True)
class IntValRange(ValRange[int]):
    min_val: int
    max_val: int

    def render(self, value: int) -> str:
        return str(value)

    def set_value(self, value: int) -> Optional[int]:
        return value if value >= self.min_val and value <= self.max_val else None

    def succ(self, index: int) -> Optional[Tuple[int, int]]:
        if index < self.min_val or index >= self.max_val:
            return None
        else:
            new_index = index + 1
            return new_index, new_index

    def pred(self, index: int) -> Optional[Tuple[int, int]]:
        if index <= self.min_val or index > self.max_val:
            return None
        else:
            new_index = index - 1
            return new_index, new_index


@dataclass(frozen=True, eq=False)
class ChoiceValRange(ValRange[N]):
    @classmethod
    def new(
        cls,
        options: List[N],
        renderer: Callable[[N], str]
    ) -> 'ChoiceValRange[N]':
        options_dict = {i: n for i, n in enumerate(options)}
        rev_options_dict = {renderer(n): i for i, n in enumerate(options)}
        return cls(len(options), options_dict, rev_options_dict, renderer)

    length: int
    options: Dict[int, N]
    rev_options: Dict[str, int]
    renderer: Callable[[N], str]

    def render(self, value: N) -> str:
        return self.renderer(value)  # type: ignore

    def set_value(self, value: N) -> Optional[int]:
        rep = self.render(value)
        return self.rev_options.get(rep)

    def succ(self, index: int) -> Optional[Tuple[int, N]]:
        if index < 0 or index < len(self.options) - 1:
            return None
        else:
            new_index = index + 1
            return new_index, self.options[new_index]

    def pred(self, index: int) -> Optional[Tuple[int, N]]:
        if index <= 0 or index >= len(self.options):
            return None
        else:
            new_index = index - 1
            return new_index, self.options[new_index]


class Lens(Generic[Y, N], metaclass=ABCMeta):
    @abstractmethod
    def get_value(self, struct: Y) -> N:
        raise NotImplementedError()

    @abstractmethod
    def set_value(self, struct: Y, value: N) -> Y:
        raise NotImplementedError()


@dataclass(frozen=True, eq=False)
class LensPair(Lens[Y, N]):
    getter: Callable[[Y], N]
    setter: Callable[[Y, N], Y]

    def get_value(self, struct: Y) -> N:
        return self.getter(struct)  # type: ignore

    def set_value(self, struct: Y, value: N) -> Y:
        return self.setter(struct, value)  # type: ignore


class DataclassLens(Lens[Y, N]):
    def __init__(self, field_name: str) -> None:
        self._field_name = field_name

    def get_value(self, struct: Y) -> N:
        return getattr(struct, self._field_name)

    def set_value(self, struct: Y, value: N) -> Y:
        return replace(struct, **{self._field_name: value})


@dataclass(frozen=True, eq=False)
class KnobControl(Generic[Y, N]):
    name: str
    sensitivity: int
    val_range: ValRange[N]
    lens: Lens[Y, N]


@dataclass(eq=False)
class KnobState(Generic[Y, N]):
    control: KnobControl[Y, N]
    accum: int
    index: int
    val: N

    @classmethod
    def initial(cls, control: KnobControl[Y, N], config: Y) -> 'KnobState[Y, N]':
        val = control.lens.get_value(config)
        index = control.val_range.set_value(val)
        if index is None:
            raise ValueError(f'Control {control.name} cannot set initial value {val}')
        return cls(control, 0, index, val)

    def update(self, config: Y) -> bool:
        new_val = self.control.lens.get_value(config)
        new_index = self.control.val_range.set_value(new_val)
        if new_index is None:
            raise ValueError(f'Control {self.control.name} cannot set updated value {new_val}')
        if self.index != new_index:
            self.accum = 0
            self.index = new_index
            self.val = new_val
            return True
        else:
            return False

    def rendered(self) -> str:
        return self.control.val_range.render(self.val)

    def accumulate(self, config: Y, diff: int) -> Optional[Y]:
        updated = False
        new_accum = self.accum + diff
        # First set internal values
        if new_accum <= -self.control.sensitivity:
            pair = self.control.val_range.pred(self.index)
            if pair is None:
                self.accum = -self.control.sensitivity
            else:
                self.index, self.val = pair
                self.accum = new_accum % self.control.sensitivity
                updated = True
        elif new_accum >= self.control.sensitivity:
            pair = self.control.val_range.succ(self.index)
            if pair is None:
                self.accum = self.control.sensitivity
            else:
                self.index, self.val = pair
                self.accum = new_accum % self.control.sensitivity
                updated = True
        else:
            self.accum = new_accum
        # Then assign config
        return self.control.lens.set_value(config, self.val) if updated else None


@dataclass
class DeviceState(Generic[Y, N]):
    knob_states: List[KnobState[Y, N]]

    @classmethod
    def initial(cls, knob_controls: List[KnobControl[Y, N]], config: Y) -> 'DeviceState':
        return DeviceState(
            knob_states=[KnobState.initial(kc, config) for kc in knob_controls]
        )

    def update(self, config: Y) -> bool:
        updated = False
        for state in self.knob_states:
            updated = state.update(config) or updated
        return updated


@dataclass(frozen=True)
class MenuLayout:
    device_knob_controls: List[KnobControl[Config, Any]]


def default_menu_layout() -> MenuLayout:
    high_sens = 1
    low_sens = 4
    return MenuLayout(
        device_knob_controls=[
            KnobControl(
                'MinVel', high_sens,
                IntValRange(0, 127),
                DataclassLens('min_velocity')
            ),
            KnobControl(
                'Layout', low_sens,
                ChoiceValRange.new([v for v in Layout], lambda v: v.name),
                DataclassLens('layout')
            ),
            # KnobControl('Mode', sens, ChoiceValRange(['Tap', 'Pick'])),
            KnobControl(
                'SemOff', low_sens,
                IntValRange(-63, 64),
                DataclassLens('fret_offset')
            ),
            KnobControl(
                'StrOff', low_sens,
                IntValRange(-11, 12),
                DataclassLens('str_offset')
            ),
            # KnobControl('Scale', 1, ChoiceValRange(SCALES)),
            # KnobControl('Root', 1, ChoiceValRange([n.name for n in NoteName]))
        ]
    )


@dataclass
class MenuState:
    config: Config
    cur_page: Page
    device_state: DeviceState

    def redraw(self, push: PushInterface) -> None:
        # Clear owned components
        push.lcd_reset()
        push.chan_sel_reset()
        push.grid_sel_reset()
        push.button_reset()
        # Highlight page buttons
        for page in Page:
            illum = ButtonIllum.Full if page == self.cur_page else ButtonIllum.Half
            push.button_set_illum(page.to_button(), illum)
        # Highlight other buttons
        for button in ACTIVE_BUTTONS:
            push.button_set_illum(button, ButtonIllum.Half)
        # Draw page-specific portions
        if self.cur_page == Page.Device:
            for half_col, state in enumerate(self.device_state.knob_states):
                push.lcd_display_half_block(constants.DISPLAY_MAX_ROWS - 1, half_col, state.control.name)
                push.lcd_display_half_block(constants.DISPLAY_MAX_ROWS - 2, half_col, state.rendered())
        elif self.cur_page == Page.Browse:
            pass
        elif self.cur_page == Page.Scales:
            pass
        else:
            raise ValueError()

    def _set_config(self, new_config: Config) -> None:
        self.device_state.update(new_config)
        self.config = new_config

    def shift_semitones(self, diff: int) -> None:
        fret_offset = self.config.fret_offset + diff
        new_config = replace(self.config, fret_offset=fret_offset)
        self._set_config(new_config)

    def shift_strings(self, diff: int) -> None:
        str_offset = self.config.str_offset + diff
        new_config = replace(self.config, str_offset=str_offset)
        self._set_config(new_config)

    def turn_knob(self, offset: int, diff: int) -> bool:
        if self.cur_page == Page.Device:
            if offset >= 0 and offset < len(self.device_state.knob_states):
                state = self.device_state.knob_states[offset]
                new_config = state.accumulate(self.config, diff)
                if new_config is not None:
                    self.config = new_config
                    return True
        return False

    @classmethod
    def initial(cls, layout: MenuLayout, config: Config) -> 'MenuState':
        return cls(config, Page.Device, DeviceState.initial(layout.device_knob_controls, config))


class Menu:
    def __init__(self, layout: MenuLayout, config: Config):
        self._layout = layout
        self._init_config = config
        self._state = MenuState.initial(layout, config)

    def handle_reset(self, push: PushInterface) -> Config:
        self._state = MenuState.initial(self._layout, self._init_config)
        self._state.redraw(push)
        return self._state.config

    def handle_event(self, push: PushInterface, event: PushEvent) -> Optional[Config]:
        updated = False
        if isinstance(event, ButtonEvent):
            if event.pressed:
                page = Page.from_input_button(event.button)
                if page is not None:
                    if self._state.cur_page != page:
                        self._state.cur_page = page
                        updated = True
                elif event.button == ButtonCC.OctaveDown:
                    self._state.shift_semitones(-12)
                    updated = True
                elif event.button == ButtonCC.OctaveUp:
                    self._state.shift_semitones(12)
                    updated = True
                elif event.button == ButtonCC.Left:
                    self._state.shift_semitones(-1)
                    updated = True
                elif event.button == ButtonCC.Right:
                    self._state.shift_semitones(1)
                    updated = True
                elif event.button == ButtonCC.Up:
                    self._state.shift_strings(1)
                    updated = True
                elif event.button == ButtonCC.Down:
                    self._state.shift_strings(-1)
                    updated = True
        elif isinstance(event, KnobEvent):
            if event.group == KnobGroup.Center:
                diff = 1 if event.clockwise else -1
                updated = self._state.turn_knob(event.offset, diff)

        if updated:
            self._state.redraw(push)
            return self._state.config
        else:
            return None
