import abc

from .compat import with_metaclass

class IReloaderProxy(with_metaclass(abc.ABCMeta)):
    @abc.abstractmethod
    def watch_files(self, files):
        """ Signal to the monitor to track some custom paths."""
        pass

    @abc.abstractmethod
    def trigger_reload(self, files):
        """ Signal the monitor to execute a reload."""
        pass

class IFileMonitor(with_metaclass(abc.ABCMeta)):
    @abc.abstractmethod
    def add_path(self, path):
        pass

    @abc.abstractmethod
    def start(self):
        pass

    @abc.abstractmethod
    def stop(self):
        pass

    @abc.abstractmethod
    def is_changed(self):
        pass

    @abc.abstractmethod
    def wait_for_change(self, timeout=None):
        pass

    @abc.abstractmethod
    def clear_changes(self):
        pass
