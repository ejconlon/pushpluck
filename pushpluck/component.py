from abc import ABCMeta, abstractmethod
from typing import Generic, Optional, Type, TypeVar


C = TypeVar('C')
X = TypeVar('X', bound='MappedComponentConfig')
R = TypeVar('R')
K = TypeVar('K', bound='Component')


class MappedComponentConfig(Generic[C], metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def extract(cls: Type[X], root_config: C) -> X:
        raise NotImplementedError()


class Component(Generic[C, R], metaclass=ABCMeta):
    @abstractmethod
    def handle_reset(self) -> R:
        raise NotImplementedError()

    @abstractmethod
    def handle_config(self, config: C) -> Optional[R]:
        raise NotImplementedError()


class MappedComponent(Generic[C, X, R], Component[C, R]):
    @classmethod
    @abstractmethod
    def extract_config(cls: Type[K], root_config: C) -> X:
        raise NotImplementedError()

    def __init__(self, config: X) -> None:
        self._config = config

    @abstractmethod
    def handle_mapped_config(self, config: X) -> R:
        raise NotImplementedError()

    def handle_reset(self) -> R:
        return self.handle_mapped_config(self._config)

    def handle_config(self, root_config: C) -> Optional[R]:
        config = type(self).extract_config(root_config)
        if config != self._config:
            return self.handle_mapped_config(config)
        else:
            return None
