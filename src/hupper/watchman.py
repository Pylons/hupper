# check ``hupper.utils.is_watchman_supported`` before using this module
import json
import os
import socket
import threading
import time

from .compat import PY2
from .interfaces import IFileMonitor
from .utils import get_watchman_sockpath


class WatchmanFileMonitor(threading.Thread, IFileMonitor):
    """
    An :class:`hupper.interfaces.IFileMonitor` that uses Facebook's
    ``watchman`` daemon to detect changes.

    ``callback`` is a callable that accepts a path to a changed file.

    """

    def __init__(
        self,
        callback,
        logger,
        sockpath=None,
        binpath='watchman',
        timeout=1.0,
        **kw
    ):
        super(WatchmanFileMonitor, self).__init__()
        self.callback = callback
        self.logger = logger
        self.paths = set()
        self.dirpaths = set()
        self.lock = threading.Lock()
        self.enabled = True
        self.sockpath = sockpath
        self.binpath = binpath
        self.timeout = timeout

    def add_path(self, path):
        with self.lock:
            dirpath = os.path.dirname(path)
            if dirpath not in self.dirpaths:
                self._subscribe(dirpath)
                self.dirpaths.add(dirpath)

            if path not in self.paths:
                self.paths.add(path)

    def start(self):
        sockpath = self._resolve_sockpath()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(sockpath)
        self._sock = sock
        self._recvbufs = []

        self._send(['version'])
        result = self._recv()
        self.logger.debug('Connected to watchman v' + result['version'] + '.')

        super(WatchmanFileMonitor, self).start()

    def join(self):
        try:
            return super(WatchmanFileMonitor, self).join()
        finally:
            self._sock.close()
            self._sock = None

    def run(self):
        while self.enabled:
            try:
                result = self._recv()
                if 'warning' in result:
                    self.logger.error('watchman warning=' + result['warning'])
                if 'error' in result:
                    self.logger.error('watchman error=' + result['error'])
                    continue
                if 'subscription' in result:
                    root = result['root']
                    files = result['files']
                    with self.lock:
                        for f in files:
                            path = os.path.join(root, f)
                            if path in self.paths:
                                self.callback(path)
            except socket.timeout:
                pass

    def stop(self):
        self.enabled = False

    def _resolve_sockpath(self):
        if self.sockpath:
            return self.sockpath
        return get_watchman_sockpath(self.binpath)

    def _subscribe(self, dirpath):
        self._send(
            [
                'subscribe',
                dirpath,
                '{}.{}.{}'.format(os.getpid(), id(self), dirpath),
                {
                    # +1 second because we don't want any buffered changes
                    # if the daemon is already watching the folder
                    'since': int(time.time() + 1),
                    'expression': [
                        'allof',
                        ['type', 'f'],
                        # watchman monitors entire subdirectories with
                        # a single subscription but we want to only
                        # watch the specific folder's immediate files
                        ['dirname', "", ["depth", "eq", 0]],
                    ],
                    'fields': ['name'],
                },
            ]
        )

    def _readline(self):
        # buffer may already have a line
        if len(self._recvbufs) == 1 and b'\n' in self._recvbufs[0]:
            line, b = self._recvbufs[0].split(b'\n', 1)
            self._recvbufs = [b]
            return line

        while True:
            b = self._sock.recv(4096)
            if not b:
                raise RuntimeError('lost connection to watchman')
            if b'\n' in b:
                result = b''.join(self._recvbufs)
                line, b = b.split(b'\n', 1)
                self._recvbufs = [b]
                return result + line
            self._recvbufs.append(b)

    def _recv(self):
        line = self._readline()
        if not PY2:
            line = line.decode('utf8')
        try:
            return json.loads(line)
        except Exception:  # pragma: no cover
            self.logger.info('ignoring corrupted payload from watchman')
            return {}

    def _send(self, msg):
        cmd = json.dumps(msg)
        if not PY2:
            cmd = cmd.encode('ascii')
        self._sock.sendall(cmd + b'\n')
