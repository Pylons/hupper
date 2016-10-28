# flake8: noqa
import platform
import sys

PY2 = sys.version_info[0] == 2
WIN = sys.platform == 'win32'

OS64 = platform.machine().endswith('64')
PY64 = sys.maxsize > 2**32

if PY2:
    long = long
else:
    long = int

try:
    import queue
except ImportError:
    import Queue as queue

try:
    from _thread import interrupt_main
except ImportError:
    from thread import interrupt_main

def is_watchdog_supported():
    """ Return ``True`` if watchdog is available."""
    try:
        import watchdog
    except ImportError:
        return False
    return True

################################################
# cross-compatible metaclass implementation
# Copyright (c) 2010-2012 Benjamin Peterson

def with_metaclass(meta, base=object):
    """Create a base class with a metaclass."""
    return meta("%sBase" % meta.__name__, (base,), {})
