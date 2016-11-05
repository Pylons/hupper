# check ``hupper.compat.is_watchdog_supported`` before using this module
from __future__ import absolute_import

import os.path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .interfaces import IFileMonitor


class WatchdogFileMonitor(FileSystemEventHandler, Observer, IFileMonitor):
    def __init__(self, callback):
        super(WatchdogFileMonitor, self).__init__()
        self.callback = callback
        self.paths = set()
        self.dirpaths = set()

    def add_path(self, path):
        if path not in self.paths:
            self.paths.add(path)
            dirpath = os.path.dirname(path)
            if dirpath not in self.dirpaths:
                self.dirpaths.add(dirpath)
                self.schedule(self, dirpath)

    def on_any_event(self, event):
        path = event.src_path
        if path in self.paths:
            self.callback(path)
