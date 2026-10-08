"""Shared, filesystem-backed storage for long-running local artifacts outside the checkout.

The storage keeps one passport per run in ``<root>/runs/<id>.json`` with status ``active``, ``success``
or ``failed`` and a pin flag. ``begin`` checks the byte budget and the free space (and, on Linux, the
inode budget and free inodes) under one storage lock, counting the reserve of active runs, and refuses
before the run is created. Successful unpinned runs lose their declared temporary directories.

The lock is the template ``runtime_lock.ResourceLock`` (exclusive create of a lock file with stale owner
detection), so the module works on Linux and Windows. Free space comes from ``os.statvfs`` on POSIX and
from ``shutil.disk_usage`` on Windows, where inode limits do not apply.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .common import project_root
from .runtime_errors import CommandError
from .runtime_lock import ResourceLock

WINDOWS = os.name == "nt"
_RUNS_DIR = "runs"
_LOCK_FILE = ".storage.lock"
_DEFAULT_MAX_BYTES = 200 * 1024**3
_DEFAULT_MIN_FREE_BYTES = 20 * 1024**3
_DEFAULT_MAX_INODES = 2_000_000
_DEFAULT_MIN_FREE_INODES = 10_000
_DEFAULT_RETENTION_DAYS = 7
_DEFAULT_LOCK_TIMEOUT_SECONDS = 300

Passport = dict[str, Any]


def repository_root() -> Path:
    return Path(os.path.abspath(project_root()))


def default_storage_root(repo: Path | None = None) -> Path:
    """``<repo>-artifacts`` next to the checkout."""
    repo = repo or repository_root()
    return repo.parent / f"{repo.name}-artifacts"


def storage_root() -> Path:
    """Return the shared artifact root, always outside this checkout."""
    repo = repository_root()
    configured = os.environ.get("ONEC_ARTIFACT_ROOT")
    root = Path(configured).expanduser() if configured else default_storage_root(repo)
    if configured and not root.is_absolute():
        raise ValueError("ONEC_ARTIFACT_ROOT must be absolute")
    root = Path(os.path.abspath(root))
    _reject_symlink_ancestors(root)
    if root == Path(root.anchor) or root == repo or root.is_relative_to(repo):
        raise ValueError("ONEC_ARTIFACT_ROOT must be outside the repository checkout")
    return root


def _reject_symlink_ancestors(path: Path) -> None:
    path = Path(os.path.abspath(path))
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            if stat.S_ISLNK(current.lstat().st_mode):
                raise ValueError(f"path contains symlink: {current}")
        except FileNotFoundError:
            break


def _runs_dir() -> Path:
    path = storage_root() / _RUNS_DIR
    _reject_symlink_ancestors(path)
    return path


def _lock_timeout() -> float:
    return float(_integer_env("ONEC_ARTIFACT_LOCK_TIMEOUT_SECONDS", _DEFAULT_LOCK_TIMEOUT_SECONDS))


@contextmanager
def _locked() -> Iterator[Path]:
    root = storage_root()
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / _LOCK_FILE
    _reject_symlink_ancestors(lock_path)
    # The token keeps owners of threads in one process distinct for the release check.
    owner = {"pid": os.getpid(), "operation": "artifact-storage", "token": uuid.uuid4().hex}
    with ResourceLock(lock_path, owner, timeout=_lock_timeout()):
        yield root


def _passports() -> list[tuple[Path, Passport]]:
    directory = _runs_dir()
    if not directory.exists():
        return []
    result: list[tuple[Path, Passport]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read artifact passport: {path}") from exc
        if not isinstance(data, dict) or data.get("id") != path.stem:
            raise ValueError(f"invalid artifact passport: {path}")
        result.append((path, data))
    return result


def _write_json(path: Path, data: Passport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".passport-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _allocated_bytes(info: os.stat_result) -> int:
    if not stat.S_ISREG(info.st_mode):
        return 0
    blocks = getattr(info, "st_blocks", None)
    # Windows has no st_blocks: the logical size is the closest available measure.
    return blocks * 512 if isinstance(blocks, int) else info.st_size


def _tree_usage(path: Path, seen: set[tuple[int, int]] | None = None) -> tuple[int, int]:
    """Count regular-file bytes and filesystem entries without following links."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return 0, 0
    seen = seen if seen is not None else set()
    inode = (info.st_dev, info.st_ino)
    if info.st_ino and inode in seen:
        return 0, 0
    seen.add(inode)
    mode = info.st_mode
    if stat.S_ISLNK(mode):
        return 0, 1
    if not stat.S_ISDIR(mode):
        return _allocated_bytes(info), 1
    size, inodes = 0, 1
    for child in list(path.iterdir()):
        child_size, child_inodes = _tree_usage(child, seen)
        size += child_size
        inodes += child_inodes
    return size, inodes


def _usage_and_reservations(passports: list[tuple[Path, Passport]]) -> tuple[int, int, int, int]:
    root = storage_root()
    seen: set[tuple[int, int]] = set()
    total_bytes, total_inodes = _tree_usage(root, seen)
    roots: list[Path] = []
    for _, data in passports:
        run_path = Path(str(data.get("run_root", "")))
        if not run_path.is_absolute():
            continue
        run_path = Path(os.path.abspath(run_path))
        _reject_symlink_ancestors(run_path)
        if run_path == root or run_path.is_relative_to(root):
            continue
        if run_path not in roots:
            roots.append(run_path)
    roots = [path for path in roots if not any(path != other and path.is_relative_to(other) for other in roots)]
    for run_path in roots:
        size, inodes = _tree_usage(run_path, seen)
        total_bytes += size
        total_inodes += inodes

    reserved_bytes = reserved_inodes = 0
    for _, data in passports:
        if data.get("status") != "active":
            continue
        run_path = Path(str(data.get("run_root", "")))
        _reject_symlink_ancestors(run_path)
        used_bytes, used_inodes = _tree_usage(run_path)
        reserved_bytes += max(0, int(data.get("reserve_bytes", 0)) - used_bytes)
        reserved_inodes += max(0, int(data.get("reserve_inodes", 0)) - used_inodes)
    return total_bytes, total_inodes, reserved_bytes, reserved_inodes


def _integer_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if number < 0:
        raise ValueError(f"{name} cannot be negative")
    return number


def inode_limits_apply() -> bool:
    return not WINDOWS


def free_space(path: Path) -> tuple[int, int | None]:
    """Return available bytes and inodes; inodes are ``None`` where the platform has no such limit."""
    if WINDOWS or not hasattr(os, "statvfs"):
        return shutil.disk_usage(path).free, None
    free = os.statvfs(path)
    return free.f_bavail * free.f_frsize, free.f_favail


def _filesystem_paths(target_path: Path | None = None) -> list[Path]:
    paths = [storage_root()]
    if target_path is not None:
        paths.append(Path(os.path.abspath(target_path)))
    db_path = os.environ.get("ONEC_ARTIFACT_DB_PATH")
    if db_path:
        paths.append(Path(db_path).expanduser().resolve())
    return paths


def _check_capacity(
    add_bytes: int,
    add_inodes: int,
    passports: list[tuple[Path, Passport]],
    target_path: Path | None = None,
) -> None:
    used_bytes, used_inodes, reserved_bytes, reserved_inodes = _usage_and_reservations(passports)
    projected_bytes = used_bytes + reserved_bytes + add_bytes
    max_bytes = _integer_env("ONEC_ARTIFACT_MAX_BYTES", _DEFAULT_MAX_BYTES)
    if projected_bytes > max_bytes:
        raise OSError(f"artifact byte budget exceeded: {projected_bytes} > {max_bytes}")
    check_inodes = inode_limits_apply()
    if check_inodes:
        projected_inodes = used_inodes + reserved_inodes + add_inodes
        max_inodes = _integer_env("ONEC_ARTIFACT_MAX_INODES", _DEFAULT_MAX_INODES)
        if projected_inodes > max_inodes:
            raise OSError(f"artifact inode budget exceeded: {projected_inodes} > {max_inodes}")

    min_free_bytes = _integer_env("ONEC_ARTIFACT_MIN_FREE_BYTES", _DEFAULT_MIN_FREE_BYTES)
    min_free_inodes = _integer_env("ONEC_ARTIFACT_MIN_FREE_INODES", _DEFAULT_MIN_FREE_INODES)
    for path in _filesystem_paths(target_path):
        probe = path
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        available_bytes, available_inodes = free_space(probe)
        if available_bytes - reserved_bytes - add_bytes < min_free_bytes:
            raise OSError(f"insufficient free bytes on {probe}")
        if check_inodes and available_inodes is not None:
            if available_inodes - reserved_inodes - add_inodes < min_free_inodes:
                raise OSError(f"insufficient free inodes on {probe}")


def _normalized_paths(paths: list[Path] | None, run_root: Path) -> list[str]:
    result: list[str] = []
    root = Path(os.path.abspath(run_root))
    for path in paths or []:
        absolute = path.expanduser()
        if not absolute.is_absolute():
            absolute = root / absolute
        absolute = Path(os.path.abspath(absolute))
        _scratch_target(str(absolute), root)
        result.append(str(absolute))
    return result


def begin_run(
    kind: str,
    run_root: Path,
    reserve_bytes: int = 0,
    reserve_inodes: int = 0,
    scratch: list[Path] | None = None,
) -> str:
    """Create a run passport and reserve shared capacity under one lock."""
    if not kind.strip():
        raise ValueError("kind cannot be empty")
    if reserve_bytes < 0 or reserve_inodes < 0:
        raise ValueError("reservations cannot be negative")
    run_root = Path(os.path.abspath(run_root.expanduser()))
    _reject_symlink_ancestors(run_root)
    if run_root == Path(run_root.anchor) or run_root == repository_root():
        raise ValueError("run_root cannot be the filesystem root or repository root")
    run_id = uuid.uuid4().hex
    with _locked():
        passports = _passports()
        existed = run_root.exists()
        candidate: Passport = {
            "id": run_id,
            "run_root": str(run_root),
            "status": "active",
            "reserve_bytes": reserve_bytes,
            "reserve_inodes": reserve_inodes,
        }
        passport: Passport = {
            "id": run_id,
            "kind": kind,
            "run_root": str(run_root),
            "created_at": time.time(),
            "status": "active",
            "reserve_bytes": reserve_bytes,
            "reserve_inodes": reserve_inodes,
            "created_root": not existed,
            "pinned": False,
            "scratch": _normalized_paths(scratch, run_root),
        }
        passport_bytes = len(json.dumps(passport, ensure_ascii=False, sort_keys=True).encode("utf-8")) + 1
        _check_capacity(
            passport_bytes,
            1 + int(not existed),
            [*passports, (Path(), candidate)],
            target_path=run_root,
        )
        run_root.mkdir(parents=True, exist_ok=True)
        _write_json(_runs_dir() / f"{run_id}.json", passport)
    return run_id


def _scratch_target(value: str, run_root: Path) -> Path:
    target = Path(value)
    if not target.is_absolute():
        target = run_root / target
    root = Path(os.path.abspath(run_root))
    _reject_symlink_ancestors(root)
    target = Path(os.path.abspath(target))
    if target == root or not target.is_relative_to(root):
        raise ValueError(f"scratch path must be a child of run root: {target}")
    current = root
    for part in target.relative_to(root).parts:
        current = current / part
        try:
            if stat.S_ISLNK(current.lstat().st_mode):
                raise ValueError(f"scratch path contains symlink: {current}")
        except FileNotFoundError:
            break
    return target


def _ensure_scratch_not_shared(passport: Passport, target: Path) -> None:
    for _, other in _passports():
        if other.get("id") == passport.get("id") or not (other.get("status") == "active" or other.get("pinned")):
            continue
        other_root = Path(os.path.abspath(str(other.get("run_root", ""))))
        if target == other_root or target in other_root.parents or other_root in target.parents:
            raise ValueError(f"scratch overlaps protected run {other['id']}: {target}")


def _reject_mountpoints(path: Path) -> None:
    for current, directories, _ in os.walk(path, topdown=True, followlinks=False):
        current_path = Path(current)
        if os.path.ismount(current_path):
            raise ValueError(f"scratch contains mount point: {current_path}")
        directories[:] = [name for name in directories if not (current_path / name).is_symlink()]


def _make_writable_and_retry(function: Callable[..., Any], path: str, _error: BaseException) -> None:
    # Windows refuses to delete read-only files; clear the flag and retry once.
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    function(path)


def _remove_path(target: Path) -> None:
    if target.is_dir() and not target.is_symlink():
        shutil.rmtree(target, onexc=_make_writable_and_retry)
    else:
        if WINDOWS:
            os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
        target.unlink()


def _remove_scratch(passport: Passport) -> list[str]:
    run_root = Path(passport["run_root"])
    removed: list[str] = []
    for value in passport.get("scratch", []):
        target = _scratch_target(value, run_root)
        _ensure_scratch_not_shared(passport, target)
        if not target.exists():
            continue
        _reject_mountpoints(target)
        _remove_path(target)
        removed.append(str(target))
    passport["scratch"] = []
    return removed


def finish_run(run_id: str, status: str, scratch: list[Path] | None = None, pinned: bool = False) -> None:
    passport_path = _passport_path(run_id)
    if status not in {"success", "failed"}:
        raise ValueError("status must be 'success' or 'failed'")
    with _locked():
        passport = json.loads(passport_path.read_text(encoding="utf-8"))
        if passport.get("status") != "active":
            raise ValueError(f"run is already terminal: {run_id}")
        passport["status"] = status
        passport["finished_at"] = time.time()
        passport["pinned"] = bool(pinned)
        if scratch is not None:
            passport["scratch"] = _normalized_paths(scratch, Path(passport["run_root"]))
        if status == "success" and not pinned:
            _remove_scratch(passport)
        _write_json(passport_path, passport)


def set_pinned(run_id: str, pinned: bool) -> None:
    passport_path = _passport_path(run_id)
    with _locked():
        passport = json.loads(passport_path.read_text(encoding="utf-8"))
        passport["pinned"] = bool(pinned)
        _write_json(passport_path, passport)


def _passport_path(run_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise ValueError("run id must be a 32-character lowercase UUID hex value")
    return _runs_dir() / f"{run_id}.json"


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cache_file(source: Path) -> Path:
    """Copy a file into a content-addressed, read-only cache without hardlinks."""
    source = source.expanduser().resolve(strict=True)
    if not source.is_file():
        raise ValueError(f"cache source is not a file: {source}")
    digest = _digest_file(source)
    target_dir = storage_root() / "cache" / digest[:2]
    target = target_dir / f"{digest}{source.suffix}"
    with _locked():
        _reject_symlink_ancestors(target_dir)
        try:
            if stat.S_ISLNK(target.lstat().st_mode):
                raise ValueError(f"cache target is a symlink: {target}")
        except FileNotFoundError:
            pass
        if target.exists() and _digest_file(target) == digest:
            target.chmod(0o444)
            return target
        _check_capacity(source.stat().st_size, 1, _passports())
        target_dir.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".cache-", dir=target_dir)
        os.close(fd)
        try:
            shutil.copyfile(source, temporary)
            if _digest_file(Path(temporary)) != digest:
                raise OSError("source changed while caching")
            os.chmod(temporary, 0o444)
            if target.exists():
                # A corrupted read-only copy cannot be replaced on Windows until it is writable.
                target.chmod(0o644)
            os.replace(temporary, target)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
    return target


def prune(apply: bool = False) -> dict[str, Any]:
    now = time.time()
    retention = _integer_env("ONEC_ARTIFACT_RETENTION_DAYS", _DEFAULT_RETENTION_DAYS) * 86400
    eligible: list[dict[str, Any]] = []
    removed: list[str] = []
    errors: list[str] = []
    protected = 0
    with _locked():
        for passport_path, passport in _passports():
            if passport.get("status") == "active" or passport.get("pinned"):
                protected += 1
                continue
            if now - float(passport.get("finished_at", now)) < retention:
                continue
            if not passport.get("scratch"):
                continue
            for value in passport["scratch"]:
                try:
                    target = _scratch_target(value, Path(passport["run_root"]))
                    _ensure_scratch_not_shared(passport, target)
                    if not target.exists():
                        continue
                    _reject_mountpoints(target)
                    size, inodes = _tree_usage(target)
                    eligible.append({"run_id": passport["id"], "path": str(target), "bytes": size, "inodes": inodes})
                except (OSError, ValueError) as exc:
                    errors.append(f"{passport['id']}: {exc}")
            if apply:
                try:
                    removed.extend(_remove_scratch(passport))
                    _write_json(passport_path, passport)
                except (OSError, ValueError) as exc:
                    errors.append(f"{passport['id']}: {exc}")
    return {"eligible": eligible, "removed": removed, "protected": protected, "errors": errors}


def status() -> dict[str, Any]:
    passports = _passports()
    used_bytes, used_inodes, reserved_bytes, reserved_inodes = _usage_and_reservations(passports)
    return {
        "root": str(storage_root()),
        "runs": len(passports),
        "active": sum(data.get("status") == "active" for _, data in passports),
        "pinned": sum(bool(data.get("pinned")) for _, data in passports),
        "used_bytes": used_bytes,
        "used_inodes": used_inodes,
        "reserved_bytes": reserved_bytes,
        "reserved_inodes": reserved_inodes,
        "inode_limits": inode_limits_apply(),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="artifact-storage", description=(__doc__ or "").splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("root", help="print the storage root")
    begin = subparsers.add_parser("begin", help="reserve capacity and create an active run passport")
    begin.add_argument("--kind", required=True)
    begin.add_argument("--run-root", type=Path, required=True)
    begin.add_argument("--reserve-bytes", type=int, default=0)
    begin.add_argument("--reserve-inodes", type=int, default=0)
    begin.add_argument("--scratch", type=Path, action="append")
    finish = subparsers.add_parser("finish", help="mark a run as success or failed")
    finish.add_argument("--id", required=True)
    finish.add_argument("--status", choices=("success", "failed"), required=True)
    finish.add_argument("--scratch", type=Path, action="append")
    finish.add_argument("--pin", action="store_true")
    pin = subparsers.add_parser("pin", help="pin or unpin a run")
    pin.add_argument("--id", required=True)
    pin.add_argument("--off", action="store_true")
    cache = subparsers.add_parser("cache-file", help="copy a file into the read-only content cache")
    cache.add_argument("path", type=Path)
    subparsers.add_parser("status", help="print usage and reservations as JSON")
    prune_parser = subparsers.add_parser("prune", help="list (or remove with --apply) expired temporary directories")
    prune_parser.add_argument("--apply", action="store_true")
    return parser


def run_artifact_storage(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "root":
            print(storage_root())
        elif args.command == "begin":
            print(begin_run(args.kind, args.run_root, args.reserve_bytes, args.reserve_inodes, args.scratch))
        elif args.command == "finish":
            finish_run(args.id, args.status, args.scratch, args.pin)
        elif args.command == "pin":
            set_pinned(args.id, not args.off)
        elif args.command == "cache-file":
            print(cache_file(args.path))
        elif args.command == "status":
            print(json.dumps(status(), ensure_ascii=False, sort_keys=True))
        else:
            result = prune(args.apply)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 1 if result["errors"] else 0
    except (OSError, ValueError) as error:
        raise CommandError(f"artifact-storage: {error}") from error
    return 0
