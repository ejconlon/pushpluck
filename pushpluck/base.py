from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
from typing import Callable, Generator, Generic, List, Optional, Tuple, TypeVar


T = TypeVar('T')
U = TypeVar('U')


class Closeable(metaclass=ABCMeta):
    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError()


class Resettable(metaclass=ABCMeta):
    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError()


class Configurable(Generic[T], metaclass=ABCMeta):
    @abstractmethod
    def configure(self, config: T) -> None:
        raise NotImplementedError()


class ResetConfigurable(Configurable[T], Resettable):
    def __init__(self, config: T) -> None:
        self._config = config

    def get_config(self) -> T:
        return self._config

    @abstractmethod
    def pre_reset(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    def post_reset(self) -> None:
        raise NotImplementedError()

    def reset(self) -> None:
        self.pre_reset()
        self.post_reset()

    def configure(self, config: T) -> None:
        if self._config != config:
            self.pre_reset()
            self._config = config
            self.post_reset()


class ReadRef(Generic[T], metaclass=ABCMeta):
    @abstractmethod
    def get_versioned_value(self) -> Tuple[int, T]:
        raise NotImplementedError()

    def get_value(self) -> T:
        return self.get_versioned_value()[1]

    @contextmanager
    def context(self) -> Generator[T, None, None]:
        yield self.get_value()

    def extract(self, fn: Callable[[T], U]) -> 'ReadRef[U]':
        return ExtractedRef(self, fn)


class Ref(ReadRef[T]):
    def __init__(self, value: T) -> None:
        self._version = 0
        self._value = value
        self._listeners: List[Callable[[int, T], None]] = []

    def get_versioned_value(self) -> Tuple[int, T]:
        return self._version, self._value

    def get_value(self) -> T:
        return self._value

    def set_value(self, new_value: T) -> None:
        self._version += 1
        self._value = new_value
        for fn in self._listeners:
            fn(self._version, self._value)

    def add_listener(self, fn: Callable[[int, T], None]) -> None:
        self._listeners.append(fn)


class ExtractedRef(ReadRef[U]):
    def __init__(self, ref: ReadRef[T], fn: Callable[[T], U]) -> None:
        self._ref = ref
        self._fn = fn
        self._version: Optional[int] = None
        self._value: Optional[U] = None

    def _update(self) -> None:
        outer_version, outer_value = self._ref.get_versioned_value()
        if self._version is None or self._version != outer_version:
            self._version = outer_version
            self._value = self._fn(outer_value)

    def get_versioned_value(self) -> Tuple[int, U]:
        self._update()
        assert self._version is not None
        assert self._value is not None
        return self._version, self._value

    def get_value(self) -> U:
        self._update()
        assert self._value is not None
        return self._value
