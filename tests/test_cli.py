import argparse
import pytest

from hupper.cli import interval_parser


@pytest.mark.parametrize('value', ['0', "-1"])
def test_interval_parser_errors(value):
    with pytest.raises(argparse.ArgumentTypeError):
        interval_parser(value)


def test_interval_parser():
    assert interval_parser("5") == 5
