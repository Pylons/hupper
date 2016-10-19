from __future__ import print_function

import importlib
import multiprocessing
import os
import threading
import time
import sys

from .compat import interrupt_main
from .compat import queue
from .polling import PollingFileMonitor


RELOADER_ENVIRON_KEY = 'HUPPER_RELOADER'


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


class WatchForParentShutdown(threading.Thread):
    """ Poll the parent process to ensure it is still alive."""
    poll_interval = 1

    def __init__(self, parent_pid):
        super(WatchForParentShutdown, self).__init__()
        self.parent_pid = parent_pid

    def run(self):
        # If parent shuts down (and we are adopted by a different parent
        # process), we should shut down.
        while (os.getppid() == self.parent_pid):
            time.sleep(self.poll_interval)

        interrupt_main()


class ReloaderProxy(object):
    def watch_files(self, files):
        """ Signal to the parent process to track some custom paths."""
        pass


class WorkerProcess(ReloaderProxy, multiprocessing.Process):
    """ The process responsible for handling the worker.

    The worker process object also acts as a proxy back to the reloader.

    """
    def __init__(self, worker_path, files_queue, parent_pid, environ_key):
        super(WorkerProcess, self).__init__()
        self.worker_path = worker_path
        self.files_queue = files_queue
        self.parent_pid = parent_pid
        self.environ_key = environ_key

    def run(self):
        # activate the environ
        os.environ[self.environ_key] = '1'

        # import the worker path
        modname, funcname = self.worker_path.rsplit('.', 1)
        module = importlib.import_module(modname)
        func = getattr(module, funcname)

        poller = WatchSysModules(self.files_queue.put)
        poller.start()

        parent_watcher = WatchForParentShutdown(self.parent_pid)
        parent_watcher.start()

        # start the worker
        func()

    def watch_files(self, files):
        """ Signal to the parent process to track some custom paths."""
        for file in files:
            self.files_queue.put(file)


class Reloader(object):
    """
    A wrapper class around a file monitor which will handle changes by
    restarting a new worker process.

    """
    def __init__(self,
                 worker_path,
                 monitor_factory,
                 reload_interval=1,
                 verbose=1,
                 environ_key=RELOADER_ENVIRON_KEY,
                 ):
        self.worker_path = worker_path
        self.monitor_factory = monitor_factory
        self.reload_interval = reload_interval
        self.verbose = verbose
        self.monitor = None
        self.environ_key = environ_key

    def out(self, msg):
        if self.verbose > 0:
            print(msg)

    def run(self):
        """
        Execute the reloader forever, blocking the current thread.

        """
        self._start_monitor()
        try:
            while True:
                start = time.time()
                if not self._run_worker():
                    self._wait_for_changes()
                debounce = self.reload_interval - (time.time() - start)
                if debounce > 0:
                    time.sleep(debounce)
        finally:
            if self.monitor:
                self._stop_monitor()

    def run_once(self):
        """
        Execute the worker once.

        This method will return after a file change is detected.

        """
        self._start_monitor()
        try:
            self._run_worker()
        finally:
            if self.monitor:
                self._stop_monitor()

    def _run_worker(self):
        files_queue = multiprocessing.Queue()
        worker = WorkerProcess(
            self.worker_path,
            files_queue,
            os.getpid(),
            self.environ_key,
        )
        worker.daemon = True
        worker.start()

        self.out("Starting monitor for PID %s." % worker.pid)

        while not self.monitor.is_changed() and worker.is_alive():
            try:
                path = files_queue.get(timeout=self.reload_interval)
            except queue.Empty:
                pass
            else:
                self.monitor.add_path(path)

        self.monitor.clear_changes()

        if worker.is_alive():
            self.out("Killing server with PID %s." % worker.pid)
            worker.terminate()
            worker.join()
            return True

        else:
            worker.join()
            self.out('Server with PID %s exited with code %d.' %
                     (worker.pid, worker.exitcode))
            return False

    def _wait_for_changes(self):
        while not self.monitor.wait_for_change(self.reload_interval):
            pass

        self.monitor.clear_changes()

    def _start_monitor(self):
        self.monitor = self.monitor_factory()
        self.monitor.daemon = True
        self.monitor.start()

    def _stop_monitor(self):
        self.monitor.stop()
        self.monitor.join()
        self.monitor = None


def start_reloader(worker_path, reload_interval=1, verbose=1):
    """
    Start a monitor and then fork a worker process which starts by executing
    the importable function at ``worker_path``.

    If this function is called from a worker process that is already being
    monitored then it will return a reference to the current
    :class:`.ReloaderProxy` which can be used to communicate with the monitor.

    ``worker_path`` must be a dotted string pointing to a globally importable
    function that will be executed to start the worker. An example could be
    ``myapp.cli.main``. In most cases it will point at the same function that
    is invoking ``start_reloader`` in the first place.

    ``reload_interval`` is a value in seconds and will be used to throttle
    restarts.

    ``verbose`` controls the output. Set to ``0`` to turn off any logging
    of activity and turn up to ``2`` for extra output.

    """
    if RELOADER_ENVIRON_KEY in os.environ:
        return get_reloader()

    def monitor_factory():
        return PollingFileMonitor(reload_interval, verbose)

    reloader = Reloader(
        worker_path=worker_path,
        reload_interval=reload_interval,
        verbose=verbose,
        monitor_factory=monitor_factory,
        envkey=RELOADER_ENVIRON_KEY,
    )
    return reloader.run()


def get_reloader():
    """ Get a reference to the current :class:`.ReloaderProxy`.

    Raises a ``RuntimeError`` if the current process is not actively being
    monitored by a parent process.

    """
    p = multiprocessing.current_process()
    if not isinstance(p, WorkerProcess):
        raise RuntimeError('process is not controlled by hupper')
    return p


def is_active():
    """
    Return ``True`` if the current process being monitored by a parent process.

    """
    try:
        get_reloader()
    except RuntimeError:
        return False
    return True


def watch_files(files):
    """
    Mark certain file paths to be watched for changes which will trigger a
    restart.

    This function may be called from either the worker process or from the
    monitor process prior to calling :func:`.start_reloader`.

    """
    # TODO need to make this work from the monitor process as well, probably
    # by setting some global state on the Reloader class similar to how
    # pserve used to work via the classinstancemethod decorator
    reloader = get_reloader()
    reloader.watch_files(files)


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
