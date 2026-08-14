from __future__ import annotations

import os
import re
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
from .runtime_profiles import load_runtime_profile, require_runtime_profile, resolve_runtime_profile_path
from .runtime_lock import project_runtime_lock
from .runtime_result import prepare_run_artifacts, publish_interrupted_summary, publish_summary, sanitize_artifact_logs
from .runtime_process import run_logged


CFE_COMMANDS = {"load-cfe", "configure-cfe-runtime-flags", "check-cfe-applicability", "check-cfe-config", "manage-cfe"}


def validate_extension_name(value: str) -> str:
    if not value or not re.fullmatch(r"[^/\\\x00-\x1f]+", value) or value in {".", ".."}:
        raise CommandError(f"invalid extension name: {value}")
    return value


def _ibcmd_base(profile: Any, *parts: str, dry_run: bool) -> list[str]:
    command = [ibcmd_binary_path(profile), *parts]
    append_ibcmd_server_access_args(profile, command)
    append_ibcmd_target_args(profile, command, dry_run=dry_run)
    append_ibcmd_infobase_auth_args(profile, command, dry_run=dry_run)
    return command


def build_cfe_commands(command_id: str, profile: Any, extension: str, *, action: str = "", dry_run: bool) -> list[list[str]]:
    name = validate_extension_name(extension) if extension else ""
    if command_id == "load-cfe":
        source = project_root() / "src" / "cfe" / name
        return [
            [*_ibcmd_base(profile, "config", "import", dry_run=dry_run), f"--extension={name}", str(source)],
            [*_ibcmd_base(profile, "config", "check", dry_run=dry_run), f"--extension={name}", "--force"],
            [*_ibcmd_base(profile, "config", "apply", dry_run=dry_run), f"--extension={name}", "--force"],
        ]
    if command_id == "configure-cfe-runtime-flags":
        return [[*_ibcmd_base(profile, "infobase", "config", "extension", "update", dry_run=dry_run), f"--name={name}", "--safe-mode=no", "--unsafe-action-protection=no"]]
    if command_id == "manage-cfe":
        if action not in {"list", "delete"}:
            raise CommandError(f"unsupported manage-cfe action: {action}")
        result = _ibcmd_base(profile, "config", "extension", action, dry_run=dry_run)
        if action == "delete":
            result.append(f"--name={name}")
        return [result]
    if command_id == "check-cfe-applicability":
        return [[*build_designer_command(profile, "/DisableStartupDialogs", "/DisableStartupMessages", "/CheckCanApplyConfigurationExtensions", "-Extension", name, dry_run=dry_run)]]
    if command_id == "check-cfe-config":
        return [[*build_designer_command(profile, "/DisableStartupDialogs", "/DisableStartupMessages", "/CheckConfig", "-HandlersExistence", "-ThinClient", "-WebClient", "-Server", "-ThickClientManagedApplication", "-ThickClientServerManagedApplication", "-Extension", name, dry_run=dry_run)]]
    raise CommandError(f"unsupported CFE command: {command_id}")


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
            if arg == "--profile": profile_input = argv[index]
            elif arg == "--run-root": run_root_input = argv[index]
            else: extension = argv[index]
        elif arg == "--dry-run":
            dry_run = True
        else:
            raise CommandError(f"unknown argument: {arg}")
        index += 1
    if command_id != "manage-cfe" or action == "delete":
        validate_extension_name(extension)
    profile = require_runtime_profile(load_runtime_profile(resolve_runtime_profile_path(profile_input)))
    run_root = Path(run_root_input) if run_root_input else project_root() / ".artifacts" / command_id
    artifacts = prepare_run_artifacts(run_root)
    commands = build_cfe_commands(command_id, profile, extension, action=action, dry_run=dry_run)
    started_at = timestamp_utc()
    secret_refs = (
        profile.string("infobase", "auth", "passwordEnv"),
        profile.string("ibcmd", "dbmsInfobase", "passwordEnv"),
        profile.string("ibcmd", "auth", "passwordEnv"),
    )
    secrets = [os.environ[name] for name in secret_refs if name and os.environ.get(name)]
    exit_code = 0
    if not dry_run:
        try:
            with project_runtime_lock(project_root(), command_id):
                for command in commands:
                    exit_code = run_logged(command, stdout_path=artifacts.stdout_path, stderr_path=artifacts.stderr_path, cwd=project_root())
                    if exit_code:
                        break
        except KeyboardInterrupt:
            publish_interrupted_summary(
                artifacts,
                {
                    "capability": {"id": command_id},
                    "profile_path": str(profile.path),
                    "extension_name": extension or None,
                    "action": action or None,
                    "started_at": started_at,
                    "finished_at": timestamp_utc(),
                    "dry_run": False,
                },
                reason="operator cancellation",
                cleanup=lambda: None,
                secrets=secrets,
            )
            return 130
    payload = {
        "status": "dry-run" if dry_run else ("success" if exit_code == 0 else "failed"),
        "capability": {"id": command_id},
        "profile_path": str(profile.path),
        "extension_name": extension or None,
        "action": action or None,
        "started_at": started_at,
        "finished_at": timestamp_utc(),
        "exit_code": exit_code,
        "dry_run": dry_run,
        "execution": {"source": "python-cfe-runtime", "commands": commands},
        "artifacts": {"summary_json": str(artifacts.summary_path), "stdout_log": str(artifacts.stdout_path), "stderr_log": str(artifacts.stderr_path)},
    }
    sanitize_artifact_logs(artifacts, secrets)
    publish_summary(artifacts, payload, secrets)
    return exit_code
