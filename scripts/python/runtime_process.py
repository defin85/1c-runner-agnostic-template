from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .runtime_errors import CommandError


@dataclass(slots=True)
class ProcessResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


def resolve_executable(
    executable: str,
    *,
    windows: bool | None = None,
    search_path: str | None = None,
    pathext: str | None = None,
) -> str:
    """Resolve an executable without invoking a shell or a PowerShell shim."""
    is_windows = os.name == "nt" if windows is None else windows
    candidate = Path(executable).expanduser()
    has_path = candidate.is_absolute() or candidate.parent != Path(".")
    if has_path:
        if not candidate.is_file():
            raise CommandError(f"configured executable not found: {candidate}")
        if is_windows and candidate.suffix.lower() == ".ps1":
            raise CommandError(f"PowerShell shim is not an executable argv target: {candidate}")
        return str(candidate.resolve(strict=False))

    if not is_windows:
        resolved = shutil.which(executable, path=search_path)
        if not resolved:
            raise CommandError(f"command not found: {executable}")
        return resolved

    path_value = search_path if search_path is not None else os.environ.get("PATH", "")
    configured_extensions = pathext if pathext is not None else os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD")
    extensions = [item.lower() for item in configured_extensions.split(";") if item]
    # npm commonly installs both npm.cmd and npm.ps1. A .ps1 shim is deliberately
    # never selected because its execution depends on the user's ExecutionPolicy.
    extensions = [item for item in extensions if item != ".ps1"]
    suffix = candidate.suffix.lower()
    names = [executable] if suffix else [executable + extension for extension in extensions]
    for directory in path_value.split(os.pathsep):
        if not directory:
            continue
        for name in names:
            resolved = Path(directory) / name
            if resolved.is_file():
                return str(resolved.resolve(strict=False))
    raise CommandError(f"command not found: {executable}")


def run_process(
    command: Sequence[str],
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: dict[str, str] | None = None,
    check: bool = False,
    capture_output: bool = True,
    text: bool = True,
    timeout: float | None = None,
    input_text: str | None = None,
) -> ProcessResult:
    if not command:
        raise CommandError("process command must not be empty")
    argv = [str(item) for item in command]
    final_env = os.environ.copy()
    if env:
        final_env.update(env)
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            env=final_env,
            check=False,
            capture_output=capture_output,
            text=text,
            encoding="utf-8" if text else None,
            errors="replace" if text else None,
            timeout=timeout,
            input=input_text,
        )
        result = ProcessResult(argv, completed.returncode, completed.stdout or "", completed.stderr or "")
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        result = ProcessResult(argv, 124, stdout, stderr, timed_out=True)
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        if result.timed_out:
            detail = detail or f"command timed out after {timeout} seconds"
        raise CommandError(detail or f"command failed with exit code {result.returncode}", result.returncode)
    return result


def run_logged(
    command: Sequence[str],
    *,
    stdout_path: str | os.PathLike[str],
    stderr_path: str | os.PathLike[str],
    cwd: str | os.PathLike[str] | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> int:
    stdout_target = Path(stdout_path)
    stderr_target = Path(stderr_path)
    stdout_target.parent.mkdir(parents=True, exist_ok=True)
    stderr_target.parent.mkdir(parents=True, exist_ok=True)
    final_env = os.environ.copy()
    if env:
        final_env.update(env)
    try:
        with stdout_target.open("w", encoding="utf-8", newline="\n") as stdout_stream:
            with stderr_target.open("w", encoding="utf-8", newline="\n") as stderr_stream:
                completed = subprocess.run(
                    [str(item) for item in command],
                    cwd=str(cwd) if cwd else None,
                    env=final_env,
                    stdout=stdout_stream,
                    stderr=stderr_stream,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                    timeout=timeout,
                )
        return completed.returncode
    except subprocess.TimeoutExpired:
        with stderr_target.open("a", encoding="utf-8", newline="\n") as stderr_stream:
            stderr_stream.write(f"process timed out after {timeout} seconds\n")
        return 124
