import argparse
import runpy
import sys

from .logger import LogLevel
from .reloader import start_reloader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", dest="module", required=True)
    parser.add_argument("-w", dest="watch", action="append")
    parser.add_argument("-x", dest="ignore", action="append")
    parser.add_argument("-v", dest="verbose", action='store_true')
    parser.add_argument("-q", dest="quiet", action='store_true')

    args, unknown_args = parser.parse_known_args()

    if args.quiet:
        level = LogLevel.ERROR

    elif args.verbose:
        level = LogLevel.DEBUG

    else:
        level = LogLevel.INFO

    reloader = start_reloader(
        "hupper.cli.main", verbose=level, ignore_files=args.ignore
    )

    sys.argv[1:] = unknown_args
    sys.path.insert(0, "")

    if args.watch:
        reloader.watch_files(args.watch)

    return runpy.run_module(args.module, alter_sys=True, run_name="__main__")
