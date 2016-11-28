import os

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
            return winapi.AssignProcessToJobObject(self.h_job, hp)

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
        return os.fdopen(fd, mode)

else:
    class ProcessGroup(object):
        def add_child(self, pid):
            # nothing to do on *nix
            pass

    def send_fd(pipe, fd, pid):
        pipe.send(fd)

    def recv_fd(pipe, mode):
        fd = pipe.recv()
        return os.fdopen(fd, mode)
