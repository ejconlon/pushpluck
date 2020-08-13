from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from pushpluck.config import Config
from typing import Generic, Optional, Type, TypeVar


C = TypeVar('C', bound='ComponentConfig')
S = TypeVar('S', bound='ComponentState')
R = TypeVar('R')
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


class ComponentState(Generic[C], metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def initialize(cls: Type[S], config: C) -> S:
        raise NotImplementedError()


@dataclass
class NullState(ComponentState[C]):
    pass

    @classmethod
    def initialize(cls, config: C) -> 'NullState':
        return cls()


class Component(Generic[C, S, R], metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def extract_config(cls: Type[K], root_config: Config) -> C:
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def initialize_state(cls: Type[K], config: C) -> S:
        raise NotImplementedError()

    def __init__(self, config: C) -> None:
        self._config = config
        self._state = type(self).initialize_state(config)

    @abstractmethod
    def handle_reset(self) -> R:
        raise NotImplementedError()

    @abstractmethod
    def internal_handle_config(self, config: C) -> R:
        raise NotImplementedError()

    def handle_root_config(self, root_config: Config) -> Optional[R]:
        config = type(self).extract_config(root_config)
        return self.handle_config(config)

    def handle_config(self, config: C) -> Optional[R]:
        if config != self._config:
            return self.internal_handle_config(config)
        else:
            return None


class NullConfigComponent(Component[NullConfig, S, R]):
    @classmethod
    def extract_config(cls: Type[K], root_config: Config) -> NullConfig:
        return NullConfig.extract(root_config)

    def internal_handle_config(self, config: C) -> R:
        return self.handle_reset()
