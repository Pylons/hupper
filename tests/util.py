import os
import subprocess
import sys
import threading


here = os.path.dirname(__file__)


class TestApp(threading.Thread):
    stdin = None
    daemon = True

    def __init__(self, name, args):
        super(TestApp, self).__init__()
        self.name = name
        self.args = args
        self.exitcode = None

    def run(self):
        cmd = [
            sys.executable,
            os.path.join(here, self.name),
        ] + self.args

        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                close_fds=True,
                universal_newlines=True,
            )
            self.stdout, self.stderr = self.process.communicate(self.stdin)
        finally:
            self.exitcode = self.process.wait()

    def is_alive(self):
        return self.exitcode is None

    def stop(self):
        if self.is_alive():
            self.process.terminate()
        self.join()


def touch(fname, times=None):
    if not os.path.isabs(fname):
        fname = os.path.join(here, fname)
    with open(fname, 'a'):
        os.utime(fname, times)
