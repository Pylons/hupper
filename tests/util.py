import os
import subprocess
import sys
import tempfile
import threading
import time

here = os.path.abspath(os.path.dirname(__file__))


class TestApp(threading.Thread):
    name = None
    args = None
    stdin = None
    daemon = True

    def __init__(self):
        super(TestApp, self).__init__()
        self.exitcode = None
        self.process = None
        self.tmpfile = None
        self.tmpsize = 0
        self.response = None
        self.stdout, self.stderr = b'', b''

    def start(self, name, args):
        self.name = name
        self.args = args or []

        fd, self.tmpfile = tempfile.mkstemp()
        os.close(fd)
        touch(self.tmpfile)
        self.tmpsize = os.path.getsize(self.tmpfile)
        self.response = readfile(self.tmpfile)
        super(TestApp, self).start()

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

        if self.tmpfile:
            os.unlink(self.tmpfile)
            self.tmpfile = None

    def wait_for_response(self, timeout=5, interval=0.1):
        self.tmpsize = wait_for_change(
            self.tmpfile,
            last_size=self.tmpsize,
            timeout=timeout,
            interval=interval,
        )
        self.response = readfile(self.tmpfile)


def touch(fname, times=None):
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
        sleepfor = interval
        if timeout is not None:  # pragma: no cover
            if duration >= timeout:
                raise RuntimeError(
                    'timeout waiting for change to file=%s' % (path,))
            sleepfor = min(timeout - duration, sleepfor)
        time.sleep(sleepfor)
        size = os.path.getsize(path)
    return size
