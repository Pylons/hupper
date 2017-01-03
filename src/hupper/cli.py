from __future__ import print_function

import argparse
import sys

from .reloader import start_reloader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", dest="module", required=True)

    args, unknown_args = parser.parse_known_args()

    sys.argv[1:] = unknown_args
    sys.path.insert(0, "")

    start_reloader(
        "runpy.run_module",
        worker_args=[args.module],
        worker_kwargs={"alter_sys": True, "run_name": "__main__"})
