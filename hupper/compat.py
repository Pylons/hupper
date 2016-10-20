# flake8: noqa
try:
    import queue
except ImportError:
    import Queue as queue

try:
    from _thread import interrupt_main
except ImportError:
    from thread import interrupt_main

################################################
# cross-compatible metaclass implementation
# Copyright (c) 2010-2012 Benjamin Peterson

def with_metaclass(meta, base=object):
    """Create a base class with a metaclass."""
    return meta("%sBase" % meta.__name__, (base,), {})
