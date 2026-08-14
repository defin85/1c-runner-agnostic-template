from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from .common import ensure_dir, write_json


@dataclass(frozen=True, slots=True)
class RunArtifacts:
    run_root: Path
    summary_path: Path
    stdout_path: Path
    stderr_path: Path


def prepare_run_artifacts(run_root: str | Path) -> RunArtifacts:
    root = ensure_dir(run_root)
    artifacts = RunArtifacts(root, root / "summary.json", root / "stdout.log", root / "stderr.log")
    artifacts.stdout_path.write_text("", encoding="utf-8", newline="\n")
    artifacts.stderr_path.write_text("", encoding="utf-8", newline="\n")
    return artifacts


def redact_text(value: str, secrets: Iterable[str]) -> str:
    redacted = value
    for secret in sorted({item for item in secrets if item}, key=len, reverse=True):
        redacted = redacted.replace(secret, "__REDACTED_SECRET__")
    return redacted


def redact_payload(value: Any, secrets: Iterable[str]) -> Any:
    secret_values = tuple(secrets)
    if isinstance(value, str):
        return redact_text(value, secret_values)
    if isinstance(value, list):
        return [redact_payload(item, secret_values) for item in value]
    if isinstance(value, dict):
        return {key: redact_payload(item, secret_values) for key, item in value.items()}
    return value


def sanitize_artifact_logs(artifacts: RunArtifacts, secrets: Iterable[str]) -> None:
    secret_values = tuple(item for item in secrets if item)
    if not secret_values:
        return
    for path in (artifacts.stdout_path, artifacts.stderr_path):
        content = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        path.write_text(redact_text(content, secret_values), encoding="utf-8", newline="\n")


def publish_summary(artifacts: RunArtifacts, payload: dict[str, Any], secrets: Iterable[str] = ()) -> None:
    write_json(artifacts.summary_path, redact_payload(payload, tuple(secrets)))


def evaluate_postcondition(
    predicate: Callable[[], bool],
    *,
    failure_message: str,
    tool_exit_code: int,
) -> tuple[str, int, str | None]:
    if tool_exit_code != 0:
        return "failed", tool_exit_code, None
    try:
        passed = bool(predicate())
    except Exception as error:  # postcondition failures are result data, not crashes
        return "failed", 70, f"{failure_message}: {error}"
    if not passed:
        return "failed", 70, failure_message
    return "success", 0, None


def publish_interrupted_summary(
    artifacts: RunArtifacts,
    payload: dict[str, Any],
    *,
    reason: str,
    cleanup: Callable[[], None],
    secrets: Iterable[str] = (),
) -> None:
    cleanup_error: str | None = None
    try:
        cleanup()
    except Exception as error:
        cleanup_error = str(error)
    interrupted = dict(payload)
    interrupted.update({"status": "interrupted", "exit_code": 130, "interruption_reason": reason})
    if cleanup_error:
        interrupted["cleanup_error"] = cleanup_error
    sanitize_artifact_logs(artifacts, secrets)
    publish_summary(artifacts, interrupted, secrets)
