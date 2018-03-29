import argparse
import runpy
import sys

from .reloader import start_reloader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", dest="module", required=True)
    parser.add_argument("-w", dest="watch", action="append")

    args, unknown_args = parser.parse_known_args()

    reloader = start_reloader("hupper.cli.main")

    sys.argv[1:] = unknown_args
    sys.path.insert(0, "")

    if args.watch:
        reloader.watch_files(args.watch)

    return runpy.run_module(
        args.module,
        alter_sys=True,
        run_name="__main__")
