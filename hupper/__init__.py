# public api
# flake8: noqa

from .compat import is_watchdog_supported

from .reloader import (
    is_active,
    get_reloader,
    start_reloader,
)
