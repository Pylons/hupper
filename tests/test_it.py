import os.path
import time

from . import util

here = os.path.abspath(os.path.dirname(__file__))


def test_myapp_reloads_when_touching_ini(TestAppFactory):
    with TestAppFactory('myapp', ['--reload']) as app:
        app.wait_for_response(interval=1)
        util.touch(os.path.join(here, 'myapp/foo.ini'))
        app.wait_for_response()
        app.stop()

        assert len(app.response) == 2
        assert app.stderr == ''
        assert app.stdout != ''


def test_myapp_reloads_when_touching_pyfile(TestAppFactory):
    with TestAppFactory('myapp', ['--reload']) as app:
        app.wait_for_response(interval=1)
        util.touch(os.path.join(here, 'myapp/cli.py'))
        app.wait_for_response()
        app.stop()

        assert len(app.response) == 2
        assert app.stderr == ''
        assert app.stdout != ''
