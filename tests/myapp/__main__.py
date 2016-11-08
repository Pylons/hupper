import argparse
import hupper
import os
import sys
import time

here = os.path.dirname(__file__)


def parse_options(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('--reload', action='store_true')
    parser.add_argument('--callback-file')
    parser.add_argument('--watch-file', action='append', dest='watch_files',
                        default=[])
    parser.add_argument('--watchdog', action='store_true')
    parser.add_argument('--poll', action='store_true')
    parser.add_argument('--poll-interval', type=int)
    parser.add_argument('--reload-interval', type=int)
    return parser.parse_args(args)


def main():
    args = parse_options(sys.argv[1:])
    if args.reload:
        kw = {}
        if args.poll:
            from hupper.polling import PollingFileMonitor
            pkw = {}
            if args.poll_interval:
                pkw['poll_interval'] = args.poll_interval
            kw['monitor_factory'] = lambda cb: PollingFileMonitor(cb, **pkw)

        if args.watchdog:
            from hupper.watchdog import WatchdogFileMonitor
            kw['monitor_factory'] = WatchdogFileMonitor

        if args.reload_interval:
            kw['reload_interval'] = args.reload_interval

        reloader = hupper.start_reloader(__name__ + '.main', **kw)

    if hupper.is_active():
        reloader.watch_files([os.path.join(here, 'foo.ini')])
        reloader.watch_files(args.watch_files)

    if args.callback_file:
        with open(args.callback_file, 'ab') as fp:
            fp.write('{:d}\n'.format(int(time.time())).encode('utf8'))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
