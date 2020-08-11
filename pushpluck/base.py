from abc import ABCMeta, abstractmethod


class Closeable(metaclass=ABCMeta):
    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError()


class Resettable(metaclass=ABCMeta):
    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError()
