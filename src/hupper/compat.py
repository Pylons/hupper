# flake8: noqa
import imp
import importlib
import site
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


def get_site_packages():  # pragma: no cover
    try:
        paths = site.getsitepackages()
        if site.ENABLE_USER_SITE:
            paths.append(site.getusersitepackages())
        return paths

    # virtualenv does not ship with a getsitepackages impl so we fallback
    # to using distutils if we can
    # https://github.com/pypa/virtualenv/issues/355
    except Exception:
        try:
            from distutils.sysconfig import get_python_lib
            return [get_python_lib()]

        # just incase, don't fail here, it's not worth it
        except Exception:
            return []


################################################
# cross-compatible metaclass implementation
# Copyright (c) 2010-2012 Benjamin Peterson
def with_metaclass(meta, base=object):
    """Create a base class with a metaclass."""
    return meta("%sBase" % meta.__name__, (base,), {})
