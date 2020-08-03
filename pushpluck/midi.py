from abc import ABCMeta, abstractmethod
# TODO use frozenmessage
from mido import Message
from mido.ports import BaseInput, BaseOutput
from pushpluck.base import Closeable
from queue import SimpleQueue
from typing import Optional

import mido
import time


class MidiSource(metaclass=ABCMeta):
    @abstractmethod
    def recv_msg(self) -> Message:
        raise NotImplementedError()


class MidiSink(metaclass=ABCMeta):
    @abstractmethod
    def send_msg(self, msg: Message) -> None:
        raise NotImplementedError()


class MidiInput(MidiSource, Closeable):
    @classmethod
    def open(cls, in_port_name: str) -> 'MidiInput':
        queue: SimpleQueue[Message] = SimpleQueue()
        in_port = mido.open_input(in_port_name, callback=queue.put_nowait)
        return cls(in_port=in_port, queue=queue)

    def __init__(self, in_port: BaseInput, queue: 'SimpleQueue[Message]') -> None:
        self._in_port = in_port
        self._queue = queue

    def close(self) -> None:
        self._in_port.close()

    def recv_msg(self) -> Message:
        return self._queue.get()


class MidiOutput(MidiSink, Closeable):
    @classmethod
    def open(cls, out_port_name: str, virtual: bool = False, delay: Optional[float] = None) -> 'MidiOutput':
        out_port = mido.open_output(out_port_name, virtual=virtual)
        return cls(out_port=out_port, delay=delay)

    def __init__(self, out_port: BaseOutput, delay: Optional[float] = None) -> None:
        self._out_port = out_port
        self._delay = delay
        self._last_sent = 0.0

    def close(self) -> None:
        self._out_port.close()

    def send_msg(self, msg: Message) -> None:
        if self._delay is not None:
            now = time.monotonic()
            lim = self._last_sent + self._delay
            diff = lim - now
            if diff > 0:
                time.sleep(diff)
                self._last_sent = lim
            else:
                self._last_sent = now
        self._out_port.send(msg)
