from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
from typing import ContextManager, Generator, Generic, TypeVar


class Closeable(metaclass=ABCMeta):
    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError()


class Resettable(metaclass=ABCMeta):
    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError()


T = TypeVar('T')


class ReadRef(Generic[T], metaclass=ABCMeta):
    @abstractmethod
    def get_value(self) -> T:
        raise NotImplementedError()

    @abstractmethod
    def context(self) -> ContextManager[T]:
        raise NotImplementedError()


class Ref(ReadRef[T]):
    def __init__(self, value: T) -> None:
        self._value = value

    def get_value(self) -> T:
        return self._value

    def set_value(self, new_value: T) -> None:
        self._value = new_value

    @contextmanager
    def context(self) -> Generator[T, None, None]:
        yield self._value
