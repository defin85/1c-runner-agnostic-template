from __future__ import annotations

import ctypes
import os
import signal
from dataclasses import dataclass
from pathlib import Path

from .runtime_errors import CommandError
from .runtime_process import ProcessResult, run_process


@dataclass(frozen=True, slots=True)
class ProcessIdentity:
    pid: int
    executable: str
    start_time: str


def process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        handle = kernel32.OpenProcess(0x00100000, False, pid)
        if not handle:
            return False
        kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError, PermissionError):
        return False
    return True


def identity_matches(actual: ProcessIdentity, expected: ProcessIdentity) -> bool:
    return (
        actual.pid == expected.pid
        and Path(actual.executable).resolve(strict=False) == Path(expected.executable).resolve(strict=False)
        and actual.start_time == expected.start_time
    )


def terminate_owned_process(actual: ProcessIdentity, expected: ProcessIdentity) -> None:
    if not identity_matches(actual, expected):
        raise CommandError(f"refusing to terminate process {expected.pid}: identity mismatch")
    if process_is_alive(expected.pid):
        os.kill(expected.pid, signal.SIGTERM)


def service_command(service_name: str, action: str, *, windows: bool | None = None) -> list[str]:
    if not service_name or any(character in service_name for character in "\r\n\0"):
        raise CommandError("service name is invalid")
    if action not in {"start", "stop", "restart", "status"}:
        raise CommandError(f"unsupported service action: {action}")
    is_windows = os.name == "nt" if windows is None else windows
    if is_windows:
        windows_action = "query" if action == "status" else action
        return ["sc.exe", windows_action, service_name]
    return ["systemctl", action, service_name]


def manage_service(
    service_name: str,
    action: str,
    *,
    windows: bool | None = None,
    timeout: float | None = 30,
) -> ProcessResult:
    if (os.name == "nt" if windows is None else windows) and action == "restart":
        stopped = run_process(service_command(service_name, "stop", windows=True), timeout=timeout)
        if stopped.returncode != 0:
            return stopped
        return run_process(service_command(service_name, "start", windows=True), timeout=timeout)
    return run_process(service_command(service_name, action, windows=windows), timeout=timeout)
