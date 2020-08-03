from pushpluck import constants
from pushpluck.controller import Controller, Profile
from pushpluck.push import PushOutput, PushPorts, cache_colors, push_ports_context

import logging


def main_with_ports(ports: PushPorts) -> None:
    profile = Profile(
        instrument_name='Guitar',
        tuning_name='Standard',
        tuning=constants.STANDARD_TUNING
    )
    push = PushOutput(ports.midi_out)
    # Start with a clean slate
    logging.info('resetting push')
    push.reset()
    try:
        controller = Controller(push, ports.midi_processed, profile)
        logging.info('resetting controller')
        controller.reset()
        logging.info('controller ready')
        while True:
            msg = ports.midi_in.recv_msg()
            controller.send_msg(msg)
    finally:
        # End with a clean slate
        logging.info('final reset of push')
        push.reset()


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        format='%(asctime)s %(levelname)s %(filename)s:%(lineno)d -- %(message)s',
        level=log_level
    )


def main():
    configure_logging('INFO')
    cache_colors()
    with push_ports_context(delay=constants.DEFAULT_SLEEP_SECS) as ports:
        main_with_ports(ports)
    logging.info('done')


if __name__ == '__main__':
    main()
