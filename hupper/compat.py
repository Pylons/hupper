# flake8: noqa
import os
import sys

PY2 = sys.version_info[0] == 2
WIN = sys.platform == 'win32'

try:
    import queue
except ImportError:
    import Queue as queue

try:
    from _thread import interrupt_main
except ImportError:
    from thread import interrupt_main

if WIN: # pragma: nocover
    from .winapi import (
        ProcessGroup,
        recv_fd,
        send_fd,
    )
else:
    class ProcessGroup(object):
        def add_child(self, pid):
            # nothing to do on *nix
            pass

    def send_fd(pipe, fd, pid):
        pipe.send(fd)

    def recv_fd(pipe, mode):
        fd = pipe.recv()
        return os.fdopen(fd, mode)

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
