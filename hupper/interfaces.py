import abc

from .compat import with_metaclass

class IReloaderProxy(with_metaclass(abc.ABCMeta)):
    @abc.abstractmethod
    def watch_files(self, files):
        """ Signal to the monitor to track some custom paths."""
        pass

    @abc.abstractmethod
    def trigger_reload(self):
        """ Signal the monitor to execute a reload."""
        pass

class IFileMonitor(with_metaclass(abc.ABCMeta)):
    @abc.abstractmethod
    def add_path(self, path):
        """ Start monitoring a new path."""
        pass

    @abc.abstractmethod
    def start(self):
        """ Start the monitor. This method should not block."""
        pass

    @abc.abstractmethod
    def join(self):
        """ Block until the monitor has stopped."""
        pass

    @abc.abstractmethod
    def stop(self):
        """ Trigger the monitor to stop.

        This should be called before invoking :meth:`.join`.

        """
        pass

    @abc.abstractmethod
    def is_changed(self):
        """ Return ``True`` if any files have been changed."""
        pass

    @abc.abstractmethod
    def wait_for_change(self, timeout=None):
        """ Wait until a file has changed or until ``timeout`` seconds.

        If :meth:`.is_changed` is ``True`` then this will return immediately.

        If ``timeout`` is ``None`` then this should block until a file
        has changed.

        """
        pass

    @abc.abstractmethod
    def clear_changes(self):
        """ Reset :meth:`.is_changed` and :meth:`.wait_for_change`."""
        pass
