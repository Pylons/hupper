import io
import imp
import os
import struct
import sys
import subprocess
import threading

from .compat import WIN
from .compat import pickle
from .compat import queue
from .utils import resolve_spec


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
    import fcntl
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


def _pipe():
    r, w = os.pipe()
    set_inheritable(r, False)
    set_inheritable(w, False)
    return r, w


def Pipe():
    c2pr_fd, c2pw_fd = _pipe()
    p2cr_fd, p2cw_fd = _pipe()

    c1 = Connection(c2pr_fd, p2cw_fd)
    c2 = Connection(p2cr_fd, c2pw_fd)
    return c1, c2


class Connection(object):
    """
    A connection to a bi-directional pipe.

    """
    _packet_len = struct.Struct('Q')

    def __init__(self, r_fd, w_fd):
        self.r_fd = r_fd
        self.w_fd = w_fd

    def __getstate__(self):
        return {
            'r_handle': get_handle(self.r_fd),
            'w_handle': get_handle(self.w_fd),
        }

    def __setstate__(self, state):
        self.r_fd = open_handle(state['r_handle'], 'rb')
        self.w_fd = open_handle(state['w_handle'], 'wb')

    def activate(self):
        self.send_lock = threading.Lock()
        self.reader_queue = queue.Queue()

        self.reader_thread = threading.Thread(target=self._read_loop)
        self.reader_thread.daemon = True
        self.reader_thread.start()

    def close(self):
        close_fd(self.r_fd)
        close_fd(self.w_fd)

    def _recv_packet(self):
        buf = io.BytesIO()
        chunk = os.read(self.r_fd, self._packet_len.size)
        if not chunk:
            return
        size = remaining = self._packet_len.unpack(chunk)[0]
        while remaining > 0:
            chunk = os.read(self.r_fd, remaining)
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

    def _write_packet(self, data):
        while data:
            n = os.write(self.w_fd, data)
            data = data[n:]

    def send(self, value):
        data = pickle.dumps(value)
        with self.send_lock:
            self._write_packet(self._packet_len.pack(len(data)))
            self._write_packet(data)
        return len(data) + self._packet_len.size

    def recv(self, timeout=None):
        packet = self.reader_queue.get(block=True, timeout=timeout)
        return packet


def set_inheritable(fd, inheritable):
    # On py34+ we can use os.set_inheritable but < py34 we must polyfill
    # with fcntl and SetHandleInformation
    if hasattr(os, 'get_inheritable'):
        if os.get_inheritable(fd) != inheritable:
            os.set_inheritable(fd, inheritable)

    elif WIN:
        h = get_handle(fd)
        flags = winapi.HANDLE_FLAG_INHERIT if inheritable else 0
        winapi.SetHandleInformation(h, winapi.HANDLE_FLAG_INHERIT, flags)

    else:
        flags = fcntl.fcntl(fd, fcntl.F_GETFD)
        if inheritable:
            new_flags = flags & ~fcntl.FD_CLOEXEC
        else:
            new_flags = flags | fcntl.FD_CLOEXEC
        if new_flags != flags:
            fcntl.fcntl(fd, fcntl.F_SETFD, new_flags)


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
    args = [sys.executable] + opts + ['-c', prog]

    # ensure hupper is on the PYTHONPATH in the worker process
    self_path = os.path.abspath(imp.find_module('hupper')[1])
    extra_py_paths = [os.path.dirname(self_path)]

    env = os.environ.copy()
    env['PYTHONPATH'] = (
        os.pathsep.join(extra_py_paths) +
        os.pathsep +
        env.get('PYTHONPATH', '')
    )
    return args, env


def get_preparation_data():
    data = {}
    data['sys.argv'] = sys.argv

    # multiprocessing does some work here to replace '' in sys.path with
    # os.getcwd() but it is not valid to assume that os.getcwd() at the time
    # hupper is imported is the starting folder of the process so for now
    # we'll just assume that the user has not changed the CWD
    data['sys.path'] = list(sys.path)
    return data


def prepare(data):
    if 'sys.argv' in data:
        sys.argv = data['sys.argv']

    if 'sys.path' in data:
        sys.path = data['sys.path']


def spawn(spec, kwargs, pass_fds=()):
    """
    Invoke a python function in a subprocess.

    """
    r, w = os.pipe()
    for fd in [r] + list(pass_fds):
        set_inheritable(fd, True)

    preparation_data = get_preparation_data()

    r_handle = get_handle(r)
    args, env = get_command_line(pipe_handle=r_handle)
    process = subprocess.Popen(args, env=env, close_fds=False)

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

    func = resolve_spec(spec)
    func(**kwargs)
    sys.exit(0)
