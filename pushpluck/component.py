from abc import ABCMeta, abstractmethod
from pushpluck.base import Void
from typing import Generic, List, Type, TypeVar


C = TypeVar('C')
X = TypeVar('X', bound='MappedComponentConfig')
E = TypeVar('E')
M = TypeVar('M', bound='ComponentMessage')
K = TypeVar('K', bound='Component')


class MappedComponentConfig(Generic[C], metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def extract(cls: Type[X], root_config: C) -> X:
        raise NotImplementedError()


class ComponentMessage:
    pass


class VoidComponentMessage(Void, ComponentMessage):
    def __init__(self):
        super(Void, self).__init__()


class Component(Generic[C, E, M], metaclass=ABCMeta):
    @abstractmethod
    def handle_event(self, event: E) -> List[M]:
        raise NotImplementedError()

    @abstractmethod
    def handle_reset(self) -> List[M]:
        raise NotImplementedError()

    @abstractmethod
    def handle_config(self, config: C) -> List[M]:
        raise NotImplementedError()


class MappedComponent(Generic[C, X, E, M], Component[C, E, M]):
    @classmethod
    @abstractmethod
    def extract_config(cls: Type[K], root_config: C) -> X:
        raise NotImplementedError()

    def __init__(self, config: X) -> None:
        self._config = config

    @abstractmethod
    def handle_mapped_config(self, config: X) -> List[M]:
        raise NotImplementedError()

    def handle_reset(self) -> List[M]:
        return self.handle_mapped_config(self._config)

    def handle_config(self, root_config: C) -> List[M]:
        config = type(self).extract_config(root_config)
        if config != self._config:
            return self.handle_mapped_config(config)
        else:
            return []
