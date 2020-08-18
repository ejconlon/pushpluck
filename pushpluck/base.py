from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import TypeVar


X = TypeVar('X')


class Closeable(metaclass=ABCMeta):
    @abstractmethod
    def close(self) -> None:
        """ Close this to free resources and deny further use. """
        raise NotImplementedError()


class Resettable(metaclass=ABCMeta):
    @abstractmethod
    def reset(self) -> None:
        """ Reset this to a known good state for further use. """
        raise NotImplementedError()


class Void:
    """ None is the type with 1 inhabitant, None. Void is the type with 0 inhabitants. """

    def __init__(self) -> None:
        raise Exception('Cannot instantiate Void')

    def absurd(self) -> X:
        """
        This allows you to trivially satisfy type checking by returning
        `void.absurd()` since it's impossible for `void` to exist in the first place.
        """
        raise Exception('Absurd')


@dataclass(frozen=True)
class Unit:
    """ A simple type with one inhabitant (according to eq and hash). """

    @staticmethod
    def instance() -> 'Unit':
        return _UNIT_SINGLETON


_UNIT_SINGLETON = Unit()
