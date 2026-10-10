from __future__ import annotations

import json
import os
import re
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
            enabled = [
                name
                for name in ("xpra", "xvfb", "ldPreload")
                if isinstance(platform.get(name), dict) and platform[name].get("enabled") is True
            ]
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
            die(
                f"schemaVersion=3 does not support profile-defined command orchestration: capabilities.{name}.command; use a repo-owned structured backend"
            )
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


# --- Target-aware profiles: project-owned multi-target metadata ------------------------------
#
# A generated project that keeps several target configurations under ``src/cf/<target-id>``
# declares them in ``automation/context/target-matrix.json`` together with the extension set of
# each target. Source and extension runtime commands then require an explicit ``--target`` that
# matches ``target.id`` of the runtime profile, and resolve the source tree and the extension set
# from the matrix.

TARGET_MATRIX_RELPATH = "automation/context/target-matrix.json"
RUNTIME_SUPPORT_MATRIX_RELPATH = "automation/context/runtime-support-matrix.json"


def target_matrix_path(root: Path) -> Path:
    return root / TARGET_MATRIX_RELPATH


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        die(f"invalid JSON in {path}: {error}")


def load_target_matrix(root: Path) -> dict[str, Any] | None:
    """Return the matrix when the file exists; ``None`` for a single-target project."""
    path = target_matrix_path(root)
    if not path.is_file():
        return None
    payload = _read_json(path)
    if not isinstance(payload, dict):
        die(f"invalid target metadata schema: {TARGET_MATRIX_RELPATH}")
    return payload


def _targets(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    targets = matrix.get("targets") or []
    if not isinstance(targets, list):
        return []
    return [item for item in targets if isinstance(item, dict)]


def target_matrix_enabled(root: Path) -> bool:
    matrix = load_target_matrix(root)
    return matrix is not None and len(_targets(matrix)) > 0


def _find_target(matrix: dict[str, Any], target_id: str) -> dict[str, Any] | None:
    for target in _targets(matrix):
        if target.get("id") == target_id:
            return target
    return None


def _target_source_path(target: dict[str, Any]) -> str:
    source_path = target.get("sourcePath")
    if isinstance(source_path, str) and source_path:
        return source_path
    return f"src/cf/{target.get('id')}"


def require_requested_target(root: Path, requested: str, profile_target: str) -> str | None:
    """Fail closed for a multi-target workspace without a matching ``--target``.

    Returns the requested target id, or ``None`` when the project has no target matrix.
    """
    matrix = load_target_matrix(root)
    if matrix is None or not _targets(matrix):
        return None
    if not requested:
        die("multi-target workspace requires --target <id>")
    if _find_target(matrix, requested) is None:
        die(f"target not found in {TARGET_MATRIX_RELPATH}: {requested}")
    if not profile_target:
        die("runtime profile target.id is required for multi-target workspace")
    if profile_target != requested:
        die(f"runtime profile target '{profile_target}' does not match requested target '{requested}'")
    return requested


def target_source_dir_or_default(root: Path, requested: str, profile_target: str, default_source: str) -> str:
    """Source tree of the requested target (``src/cf/<target-id>``) or ``default_source``."""
    target_id = require_requested_target(root, requested, profile_target)
    if target_id is None:
        return default_source
    matrix = load_target_matrix(root) or {}
    target = _find_target(matrix, target_id) or {}
    source_path = _target_source_path(target)
    if not (root / source_path).is_dir():
        die(f"target source path not found: {source_path}")
    return source_path


def target_extension_names(root: Path, target_id: str) -> list[str]:
    """Extension names the matrix assigns to ``target_id``, in matrix order."""
    matrix = load_target_matrix(root) or {}
    extension_matrix = matrix.get("extensionMatrix") or {}
    names = extension_matrix.get(target_id) if isinstance(extension_matrix, dict) else None
    if not isinstance(names, list):
        return []
    return [name for name in names if isinstance(name, str) and name]


def resolve_target_extensions(
    root: Path,
    requested_target: str,
    profile_target: str,
    explicit: list[str],
    available: list[str],
    source_root: Path,
) -> tuple[list[str], str | None]:
    """Select extensions for a CFE wrapper; returns ``(names, target_id)``.

    Without a target matrix the explicit names (or every available directory) are used. In a
    multi-target workspace the names come from the matrix of the requested target and every
    explicit name must belong to that target.
    """
    target_id = require_requested_target(root, requested_target, profile_target)
    if target_id is None:
        if not explicit:
            return list(available), None
        for name in explicit:
            if name not in available:
                die(f"requested extension is not present under {source_root}: {name}")
        return list(explicit), None
    target_names = target_extension_names(root, target_id)
    if explicit:
        for name in explicit:
            if name not in available:
                die(f"requested extension is not present under {source_root}: {name}")
            if name not in target_names:
                die(f"requested extension is not present in target matrix for target={target_id}: {name}")
        return list(explicit), target_id
    for name in target_names:
        if not (root / "src" / "cfe" / name).is_dir():
            die(f"target matrix extension not found under src/cfe: {name}")
    return target_names, target_id


def validate_target_matrix(root: Path) -> None:
    matrix = load_target_matrix(root)
    if matrix is None:
        return
    targets = matrix.get("targets")
    extension_matrix = matrix.get("extensionMatrix")
    if (
        matrix.get("schemaVersion") != 1
        or not isinstance(targets, list)
        or not isinstance(extension_matrix, dict)
        or not all(isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"] for item in targets)
    ):
        die(f"invalid target metadata schema: {TARGET_MATRIX_RELPATH}")
    for target in _targets(matrix):
        source_path = _target_source_path(target)
        if not (root / source_path).is_dir():
            die(f"target source path not found: {source_path}")
    for target_id in extension_matrix:
        if _find_target(matrix, target_id) is None:
            die(f"extension matrix references unknown target: {target_id}")
    names = sorted({name for value in extension_matrix.values() if isinstance(value, list) for name in value})
    for name in names:
        if not (root / "src" / "cfe" / str(name)).is_dir():
            die(f"target matrix extension not found under src/cfe: {name}")


def validate_runtime_support_matrix_targets(root: Path) -> None:
    """Fail when the runtime support matrix references targets or extensions absent from metadata."""
    matrix = load_target_matrix(root)
    support_path = root / RUNTIME_SUPPORT_MATRIX_RELPATH
    if matrix is None or not support_path.is_file():
        return
    support = _read_json(support_path)
    contours = support.get("contours") if isinstance(support, dict) else None
    if not isinstance(contours, list):
        return
    entries = [item for item in contours if isinstance(item, dict)]
    for contour in entries:
        for target_id in contour.get("targets") or []:
            if _find_target(matrix, target_id) is None:
                die(f"runtime support matrix references unknown target: {target_id}")
    extension_names: set[str] = set()
    for contour in entries:
        contour_matrix = contour.get("extensionMatrix") or {}
        if not isinstance(contour_matrix, dict):
            continue
        for target_id, names in contour_matrix.items():
            if _find_target(matrix, target_id) is None:
                die(f"runtime support matrix extensionMatrix references unknown target: {target_id}")
            if isinstance(names, list):
                extension_names.update(str(name) for name in names)
    for name in sorted(extension_names):
        if not (root / "src" / "cfe" / name).is_dir():
            die(f"runtime support matrix references missing extension under src/cfe: {name}")


def configuration_attribute(config_xml: Path, attribute: str) -> str:
    if not config_xml.is_file():
        return ""
    text = config_xml.read_text(encoding="utf-8", errors="ignore")
    match = re.search(rf'{attribute}="([^"]+)"', text)
    if match:
        return match.group(1)
    if attribute == "name":
        match = re.search(r"<Name>([^<]+)</Name>", text)
        return match.group(1) if match else ""
    return ""


def target_metadata(root: Path) -> dict[str, Any] | None:
    """Compact multi-target context for ``metadata-index.generated.json``; validates the matrix."""
    matrix = load_target_matrix(root)
    if matrix is None:
        return None
    validate_target_matrix(root)
    validate_runtime_support_matrix_targets(root)
    targets: list[dict[str, Any]] = []
    for target in _targets(matrix):
        source_path = _target_source_path(target)
        config_xml = root / source_path / "Configuration.xml"
        targets.append(
            {
                "id": target.get("id"),
                "sourcePath": source_path,
                "configuration": {
                    "xmlPath": f"{source_path}/Configuration.xml",
                    "present": config_xml.is_file(),
                    "name": configuration_attribute(config_xml, "name"),
                    "uuid": configuration_attribute(config_xml, "uuid"),
                },
            }
        )
    return {
        "metadataPath": TARGET_MATRIX_RELPATH,
        "sourceContainer": "src/cf",
        "targets": targets,
        "extensionMatrix": matrix.get("extensionMatrix") or {},
    }
