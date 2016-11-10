import os
import subprocess
import sys
import tempfile
import threading
import time

here = os.path.dirname(__file__)


class TestApp(threading.Thread):
    stdin = None
    daemon = True

    def __init__(self, name, args):
        super(TestApp, self).__init__()
        self.name = name
        self.args = args or []
        self.exitcode = None
        self.process = None
        self.tmpfile = None
        self.tmpsize = 0
        self.response = None
        self.stdout, self.stderr = b'', b''

    def __enter__(self):
        fd, self.tmpfile = tempfile.mkstemp()
        os.close(fd)
        touch(self.tmpfile)
        self.tmpsize = os.path.getsize(self.tmpfile)
        self.response = readfile(self.tmpfile)
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
        if self.tmpfile:
            os.unlink(self.tmpfile)
            self.tmpfile = None

    def run(self):
        cmd = [sys.executable, '-m', 'tests.' + self.name]
        if self.tmpfile:
            cmd += ['--callback-file', self.tmpfile]
        cmd += self.args

        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'

        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            close_fds=True,
            universal_newlines=True,
        )
        try:
            self.stdout, self.stderr = self.process.communicate(self.stdin)
        finally:
            self.exitcode = self.process.wait()

    def is_alive(self):
        return self.process is not None and self.exitcode is None

    def stop(self):
        if self.is_alive():
            self.process.terminate()
        self.join()

    def wait_for_response(self, timeout=5, interval=0.1):
        self.tmpsize = wait_for_change(
            self.tmpfile,
            last_size=self.tmpsize,
            timeout=timeout,
            interval=interval,
        )
        self.response = readfile(self.tmpfile)


def touch(fname, times=None):
    if not os.path.isabs(fname):
        fname = os.path.join(here, fname)
    with open(fname, 'a'):
        os.utime(fname, times)


def readfile(path):
    with open(path, 'rb') as fp:
        return fp.readlines()


def wait_for_change(path, last_size=0, timeout=5, interval=0.1):
    start = time.time()
    size = os.path.getsize(path)
    while size == last_size:
        duration = time.time() - start
        if timeout is not None and duration >= timeout:  # pragma: nocover
            raise RuntimeError(
                'timeout waiting for change to file=%s' % (path,))
        time.sleep(min(
            timeout - duration if timeout is not None else 0,
            interval,
        ))
        size = os.path.getsize(path)
    return size
