from argparse import ArgumentParser
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


def make_parser() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument('--log-level', default='INFO')
    parser.add_argument('--push-delay', type=float, default=constants.DEFAULT_PUSH_DELAY)
    parser.add_argument('--push-port', default=constants.DEFAULT_PUSH_PORT_NAME)
    parser.add_argument('--processed-port', default=constants.DEFAULT_PROCESSED_PORT_NAME)
    return parser


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        format='%(asctime)s %(levelname)s %(filename)s:%(lineno)d -- %(message)s',
        level=log_level
    )


def main():
    parser = make_parser()
    args = parser.parse_args()
    configure_logging(args.log_level)
    cache_colors()
    with push_ports_context(
        push_port_name=args.push_port,
        processed_port_name=args.processed_port,
        delay=args.push_delay
    ) as ports:
        main_with_ports(ports)
    logging.info('done')


if __name__ == '__main__':
    main()
