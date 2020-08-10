from dataclasses import dataclass
from typing import Dict, Generator


@dataclass(frozen=True)
class Color:
    red: int
    green: int
    blue: int

    def __iter__(self) -> Generator[int, None, None]:
        yield self.red
        yield self.green
        yield self.blue

    def to_code(self) -> str:
        nums = ''.join(f'{x:02x}' for x in self)
        return f'#{nums.upper()}'

    @classmethod
    def from_code(cls, code: str) -> 'Color':
        assert code[0] == '#'
        red = int(code[1:3], 16)
        green = int(code[3:5], 16)
        blue = int(code[5:7], 16)
        return cls(red, green, blue)


COLORS: Dict[str, Color] = {
    'Black': Color.from_code('#000000'),
    'DarkGrey': Color.from_code('#A9A9A9'),
    'Gray': Color.from_code('#808080'),
    'White': Color.from_code('#FFFFFF'),
    'Red': Color.from_code('#FF0000'),
    'Yellow': Color.from_code('#FFFF00'),
    'Lime': Color.from_code('#00FF00'),
    'Green': Color.from_code('#008000'),
    'Spring': Color.from_code('#00FF7F'),
    'Turquoise': Color.from_code('#40E0D0'),
    'Cyan': Color.from_code('#00FFFF'),
    'Sky': Color.from_code('#87CEEB'),
    'Blue': Color.from_code('#0000FF'),
    'Orchid': Color.from_code('#DA70D6'),
    'Magenta': Color.from_code('#FF00FF'),
    'Pink': Color.from_code('#FFC0CB'),
    'Orange': Color.from_code('#FFA580'),
    'Indigo': Color.from_code('#4B0082'),
    'Violet': Color.from_code('#EE82EE')
}
