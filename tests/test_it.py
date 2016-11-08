from . import util


def test_myapp_reloads_when_touching_ini():
    with util.TestApp('myapp', ['--reload']) as app:
        app.wait_for_response(interval=1)
        util.touch('myapp/foo.ini')
        app.wait_for_response()
        app.stop()

        assert len(app.response) == 2
        assert app.stderr == ''
        assert app.stdout != ''


def test_myapp_reloads_when_touching_pyfile():
    with util.TestApp('myapp', ['--reload']) as app:
        app.wait_for_response(interval=1)
        util.touch('myapp/__main__.py')
        app.wait_for_response()
        app.stop()

        assert len(app.response) == 2
        assert app.stderr == ''
        assert app.stdout != ''
