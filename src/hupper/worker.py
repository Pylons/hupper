import importlib
import multiprocessing
import os
import sys
import threading
import time
import traceback

from .compat import (
    interrupt_main,
    get_pyc_path,
    get_py_path,
)
from .interfaces import IReloaderProxy
from .ipc import (
    recv_fd,
    send_fd,
)


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
        """Check sys.modules for paths to add to our path set."""
        with self.lock:
            for path in iter_source_paths(iter_module_paths()):
                if path not in self.paths:
                    self.paths.add(path)
                    self.callback(path)

    def search_traceback(self, tb):
        with self.lock:
            for filename, line, funcname, txt in traceback.extract_tb(tb):
                path = os.path.abspath(filename)
                if path not in self.paths:
                    self.paths.add(path)
                    self.callback(path)


def iter_source_paths(paths):
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
            while self.pipe.recv_bytes():  # pragma: nocover
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
        self.files_queue = multiprocessing.Queue()
        self.pipe, self._c2p = multiprocessing.Pipe()
        self.terminated = False
        self.pid = None
        self.exitcode = None

    def start(self):
        # prepare to close our stdin by making a new copy that is
        # not attached to sys.stdin - we will pass this to the worker while
        # it's running and then restore it when the worker is done
        # we dup it early such that it's inherited by the child
        self.stdin_fd = os.dup(sys.stdin.fileno())

        # py34 and above sets CLOEXEC automatically on file descriptors
        # NOTE: this isn't usually an issue because multiprocessing doesn't
        # actually exec on linux/macos, but we're depending on the behavior
        if hasattr(os, 'set_inheritable'):  # pragma: nocover
            os.set_inheritable(self.stdin_fd, True)

        kw = dict(
            spec=self.worker_spec,
            spec_args=self.worker_args,
            spec_kwargs=self.worker_kwargs,
            files_queue=self.files_queue,
            pipe=self._c2p,
            parent_pipe=self.pipe,
        )
        self.process = multiprocessing.Process(target=worker_main, kwargs=kw)
        self.process.start()

        self.pid = self.process.pid

        # we no longer control the worker's end of the pipe
        self._c2p.close()
        del self._c2p

        # send the stdin handle to the worker
        send_fd(self.pipe, self.stdin_fd, self.pid)

    def is_alive(self):
        if self.process:
            return self.process.is_alive()
        return False

    def terminate(self):
        self.terminated = True
        self.process.terminate()

    def join(self):
        self.process.join()
        self.exitcode = self.process.exitcode

        if self.stdin_fd is not None:
            try:
                os.close(self.stdin_fd)
            except:  # pragma: nocover
                pass
            finally:
                self.stdin_fd = None

        if self.pipe is not None:
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
    def __init__(self, files_queue, pipe):
        self.files_queue = files_queue
        self.pipe = pipe

    def watch_files(self, files):
        for file in files:
            self.files_queue.put(os.path.abspath(file))

    def trigger_reload(self):
        self.pipe.send_bytes(b'1')


def worker_main(spec, files_queue, pipe, parent_pipe, spec_args=None,
                spec_kwargs=None):
    if spec_args is None:
        spec_args = []
    if spec_kwargs is None:
        spec_kwargs = {}

    # close the parent end of the pipe, we aren't using it in the worker
    parent_pipe.close()
    del parent_pipe

    # use the stdin fd passed in from the reloader process
    sys.stdin = recv_fd(pipe, 'r')

    # disable pyc files for project code because it can cause timestamp
    # issues in which files are reloaded twice
    sys.dont_write_bytecode = True

    global _reloader_proxy
    _reloader_proxy = ReloaderProxy(files_queue, pipe)

    parent_watcher = WatchForParentShutdown(pipe)
    parent_watcher.start()

    poller = WatchSysModules(files_queue.put)
    poller.start()

    # import the worker path before polling sys.modules
    modname, funcname = spec.rsplit('.', 1)
    module = importlib.import_module(modname)
    func = getattr(module, funcname)

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
