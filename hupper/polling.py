import os
import threading
import time

from .interfaces import IFileMonitor


class PollingFileMonitor(threading.Thread, IFileMonitor):
    def __init__(self, poll_interval=1, verbose=1):
        super(PollingFileMonitor, self).__init__()
        self.poll_interval = poll_interval
        self.verbose = verbose
        self.paths = set()
        self.mtimes = {}
        self.lock = threading.Lock()
        self.change_event = threading.Event()

    def add_path(self, path):
        with self.lock:
            self.paths.add(path)

    def out(self, msg):
        print(msg)

    def run(self):
        self.enabled = True
        while self.enabled:
            with self.lock:
                paths = list(self.paths)
            if self.check_reload(paths):
                self.change_event.set()
            time.sleep(self.poll_interval)

    def stop(self):
        self.enabled = False

    def check_reload(self, paths):
        changes = set()
        for path in paths:
            try:
                stat = os.stat(path)
                if stat:
                    mtime = stat.st_mtime
                else:
                    mtime = 0
            except (OSError, IOError):
                continue
            if path.endswith('.pyc') and os.path.exists(path[:-1]):
                mtime = max(os.stat(path[:-1]).st_mtime, mtime)
            if path not in self.mtimes:
                self.mtimes[path] = mtime
            elif self.mtimes[path] < mtime:
                self.mtimes[path] = mtime
                changes.add(path)
        if changes and self.verbose > 0:
            for path in sorted(changes):
                self.out('%s changed; reloading ...' % (path,))
        return len(changes) > 0

    def is_changed(self):
        return self.change_event.is_set()

    def wait_for_change(self, timeout=None):
        return self.change_event.wait(timeout)

    def clear_changes(self):
        self.change_event.clear()
