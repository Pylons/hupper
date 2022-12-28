import importlib
import json
import os
import subprocess
import sys

WIN = sys.platform == 'win32'


class Sentinel(object):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<{0}>'.format(self.name)


default = Sentinel('default')


def resolve_spec(spec):
    modname, funcname = spec.rsplit('.', 1)
    module = importlib.import_module(modname)
    func = getattr(module, funcname)
    return func


def is_watchdog_supported():
    """Return ``True`` if watchdog is available."""
    try:
        import watchdog  # noqa: F401
    except ImportError:
        return False
    return True


def is_watchman_supported():
    """Return ``True`` if watchman is available."""
    if WIN:
        # for now we aren't bothering with windows sockets
        return False

    try:
        sockpath = get_watchman_sockpath()
        return bool(sockpath)
    except Exception:
        return False


def get_watchman_sockpath(binpath='watchman'):
    """Find the watchman socket or raise."""
    path = os.getenv('WATCHMAN_SOCK')
    if path:
        return path

    cmd = [binpath, '--output-encoding=json', 'get-sockname']
    result = subprocess.check_output(cmd)
    result = json.loads(result)
    return result['sockname']


def is_stream_interactive(stream):
    return stream is not None and stream.isatty()
