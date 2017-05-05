import io
import importlib
import os
import struct
import sys
import subprocess
import threading

from .compat import WIN
from .compat import pickle
from .compat import queue


def resolve_spec(spec):
    modname, funcname = spec.rsplit('.', 1)
    module = importlib.import_module(modname)
    func = getattr(module, funcname)
    return func


if WIN:  # pragma: no cover
    import msvcrt
    from . import winapi

    class ProcessGroup(object):
        def __init__(self):
            self.h_job = winapi.CreateJobObject(None, None)

            info = winapi.JOBOBJECT_BASIC_LIMIT_INFORMATION()
            info.LimitFlags = winapi.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

            extended_info = winapi.JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            extended_info.BasicLimitInformation = info

            winapi.SetInformationJobObject(
                self.h_job,
                winapi.JobObjectExtendedLimitInformation,
                extended_info,
            )

        def add_child(self, pid):
            hp = winapi.OpenProcess(winapi.PROCESS_ALL_ACCESS, False, pid)
            try:
                return winapi.AssignProcessToJobObject(self.h_job, hp)
            except OSError as ex:
                if getattr(ex, 'winerror') == 5:
                    # skip ACCESS_DENIED_ERROR on windows < 8 which occurs when
                    # the process is already attached to another job
                    pass
                else:
                    raise

    def snapshot_termios(fd):
        pass

    def restore_termios(fd, state):
        pass

    def get_handle(fd):
        return msvcrt.get_osfhandle(fd)

    def open_handle(handle, mode):
        flags = 0
        if 'w' not in mode and '+' not in mode:
            flags |= os.O_RDONLY
        if 'b' not in mode:
            flags |= os.O_TEXT
        if 'a' in mode:
            flags |= os.O_APPEND
        return msvcrt.open_osfhandle(handle, flags)

else:
    import termios

    class ProcessGroup(object):
        def add_child(self, pid):
            # nothing to do on *nix
            pass

    def snapshot_termios(fd):
        if os.isatty(fd):
            state = termios.tcgetattr(fd)
            return state

    def restore_termios(fd, state):
        if os.isatty(fd) and state:
            termios.tcflush(fd, termios.TCIOFLUSH)
            termios.tcsetattr(fd, termios.TCSANOW, state)

    def get_handle(fd):
        return fd

    def open_handle(handle, mode):
        return handle


class Pipe(object):
    """
    A pickle-able bidirectional pipe.

    """
    def __init__(self):
        self.is_parent = True
        self.parent_pid = os.getpid()
        self.c2pr_fd, self.c2pw_fd = os.pipe()
        self.p2cr_fd, self.p2cw_fd = os.pipe()

        self.inheritable_fds = [self.c2pw_fd, self.p2cr_fd]

    def __getstate__(self):
        return dict(
            parent_pid=self.parent_pid,
            p2cr_handle=get_handle(self.p2cr_fd),
            p2cw_handle=get_handle(self.p2cw_fd),
            c2pr_handle=get_handle(self.c2pr_fd),
            c2pw_handle=get_handle(self.c2pw_fd),
        )

    def __setstate__(self, state):
        self.parent_pid = state['parent_pid']
        self.is_parent = os.getpid() == self.parent_pid
        if self.is_parent:
            raise RuntimeError('pipe pickled to the same process')

        self.p2cr_fd = open_handle(state['p2cr_handle'], 'rb')
        self.p2cw_fd = open_handle(state['p2cw_handle'], 'wb')
        self.c2pr_fd = open_handle(state['c2pr_handle'], 'rb')
        self.c2pw_fd = open_handle(state['c2pw_handle'], 'wb')

    def activate(self):
        if self.is_parent:
            close_fd(self.c2pw_fd, raises=False)
            close_fd(self.p2cr_fd, raises=False)

            self.c2pr = os.fdopen(self.c2pr_fd, 'rb')
            self.p2cw = os.fdopen(self.p2cw_fd, 'wb')
            self._send_packet = self._send_to_child
            self._recv_packet = self._recv_from_child

        else:
            close_fd(self.c2pr_fd, raises=False)
            close_fd(self.p2cw_fd, raises=False)

            self.p2cr = os.fdopen(self.p2cr_fd, 'rb')
            self.c2pw = os.fdopen(self.c2pw_fd, 'wb')
            self._send_packet = self._send_to_parent
            self._recv_packet = self._recv_from_parent

        self.send_lock = threading.Lock()
        self.reader_queue = queue.Queue()

        self.reader_thread = threading.Thread(target=self._read_loop)
        self.reader_thread.daemon = True
        self.reader_thread.start()

    def close(self):
        if self.is_parent:
            self.c2pr.close()
            self.p2cw.close()

        else:
            self.c2pw.close()
            self.p2cr.close()

    def _send_to_parent(self, value):
        return self._send_into(self.c2pw, value)

    def _send_to_child(self, value):
        return self._send_into(self.p2cw, value)

    def _recv_from_parent(self, timeout=None):
        return self._recv_from(self.p2cr, timeout=timeout)

    def _recv_from_child(self, timeout=None):
        return self._recv_from(self.c2pr, timeout=timeout)

    def _send_into(self, fp, value):
        data = pickle.dumps(value)
        with self.send_lock:
            fp.write(struct.pack('Q', len(data)))
            fp.write(data)
            fp.flush()
        return len(data) + 8

    def _recv_from(self, fp, timeout=None):
        buf = io.BytesIO()
        chunk = fp.read(8)
        if not chunk:
            return
        size = remaining = struct.unpack('Q', chunk)[0]
        while remaining > 0:
            chunk = fp.read(remaining)
            n = len(chunk)
            if n == 0:
                if remaining == size:
                    raise EOFError
                else:
                    raise IOError('got end of file during message')
            buf.write(chunk)
            remaining -= n
        return pickle.loads(buf.getvalue())

    def _read_loop(self):
        try:
            while True:
                packet = self._recv_packet()
                if packet is None:
                    break
                self.reader_queue.put(packet)
        except EOFError:
            pass
        self.reader_queue.put(None)

    def send(self, value):
        return self._send_packet(value)

    def recv(self, timeout=None):
        packet = self.reader_queue.get(block=True, timeout=timeout)
        return packet


def set_inheritable(fd):
    # py34 and above sets CLOEXEC automatically on file descriptors
    # and we want to prevent that from happening
    if hasattr(os, 'get_inheritable') and not os.get_inheritable(fd):
        os.set_inheritable(fd, True)


def close_fd(fd, raises=True):
    if fd is not None:
        try:
            os.close(fd)
        except Exception:  # pragma: nocover
            if raises:
                raise


def args_from_interpreter_flags():
    """
    Return a list of command-line arguments reproducing the current
    settings in sys.flags and sys.warnoptions.

    """
    flag_opt_map = {
        'debug': 'd',
        'dont_write_bytecode': 'B',
        'no_user_site': 's',
        'no_site': 'S',
        'ignore_environment': 'E',
        'verbose': 'v',
        'bytes_warning': 'b',
        'quiet': 'q',
        'optimize': 'O',
    }
    args = []
    for flag, opt in flag_opt_map.items():
        v = getattr(sys.flags, flag, 0)
        if v > 0:
            args.append('-' + opt * v)
    for opt in sys.warnoptions:
        args.append('-W' + opt)
    return args


def get_command_line(**kwds):
    prog = 'from hupper.ipc import spawn_main; spawn_main(%s)'
    prog %= ', '.join('%s=%r' % item for item in kwds.items())
    opts = args_from_interpreter_flags()
    return [sys.executable] + opts + ['-c', prog]


def get_preparation_data():
    data = {}
    data['sys.argv'] = sys.argv
    return data


def prepare(data):
    if 'sys.argv' in data:
        sys.argv = data['sys.argv']


def spawn(spec, kwargs, pass_fds=()):
    """
    Invoke a python function in a subprocess.

    """
    r, w = os.pipe()
    for fd in [r] + list(pass_fds):
        set_inheritable(fd)

    preparation_data = get_preparation_data()

    r_handle = get_handle(r)
    args = get_command_line(pipe_handle=r_handle)
    process = subprocess.Popen(args, close_fds=False)

    to_child = os.fdopen(w, 'wb')
    to_child.write(pickle.dumps([preparation_data, spec, kwargs]))
    to_child.close()

    return process


def spawn_main(pipe_handle):
    fd = open_handle(pipe_handle, 'rb')
    from_parent = os.fdopen(fd, 'rb')
    preparation_data, spec, kwargs = pickle.load(from_parent)
    from_parent.close()

    prepare(preparation_data)

    modname, funcname = spec.rsplit('.', 1)
    module = importlib.import_module(modname)
    func = getattr(module, funcname)

    func(**kwargs)
    sys.exit(0)
