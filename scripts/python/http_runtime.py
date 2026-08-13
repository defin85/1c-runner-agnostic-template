from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .common import CommandError, project_root, timestamp_utc
from .runtime_os import manage_service
from .runtime_process import ProcessResult, run_logged, run_process
from .runtime_profiles import load_runtime_profile, require_runtime_profile, resolve_runtime_profile_path
from .runtime_result import evaluate_postcondition, prepare_run_artifacts, publish_summary


@dataclass(frozen=True, slots=True)
class ApachePublication:
    webinst_path: str
    config_path: str
    directory: str
    descriptor: str
    name: str
    connection_string: str
    service_name: str
    url: str


def load_apache_publication(profile: Any) -> ApachePublication:
    capability = profile.get("capabilities", "publishHttp", default={})
    if not isinstance(capability, dict) or capability.get("backend") != "apache-webinst":
        raise CommandError("publishHttp requires backend=apache-webinst")
    fields = {key: capability.get(key) for key in ("webinstPath", "configPath", "directory", "descriptor", "name", "connectionString", "serviceName", "url")}
    missing = [key for key, value in fields.items() if not isinstance(value, str) or not value]
    if missing:
        raise CommandError("publishHttp apache-webinst is missing: " + ", ".join(missing))
    return ApachePublication(**{key.replace("webinstPath", "webinst_path").replace("configPath", "config_path").replace("connectionString", "connection_string").replace("serviceName", "service_name"): value for key, value in fields.items()})


def build_webinst_command(publication: ApachePublication) -> list[str]:
    return [publication.webinst_path, "-publish", "-apache24", "-wsdir", publication.name, "-descriptor", publication.descriptor, "-dir", publication.directory, "-connstr", publication.connection_string, "-confPath", publication.config_path]


def diagnostic_webinst_command(command: list[str]) -> list[str]:
    result = list(command)
    if "-connstr" in result:
        result[result.index("-connstr") + 1] = "__REDACTED__"
    return result


def default_http_probe(url: str, timeout: float = 10.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def default_service_pid(service_name: str) -> int | None:
    result = run_process(["sc.exe", "queryex", service_name])
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if "PID" not in line or ":" not in line:
            continue
        value = line.split(":", 1)[1].strip()
        return int(value) if value.isdigit() and int(value) > 0 else None
    return None


def run_publish_http(
    argv: list[str],
    *,
    service_manager: Callable[..., ProcessResult] = manage_service,
    http_probe: Callable[[str], bool] = default_http_probe,
    command_runner: Callable[..., int] = run_logged,
    service_pid: Callable[[str], int | None] = default_service_pid,
) -> int:
    profile_input = ""
    run_root_input = ""
    dry_run = False
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in {"--profile", "--run-root"}:
            index += 1
            if index >= len(argv): raise CommandError(f"{arg} requires a value")
            if arg == "--profile": profile_input = argv[index]
            else: run_root_input = argv[index]
        elif arg == "--dry-run": dry_run = True
        else: raise CommandError(f"unknown argument: {arg}")
        index += 1
    profile = require_runtime_profile(load_runtime_profile(resolve_runtime_profile_path(profile_input)))
    publication = load_apache_publication(profile)
    artifacts = prepare_run_artifacts(Path(run_root_input) if run_root_input else project_root() / ".artifacts" / "publish-http")
    command = build_webinst_command(publication)
    started_at = timestamp_utc()
    exit_code = 0
    service_exit = 0
    service_pid_before: int | None = None
    service_pid_after: int | None = None
    postcondition_reason = None
    if not dry_run:
        exit_code = command_runner(command, stdout_path=artifacts.stdout_path, stderr_path=artifacts.stderr_path, cwd=project_root())
        if exit_code == 0:
            service_pid_before = service_pid(publication.service_name)
            service_result = service_manager(publication.service_name, "restart")
            service_exit = service_result.returncode
            service_pid_after = service_pid(publication.service_name)
            if service_result.stderr:
                artifacts.stderr_path.write_text(service_result.stderr, encoding="utf-8")
        status, exit_code, postcondition_reason = evaluate_postcondition(
            lambda: service_exit == 0 and service_pid_after is not None and service_pid_after != service_pid_before and http_probe(publication.url),
            failure_message="Apache restart or HTTP readiness postcondition failed",
            tool_exit_code=exit_code,
        )
    else:
        status = "dry-run"
    publish_summary(artifacts, {
        "status": status,
        "capability": {"id": "publish-http"},
        "backend": "apache-webinst",
        "profile_path": str(profile.path),
        "started_at": started_at,
        "finished_at": timestamp_utc(),
        "exit_code": exit_code,
        "dry_run": dry_run,
        "publication": {"name": publication.name, "url": publication.url, "service_name": publication.service_name},
        "execution": {"command": diagnostic_webinst_command(command), "service_exit_code": service_exit, "service_pid_before": service_pid_before, "service_pid_after": service_pid_after},
        "postcondition_failure": postcondition_reason,
        "artifacts": {"summary_json": str(artifacts.summary_path), "stdout_log": str(artifacts.stdout_path), "stderr_log": str(artifacts.stderr_path)},
    })
    return exit_code
