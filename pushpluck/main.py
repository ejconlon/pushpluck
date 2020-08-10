from argparse import ArgumentParser
from pushpluck import constants
from pushpluck.controller import Controller, Profile
from pushpluck.push import push_ports_context, PushOutput, PushPorts
from pushpluck.scale import SCALE_LOOKUP, NoteName

import logging


def main_with_ports(ports: PushPorts, min_velocity: int) -> None:
    profile = Profile(
        instrument_name='Guitar',
        tuning_name='Standard',
        tuning=constants.STANDARD_TUNING
    )
    scale = SCALE_LOOKUP['Major']
    push = PushOutput(ports.midi_out)
    # Start with a clean slate
    logging.info('resetting push')
    push.reset()
    try:
        controller = Controller(push, ports.midi_processed, min_velocity, profile, scale, NoteName.C)
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
    parser.add_argument('--min-velocity', type=int, default=0)
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
    with push_ports_context(
        push_port_name=args.push_port,
        processed_port_name=args.processed_port,
        delay=args.push_delay
    ) as ports:
        main_with_ports(ports, args.min_velocity)
    logging.info('done')


if __name__ == '__main__':
    main()
