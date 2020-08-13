from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from pushpluck.config import Config
from typing import Generic, Optional, Type, TypeVar


C = TypeVar('C', bound='ComponentConfig')
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


class Component(Generic[C, R], metaclass=ABCMeta):
    @classmethod
    @abstractmethod
    def extract_config(cls: Type[K], root_config: Config) -> C:
        raise NotImplementedError()

    def __init__(self, config: C) -> None:
        self._config = config

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


class NullConfigComponent(Component[NullConfig, R]):
    @classmethod
    def extract_config(cls: Type[K], root_config: Config) -> NullConfig:
        return NullConfig()

    def __init__(self) -> None:
        super().__init__(NullConfig())

    def internal_handle_config(self, config: C) -> R:
        return self.handle_reset()
