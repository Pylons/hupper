# public api
# flake8: noqa

from .compat import is_watchdog_supported

from .interfaces import (
    IFileMonitor,
    IReloaderProxy,
)

from .polling import PollingFileMonitor

from .reloader import (
    Reloader,
    is_active,
    get_reloader,
    start_reloader,
)

if is_watchdog_supported():
    from .watchdog import WatchdogFileMonitor
