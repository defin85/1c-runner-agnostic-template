from __future__ import annotations

import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .common import CommandError, project_root, timestamp_utc
from .runtime import (
    append_ibcmd_infobase_auth_args,
    append_ibcmd_server_access_args,
    append_ibcmd_target_args,
    build_designer_command,
    ibcmd_binary_path,
)
from .runtime_lock import project_runtime_lock
from .runtime_observation import (
    PLATFORM_PROCESSES,
    PROGRESS_FILE,
    ObservationRequest,
    attach_observation,
    build_observation_summary,
    launch_identity,
    run_observed,
    stall_timeout_from_env,
)
from .runtime_profiles import (
    RuntimeProfile,
    load_runtime_profile,
    require_runtime_profile,
    resolve_runtime_profile_path,
)
from .runtime_result import (
    RunArtifacts,
    prepare_run_artifacts,
    publish_interrupted_summary,
    publish_summary,
    sanitize_artifact_logs,
)
from .runtime_techlog import plan_from_env as techlog_plan_from_env

CFE_COMMANDS = {"load-cfe", "configure-cfe-runtime-flags", "check-cfe-applicability", "check-cfe-config", "manage-cfe"}


def validate_extension_name(value: str) -> str:
    if not value or not re.fullmatch(r"[^/\\\x00-\x1f]+", value) or value in {".", ".."}:
        raise CommandError(f"invalid extension name: {value}")
    return value


def ibcmd_command(profile: Any, *parts: str, dry_run: bool) -> list[str]:
    """ibcmd command line with the server access, infobase and auth arguments of the runtime profile."""
    command = [ibcmd_binary_path(profile), *parts]
    append_ibcmd_server_access_args(profile, command)
    append_ibcmd_target_args(profile, command, dry_run=dry_run)
    append_ibcmd_infobase_auth_args(profile, command, dry_run=dry_run)
    return command


def build_cfe_commands(
    command_id: str, profile: Any, extension: str, *, action: str = "", dry_run: bool
) -> list[list[str]]:
    name = validate_extension_name(extension) if extension else ""
    if command_id == "load-cfe":
        source = project_root() / "src" / "cfe" / name
        return [
            [*ibcmd_command(profile, "config", "import", dry_run=dry_run), f"--extension={name}", str(source)],
            [*ibcmd_command(profile, "config", "check", dry_run=dry_run), f"--extension={name}", "--force"],
            [*ibcmd_command(profile, "config", "apply", dry_run=dry_run), f"--extension={name}", "--force"],
        ]
    if command_id == "configure-cfe-runtime-flags":
        return [
            [
                *ibcmd_command(profile, "infobase", "config", "extension", "update", dry_run=dry_run),
                f"--name={name}",
                "--safe-mode=no",
                "--unsafe-action-protection=no",
            ]
        ]
    if command_id == "manage-cfe":
        if action not in {"list", "delete"}:
            raise CommandError(f"unsupported manage-cfe action: {action}")
        result = ibcmd_command(profile, "config", "extension", action, dry_run=dry_run)
        if action == "delete":
            result.append(f"--name={name}")
        return [result]
    if command_id == "check-cfe-applicability":
        return [
            [
                *build_designer_command(
                    profile,
                    "/DisableStartupDialogs",
                    "/DisableStartupMessages",
                    "/CheckCanApplyConfigurationExtensions",
                    "-Extension",
                    name,
                    dry_run=dry_run,
                )
            ]
        ]
    if command_id == "check-cfe-config":
        return [
            [
                *build_designer_command(
                    profile,
                    "/DisableStartupDialogs",
                    "/DisableStartupMessages",
                    "/CheckConfig",
                    "-HandlersExistence",
                    "-ThinClient",
                    "-WebClient",
                    "-Server",
                    "-ThickClientManagedApplication",
                    "-ThickClientServerManagedApplication",
                    "-Extension",
                    name,
                    dry_run=dry_run,
                )
            ]
        ]
    raise CommandError(f"unsupported CFE command: {command_id}")


def profile_secret_values(profile: RuntimeProfile) -> list[str]:
    """Resolved password values of the runtime profile that must not reach summaries or logs."""
    refs = (
        profile.string("infobase", "auth", "passwordEnv"),
        profile.string("ibcmd", "dbmsInfobase", "passwordEnv"),
        profile.string("ibcmd", "auth", "passwordEnv"),
    )
    return [os.environ[name] for name in refs if name and os.environ.get(name)]


def _step_root(run_root: Path, index: int, total: int) -> Path:
    # One observation.jsonl per launch: a multi-step operation keeps each step in its own directory.
    return run_root if total == 1 else run_root / "steps" / f"{index + 1:02d}"


def run_observed_step(
    capability: str,
    profile: RuntimeProfile,
    command: Sequence[str],
    step_root: Path,
    artifacts: RunArtifacts,
    *,
    expected_result: Path | None = None,
) -> int:
    """Run one Designer or ibcmd command through the shared observation adapter.

    The stall threshold comes only from ONEC_OBSERVATION_STALL_TIMEOUT_SECONDS set by the calling
    wrapper; without it the adapter reports heartbeats and never stops the operation.
    """
    step_root.mkdir(parents=True, exist_ok=True)
    progress_file = step_root / PROGRESS_FILE
    progress_file.unlink(missing_ok=True)
    identity_env, on_started = launch_identity(step_root, command)
    env = {**identity_env, "ONEC_OBSERVATION_PROGRESS_FILE": str(progress_file)}
    platform_launch = bool(command) and Path(str(command[0])).name.lower() in PLATFORM_PROCESSES
    techlog = (
        techlog_plan_from_env(
            step_root,
            infobase_mode=profile.string("infobase", "mode"),
            infobase_ref=profile.string("infobase", "ref"),
            process_id_file=step_root / "process.pid",
        )
        if platform_launch
        else None
    )
    result = run_observed(
        ObservationRequest(
            capability=capability,
            target=profile.name or "runtime-profile",
            run_root=step_root,
            command=list(command),
            stdout_log=artifacts.stdout_path,
            stderr_log=artifacts.stderr_path,
            cwd=project_root(),
            env=env,
            progress_file=progress_file,
            stall_timeout_seconds=stall_timeout_from_env(),
            expected_result=expected_result,
            techlog=techlog,
            on_started=on_started,
        )
    )
    if result.signal == "SIGINT":
        raise KeyboardInterrupt
    return result.exit_code


def _attach_step_observations(payload: dict[str, Any], run_root: Path, executed: int, total: int) -> None:
    if total == 1:
        attach_observation(payload, run_root)
        return
    steps = []
    for index in range(executed):
        summary = build_observation_summary(_step_root(run_root, index, total))
        if summary is not None:
            steps.append(summary)
    if steps:
        payload["observation"] = steps[-1]
        payload["observation_steps"] = steps


def execute_profile_operation(
    command_id: str,
    profile: RuntimeProfile,
    commands: list[list[str]],
    run_root: Path,
    *,
    dry_run: bool,
    context: dict[str, Any],
    expected_result: Path | None = None,
) -> int:
    """Run profile commands under the project runtime lock and observation; publish summary.json.

    ``expected_result`` applies to the last command: a zero exit without the file is a failure.
    """
    artifacts = prepare_run_artifacts(run_root)
    started_at = timestamp_utc()
    secrets = profile_secret_values(profile)
    base = {"capability": {"id": command_id}, "profile_path": str(profile.path), **context, "started_at": started_at}
    exit_code = 0
    executed = 0
    if not dry_run:
        try:
            with project_runtime_lock(project_root(), command_id):
                for index, command in enumerate(commands):
                    executed = index + 1
                    exit_code = run_observed_step(
                        command_id,
                        profile,
                        command,
                        _step_root(artifacts.run_root, index, len(commands)),
                        artifacts,
                        expected_result=expected_result if executed == len(commands) else None,
                    )
                    if exit_code:
                        break
        except KeyboardInterrupt:
            interrupted = {**base, "finished_at": timestamp_utc(), "dry_run": False}
            _attach_step_observations(interrupted, artifacts.run_root, executed, len(commands))
            publish_interrupted_summary(
                artifacts, interrupted, reason="operator cancellation", cleanup=lambda: None, secrets=secrets
            )
            return 130
    payload = {
        **base,
        "status": "dry-run" if dry_run else ("success" if exit_code == 0 else "failed"),
        "finished_at": timestamp_utc(),
        "exit_code": exit_code,
        "dry_run": dry_run,
        "execution": {"source": "python-cfe-runtime", "commands": commands},
        "artifacts": {
            "summary_json": str(artifacts.summary_path),
            "stdout_log": str(artifacts.stdout_path),
            "stderr_log": str(artifacts.stderr_path),
        },
    }
    if not dry_run:
        _attach_step_observations(payload, artifacts.run_root, executed, len(commands))
    sanitize_artifact_logs(artifacts, secrets)
    publish_summary(artifacts, payload, secrets)
    return exit_code


def run_cfe_command(command_id: str, argv: list[str]) -> int:
    if command_id not in CFE_COMMANDS:
        raise CommandError(f"unsupported CFE command: {command_id}")
    profile_input = ""
    run_root_input = ""
    extension = ""
    action = ""
    dry_run = False
    index = 0
    if command_id == "manage-cfe" and argv and not argv[0].startswith("-"):
        action = argv[0]
        index = 1
    while index < len(argv):
        arg = argv[index]
        if arg in {"--profile", "--run-root", "--extension"}:
            index += 1
            if index >= len(argv):
                raise CommandError(f"{arg} requires a value")
            if arg == "--profile":
                profile_input = argv[index]
            elif arg == "--run-root":
                run_root_input = argv[index]
            else:
                extension = argv[index]
        elif arg == "--dry-run":
            dry_run = True
        else:
            raise CommandError(f"unknown argument: {arg}")
        index += 1
    if command_id != "manage-cfe" or action == "delete":
        validate_extension_name(extension)
    profile = require_runtime_profile(load_runtime_profile(resolve_runtime_profile_path(profile_input)))
    run_root = Path(run_root_input) if run_root_input else project_root() / ".artifacts" / command_id
    commands = build_cfe_commands(command_id, profile, extension, action=action, dry_run=dry_run)
    return execute_profile_operation(
        command_id,
        profile,
        commands,
        run_root,
        dry_run=dry_run,
        context={"extension_name": extension or None, "action": action or None},
    )
