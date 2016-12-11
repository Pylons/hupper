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


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    opts = parse_options(args)
    if opts.reload:
        kw = {}
        if opts.poll:
            from hupper.polling import PollingFileMonitor
            pkw = {}
            if opts.poll_interval:
                pkw['poll_interval'] = opts.poll_interval
            kw['monitor_factory'] = lambda cb: PollingFileMonitor(cb, **pkw)

        if opts.watchdog:
            from hupper.watchdog import WatchdogFileMonitor
            kw['monitor_factory'] = WatchdogFileMonitor

        if opts.reload_interval:
            kw['reload_interval'] = opts.reload_interval

        hupper.start_reloader(__name__ + '.main', **kw)

    if hupper.is_active():
        hupper.get_reloader().watch_files([os.path.join(here, 'foo.ini')])
        hupper.get_reloader().watch_files(opts.watch_files)

    if opts.callback_file:
        with open(opts.callback_file, 'ab') as fp:
            fp.write('{:d}\n'.format(int(time.time())).encode('utf8'))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
