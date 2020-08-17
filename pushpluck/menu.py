from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto, unique
from pushpluck import constants
from pushpluck.base import Void
from pushpluck.constants import ButtonCC, ButtonIllum
from pushpluck.component import Component, ComponentMessage
from pushpluck.push import PushEvent, ButtonEvent
from typing import Any, Generic, List, Optional, Tuple, TypeVar


N = TypeVar('N')


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
    def succ(self, index: int) -> Optional[Tuple[int, N]]:
        raise NotImplementedError()

    @abstractmethod
    def pred(self, index: int) -> Optional[Tuple[int, N]]:
        raise NotImplementedError()


@dataclass(frozen=True)
class IntValRange(ValRange[int]):
    min_val: int
    max_val: int

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


@dataclass(frozen=True)
class ChoiceValRange(ValRange[N]):
    options: List[N]

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


@dataclass(frozen=True)
class KnobControl(Generic[N]):
    name: str
    sensitivity: int
    val_range: ValRange[N]
    default_val: N


@dataclass
class KnobState(Generic[N]):
    control: KnobControl[N]
    accum: int
    index: int
    val: N

    @classmethod
    def initial(cls, control: KnobControl[N]) -> 'KnobState[N]':
        return cls(control, 0, 0, control.default_val)

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
class DeviceState:
    knob_states: List[KnobState[Any]]

    @classmethod
    def initial(cls, knob_controls: List[KnobControl]) -> 'DeviceState':
        return DeviceState(
            knob_states=[KnobState.initial(kc) for kc in knob_controls]
        )


@dataclass(frozen=True)
class MenuLayout:
    device_knob_controls: List[KnobControl]


def default_menu_layout() -> MenuLayout:
    return MenuLayout(
        device_knob_controls=[
            KnobControl('Min Vel', 1, IntValRange(0, 127), 0),
            KnobControl('Layout', 1, ChoiceValRange(['Horiz', 'Vert']), 0)
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
    def initial(cls, layout: MenuLayout) -> 'MenuState':
        return cls(Page.Device, DeviceState.initial(layout.device_knob_controls))


class Menu(Component[Void, PushEvent, MenuMessage]):
    def __init__(self, layout: MenuLayout):
        self._layout = layout
        self._state = MenuState.initial(layout)

    def handle_reset(self) -> List[MenuMessage]:
        self._state = MenuState.initial(self._layout)
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
        return []

    def handle_config(self, config: Void) -> List[MenuMessage]:
        return config.absurd()
