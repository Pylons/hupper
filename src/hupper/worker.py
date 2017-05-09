import os
import signal
import sys
import threading
import time
import traceback

from .compat import get_pyc_path
from .compat import get_py_path
from .compat import interrupt_main
from .interfaces import IReloaderProxy
from . import ipc


class WatchSysModules(threading.Thread):
    """ Poll ``sys.modules`` for imported modules."""
    poll_interval = 1

    def __init__(self, callback):
        super(WatchSysModules, self).__init__()
        self.paths = set()
        self.callback = callback
        self.lock = threading.Lock()
        self.stopped = False

    def run(self):
        while not self.stopped:
            self.update_paths()
            time.sleep(self.poll_interval)

    def stop(self):
        self.stopped = True

    def update_paths(self):
        """ Check sys.modules for paths to add to our path set."""
        new_paths = []
        with self.lock:
            for path in expand_source_paths(iter_module_paths()):
                if path not in self.paths:
                    self.paths.add(path)
                    new_paths.append(path)
        if new_paths:
            self.callback(new_paths)

    def search_traceback(self, tb):
        """ Inspect a traceback for new paths to add to our path set."""
        new_paths = []
        with self.lock:
            for filename, line, funcname, txt in traceback.extract_tb(tb):
                path = os.path.abspath(filename)
                if path not in self.paths:
                    self.paths.add(path)
                    new_paths.append(path)
        if new_paths:
            self.callback(new_paths)


def expand_source_paths(paths):
    """ Convert pyc files into their source equivalents."""
    for src_path in paths:
        yield src_path

        # track pyc files for py files
        if src_path.endswith('.py'):
            pyc_path = get_pyc_path(src_path)
            if pyc_path:
                yield pyc_path

        # track py files for pyc files
        elif src_path.endswith('.pyc'):
            py_path = get_py_path(src_path)
            if py_path:
                yield py_path


def iter_module_paths(modules=None):
    """ Yield paths of all imported modules."""
    modules = modules or list(sys.modules.values())
    for module in modules:
        try:
            filename = module.__file__
        except (AttributeError, ImportError):  # pragma: nocover
            continue
        if filename is not None:
            abs_filename = os.path.abspath(filename)
            if os.path.isfile(abs_filename):
                yield abs_filename


class WatchForParentShutdown(threading.Thread):
    """ Watch the pipe to ensure the parent is still alive."""
    def __init__(self, pipe):
        super(WatchForParentShutdown, self).__init__()
        self.pipe = pipe

    def run(self):
        try:
            # wait until the pipe breaks
            while self.pipe.recv():  # pragma: nocover
                pass
        except EOFError:
            pass
        interrupt_main()


class Worker(object):
    """ A helper object for managing a worker process lifecycle. """
    def __init__(self, spec, args=None, kwargs=None):
        super(Worker, self).__init__()
        self.worker_spec = spec
        self.worker_args = args
        self.worker_kwargs = kwargs
        self.pipe, self._child_pipe = ipc.Pipe()
        self.terminated = False
        self.pid = None
        self.process = None
        self.exitcode = None
        self.stdin_termios = None

    def start(self):
        self.stdin_termios = ipc.snapshot_termios(sys.stdin.fileno())

        kw = dict(
            spec=self.worker_spec,
            spec_args=self.worker_args,
            spec_kwargs=self.worker_kwargs,
            pipe=self._child_pipe,
        )
        self.process = ipc.spawn(
            'hupper.worker.worker_main',
            kwargs=kw,
            pass_fds=[self._child_pipe.r_fd, self._child_pipe.w_fd],
        )
        self.pid = self.process.pid

        # activate the pipe after forking
        self.pipe.activate()

        # kill the child side of the pipe after forking as the child is now
        # responsible for it
        self._child_pipe.close()

    def is_alive(self):
        if self.process:
            return self.process.poll() is None
        return False

    def terminate(self):
        self.terminated = True
        self.process.terminate()

    def join(self):
        self.process.wait()
        self.exitcode = self.process.returncode

        if self.stdin_termios:
            ipc.restore_termios(sys.stdin.fileno(), self.stdin_termios)

        if self.pipe:
            try:
                self.pipe.close()
            except:  # pragma: nocover
                pass
            finally:
                self.pipe = None


# set when the current process is being monitored
_reloader_proxy = None


def get_reloader():
    """
    Get a reference to the current :class:`hupper.interfaces.IReloaderProxy`.

    Raises a ``RuntimeError`` if the current process is not actively being
    monitored by a parent process.

    """
    if _reloader_proxy is None:
        raise RuntimeError('process is not controlled by hupper')
    return _reloader_proxy


def is_active():
    """
    Return ``True`` if the current process being monitored by a parent process.

    """
    return _reloader_proxy is not None


class ReloaderProxy(IReloaderProxy):
    def __init__(self, pipe):
        self.pipe = pipe

    def watch_files(self, files):
        self.pipe.send(('watch', files))

    def trigger_reload(self):
        self.pipe.send(('reload',))


def worker_main(spec, pipe, spec_args=None, spec_kwargs=None):
    if spec_args is None:
        spec_args = []
    if spec_kwargs is None:
        spec_kwargs = {}

    # activate the pipe after forking
    pipe.activate()

    # SIGHUP is not supported on windows
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, signal.SIG_IGN)

    # disable pyc files for project code because it can cause timestamp
    # issues in which files are reloaded twice
    sys.dont_write_bytecode = True

    global _reloader_proxy
    _reloader_proxy = ReloaderProxy(pipe)

    parent_watcher = WatchForParentShutdown(pipe)
    parent_watcher.daemon = True
    parent_watcher.start()

    poller = WatchSysModules(_reloader_proxy.watch_files)
    poller.daemon = True
    poller.start()

    # import the worker path before polling sys.modules
    func = ipc.resolve_spec(spec)

    # start the worker
    try:
        func(*spec_args, **spec_kwargs)
    except:
        try:
            # attempt to send imported paths to the master prior to crashing
            poller.update_paths()
            poller.search_traceback(sys.exc_info()[2])
            poller.stop()
            poller.join()
        except:  # pragma: no cover
            pass
        raise
