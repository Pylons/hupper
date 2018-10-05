from __future__ import print_function

from glob import glob
import os
import signal
import sys
import threading
import time

from .compat import queue
from .ipc import ProcessGroup
from .logger import DefaultLogger
from .utils import (
    resolve_spec,
    is_watchdog_supported,
    is_watchman_supported,
)
from .worker import (
    Worker,
    is_active,
    get_reloader,
)


class FileMonitorProxy(object):
    """
    Wrap an :class:`hupper.interfaces.IFileMonitor` into an object that
    exposes a thread-safe interface back to the reloader to detect
    when it should reload.

    """
    monitor = None

    def __init__(self, logger):
        self.logger = logger
        self.change_event = threading.Event()
        self.changed_paths = set()

    def add_path(self, path):
        # if the glob does not match any files then go ahead and pass
        # the pattern to the monitor anyway incase it is just a file that
        # is currently missing
        for p in glob(path) or [path]:
            self.monitor.add_path(p)

    def start(self):
        self.monitor.start()

    def stop(self):
        self.monitor.stop()
        self.monitor.join()

    def file_changed(self, path):
        if path not in self.changed_paths:
            self.changed_paths.add(path)
            self.logger.info('%s changed; reloading ...' % (path,))
        self.set_changed()

    def is_changed(self):
        return self.change_event.is_set()

    def wait_for_change(self, timeout=None):
        return self.change_event.wait(timeout)

    def clear_changes(self):
        self.change_event.clear()
        self.changed_paths.clear()

    def set_changed(self):
        self.change_event.set()


class Reloader(object):
    """
    A wrapper class around a file monitor which will handle changes by
    restarting a new worker process.

    """
    def __init__(self,
                 worker_path,
                 monitor_factory,
                 logger,
                 reload_interval=1,
                 worker_args=None,
                 worker_kwargs=None,
                 ):
        self.worker_path = worker_path
        self.worker_args = worker_args
        self.worker_kwargs = worker_kwargs
        self.monitor_factory = monitor_factory
        self.reload_interval = reload_interval
        self.logger = logger
        self.monitor = None
        self.worker = None
        self.group = ProcessGroup()

    def run(self):
        """
        Execute the reloader forever, blocking the current thread.

        This will invoke ``sys.exit(1)`` if interrupted.

        """
        self._capture_signals()
        self._start_monitor()
        try:
            while True:
                if not self._run_worker():
                    self._wait_for_changes()
                time.sleep(self.reload_interval)
        except KeyboardInterrupt:
            pass
        finally:
            self._stop_monitor()
            self._restore_signals()
        sys.exit(1)

    def run_once(self):
        """
        Execute the worker once.

        This method will return after a file change is detected.

        """
        self._capture_signals()
        self._start_monitor()
        try:
            self._run_worker()
        except KeyboardInterrupt:
            return
        finally:
            self._stop_monitor()
            self._restore_signals()

    def _run_worker(self):
        self.worker = Worker(
            self.worker_path,
            args=self.worker_args,
            kwargs=self.worker_kwargs,
        )
        self.worker.start()

        try:
            # register the worker with the process group
            self.group.add_child(self.worker.pid)

            self.logger.info("Starting monitor for PID %s." % self.worker.pid)
            self.monitor.clear_changes()

            while not self.monitor.is_changed() and self.worker.is_alive():
                try:
                    cmd = self.worker.pipe.recv(timeout=self.reload_interval)
                except queue.Empty:
                    continue

                if cmd is None:
                    if self.worker.is_alive():
                        # the worker socket has died but the process is still
                        # alive (somehow) so wait a brief period to see if it
                        # dies on its own - if it does die then we want to
                        # treat it as a crash and wait for changes before
                        # reloading, if it doesn't die then we want to force
                        # reload the app immediately because it probably
                        # didn't die due to some file changes
                        time.sleep(self.reload_interval)
                    break

                if cmd[0] == 'reload':
                    break

                if cmd[0] == 'watch':
                    for path in cmd[1]:
                        self.monitor.add_path(path)

                else:  # pragma: no cover
                    raise RuntimeError('received unknown command')

        except KeyboardInterrupt:
            if self.worker.is_alive():
                self.logger.info('Waiting for server to exit ...')
                time.sleep(self.reload_interval)
            raise

        finally:
            if self.worker.is_alive():
                self.logger.info(
                    'Killing server with PID %s.' % self.worker.pid,
                )
                self.worker.terminate()
                self.worker.join()

            else:
                self.worker.join()
                self.logger.info('Server with PID %s exited with code %d.' %
                                 (self.worker.pid, self.worker.exitcode))

        self.monitor.clear_changes()

        force_restart = self.worker.terminated
        self.worker = None
        return force_restart

    def _wait_for_changes(self):
        self.logger.info('Waiting for changes before reloading.')
        while (
            not self.monitor.wait_for_change(self.reload_interval)
        ):  # pragma: nocover
            pass

        self.monitor.clear_changes()

    def _start_monitor(self):
        proxy = FileMonitorProxy(self.logger)
        proxy.monitor = self.monitor_factory(
            proxy.file_changed,
            interval=self.reload_interval,
            logger=self.logger,
        )
        self.monitor = proxy
        self.monitor.start()

    def _stop_monitor(self):
        if self.monitor:
            self.monitor.stop()
            self.monitor = None

    def _capture_signals(self):
        # SIGHUP is not supported on windows
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, self._signal_sighup)

    def _signal_sighup(self, signum, frame):
        self.logger.info('Received SIGHUP, triggering a reload.')
        self.monitor.set_changed()

    def _restore_signals(self):
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal.SIG_DFL)


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
    verbose=1,
    monitor_factory=None,
    worker_args=None,
    worker_kwargs=None,
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
    restarts.

    ``verbose`` controls the output. Set to ``0`` to turn off any logging
    of activity and turn up to ``2`` for extra output. Default is ``1``.

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

    """
    if is_active():
        return get_reloader()

    logger = DefaultLogger(verbose)

    if monitor_factory is None:
        monitor_factory = find_default_monitor_factory(logger)

    reloader = Reloader(
        worker_path=worker_path,
        worker_args=worker_args,
        worker_kwargs=worker_kwargs,
        reload_interval=reload_interval,
        monitor_factory=monitor_factory,
        logger=logger,
    )
    return reloader.run()
