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
            hp = winapi.OpenProcess(winapi.PROCESS_ALL_ACCESS, 0, pid)
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
        # we are expecting the fd to be inheritable as well as the handle
        # otherwise we would need to dup the handle
        th = msvcrt.get_osfhandle(fd)
        if (
            hasattr(os, 'get_handle_inheritable') and
            not os.get_handle_inheritable(th)
        ):
            hp = winapi.OpenProcess(winapi.PROCESS_ALL_ACCESS, 0, pid)
            th = winapi.DuplicateHandle(
                winapi.GetCurrentProcess(), th, hp,
                0, 0, winapi.DUPLICATE_SAME_ACCESS,
            ).Detach()  # do not close the handle
        pipe.send(th)

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


def dup_fd(src_fd):
    fd = os.dup(src_fd)

    # we want to return an inheritable fd
    # in py3 the default is set to not inheritable, but before that
    # it was always inheritable so we only bother to use the py3 api here
    # to switch the flag if necessary (in hupper we are usually duping stdin
    # which is inheritable by default)
    if hasattr(os, 'get_inheritable') and not os.get_inheritable(fd):
        os.set_inheritable(fd, True)

    return fd