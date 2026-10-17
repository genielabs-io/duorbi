"""Small native Job Object binding; imported only on Windows.

An unnamed, non-inheritable KILL_ON_JOB_CLOSE handle belongs to the backend,
never the runner. Breakaway is not enabled, so descendants remain contained.
"""
import ctypes
from ctypes import wintypes as w

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
SIZE_T = ctypes.c_size_t


class BasicLimits(ctypes.Structure):
    _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64),
                ('PerJobUserTimeLimit', ctypes.c_int64), ('LimitFlags', w.DWORD),
                ('MinimumWorkingSetSize', SIZE_T), ('MaximumWorkingSetSize', SIZE_T),
                ('ActiveProcessLimit', w.DWORD), ('Affinity', SIZE_T),
                ('PriorityClass', w.DWORD), ('SchedulingClass', w.DWORD)]


class IOCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
                ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [('BasicLimitInformation', BasicLimits), ('IoInfo', IOCounters),
                ('ProcessMemoryLimit', SIZE_T), ('JobMemoryLimit', SIZE_T),
                ('PeakProcessMemoryUsed', SIZE_T), ('PeakJobMemoryUsed', SIZE_T)]


class Accounting(ctypes.Structure):
    _fields_ = [(name, ctypes.c_int64) for name in
                ('TotalUserTime', 'TotalKernelTime', 'ThisPeriodTotalUserTime',
                 'ThisPeriodTotalKernelTime')] + [(name, w.DWORD) for name in
                ('TotalPageFaultCount', 'TotalProcesses', 'ActiveProcesses',
                 'TotalTerminatedProcesses')]


def _bind(name, result, *args):
    fn = getattr(k32, name)
    fn.restype, fn.argtypes = result, args
    return fn


_create = _bind('CreateJobObjectW', w.HANDLE, ctypes.c_void_p, w.LPCWSTR)
_set = _bind('SetInformationJobObject', w.BOOL, w.HANDLE, ctypes.c_int,
             ctypes.c_void_p, w.DWORD)
_query = _bind('QueryInformationJobObject', w.BOOL, w.HANDLE, ctypes.c_int,
               ctypes.c_void_p, w.DWORD, ctypes.c_void_p)
_open = _bind('OpenProcess', w.HANDLE, w.DWORD, w.BOOL, w.DWORD)
_assign = _bind('AssignProcessToJobObject', w.BOOL, w.HANDLE, w.HANDLE)
_terminate = _bind('TerminateJobObject', w.BOOL, w.HANDLE, w.UINT)
_close = _bind('CloseHandle', w.BOOL, w.HANDLE)
_wait = _bind('WaitForSingleObject', w.DWORD, w.HANDLE, w.DWORD)


def _check(value):
    if not value:
        raise ctypes.WinError(ctypes.get_last_error())
    return value


class Job:
    def __init__(self):
        self.handle = _check(_create(None, None))
        self.closed = False
        try:
            info = ExtendedLimits()
            info.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
            _check(_set(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)))
        except BaseException:
            self.close()
            raise

    def assign(self, pid):
        process = _check(_open(0x0100 | 0x0001, False, pid))  # SET_QUOTA | TERMINATE
        try:
            _check(_assign(self.handle, process))
        finally:
            _check(_close(process))

    def terminate(self):
        _check(_terminate(self.handle, 1))

    def active_count(self):
        info = Accounting()
        _check(_query(self.handle, 1, ctypes.byref(info), ctypes.sizeof(info), None))
        return info.ActiveProcesses

    def close(self):
        if not self.closed:
            _check(_close(self.handle))
            self.closed = True


def process_is_running(pid):
    """Check liveness without os.kill on Windows (which may send a signal)."""
    process = _open(0x00100000, False, pid)  # SYNCHRONIZE
    if not process:
        error = ctypes.get_last_error()
        if error == 87:  # ERROR_INVALID_PARAMETER: PID no longer exists
            return False
        raise ctypes.WinError(error)
    try:
        status = _wait(process, 0)
        if status == 0xffffffff:
            raise ctypes.WinError(ctypes.get_last_error())
        return status == 258  # WAIT_TIMEOUT
    finally:
        _check(_close(process))
