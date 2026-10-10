"""`make analyze-bsl`: full BSL diagnostics through the `bsl-analyzer` MCP server.

The command starts the repository MCP server (`make bsl-analyzer-mcp`) as a child process, asks its
`diagnostics` tool for every module of the source tree and compares the result with the optional
registry of exact diagnostic exceptions. The child process tree is owned by this command: a POSIX
session (process group) or a Windows Job object, so a hung server and its descendants are stopped.

`BSL_ANALYZER_MODE=standalone` runs `bsl-analyzer-app analyze` instead of the resident server; it
is meant for small fixture trees and requires `BSL_ANALYZER_REPORT`.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import IO, Any

from .bsl_mcp_runtime import (
    connection_registry_path,
    load_dotenv,
    resolve_analyzer_executable,
    select_source_dir,
    source_candidates,
)
from .common import WINDOWS, CommandError, die, object_dict, object_list, project_root
from .external_bsl_check import analyzer_app, analyzer_available, run_analyzer

RUNBOOK = "docs/agent/bsl-analyzer-workspace-runbook.md"
DEFAULT_EXCEPTIONS_FILE = "bsl-analyzer-exceptions.json"
# Identifier of the reviewed finding that justifies an exception, for example `EX-001`.
EXCEPTION_ID = re.compile(r"[A-Z][A-Z0-9]*-\d+")
EXCEPTION_FIELDS = frozenset({"finding", "path", "line", "rule", "message", "fingerprint"})
CREATE_SUSPENDED = 0x00000004
STOP_GRACE_SECONDS = 2.0

Diagnostic = dict[str, Any]


def _not_configured(reason: str) -> CommandError:
    return CommandError(f"bsl-analyzer is not configured: {reason}; see {RUNBOOK}")


# ---------------------------------------------------------------------------------------------
# Entry point


def analyze_bsl(args: list[str] | None = None) -> int:
    if args:
        die("analyze-bsl does not accept arguments; configure it through BSL_* environment variables")
    root = project_root()
    load_dotenv(root / ".env")
    source = _source_dir(root)
    files = sorted(source.rglob("*.bsl")) if source.is_dir() else []
    if not files:
        die(f"BSL source directory contains no modules: {source}")
    try:
        source.relative_to(root)
    except ValueError:
        die(f"BSL source directory is outside the MCP workspace: {source}")
    report_value = os.environ.get("BSL_ANALYZER_REPORT")
    report_path = Path(report_value).resolve() if report_value else None
    exceptions_path = _exceptions_path(root)
    if os.environ.get("BSL_ANALYZER_MODE") == "standalone":
        if report_path is None:
            die("standalone analysis requires BSL_ANALYZER_REPORT")
        return _analyze_bsl_standalone(source, files, report_path, exceptions_path, root)

    command = _mcp_command(root)
    timeout = float(os.environ.get("BSL_ANALYZER_MCP_TIMEOUT", "180"))
    server_info, revisions, findings = _collect_mcp_diagnostics(root, files, command, timeout)
    if report_path is not None:
        _write_json_atomic(report_path, _diagnostics_report(root, source, files, server_info, revisions, findings))

    analyzed = {path.relative_to(root).as_posix() for path in files}
    all_exceptions = _load_diagnostic_exceptions(exceptions_path)
    exceptions = [item for item in all_exceptions if item["path"] in analyzed]
    if os.environ.get("BSL_ANALYZER_REFRESH_RELOCATED_EXCEPTIONS") == "1":
        _refresh_relocated_diagnostic_exceptions(exceptions_path, all_exceptions, exceptions, findings)
        exceptions = [item for item in _load_diagnostic_exceptions(exceptions_path) if item["path"] in analyzed]
    unmatched = _unmatched_diagnostics(findings, exceptions)
    if unmatched:
        print(f"BSL analysis found {len(unmatched)} unexpected diagnostics ({len(findings)} total):", file=sys.stderr)
        for finding in unmatched:
            print(f"- {finding['path']}:{finding['line']}: {finding['rule']} — {finding['message']}", file=sys.stderr)
        return 1
    print(f"BSL analysis passed: {len(files)} modules, {len(findings)} diagnostics, {len(exceptions)} exact exceptions")
    return 0


def _source_dir(root: Path) -> Path:
    configured = os.environ.get("BSL_SRC_DIR")
    if configured:
        path = Path(configured)
        return (path if path.is_absolute() else root / path).resolve()
    try:
        return select_source_dir(root, source_candidates()).resolve()
    except CommandError as error:
        raise _not_configured(f"{error} (set BSL_SRC_DIR or BSL_ANALYZER_SOURCE_CANDIDATES)") from error


def _exceptions_path(root: Path) -> Path | None:
    configured = os.environ.get("BSL_ANALYZER_EXCEPTIONS")
    if configured:
        return Path(configured).resolve()
    default = root / DEFAULT_EXCEPTIONS_FILE
    return default if default.is_file() else None


def _mcp_command(root: Path) -> list[str]:
    """Command that starts the MCP server; fails with a pointer to the runbook when it is not configured."""
    configured = os.environ.get("BSL_ANALYZER_MCP_BIN")
    if configured:
        launcher = Path(configured).resolve()
        if not launcher.is_file():
            raise _not_configured(f"MCP launcher BSL_ANALYZER_MCP_BIN is not a file: {launcher}")
        return _mcp_launcher_command(launcher)
    try:
        resolve_analyzer_executable()
    except CommandError as error:
        raise _not_configured(str(error)) from error
    registry = connection_registry_path(root)
    if not registry.is_file():
        raise _not_configured(f"connection registry is missing: {registry}")
    return [sys.executable, "-m", "scripts.python.cli", "bsl-analyzer-mcp"]


def _mcp_launcher_command(launcher: Path) -> list[str]:
    suffix = launcher.suffix.lower()
    if suffix == ".py":
        return [sys.executable, str(launcher)]
    if suffix == ".ps1":
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            die("PowerShell 7 is required to start the BSL Analyzer MCP launcher: install pwsh")
        return [pwsh, "-NoLogo", "-NoProfile", "-File", str(launcher)]
    if suffix == ".sh":
        return ["bash", str(launcher)]
    return [str(launcher)]


# ---------------------------------------------------------------------------------------------
# MCP session


def _collect_mcp_diagnostics(
    root: Path, files: list[Path], command: list[str], timeout: float
) -> tuple[dict[str, Any], set[int], list[Diagnostic]]:
    findings: list[Diagnostic] = []
    revisions: set[int] = set()
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr:
        process = _spawn_mcp_process(command, root, stderr)
        responses, reader = _start_mcp_reader(process)
        try:
            initialize = _mcp_request(
                process,
                1,
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "analyze-bsl", "version": "1"},
                },
                timeout,
                responses,
            )
            _mcp_notify(process, "notifications/initialized", {})
            status, request_id = _wait_for_diagnostics(process, 2, timeout, responses)
            print(
                f"BSL Analyzer MCP ready: generation={status.get('generation')}, files={status.get('files')}",
                flush=True,
            )
            started = last_progress = time.monotonic()
            for index, path in enumerate(files, 1):
                relative = path.relative_to(root).as_posix()
                payload, request_id = _wait_for_file_diagnostics(process, request_id, relative, timeout, responses)
                revision, file_findings = _file_findings(relative, payload)
                revisions.add(revision)
                findings.extend(file_findings)
                now = time.monotonic()
                if index == len(files) or now - last_progress >= 30:
                    print(
                        f"BSL Analyzer progress: checked={index}/{len(files)} elapsed={int(now - started)}s", flush=True
                    )
                    last_progress = now
        finally:
            _stop_mcp_process(process, reader)
    findings.sort(key=lambda item: (item["path"], item["line"], item["column"], item["rule"], item["message"]))
    return object_dict(initialize.get("serverInfo")), revisions, findings


def _file_findings(relative: str, payload: dict[str, Any]) -> tuple[int, list[Diagnostic]]:
    if payload.get("stale") or payload.get("reload") == "failed":
        die(f"BSL diagnostics are stale for {relative}")
    result = object_dict(payload.get("result"))
    if result.get("error"):
        if result.get("detail") == "path is not a resident workspace .bsl file":
            die(
                f"BSL source is outside the analyzer resident roots: {relative}; analyze the source tree "
                "the MCP server indexes (BSL_ANALYZER_SOURCE_CANDIDATES)"
            )
        die(f"BSL diagnostics failed for {relative}: {result.get('detail') or result['error']}")
    if result.get("out_of_scope"):
        die(f"BSL module was not analyzed because it is out of scope: {relative}")
    if result.get("truncated"):
        die(f"BSL diagnostics were truncated for {relative}")
    file_findings = object_list(result.get("findings"))
    counts = object_dict(result.get("counts"))
    total = sum(
        value if isinstance(value := counts.get(key), int) else 0 for key in ("error", "warning", "info", "hint")
    )
    if total != len(file_findings):
        die(f"incomplete BSL diagnostics for {relative}: returned {len(file_findings)} of {total}")
    revision = payload.get("revision")
    if not isinstance(revision, int):
        die(f"incomplete BSL diagnostics for {relative}: revision is missing")
    diagnostics: list[Diagnostic] = []
    for value in file_findings:
        finding = object_dict(value)
        location = object_dict(finding.get("range"))
        start_line = location.get("start_line")
        if not isinstance(start_line, int):
            die(f"incomplete BSL diagnostic location for {relative}")
        diagnostics.append(
            _diagnostic(
                relative,
                finding,
                start_line=start_line,
                start_column=location.get("start_column"),
                end_line=location.get("end_line"),
                end_column=location.get("end_column"),
            )
        )
    return revision, diagnostics


def _diagnostic(
    path: str,
    finding: dict[str, Any],
    *,
    start_line: object,
    start_column: object,
    end_line: object,
    end_column: object,
) -> Diagnostic:
    diagnostic: Diagnostic = {
        "path": path,
        "line": _one_based(start_line),
        "column": _one_based(start_column),
        "endLine": _one_based(end_line),
        "endColumn": _one_based(end_column),
        "rule": str(finding.get("code", "Unknown")),
        "severity": str(finding.get("severity", "unknown")),
        "message": str(finding.get("message", "")),
    }
    diagnostic["fingerprint"] = _diagnostic_fingerprint(diagnostic)
    return diagnostic


def _wait_for_diagnostics(
    process: subprocess.Popen[str], request_id: int, timeout: float, responses: queue.Queue[str | Exception | None]
) -> tuple[dict[str, Any], int]:
    deadline = time.monotonic() + timeout
    while True:
        response = _mcp_request(
            process,
            request_id,
            "tools/call",
            {"name": "diagnostics", "arguments": {"action": "status"}},
            max(0.1, deadline - time.monotonic()),
            responses,
        )
        request_id += 1
        status = _structured_result(response)
        state = status.get("state") or status.get("status")
        if state == "ready":
            return status, request_id
        if state == "failed":
            die(f"BSL diagnostics resident failed: {status.get('error', 'unknown error')}")
        if time.monotonic() >= deadline:
            die("BSL diagnostics resident did not become ready")
        time.sleep(0.25)


def _wait_for_file_diagnostics(
    process: subprocess.Popen[str],
    request_id: int,
    path: str,
    timeout: float,
    responses: queue.Queue[str | Exception | None],
) -> tuple[dict[str, Any], int]:
    deadline = time.monotonic() + timeout
    arguments = {"action": "file", "path": path, "min_severity": "hint", "detail": "concise", "max_findings": 100000}
    while True:
        response = _mcp_request(
            process,
            request_id,
            "tools/call",
            {"name": "diagnostics", "arguments": arguments},
            max(0.1, deadline - time.monotonic()),
            responses,
        )
        request_id += 1
        payload = _structured_result(response)
        if (payload.get("state") or payload.get("status")) != "loading":
            return payload, request_id
        if time.monotonic() >= deadline:
            die(f"BSL diagnostics did not become ready for {path}")
        time.sleep(0.25)


def _structured_result(response: dict[str, Any]) -> dict[str, Any]:
    if response.get("isError"):
        die("BSL Analyzer MCP tool returned an error")
    return object_dict(response.get("structuredContent"))


def _start_mcp_reader(process: subprocess.Popen[str]) -> tuple[queue.Queue[str | Exception | None], threading.Thread]:
    responses: queue.Queue[str | Exception | None] = queue.Queue()
    stdout = process.stdout
    if stdout is None:
        die("BSL Analyzer MCP stdout is unavailable")

    def read() -> None:
        try:
            for line in stdout:
                responses.put(line)
        except Exception as exc:  # any read failure is reported to the waiting request
            responses.put(exc)
        finally:
            responses.put(None)

    reader = threading.Thread(target=read, name="bsl-mcp-stdout", daemon=True)
    reader.start()
    return responses, reader


def _mcp_request(
    process: subprocess.Popen[str],
    request_id: int,
    method: str,
    params: dict[str, Any],
    timeout: float,
    responses: queue.Queue[str | Exception | None],
) -> dict[str, Any]:
    _mcp_write(process, {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        try:
            if remaining <= 0:
                raise queue.Empty
            line = responses.get(timeout=remaining)
        except queue.Empty:
            die(f"BSL Analyzer MCP request timed out: {method}")
        if line is None:
            # Server stderr may contain local credentials, so it is never echoed.
            die("BSL Analyzer MCP stopped unexpectedly")
        if isinstance(line, Exception):
            die("BSL Analyzer MCP stdout could not be read")
        try:
            response = object_dict(json.loads(line))
        except ValueError:
            die("BSL Analyzer MCP returned invalid JSON")
        if response.get("id") != request_id:
            continue
        if "error" in response:
            error = object_dict(response["error"])
            die(f"BSL Analyzer MCP error: code={error.get('code', 'unknown')}")
        return object_dict(response.get("result"))


def _mcp_notify(process: subprocess.Popen[str], method: str, params: dict[str, Any]) -> None:
    _mcp_write(process, {"jsonrpc": "2.0", "method": method, "params": params})


def _mcp_write(process: subprocess.Popen[str], payload: dict[str, Any]) -> None:
    if process.stdin is None:
        die("BSL Analyzer MCP stdin is unavailable")
    try:
        process.stdin.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        process.stdin.flush()
    except OSError:
        die("BSL Analyzer MCP stdin closed unexpectedly")


# ---------------------------------------------------------------------------------------------
# Process tree ownership

_mcp_process_cleanup: dict[int, Callable[[], None]] = {}


def _spawn_mcp_process(
    command: list[str],
    cwd: Path,
    stderr: IO[str],
    env: dict[str, str] | None = None,
    *,
    windows: bool = WINDOWS,
) -> subprocess.Popen[str]:
    """Start the server owning its whole tree: a new POSIX session, or a Job object on Windows.

    On Windows the launcher starts suspended and is assigned to a kill-on-close Job before its
    first thread runs, so no descendant can escape the Job.
    """
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr,
        text=True,
        encoding="utf-8",
        bufsize=1,
        start_new_session=not windows,
        creationflags=CREATE_SUSPENDED if windows else 0,
    )
    try:
        if windows:
            _mcp_process_cleanup[process.pid] = _windows_mcp_job(process)
        else:

            def stop_group() -> None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass

            _mcp_process_cleanup[process.pid] = stop_group
    except BaseException:
        process.kill()
        process.wait(timeout=5)
        for stream in (process.stdin, process.stdout):
            if stream is not None:
                stream.close()
        raise
    return process


def _stop_mcp_process(process: subprocess.Popen[str], reader: threading.Thread | None = None) -> None:
    """Close stdin, give the server a short grace period, then stop every process it owns."""
    if process.stdin is not None:
        try:
            process.stdin.close()
        except OSError:
            pass
    try:
        process.wait(timeout=STOP_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        pass
    # Ownership survives an early launcher exit: the Job on Windows, the session group on POSIX.
    stop_tree = _mcp_process_cleanup.pop(process.pid, None)
    cleanup_error: Exception | None = None
    if stop_tree is not None:
        try:
            stop_tree()
        except Exception as error:  # re-raised after the process and reader are reaped
            cleanup_error = error
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    if reader is not None:
        reader.join(timeout=5)
        if reader.is_alive():
            die("BSL Analyzer MCP reader did not stop after process termination")
    if process.stdout is not None:
        process.stdout.close()
    if cleanup_error is not None:
        raise cleanup_error


def _windows_mcp_job(process: subprocess.Popen[str]) -> Callable[[], None]:
    """Assign the still-suspended launcher to a kill-on-close Job, then resume its primary thread."""
    if sys.platform != "win32":
        raise OSError("Windows Job objects are available only on Windows")
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    class BasicLimit(ctypes.Structure):
        _fields_ = [
            ("process_time", ctypes.c_int64),
            ("job_time", ctypes.c_int64),
            ("flags", wintypes.DWORD),
            ("min_ws", ctypes.c_size_t),
            ("max_ws", ctypes.c_size_t),
            ("active_limit", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority", wintypes.DWORD),
            ("scheduling", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_uint64)
            for name in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")
        ]

    class ExtendedLimit(ctypes.Structure):
        _fields_ = [
            ("basic", BasicLimit),
            ("io", IoCounters),
            ("process_memory", ctypes.c_size_t),
            ("job_memory", ctypes.c_size_t),
            ("peak_process_memory", ctypes.c_size_t),
            ("peak_job_memory", ctypes.c_size_t),
        ]

    class Accounting(ctypes.Structure):
        _fields_ = [
            ("user_time", ctypes.c_int64),
            ("kernel_time", ctypes.c_int64),
            ("period_user_time", ctypes.c_int64),
            ("period_kernel_time", ctypes.c_int64),
            ("page_faults", wintypes.DWORD),
            ("total", wintypes.DWORD),
            ("active", wintypes.DWORD),
            ("terminated", wintypes.DWORD),
        ]

    class ThreadEntry(ctypes.Structure):
        _fields_ = [
            ("size", wintypes.DWORD),
            ("usage", wintypes.DWORD),
            ("thread_id", wintypes.DWORD),
            ("owner_pid", wintypes.DWORD),
            ("priority", wintypes.LONG),
            ("delta", wintypes.LONG),
            ("flags", wintypes.DWORD),
        ]

    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateJobObject.restype = wintypes.BOOL
    kernel.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    kernel.QueryInformationJobObject.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
    kernel.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
    kernel.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenThread.restype = wintypes.HANDLE
    kernel.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel.ResumeThread.restype = wintypes.DWORD

    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        limits = ExtendedLimit()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        handle = kernel.OpenProcess(0x0101, False, process.pid)  # PROCESS_SET_QUOTA | PROCESS_TERMINATE
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not kernel.AssignProcessToJobObject(job, handle):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.CloseHandle(handle)
        snapshot = kernel.CreateToolhelp32Snapshot(4, 0)  # TH32CS_SNAPTHREAD
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = ThreadEntry()
            entry.size = ctypes.sizeof(entry)
            more = kernel.Thread32First(snapshot, ctypes.byref(entry))
            while more:
                if entry.owner_pid == process.pid:
                    thread = kernel.OpenThread(2, False, entry.thread_id)  # THREAD_SUSPEND_RESUME
                    if not thread:
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if kernel.ResumeThread(thread) == 0xFFFFFFFF:
                            raise ctypes.WinError(ctypes.get_last_error())
                    finally:
                        kernel.CloseHandle(thread)
                    break
                more = kernel.Thread32Next(snapshot, ctypes.byref(entry))
            else:
                raise OSError("primary thread of the suspended MCP launcher was not found")
        finally:
            kernel.CloseHandle(snapshot)
    except BaseException:
        kernel.CloseHandle(job)
        raise

    def close_job() -> None:
        handles: list[int] = []
        try:
            capacity = 16
            while True:

                class ProcessIds(ctypes.Structure):
                    _fields_ = [
                        ("assigned", wintypes.DWORD),
                        ("count", wintypes.DWORD),
                        ("ids", ctypes.c_size_t * capacity),
                    ]

                members = ProcessIds()
                if kernel.QueryInformationJobObject(job, 3, ctypes.byref(members), ctypes.sizeof(members), None):
                    break
                if ctypes.get_last_error() != 234:  # ERROR_MORE_DATA
                    raise ctypes.WinError(ctypes.get_last_error())
                capacity = max(capacity * 2, members.assigned)
            for pid in members.ids[: members.count]:
                member = kernel.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
                if member:
                    handles.append(member)
                elif ctypes.get_last_error() != 87:  # ERROR_INVALID_PARAMETER: already exited
                    raise ctypes.WinError(ctypes.get_last_error())
            if not kernel.TerminateJobObject(job, 1):
                raise ctypes.WinError(ctypes.get_last_error())
            # Job accounting reaches zero before Windows releases file handles, so every member
            # process object must also be signaled before the caller reuses the files.
            deadline = time.monotonic() + 5
            for member in handles:
                remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
                if kernel.WaitForSingleObject(member, remaining_ms) != 0:
                    die("BSL Analyzer MCP owned process did not finish termination")
            accounting = Accounting()
            while True:
                if not kernel.QueryInformationJobObject(
                    job, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None
                ):
                    raise ctypes.WinError(ctypes.get_last_error())
                if accounting.active == 0:
                    break
                if time.monotonic() >= deadline:
                    die("BSL Analyzer MCP owned job did not finish termination")
                time.sleep(0.01)
        finally:
            for member in handles:
                kernel.CloseHandle(member)
            kernel.CloseHandle(job)

    return close_job


# ---------------------------------------------------------------------------------------------
# Standalone mode


def _analyze_bsl_standalone(
    source: Path, files: list[Path], report: Path, exceptions_path: Path | None = None, root: Path | None = None
) -> int:
    """Analyze a small tree with `bsl-analyzer-app analyze`, without the resident MCP server."""
    app = analyzer_app()
    if not analyzer_available(app):
        raise _not_configured(f"analyzer executable is not available: {app} (BSL_ANALYZER_APP)")
    path_root = root or source
    report.parent.mkdir(parents=True, exist_ok=True)
    version = subprocess.run([app, "--version"], capture_output=True, text=True, check=False).stdout.strip()
    directories = sorted({path.parent for path in files})
    commands = [
        [app, "analyze", "--source-dir", str(directory), "--workers", "1", "--format", "jsonl"]
        for directory in directories
    ]
    findings: list[Diagnostic] = []
    problems: list[str] = []
    outputs: list[str] = []
    for index, (directory, command) in enumerate(zip(directories, commands, strict=True)):
        expected = [path for path in files if path.parent == directory]
        expected_resolved = {path.resolve() for path in expected}
        output = report.with_name(f"{report.stem}.{index}.jsonl")
        outputs.append(str(output))
        outcome = run_analyzer(source, command, expected, output, report.with_name(f"{report.stem}.{index}.stderr.log"))
        problems.extend(outcome.problems)
        for module, finding in outcome.diagnostics:
            if module not in expected_resolved:
                continue  # A nested directory is analyzed by its own command.
            findings.append(
                _diagnostic(
                    _relative_path(module, path_root),
                    finding,
                    start_line=finding.get("start_line"),
                    start_column=finding.get("start_column"),
                    end_line=finding.get("end_line"),
                    end_column=finding.get("end_column"),
                )
            )
    findings.sort(key=lambda item: (item["path"], item["line"], item["column"], item["rule"], item["message"]))
    payload: dict[str, Any] = {
        "version": version,
        "mode": "standalone",
        "source": str(source),
        "files": [str(path) for path in files],
        "commands": commands,
        "exit_code": 1,
        "problems": problems,
        "findings": len(findings),
        "diagnostics": findings,
        "outputs": outputs,
    }
    # Write a failed report first: stale exceptions abort below and must not leave a stale success.
    _write_json_atomic(report, payload)
    analyzed = {_relative_path(path, path_root) for path in files}
    exceptions = [item for item in _load_diagnostic_exceptions(exceptions_path) if item["path"] in analyzed]
    unmatched = _unmatched_diagnostics(findings, exceptions)
    returncode = 1 if problems or unmatched else 0
    payload.update(exit_code=returncode, unexpected_findings=len(unmatched), exact_exceptions=len(exceptions))
    _write_json_atomic(report, payload)
    for problem in problems:
        print(f"BSL standalone analysis: {problem}", file=sys.stderr)
    print(f"BSL standalone report: {report}")
    return returncode


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------------------------
# Report and exact exceptions


def _one_based(value: object) -> int:
    return value + 1 if isinstance(value, int) else 0


def _diagnostic_fingerprint(diagnostic: dict[str, Any]) -> str:
    exact = {key: diagnostic[key] for key in ("path", "line", "rule", "message")}
    payload = json.dumps(exact, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _source_revision(root: Path) -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=False, capture_output=True, text=True)
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _diagnostics_report(
    root: Path,
    source: Path,
    files: list[Path],
    server_info: dict[str, Any],
    analyzer_revisions: set[int],
    findings: list[Diagnostic],
) -> dict[str, Any]:
    aggregates: dict[str, dict[str, int]] = {"byPath": {}, "byRule": {}, "bySeverity": {}}
    for finding in findings:
        for name, key in (("byPath", "path"), ("byRule", "rule"), ("bySeverity", "severity")):
            value = str(finding[key])
            aggregates[name][value] = aggregates[name].get(value, 0) + 1
    return {
        "schemaVersion": 1,
        "analyzer": {"name": server_info.get("name"), "version": server_info.get("version")},
        "sourceRevision": _source_revision(root),
        "sourceRoot": source.relative_to(root).as_posix(),
        "complete": True,
        "moduleCount": len(files),
        "analyzerRevisions": sorted(analyzer_revisions),
        "total": len(findings),
        "aggregates": {name: dict(sorted(values.items())) for name, values in aggregates.items()},
        "diagnostics": findings,
    }


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _load_diagnostic_exceptions(path: Path | None) -> list[dict[str, Any]]:
    """Read the exact exception registry: `{"schemaVersion": 1, "exceptions": [...]}`."""
    if path is None:
        return []
    try:
        payload = object_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        die(f"invalid BSL diagnostic exceptions JSON: {path}")
    result: list[dict[str, Any]] = []
    for value in object_list(payload.get("exceptions")):
        exception = object_dict(value)
        if set(exception) != EXCEPTION_FIELDS or not EXCEPTION_ID.fullmatch(str(exception.get("finding", ""))):
            die(f"invalid exact BSL diagnostic exception: {path}")
        result.append(exception)
    if len({item["fingerprint"] for item in result}) != len(result):
        die(f"duplicate BSL diagnostic exception fingerprint: {path}")
    return result


_EXACT_KEYS = ("path", "line", "rule", "message", "fingerprint")


def _unmatched_diagnostics(findings: list[Diagnostic], exceptions: list[dict[str, Any]]) -> list[Diagnostic]:
    """Return findings without an exact exception; fail when an exception no longer matches a finding."""
    expected = {tuple(item[key] for key in _EXACT_KEYS): item for item in exceptions}
    actual = {tuple(item[key] for key in _EXACT_KEYS) for item in findings}
    stale = [expected[key] for key in expected.keys() - actual]
    if stale:
        print(f"BSL analysis found {len(stale)} stale or drifted exact exceptions:", file=sys.stderr)
        for exception in sorted(stale, key=lambda item: (item["path"], item["line"], item["rule"])):
            print(
                f"- {exception['finding']}: {exception['path']}:{exception['line']}: "
                f"{exception['rule']} — {exception['message']}",
                file=sys.stderr,
            )
        die("BSL diagnostic exceptions contain stale or drifted entries")
    return [item for item in findings if tuple(item[key] for key in _EXACT_KEYS) not in expected]


def _refresh_relocated_diagnostic_exceptions(
    path: Path | None,
    all_exceptions: list[dict[str, Any]],
    scoped_exceptions: list[dict[str, Any]],
    findings: list[Diagnostic],
) -> None:
    """Move exceptions to new line numbers when only the location of the same diagnostics changed."""
    if path is None:
        die("BSL exception refresh requires an exception file")

    def identity(item: dict[str, Any]) -> tuple[str, str, str]:
        return (item["path"], item["rule"], item["message"])

    expected: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    actual: dict[tuple[str, str, str], list[Diagnostic]] = {}
    for item in scoped_exceptions:
        expected.setdefault(identity(item), []).append(item)
    for item in {tuple(finding[name] for name in _EXACT_KEYS): finding for finding in findings}.values():
        actual.setdefault(identity(item), []).append(item)
    if {key: len(value) for key, value in expected.items()} != {key: len(value) for key, value in actual.items()}:
        die("BSL exception refresh rejects changed diagnostic identities")
    replacements: dict[int, dict[str, Any]] = {}
    for key, old_group in expected.items():
        for old, new in zip(
            sorted(old_group, key=lambda item: item["line"]),
            sorted(actual[key], key=lambda item: item["line"]),
            strict=True,
        ):
            replacements[id(old)] = {"finding": old["finding"], **{name: new[name] for name in _EXACT_KEYS}}
    _write_json_atomic(
        path,
        {"schemaVersion": 1, "exceptions": [replacements.get(id(item), item) for item in all_exceptions]},
    )
    print(f"BSL exception locations refreshed: {len(replacements)}", flush=True)
