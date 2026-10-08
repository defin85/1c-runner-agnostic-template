"""Registration of a client-server infobase in the 1C cluster through ``rac`` after ``create-ib``.

``ibcmd infobase create`` creates the DBMS database but does not register the infobase in the
cluster. When the profile enables ``capabilities.createIb.registerInCluster``, create-ib registers it
with ``rac infobase create`` with scheduled jobs denied. An infobase with the same name is never
re-registered.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .runtime_process import run_process
from .runtime_profiles import RuntimeProfile
from .runtime_secrets import resolve_secret_value

RAC_TIMEOUT_SECONDS = 120
_FIELD_RE = re.compile(r"^\s*(?P<key>[\w-]+)\s*:\s*(?P<value>.*?)\s*$")


def cluster_registration_requested(profile: RuntimeProfile) -> bool:
    return profile.bool("capabilities", "createIb", "registerInCluster") is True


def cluster_registration_failure_reason(profile: RuntimeProfile) -> str:
    if profile.string("infobase", "mode") != "client-server":
        return "capabilities.createIb.registerInCluster requires infobase.mode=client-server"
    if profile.string("ibcmd", "runtimeMode") != "dbms-infobase":
        return "capabilities.createIb.registerInCluster requires ibcmd.runtimeMode=dbms-infobase"
    for keys in (("platform", "racPath"), ("cluster", "ras"), ("infobase", "ref")):
        if not profile.string(*keys):
            return f"capabilities.createIb.registerInCluster requires {'.'.join(keys)}"
    if profile.string("clusterAdmin", "user") and not profile.string("clusterAdmin", "passwordEnv"):
        return "clusterAdmin.user requires clusterAdmin.passwordEnv"
    return ""


def parse_rac_records(output: str) -> list[dict[str, str]]:
    """Split ``rac`` key/value output into records separated by blank lines."""
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in output.splitlines():
        if not line.strip():
            if current:
                records.append(current)
                current = {}
            continue
        match = _FIELD_RE.match(line)
        if match:
            value = match.group("value")
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
            current[match.group("key")] = value
    if current:
        records.append(current)
    return records


def _cluster_auth_args(profile: RuntimeProfile, *, dry_run: bool) -> list[str]:
    user = profile.string("clusterAdmin", "user")
    if not user:
        return []
    password = resolve_secret_value(profile.string("clusterAdmin", "passwordEnv"), dry_run=dry_run)
    return [f"--cluster-user={user}", f"--cluster-pwd={password}"]


def build_rac_create_command(profile: RuntimeProfile, cluster_uuid: str, *, dry_run: bool) -> list[str]:
    rac = profile.string("platform", "racPath")
    db_password = resolve_secret_value(profile.string("ibcmd", "dbmsInfobase", "passwordEnv"), dry_run=dry_run)
    return [
        rac,
        profile.string("cluster", "ras"),
        "infobase",
        "create",
        f"--cluster={cluster_uuid}",
        *_cluster_auth_args(profile, dry_run=dry_run),
        f"--name={profile.string('infobase', 'ref')}",
        f"--dbms={profile.string('ibcmd', 'dbmsInfobase', 'kind')}",
        f"--db-server={profile.string('ibcmd', 'dbmsInfobase', 'server')}",
        f"--db-name={profile.string('ibcmd', 'dbmsInfobase', 'name')}",
        f"--db-user={profile.string('ibcmd', 'dbmsInfobase', 'user')}",
        f"--db-pwd={db_password}",
        f"--locale={profile.string('ibcmd', 'locale') or 'ru_RU'}",
        "--descr=created-by=create-ib",
        "--scheduled-jobs-deny=on",
    ]


def _run_rac(command: Sequence[str], stdout_log: Path, stderr_log: Path) -> tuple[int, str]:
    result = run_process(command, timeout=RAC_TIMEOUT_SECONDS)
    with stdout_log.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(result.stdout)
    with stderr_log.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(result.stderr)
    return result.returncode, result.stdout


def _fail(stderr_log: Path, message: str, exit_code: int = 1) -> tuple[int, dict[str, Any]]:
    with stderr_log.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"[create-ib] cluster registration failed: {message}\n")
    return exit_code, {"status": "failed", "reason": message}


def register_infobase_in_cluster(
    profile: RuntimeProfile, stdout_log: Path, stderr_log: Path
) -> tuple[int, dict[str, Any]]:
    """Register the created infobase; return the exit code and the ``registration`` summary section."""
    reason = cluster_registration_failure_reason(profile)
    if reason:
        return _fail(stderr_log, reason, 2)
    rac = profile.string("platform", "racPath")
    ras = profile.string("cluster", "ras")
    ref = profile.string("infobase", "ref")
    code, output = _run_rac([rac, ras, "cluster", "list"], stdout_log, stderr_log)
    if code != 0:
        return _fail(stderr_log, f"rac cluster list exit code {code}", code)
    clusters = [record["cluster"] for record in parse_rac_records(output) if record.get("cluster")]
    if len(clusters) != 1:
        return _fail(stderr_log, f"expected exactly one cluster at {ras}, found {len(clusters)}")
    cluster_uuid = clusters[0]
    auth = _cluster_auth_args(profile, dry_run=False)
    code, output = _run_rac(
        [rac, ras, "infobase", "summary", "list", f"--cluster={cluster_uuid}", *auth], stdout_log, stderr_log
    )
    if code != 0:
        return _fail(stderr_log, f"rac infobase summary list exit code {code}", code)
    if any(record.get("name") == ref for record in parse_rac_records(output)):
        return _fail(stderr_log, f"refusing to register existing infobase: {ref}")
    code, output = _run_rac(build_rac_create_command(profile, cluster_uuid, dry_run=False), stdout_log, stderr_log)
    if code != 0:
        return _fail(stderr_log, f"rac infobase create exit code {code}", code)
    created = [record["infobase"] for record in parse_rac_records(output) if record.get("infobase")]
    infobase_uuid = created[0] if created else output.strip()
    if not infobase_uuid:
        return _fail(stderr_log, "rac did not return the registered infobase UUID")
    with stdout_log.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"[create-ib] registered ref={ref} uuid={infobase_uuid} cluster={cluster_uuid}\n")
    return 0, {
        "status": "registered",
        "ref": ref,
        "cluster_uuid": cluster_uuid,
        "infobase_uuid": infobase_uuid,
        "scheduled_jobs_denied": True,
    }
