from . import util


def test_myapp_reloads():
    with util.TestApp('myapp', ['--reload']) as app:
        app.wait_for_response(interval=1)
        util.touch('myapp/foo.ini')
        app.wait_for_response()
        app.stop()

        assert len(app.response) == 2
        assert app.stderr == ''
        assert app.stdout != ''
