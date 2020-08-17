from argparse import ArgumentParser
from pushpluck import constants
from pushpluck.config import default_scheme, init_config
from pushpluck.menu import default_menu_layout
from pushpluck.plucked import Plucked
from pushpluck.push import match_event, push_ports_context, PushOutput, PushPorts

import logging


def main_with_ports(ports: PushPorts, min_velocity: int) -> None:
    scheme = default_scheme()
    layout = default_menu_layout()
    config = init_config(min_velocity)
    push = PushOutput(ports.midi_out)
    # Start with a clean slate
    logging.info('resetting push')
    push.reset()
    try:
        plucked = Plucked(push, ports.midi_processed, scheme, layout, config)
        logging.info('resetting controller')
        plucked.reset()
        logging.info('controller ready')
        while True:
            msg = ports.midi_in.recv_msg()
            event = match_event(msg)
            if event is not None:
                plucked.handle_event(event)
    except KeyboardInterrupt:
        pass
    finally:
        # Send all notes off
        logging.info('final all notes off')
        ports.midi_processed.reset()
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
