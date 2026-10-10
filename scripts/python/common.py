from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

from .runtime_atomic import atomic_write_json, atomic_write_text
from .runtime_errors import CommandError
from .runtime_process import ProcessResult, run_process

WINDOWS = os.name == "nt"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent


def die(message: str, exit_code: int = 1) -> NoReturn:
    raise CommandError(message, exit_code)


def log(message: str, script_name: str | None = None) -> None:
    label = script_name or "python-cli"
    print(f"[{label}] {message}")


def project_root() -> Path:
    return PROJECT_ROOT


_CHANGE_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")


def resolve_openspec_path(path: Path, *, root: Path = PROJECT_ROOT) -> Path:
    """Locate evidence of an archived OpenSpec change without rewriting its recorded path.

    Evidence records keep the path `openspec/changes/<change>/...` they had while the change was
    active. After `openspec archive` the change lives in `openspec/changes/archive/<date>-<change>/`;
    this returns that location when the recorded path no longer exists. Any other path is returned
    unchanged. Two archived copies of one change are ambiguous and raise `ValueError`.
    """
    if path.exists() or path.is_symlink() or not path.is_relative_to(root):
        return path
    parts = path.relative_to(root).parts
    if (
        len(parts) < 3
        or parts[:2] != ("openspec", "changes")
        or parts[2] == "archive"
        or ".." in parts
        or not _CHANGE_NAME.fullmatch(parts[2])
    ):
        return path
    active = root.joinpath(*parts[:3])
    if active.exists() or active.is_symlink():
        return path
    archive = root / "openspec" / "changes" / "archive"
    matches = list(archive.glob(f"[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-{parts[2]}"))
    if len(matches) > 1:
        raise ValueError(f"ambiguous archived change: {parts[2]}")
    return matches[0].joinpath(*parts[3:]) if matches else path


def canonical_path(value: str | os.PathLike[str]) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def ensure_dir(path: str | os.PathLike[str]) -> Path:
    resolved = canonical_path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def timestamp_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    atomic_write_text(path, content)


def write_json(path: str | os.PathLike[str], payload: object) -> None:
    atomic_write_json(path, payload)


def read_json(path: str | os.PathLike[str]) -> object:
    with Path(path).open("r", encoding="utf-8") as stream:
        return json.load(stream)


def object_dict(value: object) -> dict[str, object]:
    """Narrow parsed JSON to a mapping with string keys; anything else becomes an empty dict."""
    if not isinstance(value, dict):
        return {}
    return {key: item for key, item in value.items() if isinstance(key, str)}


def object_list(value: object) -> list[object]:
    """Narrow parsed JSON to a list; anything else becomes an empty list."""
    return list(value) if isinstance(value, list) else []


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
