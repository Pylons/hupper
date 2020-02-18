import os.path
import time

from . import util

here = os.path.abspath(os.path.dirname(__file__))


def test_myapp_reloads_when_touching_ini(testapp):
    testapp.start('myapp', ['--reload'])
    testapp.wait_for_response()
    time.sleep(2)
    util.touch(os.path.join(here, 'myapp/foo.ini'))
    testapp.wait_for_response()
    testapp.stop()

    assert len(testapp.response) == 2
    assert testapp.stderr != ''


def test_myapp_reloads_when_touching_pyfile(testapp):
    testapp.start('myapp', ['--reload'])
    testapp.wait_for_response()
    time.sleep(2)
    util.touch(os.path.join(here, 'myapp/cli.py'))
    testapp.wait_for_response()
    testapp.stop()

    assert len(testapp.response) == 2
    assert testapp.stderr != ''
