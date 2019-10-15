import argparse
import runpy
import sys

from .logger import LogLevel
from .reloader import start_reloader


def interval_parser(string):
    """Parses the shutdown or reload interval into an int greater than 0."""
    msg = "Interval must be an int greater than 0"
    try:
        value = int(string)
        if value <= 0:
            raise argparse.ArgumentTypeError(msg)
        return value
    except ValueError:
        raise argparse.ArgumentTypeError(msg)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", dest="module", required=True)
    parser.add_argument("-w", dest="watch", action="append")
    parser.add_argument("-x", dest="ignore", action="append")
    parser.add_argument("-v", dest="verbose", action='store_true')
    parser.add_argument("-q", dest="quiet", action='store_true')
    parser.add_argument("--shutdown-interval", type=interval_parser)
    parser.add_argument("--reload-interval", type=interval_parser)

    args, unknown_args = parser.parse_known_args()

    if args.quiet:
        level = LogLevel.ERROR

    elif args.verbose:
        level = LogLevel.DEBUG

    else:
        level = LogLevel.INFO

    # start_reloader has defaults for some values so we avoid passing
    # arguments if we don't have to
    reloader_kw = {}
    if args.reload_interval is not None:
        reloader_kw['reload_interval'] = args.reload_interval
    if args.shutdown_interval is not None:
        reloader_kw['shutdown_interval'] = args.shutdown_interval

    reloader = start_reloader(
        "hupper.cli.main",
        verbose=level,
        ignore_files=args.ignore,
        **reloader_kw
    )

    sys.argv[1:] = unknown_args
    sys.path.insert(0, "")

    if args.watch:
        reloader.watch_files(args.watch)

    return runpy.run_module(args.module, alter_sys=True, run_name="__main__")
