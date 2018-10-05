import hupper


def test_watch(monkeypatch):

    def start_reloader(worker_path, *args, **kwargs):
        assert worker_path == 'tests.test_watch.myfunc'
        assert kwargs['verbose'] == 1
        start_reloader._called = True

    monkeypatch.setattr('hupper.reloader.start_reloader', start_reloader)

    @hupper.watch(verbose=1)
    def myfunc():
        pass

    myfunc()
    assert start_reloader._called
