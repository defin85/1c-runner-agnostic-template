"""Graphical 1C launches through the repository adapter and the shared observation adapter.

On Linux the platform process runs inside an own Xpra session of
``scripts/adapters/direct-platform.sh`` that belongs to one run-root. On Windows
the platform binary is started directly. Either way the launch is observed by
``runtime_observation`` and the password never appears in output or artifacts.
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from .runtime_observation import (
    ObservationRequest,
    ObservationResult,
    launch_identity,
    publish_observation_summary,
    run_observed,
)
from .runtime_techlog import plan_from_env

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "scripts" / "adapters" / "direct-platform.sh"
DEFAULT_XVFB_ARGS = "Xvfb -screen 0 1440x900x24 -nolisten tcp -noreset -auth $XAUTHORITY"
MASK = "***"
SECRET_FLAGS = {"/P", "--password", "--db-pwd"}


def resolve_v8path(value: str = "") -> str:
    """Path to the platform executable: explicit value first, then the newest standard installation."""
    if value:
        path = Path(value)
        if path.is_dir():
            names = ("1cv8.exe",) if os.name == "nt" else ("1cv8", "1cv8c")
            path = next((path / name for name in names if (path / name).is_file()), path)
        if path.is_file():
            return str(path)
        raise FileNotFoundError(f"1C executable not found at {path}")
    candidates = glob.glob(r"C:\Program Files\1cv8\*\bin\1cv8.exe") + glob.glob("/opt/1cv8/x86_64/*/1cv8")
    found = shutil.which("1cv8")
    if found:
        candidates.append(found)
    if not candidates:
        raise FileNotFoundError("1C executable not found; set platform.binaryPath in the runtime profile")
    return sorted(candidates)[-1]


def adapter_command(
    v8path: str,
    arguments: list[str],
    run_root: Path,
    *,
    xvfb_args: str = "",
    start_child: str = "",
    modal_policy: str = "",
) -> tuple[list[str], dict[str, str]]:
    """Command and extra environment that start the platform inside the run-root's own Xpra session."""
    env = {"ONEC_CAPABILITY_RUN_ROOT": str(run_root)}
    if os.name == "nt":
        return [v8path, *arguments], env
    if not ADAPTER.is_file():
        raise FileNotFoundError(f"Xpra adapter not found: {ADAPTER}")
    env["ONEC_DIRECT_PLATFORM_XPRA_ENABLED"] = "1"
    env["ONEC_DIRECT_PLATFORM_XPRA_XVFB_ARGS"] = xvfb_args or os.environ.get(
        "ONEC_DIRECT_PLATFORM_XPRA_XVFB_ARGS", DEFAULT_XVFB_ARGS
    )
    env["ONEC_DIRECT_PLATFORM_XPRA_START_CHILD"] = start_child or os.environ.get(
        "ONEC_DIRECT_PLATFORM_XPRA_START_CHILD", "openbox"
    )
    if modal_policy:
        env["ONEC_DIRECT_PLATFORM_XPRA_MODAL_POLICY"] = modal_policy
    return [str(ADAPTER), v8path, *arguments], env


def redacted(arguments: list[str]) -> list[str]:
    """Arguments safe to print: password values are replaced with ``***``."""
    result: list[str] = []
    hide_next = False
    for argument in arguments:
        if hide_next:
            result.append(MASK)
            hide_next = False
        elif argument in SECRET_FLAGS:
            result.append(argument)
            hide_next = True
        elif argument.startswith("/P") and len(argument) > 2:
            result.append("/P" + MASK)
        elif argument.startswith(("--password=", "--db-pwd=")):
            result.append(argument.split("=", 1)[0] + "=" + MASK)
        else:
            result.append(argument)
    return result


def secret_values(arguments: list[str]) -> list[str]:
    """Password values present in platform arguments; used to mask logs and summaries."""
    values: list[str] = []
    for index, argument in enumerate(arguments):
        if argument in SECRET_FLAGS and index + 1 < len(arguments):
            values.append(arguments[index + 1])
        elif argument.startswith("/P") and len(argument) > 2:
            values.append(argument[2:])
        elif argument.startswith(("--password=", "--db-pwd=")):
            values.append(argument.split("=", 1)[1])
    return [value for value in values if value]


def mask_text(text: str, secrets: list[str]) -> str:
    for secret in sorted(set(secrets), key=len, reverse=True):
        if secret:
            text = text.replace(secret, MASK)
    return text


def mask_files(paths: list[Path], secrets: list[str]) -> None:
    if not secrets:
        return
    for path in paths:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        masked = mask_text(content, secrets)
        if masked != content:
            path.write_text(masked, encoding="utf-8", newline="\n")


def observed_launch(
    command: list[str],
    env: dict[str, str],
    run_root: Path,
    *,
    capability: str,
    target: str,
    secrets: list[str],
    summary: dict[str, Any] | None = None,
    **request_options: Any,
) -> ObservationResult:
    """Run one platform command under observation and publish a masked ``summary.json``."""
    run_root.mkdir(parents=True, exist_ok=True)
    identity_env, on_started = launch_identity(run_root, command)
    merged_env = {**env, **identity_env}
    result = run_observed(
        ObservationRequest(
            capability=capability,
            target=target,
            run_root=run_root,
            command=command,
            env=merged_env,
            techlog=plan_from_env(run_root, process_id_file=run_root / "process.pid"),
            on_started=on_started,
            **request_options,
        )
    )
    mask_files([run_root / "stdout.log", run_root / "stderr.log"], secrets)
    payload = dict(summary or {})
    payload.update(
        status="success" if result.exit_code == 0 else "failed",
        exit_code=result.exit_code,
        run_root=str(run_root),
        command=redacted(command),
        artifacts={"stdout_log": str(run_root / "stdout.log"), "stderr_log": str(run_root / "stderr.log")},
    )
    summary_path = publish_observation_summary(run_root, payload)
    mask_files([summary_path], secrets)
    return result


def launch_from_stdin() -> int:
    """``python -m scripts.python.onec_xpra`` entry: JSON request on stdin keeps the password off argv."""
    request = json.load(sys.stdin)
    if not isinstance(request, dict):
        raise SystemExit("launch request must be a JSON object")
    command = [str(item) for item in request["command"]]
    result = observed_launch(
        command,
        {str(key): str(value) for key, value in dict(request.get("env", {})).items()},
        Path(str(request["run_root"])),
        capability=str(request.get("capability", "platform-launch")),
        target=str(request.get("target", "platform")),
        secrets=[str(item) for item in request.get("secrets", [])] or secret_values(command),
        summary=dict(request.get("summary", {})),
    )
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(launch_from_stdin())
