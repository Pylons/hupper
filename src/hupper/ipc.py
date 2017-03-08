import os
import sys

from .compat import WIN


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

    def send_fd(pipe, fd, pid):
        hf = msvcrt.get_osfhandle(fd)
        hp = winapi.OpenProcess(winapi.PROCESS_ALL_ACCESS, False, pid)
        tp = winapi.DuplicateHandle(
            winapi.GetCurrentProcess(), hf, hp,
            0, False, winapi.DUPLICATE_SAME_ACCESS,
        ).Detach()  # do not close the handle
        pipe.send(tp)

    def recv_fd(pipe, mode):
        handle = pipe.recv()
        flags = 0
        if 'w' not in mode and '+' not in mode:
            flags |= os.O_RDONLY
        if 'b' not in mode:
            flags |= os.O_TEXT
        if 'a' in mode:
            flags |= os.O_APPEND
        fd = msvcrt.open_osfhandle(handle, flags)
        return fd

    def patch_stdin(fd):
        sys.stdin = os.fdopen(fd, 'r')

    def snapshot_termios(fd):
        pass

    def restore_termios(fd, state):
        pass

else:
    import termios

    class ProcessGroup(object):
        def add_child(self, pid):
            # nothing to do on *nix
            pass

    def send_fd(pipe, fd, pid):
        pipe.send(fd)

    def recv_fd(pipe, mode):
        fd = pipe.recv()
        return fd

    def patch_stdin(fd):
        # Python's input() function used by pdb and other things only uses
        # readline if stdin matches the stdin file descriptor that the
        # process started with (0). Since multiprocessing closes it already
        # we can just dup the new fd over it.
        os.dup2(fd, 0)
        sys.stdin = os.fdopen(0, 'r')

    def snapshot_termios(fd):
        if os.isatty(fd):
            state = termios.tcgetattr(fd)
            return state

    def restore_termios(fd, state):
        if os.isatty(fd) and state:
            termios.tcflush(fd, termios.TCIOFLUSH)
            termios.tcsetattr(fd, termios.TCSANOW, state)


def dup_fd(fd):
    fd = os.dup(fd)

    # py34 and above sets CLOEXEC automatically on file descriptors
    # NOTE: this isn't usually an issue because multiprocessing doesn't
    # actually exec on linux/macos, but we're depending on the behavior
    if hasattr(os, 'get_inheritable') and not os.get_inheritable(fd):
        os.set_inheritable(fd, True)

    return fd
