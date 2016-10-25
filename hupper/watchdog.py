# check ``hupper.compat.is_watchdog_supported`` before using this module
from __future__ import absolute_import

import os.path
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .interfaces import IFileMonitor


class WatchdogFileMonitor(FileSystemEventHandler, Observer, IFileMonitor):
    def __init__(self, verbose=1):
        super(WatchdogFileMonitor, self).__init__()
        self.verbose = verbose
        self.paths = set()
        self.dirpaths = set()
        self.change_event = threading.Event()
        self.changed_paths = set()

    def add_path(self, path):
        if path not in self.paths:
            self.paths.add(path)
            dirpath = os.path.dirname(path)
            if dirpath not in self.dirpaths:
                self.dirpaths.add(dirpath)
                self.schedule(self, dirpath)

    def on_any_event(self, event):
        path = event.src_path
        if (
            path in self.paths
            and path not in self.changed_paths
        ):
            self.changed_paths.add(path)
            self.change_event.set()
            self.out('%s changed; reloading ...' % (path,))

    def out(self, msg):
        if self.verbose > 0:
            print(msg)

    def is_changed(self):
        return self.change_event.is_set()

    def wait_for_change(self, timeout=None):
        return self.change_event.wait(timeout)

    def clear_changes(self):
        self.changed_paths.clear()
        self.change_event.clear()
