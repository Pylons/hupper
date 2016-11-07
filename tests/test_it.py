import time

from . import util

def test_myapp_reloads():
    app = util.TestApp('myapp', ['--reload'])
    app.start()
    try:
        time.sleep(1)
        util.touch('myapp/foo.ini')
        time.sleep(3)
    finally:
        app.stop()

    assert app.stderr == ''
    assert app.stdout.count('myapp started') == 2
