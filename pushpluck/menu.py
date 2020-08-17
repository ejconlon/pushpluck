from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto, unique
from pushpluck import constants
from pushpluck.config import Config, Layout
from pushpluck.constants import ButtonCC, ButtonIllum
from pushpluck.component import Component, ComponentMessage
from pushpluck.push import PushEvent, ButtonEvent, KnobEvent
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


class MenuMessage(ComponentMessage):
    pass


@dataclass(frozen=True)
class ClearMessage(MenuMessage):
    pass


@dataclass(frozen=True)
class HalfBlockMessage(MenuMessage):
    row: int
    half_col: int
    text: str


@dataclass(frozen=True)
class BlockMessage(MenuMessage):
    row: int
    block_col: int
    text: str


@dataclass(frozen=True)
class ButtonLedMessage(MenuMessage):
    button: ButtonCC
    illum: Optional[ButtonIllum]


@dataclass(frozen=True)
class SemitoneShiftMessage(MenuMessage):
    diff: int


@dataclass(frozen=True)
class StringShiftMessage(MenuMessage):
    diff: int


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
    init_val: int
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


@dataclass(frozen=True, eq=False)
class KnobControl(Generic[Y, N]):
    name: str
    sensitivity: int
    val_range: ValRange[N]
    extractor: Callable[[Y], N]


@dataclass(eq=False)
class KnobState(Generic[Y, N]):
    control: KnobControl[Y, N]
    accum: int
    index: int
    val: N

    @classmethod
    def initial(cls, control: KnobControl[Y, N], config: Y) -> 'KnobState[Y, N]':
        val = control.extractor(config)  # type: ignore
        index = control.val_range.set_value(val)
        if index is None:
            raise ValueError(f'Control {control.name} cannot set initial value {val}')
        return cls(control, 0, index, val)

    def update(self, config: Y) -> None:
        new_val = self.control.extractor(config)  # type: ignore
        new_index = self.control.val_range.set_value(new_val)
        if new_index is None:
            raise ValueError(f'Control {self.control.name} cannot set updated value {new_val}')
        if self.index != new_index:
            self.accum = 0
        self.index = new_index
        self.val = new_val

    def rendered(self) -> str:
        return self.control.val_range.render(self.val)

    def accumulate(self, diff: int) -> None:
        new_accum = self.accum + diff
        if new_accum <= -self.control.sensitivity:
            pair = self.control.val_range.pred(self.index)
            if pair is None:
                self.accum = -self.control.sensitivity
            else:
                self.index, self.val = pair
                self.accum = new_accum % self.control.sensitivity
        elif new_accum >= self.control.sensitivity:
            pair = self.control.val_range.succ(self.index)
            if pair is None:
                self.accum = self.control.sensitivity
            else:
                self.index, self.val = pair
                self.accum = new_accum % self.control.sensitivity
        else:
            self.accum = new_accum


@dataclass
class DeviceState(Generic[Y, N]):
    knob_states: List[KnobState[Y, N]]

    @classmethod
    def initial(cls, knob_controls: List[KnobControl[Y, N]], config: Y) -> 'DeviceState':
        return DeviceState(
            knob_states=[KnobState.initial(kc, config) for kc in knob_controls]
        )


@dataclass(frozen=True)
class MenuLayout:
    device_knob_controls: List[KnobControl[Config, Any]]


def default_menu_layout() -> MenuLayout:
    return MenuLayout(
        device_knob_controls=[
            KnobControl(
                'MinVel', 1,
                IntValRange(0, 0, 127),
                lambda c: c.min_velocity
            ),
            KnobControl(
                'Layout', 1,
                ChoiceValRange.new([v for v in Layout], lambda v: v.name),
                lambda c: c.layout
            ),
            # KnobControl('Mode', 1, ChoiceValRange(['Tap', 'Pick'])),
            # KnobControl('SemOff', 1, IntValRange(-63, 0, 64)),
            # KnobControl('StrOff', 1, IntValRange(-11, 0, 12)),
            # KnobControl('Scale', 1, ChoiceValRange(SCALES)),
            # KnobControl('Root', 1, ChoiceValRange([n.name for n in NoteName]))
        ]
    )


@dataclass
class MenuState:
    cur_page: Page
    device_state: DeviceState

    def redraw(self) -> List[MenuMessage]:
        msgs: List[MenuMessage] = []
        msgs.append(ClearMessage())
        for page in Page:
            illum = ButtonIllum.Full if page == self.cur_page else ButtonIllum.Half
            msgs.append(ButtonLedMessage(page.to_button(), illum))
        for button in ACTIVE_BUTTONS:
            msgs.append(ButtonLedMessage(button, ButtonIllum.Half))
        if self.cur_page == Page.Device:
            for half_col, state in enumerate(self.device_state.knob_states):
                msgs.append(HalfBlockMessage(constants.DISPLAY_MAX_ROWS - 1, half_col, state.control.name))
                msgs.append(HalfBlockMessage(constants.DISPLAY_MAX_ROWS - 2, half_col, state.rendered()))
        elif self.cur_page == Page.Browse:
            pass
        elif self.cur_page == Page.Scales:
            pass
        else:
            raise ValueError()
        return msgs

    def transition(self, new_page: Page) -> List[MenuMessage]:
        self.cur_page = new_page
        return self.redraw()

    @classmethod
    def initial(cls, layout: MenuLayout, config: Config) -> 'MenuState':
        return cls(Page.Device, DeviceState.initial(layout.device_knob_controls, config))


class Menu(Component[Config, PushEvent, MenuMessage]):
    def __init__(self, layout: MenuLayout, config: Config):
        self._layout = layout
        self._config = config
        self._state = MenuState.initial(layout, config)

    def handle_reset(self) -> List[MenuMessage]:
        self._state = MenuState.initial(self._layout, self._config)
        return self._state.redraw()

    def handle_event(self, event: PushEvent) -> List[MenuMessage]:
        if isinstance(event, ButtonEvent):
            if event.pressed:
                page = Page.from_input_button(event.button)
                if page is not None:
                    return self._state.transition(page)
                elif event.button == ButtonCC.OctaveDown:
                    return [SemitoneShiftMessage(-12)]
                elif event.button == ButtonCC.OctaveUp:
                    return [SemitoneShiftMessage(12)]
                elif event.button == ButtonCC.Left:
                    return [SemitoneShiftMessage(-1)]
                elif event.button == ButtonCC.Right:
                    return [SemitoneShiftMessage(1)]
                elif event.button == ButtonCC.Up:
                    return [StringShiftMessage(1)]
                elif event.button == ButtonCC.Down:
                    return [StringShiftMessage(-1)]
            else:
                return []
        elif isinstance(event, KnobEvent):
            # TODO
            return []
        return []

    def handle_config(self, config: Config) -> List[MenuMessage]:
        self._config = config
        for state in self._state.device_state.knob_states:
            state.update(config)
        return self._state.redraw()
