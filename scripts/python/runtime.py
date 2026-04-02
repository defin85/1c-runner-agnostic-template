from __future__ import annotations

import json
import os
import shutil
import socket
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .common import (
    CommandError,
    WINDOWS,
    canonical_path,
    command_display,
    die,
    ensure_dir,
    log,
    project_root,
    read_json,
    repo_path,
    run_git,
    run_logged,
    run_process,
    timestamp_utc,
    unique_preserve_order,
    write_json,
)


LOCAL_SANDBOX_DIR = "env/.local/"
RUNTIME_POLICY_PATH = "automation/context/runtime-profile-policy.json"


CAPABILITY_KEY_MAP = {
    "create-ib": "createIb",
    "dump-src": "dumpSrc",
    "load-src": "loadSrc",
    "update-db": "updateDb",
    "diff-src": "diffSrc",
    "run-xunit": "xunit",
    "run-bdd": "bdd",
    "run-smoke": "smoke",
    "publish-http": "publishHttp",
}

DRIVER_CAPABILITIES = {"create-ib", "dump-src", "load-src", "update-db"}
VERIFICATION_CAPABILITIES = {"run-xunit", "run-bdd", "run-smoke", "publish-http"}


def capability_key(capability_id: str) -> str:
    try:
        return CAPABILITY_KEY_MAP[capability_id]
    except KeyError:
        die(f"unsupported capability id: {capability_id}")


def _require_type(value: Any, type_name: type | tuple[type, ...], field_name: str) -> Any:
    if not isinstance(value, type_name):
        die(f"runtime profile field has invalid type: {field_name}")
    return value


def _json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__


def _relative_to_repo(path: Path) -> str:
    try:
        return path.relative_to(project_root()).as_posix()
    except ValueError:
        return path.as_posix()


@dataclass(slots=True)
class RuntimeProfile:
    path: Path
    payload: dict[str, Any]
    name: str
    runner_adapter: str

    def get(self, *keys: str, default: Any = None) -> Any:
        cursor: Any = self.payload
        for key in keys:
            if not isinstance(cursor, dict):
                return default
            cursor = cursor.get(key, default)
        return cursor

    def has(self, *keys: str) -> bool:
        cursor: Any = self.payload
        for key in keys:
            if not isinstance(cursor, dict) or key not in cursor:
                return False
            cursor = cursor[key]
        return cursor is not None

    def string(self, *keys: str, default: str = "") -> str:
        value = self.get(*keys, default=default)
        if value is None:
            return default
        if not isinstance(value, str):
            die(
                "runtime profile field has invalid type: "
                + ".".join(keys)
                + f" ({_json_type_name(value)})"
            )
        return value

    def bool(self, *keys: str, default: bool | None = None) -> bool | None:
        value = self.get(*keys, default=default)
        if value is None:
            return default
        if not isinstance(value, bool):
            die(
                "runtime profile field has invalid type: "
                + ".".join(keys)
                + f" ({_json_type_name(value)})"
            )
        return value

    def array_strings(self, *keys: str) -> list[str]:
        value = self.get(*keys, default=[])
        if value is None:
            return []
        _require_type(value, list, ".".join(keys))
        result: list[str] = []
        for item in value:
            result.append(str(item))
        return result

    def require_string(self, *keys: str) -> str:
        label = ".".join(keys)
        value = self.string(*keys)
        if not value:
            die(f"runtime profile is missing {label} in {self.path}")
        return value


@dataclass(slots=True)
class CapabilityArgs:
    profile_input: str = ""
    run_root_input: str = ""
    dry_run: bool = False
    show_help: bool = False
    selected_files_input: str = ""


@dataclass(slots=True)
class PreparedCommand:
    capability_id: str
    label: str
    adapter: str
    driver: str = ""
    command_source: str = ""
    executor: str = "direct"
    command: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CapabilityResult:
    status: str
    exit_code: int
    summary_path: Path
    stdout_log: Path
    stderr_log: Path


def canonical_root_runtime_profile_filename(filename: str) -> bool:
    return filename in {
        "local.json",
        "wsl.json",
        "ci.json",
        "windows-executor.json",
        "windows-local.json",
        "local.example.json",
        "wsl.example.json",
        "ci.example.json",
        "windows-executor.example.json",
        "windows-local.example.json",
    }


def runtime_policy_file_path(root: Path | None = None) -> Path:
    return (root or project_root()) / RUNTIME_POLICY_PATH


def resolve_runtime_profile_path(requested_path: str = "", root: Path | None = None) -> Path | None:
    repo_root = root or project_root()
    resolved = requested_path or os.environ.get("ONEC_PROFILE", "")
    if not resolved:
        default_profile = repo_root / "env" / "local.json"
        if default_profile.is_file():
            return canonical_path(default_profile)
        return None
    return canonical_path(resolved)


def runtime_profile_migration_error(profile_path: Path) -> None:
    die(
        "runtime profile schemaVersion=1 is no longer supported: "
        f"{profile_path}. Migrate it with ./scripts/template/migrate-runtime-profile-v2.sh "
        "<legacy-profile> and see docs/migrations/runtime-profile-v2.md"
    )


def load_runtime_profile(profile_path: Path | None) -> RuntimeProfile | None:
    if profile_path is None:
        return None
    if not profile_path.is_file():
        die(f"runtime profile not found: {profile_path}")
    payload = read_json(profile_path)
    if not isinstance(payload, dict):
        die(f"runtime profile root must be an object: {profile_path}")
    schema_version = payload.get("schemaVersion")
    shell_env = payload.get("shellEnv")
    if schema_version == 1 or (schema_version is None and isinstance(shell_env, dict)):
        runtime_profile_migration_error(profile_path)
    if schema_version != 2:
        die(f"unsupported runtime profile schemaVersion={schema_version} in {profile_path}")
    runner_adapter = payload.get("runnerAdapter")
    if not isinstance(runner_adapter, str) or not runner_adapter:
        die(f"runtime profile is missing runnerAdapter in {profile_path}")
    name = payload.get("profileName")
    if name is None:
        name = ""
    elif not isinstance(name, str):
        die(f"runtime profile field has invalid type: profileName ({_json_type_name(name)})")
    return RuntimeProfile(
        path=canonical_path(profile_path),
        payload=payload,
        name=name,
        runner_adapter=runner_adapter,
    )


def require_runtime_profile(profile: RuntimeProfile | None) -> RuntimeProfile:
    if profile is None:
        die("runtime profile is required; pass --profile <file> or create env/local.json")
    return profile


def profile_answer_value(root: Path, key: str, default: str | None = None) -> str:
    answers_path = root / ".copier-answers.yml"
    if not answers_path.is_file():
        die(f"answers file not found: {answers_path}")
    prefix = f"{key}:"
    for line in answers_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith(prefix):
            continue
        value = line[len(prefix) :].strip()
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        if value.startswith("'") and value.endswith("'"):
            return value[1:-1]
        return value
    if default is not None:
        return default
    die(f"answers file does not contain {key}: {answers_path}")


def load_sanctioned_additional_root_runtime_profiles(root: Path | None = None) -> list[str]:
    repo_root = root or project_root()
    policy_path = runtime_policy_file_path(repo_root)
    if not policy_path.is_file():
        return []
    payload = read_json(policy_path)
    entries = payload.get("rootEnvProfiles", {}).get("sanctionedAdditionalProfiles", [])
    if not isinstance(entries, list):
        die("rootEnvProfiles.sanctionedAdditionalProfiles must be an array")
    result: list[str] = []
    for entry in entries:
        candidate = str(entry)
        if not candidate.startswith("env/") or not candidate.endswith(".json"):
            die(f"runtime-profile policy lists a non env/*.json path: {candidate}")
        result.append(candidate)
    return unique_preserve_order(result)


def collect_runtime_profile_layout_drift_paths(root: Path | None = None) -> list[str]:
    repo_root = root or project_root()
    env_root = repo_root / "env"
    if not env_root.is_dir():
        return []
    sanctioned = set(load_sanctioned_additional_root_runtime_profiles(repo_root))
    result: list[str] = []
    for path in sorted(env_root.glob("*.json")):
        rel = f"env/{path.name}"
        if canonical_root_runtime_profile_filename(path.name):
            continue
        if rel in sanctioned:
            continue
        result.append(rel)
    return result


def build_runtime_profile_layout_warning_json(root: Path | None = None) -> dict[str, Any]:
    repo_root = root or project_root()
    sanctioned = load_sanctioned_additional_root_runtime_profiles(repo_root)
    unexpected = collect_runtime_profile_layout_drift_paths(repo_root)
    return {
        "runtime_profile_layout": {
            "status": "warning" if unexpected else "clean",
            "unexpected_root_profiles": unexpected,
            "recommended_sandbox": LOCAL_SANDBOX_DIR,
            "policy_path": RUNTIME_POLICY_PATH,
            "sanctioned_additional_profiles": sanctioned,
        }
    }


def parse_capability_cli_args(argv: list[str], allow_files: bool = True) -> CapabilityArgs:
    result = CapabilityArgs(dry_run=os.environ.get("DRY_RUN", "0") == "1")
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in {"-h", "--help"}:
            result.show_help = True
            index += 1
            continue
        if arg == "--profile":
            index += 1
            if index >= len(argv):
                die("--profile requires a value")
            result.profile_input = argv[index]
            index += 1
            continue
        if arg == "--run-root":
            index += 1
            if index >= len(argv):
                die("--run-root requires a value")
            result.run_root_input = argv[index]
            index += 1
            continue
        if arg == "--dry-run":
            result.dry_run = True
            index += 1
            continue
        if arg == "--files":
            if not allow_files:
                die("--files is not supported for this command")
            index += 1
            if index >= len(argv):
                die("--files requires a value")
            result.selected_files_input = argv[index]
            index += 1
            continue
        die(f"unknown argument: {arg}")
    return result


def capability_help_requested(argv: list[str]) -> bool:
    return any(arg in {"-h", "--help"} for arg in argv)


def prepare_capability_run_root(capability_id: str, requested_root: str = "") -> Path:
    if requested_root:
        return ensure_dir(requested_root)
    artifacts_root = ensure_dir(project_root() / ".artifacts" / capability_id)
    return Path(tempfile.mkdtemp(prefix=f"{capability_id}-", dir=artifacts_root))


def capability_summary_path(run_root: Path) -> Path:
    return run_root / "summary.json"


def normalize_capability_selected_file(value: str) -> str:
    candidate = value.replace("\\", "/").strip()
    if not candidate:
        die("--files must not contain empty entries")
    if candidate.startswith("/"):
        die(f"--files entries must be relative to the configured source tree: {value}")
    stack: list[str] = []
    for segment in candidate.split("/"):
        if segment in {"", "."}:
            continue
        if segment == "..":
            if not stack:
                die(f"--files entries must stay within the configured source tree: {value}")
            stack.pop()
            continue
        stack.append(segment)
    if not stack:
        die(f"--files entries must point to files within the configured source tree: {value}")
    return "/".join(stack)


def load_capability_selected_files(csv_value: str) -> list[str]:
    if not csv_value:
        return []
    return [normalize_capability_selected_file(item) for item in csv_value.split(",")]


def resolve_project_tree_path(candidate: str) -> Path:
    if os.path.isabs(candidate):
        return canonical_path(candidate)
    return canonical_path(project_root() / candidate)


def resolve_secret_value(env_name: str, dry_run: bool = False) -> str:
    if not env_name:
        return ""
    value = os.environ.get(env_name, "")
    if value:
        return value
    if dry_run:
        return "__REDACTED_SECRET__"
    die(f"required secret env var is not set: {env_name}")


def normalize_repo_command_tokens(command: list[str]) -> list[str]:
    normalized: list[str] = []
    for token in command:
        if token.startswith("./") and (project_root() / token[2:]).exists():
            normalized.append(str(project_root() / token[2:]))
        else:
            normalized.append(token)
    return normalized


def build_redacted_context(profile: RuntimeProfile | None) -> dict[str, Any]:
    if profile is None:
        return {}
    return {
        "runtime_profile": {
            "name": profile.name or None,
        },
        "infobase": {
            "mode": profile.string("infobase", "mode") or None,
            "server": profile.string("infobase", "server") or None,
            "ref": profile.string("infobase", "ref") or None,
            "file_path": profile.string("infobase", "filePath") or None,
            "auth_mode": profile.string("infobase", "auth", "mode", default="os") or None,
        },
    }


def direct_platform_xvfb_enabled(profile: RuntimeProfile) -> bool:
    return bool(profile.bool("platform", "xvfb", "enabled", default=False))


def direct_platform_ld_preload_enabled(profile: RuntimeProfile) -> bool:
    return bool(profile.bool("platform", "ldPreload", "enabled", default=False))


def load_direct_platform_xvfb_server_args(profile: RuntimeProfile) -> list[str]:
    if not direct_platform_xvfb_enabled(profile):
        return []
    return profile.array_strings("platform", "xvfb", "serverArgs")


def load_direct_platform_ld_preload_libraries(profile: RuntimeProfile) -> list[str]:
    if not direct_platform_ld_preload_enabled(profile):
        return []
    return profile.array_strings("platform", "ldPreload", "libraries")


def command_targets_local_platform_gui(command_path: str) -> bool:
    name = Path(command_path).name.lower()
    return name in {"1cv8", "1cv8c", "1cv8.exe", "1cv8c.exe"}


def direct_platform_adapter_context(profile: RuntimeProfile) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if direct_platform_xvfb_enabled(profile):
        result["wrapper"] = "xvfb-run"
        result["xvfb"] = {
            "enabled": True,
            "server_args": load_direct_platform_xvfb_server_args(profile),
        }
    if direct_platform_ld_preload_enabled(profile):
        result["ld_preload"] = {
            "enabled": True,
            "libraries": load_direct_platform_ld_preload_libraries(profile),
        }
    if not result:
        return {}
    return {"adapter_context": result}


def build_capability_context(profile: RuntimeProfile, adapter: str, command: list[str]) -> dict[str, Any]:
    context = build_redacted_context(profile)
    if adapter == "direct-platform" and command and command_targets_local_platform_gui(command[0]):
        context.update(direct_platform_adapter_context(profile))
    return context


def build_unsupported_capability_context(profile: RuntimeProfile, reason: str) -> dict[str, Any]:
    context = build_redacted_context(profile)
    context["unsupported"] = {
        "placeholder": True,
        "reason": reason,
    }
    return context


def profile_command(profile: RuntimeProfile, capability_id: str) -> list[str] | None:
    value = profile.get("capabilities", capability_key(capability_id), "command")
    if value is None:
        return None
    if not isinstance(value, list):
        die(
            "runtime profile field must be an array: "
            f".capabilities.{capability_key(capability_id)}.command"
        )
    result = [str(item) for item in value]
    if not result:
        die(
            "runtime profile capability command must not be empty: "
            f".capabilities.{capability_key(capability_id)}.command"
        )
    return result


def profile_unsupported_reason(profile: RuntimeProfile, capability_id: str) -> str | None:
    value = profile.get("capabilities", capability_key(capability_id), "unsupportedReason")
    if value is None:
        return None
    if not isinstance(value, str):
        die(
            "runtime profile field has invalid type: "
            f".capabilities.{capability_key(capability_id)}.unsupportedReason"
        )
    if not value:
        die(
            "runtime profile field must not be empty: "
            f".capabilities.{capability_key(capability_id)}.unsupportedReason"
        )
    return value


def capability_supports_driver_selection(capability_id: str) -> bool:
    return capability_id in DRIVER_CAPABILITIES


def validate_capability_command_driver_contract(profile: RuntimeProfile, capability_id: str) -> None:
    key = capability_key(capability_id)
    capability_payload = profile.get("capabilities", key, default={})
    if capability_payload is None:
        capability_payload = {}
    if not isinstance(capability_payload, dict):
        die(f"runtime profile field has invalid type: .capabilities.{key}")
    has_command = "command" in capability_payload and capability_payload["command"] is not None
    has_driver = "driver" in capability_payload and capability_payload["driver"] is not None
    has_unsupported = (
        "unsupportedReason" in capability_payload and capability_payload["unsupportedReason"] is not None
    )
    if has_command and has_driver:
        die(f"capability {capability_id} must not define both driver and command in {profile.path}")
    if has_command and has_unsupported:
        die(
            f"capability {capability_id} must not define both command and unsupportedReason in {profile.path}"
        )
    if has_driver and has_unsupported:
        die(
            f"capability {capability_id} must not define both driver and unsupportedReason in {profile.path}"
        )
    if has_driver and not capability_supports_driver_selection(capability_id):
        die(f"capability {capability_id} does not support driver selection in {profile.path}")


def resolve_capability_driver(profile: RuntimeProfile, capability_id: str) -> str:
    validate_capability_command_driver_contract(profile, capability_id)
    if not capability_supports_driver_selection(capability_id):
        return ""
    driver = profile.string("capabilities", capability_key(capability_id), "driver")
    if not driver:
        return "designer"
    if driver not in {"designer", "ibcmd"}:
        die(f"unsupported driver={driver} for capability {capability_id} in {profile.path}")
    return driver


def infobase_mode(profile: RuntimeProfile) -> str:
    return profile.require_string("infobase", "mode")


def platform_binary_path(profile: RuntimeProfile) -> str:
    return profile.require_string("platform", "binaryPath")


def ibcmd_binary_path(profile: RuntimeProfile) -> str:
    return profile.require_string("platform", "ibcmdPath")


def append_connection_args(profile: RuntimeProfile, args: list[str]) -> None:
    override = profile.string("infobase", "connectionStringOverride")
    if override:
        args.extend(["/IBConnectionString", override])
        return
    mode = infobase_mode(profile)
    if mode == "file":
        args.extend(["/F", profile.require_string("infobase", "filePath")])
        return
    if mode == "client-server":
        server = profile.require_string("infobase", "server")
        ref = profile.require_string("infobase", "ref")
        args.extend(["/S", f"{server}/{ref}"])
        return
    die(f"unsupported infobase.mode={mode} in {profile.path}")


def append_auth_args(profile: RuntimeProfile, args: list[str], *, dry_run: bool) -> None:
    auth_mode = profile.string("infobase", "auth", "mode", default="os")
    if auth_mode == "os":
        args.append("/WA+")
        return
    if auth_mode == "user-password":
        user = profile.require_string("infobase", "auth", "user")
        password_env = profile.require_string("infobase", "auth", "passwordEnv")
        password = resolve_secret_value(password_env, dry_run=dry_run)
        args.extend(["/WA-", "/N", user, "/P", password])
        return
    die(f"unsupported infobase.auth.mode={auth_mode} in {profile.path}")


def build_create_infobase_connection_string(profile: RuntimeProfile, *, dry_run: bool) -> str:
    override = profile.string("infobase", "connectionStringOverride")
    if override:
        return override
    mode = infobase_mode(profile)
    if mode == "file":
        file_path = profile.require_string("infobase", "filePath").replace('"', '""')
        return f'File="{file_path}"'
    if mode == "client-server":
        server = profile.require_string("infobase", "server").replace('"', '""')
        ref = profile.require_string("infobase", "ref").replace('"', '""')
        auth_mode = profile.string("infobase", "auth", "mode", default="os")
        result = f'Srvr="{server}";Ref="{ref}"'
        if auth_mode == "user-password":
            user = profile.require_string("infobase", "auth", "user").replace('"', '""')
            password_env = profile.require_string("infobase", "auth", "passwordEnv")
            password = resolve_secret_value(password_env, dry_run=dry_run).replace('"', '""')
            result += f';Usr="{user}";Pwd="{password}"'
        return result
    die(f"unsupported infobase.mode={mode} in {profile.path}")


def build_designer_command(profile: RuntimeProfile, *extra: str, dry_run: bool) -> list[str]:
    result = [platform_binary_path(profile), "DESIGNER"]
    append_connection_args(profile, result)
    append_auth_args(profile, result, dry_run=dry_run)
    result.extend(extra)
    return result


def ibcmd_runtime_mode(profile: RuntimeProfile) -> str:
    return profile.require_string("ibcmd", "runtimeMode")


def ibcmd_server_access_mode(profile: RuntimeProfile) -> str:
    return profile.require_string("ibcmd", "serverAccess", "mode")


def ibcmd_server_access_data_dir(profile: RuntimeProfile) -> str:
    return profile.require_string("ibcmd", "serverAccess", "dataDir")


def append_ibcmd_server_access_args(profile: RuntimeProfile, args: list[str]) -> None:
    access_mode = ibcmd_server_access_mode(profile)
    if access_mode != "data-dir":
        die(f"unsupported ibcmd.serverAccess.mode={access_mode} in {profile.path}")
    args.append(f"--data={ibcmd_server_access_data_dir(profile)}")


def append_ibcmd_target_args(profile: RuntimeProfile, args: list[str], *, dry_run: bool) -> None:
    runtime_mode = ibcmd_runtime_mode(profile)
    if runtime_mode == "standalone-server":
        args.append(f"--database-path={profile.require_string('ibcmd', 'standalone', 'databasePath')}")
        return
    if runtime_mode == "file-infobase":
        args.append(f"--database-path={profile.require_string('ibcmd', 'fileInfobase', 'databasePath')}")
        return
    if runtime_mode == "dbms-infobase":
        password_env = profile.require_string("ibcmd", "dbmsInfobase", "passwordEnv")
        password = resolve_secret_value(password_env, dry_run=dry_run)
        args.extend(
            [
                f"--dbms={profile.require_string('ibcmd', 'dbmsInfobase', 'kind')}",
                f"--db-server={profile.require_string('ibcmd', 'dbmsInfobase', 'server')}",
                f"--db-name={profile.require_string('ibcmd', 'dbmsInfobase', 'name')}",
                f"--db-user={profile.require_string('ibcmd', 'dbmsInfobase', 'user')}",
                f"--db-pwd={password}",
            ]
        )
        return
    die(f"unsupported ibcmd.runtimeMode={runtime_mode} in {profile.path}")


def append_ibcmd_infobase_auth_args(profile: RuntimeProfile, args: list[str], *, dry_run: bool) -> None:
    user = profile.require_string("ibcmd", "auth", "user")
    password_env = profile.require_string("ibcmd", "auth", "passwordEnv")
    password = resolve_secret_value(password_env, dry_run=dry_run)
    args.extend([f"--user={user}", f"--password={password}"])


def ibcmd_capability_failure_reason(profile: RuntimeProfile, capability_id: str, adapter: str) -> str:
    if adapter != "direct-platform":
        return "ibcmd driver is supported only with runnerAdapter=direct-platform"
    if not profile.has("platform", "ibcmdPath"):
        return "missing platform.ibcmdPath"
    runtime_mode = profile.string("ibcmd", "runtimeMode")
    if not runtime_mode:
        return "missing ibcmd.runtimeMode"
    if runtime_mode not in {"standalone-server", "file-infobase", "dbms-infobase"}:
        return (
            f"ibcmd.runtimeMode={runtime_mode} is unsupported; use standalone-server, "
            "file-infobase, or dbms-infobase"
        )
    access_mode = profile.string("ibcmd", "serverAccess", "mode")
    if not access_mode:
        return "missing ibcmd.serverAccess.mode"
    if access_mode != "data-dir":
        return (
            f"ibcmd.serverAccess.mode={access_mode} is unsupported in the current release; "
            "use data-dir"
        )
    if not profile.has("ibcmd", "serverAccess", "dataDir"):
        return "missing ibcmd.serverAccess.dataDir"
    if runtime_mode == "standalone-server" and not profile.has("ibcmd", "standalone", "databasePath"):
        return "missing ibcmd.standalone.databasePath"
    if runtime_mode == "file-infobase" and not profile.has("ibcmd", "fileInfobase", "databasePath"):
        return "missing ibcmd.fileInfobase.databasePath"
    if runtime_mode == "dbms-infobase":
        required = [
            ("kind", "missing ibcmd.dbmsInfobase.kind"),
            ("server", "missing ibcmd.dbmsInfobase.server"),
            ("name", "missing ibcmd.dbmsInfobase.name"),
            ("user", "missing ibcmd.dbmsInfobase.user"),
            ("passwordEnv", "missing ibcmd.dbmsInfobase.passwordEnv"),
        ]
        for key, message in required:
            if not profile.has("ibcmd", "dbmsInfobase", key):
                return message
    if capability_id in {"dump-src", "load-src", "update-db"}:
        if not profile.has("ibcmd", "auth", "user"):
            return "missing ibcmd.auth.user"
        if not profile.has("ibcmd", "auth", "passwordEnv"):
            return "missing ibcmd.auth.passwordEnv"
    return ""


def windows_direct_platform_failure_reason(profile: RuntimeProfile, adapter: str, command_path: str) -> str:
    if not WINDOWS or adapter != "direct-platform" or not command_targets_local_platform_gui(command_path):
        return ""
    if direct_platform_xvfb_enabled(profile):
        return "platform.xvfb is supported only on POSIX direct-platform contours"
    if direct_platform_ld_preload_enabled(profile):
        return "platform.ldPreload is supported only on POSIX direct-platform contours"
    return ""


def posix_direct_platform_failure_reason(profile: RuntimeProfile, adapter: str, command_path: str) -> str:
    if WINDOWS or adapter != "direct-platform" or not command_targets_local_platform_gui(command_path):
        return ""
    if direct_platform_xvfb_enabled(profile):
        for tool in ("xvfb-run", "xauth"):
            if not shutil.which(tool):
                return f"missing {tool} for direct-platform xvfb wrapper"
    if direct_platform_ld_preload_enabled(profile):
        libraries = load_direct_platform_ld_preload_libraries(profile)
        if not libraries:
            return "platform.ldPreload.libraries must not be empty for direct-platform ld-preload contour"
        for library_path in libraries:
            library = Path(library_path)
            if not library.is_absolute():
                return f"direct-platform ld-preload library path must be absolute: {library_path}"
            if not library.exists():
                return f"missing direct-platform ld-preload library: {library_path}"
    return ""


def capability_command_failure_reason(profile: RuntimeProfile, adapter: str, command: list[str]) -> str:
    if not command:
        return ""
    reason = windows_direct_platform_failure_reason(profile, adapter, command[0])
    if reason:
        return reason
    return posix_direct_platform_failure_reason(profile, adapter, command[0])


def collect_required_env_refs(profile: RuntimeProfile) -> list[str]:
    refs: list[str] = []
    for path in [
        ("dbms", "passwordEnv"),
        ("clusterAdmin", "passwordEnv"),
    ]:
        value = profile.string(*path)
        if value:
            refs.append(value)
    for capability_id in DRIVER_CAPABILITIES:
        if profile_command(profile, capability_id) or profile_unsupported_reason(profile, capability_id):
            continue
        driver = resolve_capability_driver(profile, capability_id)
        if driver == "designer" and profile.string("infobase", "auth", "mode", default="os") == "user-password":
            refs.append(profile.string("infobase", "auth", "passwordEnv"))
        if driver == "ibcmd":
            if profile.string("ibcmd", "runtimeMode") == "dbms-infobase":
                refs.append(profile.string("ibcmd", "dbmsInfobase", "passwordEnv"))
            if capability_id in {"dump-src", "load-src", "update-db"}:
                refs.append(profile.string("ibcmd", "auth", "passwordEnv"))
    return [item for item in unique_preserve_order(refs) if item]


def collect_required_profile_fields(profile: RuntimeProfile, adapter: str) -> list[str]:
    fields = ["runnerAdapter"]
    if adapter not in {"direct-platform", "remote-windows", "vrunner"}:
        return fields
    for capability_id in DRIVER_CAPABILITIES:
        if profile_command(profile, capability_id) or profile_unsupported_reason(profile, capability_id):
            continue
        driver = resolve_capability_driver(profile, capability_id)
        if driver == "designer":
            fields.extend(["platform.binaryPath", "infobase.mode"])
            mode = profile.string("infobase", "mode")
            if mode == "file":
                fields.append("infobase.filePath")
            elif mode == "client-server":
                fields.extend(["infobase.server", "infobase.ref"])
            if profile.string("infobase", "auth", "mode", default="os") == "user-password":
                fields.extend(["infobase.auth.user", "infobase.auth.passwordEnv"])
        elif driver == "ibcmd":
            fields.extend(
                [
                    "platform.ibcmdPath",
                    "ibcmd.runtimeMode",
                    "ibcmd.serverAccess.mode",
                    "ibcmd.serverAccess.dataDir",
                ]
            )
            runtime_mode = profile.string("ibcmd", "runtimeMode")
            if runtime_mode == "standalone-server":
                fields.append("ibcmd.standalone.databasePath")
            elif runtime_mode == "file-infobase":
                fields.append("ibcmd.fileInfobase.databasePath")
            elif runtime_mode == "dbms-infobase":
                fields.extend(
                    [
                        "ibcmd.dbmsInfobase.kind",
                        "ibcmd.dbmsInfobase.server",
                        "ibcmd.dbmsInfobase.name",
                        "ibcmd.dbmsInfobase.user",
                        "ibcmd.dbmsInfobase.passwordEnv",
                    ]
                )
            if capability_id in {"dump-src", "load-src", "update-db"}:
                fields.extend(["ibcmd.auth.user", "ibcmd.auth.passwordEnv"])
    if adapter == "direct-platform" and direct_platform_xvfb_enabled(profile):
        fields.extend(["platform.xvfb.enabled", "platform.xvfb.serverArgs"])
    if adapter == "direct-platform" and direct_platform_ld_preload_enabled(profile):
        fields.extend(["platform.ldPreload.enabled", "platform.ldPreload.libraries"])
    return unique_preserve_order(fields)


def doctor_capability_failure_reason(profile: RuntimeProfile, capability_id: str, adapter: str) -> str:
    reason = profile_unsupported_reason(profile, capability_id)
    if reason:
        return reason
    override = profile_command(profile, capability_id)
    if override:
        return capability_command_failure_reason(profile, adapter, normalize_repo_command_tokens(override))
    if capability_id in DRIVER_CAPABILITIES:
        driver = resolve_capability_driver(profile, capability_id)
        if driver == "designer":
            if adapter not in {"direct-platform", "remote-windows"}:
                return f"driver=designer is unsupported with runnerAdapter={adapter}"
            if not profile.string("platform", "binaryPath"):
                return "missing platform.binaryPath"
            mode = profile.string("infobase", "mode")
            if not mode:
                return "missing infobase.mode"
            if mode == "file" and not profile.has("infobase", "filePath"):
                return "missing infobase.filePath for infobase.mode=file"
            if mode == "client-server":
                if not profile.has("infobase", "server"):
                    return "missing infobase.server for infobase.mode=client-server"
                if not profile.has("infobase", "ref"):
                    return "missing infobase.ref for infobase.mode=client-server"
            if mode not in {"file", "client-server"}:
                return f"unsupported infobase.mode={mode}"
            auth_mode = profile.string("infobase", "auth", "mode", default="os")
            if auth_mode == "user-password":
                if not profile.has("infobase", "auth", "user"):
                    return "missing infobase.auth.user for infobase.auth.mode=user-password"
                if not profile.has("infobase", "auth", "passwordEnv"):
                    return "missing infobase.auth.passwordEnv for infobase.auth.mode=user-password"
            elif auth_mode != "os":
                return f"unsupported infobase.auth.mode={auth_mode}"
            return capability_command_failure_reason(profile, adapter, [platform_binary_path(profile)])
        if driver == "ibcmd":
            return ibcmd_capability_failure_reason(profile, capability_id, adapter)
        return f"unsupported driver={driver} for capability {capability_id}"
    if capability_id == "diff-src":
        return ""
    if capability_id in VERIFICATION_CAPABILITIES:
        return f"missing .capabilities.{capability_key(capability_id)}.command"
    return f"unsupported capability id: {capability_id}"


def capability_string_or_default(
    profile: RuntimeProfile,
    capability_id: str,
    field_name: str,
    default_value: str,
) -> str:
    value = profile.string("capabilities", capability_key(capability_id), field_name)
    return value or default_value


def prepare_ibcmd_command(
    profile: RuntimeProfile,
    capability_id: str,
    adapter: str,
    selected_files: list[str],
    *,
    dry_run: bool,
) -> PreparedCommand:
    reason = ibcmd_capability_failure_reason(profile, capability_id, adapter)
    if reason:
        die(reason)
    binary_path = ibcmd_binary_path(profile)
    command: list[str]
    partial_import = False
    if capability_id == "create-ib":
        command = [binary_path, "infobase", "create"]
        append_ibcmd_server_access_args(profile, command)
        append_ibcmd_target_args(profile, command, dry_run=dry_run)
        command.append("--create-database")
    elif capability_id == "dump-src":
        output_dir = resolve_project_tree_path(
            capability_string_or_default(profile, capability_id, "outputDir", "./src/cf")
        )
        command = [binary_path, "config", "export"]
        append_ibcmd_server_access_args(profile, command)
        append_ibcmd_target_args(profile, command, dry_run=dry_run)
        append_ibcmd_infobase_auth_args(profile, command, dry_run=dry_run)
        command.append(str(output_dir))
    elif capability_id == "load-src":
        source_dir = resolve_project_tree_path(
            capability_string_or_default(profile, capability_id, "sourceDir", "./src/cf")
        )
        if selected_files:
            partial_import = True
            command = [binary_path, "config", "import", "files"]
            append_ibcmd_server_access_args(profile, command)
            append_ibcmd_target_args(profile, command, dry_run=dry_run)
            append_ibcmd_infobase_auth_args(profile, command, dry_run=dry_run)
            command.extend([f"--base-dir={source_dir}", "--partial", *selected_files])
        else:
            command = [binary_path, "config", "import"]
            append_ibcmd_server_access_args(profile, command)
            append_ibcmd_target_args(profile, command, dry_run=dry_run)
            append_ibcmd_infobase_auth_args(profile, command, dry_run=dry_run)
            command.append(str(source_dir))
    elif capability_id == "update-db":
        command = [binary_path, "config", "apply"]
        append_ibcmd_server_access_args(profile, command)
        append_ibcmd_target_args(profile, command, dry_run=dry_run)
        append_ibcmd_infobase_auth_args(profile, command, dry_run=dry_run)
        command.append("--force")
    else:
        die(f"unsupported ibcmd capability: {capability_id}")
    return PreparedCommand(
        capability_id=capability_id,
        label="",
        adapter=adapter,
        driver="ibcmd",
        command_source="ibcmd-builder",
        executor="adapter-wrapper" if not WINDOWS else "direct",
        command=command,
        context=build_redacted_context(profile)
        | {
            "driver_context": {
                "runtime_mode": profile.string("ibcmd", "runtimeMode") or None,
                "server_access": {
                    "mode": profile.string("ibcmd", "serverAccess", "mode") or None,
                    "data_dir": profile.string("ibcmd", "serverAccess", "dataDir") or None,
                },
                "partial_import": partial_import,
            }
        },
    )


def prepare_standard_capability_command(
    profile: RuntimeProfile,
    capability_id: str,
    label: str,
    adapter: str,
    selected_files: list[str],
    *,
    dry_run: bool,
) -> PreparedCommand:
    if selected_files and capability_id != "load-src":
        die(f"capability {capability_id} does not support --files")
    reason = profile_unsupported_reason(profile, capability_id)
    if reason:
        return PreparedCommand(
            capability_id=capability_id,
            label=label,
            adapter=adapter,
            command_source="unsupported-profile",
            executor="builtin-unsupported",
            command=[reason],
            context=build_unsupported_capability_context(profile, reason),
        )
    override = profile_command(profile, capability_id)
    if override:
        normalized = normalize_repo_command_tokens(override)
        executor = "direct"
        if not WINDOWS and adapter == "direct-platform" and normalized and command_targets_local_platform_gui(normalized[0]):
            executor = "adapter-wrapper"
        return PreparedCommand(
            capability_id=capability_id,
            label=label,
            adapter=adapter,
            command_source="profile-command",
            executor=executor,
            command=normalized,
            context=build_capability_context(profile, adapter, normalized),
        )
    if capability_id == "diff-src":
        command = ["git", "diff", "--", "./src"]
        return PreparedCommand(
            capability_id=capability_id,
            label=label,
            adapter=adapter,
            command_source="builtin-command",
            executor="direct",
            command=normalize_repo_command_tokens(command),
            context=build_redacted_context(profile),
        )
    if capability_id in DRIVER_CAPABILITIES:
        driver = resolve_capability_driver(profile, capability_id)
        if capability_id == "load-src" and selected_files and driver != "ibcmd":
            die("partial load-src is supported only for ibcmd driver")
        if driver == "ibcmd":
            result = prepare_ibcmd_command(profile, capability_id, adapter, selected_files, dry_run=dry_run)
            result.label = label
            return result
        if adapter not in {"direct-platform", "remote-windows"}:
            die(
                f"capability {capability_id} requires capabilities.{capability_key(capability_id)}.command "
                f"for adapter {adapter}"
            )
        if capability_id == "create-ib":
            command = [platform_binary_path(profile), "CREATEINFOBASE", build_create_infobase_connection_string(profile, dry_run=dry_run)]
        elif capability_id == "dump-src":
            output_dir = resolve_project_tree_path(
                capability_string_or_default(profile, capability_id, "outputDir", "./src/cf")
            )
            command = build_designer_command(profile, "/DumpConfigToFiles", str(output_dir), dry_run=dry_run)
        elif capability_id == "load-src":
            source_dir = resolve_project_tree_path(
                capability_string_or_default(profile, capability_id, "sourceDir", "./src/cf")
            )
            command = build_designer_command(profile, "/LoadConfigFromFiles", str(source_dir), dry_run=dry_run)
        elif capability_id == "update-db":
            command = build_designer_command(profile, "/UpdateDBCfg", dry_run=dry_run)
        else:
            die(f"unsupported capability id: {capability_id}")
        return PreparedCommand(
            capability_id=capability_id,
            label=label,
            adapter=adapter,
            driver="designer",
            command_source="standard-builder",
            executor="adapter-wrapper" if not WINDOWS else "direct",
            command=command,
            context=build_capability_context(profile, adapter, command),
        )
    if capability_id in VERIFICATION_CAPABILITIES:
        die(
            f"runtime profile is missing .capabilities.{capability_key(capability_id)}.command in {profile.path}"
        )
    die(f"unsupported capability id: {capability_id}")


def write_capability_summary(
    prepared: PreparedCommand,
    profile: RuntimeProfile,
    run_root: Path,
    stdout_log: Path,
    stderr_log: Path,
    status: str,
    exit_code: int,
    started_at: str,
    finished_at: str,
    dry_run: bool,
    summary_path: Path,
) -> None:
    payload = {
        "status": status,
        "capability": {
            "id": prepared.capability_id,
            "label": prepared.label,
        },
        "adapter": prepared.adapter,
        "driver": prepared.driver or None,
        "profile_path": str(profile.path),
        "run_root": str(run_root),
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_code": exit_code,
        "dry_run": dry_run,
        "execution": {
            "source": prepared.command_source,
            "executor": prepared.executor,
        },
        "artifacts": {
            "summary_json": str(summary_path),
            "stdout_log": str(stdout_log),
            "stderr_log": str(stderr_log),
        },
    }
    payload.update(prepared.context)
    write_json(summary_path, payload)


def execute_prepared_capability_command(
    prepared: PreparedCommand,
    profile: RuntimeProfile,
    run_root: Path,
    stdout_log: Path,
    stderr_log: Path,
) -> int:
    if prepared.executor == "builtin-unsupported":
        stderr_log.write_text(
            f"unsupported contour: {prepared.command[0] if prepared.command else 'unsupported'}\n",
            encoding="utf-8",
            newline="\n",
        )
        return 64
    env = {
        "ONEC_PROJECT_ROOT": str(project_root()),
        "ONEC_PROFILE_PATH": str(profile.path),
        "ONEC_RUNNER_ADAPTER": prepared.adapter,
        "ONEC_CAPABILITY_ID": prepared.capability_id,
        "ONEC_CAPABILITY_LABEL": prepared.label,
        "ONEC_CAPABILITY_RUN_ROOT": str(run_root),
    }
    command = list(prepared.command)
    if prepared.executor == "adapter-wrapper":
        adapter_name = "direct-platform" if prepared.adapter == "direct-platform" else prepared.adapter
        suffix = ".ps1" if WINDOWS else ".sh"
        adapter_path = project_root() / "scripts" / "adapters" / f"{adapter_name}{suffix}"
        if not adapter_path.is_file():
            die(f"adapter launcher not found: {adapter_path}")
        if WINDOWS:
            command = [
                "pwsh",
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(adapter_path),
                *command,
            ]
        else:
            command = [str(adapter_path), *command]
    if WINDOWS:
        command = normalize_repo_command_tokens(command)
    return run_logged(command, stdout_path=stdout_log, stderr_path=stderr_log, cwd=project_root(), env=env)


def run_profile_capability(
    capability_id: str,
    label: str,
    argv: list[str],
) -> CapabilityResult:
    args = parse_capability_cli_args(argv, allow_files=True)
    if args.show_help:
        raise CommandError("help-requested", 2)
    profile_path = resolve_runtime_profile_path(args.profile_input)
    profile = require_runtime_profile(load_runtime_profile(profile_path))
    adapter = os.environ.get("RUNNER_ADAPTER") or profile.runner_adapter or "direct-platform"
    selected_files = load_capability_selected_files(args.selected_files_input)
    prepared = prepare_standard_capability_command(
        profile,
        capability_id,
        label,
        adapter,
        selected_files,
        dry_run=args.dry_run,
    )
    run_root = prepare_capability_run_root(capability_id, args.run_root_input)
    summary_path = capability_summary_path(run_root)
    stdout_log = run_root / "stdout.log"
    stderr_log = run_root / "stderr.log"
    stdout_log.write_text("", encoding="utf-8", newline="\n")
    stderr_log.write_text("", encoding="utf-8", newline="\n")
    log(label)
    log(f"adapter={adapter}")
    if prepared.driver:
        log(f"driver={prepared.driver}")
    log(f"command_source={prepared.command_source}")
    log(f"executor={prepared.executor}")
    log(f"profile={profile.path}")
    log(f"run_root={run_root}")
    started_at = timestamp_utc()
    status = "dry-run" if args.dry_run else "success"
    exit_code = 0
    if not args.dry_run:
        exit_code = execute_prepared_capability_command(prepared, profile, run_root, stdout_log, stderr_log)
        if exit_code != 0:
            status = "failed"
    finished_at = timestamp_utc()
    write_capability_summary(
        prepared,
        profile,
        run_root,
        stdout_log,
        stderr_log,
        status,
        exit_code,
        started_at,
        finished_at,
        args.dry_run,
        summary_path,
    )
    log(f"summary_json={summary_path}")
    return CapabilityResult(
        status=status,
        exit_code=exit_code,
        summary_path=summary_path,
        stdout_log=stdout_log,
        stderr_log=stderr_log,
    )


def git_lines(args: list[str], *, cwd: Path | None = None, check: bool = True) -> list[str]:
    result = run_git(args, cwd=cwd or project_root(), check=check)
    return [line for line in result.stdout.splitlines() if line]


def git_is_worktree(root: Path | None = None) -> bool:
    return run_git(["rev-parse", "--is-inside-work-tree"], cwd=root or project_root()).returncode == 0


def task_trailers_render(bead: str = "", work_item: str = "") -> str:
    if not bead and not work_item:
        die("render requires --bead and/or --work-item")
    lines: list[str] = []
    if bead:
        lines.append(f"Bead: {bead.strip()}")
    if work_item:
        lines.append(f"Work-Item: {work_item.strip()}")
    return "\n".join(lines) + "\n"


def task_trailers_validate_message(message_file: Path, require_any: bool = False) -> None:
    if not message_file.is_file():
        die(f"message file not found: {message_file}")
    bead_count = 0
    work_item_count = 0
    parsed_lines = []
    for raw_line in message_file.read_text(encoding="utf-8").splitlines():
        if raw_line.startswith("Bead:") or raw_line.startswith("Work-Item:"):
            parsed_lines.append(raw_line)
    for line in parsed_lines:
        key, _, raw_value = line.partition(":")
        value = raw_value.strip()
        if not value:
            die(f"empty value for trailer: {key}")
        if key == "Bead":
            bead_count += 1
            if bead_count > 1:
                die("duplicate trailer: Bead")
        elif key == "Work-Item":
            work_item_count += 1
            if work_item_count > 1:
                die("duplicate trailer: Work-Item")
    if require_any and bead_count == 0 and work_item_count == 0:
        die("message does not contain canonical task trailers")


def task_trailers_select_commits(selector_mode: str, selector_value: str, repo: Path | None = None) -> list[str]:
    repo_root = repo or project_root()
    if selector_mode == "range":
        return git_lines(["rev-list", "--reverse", selector_value], cwd=repo_root)
    if selector_mode not in {"bead", "work-item"}:
        die("select-commits requires one of --bead, --work-item, or --range")
    trailer_key = "Bead" if selector_mode == "bead" else "Work-Item"
    commits: list[str] = []
    for rev in git_lines(["rev-list", "--reverse", "HEAD"], cwd=repo_root):
        message = run_git(["log", "-1", "--format=%B", rev], cwd=repo_root, check=True).stdout
        values = []
        for line in message.splitlines():
            if line.startswith(f"{trailer_key}:"):
                value = line.partition(":")[2].strip()
                if value:
                    values.append(value)
        if len(values) == 1 and values[0] == selector_value:
            commits.append(rev)
    return unique_preserve_order(commits)


def build_doctor_capability_drivers_json(profile: RuntimeProfile, adapter: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for capability_id in DRIVER_CAPABILITIES:
        reason = profile_unsupported_reason(profile, capability_id)
        if reason:
            result[capability_id] = {
                "status": "missing",
                "source": "unsupported-profile",
                "driver": None,
                "reason": reason,
                "context": {"unsupported": {"placeholder": True, "reason": reason}},
            }
            continue
        command = profile_command(profile, capability_id)
        if command:
            result[capability_id] = {
                "status": "present" if not capability_command_failure_reason(profile, adapter, command) else "missing",
                "source": "profile-command",
                "driver": None,
                "reason": capability_command_failure_reason(profile, adapter, command) or None,
                "context": {},
            }
            continue
        driver = resolve_capability_driver(profile, capability_id)
        reason = doctor_capability_failure_reason(profile, capability_id, adapter)
        result[capability_id] = {
            "status": "present" if not reason else "missing",
            "source": "driver-selection",
            "driver": driver or None,
            "reason": reason or None,
            "context": {},
        }
    return result


def run_doctor(argv: list[str]) -> int:
    args = parse_capability_cli_args(argv, allow_files=False)
    if args.show_help:
        raise CommandError("help-requested", 2)
    profile = require_runtime_profile(load_runtime_profile(resolve_runtime_profile_path(args.profile_input)))
    adapter = os.environ.get("RUNNER_ADAPTER") or profile.runner_adapter
    run_root = prepare_capability_run_root("doctor", args.run_root_input)
    summary_path = capability_summary_path(run_root)
    stdout_log = run_root / "stdout.log"
    stderr_log = run_root / "stderr.log"
    stdout_log.write_text("", encoding="utf-8", newline="\n")
    stderr_log.write_text("", encoding="utf-8", newline="\n")
    required_tools = ["git", "rg"]
    optional_tools = ["openspec", "bd"]
    if not WINDOWS and adapter == "direct-platform" and direct_platform_xvfb_enabled(profile):
        required_tools.extend(["xvfb-run", "xauth"])
    required_fields = collect_required_profile_fields(profile, adapter)
    required_env_refs = collect_required_env_refs(profile)
    required_capabilities = [
        "create-ib",
        "dump-src",
        "load-src",
        "update-db",
        "diff-src",
        "run-xunit",
        "run-bdd",
        "run-smoke",
    ]
    optional_capabilities = ["publish-http"]
    checks = {
        "required_tools": [],
        "optional_tools": [],
        "required_profile_fields": [],
        "required_env_refs": [],
        "required_capabilities": [],
        "optional_capabilities": [],
        "derived_contours": [],
    }
    status = "success"
    for tool in required_tools:
        present = shutil.which(tool) is not None
        checks["required_tools"].append({"name": tool, "status": "present" if present else "missing", "required": True, "reason": None})
        if not present:
            status = "failed"
    for tool in optional_tools:
        checks["optional_tools"].append({"name": tool, "status": "present" if shutil.which(tool) else "missing", "required": False, "reason": None})
    for field_name in required_fields:
        cursor = profile.payload
        present = True
        for segment in field_name.split("."):
            if not isinstance(cursor, dict) or segment not in cursor or cursor[segment] is None:
                present = False
                break
            cursor = cursor[segment]
        checks["required_profile_fields"].append({"name": field_name, "status": "present" if present else "missing", "required": True, "reason": None})
        if not present:
            status = "failed"
    for env_name in required_env_refs:
        present = bool(os.environ.get(env_name))
        checks["required_env_refs"].append({"name": env_name, "status": "set" if present else "missing", "required": True, "reason": None})
        if not present:
            status = "failed"
    for capability_id in required_capabilities:
        reason = doctor_capability_failure_reason(profile, capability_id, adapter)
        item_status = "present" if not reason else "missing"
        if capability_id in {"run-xunit", "run-bdd", "run-smoke"} and profile_unsupported_reason(profile, capability_id):
            item_status = "unsupported"
        checks["required_capabilities"].append(
            {"name": capability_id, "status": item_status, "required": True, "reason": reason or None}
        )
        if item_status == "missing":
            status = "failed"
    for capability_id in optional_capabilities:
        reason = doctor_capability_failure_reason(profile, capability_id, adapter)
        checks["optional_capabilities"].append(
            {"name": capability_id, "status": "present" if not reason else "missing", "required": False, "reason": reason or None}
        )
    derived = []
    load_src_driver = resolve_capability_driver(profile, "load-src") if not profile_command(profile, "load-src") else ""
    for contour_id in ("load-diff-src", "load-task-src"):
        reason = ""
        if profile_unsupported_reason(profile, "load-src"):
            reason = profile_unsupported_reason(profile, "load-src") or ""
        elif profile_command(profile, "load-src"):
            reason = "partial load-src is not supported when capabilities.loadSrc.command override is set"
        elif load_src_driver != "ibcmd":
            reason = "partial load-src requires capabilities.loadSrc.driver=ibcmd"
        elif not git_is_worktree(project_root()):
            reason = "git-backed contour requires a git worktree"
        derived.append(
            {
                "name": contour_id,
                "status": "present" if not reason else "missing",
                "required": False,
                "source": "driver-selection",
                "driver": load_src_driver or None,
                "reason": reason or None,
            }
        )
    checks["derived_contours"] = derived
    payload = {
        "status": "dry-run" if args.dry_run else status,
        "capability": {"id": "doctor", "label": "1C runtime doctor"},
        "adapter": adapter,
        "profile_path": str(profile.path),
        "run_root": str(run_root),
        "artifacts": {
            "summary_json": str(summary_path),
            "stdout_log": str(stdout_log),
            "stderr_log": str(stderr_log),
        },
        "capability_drivers": build_doctor_capability_drivers_json(profile, adapter),
        "checks": checks,
        "warnings": build_runtime_profile_layout_warning_json(),
    }
    payload.update(build_redacted_context(profile))
    payload.update(direct_platform_adapter_context(profile) if adapter == "direct-platform" else {})
    write_json(summary_path, payload)
    log(f"summary_json={summary_path}")
    return 0 if status == "success" or args.dry_run else 1


def _write_delegate_summary(
    summary_path: Path,
    capability_id: str,
    label: str,
    adapter: str | None,
    profile_path: Path | None,
    run_root: Path,
    started_at: str,
    finished_at: str,
    stdout_log: Path,
    stderr_log: Path,
    dry_run: bool,
    exit_code: int,
    execution_source: str,
    selection: dict[str, Any],
    delegated: dict[str, Any] | None,
    context: dict[str, Any],
    driver: str | None = None,
) -> None:
    payload = {
        "status": "dry-run" if dry_run and exit_code == 0 else ("success" if exit_code == 0 else "failed"),
        "capability": {"id": capability_id, "label": label},
        "adapter": adapter,
        "driver": driver,
        "profile_path": str(profile_path) if profile_path else None,
        "run_root": str(run_root),
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_code": exit_code,
        "dry_run": dry_run,
        "execution": {"source": execution_source, "executor": "delegated-script"},
        "artifacts": {
            "summary_json": str(summary_path),
            "stdout_log": str(stdout_log),
            "stderr_log": str(stderr_log),
        },
        "selection": selection,
        "delegated": delegated,
    }
    payload.update(context)
    write_json(summary_path, payload)


def _find_free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_load_diff_src(argv: list[str]) -> int:
    args = parse_capability_cli_args(argv, allow_files=False)
    if args.show_help:
        raise CommandError("help-requested", 2)
    root = project_root()
    run_root = prepare_capability_run_root("load-diff-src", args.run_root_input)
    summary_path = capability_summary_path(run_root)
    stdout_log = run_root / "stdout.log"
    stderr_log = run_root / "stderr.log"
    stdout_log.write_text("", encoding="utf-8", newline="\n")
    stderr_log.write_text("", encoding="utf-8", newline="\n")
    started_at = timestamp_utc()
    profile = require_runtime_profile(load_runtime_profile(resolve_runtime_profile_path(args.profile_input)))
    adapter = os.environ.get("RUNNER_ADAPTER") or profile.runner_adapter
    source_dir = capability_string_or_default(profile, "load-src", "sourceDir", "./src/cf")
    source_dir_rel = normalize_capability_selected_file(source_dir)
    if not git_is_worktree(root):
        error = "git-backed diff requires a git worktree"
        _write_delegate_summary(
            summary_path,
            "load-diff-src",
            "Load source diff",
            adapter,
            profile.path,
            run_root,
            started_at,
            timestamp_utc(),
            stdout_log,
            stderr_log,
            args.dry_run,
            66,
            "git-diff-to-load-src",
            {"source_dir": source_dir, "base_ref": None, "selected_files": [], "ignored_files": [], "error": error},
            None,
            build_redacted_context(profile),
        )
        return 66
    base_ref = (
        "HEAD"
        if run_git(["rev-parse", "--verify", "HEAD"], cwd=root).returncode == 0
        else "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    )
    raw_paths = unique_preserve_order(
        git_lines(["diff", "--name-only", base_ref, "--", "."], cwd=root) + git_lines(["ls-files", "--others", "--exclude-standard", "--", "."], cwd=root)
    )
    selected_files: list[str] = []
    ignored_files: list[dict[str, str]] = []
    for repo_path in raw_paths:
        normalized = normalize_capability_selected_file(repo_path)
        if normalized != source_dir_rel and not normalized.startswith(f"{source_dir_rel}/"):
            ignored_files.append({"path": normalized, "reason": "outside-source-tree"})
            continue
        absolute_path = root / normalized
        if not absolute_path.is_file():
            ignored_files.append({"path": normalized, "reason": "missing-or-deleted"})
            continue
        relative_path = normalized[len(source_dir_rel) + 1 :]
        if not relative_path:
            ignored_files.append({"path": normalized, "reason": "not-a-source-file"})
            continue
        if relative_path not in selected_files:
            selected_files.append(relative_path)
    exit_code = 0
    driver: str | None = None
    delegated = None
    if not selected_files:
        exit_code = 65
    else:
        delegated_run_root = run_root / "load-src"
        delegated_args = ["--profile", str(profile.path), "--run-root", str(delegated_run_root), "--files", ",".join(selected_files)]
        if args.dry_run:
            delegated_args.append("--dry-run")
        result = run_profile_capability("load-src", "Load source tree", delegated_args)
        exit_code = result.exit_code
        delegated = {
            "capability": "load-src",
            "run_root": str(delegated_run_root),
            "summary_json": str(delegated_run_root / "summary.json"),
            "stdout_log": str(delegated_run_root / "stdout.log"),
            "stderr_log": str(delegated_run_root / "stderr.log"),
        }
        if delegated and Path(delegated["summary_json"]).is_file():
            driver = read_json(delegated["summary_json"]).get("driver")
    selection = {
        "source_dir": source_dir,
        "base_ref": base_ref,
        "selected_files": selected_files,
        "ignored_files": ignored_files,
        "error": None if selected_files else "no eligible changed files inside source tree",
    }
    _write_delegate_summary(
        summary_path,
        "load-diff-src",
        "Load source diff",
        adapter,
        profile.path,
        run_root,
        started_at,
        timestamp_utc(),
        stdout_log,
        stderr_log,
        args.dry_run,
        exit_code,
        "git-diff-to-load-src",
        selection,
        delegated,
        build_redacted_context(profile),
        driver=driver,
    )
    log(f"summary_json={summary_path}")
    return exit_code


def run_load_task_src(argv: list[str]) -> int:
    profile_input = ""
    run_root_input = ""
    dry_run = os.environ.get("DRY_RUN", "0") == "1"
    selector_mode = ""
    selector_value = ""
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in {"-h", "--help"}:
            raise CommandError("help-requested", 2)
        if arg == "--profile":
            index += 1
            profile_input = argv[index]
        elif arg == "--run-root":
            index += 1
            run_root_input = argv[index]
        elif arg == "--dry-run":
            dry_run = True
        elif arg in {"--bead", "--work-item", "--range"}:
            if selector_mode:
                die("load-task-src requires exactly one selector")
            selector_mode = arg[2:]
            index += 1
            selector_value = argv[index]
        elif arg == "--files":
            die("load-task-src derives file selection internally; --files is not supported")
        else:
            die(f"unknown argument: {arg}")
        index += 1
    if not selector_mode:
        die("load-task-src requires one of --bead, --work-item, or --range")
    root = project_root()
    run_root = prepare_capability_run_root("load-task-src", run_root_input)
    summary_path = capability_summary_path(run_root)
    stdout_log = run_root / "stdout.log"
    stderr_log = run_root / "stderr.log"
    stdout_log.write_text("", encoding="utf-8", newline="\n")
    stderr_log.write_text("", encoding="utf-8", newline="\n")
    started_at = timestamp_utc()
    profile = require_runtime_profile(load_runtime_profile(resolve_runtime_profile_path(profile_input)))
    adapter = os.environ.get("RUNNER_ADAPTER") or profile.runner_adapter
    source_dir = capability_string_or_default(profile, "load-src", "sourceDir", "./src/cf")
    source_dir_rel = normalize_capability_selected_file(source_dir)
    selected_commits = task_trailers_select_commits(selector_mode, selector_value, root)
    selected_files: list[str] = []
    ignored_files: list[dict[str, str]] = []
    deleted_paths: list[dict[str, str]] = []
    for commit in selected_commits:
        lines = git_lines(["diff-tree", "--no-commit-id", "--root", "--name-status", "-r", "-m", commit], cwd=root)
        for line in lines:
            parts = line.split("\t")
            status = parts[0]
            primary = parts[1] if len(parts) > 1 else ""
            secondary = parts[2] if len(parts) > 2 else ""
            repo_path = secondary if status[:1] in {"R", "C"} else primary
            normalized = normalize_capability_selected_file(repo_path)
            if normalized != source_dir_rel and not normalized.startswith(f"{source_dir_rel}/"):
                ignored_files.append({"path": normalized, "reason": "outside-source-tree", "commit": commit})
                continue
            absolute_path = root / normalized
            if status.startswith("D") or not absolute_path.is_file():
                deleted_paths.append({"path": normalized, "commit": commit})
                continue
            relative_path = normalized[len(source_dir_rel) + 1 :]
            if relative_path and relative_path not in selected_files:
                selected_files.append(relative_path)
    exit_code = 0
    delegated = None
    driver = None
    if not selected_commits:
        exit_code = 65
    elif not selected_files:
        exit_code = 65
    else:
        delegated_run_root = run_root / "load-src"
        delegated_args = ["--profile", str(profile.path), "--run-root", str(delegated_run_root), "--files", ",".join(selected_files)]
        if dry_run:
            delegated_args.append("--dry-run")
        result = run_profile_capability("load-src", "Load source tree", delegated_args)
        exit_code = result.exit_code
        delegated = {
            "capability": "load-src",
            "run_root": str(delegated_run_root),
            "summary_json": str(delegated_run_root / "summary.json"),
            "stdout_log": str(delegated_run_root / "stdout.log"),
            "stderr_log": str(delegated_run_root / "stderr.log"),
        }
        if Path(delegated["summary_json"]).is_file():
            driver = read_json(delegated["summary_json"]).get("driver")
    selection = {
        "source_dir": source_dir,
        "selector": {"mode": selector_mode, "value": selector_value},
        "selected_commits": selected_commits,
        "selected_files": selected_files,
        "ignored_files": ignored_files,
        "deleted_paths": deleted_paths,
        "error": None if selected_files else ("no commits matched selector" if not selected_commits else "no eligible committed files inside source tree"),
    }
    _write_delegate_summary(
        summary_path,
        "load-task-src",
        "Load task-scoped source changes",
        adapter,
        profile.path,
        run_root,
        started_at,
        timestamp_utc(),
        stdout_log,
        stderr_log,
        dry_run,
        exit_code,
        "git-task-to-load-src",
        selection,
        delegated,
        build_redacted_context(profile),
        driver=driver,
    )
    log(f"summary_json={summary_path}")
    return exit_code


def run_tdd_xunit(argv: list[str]) -> int:
    profile_input = ""
    run_root_input = ""
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in {"-h", "--help"}:
            raise CommandError("help-requested", 2)
        if arg == "--profile":
            index += 1
            profile_input = argv[index]
        elif arg == "--run-root":
            index += 1
            run_root_input = argv[index]
        else:
            die(f"unknown argument: {arg}")
        index += 1
    root = project_root()
    if not git_is_worktree(root):
        die("tdd-xunit requires a git worktree")
    profile_path = resolve_runtime_profile_path(profile_input)
    if profile_path is None:
        die("runtime profile is required")
    run_root = prepare_capability_run_root("tdd-xunit", run_root_input)
    summary_path = run_root / "summary.json"
    started_at = timestamp_utc()
    base_ref = "HEAD" if run_git(["rev-parse", "--verify", "HEAD"], cwd=root).returncode == 0 else "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    diff_lines = git_lines(["diff", "--name-status", base_ref, "--", "src/cf"], cwd=root) + [
        f"??\t{line}" for line in git_lines(["ls-files", "--others", "--exclude-standard", "--", "src/cf"], cwd=root)
    ]
    unsupported = [line for line in diff_lines if not line.startswith(("A\t", "M\t", "??\t"))]
    if unsupported:
        write_json(
            summary_path,
            {
                "status": "failed",
                "profile_path": str(profile_path),
                "run_root": str(run_root),
                "started_at": started_at,
                "finished_at": timestamp_utc(),
                "exit_code": 65,
                "sync": {
                    "required": False,
                    "action": "unsupported-delta-shape",
                    "cf_changes": diff_lines,
                    "unsupported_cf_changes": unsupported,
                    "message": "tdd-xunit supports only added, modified, or untracked files under src/cf",
                },
                "delegated": {"load_diff_run_root": None, "update_db_run_root": None, "xunit_run_root": None},
            },
        )
        return 65
    sync_required = bool(diff_lines)
    exit_code = 0
    load_diff_run_root = ""
    update_db_run_root = ""
    xunit_run_root = str(run_root / "xunit")
    if sync_required:
        load_diff_run_root = str(run_root / "load-diff-src")
        exit_code = run_load_diff_src(["--profile", str(profile_path), "--run-root", load_diff_run_root])
        if exit_code != 0:
            write_json(
                summary_path,
                {
                    "status": "failed",
                    "profile_path": str(profile_path),
                    "run_root": str(run_root),
                    "started_at": started_at,
                    "finished_at": timestamp_utc(),
                    "exit_code": exit_code,
                    "sync": {
                        "required": True,
                        "action": "load-diff-src-failed",
                        "cf_changes": diff_lines,
                        "unsupported_cf_changes": [],
                        "message": "Load git-backed src/cf diff failed",
                    },
                    "delegated": {
                        "load_diff_run_root": load_diff_run_root,
                        "update_db_run_root": None,
                        "xunit_run_root": None,
                    },
                },
            )
            return exit_code
        update_db_run_root = str(run_root / "update-db")
        exit_code = run_profile_capability(
            "update-db", "Update DB configuration", ["--profile", str(profile_path), "--run-root", update_db_run_root]
        ).exit_code
        if exit_code != 0:
            write_json(
                summary_path,
                {
                    "status": "failed",
                    "profile_path": str(profile_path),
                    "run_root": str(run_root),
                    "started_at": started_at,
                    "finished_at": timestamp_utc(),
                    "exit_code": exit_code,
                    "sync": {
                        "required": True,
                        "action": "update-db-failed",
                        "cf_changes": diff_lines,
                        "unsupported_cf_changes": [],
                        "message": "Update DB configuration failed",
                    },
                    "delegated": {
                        "load_diff_run_root": load_diff_run_root,
                        "update_db_run_root": update_db_run_root,
                        "xunit_run_root": None,
                    },
                },
            )
            return exit_code
    exit_code = run_profile_capability("run-xunit", "Run xUnit checks", ["--profile", str(profile_path), "--run-root", xunit_run_root]).exit_code
    status = "success" if exit_code == 0 else "failed"
    write_json(
        summary_path,
        {
            "status": status,
            "profile_path": str(profile_path),
            "run_root": str(run_root),
            "started_at": started_at,
            "finished_at": timestamp_utc(),
            "exit_code": exit_code,
            "sync": {
                "required": sync_required,
                "action": "load-diff-src-and-update-db" if sync_required else "skip-clean-src-cf",
                "cf_changes": diff_lines,
                "unsupported_cf_changes": unsupported,
                "message": None,
            },
            "delegated": {
                "load_diff_run_root": load_diff_run_root or None,
                "update_db_run_root": update_db_run_root or None,
                "xunit_run_root": xunit_run_root,
            },
        },
    )
    return exit_code
