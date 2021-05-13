from collections import deque
from contextlib import contextmanager
import fnmatch
import os
import re
import signal
import sys
import threading
import time

from .compat import WIN, glob
from .ipc import ProcessGroup
from .logger import DefaultLogger, SilentLogger
from .utils import (
    default,
    is_stream_interactive,
    is_watchdog_supported,
    is_watchman_supported,
    resolve_spec,
)
from .worker import Worker, get_reloader, is_active

if WIN:
    from . import winapi


class FileMonitorProxy(object):
    """
    Wrap an :class:`hupper.interfaces.IFileMonitor` into an object that
    exposes a thread-safe interface back to the reloader to detect
    when it should reload.

    """

    monitor = None

    def __init__(self, callback, logger, ignore_files=None):
        self.callback = callback
        self.logger = logger
        self.changed_paths = set()
        self.ignore_files = [
            re.compile(fnmatch.translate(x)) for x in set(ignore_files or [])
        ]
        self.lock = threading.Lock()
        self.is_changed = False

    def add_path(self, path):
        # if the glob does not match any files then go ahead and pass
        # the pattern to the monitor anyway incase it is just a file that
        # is currently missing
        for p in glob(path, recursive=True) or [path]:
            if not any(x.match(p) for x in self.ignore_files):
                self.monitor.add_path(p)

    def start(self):
        self.monitor.start()

    def stop(self):
        self.monitor.stop()
        self.monitor.join()

    def file_changed(self, path):
        with self.lock:
            if path not in self.changed_paths:
                self.logger.info('{} changed; reloading ...'.format(path))
                self.changed_paths.add(path)

                if not self.is_changed:
                    self.is_changed = True
                    self.callback(self.changed_paths)

    def clear_changes(self):
        with self.lock:
            self.changed_paths = set()
            self.is_changed = False


class ControlSignal:
    byte = lambda x: chr(x).encode('ascii')

    SIGINT = byte(1)
    SIGHUP = byte(2)
    SIGTERM = byte(3)
    SIGCHLD = byte(4)
    FILE_CHANGED = byte(10)
    WORKER_COMMAND = byte(11)

    del byte


class WorkerResult:
    # exit - do not reload
    EXIT = 'exit'

    # reload immediately
    RELOAD = 'reload'

    # wait for changes before reloading
    WAIT = 'wait'


class Reloader(object):
    """
    A wrapper class around a file monitor which will handle changes by
    restarting a new worker process.

    """

    def __init__(
        self,
        worker_path,
        monitor_factory,
        logger,
        reload_interval=1,
        shutdown_interval=1,
        worker_args=None,
        worker_kwargs=None,
        ignore_files=None,
    ):
        self.worker_path = worker_path
        self.worker_args = worker_args
        self.worker_kwargs = worker_kwargs
        self.ignore_files = ignore_files
        self.monitor_factory = monitor_factory
        self.reload_interval = reload_interval
        self.shutdown_interval = shutdown_interval
        self.logger = logger
        self.monitor = None
        self.process_group = ProcessGroup()

    def run(self):
        """
        Execute the reloader forever, blocking the current thread.

        This will invoke ``sys.exit(1)`` if interrupted.

        """
        with self._setup_runtime():
            while True:
                result = self._run_worker()
                start = time.time()
                if result == WorkerResult.WAIT:
                    result = self._wait_for_changes()
                if result == WorkerResult.EXIT:
                    break
                dt = self.reload_interval - (time.time() - start)
                if dt > 0:
                    time.sleep(dt)
        sys.exit(1)

    def run_once(self):
        """
        Execute the worker once.

        This method will return after the worker exits.

        """
        with self._setup_runtime():
            self._run_worker()

    def _run_worker(self):
        worker = Worker(
            self.worker_path, args=self.worker_args, kwargs=self.worker_kwargs
        )
        return _run_worker(self, worker)

    def _wait_for_changes(self):
        worker = Worker(__name__ + '.wait_main')
        return _run_worker(
            self,
            worker,
            logger=SilentLogger(),
            shutdown_interval=0,
        )

    @contextmanager
    def _setup_runtime(self):
        with self._start_control():
            with self._start_monitor():
                with self._capture_signals():
                    yield

    @contextmanager
    def _start_control(self):
        self.control_r, self.control_w = os.pipe()
        try:
            yield
        finally:
            os.close(self.control_r)
            os.close(self.control_w)
            self.control_r = self.control_w = None

    def _control_proxy(self, signal):
        return lambda *args: os.write(self.control_w, signal)

    @contextmanager
    def _start_monitor(self):
        proxy = FileMonitorProxy(
            self._control_proxy(ControlSignal.FILE_CHANGED),
            self.logger,
            self.ignore_files,
        )
        proxy.monitor = self.monitor_factory(
            proxy.file_changed,
            interval=self.reload_interval,
            logger=self.logger,
        )
        self.monitor = proxy
        self.monitor.start()
        try:
            yield
        finally:
            self.monitor = None
            proxy.stop()

    _signals = {
        'SIGINT': ControlSignal.SIGINT,
        'SIGHUP': ControlSignal.SIGHUP,
        'SIGTERM': ControlSignal.SIGTERM,
        'SIGCHLD': ControlSignal.SIGCHLD,
    }

    @contextmanager
    def _capture_signals(self):
        undo_handlers = []
        try:
            for signame, control in self._signals.items():
                signum = getattr(signal, signame, None)
                if signum is None:
                    self.logger.debug(
                        'skipping unsupported signal={}'.format(signame)
                    )
                    continue
                handler = self._control_proxy(control)
                if WIN and signame == 'SIGINT':
                    undo = winapi.AddConsoleCtrlHandler(handler)
                    undo_handlers.append(undo)
                    handler = signal.SIG_IGN
                psig = signal.signal(signum, handler)
                undo_handlers.append(
                    lambda s=signum, p=psig: signal.signal(s, p)
                )
            yield
        finally:
            for undo in reversed(undo_handlers):
                undo()


def _run_worker(self, worker, logger=None, shutdown_interval=None):
    if logger is None:
        logger = self.logger

    if shutdown_interval is None:
        shutdown_interval = self.shutdown_interval

    packets = deque()

    def handle_packet(packet):
        packets.append(packet)
        os.write(self.control_w, ControlSignal.WORKER_COMMAND)

    self.monitor.clear_changes()

    worker.start(handle_packet)
    result = WorkerResult.WAIT
    soft_kill = True

    logger.info('Starting monitor for PID %s.' % worker.pid)
    try:
        # register the worker with the process group
        self.process_group.add_child(worker.pid)

        while True:
            # process all packets before moving on to signals to avoid
            # missing any files that need to be watched
            if packets:
                cmd = packets.popleft()

                if cmd is None:
                    if worker.is_alive:
                        # the worker socket has died but the process is still
                        # alive (somehow) so wait a brief period to see if it
                        # dies on its own - if it does die then we want to
                        # treat it as a crash and wait for changes before
                        # reloading, if it doesn't die then we want to force
                        # reload the app immediately because it probably
                        # didn't die due to some file changes
                        time.sleep(1)

                    if worker.is_alive:
                        logger.info(
                            'Worker pipe died unexpectedly, triggering a reload.'
                        )
                        result = WorkerResult.RELOAD
                        break

                    os.write(self.control_w, ControlSignal.SIGCHLD)
                    continue

                logger.debug('Received worker command "{}".'.format(cmd[0]))
                if cmd[0] == 'reload':
                    result = WorkerResult.RELOAD
                    break

                elif cmd[0] == 'watch_files':
                    for path in cmd[1]:
                        self.monitor.add_path(path)

                else:  # pragma: no cover
                    raise RuntimeError('received unknown control signal', cmd)

                # done handling the packet, continue to the next one
                # do not fall through here because it will block
                continue

            signal = os.read(self.control_r, 1)

            if not signal:
                logger.error('Control pipe died unexpectedly.')
                result = WorkerResult.EXIT
                break

            elif signal == ControlSignal.SIGINT:
                logger.info('Received SIGINT, waiting for server to exit ...')
                result = WorkerResult.EXIT

                # normally a SIGINT is sent automatically to the process
                # group and we want to avoid forwarding both a SIGINT and a
                # SIGTERM at the same time
                #
                # in the off chance that the SIGINT is not sent, we'll
                # just terminate after waiting shutdown_interval
                soft_kill = False
                break

            elif signal == ControlSignal.SIGHUP:
                logger.info('Received SIGHUP, triggering a reload.')
                result = WorkerResult.RELOAD
                break

            elif signal == ControlSignal.SIGTERM:
                logger.info('Received SIGTERM, triggering a shutdown.')
                result = WorkerResult.EXIT
                break

            elif signal == ControlSignal.FILE_CHANGED:
                if self.monitor.is_changed:
                    result = WorkerResult.RELOAD
                    break

            elif signal == ControlSignal.SIGCHLD:
                if not worker.is_alive:
                    break

        if worker.is_alive and shutdown_interval:
            if soft_kill:
                logger.info('Gracefully killing the server.')
                worker.kill(soft=True)
            worker.wait(shutdown_interval)

    finally:
        if worker.is_alive:
            logger.info('Server did not exit, forcefully killing.')
            worker.kill()
            worker.join()

        else:
            worker.join()
        logger.debug('Server exited with code %d.' % worker.exitcode)

    return result


def wait_main():
    try:
        reloader = get_reloader()
        if is_stream_interactive(sys.stdin):
            input('Press ENTER or change a file to reload.\n')
            reloader.trigger_reload()
        else:
            # just block while we wait for a file to change
            print('Waiting for a file to change before reload.')
            while True:
                time.sleep(10)
    except KeyboardInterrupt:
        pass


def find_default_monitor_factory(logger):
    spec = os.getenv('HUPPER_DEFAULT_MONITOR')
    if spec:
        monitor_factory = resolve_spec(spec)

        logger.debug('File monitor backend: ' + spec)

    elif is_watchman_supported():
        from .watchman import WatchmanFileMonitor as monitor_factory

        logger.debug('File monitor backend: watchman')

    elif is_watchdog_supported():
        from .watchdog import WatchdogFileMonitor as monitor_factory

        logger.debug('File monitor backend: watchdog')

    else:
        from .polling import PollingFileMonitor as monitor_factory

        logger.debug('File monitor backend: polling')

    return monitor_factory


def start_reloader(
    worker_path,
    reload_interval=1,
    shutdown_interval=default,
    verbose=1,
    logger=None,
    monitor_factory=None,
    worker_args=None,
    worker_kwargs=None,
    ignore_files=None,
):
    """
    Start a monitor and then fork a worker process which starts by executing
    the importable function at ``worker_path``.

    If this function is called from a worker process that is already being
    monitored then it will return a reference to the current
    :class:`hupper.interfaces.IReloaderProxy` which can be used to
    communicate with the monitor.

    ``worker_path`` must be a dotted string pointing to a globally importable
    function that will be executed to start the worker. An example could be
    ``myapp.cli.main``. In most cases it will point at the same function that
    is invoking ``start_reloader`` in the first place.

    ``reload_interval`` is a value in seconds and will be used to throttle
    restarts. Default is ``1``.

    ``shutdown_interval`` is a value in seconds and will be used to trigger
    a graceful shutdown of the server. Set to ``None`` to disable the graceful
    shutdown. Default is the same as ``reload_interval``.

    ``verbose`` controls the output. Set to ``0`` to turn off any logging
    of activity and turn up to ``2`` for extra output. Default is ``1``.

    ``logger``, if supplied, supersedes ``verbose`` and should be an object
    implementing :class:`hupper.interfaces.ILogger`.

    ``monitor_factory`` is an instance of
    :class:`hupper.interfaces.IFileMonitorFactory`. If left unspecified, this
    will try to create a :class:`hupper.watchdog.WatchdogFileMonitor` if
    `watchdog <https://pypi.org/project/watchdog/>`_ is installed and will
    fallback to the less efficient
    :class:`hupper.polling.PollingFileMonitor` otherwise.

    If ``monitor_factory`` is ``None`` it can be overridden by the
    ``HUPPER_DEFAULT_MONITOR`` environment variable. It should be a dotted
    python path pointing at an object implementing
    :class:`hupper.interfaces.IFileMonitorFactory`.

    ``ignore_files`` if provided must be an iterable of shell-style patterns
    to ignore.
    """
    if is_active():
        return get_reloader()

    if logger is None:
        logger = DefaultLogger(verbose)

    if monitor_factory is None:
        monitor_factory = find_default_monitor_factory(logger)

    if shutdown_interval is default:
        shutdown_interval = reload_interval

    reloader = Reloader(
        worker_path=worker_path,
        worker_args=worker_args,
        worker_kwargs=worker_kwargs,
        reload_interval=reload_interval,
        shutdown_interval=shutdown_interval,
        monitor_factory=monitor_factory,
        logger=logger,
        ignore_files=ignore_files,
    )
    return reloader.run()
