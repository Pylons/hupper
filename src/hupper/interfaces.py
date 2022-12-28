from abc import ABC, abstractmethod


class IReloaderProxy(ABC):
    @abstractmethod
    def watch_files(self, files):
        """Signal to the monitor to track some custom paths."""

    @abstractmethod
    def trigger_reload(self):
        """Signal the monitor to execute a reload."""


class IFileMonitorFactory(ABC):
    @abstractmethod
    def __call__(self, callback, **kw):
        """Return an :class:`.IFileMonitor` instance.

        ``callback`` is a callable to be invoked by the ``IFileMonitor``
        when file changes are detected. It should accept the path of
        the changed file as its only parameter.

        Extra keyword-only arguments:

        ``interval`` is the value of ``reload_interval`` passed to the
        reloader and may be used to control behavior in the file monitor.

        ``logger`` is an :class:`.ILogger` instance used to record runtime
        output.

        """


class IFileMonitor(ABC):
    @abstractmethod
    def add_path(self, path):
        """Start monitoring a new path."""

    @abstractmethod
    def start(self):
        """Start the monitor. This method should not block."""

    @abstractmethod
    def stop(self):
        """Trigger the monitor to stop.

        This should be called before invoking ``join``.

        """

    @abstractmethod
    def join(self):
        """Block until the monitor has stopped."""


class ILogger(ABC):
    @abstractmethod
    def error(self, msg):
        """Record an error message."""

    @abstractmethod
    def info(self, msg):
        """Record an informational message."""

    @abstractmethod
    def debug(self, msg):
        """Record a debug-only message."""
