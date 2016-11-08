from . import util


def test_myapp_reloads(tmpdir):
    tmpfile = tmpdir.join('watch.txt').strpath
    util.touch(tmpfile)
    app = util.TestApp('myapp', ['--reload', tmpfile])
    app.start()
    try:
        size = util.wait_for_change(tmpfile, interval=1)
        util.touch('myapp/foo.ini')
        size = util.wait_for_change(tmpfile, last_size=size)
    finally:
        app.stop()

    assert size == 22
    assert app.stderr == ''
