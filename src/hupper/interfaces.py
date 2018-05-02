import abc

from .compat import with_metaclass


class IReloaderProxy(with_metaclass(abc.ABCMeta)):
    @abc.abstractmethod
    def watch_files(self, files):
        """ Signal to the monitor to track some custom paths."""

    @abc.abstractmethod
    def trigger_reload(self):
        """ Signal the monitor to execute a reload."""


class IFileMonitorFactory(with_metaclass(abc.ABCMeta)):
    def __call__(self, callback, **kw):
        """ Return an :class:`.IFileMonitor` instance.

        ``callback`` is a callable to be invoked by the ``IFileMonitor``
        when file changes are detected. It should accept the path of
        the changed file as its only parameter.

        """


class IFileMonitor(with_metaclass(abc.ABCMeta)):
    @abc.abstractmethod
    def add_path(self, path):
        """ Start monitoring a new path."""

    @abc.abstractmethod
    def start(self):
        """ Start the monitor. This method should not block."""

    @abc.abstractmethod
    def stop(self):
        """ Trigger the monitor to stop.

        This should be called before invoking :meth:`.join`.

        """

    @abc.abstractmethod
    def join(self):
        """ Block until the monitor has stopped."""
