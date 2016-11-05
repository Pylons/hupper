import os
import threading
import time

from .interfaces import IFileMonitor


class PollingFileMonitor(threading.Thread, IFileMonitor):
    def __init__(self, callback, poll_interval=1):
        super(PollingFileMonitor, self).__init__()
        self.callback = callback
        self.poll_interval = poll_interval
        self.paths = set()
        self.mtimes = {}
        self.lock = threading.Lock()

    def add_path(self, path):
        with self.lock:
            self.paths.add(path)

    def run(self):
        self.enabled = True
        while self.enabled:
            with self.lock:
                paths = list(self.paths)
            self.check_reload(paths)
            time.sleep(self.poll_interval)

    def stop(self):
        self.enabled = False

    def check_reload(self, paths):
        changes = set()
        for path in paths:
            mtime = get_mtime(path)
            if path.endswith('.pyc') and os.path.exists(path[:-1]):
                # track the py as the canonical file that changed anytime
                # its pyc file changes
                path = path[:-1]
                mtime = max(get_mtime(path), mtime)
            if path not in self.mtimes:
                self.mtimes[path] = mtime
            elif self.mtimes[path] < mtime:
                self.mtimes[path] = mtime
                changes.add(path)
        if changes:
            self.callback(changes)


def get_mtime(path, raises=False):
    try:
        stat = os.stat(path)
        if stat:
            return stat.st_mtime
        else:
            return 0
    except (OSError, IOError):
        if raises:
            raise
        return 0
