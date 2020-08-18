from abc import ABCMeta, abstractmethod
from mido import Message
from mido.frozen import freeze_message, FrozenMessage
from mido.ports import BaseInput, BaseOutput
from pushpluck.base import Closeable, Resettable
from queue import SimpleQueue
from typing import Optional

import logging
import mido
import time


def is_note_msg(msg: FrozenMessage) -> bool:
    return msg.type == 'note_on' or msg.type == 'note_off'


def is_note_on_msg(msg: FrozenMessage) -> bool:
    return msg.type == 'note_on' and msg.velocity > 0


class MidiSource(metaclass=ABCMeta):
    @abstractmethod
    def recv_msg(self) -> FrozenMessage:
        raise NotImplementedError()


class MidiSink(metaclass=ABCMeta):
    @abstractmethod
    def send_msg(self, msg: FrozenMessage) -> None:
        raise NotImplementedError()


class MidiInput(MidiSource, Closeable):
    @classmethod
    def open(cls, in_port_name: str) -> 'MidiInput':
        queue: SimpleQueue[Message] = SimpleQueue()
        in_port = mido.open_input(in_port_name, callback=queue.put_nowait)
        return cls(
            in_port_name=in_port_name,
            in_port=in_port,
            queue=queue
        )

    def __init__(
        self,
        in_port_name: str,
        in_port: BaseInput,
        queue: 'SimpleQueue[Message]',
    ) -> None:
        self._in_port_name = in_port_name
        self._in_port = in_port
        self._queue = queue

    def close(self) -> None:
        self._in_port.close()

    def recv_msg(self) -> FrozenMessage:
        mut_msg = self._queue.get()
        msg = freeze_message(mut_msg)
        logging.debug('Received message from %s: %s', self._in_port_name, msg)
        return msg


class MidiOutput(MidiSink, Resettable, Closeable):
    @classmethod
    def open(
        cls,
        out_port_name: str,
        virtual: bool = False,
        delay: Optional[float] = None
    ) -> 'MidiOutput':
        out_port = mido.open_output(out_port_name, virtual=virtual)
        return cls(
            out_port_name=out_port_name,
            out_port=out_port,
            delay=delay
        )

    def __init__(
        self,
        out_port_name: str,
        out_port: BaseOutput,
        delay: Optional[float]
    ) -> None:
        self._out_port_name = out_port_name
        self._out_port = out_port
        self._delay = delay
        self._last_sent = 0.0

    def reset(self) -> None:
        self._out_port.reset()

    def close(self) -> None:
        self._out_port.close()

    def send_msg(self, msg: FrozenMessage) -> None:
        if self._delay is not None:
            now = time.monotonic()
            lim = self._last_sent + self._delay
            diff = lim - now
            if diff > 0:
                time.sleep(diff)
                self._last_sent = lim
            else:
                self._last_sent = now
        logging.debug('Sending message to %s: %s', self._out_port_name, msg)
        self._out_port.send(msg)
