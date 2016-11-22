import os

here = os.path.abspath(os.path.dirname(__file__))

def make_proxy(*args, **kwargs):
    from hupper.reloader import FileMonitorProxy
    return FileMonitorProxy(*args, **kwargs)

def test_proxy_proxies():
    class DummyMonitor(object):
        started = stopped = joined = False

        def __call__(self, cb):
            self.cb = cb
            return self

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

        def join(self):
            self.joined = True

    monitor = DummyMonitor()
    proxy = make_proxy(monitor)
    assert monitor.cb
    assert not monitor.started and not monitor.stopped and not monitor.joined
    proxy.start()
    assert monitor.started and not monitor.stopped and not monitor.joined
    proxy.stop()
    assert monitor.stopped and monitor.joined

def test_proxy_expands_paths(tmpdir):
    class DummyMonitor(object):
        def __call__(self, cb):
            self.cb = cb
            self.paths = []
            return self

        def add_path(self, path):
            self.paths.append(path)

    monitor = DummyMonitor()
    proxy = make_proxy(monitor)
    proxy.add_path('foo')
    assert monitor.paths == ['foo']

    tmpdir.join('foo.txt').ensure()
    tmpdir.join('bar.txt').ensure()
    rootdir = tmpdir.strpath
    monitor.paths = []
    proxy.add_path(os.path.join(rootdir, '*.txt'))
    assert sorted(monitor.paths) == [
        os.path.join(rootdir, 'bar.txt'),
        os.path.join(rootdir, 'foo.txt'),
    ]

def test_proxy_tracks_changes(capsys):
    class DummyMonitor(object):
        def __call__(self, cb):
            self.cb = cb
            return self

    monitor = DummyMonitor()
    proxy = make_proxy(monitor)
    assert not proxy.is_changed()
    monitor.cb('foo.txt')
    assert proxy.is_changed()
    out, err = capsys.readouterr()
    assert out == 'foo.txt changed; reloading ...\n'
    monitor.cb('foo.txt')
    out, err = capsys.readouterr()
    assert out == ''
    proxy.clear_changes()
    assert not proxy.is_changed()
    monitor.cb('foo.txt')
    out, err = capsys.readouterr()
    assert out == 'foo.txt changed; reloading ...\n'
