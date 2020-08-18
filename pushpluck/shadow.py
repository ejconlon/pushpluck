from contextlib import contextmanager
from dataclasses import dataclass
from pushpluck import constants
from pushpluck.color import Color
from pushpluck.push import PushInterface, ButtonCC, ButtonIllum, ButtonColor, TimeDivCC
from pushpluck.pos import Pos, GridSelPos, ChanSelPos
from typing import Dict, Generator, Optional


class LcdRow:
    def __init__(self) -> None:
        self._buffer = [ord(' ') for i in range(constants.DISPLAY_MAX_LINE_LEN)]

    def get_text(self, start: int, length: int) -> str:
        end = start + length
        assert start >= 0 and length >= 0 and end <= constants.DISPLAY_MAX_LINE_LEN
        return ''.join(chr(i) for i in self._buffer[start:end])

    def get_all_text(self) -> str:
        return self.get_text(0, constants.DISPLAY_MAX_LINE_LEN)

    def set_text(self, start: int, text: str) -> bool:
        length = len(text)
        end = start + length
        assert start >= 0 and end <= constants.DISPLAY_MAX_LINE_LEN
        changed = False
        for i in range(length):
            old_char = self._buffer[start + i]
            new_char = ord(text[i])
            if old_char != new_char:
                changed = True
            self._buffer[start + i] = new_char
        return changed

    def set_all_text(self, text: str) -> bool:
        return self.set_text(0, text)


@dataclass(frozen=True, eq=False)
class PushState:
    lcd: Dict[int, LcdRow]
    pads: Dict[Pos, Optional[Color]]
    buttons: Dict[ButtonCC, Optional[ButtonIllum]]

    @classmethod
    def reset(cls) -> 'PushState':
        return cls(
            lcd={row: LcdRow() for row in range(constants.DISPLAY_MAX_ROWS)},
            pads={pos: None for pos in Pos.iter_all()},
            buttons={button: None for button in ButtonCC}
        )

    @classmethod
    def diff(cls) -> 'PushState':
        return cls(
            lcd={},
            pads={},
            buttons={}
        )


class PushShadow:
    def __init__(self, push: PushInterface) -> None:
        self._push = push
        self._state = PushState.reset()

    @contextmanager
    def context(self) -> Generator['PushInterface', None, None]:
        diff_state = PushState.diff()
        managed = PushShadowManaged(diff_state)
        yield managed
        self._emit(diff_state)

    def _emit(self, diff_state: PushState) -> None:
        self._emit_lcd(diff_state)
        self._emit_pads(diff_state)
        self._emit_buttons(diff_state)

    def _emit_lcd(self, diff_state: PushState) -> None:
        for row, new_row in diff_state.lcd.items():
            old_row = self._state.lcd[row]
            new_text = new_row.get_all_text()
            if old_row.set_all_text(new_text):
                self._push.lcd_display_raw(row, 0, new_text)

    def _emit_pads(self, diff_state: PushState) -> None:
        for pos, new_color in diff_state.pads.items():
            old_color = self._state.pads[pos]
            if old_color != new_color:
                if new_color is None:
                    self._push.pad_led_off(pos)
                    del self._state.pads[pos]
                else:
                    self._push.pad_set_color(pos, new_color)
                    self._state.pads[pos] = new_color

    def _emit_buttons(self, diff_state: PushState) -> None:
        for button, new_illum in diff_state.buttons.items():
            old_illum = self._state.buttons[button]
            if old_illum != new_illum:
                if new_illum is None:
                    self._push.button_off(button)
                    del self._state.buttons[button]
                else:
                    self._push.button_set_illum(button, new_illum)


class PushShadowManaged(PushInterface):
    def __init__(self, state: PushState):
        self._state = state

    def pad_led_off(self, pos: Pos) -> None:
        self._state.pads[pos] = None

    def pad_set_color(self, pos: Pos, color: Color) -> None:
        self._state.pads[pos] = color

    def lcd_display_raw(self, row: int, line_col: int, text: str) -> None:
        if row not in self._state.lcd:
            self._state.lcd[row] = LcdRow()
        self._state.lcd[row].set_text(line_col, text)

    def button_set_illum(self, button: ButtonCC, illum: ButtonIllum) -> None:
        self._state.buttons[button] = illum

    def button_off(self, button: ButtonCC) -> None:
        self._state.buttons[button] = None

    def time_div_off(self, time_div: TimeDivCC) -> None:
        raise NotImplementedError()

    def time_div_reset(self) -> None:
        raise NotImplementedError()

    def chan_sel_set_color(self, cs_pos: ChanSelPos, illum: ButtonIllum, color: ButtonColor) -> None:
        raise NotImplementedError()

    def chan_sel_off(self, cs_pos: ChanSelPos) -> None:
        raise NotImplementedError()

    def grid_sel_set_color(self, gs_pos: GridSelPos, color: Color) -> None:
        raise NotImplementedError()

    def grid_sel_off(self, gs_pos: GridSelPos) -> None:
        raise NotImplementedError()
