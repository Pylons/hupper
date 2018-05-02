# flake8: noqa
import imp
import importlib
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


try:
    from importlib.util import source_from_cache as get_py_path
except ImportError:
    if PY2:
        get_py_path = lambda path: path[:-1]

    # fallback on python < 3.5
    else:
        get_py_path = imp.source_from_cache


try:
    import cPickle as pickle
except ImportError:
    import pickle


################################################
# cross-compatible metaclass implementation
# Copyright (c) 2010-2012 Benjamin Peterson
def with_metaclass(meta, base=object):
    """Create a base class with a metaclass."""
    return meta("%sBase" % meta.__name__, (base,), {})
