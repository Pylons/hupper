from __future__ import print_function
import pytest
import sys

from . import util


def err(msg):  # pragma: no cover
    print(msg, file=sys.stderr)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    # set an report attribute for each phase of a call, which can
    # be "setup", "call", "teardown"
    setattr(item, "rep_" + rep.when, rep)


@pytest.fixture
def testapp(request):
    app = util.TestApp()
    try:
        yield app
    finally:
        app.stop()
    if (
        request.node.rep_call.failed
        and app.exitcode is not None
    ):  # pragma: no cover
        err('-- test app failed --\nname=%s\nargs=%s\ncode=%s' % (
            app.name, app.args, app.exitcode))
        err('-- stdout --\n%s' % app.stdout)
        err('-- stderr --\n%s' % app.stderr)

class DummyLogger:
    def __init__(self):
        self.messages = []

    def reset(self):
        self.messages = []

    def get_output(self, *levels):
        if not levels:
            levels = {'info', 'error', 'debug'}
        return '\n'.join(msg for lvl, msg in self.messages if lvl in levels)

    def info(self, msg):
        self.messages.append(('info', msg))

    def error(self, msg):
        self.messages.append(('error', msg))

    def debug(self, msg):
        self.messages.append(('debug', msg))

@pytest.fixture
def logger():
    return DummyLogger()
