# check ``hupper.utils.is_watchman_supported`` before using this module
import errno
import json
import os
import queue
import select
import socket
import threading
import time

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
        timeout=10.0,
        **kw,
    ):
        super(WatchmanFileMonitor, self).__init__()
        self.callback = callback
        self.logger = logger
        self.watches = set()
        self.paths = set()
        self.lock = threading.Lock()
        self.enabled = True
        self.sockpath = sockpath
        self.binpath = binpath
        self.timeout = timeout
        self.responses = queue.Queue()

    def add_path(self, path):
        is_new_root = False
        with self.lock:
            root = os.path.dirname(path)
            for watch in self.watches:
                if watch == root or root.startswith(watch + os.sep):
                    break
            else:
                is_new_root = True

            if path not in self.paths:
                self.paths.add(path)

        # it's important to release the above lock before invoking _watch
        # on a new root to prevent deadlocks
        if is_new_root:
            self._watch(root)

    def start(self):
        sockpath = self._resolve_sockpath()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(sockpath)
        self._sock = sock
        self._recvbufs = []

        self._send(['version'])
        result = self._recv()
        self.logger.debug('watchman v' + result['version'] + '.')

        super(WatchmanFileMonitor, self).start()

    def join(self):
        try:
            return super(WatchmanFileMonitor, self).join()
        finally:
            self._close_sock()

    def stop(self):
        self.enabled = False
        self._close_sock()

    def run(self):
        while self.enabled:
            try:
                result = self._recv()
            except socket.timeout:
                continue
            except OSError as ex:
                if ex.errno == errno.EBADF:
                    # this means the socket is closed which should only happen
                    # when stop is invoked, leaving enabled false
                    if self.enabled:
                        self.logger.error(
                            'Lost connection to watchman. No longer watching'
                            ' for changes.'
                        )
                    break
                raise

            self._handle_result(result)

    def _handle_result(self, result):
        if 'warning' in result:
            self.logger.error('watchman warning: ' + result['warning'])

        if 'error' in result:
            self.logger.error('watchman error: ' + result['error'])

        if 'subscription' in result:
            root = result['root']

            if result.get('canceled'):
                self.logger.info(
                    'watchman has stopped following root: ' + root
                )
                with self.lock:
                    self.watches.remove(root)

            else:
                files = result['files']
                with self.lock:
                    for f in files:
                        if isinstance(f, dict):
                            f = f['name']
                        path = os.path.join(root, f)
                        if path in self.paths:
                            self.callback(path)

        if not self._is_unilateral(result):
            self.responses.put(result)

    def _is_unilateral(self, result):
        if 'unilateral' in result and result['unilateral']:
            return True
        # fallback to checking for known unilateral responses
        for k in ['log', 'subscription']:
            if k in result:
                return True
        return False

    def _close_sock(self):
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            finally:
                self._sock = None

    def _resolve_sockpath(self):
        if self.sockpath:
            return self.sockpath
        return get_watchman_sockpath(self.binpath)

    def _watch(self, root):
        result = self._query(['watch-project', root])
        if result['watch'] != root:
            root = result['watch']
        self._query(
            [
                'subscribe',
                root,
                '{}.{}.{}'.format(os.getpid(), id(self), root),
                {
                    # +1 second because we don't want any buffered changes
                    # if the daemon is already watching the folder
                    'since': int(time.time() + 1),
                    'expression': ['type', 'f'],
                    'fields': ['name'],
                },
            ]
        )
        self.logger.debug('watchman is now tracking root: ' + root)
        with self.lock:
            self.watches.add(root)

    def _readline(self):
        # buffer may already have a line
        if len(self._recvbufs) == 1 and b'\n' in self._recvbufs[0]:
            line, b = self._recvbufs[0].split(b'\n', 1)
            self._recvbufs = [b]
            return line

        while True:
            # use select because it unblocks immediately when the socket is
            # closed unlike sock.settimeout which does not
            ready_r, _, _ = select.select([self._sock], [], [], self.timeout)
            if self._sock not in ready_r:
                continue
            b = self._sock.recv(4096)
            if not b:
                self.logger.error(
                    'Lost connection to watchman. No longer watching for'
                    ' changes.'
                )
                self.stop()
                raise socket.timeout
            if b'\n' in b:
                result = b''.join(self._recvbufs)
                line, b = b.split(b'\n', 1)
                self._recvbufs = [b]
                return result + line
            self._recvbufs.append(b)

    def _recv(self):
        line = self._readline().decode('utf8')
        try:
            return json.loads(line)
        except Exception:  # pragma: no cover
            self.logger.info(
                'Ignoring corrupted payload from watchman: ' + line
            )
            return {}

    def _send(self, msg):
        cmd = json.dumps(msg).encode('ascii')
        self._sock.sendall(cmd + b'\n')

    def _query(self, msg, timeout=None):
        self._send(msg)
        return self.responses.get(timeout=timeout)
