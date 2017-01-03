# check ``hupper.compat.is_watchdog_supported`` before using this module
from __future__ import absolute_import

import os.path
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .interfaces import IFileMonitor


class WatchdogFileMonitor(FileSystemEventHandler, Observer, IFileMonitor):
    """
    An :class:`hupper.interfaces.IFileMonitor` that uses ``watchdog``
    to watch for file changes uses inotify.

    ``callback`` is a callable that accepts a path to a changed file.

    """
    def __init__(self, callback):
        super(WatchdogFileMonitor, self).__init__()
        self.callback = callback
        self.paths = set()
        self.dirpaths = set()
        self.lock = threading.Lock()

    def add_path(self, path):
        with self.lock:
            dirpath = os.path.dirname(path)
            if dirpath not in self.dirpaths:
                try:
                    self.schedule(self, dirpath)
                except (OSError, IOError):  # pragma: no cover
                    # ideally we would handle this better but if the
                    # directory is missing watchdog raises an error
                    pass
                else:
                    self.dirpaths.add(dirpath)

            if path not in self.paths:
                self.paths.add(path)

    def on_any_event(self, event):
        with self.lock:
            path = event.src_path
            if path in self.paths:
                self.callback(path)
