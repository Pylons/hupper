import argparse

import pytest

from hupper.cli import shutdown_interval_parser


@pytest.mark.parametrize('value', ['0', "-1"])
def test_shutdown_interval_parser_errors(value):
    with pytest.raises(argparse.ArgumentTypeError):
        shutdown_interval_parser(value)


def test_shutdown_interval_parser():
    assert shutdown_interval_parser("5") == 5
