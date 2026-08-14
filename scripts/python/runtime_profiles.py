from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import WINDOWS, canonical_path, die, project_root, read_json


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
            die(f"runtime profile field has invalid type: {'.'.join(keys)} ({_json_type_name(value)})")
        return value

    def bool(self, *keys: str, default: bool | None = None) -> bool | None:
        value = self.get(*keys, default=default)
        if value is None:
            return default
        if not isinstance(value, bool):
            die(f"runtime profile field has invalid type: {'.'.join(keys)} ({_json_type_name(value)})")
        return value

    def array_strings(self, *keys: str) -> list[str]:
        value = self.get(*keys, default=[])
        if value is None:
            return []
        if not isinstance(value, list):
            die(f"runtime profile field has invalid type: {'.'.join(keys)}")
        return [str(item) for item in value]

    def require_string(self, *keys: str) -> str:
        label = ".".join(keys)
        value = self.string(*keys)
        if not value:
            die(f"runtime profile is missing {label} in {self.path}")
        return value


def resolve_runtime_profile_path(requested_path: str = "", root: Path | None = None) -> Path | None:
    repo_root = root or project_root()
    resolved = requested_path or os.environ.get("ONEC_PROFILE", "")
    if not resolved:
        default_profile = repo_root / "env" / "local.json"
        return canonical_path(default_profile) if default_profile.is_file() else None
    return canonical_path(resolved)


def runtime_profile_migration_error(profile_path: Path, schema_version: object) -> None:
    die(
        f"runtime profile schemaVersion={schema_version} is no longer supported: {profile_path}. "
        "Migrate it with ./scripts/template/migrate-runtime-profile-v3.sh <schema-v2-profile> "
        "and see docs/migrations/runtime-profile-v3.md"
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
    if schema_version in {1, 2} or (schema_version is None and isinstance(payload.get("shellEnv"), dict)):
        runtime_profile_migration_error(profile_path, schema_version or 1)
    if schema_version != 3:
        die(f"unsupported runtime profile schemaVersion={schema_version} in {profile_path}")
    if "runnerAdapter" in payload:
        die(f"schemaVersion=3 profile must not define runnerAdapter in {profile_path}")
    if WINDOWS:
        platform = payload.get("platform", {})
        if isinstance(platform, dict):
            enabled = [name for name in ("xpra", "xvfb", "ldPreload") if isinstance(platform.get(name), dict) and platform[name].get("enabled") is True]
            if enabled:
                die("Windows runtime profile enables POSIX-only platform features: " + ", ".join(enabled))
    transport = payload.get("transport")
    if transport is None:
        runner_adapter = "direct-platform"
    elif not isinstance(transport, dict):
        die(f"runtime profile field has invalid type: transport ({_json_type_name(transport)})")
    else:
        unknown = sorted(set(transport) - {"kind"})
        if unknown:
            die("runtime profile transport has unknown fields: " + ", ".join(unknown))
        if transport.get("kind") != "remote-windows":
            die(f"unsupported transport.kind={transport.get('kind')} in {profile_path}")
        runner_adapter = "remote-windows"
    capabilities = payload.get("capabilities", {})
    if not isinstance(capabilities, dict):
        die(f"runtime profile field has invalid type: capabilities ({_json_type_name(capabilities)})")
    for name, capability in capabilities.items():
        if not isinstance(capability, dict):
            die(f"runtime profile field has invalid type: capabilities.{name} ({_json_type_name(capability)})")
        if "command" in capability:
            die(f"schemaVersion=3 does not support profile-defined command orchestration: capabilities.{name}.command; use a repo-owned structured backend")
        if "backend" in capability and (name != "publishHttp" or capability.get("backend") != "apache-webinst"):
            die(f"unsupported backend={capability.get('backend')} for capabilities.{name} in {profile_path}")
    profile_name = payload.get("profileName", "")
    if not isinstance(profile_name, str):
        die(f"runtime profile field has invalid type: profileName ({_json_type_name(profile_name)})")
    return RuntimeProfile(canonical_path(profile_path), payload, profile_name, runner_adapter)


def require_runtime_profile(profile: RuntimeProfile | None) -> RuntimeProfile:
    if profile is None:
        die("runtime profile is required; pass --profile <file> or create env/local.json")
    return profile
