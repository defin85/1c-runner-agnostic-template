from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


WINDOWS = os.name == "nt"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent


class CommandError(RuntimeError):
    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def die(message: str, exit_code: int = 1) -> "CommandError":
    raise CommandError(message, exit_code)


def log(message: str, script_name: str | None = None) -> None:
    label = script_name or "python-cli"
    print(f"[{label}] {message}")


def project_root() -> Path:
    return PROJECT_ROOT


def canonical_path(value: str | os.PathLike[str]) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def ensure_dir(path: str | os.PathLike[str]) -> Path:
    resolved = canonical_path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def timestamp_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def require_command(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        die(f"command not found: {name}")
    return resolved


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        die(f"required env var is not set: {name}")
    return value


def read_text(path: str | os.PathLike[str]) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str | os.PathLike[str], content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")


def write_json(path: str | os.PathLike[str], payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def read_json(path: str | os.PathLike[str]) -> object:
    with Path(path).open("r", encoding="utf-8") as stream:
        return json.load(stream)


def relative_repo_path(path: str | os.PathLike[str]) -> str:
    resolved = canonical_path(path)
    try:
        rel = resolved.relative_to(project_root())
    except ValueError:
        die(f"path is outside repository root: {resolved}")
    return rel.as_posix()


def repo_path(*parts: str) -> Path:
    return project_root().joinpath(*parts)


def is_repo_relative_token(token: str) -> bool:
    prefixes = (
        "./",
        "scripts/",
        "tests/",
        "features/",
        "src/",
        "automation/",
        "docs/",
        "env/",
        ".agents/",
        ".codex/",
        ".claude/",
        "Makefile",
    )
    return token.startswith(prefixes)


def normalize_repo_relative(token: str) -> Path:
    candidate = token
    if candidate.startswith("./"):
        candidate = candidate[2:]
    path = canonical_path(project_root() / candidate)
    try:
        path.relative_to(project_root())
    except ValueError:
        die(f"path escapes repository root: {token}")
    return path


def same_text(a: str | os.PathLike[str], b: str | os.PathLike[str]) -> bool:
    path_a = Path(a)
    path_b = Path(b)
    return path_a.exists() and path_b.exists() and path_a.read_bytes() == path_b.read_bytes()


def list_files(root: str | os.PathLike[str], max_depth: int | None = None) -> list[Path]:
    base = Path(root)
    if not base.exists():
        return []
    items: list[Path] = []
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        if max_depth is not None:
            try:
                depth = len(path.relative_to(base).parts)
            except ValueError:
                continue
            if depth > max_depth:
                continue
        items.append(path)
    return sorted(items)


def list_dirs(root: str | os.PathLike[str], max_depth: int | None = None) -> list[Path]:
    base = Path(root)
    if not base.exists():
        return []
    items: list[Path] = []
    for path in base.rglob("*"):
        if not path.is_dir():
            continue
        if max_depth is not None:
            try:
                depth = len(path.relative_to(base).parts)
            except ValueError:
                continue
            if depth > max_depth:
                continue
        items.append(path)
    return sorted(items)


def temp_dir(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix, dir=os.environ.get("TMPDIR") or None))


def command_display(command: Sequence[str]) -> str:
    if WINDOWS:
        return subprocess.list2cmdline(list(command))
    return " ".join(shlex_quote(part) for part in command)


def shlex_quote(value: str) -> str:
    if WINDOWS:
        return value
    import shlex

    return shlex.quote(value)


@dataclass
class ProcessResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


def run_process(
    command: Sequence[str],
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: dict[str, str] | None = None,
    check: bool = False,
    capture_output: bool = True,
    text: bool = True,
) -> ProcessResult:
    final_env = os.environ.copy()
    if env:
        final_env.update(env)
    completed = subprocess.run(
        list(command),
        cwd=str(cwd) if cwd else None,
        env=final_env,
        check=False,
        capture_output=capture_output,
        text=text,
    )
    result = ProcessResult(
        args=list(command),
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
    if check and result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        message = stderr or stdout or f"command failed: {command_display(command)}"
        die(message, result.returncode)
    return result


def run_logged(
    command: Sequence[str],
    *,
    stdout_path: str | os.PathLike[str],
    stderr_path: str | os.PathLike[str],
    cwd: str | os.PathLike[str] | None = None,
    env: dict[str, str] | None = None,
) -> int:
    Path(stdout_path).parent.mkdir(parents=True, exist_ok=True)
    Path(stderr_path).parent.mkdir(parents=True, exist_ok=True)
    final_env = os.environ.copy()
    if env:
        final_env.update(env)
    with Path(stdout_path).open("w", encoding="utf-8", newline="\n") as stdout_stream:
        with Path(stderr_path).open("w", encoding="utf-8", newline="\n") as stderr_stream:
            process = subprocess.run(
                list(command),
                cwd=str(cwd) if cwd else None,
                env=final_env,
                stdout=stdout_stream,
                stderr=stderr_stream,
                text=True,
                check=False,
            )
    return process.returncode


def run_git(args: Sequence[str], *, cwd: str | os.PathLike[str] | None = None, check: bool = False) -> ProcessResult:
    return run_process(["git", "-c", "core.quotepath=false", *args], cwd=cwd, check=check)


def coalesce(*values: str | None) -> str:
    for value in values:
        if value:
            return value
    return ""


def trim(value: str) -> str:
    return value.strip()


def unique_preserve_order(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
