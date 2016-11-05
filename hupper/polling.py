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
        if self.verbose > 0:
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
