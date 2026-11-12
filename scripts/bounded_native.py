"""Bounded native byte transport with descendant containment.

Only successful stdout is returned. Stderr is discarded unless the caller
explicitly supplies a sink; Git must retain the default because remote
diagnostics may contain credentials. No shell is invoked here.
"""
from __future__ import annotations

import math
import os
import signal
import subprocess
import sys
from typing import Callable


class Refused(RuntimeError):
    pass


class _WindowsJob:
    """Private kill-on-close job; descendants cannot inherit its handle.

    Uses the documented Windows Job Objects API, without breakaway flags:
    https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
    Nested jobs require Windows 8 / Server 2012 or later.
    """

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", IoCounters),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                    ctypes.c_void_p, wintypes.DWORD]
        self.api.SetInformationJobObject.restype = wintypes.BOOL
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.AssignProcessToJobObject.restype = wintypes.BOOL
        self.api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.api.OpenProcess.restype = wintypes.HANDLE
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise Refused("Windows process containment unavailable")
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise Refused("Windows process containment unavailable")

    def assign(self, pid: int) -> None:
        # PROCESS_SET_QUOTA | PROCESS_TERMINATE, required for job assignment.
        process_handle = self.api.OpenProcess(0x0100 | 0x0001, False, pid)
        if not process_handle:
            raise Refused("Windows process containment assignment failed")
        try:
            if not self.api.AssignProcessToJobObject(self.handle, process_handle):
                raise Refused("Windows process containment assignment failed")
        finally:
            self.api.CloseHandle(process_handle)

    def close(self) -> None:
        if self.handle:
            if not self.api.CloseHandle(self.handle):
                raise Refused("Windows process containment cleanup failed")
            self.handle = None


# -I -S excludes user site/startup hooks before containment. The launcher waits
# for a one-byte gate released only after assignment. Git receives DEVNULL,
# never the gate pipe; optional checker input is forwarded as unchanged bytes.
_WINDOWS_LAUNCHER = """
import sys
if sys.stdin.buffer.read(1) != b'G':
    raise SystemExit(125)
payload = sys.stdin.buffer.read() if sys.argv[1] == 'pipe' else None
sys.stdin.close()
import subprocess
try:
    options = {'input': payload} if payload is not None else {'stdin': subprocess.DEVNULL}
    result = subprocess.run(sys.argv[2:], check=False, **options)
except OSError:
    raise SystemExit(126)
raise SystemExit(result.returncode)
"""


def _run_windows(command, timeout, environment, input):
    job = _WindowsJob()
    process = None
    assigned = False
    communicated = False
    try:
        process = subprocess.Popen(
            [sys.executable, "-I", "-S", "-c", _WINDOWS_LAUNCHER,
             "pipe" if input is not None else "null", *command],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=environment,
        )
        job.assign(process.pid)
        assigned = True
        try:
            stdout, stderr = process.communicate(input=b"G" + (input or b""), timeout=timeout)
            communicated = True
        except subprocess.TimeoutExpired as exc:
            raise Refused("Native command timed out") from exc
        return process.returncode, stdout, stderr
    except OSError as exc:
        raise Refused("Native executable unavailable") from exc
    finally:
        # Membership survives exited parents, unlike taskkill /PID /T. Close on
        # success too, so pipe-detached descendants cannot outlive this call.
        job.close()
        if process is not None and not communicated:
            if not assigned and process.poll() is None:
                process.kill()  # This unassigned launcher is still gated.
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired as exc:
                raise Refused("Native command timed out; containment cleanup failed") from exc


def _run_posix(command, timeout, environment, input):
    try:
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
            env=environment,
        )
    except OSError as exc:
        raise Refused("Native executable unavailable") from exc
    try:
        stdout, stderr = process.communicate(input=input, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # The command already exited during timeout handling.
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired as cleanup_error:
            raise Refused("Native command timed out; child pipes did not close") from cleanup_error
        raise Refused("Native command timed out") from exc
    return process.returncode, stdout, stderr


def run(command: list[str], timeout: float = 120, *, input: bytes | None = None,
        stderr_sink: Callable[[bytes], object] | None = None) -> bytes:
    if not command or not math.isfinite(timeout) or timeout <= 0:
        raise Refused("Native command and a finite positive deadline are required")
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never"}
    execute = _run_windows if os.name == "nt" else _run_posix
    returncode, stdout, stderr = execute(command, timeout, environment, input)
    if stderr and stderr_sink is not None:
        stderr_sink(stderr)
    if returncode:
        raise Refused(f"Native command failed (exit {returncode})")
    return stdout


def main() -> int:
    try:
        result = run(sys.argv[1:])
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    sys.stdout.buffer.write(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
