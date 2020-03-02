import os
import signal
import sys
import sysconfig
import threading
import time
import traceback

from . import ipc
from .compat import get_py_path, get_site_packages, interrupt_main
from .interfaces import IReloaderProxy
from .utils import resolve_spec


class WatchSysModules(threading.Thread):
    """ Poll ``sys.modules`` for imported modules."""

    poll_interval = 1
    ignore_system_paths = True

    def __init__(self, callback):
        super(WatchSysModules, self).__init__()
        self.paths = set()
        self.callback = callback
        self.lock = threading.Lock()
        self.stopped = False
        self.system_paths = get_system_paths()

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
            self.watch_paths(new_paths)

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
            self.watch_paths(new_paths)

    def watch_paths(self, paths):
        if self.ignore_system_paths:
            paths = [path for path in paths if not self.in_system_paths(path)]
        if paths:
            self.callback(paths)

    def in_system_paths(self, path):
        # use realpath to only ignore files that live in a system path
        # versus a symlink which lives elsewhere
        path = os.path.realpath(path)
        for prefix in self.system_paths:
            if path.startswith(prefix):
                return True
        return False


def get_system_paths():
    paths = get_site_packages()
    for name in {'stdlib', 'platstdlib', 'platlib', 'purelib'}:
        path = sysconfig.get_path(name)
        if path is not None:
            paths.append(path)
    return paths


def expand_source_paths(paths):
    """ Convert pyc files into their source equivalents."""
    for src_path in paths:
        # only track the source path if we can find it to avoid double-reloads
        # when the source and the compiled path change because on some
        # platforms they are not changed at the same time
        if src_path.endswith(('.pyc', '.pyo')):
            py_path = get_py_path(src_path)
            if os.path.exists(py_path):
                src_path = py_path
        yield src_path


def iter_module_paths(modules=None):
    """ Yield paths of all imported modules."""
    modules = modules or list(sys.modules.values())
    for module in modules:
        try:
            filename = module.__file__
        except (AttributeError, ImportError):  # pragma: no cover
            continue
        if filename is not None:
            abs_filename = os.path.abspath(filename)
            if os.path.isfile(abs_filename):
                yield abs_filename


class Worker(object):
    """ A helper object for managing a worker process lifecycle. """

    def __init__(self, spec, args=None, kwargs=None):
        super(Worker, self).__init__()
        self.worker_spec = spec
        self.worker_args = args
        self.worker_kwargs = kwargs
        self.pipe, self._child_pipe = ipc.Pipe()
        self.pid = None
        self.process = None
        self.exitcode = None
        self.stdin_termios = None

    def start(self, on_packet=None):
        self.stdin_termios = ipc.snapshot_termios(sys.stdin)

        kw = dict(
            spec=self.worker_spec,
            spec_args=self.worker_args,
            spec_kwargs=self.worker_kwargs,
            pipe=self._child_pipe,
        )
        self.process = ipc.spawn(
            __name__ + '.worker_main',
            kwargs=kw,
            pass_fds=[self._child_pipe.r_fd, self._child_pipe.w_fd],
        )
        self.pid = self.process.pid

        # activate the pipe after forking
        self.pipe.activate(on_packet)

        # kill the child side of the pipe after forking as the child is now
        # responsible for it
        self._child_pipe.close()

    @property
    def is_alive(self):
        if self.exitcode is not None:
            return False
        if self.process:
            return ipc.wait(self.process, timeout=0) is None
        return False

    def kill(self, soft=False):
        return ipc.kill(self.process, soft=soft)

    def wait(self, timeout=None):
        return ipc.wait(self.process, timeout=timeout)

    def join(self):
        self.exitcode = self.wait()

        if self.stdin_termios:
            ipc.restore_termios(sys.stdin, self.stdin_termios)

        if self.pipe:
            try:
                self.pipe.close()
            except Exception:  # pragma: no cover
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
        files = [os.path.abspath(f) for f in files]
        self.pipe.send(('watch_files', files))

    def trigger_reload(self):
        self.pipe.send(('reload',))


def watch_control_pipe(pipe):
    def handle_packet(packet):
        if packet is None:
            interrupt_main()

    pipe.activate(handle_packet)


def worker_main(spec, pipe, spec_args=None, spec_kwargs=None):
    if spec_args is None:
        spec_args = []
    if spec_kwargs is None:
        spec_kwargs = {}

    # activate the pipe after forking
    watch_control_pipe(pipe)

    # SIGHUP is not supported on windows
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, signal.SIG_IGN)

    # disable pyc files for project code because it can cause timestamp
    # issues in which files are reloaded twice
    sys.dont_write_bytecode = True

    global _reloader_proxy
    _reloader_proxy = ReloaderProxy(pipe)

    poller = WatchSysModules(_reloader_proxy.watch_files)
    poller.daemon = True
    poller.start()

    # import the worker path before polling sys.modules
    func = resolve_spec(spec)

    # start the worker
    try:
        func(*spec_args, **spec_kwargs)
    except BaseException:  # catch any error
        try:
            # add files from the traceback before crashing
            poller.search_traceback(sys.exc_info()[2])
        except Exception:  # pragma: no cover
            pass
        raise
    finally:
        try:
            # attempt to send imported paths to the master prior to closing
            poller.update_paths()
            poller.stop()
            poller.join()
        except Exception:  # pragma: no cover
            pass
