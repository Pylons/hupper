from _thread import LockType as _LockType
from collections.abc import Callable as _Callable, Iterable as _Iterable
import os as os
import threading as threading
import time as time

from .interfaces import IFileMonitor as IFileMonitor

class PollingFileMonitor(threading.Thread, IFileMonitor):
    callback: _Callable[[str], None]
    poll_interval: float
    paths: set[str]
    mtimes: dict[str, float]
    lock: _LockType
    enabled: bool
    def __init__(
        self,
        callback: _Callable[[str], None],
        interval: float = 1,
        **kw: object,
    ) -> None: ...
    def add_path(self, path: str) -> None: ...
    def run(self) -> None: ...
    def stop(self) -> None: ...
    def check_reload(self, paths: _Iterable[str]) -> None: ...

def get_mtime(path: str) -> float: ...
