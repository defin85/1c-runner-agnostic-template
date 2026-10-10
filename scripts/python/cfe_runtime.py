from __future__ import annotations

import json
import os
import re
from collections.abc import Sequence
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .common import CommandError, project_root, timestamp_utc, write_json
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
    resolve_target_extensions,
    target_matrix_enabled,
)
from .runtime_result import (
    RunArtifacts,
    prepare_run_artifacts,
    publish_interrupted_summary,
    publish_summary,
    redact_payload,
    redact_text,
    sanitize_artifact_logs,
)
from .runtime_techlog import plan_from_env as techlog_plan_from_env

CFE_COMMANDS = {"load-cfe", "configure-cfe-runtime-flags", "check-cfe-applicability", "check-cfe-config", "manage-cfe"}
MANAGE_CFE_ACTIONS = ("list", "dump", "import", "load", "save", "apply", "activate", "deactivate", "delete")
EXTENSION_REQUIRED_ACTIONS = {"apply", "activate", "deactivate", "delete"}
DESIGNER_ACTIONS = {"import", "apply"}
IMPORT_LIST_FILE = "import-files.txt"
DESIGNER_OUT_LOG = "designer.out.log"


@dataclass(slots=True)
class CfeOptions:
    """Options of configure-cfe-runtime-flags and manage-cfe beyond profile, run root and extension."""

    safe_mode: str = "no"
    unsafe_action_protection: str = "no"
    active: str = ""
    security_profile_name: str = ""
    clear_security_profile: bool = False
    driver: str = "ibcmd"
    source: str = ""
    list_file: str = ""
    output: str = ""
    file: str = ""


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


def _extension_args(name: str) -> list[str]:
    return [f"--extension={name}"] if name else []


def build_runtime_flags_command(profile: Any, name: str, options: CfeOptions, *, dry_run: bool) -> list[str]:
    command = [*ibcmd_command(profile, "infobase", "config", "extension", "update", dry_run=dry_run), f"--name={name}"]
    if options.clear_security_profile:
        command.append("--security-profile-name=")
    elif options.security_profile_name:
        command.append(f"--security-profile-name={options.security_profile_name}")
    command += [f"--safe-mode={options.safe_mode}", f"--unsafe-action-protection={options.unsafe_action_protection}"]
    if options.active:
        command.append(f"--active={options.active}")
    return command


def build_manage_cfe_command(
    profile: Any, action: str, name: str, options: CfeOptions, run_root: Path | None, *, dry_run: bool
) -> list[str]:
    if options.driver == "designer":
        root = (run_root or project_root() / ".artifacts" / "manage-cfe").resolve()
        designer_action = ["/UpdateDBCfg"]
        if action == "import":
            designer_action = ["/LoadConfigFromFiles", str(Path(options.source).resolve())]
            if options.list_file:
                designer_action += ["-listFile", str(root / IMPORT_LIST_FILE), "-partial"]
        return build_designer_command(
            profile,
            *designer_action,
            "-Extension",
            name,
            "/DisableStartupDialogs",
            "/DisableStartupMessages",
            "/Out",
            str(root / DESIGNER_OUT_LOG),
            dry_run=dry_run,
        )
    if action == "list":
        return ibcmd_command(profile, "config", "extension", "list", dry_run=dry_run)
    if action == "delete":
        return [*ibcmd_command(profile, "config", "extension", "delete", dry_run=dry_run), f"--name={name}"]
    if action in {"activate", "deactivate"}:
        active = "yes" if action == "activate" else "no"
        return [
            *ibcmd_command(profile, "config", "extension", "update", dry_run=dry_run),
            f"--name={name}",
            f"--active={active}",
        ]
    if action == "apply":
        return [*ibcmd_command(profile, "config", "apply", dry_run=dry_run), f"--extension={name}", "--force"]
    if action == "import":
        return [
            *ibcmd_command(profile, "config", "import", dry_run=dry_run),
            *_extension_args(name),
            str(Path(options.source).resolve()),
        ]
    if action == "dump":
        return [
            *ibcmd_command(profile, "config", "export", dry_run=dry_run),
            *_extension_args(name),
            str(Path(options.output).resolve()),
        ]
    if action in {"load", "save"}:
        return [
            *ibcmd_command(profile, "config", action, dry_run=dry_run),
            *_extension_args(name),
            str(Path(options.file).resolve()),
        ]
    raise CommandError(f"unsupported manage-cfe action: {action}")


def build_cfe_commands(
    command_id: str,
    profile: Any,
    extension: str,
    *,
    action: str = "",
    dry_run: bool,
    options: CfeOptions | None = None,
    run_root: Path | None = None,
) -> list[list[str]]:
    options = options or CfeOptions()
    name = validate_extension_name(extension) if extension else ""
    if command_id == "load-cfe":
        source = project_root() / "src" / "cfe" / name
        return [
            [*ibcmd_command(profile, "config", "import", dry_run=dry_run), f"--extension={name}", str(source)],
            [*ibcmd_command(profile, "config", "check", dry_run=dry_run), f"--extension={name}", "--force"],
            [*ibcmd_command(profile, "config", "apply", dry_run=dry_run), f"--extension={name}", "--force"],
        ]
    if command_id == "configure-cfe-runtime-flags":
        return [build_runtime_flags_command(profile, name, options, dry_run=dry_run)]
    if command_id == "manage-cfe":
        if action not in MANAGE_CFE_ACTIONS:
            raise CommandError(f"unsupported manage-cfe action: {action}")
        return [build_manage_cfe_command(profile, action, name, options, run_root, dry_run=dry_run)]
    out_args = ["/Out", str(run_root / DESIGNER_OUT_LOG)] if run_root is not None else []
    if command_id == "check-cfe-applicability":
        return [
            [
                *build_designer_command(
                    profile,
                    "/DisableStartupDialogs",
                    "/DisableStartupMessages",
                    *out_args,
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
                    *out_args,
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


LOAD_CFE_STEPS = ("import", "check", "apply")
LOAD_CFE_MODE = "ibcmd-sequential-extension-import-check-apply"
LOAD_CFE_USAGE = """Usage: ./scripts/platform/load-cfe.sh [options]

Options:
  --profile <file>    Runtime profile JSON (defaults to env/local.json if present)
  --run-root <dir>    Directory for the wrapper summary and per-extension artifacts
  --target <id>       Target id from automation/context/target-matrix.json; selects the target's extension set
  --extension <name>  Load only this extension from src/cfe (repeatable); default: every directory in src/cfe
  --dry-run           Resolve ibcmd commands and write dry-run summaries only
  -h, --help          Show this help
"""


def collect_load_cfe_extensions(source_root: Path, explicit: Sequence[str]) -> list[str]:
    """Extensions to load: the explicit names in order, or every directory under ``source_root``."""
    if explicit:
        names: list[str] = []
        for name in explicit:
            validate_extension_name(name)
            if not (source_root / name).is_dir():
                raise CommandError(f"extension source not found under {source_root}: {name}")
            if name not in names:
                names.append(name)
        return names
    if not source_root.is_dir():
        return []
    return sorted(path.name for path in source_root.iterdir() if path.is_dir())


def _append_line(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(line + "\n")


def _redact_files(paths: Sequence[Path], secrets: Sequence[str]) -> None:
    if not secrets:
        return
    for path in paths:
        if path.is_file():
            content = path.read_text(encoding="utf-8", errors="replace")
            path.write_text(redact_text(content, secrets), encoding="utf-8", newline="\n")


@dataclass(slots=True)
class _LoadCfeRun:
    profile: RuntimeProfile
    run_root: Path
    artifacts: RunArtifacts
    secrets: list[str]
    dry_run: bool
    failed_extension: str = ""
    failed_step: str = ""
    log_paths: list[Path] = field(default_factory=list)


def _load_cfe_extension(run: _LoadCfeRun, name: str, commands: list[list[str]]) -> int:
    """Import, check and apply one extension; write per-step and per-extension summaries."""
    extension_artifacts = prepare_run_artifacts(run.run_root / "extensions" / name)
    extension_root = extension_artifacts.run_root
    run.log_paths.extend([extension_artifacts.stdout_path, extension_artifacts.stderr_path])
    started_at = timestamp_utc()
    steps: list[dict[str, Any]] = []
    exit_code = 0
    failed_step = ""
    for step_id, command in zip(LOAD_CFE_STEPS, commands, strict=True):
        step_stdout = extension_root / f"{step_id}.stdout.log"
        step_stderr = extension_root / f"{step_id}.stderr.log"
        command_txt = extension_root / f"{step_id}.command.txt"
        step_stdout.write_text("", encoding="utf-8", newline="\n")
        step_stderr.write_text("", encoding="utf-8", newline="\n")
        command_txt.write_text(redact_text("\n".join(command) + "\n", run.secrets), encoding="utf-8", newline="\n")
        run.log_paths.extend([step_stdout, step_stderr])
        for log_path in (run.artifacts.stdout_path, extension_artifacts.stdout_path):
            _append_line(log_path, f"[load-cfe] extension={name} step={step_id} started")
        step_started_at = timestamp_utc()
        step_root = extension_root / "steps" / step_id
        step_exit = 0
        if not run.dry_run:
            step_exit = run_observed_step(
                "load-cfe",
                run.profile,
                command,
                step_root,
                RunArtifacts(extension_root, extension_artifacts.summary_path, step_stdout, step_stderr),
            )
        status = "dry-run" if run.dry_run else ("failed" if step_exit else "success")
        for log_path in (run.artifacts.stdout_path, extension_artifacts.stdout_path):
            _append_line(log_path, f"[load-cfe] extension={name} step={step_id} status={status} exit_code={step_exit}")
        if step_exit:
            for log_path in (run.artifacts.stderr_path, extension_artifacts.stderr_path):
                _append_line(log_path, f"[load-cfe] extension={name} step={step_id} failed")
        step_payload: dict[str, Any] = {
            "id": step_id,
            "status": status,
            "exit_code": step_exit,
            "dry_run": run.dry_run,
            "started_at": step_started_at,
            "finished_at": timestamp_utc(),
            "artifacts": {
                "command_txt": str(command_txt),
                "stdout_log": str(step_stdout),
                "stderr_log": str(step_stderr),
            },
        }
        observation = None if run.dry_run else build_observation_summary(step_root)
        if observation is not None:
            step_payload["observation"] = observation
        write_json(extension_root / f"{step_id}.summary.json", redact_payload(step_payload, run.secrets))
        steps.append(step_payload)
        if step_exit:
            exit_code = step_exit
            failed_step = step_id
            break
    status = "failed" if exit_code else ("dry-run" if run.dry_run else "success")
    payload: dict[str, Any] = {
        "status": status,
        "extension_name": name,
        "profile_path": str(run.profile.path),
        "run_root": str(extension_root),
        "source_path": str(project_root() / "src" / "cfe" / name),
        "started_at": started_at,
        "finished_at": timestamp_utc(),
        "exit_code": exit_code,
        "dry_run": run.dry_run,
        "driver": "ibcmd",
        "adapter": run.profile.runner_adapter,
        "failed_step": failed_step or None,
        "execution": {"source": "python-cfe-runtime", "executor": "direct", "mode": LOAD_CFE_MODE},
        "steps": steps,
        "failure": (
            {"classification": "extension-sync failed", "extension_name": name, "step": failed_step}
            if failed_step
            else None
        ),
        "artifacts": {
            "summary_json": str(extension_artifacts.summary_path),
            "stdout_log": str(extension_artifacts.stdout_path),
            "stderr_log": str(extension_artifacts.stderr_path),
        },
    }
    publish_summary(extension_artifacts, payload, run.secrets)
    if failed_step:
        run.failed_extension = name
        run.failed_step = failed_step
    return exit_code


def _load_cfe_result(run: _LoadCfeRun, name: str) -> dict[str, Any]:
    extension_root = run.run_root / "extensions" / name
    summary_path = extension_root / "summary.json"
    summary: dict[str, Any] = {}
    if summary_path.is_file():
        loaded = json.loads(summary_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            summary = loaded
    return {
        "extension_name": name,
        "run_root": str(extension_root),
        "summary_json": str(summary_path),
        "stdout_log": str(extension_root / "stdout.log"),
        "stderr_log": str(extension_root / "stderr.log"),
        "status": summary.get("status"),
        "exit_code": summary.get("exit_code"),
        "failed_step": summary.get("failed_step"),
    }


def run_load_cfe(argv: list[str]) -> int:
    """Load extensions from src/cfe with ibcmd import, check and apply; stop at the first failed step."""
    profile_input = ""
    run_root_input = ""
    target = ""
    explicit: list[str] = []
    dry_run = False
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in {"-h", "--help"}:
            print(LOAD_CFE_USAGE, end="")
            return 0
        if arg in {"--profile", "--run-root", "--extension", "--target"}:
            index += 1
            if index >= len(argv):
                raise CommandError(f"{arg} requires a value")
            if arg == "--profile":
                profile_input = argv[index]
            elif arg == "--run-root":
                run_root_input = argv[index]
            elif arg == "--target":
                target = argv[index]
            else:
                explicit.append(argv[index])
        elif arg == "--dry-run":
            dry_run = True
        else:
            raise CommandError(f"unknown argument: {arg}")
        index += 1
    profile = require_runtime_profile(load_runtime_profile(resolve_runtime_profile_path(profile_input)))
    source_root = project_root() / "src" / "cfe"
    target_id: str | None = None
    if target_matrix_enabled(project_root()):
        names, target_id = select_cfe_extensions(profile, source_root, target, explicit)
    else:
        names = collect_load_cfe_extensions(source_root, explicit)
    if not names:
        raise CommandError(f"no extensions found under {source_root}")
    run_root = Path(run_root_input) if run_root_input else project_root() / ".artifacts" / "load-cfe"
    artifacts = prepare_run_artifacts(run_root)
    run = _LoadCfeRun(profile, artifacts.run_root, artifacts, profile_secret_values(profile), dry_run)
    started_at = timestamp_utc()
    for line in (f"profile={profile.path}", f"source_root={source_root}", f"extensions={' '.join(names)}"):
        _append_line(artifacts.stdout_path, f"[load-cfe] {line}")
    exit_code = 0
    interrupted = False
    lock: AbstractContextManager[object] = (
        nullcontext() if dry_run else project_runtime_lock(project_root(), "load-cfe")
    )
    try:
        with lock:
            for name in names:
                commands = build_cfe_commands("load-cfe", profile, name, dry_run=dry_run)
                exit_code = _load_cfe_extension(run, name, commands)
                if exit_code:
                    break
    except KeyboardInterrupt:
        interrupted = True
    payload: dict[str, Any] = {
        "status": "failed" if exit_code else ("dry-run" if dry_run else "success"),
        "capability": {"id": "load-cfe", "label": "Load 1C extensions"},
        "profile_path": str(profile.path),
        "run_root": str(artifacts.run_root),
        "started_at": started_at,
        "finished_at": timestamp_utc(),
        "exit_code": exit_code,
        "dry_run": dry_run,
        "driver": "ibcmd",
        "adapter": profile.runner_adapter,
        "execution": {"source": "python-cfe-runtime", "strategy": LOAD_CFE_MODE, "mode": LOAD_CFE_MODE},
        "extension_source": {
            "root": str(source_root),
            "target_id": target_id,
            "selected_names": names,
            "failed_names": [run.failed_extension] if run.failed_extension else [],
        },
        "failed_extension": run.failed_extension or None,
        "failed_step": run.failed_step or None,
        "failure": (
            {
                "classification": "extension-sync failed",
                "extension_name": run.failed_extension,
                "step": run.failed_step,
                "extensions": [run.failed_extension],
            }
            if run.failed_extension
            else None
        ),
        "results": [_load_cfe_result(run, name) for name in names],
        "artifacts": {
            "summary_json": str(artifacts.summary_path),
            "stdout_log": str(artifacts.stdout_path),
            "stderr_log": str(artifacts.stderr_path),
        },
    }
    _redact_files(run.log_paths, run.secrets)
    if interrupted:
        publish_interrupted_summary(
            artifacts, payload, reason="operator cancellation", cleanup=lambda: None, secrets=run.secrets
        )
        return 130
    sanitize_artifact_logs(artifacts, run.secrets)
    publish_summary(artifacts, payload, run.secrets)
    return exit_code


CHECK_CFE_LABELS = {
    "check-cfe-applicability": "Check extension applicability",
    "check-cfe-config": "Check extension config",
}
CHECK_CFE_STRATEGIES = {
    "check-cfe-applicability": "designer-check-can-apply-configuration-extensions",
    "check-cfe-config": "designer-check-config",
}
CHECK_CFE_FAILURES = {
    "check-cfe-applicability": "extension-applicability failed",
    "check-cfe-config": "extension-config-verification failed",
}
CHECK_CFE_USAGE = """Usage: ./scripts/platform/{command}.sh [options]

Options:
  --profile <file>       Runtime profile JSON (defaults to env/local.json if present)
  --run-root <dir>       Directory for wrapper summary and extension-level artifacts
  --target <id>          Target id from automation/context/target-matrix.json
  --extension <name>     Check only the specified extension (repeatable); default: every directory in src/cfe
  --dry-run              Resolve Designer commands and write dry-run summaries only
  -h, --help             Show this help
"""
DESIGNER_NO_ERROR_LINES = {"No errors found", "Ошибок не обнаружено"}
DESIGNER_WARNING_MARKERS = ("Handler missing:", "Cannot find method ")
DESIGNER_ERROR_MARKERS = (
    "Variable is not defined",
    "Procedure or function with the specified name is not defined",
    "Method not found",
    "Procedure or function is not defined",
)
BASE_FORM_KINDS = {
    "Документ": "Documents",
    "Справочник": "Catalogs",
    "Обработка": "DataProcessors",
    "РегистрСведений": "InformationRegisters",
}
METADATA_REF_PREFIXES = ("Документ.", "Справочник.", "ОбщаяФорма.", "Обработка.", "РегистрСведений.")


def designer_diagnostic_severity(raw: str, exit_code: int) -> str:
    if any(marker in raw for marker in DESIGNER_WARNING_MARKERS):
        return "warning"
    if any(marker in raw for marker in DESIGNER_ERROR_MARKERS):
        return "error"
    return "error" if exit_code else "warning"


def designer_out_diagnostics(out_log: Path, exit_code: int) -> list[dict[str, Any]]:
    """One diagnostic per non-empty line of the Designer ``/Out`` log, except the no-errors marker."""
    if not out_log.is_file():
        return []
    diagnostics: list[dict[str, Any]] = []
    for line in out_log.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        raw = line.rstrip("\r")
        if not raw or raw in DESIGNER_NO_ERROR_LINES:
            continue
        diagnostics.append({"severity": designer_diagnostic_severity(raw, exit_code), "message": raw, "raw": raw})
    return diagnostics


def _strip_extension_prefix(metadata_ref: str) -> str:
    if metadata_ref.startswith(METADATA_REF_PREFIXES):
        return metadata_ref
    stripped = metadata_ref.split(" ", 1)[1] if " " in metadata_ref else metadata_ref
    return stripped if stripped.startswith(METADATA_REF_PREFIXES) else metadata_ref


def base_form_module_path(metadata_ref: str) -> str:
    """Project-relative module of the base configuration form a borrowed form inherits from."""
    parts = _strip_extension_prefix(metadata_ref).split(".")
    if len(parts) == 3 and parts[0] == "ОбщаяФорма" and parts[2] == "Форма":
        return f"src/cf/CommonForms/{parts[1]}/Ext/Form/Module.bsl"
    if len(parts) == 5 and parts[0] in BASE_FORM_KINDS and parts[2] == "Форма" and parts[4] == "Форма":
        return f"src/cf/{BASE_FORM_KINDS[parts[0]]}/{parts[1]}/Forms/{parts[3]}/Ext/Form/Module.bsl"
    return ""


def _bsl_symbol_exists(module_path: Path, symbol: str) -> bool:
    if not module_path.is_file():
        return False
    pattern = re.compile(rf"^[ \t]*(Процедура|Функция)[ \t]+{re.escape(symbol)}[ \t]*\(", re.MULTILINE)
    return pattern.search(module_path.read_text(encoding="utf-8-sig", errors="replace")) is not None


def classify_config_diagnostics(root: Path, diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark ``Handler missing`` diagnostics resolved by the base form module as inherited handlers."""
    classified: list[dict[str, Any]] = []
    for diagnostic in diagnostics:
        raw = str(diagnostic.get("raw", ""))
        metadata_ref = ""
        handler_name = ""
        base_module = ""
        classification = "blocking"
        resolution = "blocking_diagnostic"
        if " Handler missing:" in raw:
            metadata_ref = raw.split(" Handler missing:", 1)[0]
            quoted = re.match(r'.*"([^"]*)"', raw)
            handler_name = quoted.group(1) if quoted else ""
            base_module = base_form_module_path(metadata_ref)
            if handler_name and base_module and _bsl_symbol_exists(root / base_module, handler_name):
                classification = "inherited_handler"
                resolution = "resolved_in_base_form_module"
            else:
                resolution = "unresolved_handler"
        classified.append(
            {
                **diagnostic,
                "classification": classification,
                "metadata_ref": _strip_extension_prefix(metadata_ref) or None,
                "handler_name": handler_name or None,
                "resolution": {"kind": resolution, "base_form_module": base_module or None},
            }
        )
    return classified


@dataclass(slots=True)
class _CheckCfeRun:
    command_id: str
    profile: RuntimeProfile
    run_root: Path
    artifacts: RunArtifacts
    secrets: list[str]
    dry_run: bool
    adapter: str
    log_paths: list[Path] = field(default_factory=list)


def _check_cfe_extension(run: _CheckCfeRun, name: str) -> int:
    """Run one Designer check with ``/Out``; write the extension summary; return its exit code."""
    extension_artifacts = prepare_run_artifacts(run.run_root / "extensions" / name)
    extension_root = extension_artifacts.run_root
    out_log = extension_root / DESIGNER_OUT_LOG
    out_log.write_text("", encoding="utf-8", newline="\n")
    run.log_paths.extend([extension_artifacts.stdout_path, extension_artifacts.stderr_path, out_log])
    command = build_cfe_commands(run.command_id, run.profile, name, dry_run=run.dry_run, run_root=extension_root)[0]
    _append_line(extension_artifacts.stdout_path, f"[{run.command_id}] extension={name}")
    _append_line(run.artifacts.stdout_path, f"[{run.command_id}] extension={name}")
    started_at = timestamp_utc()
    designer_exit = 0
    exit_code = 0
    status = "dry-run" if run.dry_run else "success"
    diagnostics: list[dict[str, Any]] = []
    if not run.dry_run:
        designer_exit = run_observed_step(run.command_id, run.profile, command, extension_root, extension_artifacts)
        exit_code = designer_exit
        status = "failed" if designer_exit else "success"
        diagnostics = designer_out_diagnostics(out_log, designer_exit)
    if run.command_id == "check-cfe-config":
        diagnostics = classify_config_diagnostics(project_root(), diagnostics)
        blocking = [item for item in diagnostics if item["classification"] == "blocking"]
        inherited = [item for item in diagnostics if item["classification"] == "inherited_handler"]
    else:
        blocking, inherited = list(diagnostics), []
    if blocking:
        status = "failed"
        exit_code = exit_code or 1
    elif inherited:
        status, exit_code = "success", 0
    paths = {
        "diagnostics_json": extension_root / "diagnostics.json",
        "blocking_diagnostics_json": extension_root / "blocking-diagnostics.json",
        "inherited_diagnostics_json": extension_root / "inherited-diagnostics.json",
    }
    for key, items in zip(paths, (diagnostics, blocking, inherited), strict=True):
        write_json(paths[key], redact_payload(items, run.secrets))
    payload: dict[str, Any] = {
        "status": status,
        "extension_name": name,
        "profile_path": str(run.profile.path),
        "run_root": str(extension_root),
        "started_at": started_at,
        "finished_at": timestamp_utc(),
        "exit_code": exit_code,
        "designer_exit_code": designer_exit,
        "dry_run": run.dry_run,
        "adapter": run.adapter,
        "diagnostics_count": len(diagnostics),
        "blocking_diagnostics_count": len(blocking),
        "inherited_diagnostics_count": len(inherited),
        "diagnostics": diagnostics,
        "blocking_diagnostics": blocking,
        "inherited_diagnostics": inherited,
        "execution": {
            "source": f"{run.command_id}-wrapper",
            "executor": "python-cfe-runtime",
            "mode": CHECK_CFE_STRATEGIES[run.command_id],
            "command": command,
        },
        "artifacts": {
            "summary_json": str(extension_artifacts.summary_path),
            "stdout_log": str(extension_artifacts.stdout_path),
            "stderr_log": str(extension_artifacts.stderr_path),
            "designer_out_log": str(out_log),
            **{key: str(path) for key, path in paths.items()},
        },
    }
    if not run.dry_run:
        attach_observation(payload, extension_root)
    publish_summary(extension_artifacts, payload, run.secrets)
    return exit_code if status == "failed" else 0


def _check_cfe_result(run_root: Path, name: str) -> dict[str, Any]:
    extension_root = run_root / "extensions" / name
    summary_path = extension_root / "summary.json"
    summary: dict[str, Any] = {}
    if summary_path.is_file():
        loaded = json.loads(summary_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            summary = loaded
    return {
        "extension_name": name,
        "run_root": str(extension_root),
        "summary_json": str(summary_path),
        "stdout_log": str(extension_root / "stdout.log"),
        "stderr_log": str(extension_root / "stderr.log"),
        "designer_out_log": str(extension_root / DESIGNER_OUT_LOG),
        "diagnostics_count": summary.get("diagnostics_count"),
        "blocking_diagnostics_count": summary.get("blocking_diagnostics_count"),
        "inherited_diagnostics_count": summary.get("inherited_diagnostics_count"),
        "status": summary.get("status"),
    }


def _available_extensions(source_root: Path) -> list[str]:
    if not source_root.is_dir():
        return []
    return sorted(path.name for path in source_root.iterdir() if path.is_dir())


def select_cfe_extensions(
    profile: RuntimeProfile, source_root: Path, target: str, explicit: Sequence[str]
) -> tuple[list[str], str | None]:
    """Extensions for a CFE wrapper: target matrix set, explicit names, or every ``src/cfe`` directory."""
    names: list[str] = []
    for name in explicit:
        validate_extension_name(name)
        if name not in names:
            names.append(name)
    available = _available_extensions(source_root)
    if not available:
        raise CommandError(f"no extensions found under {source_root}")
    return resolve_target_extensions(
        project_root(), target, profile.string("target", "id"), names, available, source_root
    )


def run_check_cfe(command_id: str, argv: list[str]) -> int:
    """Check every selected extension with Designer; collect all failures instead of stopping at the first."""
    profile_input = ""
    run_root_input = ""
    target = ""
    explicit: list[str] = []
    dry_run = False
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in {"-h", "--help"}:
            print(CHECK_CFE_USAGE.format(command=command_id), end="")
            return 0
        if arg in {"--profile", "--run-root", "--extension", "--target"}:
            index += 1
            if index >= len(argv):
                raise CommandError(f"{arg} requires a value")
            if arg == "--profile":
                profile_input = argv[index]
            elif arg == "--run-root":
                run_root_input = argv[index]
            elif arg == "--target":
                target = argv[index]
            else:
                explicit.append(argv[index])
        elif arg == "--dry-run":
            dry_run = True
        else:
            raise CommandError(f"unknown argument: {arg}")
        index += 1
    profile = require_runtime_profile(load_runtime_profile(resolve_runtime_profile_path(profile_input)))
    source_root = project_root() / "src" / "cfe"
    names, target_id = select_cfe_extensions(profile, source_root, target, explicit)
    run_root = Path(run_root_input) if run_root_input else project_root() / ".artifacts" / command_id
    artifacts = prepare_run_artifacts(run_root)
    adapter = os.environ.get("RUNNER_ADAPTER") or profile.runner_adapter
    run = _CheckCfeRun(
        command_id, profile, artifacts.run_root, artifacts, profile_secret_values(profile), dry_run, adapter
    )
    for line in (
        f"profile={profile.path}",
        f"adapter={adapter}",
        f"source_root={source_root}",
        f"selected_extensions={' '.join(names)}",
    ):
        _append_line(artifacts.stdout_path, f"[{command_id}] {line}")
    started_at = timestamp_utc()
    exit_code = 0
    failed: list[str] = []
    interrupted = False
    lock: AbstractContextManager[object] = (
        nullcontext() if dry_run else project_runtime_lock(project_root(), command_id)
    )
    try:
        with lock:
            for name in names:
                extension_exit = _check_cfe_extension(run, name)
                if extension_exit:
                    failed.append(name)
                    exit_code = exit_code or extension_exit
    except KeyboardInterrupt:
        interrupted = True
    results = [_check_cfe_result(artifacts.run_root, name) for name in names]
    payload: dict[str, Any] = {
        "status": "failed" if failed else ("dry-run" if dry_run else "success"),
        "capability": {"id": command_id, "label": CHECK_CFE_LABELS[command_id]},
        "profile_path": str(profile.path),
        "run_root": str(artifacts.run_root),
        "started_at": started_at,
        "finished_at": timestamp_utc(),
        "exit_code": exit_code,
        "dry_run": dry_run,
        "adapter": adapter,
        "execution": {"source": f"{command_id}-wrapper", "strategy": CHECK_CFE_STRATEGIES[command_id]},
        "extension_source": {
            "root": str(source_root),
            "target_id": target_id,
            "selected_names": names,
            "failed_names": failed,
        },
        "failure": {"classification": CHECK_CFE_FAILURES[command_id], "extensions": failed} if failed else None,
        "diagnostics_count": sum(int(item["diagnostics_count"] or 0) for item in results),
        "results": results,
        "artifacts": {
            "summary_json": str(artifacts.summary_path),
            "stdout_log": str(artifacts.stdout_path),
            "stderr_log": str(artifacts.stderr_path),
        },
    }
    _redact_files(run.log_paths, run.secrets)
    if interrupted:
        publish_interrupted_summary(
            artifacts, payload, reason="operator cancellation", cleanup=lambda: None, secrets=run.secrets
        )
        return 130
    sanitize_artifact_logs(artifacts, run.secrets)
    publish_summary(artifacts, payload, run.secrets)
    return exit_code


VALUE_FLAGS = {
    "configure-cfe-runtime-flags": {
        "--safe-mode",
        "--unsafe-action-protection",
        "--active",
        "--security-profile-name",
    },
    "manage-cfe": {"--driver", "--source", "--list-file", "--output", "--file"},
}


def _require_yes_no(flag: str, value: str, *, allow_empty: bool = False) -> None:
    if value in {"yes", "no"} or (allow_empty and not value):
        return
    raise CommandError(f"{flag} must be yes or no")


def read_list_file(list_file: str, source: str) -> list[str]:
    """Relative paths for a partial Designer import; each stays inside the source directory."""
    list_path = Path(list_file)
    if not list_path.is_file():
        raise CommandError(f"list file not found: {list_file}")
    source_root = Path(source).resolve()
    entries: list[str] = []
    for raw in list_path.read_text(encoding="utf-8-sig").splitlines():
        entry = raw.strip().replace("\\", "/")
        if not entry:
            raise CommandError("empty entry in list file")
        if entry.startswith("/") or ":" in entry or ".." in entry.split("/"):
            raise CommandError(f"list entries must stay relative to the source directory: {entry}")
        resolved = (source_root / entry).resolve()
        if not resolved.is_relative_to(source_root):
            raise CommandError(f"selected file escapes the source directory: {entry}")
        if not resolved.is_file():
            raise CommandError(f"selected source file not found: {entry}")
        entries.append(entry)
    if not entries:
        raise CommandError("list file is empty")
    return entries


def validate_manage_cfe(action: str, extension: str, options: CfeOptions) -> None:
    if action not in MANAGE_CFE_ACTIONS:
        raise CommandError(
            f"unsupported manage-cfe action: {action or '<none>'}; use one of {', '.join(MANAGE_CFE_ACTIONS)}"
        )
    if options.driver not in {"ibcmd", "designer"}:
        raise CommandError(f"unsupported driver: {options.driver}")
    if options.driver == "designer" and (action not in DESIGNER_ACTIONS or not extension):
        raise CommandError("--driver designer requires import or apply with --extension")
    if action in EXTENSION_REQUIRED_ACTIONS and not extension:
        raise CommandError(f"{action} requires --extension <name>")
    if action == "import":
        if not options.source:
            raise CommandError("import requires --source <dir>")
        if not (Path(options.source) / "Configuration.xml").is_file():
            raise CommandError("source Configuration.xml not found")
    elif options.source:
        raise CommandError("--source is supported only for import")
    if options.list_file and (options.driver != "designer" or action != "import"):
        raise CommandError("--list-file requires Designer import")
    if action == "dump" and not options.output:
        raise CommandError("dump requires --output <dir>")
    if action != "dump" and options.output:
        raise CommandError("--output is supported only for dump")
    if action in {"load", "save"} and not options.file:
        raise CommandError(f"{action} requires --file <file>")
    if action not in {"load", "save"} and options.file:
        raise CommandError("--file is supported only for load or save")
    if action == "load" and not Path(options.file).is_file():
        raise CommandError(f"input file not found: {options.file}")


def run_cfe_command(command_id: str, argv: list[str]) -> int:
    if command_id not in CFE_COMMANDS:
        raise CommandError(f"unsupported CFE command: {command_id}")
    if command_id == "load-cfe":
        return run_load_cfe(argv)
    if command_id in CHECK_CFE_LABELS:
        return run_check_cfe(command_id, argv)
    profile_input = ""
    run_root_input = ""
    extension = ""
    action = ""
    dry_run = False
    options = CfeOptions()
    value_flags = VALUE_FLAGS.get(command_id, set())
    index = 0
    if command_id == "manage-cfe" and argv and not argv[0].startswith("-"):
        action = argv[0]
        index = 1
    while index < len(argv):
        arg = argv[index]
        if arg in {"--profile", "--run-root", "--extension"} or arg in value_flags:
            index += 1
            if index >= len(argv):
                raise CommandError(f"{arg} requires a value")
            value = argv[index]
            if arg == "--profile":
                profile_input = value
            elif arg == "--run-root":
                run_root_input = value
            elif arg == "--extension":
                extension = value
            else:
                setattr(options, arg[2:].replace("-", "_"), value)
        elif arg == "--clear-security-profile" and command_id == "configure-cfe-runtime-flags":
            options.clear_security_profile = True
        elif arg == "--via-designer" and command_id == "manage-cfe":
            options.driver = "designer"
        elif arg == "--dry-run":
            dry_run = True
        else:
            raise CommandError(f"unknown argument: {arg}")
        index += 1
    if command_id == "configure-cfe-runtime-flags":
        _require_yes_no("--safe-mode", options.safe_mode)
        _require_yes_no("--unsafe-action-protection", options.unsafe_action_protection)
        _require_yes_no("--active", options.active, allow_empty=True)
        if options.clear_security_profile and options.security_profile_name:
            raise CommandError("--clear-security-profile conflicts with --security-profile-name")
    if command_id == "manage-cfe":
        validate_manage_cfe(action, extension, options)
        if extension:
            validate_extension_name(extension)
    else:
        validate_extension_name(extension)
    profile = require_runtime_profile(load_runtime_profile(resolve_runtime_profile_path(profile_input)))
    run_root = Path(run_root_input) if run_root_input else project_root() / ".artifacts" / command_id
    selected_files = read_list_file(options.list_file, options.source) if options.list_file else []
    if selected_files:
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / IMPORT_LIST_FILE).write_text("\ufeff" + "\n".join(selected_files) + "\n", encoding="utf-8")
    commands = build_cfe_commands(
        command_id, profile, extension, action=action, dry_run=dry_run, options=options, run_root=run_root
    )
    context: dict[str, Any] = {"extension_name": extension or None, "action": action or None}
    if command_id == "configure-cfe-runtime-flags":
        context["requested_flags"] = {
            "safe_mode": options.safe_mode,
            "unsafe_action_protection": options.unsafe_action_protection,
            "active": options.active or None,
            "security_profile_name": "" if options.clear_security_profile else (options.security_profile_name or None),
        }
    if command_id == "manage-cfe":
        context["driver"] = options.driver
        if options.driver == "designer":
            context["designer_output_log"] = str(run_root.resolve() / DESIGNER_OUT_LOG)
        if selected_files:
            context["selected_files"] = selected_files
    return execute_profile_operation(
        command_id,
        profile,
        commands,
        run_root,
        dry_run=dry_run,
        context=context,
    )
