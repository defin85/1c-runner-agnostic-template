"""KD rules cycle: profile, scenario and run-root checks."""

from __future__ import annotations

import re
import shutil
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.migration.kd_cycle_common import (
    BUILD_RULES,
    MODULE_HINT,
    RETRY_MODES,
    ROLES,
    ROOT,
    STAGES,
    CycleError,
    project_path,
    read_json,
)

_PROFILE_ID = re.compile(r"[a-z0-9][a-z0-9-]{1,63}\Z")
_DATABASE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_ENV_NAME = re.compile(r"[A-Z][A-Z0-9_]*\Z")
_NODE_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_COMMAND_KEYS = ("reset", "load")
_RESERVED_NODE_NAMES = frozenset({*STAGES, BUILD_RULES, "all"})


def _object(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CycleError(f"{where} must be an object")
    return value


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise CycleError(f"{where} must be a non-empty string")
    return value


def _positive_int(value: object, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise CycleError(f"{where} must be a positive integer")
    return value


def _command(value: object, where: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise CycleError(f"{where} must be a non-empty list of strings")
    return list(value)


def _roles(items: object, where: str) -> dict[str, Mapping[str, Any]]:
    if not isinstance(items, list) or len(items) != len(ROLES):
        raise CycleError(f"{where} must list exactly the roles source and target")
    by_role: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(items):
        entry = _object(item, f"{where}[{index}]")
        role = entry.get("role")
        if role not in ROLES or role in by_role:
            raise CycleError(f"{where}[{index}].role must be source or target, each once")
        database = _text(entry.get("database"), f"{where}[{index}].database")
        if not _DATABASE.fullmatch(database):
            raise CycleError(f"{where}[{index}].database is not a safe database name: {database}")
        by_role[str(role)] = entry
    return by_role


def require_input_file(path_value: str, kind: str) -> Path:
    path = project_path(path_value)
    if not path.is_file():
        raise CycleError(f"{kind} not found: {path}; {MODULE_HINT}")
    return path


def load_profile(path: Path) -> dict[str, Any]:
    profile = read_json(path)
    if profile.get("schemaVersion") != 1:
        raise CycleError(f"profile schemaVersion must be 1: {path}")
    profile_id = _text(profile.get("profileId"), "profile profileId")
    if not _PROFILE_ID.fullmatch(profile_id):
        raise CycleError("profile profileId must use lowercase latin letters, digits and hyphens")
    publish_root = _text(profile.get("releasePublishRoot"), "profile releasePublishRoot")
    if not Path(publish_root).is_absolute():
        raise CycleError("profile releasePublishRoot must be an absolute path")
    limits = _object(profile.get("limits"), "profile limits")
    _positive_int(limits.get("runtimeStageTimeoutSeconds"), "profile limits.runtimeStageTimeoutSeconds")
    for key in ("stageTimeoutSeconds", "maxReleaseBytes"):
        if key in limits:
            _positive_int(limits[key], f"profile limits.{key}")
    if "minFreeBytes" in limits and (not isinstance(limits["minFreeBytes"], int) or limits["minFreeBytes"] < 0):
        raise CycleError("profile limits.minFreeBytes must be a non-negative integer")
    references = _roles(profile.get("references"), "profile references")
    for role, entry in references.items():
        _text(entry.get("snapshot"), f"profile references {role}.snapshot")
        digest = entry.get("snapshotSha256")
        if digest is not None and (not isinstance(digest, str) or not _SHA256.fullmatch(digest)):
            raise CycleError(f"profile references {role}.snapshotSha256 must be a lowercase SHA-256")
    workbases = _roles(profile.get("workbases"), "profile workbases")
    for role, entry in workbases.items():
        _text(entry.get("runtimeProfile"), f"profile workbases {role}.runtimeProfile")
        _text(entry.get("target"), f"profile workbases {role}.target")
    expendable = profile.get("expendableDatabases")
    if not isinstance(expendable, list) or not all(isinstance(item, str) and item for item in expendable):
        raise CycleError("profile expendableDatabases must be a list of database names")
    required_env = profile.get("requiredEnv", [])
    if not isinstance(required_env, list) or not all(
        isinstance(item, str) and _ENV_NAME.fullmatch(item) for item in required_env
    ):
        raise CycleError("profile requiredEnv must be a list of environment variable names")
    commands = _object(profile.get("commands", {}), "profile commands")
    for key, value in commands.items():
        if key not in _COMMAND_KEYS:
            raise CycleError(f"profile commands.{key} is unknown; allowed: {', '.join(_COMMAND_KEYS)}")
        _command(value, f"profile commands.{key}")
    return profile


def check_expendable_targets(profile: Mapping[str, Any]) -> dict[str, str]:
    """Refuse a workbase that is a reference base or is missing from `expendableDatabases`.

    Names compare case-insensitively, because PostgreSQL folds unquoted identifiers.
    """
    references = {str(item["database"]).lower(): str(item["role"]) for item in profile["references"]}
    expendable = {str(item).lower() for item in profile["expendableDatabases"]}
    targets: dict[str, str] = {}
    for item in profile["workbases"]:
        role = str(item["role"])
        database = str(item["database"])
        if database.lower() in references:
            raise CycleError(
                f"workbase {role} database {database} is the reference database of role "
                f"{references[database.lower()]}; refusing to restore over a reference base"
            )
        if database.lower() not in expendable:
            raise CycleError(f"workbase {role} database {database} is not listed in profile expendableDatabases")
        targets[role] = database
    if len({name.lower() for name in targets.values()}) != len(targets):
        raise CycleError("workbases source and target must use different databases")
    leaked = sorted(name for name in expendable if name in references)
    if leaked:
        raise CycleError("profile expendableDatabases lists a reference database: " + ", ".join(leaked))
    return targets


def runtime_profile_database(path: Path) -> str | None:
    payload = read_json(path)
    ibcmd = payload.get("ibcmd")
    if isinstance(ibcmd, Mapping):
        dbms = ibcmd.get("dbmsInfobase")
        if isinstance(dbms, Mapping) and isinstance(dbms.get("name"), str):
            return str(dbms["name"])
    return None


def check_required_env(profile: Mapping[str, Any], environment: Mapping[str, str]) -> None:
    missing = [name for name in profile.get("requiredEnv", []) if not environment.get(name)]
    if missing:
        raise CycleError("missing environment variables: " + ", ".join(missing))


def _validate_nodes(nodes: object) -> list[dict[str, Any]]:
    if nodes is None:
        return []
    if not isinstance(nodes, list):
        raise CycleError("scenario nodes must be a list")
    known: set[str] = set(STAGES)
    result: list[dict[str, Any]] = []
    for index, item in enumerate(nodes):
        node = dict(_object(item, f"scenario nodes[{index}]"))
        name = _text(node.get("name"), f"scenario nodes[{index}].name")
        if not _NODE_NAME.fullmatch(name) or name in _RESERVED_NODE_NAMES or name in known:
            raise CycleError(f"scenario node name is invalid or repeated: {name}")
        dependencies = node.get("dependencies", [])
        if not isinstance(dependencies, list) or not all(isinstance(dep, str) for dep in dependencies):
            raise CycleError(f"scenario node {name}: dependencies must be a list of names")
        unknown = [dep for dep in dependencies if dep not in known]
        if unknown:
            raise CycleError(
                f"scenario node {name}: dependencies must be stages or earlier nodes: {', '.join(unknown)}"
            )
        if node.get("retry") not in RETRY_MODES:
            raise CycleError(f"scenario node {name}: retry must be one of {', '.join(RETRY_MODES)}")
        _command(node.get("command"), f"scenario node {name}.command")
        for key in ("inputs", "outputs"):
            values = node.get(key, [])
            if not isinstance(values, list) or not all(isinstance(value, str) and value for value in values):
                raise CycleError(f"scenario node {name}: {key} must be a list of paths")
        node.setdefault("dependencies", [])
        node.setdefault("inputs", [])
        node.setdefault("outputs", [])
        known.add(name)
        result.append(node)
    return result


def load_scenario(path: Path) -> dict[str, Any]:
    if path.is_dir():
        path = path / "scenario.json"
    if not path.is_file():
        raise CycleError(f"scenario not found: {path}; {MODULE_HINT}")
    scenario = read_json(path)
    if scenario.get("schemaVersion") != 1:
        raise CycleError(f"scenario schemaVersion must be 1: {path}")
    if scenario.get("type") != "workbench":
        raise CycleError("scenario type must be workbench")
    _text(scenario.get("scenarioId"), "scenario scenarioId")
    _text(scenario.get("releaseId"), "scenario releaseId")
    try:
        datetime.fromisoformat(_text(scenario.get("createdAt"), "scenario createdAt"))
    except ValueError:
        raise CycleError("scenario createdAt must be an ISO 8601 date and time") from None
    inputs = _object(scenario.get("inputs"), "scenario inputs")
    for side in ("source", "target"):
        _text(inputs.get(side + "Structure"), f"scenario inputs.{side}Structure")
        digest = _text(inputs.get(side + "StructureSha256"), f"scenario inputs.{side}StructureSha256")
        if not _SHA256.fullmatch(digest):
            raise CycleError(f"scenario inputs.{side}StructureSha256 must be a lowercase SHA-256")
    _text(scenario.get("matrix"), "scenario matrix")
    compiler = _object(scenario.get("compiler", {}), "scenario compiler")
    provider = compiler.get("rulesProvider")
    if provider is not None and (not isinstance(provider, str) or not re.fullmatch(r"[\w.]+:\w+", provider)):
        raise CycleError("scenario compiler.rulesProvider must look like package.module:attribute")
    scenario["nodes"] = _validate_nodes(scenario.get("nodes"))
    scenario["_path"] = str(path.resolve())
    return scenario


def scenario_file(scenario: Mapping[str, Any], key: str) -> Path:
    """`matrix` and `expected` are relative to the scenario directory."""
    return Path(str(scenario["_path"])).parent / str(scenario[key])


def check_run_root(value: str) -> Path:
    run_root = Path(value)
    if not run_root.is_absolute():
        raise CycleError("--run-root must be an absolute path")
    resolved = run_root.resolve(strict=False)
    root = ROOT.resolve()
    if resolved == Path(resolved.anchor) or resolved == root or root in resolved.parents:
        raise CycleError("--run-root must be an explicit directory outside the repository")
    current = Path(run_root.anchor)
    for part in run_root.parts[1:]:
        current /= part
        if current.is_symlink():
            raise CycleError(f"--run-root must not pass through a symbolic link: {current}")
    return run_root


def free_bytes(path: Path) -> int:
    probe = path
    while not probe.exists():
        probe = probe.parent
    return shutil.disk_usage(probe).free
