"""자식 프로세스를 agent와 같이 죽게 묶는다 (윈도우 Job Object, KILL_ON_JOB_CLOSE).

agent가 Ctrl+C로 정상 종료하면 mpv에 quit을 보내지만, 터미널 창을 X로 닫거나 강제 종료되면
그 정리 코드가 돌지 못한다. Job 핸들은 agent 프로세스가 끝날 때 OS가 닫고, 그때 묶인 프로세스도 종료된다.
"""

import ctypes
import logging
import subprocess
import sys

log = logging.getLogger(__name__)

_job = None  # 프로세스가 끝날 때까지 핸들을 쥐고 있어야 한다 (닫히는 순간 묶인 프로세스가 죽는다)

if sys.platform == "win32":
    from ctypes import wintypes

    class _BasicLimit(ctypes.Structure):  # JOBOBJECT_BASIC_LIMIT_INFORMATION
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):  # IO_COUNTERS
        _fields_ = [(name, ctypes.c_uint64) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class _ExtendedLimit(ctypes.Structure):  # JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        _fields_ = [
            ("BasicLimitInformation", _BasicLimit),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    _JobObjectExtendedLimitInformation = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    _kernel32.SetInformationJobObject.restype = wintypes.BOOL
    _kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]


def _get_job():
    global _job
    if _job is None:
        job = _kernel32.CreateJobObjectW(None, None)
        if not job:
            raise ctypes.WinError(ctypes.get_last_error())
        info = _ExtendedLimit()
        info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not _kernel32.SetInformationJobObject(job, _JobObjectExtendedLimitInformation,
                                                 ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        _job = job
    return _job


def kill_with_agent(proc: subprocess.Popen) -> bool:
    """proc를 agent 수명에 묶는다. 실패하면 경고만 남긴다 (정상 종료 경로는 그대로 동작)."""
    if sys.platform != "win32":
        return False
    try:
        if not _kernel32.AssignProcessToJobObject(_get_job(), int(proc._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        return True
    except OSError as e:
        log.warning("프로세스를 agent에 묶지 못함 (agent가 강제 종료되면 남을 수 있음): %s", e)
        return False
