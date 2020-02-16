import os

here = os.path.abspath(os.path.dirname(__file__))


class DummyCallback:
    called = False

    def __call__(self, paths):
        self.called = paths


def make_proxy(monitor_factory, callback, logger):
    from hupper.reloader import FileMonitorProxy

    proxy = FileMonitorProxy(callback, logger)
    proxy.monitor = monitor_factory(proxy.file_changed)
    return proxy


def test_proxy_proxies(logger):
    class DummyMonitor(object):
        started = stopped = joined = False

        def __call__(self, cb, **kw):
            self.cb = cb
            return self

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

        def join(self):
            self.joined = True

    cb = DummyCallback()
    monitor = DummyMonitor()
    proxy = make_proxy(monitor, cb, logger)
    assert monitor.cb
    assert not monitor.started and not monitor.stopped and not monitor.joined
    proxy.start()
    assert monitor.started and not monitor.stopped and not monitor.joined
    proxy.stop()
    assert monitor.stopped and monitor.joined


def test_proxy_expands_paths(tmpdir, logger):
    class DummyMonitor(object):
        def __call__(self, cb, **kw):
            self.cb = cb
            self.paths = []
            return self

        def add_path(self, path):
            self.paths.append(path)

    cb = DummyCallback()
    monitor = DummyMonitor()
    proxy = make_proxy(monitor, cb, logger)
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


def test_proxy_tracks_changes(logger):
    class DummyMonitor(object):
        def __call__(self, cb, **kw):
            self.cb = cb
            return self

    cb = DummyCallback()
    monitor = DummyMonitor()
    proxy = make_proxy(monitor, cb, logger)
    monitor.cb('foo.txt')
    assert cb.called == {'foo.txt'}
    out = logger.get_output('info')
    assert out == 'foo.txt changed; reloading ...'
    logger.reset()
    monitor.cb('foo.txt')
    out = logger.get_output('info')
    assert out == ''
    logger.reset()
    cb.called = False
    proxy.clear_changes()
    monitor.cb('foo.txt')
    out = logger.get_output('info')
    assert out == 'foo.txt changed; reloading ...'
    logger.reset()


def test_ignore_files():
    class DummyMonitor(object):
        paths = set()

        def add_path(self, path):
            self.paths.add(path)

    from hupper.reloader import FileMonitorProxy

    cb = DummyCallback()
    proxy = FileMonitorProxy(cb, None, {'/a/*'})
    monitor = proxy.monitor = DummyMonitor()

    path = 'foo.txt'
    assert path not in monitor.paths
    proxy.add_path(path)
    assert path in monitor.paths

    path = '/a/foo.txt'
    assert path not in monitor.paths
    proxy.add_path(path)
    assert path not in monitor.paths
