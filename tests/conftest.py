from __future__ import print_function
import pytest
import sys

from . import util


def err(msg):
	print(msg, file=sys.stderr)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # execute all other hooks to obtain the report object
    outcome = yield
    rep = outcome.get_result()

    # set an report attribute for each phase of a call, which can
    # be "setup", "call", "teardown"
    setattr(item, "rep_" + rep.when, rep)


@pytest.yield_fixture
def TestAppFactory(request):
    apps = []
    def factory(*args, **kwargs):
        app = util.TestApp(*args, **kwargs)
        apps.append(app)
        return app
    yield factory
    if request.node.rep_call.failed and apps:
    	for app in apps:
            err('-- test app failed --\nname=%s\nargs=%s\ncode=%s' % (
            	app.name, app.args, app.exitcode))
            err('-- stdout --\n%s' % app.stdout)
            err('-- stderr --\n%s' % app.stderr)