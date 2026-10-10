"""KD rules cycle: shared helpers (errors, JSON, hashes, paths, profile lock, observed commands)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from scripts.python.runtime_errors import CommandError
from scripts.python.runtime_lock import ResourceLock
from scripts.python.runtime_observation import ObservationRequest, run_observed

ROOT = Path(__file__).resolve().parents[2]

STAGES = ("doctor", "reset", "build", "load", "run", "verify")
# Direct dependencies of every stage. `build` reads only files, so it does not wait for the bases.
STAGE_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "doctor": (),
    "reset": ("doctor",),
    "build": (),
    "load": ("reset", "build"),
    "run": ("load",),
    "verify": ("run",),
}
# Stages that change the expendable bases.
MUTATING_STAGES = frozenset({"reset", "load", "run"})
RETRY_MODES = ("probe-and-reuse", "idempotent-retry", "fresh-generation-required")
ROLES = ("source", "target")
BUILD_RULES = "build-rules"
RESULT_STATUSES = ("in-progress", "failed", "rules-built", "workbench-run-passed", "workbench-ready")
STATE_SCHEMA_VERSION = 2
RESULT_SCHEMA_VERSION = 1

DEFAULT_PROFILE = "migration/kd21/profiles/local.json"
DEFAULT_SCENARIO = "migration/kd21/scenarios/technical-workbench/scenario.json"
MODULE_HINT = (
    "enable the module with `make optional-module-init MODULE=kd21-migration` "
    "(Windows: `./make.ps1 optional-module-init kd21-migration`) and create the profile from "
    "migration/kd21/profiles/local.example.json; see docs/agent/kd21-rules-workbench-runbook.md"
)
DEFAULT_RESET_COMMAND = (
    "bash",
    "tests/golden/restore.sh",
    "--profile",
    "{runtimeProfile}",
    "--target",
    "{target}",
    "--snapshot",
    "{snapshot}",
)
_PROGRESS = re.compile(r"[A-Za-z0-9_.:-]{1,64}\Z")
_PLACEHOLDER = re.compile(r"\{([A-Za-z]+)\}")
_SCRIPT_ARGUMENT = re.compile(r"[\w.-]+(?:[/\\][\w.-]+)+\.(?:py|sh|ps1)")


class CycleError(RuntimeError):
    """A refusal or failure with a message for the operator."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise CycleError(f"file not found: {path}") from None
    except (OSError, ValueError) as error:
        raise CycleError(f"invalid JSON {path}: {error}") from None
    if not isinstance(value, dict):
        raise CycleError(f"JSON root must be an object: {path}")
    return value


def atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(
        candidate
        for candidate in path.rglob("*")
        if candidate.is_file() and "__pycache__" not in candidate.parts and candidate.suffix not in {".pyc", ".pyo"}
    ):
        digest.update(item.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256(item)))
    return digest.hexdigest()


def path_sha256(path: Path) -> str:
    if path.is_file():
        return sha256(path)
    if path.is_dir():
        return tree_sha256(path)
    return "missing"


def canonical_json_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def project_path(value: str, *, base: Path = ROOT) -> Path:
    """Resolve a profile or scenario path: absolute as given, relative against `base`."""
    path = Path(value)
    return path if path.is_absolute() else base / path


def write_progress(path: Path, value: str) -> None:
    if not _PROGRESS.fullmatch(value):
        raise CycleError(f"invalid progress value: {value}")
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(value + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def lock_directory(profile: Mapping[str, Any]) -> Path:
    configured = profile.get("lockDirectory")
    if configured:
        return Path(str(configured))
    return Path(tempfile.gettempdir()) / "kd-rules-cycle-locks"


@contextmanager
def profile_lock(profile: Mapping[str, Any], run_root: Path) -> Iterator[Path]:
    """Hold the profile lock without waiting: a second run of the same profile fails at once."""
    path = lock_directory(profile) / f"{profile['profileId']}.lock"
    lock = ResourceLock(path, {"pid": os.getpid(), "runRoot": str(run_root)}, timeout=0.0)
    try:
        lock.acquire()
    except CommandError:
        owner = ""
        try:
            owner = path.read_text(encoding="utf-8").strip()
        except OSError:
            pass
        raise CycleError(f"profile is already running: {profile['profileId']} (lock {path}; owner {owner})") from None
    try:
        yield path
    finally:
        lock.release()


def render_command(template: Sequence[str], values: Mapping[str, str]) -> list[str]:
    """Substitute `{name}` placeholders; an unknown placeholder is an error, not an empty string."""
    rendered: list[str] = []
    for index, item in enumerate(template):

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in values:
                raise CycleError(f"command placeholder is unknown: {{{key}}}")
            return values[key]

        if index == 0 and item == "{python}":
            rendered.append(sys.executable)
            continue
        text = _PLACEHOLDER.sub(replace, item)
        if index == 0:
            if not Path(text).is_absolute() and ("/" in text or "\\" in text):
                text = str(ROOT / text)
            elif shutil.which(text) is None and not Path(text).exists():
                raise CycleError(f"command is not available: {text}")
        elif _SCRIPT_ARGUMENT.fullmatch(text) and not Path(text).is_absolute():
            # A project script named by a relative path must exist before any base is touched.
            if not (ROOT / text).is_file():
                raise CycleError(f"command file not found: {text}")
            text = str(ROOT / text)
        rendered.append(text)
    return rendered


def run_observed_stage(
    *,
    stage: str,
    target: str,
    run_root: Path,
    stage_root: Path,
    command: Sequence[str],
    environment: Mapping[str, str],
    limits: Mapping[str, Any],
    expect_result: bool,
) -> dict[str, Any]:
    """Run one blocking command through the shared observation adapter.

    The adapter stops the command when its progress file stops changing for
    `limits.runtimeStageTimeoutSeconds`; the executor keeps no waiting loop of its own.
    """
    stage_root.mkdir(parents=True, exist_ok=True)
    progress = stage_root / "progress.txt"
    result_file = stage_root / "result.json"
    progress.unlink(missing_ok=True)
    result_file.unlink(missing_ok=True)
    env = dict(environment)
    env.update({"ONEC_OBSERVATION_PROGRESS_FILE": str(progress), "KD_RULES_CYCLE_RESULT_FILE": str(result_file)})
    stage_timeout = limits.get("stageTimeoutSeconds")
    outcome = run_observed(
        ObservationRequest(
            capability=f"kd-rules-cycle.{stage}",
            target=target,
            run_root=stage_root,
            command=list(command),
            cwd=ROOT,
            env=env,
            progress_file=progress,
            stall_timeout_seconds=float(limits["runtimeStageTimeoutSeconds"]),
            timeout_seconds=float(stage_timeout) if stage_timeout else None,
            expected_result=result_file if expect_result else None,
        )
    )
    if outcome.signal == "SIGINT":
        raise KeyboardInterrupt
    evidence: dict[str, Any] = {
        "exitCode": outcome.exit_code,
        "terminalReason": outcome.terminal_reason,
        "observation": outcome.observation_path.resolve().relative_to(run_root.resolve()).as_posix(),
    }
    if outcome.exit_code != 0:
        raise CycleError(
            f"{stage} {target} failed: {outcome.terminal_reason} (exit {outcome.exit_code}); "
            f"see {outcome.observation_path}"
        )
    if expect_result:
        payload = read_json(result_file)
        if payload.get("status") != "passed":
            raise CycleError(f"{stage} {target} result is not passed: {result_file}")
        evidence["result"] = payload
    return evidence


def publish_release(release: Path, manifest: Mapping[str, Any], publish_root: Path) -> Path:
    """Copy the release files and then `manifest.json` into the publish root, checking every hash."""
    if not publish_root.is_absolute() or publish_root.is_symlink():
        raise CycleError("releasePublishRoot must be an absolute path that is not a symbolic link")
    publish_root.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {**manifest["files"], **manifest["archives"]}
    for relative, expected in sorted(files.items()):
        target = publish_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            shutil.copyfile(release / relative, temporary)
            if sha256(temporary) != expected:
                raise CycleError(f"published file hash mismatch: {relative}")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    staged = publish_root / "manifest.json.tmp"
    shutil.copyfile(release / "manifest.json", staged)
    os.replace(staged, publish_root / "manifest.json")
    return publish_root
