import importlib
import multiprocessing
import os
import sys
import threading
import time

from .compat import interrupt_main
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

    def run(self):
        while True:
            self.update_paths()
            time.sleep(self.poll_interval)

    def update_paths(self):
        """Check sys.modules for paths to add to our path set."""
        for path in get_module_paths():
            if path not in self.paths:
                self.paths.add(path)
                self.callback(path)


def get_module_paths(modules=None):
    """Yield paths of all imported modules."""
    modules = modules or list(sys.modules.values())
    for module in modules:
        try:
            filename = module.__file__
        except (AttributeError, ImportError):
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
    """ The process responsible for handling the worker.

    The worker process object also acts as a proxy back to the reloader.

    """
    def __init__(self, worker_path):
        super(Worker, self).__init__()
        self.worker_path = worker_path
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

        kw = dict(
            spec=self.worker_path,
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

    def join(self, timeout=None):
        self.process.join()

        if self.process.is_alive():
            # the join timed out
            return

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
    """ Get a reference to the current
    :class:`hupper.interfaces.IReloaderProxy`.

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
    try:
        get_reloader()
    except RuntimeError:
        return False
    return True


class ReloaderProxy(IReloaderProxy):
    def __init__(self, files_queue, pipe):
        self.files_queue = files_queue
        self.pipe = pipe

    def watch_files(self, files):
        for file in files:
            self.files_queue.put(file)

    def trigger_reload(self):
        self.pipe.send_bytes(b'1')


def worker_main(spec, files_queue, pipe, parent_pipe):
    # close the parent end of the pipe, we aren't using it in the worker
    parent_pipe.close()
    del parent_pipe

    # use the stdin fd passed in from the reloader process
    sys.stdin = recv_fd(pipe, 'r')

    # import the worker path before polling sys.modules
    modname, funcname = spec.rsplit('.', 1)
    module = importlib.import_module(modname)
    func = getattr(module, funcname)

    poller = WatchSysModules(files_queue.put)
    poller.start()

    parent_watcher = WatchForParentShutdown(pipe)
    parent_watcher.start()

    global _reloader_proxy
    _reloader_proxy = ReloaderProxy(files_queue, pipe)

    # start the worker
    func()
