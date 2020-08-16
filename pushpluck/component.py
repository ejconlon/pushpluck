from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from pushpluck.config import Config
from typing import Generic, List, Optional, Type, TypeVar


C = TypeVar('C', bound='ComponentConfig')
E = TypeVar('E', bound='ComponentConfig')
M = TypeVar('M', bound='ComponentMessage')
K = TypeVar('K', bound='Component')


class ComponentConfig(metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def extract(cls: Type[C], root_config: Config) -> C:
        raise NotImplementedError()


@dataclass(frozen=True)
class NullConfig(ComponentConfig):
    pass

    @classmethod
    def extract(cls, root_config: Config) -> 'NullConfig':
        return cls()


class ComponentMessage:
    pass


@dataclass(frozen=True)
class NullComponentMessage(ComponentMessage):
    pass


class Component(Generic[C, M], metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def extract_config(cls: Type[K], root_config: Config) -> C:
        raise NotImplementedError()

    def __init__(self, config: C) -> None:
        self._config = config

    @abstractmethod
    def internal_handle_config(self, config: C) -> List[M]:
        raise NotImplementedError()

    def handle_reset(self) -> List[M]:
        return self.internal_handle_config(self._config)

    def handle_root_config(self, root_config: Config) -> Optional[List[M]]:
        config = type(self).extract_config(root_config)
        return self.handle_config(config)

    def handle_config(self, config: C) -> Optional[List[M]]:
        if config != self._config:
            return self.internal_handle_config(config)
        else:
            return None


class NullConfigComponent(Component[NullConfig, M]):
    @classmethod
    def extract_config(cls: Type[K], root_config: Config) -> NullConfig:
        return NullConfig()

    def __init__(self) -> None:
        super().__init__(NullConfig())

    def internal_handle_config(self, config: C) -> List[M]:
        return self.handle_reset()

    @abstractmethod
    def handle_reset(self) -> List[M]:
        raise NotImplementedError()
