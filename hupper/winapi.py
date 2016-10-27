import ctypes
from ctypes import wintypes
import msvcrt
import os

kernel32 = ctypes.windll.kernel32

class JobObjectInfoType(object):
    AssociateCompletionPortInformation = 7
    BasicLimitInformation = 2
    BasicUIRestrictions = 4
    EndOfJobTimeInformation = 6
    ExtendedLimitInformation = 9
    SecurityLimitInformation = 5
    GroupInformation = 11


class JobObjectLimit(object):
    KILL_ON_JOB_CLOSE = 0x2000


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ('ReadOperationCount', ctypes.c_uint64),
        ('WriteOperationCount', ctypes.c_uint64),
        ('OtherOperationCount', ctypes.c_uint64),
        ('ReadTransferCount', ctypes.c_uint64),
        ('WriteTransferCount', ctypes.c_uint64),
        ('OtherTransferCount', ctypes.c_uint64),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('PerProcessUserTimeLimit', ctypes.c_int64),
        ('PerJobUserTimeLimit', ctypes.c_int64),
        ('LimitFlags', ctypes.c_uint32),
        ('MinimumWorkingSetSize', ctypes.c_void_p),
        ('MaximumWorkingSetSize', ctypes.c_void_p),
        ('ActiveProcessLimit', ctypes.c_uint32),
        ('Affinity', ctypes.c_void_p),
        ('PriorityClass', ctypes.c_uint32),
        ('SchedulingClass', ctypes.c_uint32),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ('IoInfo', IO_COUNTERS),
        ('ProcessMemoryLimit', ctypes.c_void_p),
        ('JobMemoryLimit', ctypes.c_void_p),
        ('PeakProcessMemoryUsed', ctypes.c_void_p),
        ('PeakJobMemoryUsed', ctypes.c_void_p),
    ]


class StandardAccessLimit(object):
    DELETE = 0x00010000
    READ_CONTROL = 0x00020000
    SYNCHRONIZE = 0x00100000
    WRITE_DAC = 0x00040000
    WRITE_OWNER = 0x00080000
    STANDARD_RIGHTS_REQUIRED = (
        DELETE | READ_CONTROL | WRITE_DAC | WRITE_OWNER)


class ProcessAccessLimit(object):
    PROCESS_CREATE_PROCESS = 0x0080
    PROCESS_CREATE_THREAD = 0x0002
    PROCESS_DUP_HANDLE = 0x0040
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PROCESS_SET_INFORMATION = 0x0200
    PROCESS_SET_QUOTA = 0x0100
    PROCESS_SUSPEND_RESUME = 0x0800
    PROCESS_TERMINATE = 0x0001
    PROCESS_VM_OPERATION = 0x0008
    PROCESS_VM_READ = 0x0010
    PROCESS_VM_WRITE = 0x0020
    SYNCHRONIZE = 0x00100000
    PROCESS_ALL_ACCESS = (
        StandardAccessLimit.STANDARD_RIGHTS_REQUIRED | SYNCHRONIZE | 0xFFF)


class DuplicateOption(object):
    DUPLICATE_SAME_ACCESS = 0x0002


class Handle(int):
    closed = False

    def Close(self):
        if not self.closed:
            self.closed = True
            CloseHandle(int(self))

    def Detach(self):
        if not self.closed:
            self.closed = True
            return int(self)
        raise ValueError("already closed")

    def __repr__(self):
        return "%s(%d)" % (self.__class__.__name__, int(self))

    __del__ = Close
    __str__ = __repr__


def CloseHandle(h):
    kernel32.CloseHandle(h)


def DuplicateHandle(
    sourceProcessHandle, sourceHandle, targetProcessHandle,
    desiredAccess, inheritHandle, options
):
    targetHandle = wintypes.HANDLE()
    ret = kernel32.DuplicateHandle(
        sourceProcessHandle, sourceHandle, targetProcessHandle,
        ctypes.byref(targetHandle), desiredAccess, inheritHandle, options)
    if not ret:
        raise RuntimeError('failed to duplicate handle')
    return Handle(targetHandle.value)


def GetCurrentProcess():
    hp = kernel32.GetCurrentProcess()
    return Handle(hp)
    

def OpenProcess(desiredAccess, inherit, pid):
    hp = kernel32.OpenProcess(desiredAccess, inherit, pid)
    if not hp:
        raise RuntimeError('failed to open process')
    return Handle(hp)


def CreateJobObject(jobAttributes, name):
    hp = kernel32.CreateJobObjectA(jobAttributes, name)
    if not hp:
        raise RuntimeError('failed to create job object')
    return Handle(hp)


def SetInformationJobObject(
    hJob, infoType, jobObjectInfo, jobObjectInfoLength,
):
    ret = kernel32.SetInformationJobObject(
        hJob, infoType, jobObjectInfo, jobObjectInfoLength,
    )
    if not ret:
        raise RuntimeError('failed to set information job object')


def AssignProcessToJobObject(hJob, hProcess):
    ret = kernel32.AssignProcessToJobObject(hJob, hProcess)
    if not ret:
        raise RuntimeError('failed to assign process to job object')


class ProcessGroup(object):
    def __init__(self):
        self.h_job = CreateJobObject(None, None)

        info = JOBOBJECT_BASIC_LIMIT_INFORMATION()
        info.LimitFlags = JobObjectLimit.KILL_ON_JOB_CLOSE

        extended_info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        extended_info.BasicLimitInformation = info

        SetInformationJobObject(
            self.h_job,
            JobObjectInfoType.ExtendedLimitInformation,
            ctypes.pointer(extended_info),
            ctypes.sizeof(extended_info),
        )

    def add_child(self, pid):
        hp = OpenProcess(ProcessAccessLimit.PROCESS_ALL_ACCESS, False, pid)
        return AssignProcessToJobObject(self.h_job, hp)


def send_fd(pipe, fd, pid):
    hf = msvcrt.get_osfhandle(fd)
    hp = OpenProcess(ProcessAccessLimit.PROCESS_ALL_ACCESS, False, pid)
    tp = DuplicateHandle(
        GetCurrentProcess(), hf, hp,
        0, True, DuplicateOption.DUPLICATE_SAME_ACCESS,
    )
    tp.Detach()  # do not close the handle
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
