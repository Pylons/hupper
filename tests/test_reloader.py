import os

here = os.path.abspath(os.path.dirname(__file__))

def make_proxy(monitor_factory, logger):
    from hupper.reloader import FileMonitorProxy
    proxy = FileMonitorProxy(logger)
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

    monitor = DummyMonitor()
    proxy = make_proxy(monitor, logger)
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

    monitor = DummyMonitor()
    proxy = make_proxy(monitor, logger)
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

    monitor = DummyMonitor()
    proxy = make_proxy(monitor, logger)
    assert not proxy.is_changed()
    monitor.cb('foo.txt')
    assert proxy.is_changed()
    out = logger.get_output('info')
    assert out == 'foo.txt changed; reloading ...'
    logger.reset()
    monitor.cb('foo.txt')
    out = logger.get_output('info')
    assert out == ''
    logger.reset()
    proxy.clear_changes()
    assert not proxy.is_changed()
    monitor.cb('foo.txt')
    out = logger.get_output('info')
    assert out == 'foo.txt changed; reloading ...'
    logger.reset()
