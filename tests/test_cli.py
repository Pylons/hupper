import argparse
import sys

import pytest

from hupper import cli as cli_module
from hupper.cli import interval_parser


@pytest.mark.parametrize('value', ['0', "-1"])
def test_interval_parser_errors(value):
    with pytest.raises(argparse.ArgumentTypeError):
        interval_parser(value)


def test_interval_parser():
    assert interval_parser("5") == 5


class DummyReloader:
    def watch_files(self, files):
        self.watched = files


def test_main_missing_module(monkeypatch, capsys):
    """A typo'd -m module fails fast with a clean error, not a traceback."""
    monkeypatch.setattr(
        cli_module,
        'start_reloader',
        lambda *args, **kwargs: DummyReloader(),
    )
    monkeypatch.setattr(
        sys, 'argv', ['hupper', '-m', 'nonexistent_module_xyz']
    )
    with pytest.raises(SystemExit) as exc:
        cli_module.main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert 'No module named' in captured.err
    assert 'Traceback' not in captured.err


def test_main_broken_module_still_raises(monkeypatch, tmp_path):
    """A module that exists but fails internally still raises ImportError."""
    monkeypatch.setattr(
        cli_module,
        'start_reloader',
        lambda *args, **kwargs: DummyReloader(),
    )
    monkeypatch.setattr(sys, 'argv', ['hupper', '-m', 'broken_mod_xyz'])
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / 'broken_mod_xyz.py').write_text(
        'import nonexistent_dependency_xyz\n'
    )
    with pytest.raises(ImportError):
        cli_module.main()
