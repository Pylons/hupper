# check ``hupper.utils.is_watchdog_supported`` before using this module
from __future__ import absolute_import
import os.path
import threading
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .interfaces import IFileMonitor


class WatchdogFileMonitor(FileSystemEventHandler, Observer, IFileMonitor):
    """
    An :class:`hupper.interfaces.IFileMonitor` that uses ``watchdog``
    to watch for file changes uses inotify.

    ``callback`` is a callable that accepts a path to a changed file.

    ``logger`` is an :class:`hupper.interfaces.ILogger` instance.

    """

    def __init__(self, callback, logger, **kw):
        super(WatchdogFileMonitor, self).__init__()
        self.callback = callback
        self.logger = logger
        self.paths = set()
        self.dirpaths = set()
        self.lock = threading.Lock()

    def add_path(self, path):
        with self.lock:
            dirpath = os.path.dirname(path)
            if dirpath not in self.dirpaths:
                try:
                    self.schedule(self, dirpath)
                except OSError as ex:  # pragma: no cover
                    # watchdog raises exceptions if folders are missing
                    # or if the ulimit is passed
                    self.logger.error('watchdog error: ' + str(ex))
                else:
                    self.dirpaths.add(dirpath)

            if path not in self.paths:
                self.paths.add(path)

    def _check(self, path):
        with self.lock:
            if path in self.paths:
                self.callback(path)

    def on_created(self, event):
        self._check(event.src_path)

    def on_modified(self, event):
        self._check(event.src_path)

    def on_moved(self, event):
        self._check(event.src_path)
        self._check(event.dest_path)
        self.add_path(event.dest_path)

    def on_deleted(self, event):
        self._check(event.src_path)
