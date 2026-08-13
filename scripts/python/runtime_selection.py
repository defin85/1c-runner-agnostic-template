from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .runtime_errors import CommandError


def normalize_repo_relative_path(value: str) -> str:
    candidate = value.replace("\\", "/").strip()
    if not candidate or candidate.startswith("/") or (len(candidate) >= 2 and candidate[1] == ":"):
        raise CommandError(f"repository path must be relative: {value}")
    stack: list[str] = []
    for segment in candidate.split("/"):
        if segment in {"", "."}:
            continue
        if segment == "..":
            if not stack:
                raise CommandError(f"repository path escapes root: {value}")
            stack.pop()
            continue
        stack.append(segment)
    if not stack:
        raise CommandError(f"repository path must point inside root: {value}")
    return "/".join(stack)


@dataclass(frozen=True, slots=True)
class SourcePathSelection:
    repo_path: str
    relative_path: str | None
    reason: str | None


def select_source_path(
    repo_root: Path,
    source_dir: str,
    repo_path: str,
    *,
    deleted: bool = False,
) -> SourcePathSelection:
    source = normalize_repo_relative_path(source_dir)
    candidate = normalize_repo_relative_path(repo_path)
    if candidate == source:
        return SourcePathSelection(candidate, None, "not-a-source-file")
    prefix = f"{source}/"
    if not candidate.startswith(prefix):
        return SourcePathSelection(candidate, None, "outside-source-tree")
    if deleted or not (repo_root / Path(candidate)).is_file():
        return SourcePathSelection(candidate, None, "missing-or-deleted")
    return SourcePathSelection(candidate, candidate[len(prefix) :], None)
