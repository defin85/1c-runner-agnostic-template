"""Platform compilation of main-configuration BSL modules in the exact infobase of a runtime profile.

With module paths the wrapper first loads only those modules (with the owning object descriptions)
into the infobase configuration through ``/LoadConfigFromFiles -listFile -partial``; the database
configuration is not updated. Then Designer ``/CheckModules`` compiles the configuration in the
execution modes of the target. The summary records the platform version, the configuration version,
its compatibility mode, the execution modes and the selected modules. Compilation verdicts come
only from Designer: the wrapper reads Designer output lines and never parses BSL.
"""

from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Any

from .common import WINDOWS, CommandError, die, project_root, run_git, timestamp_utc
from .runtime import PreparedCommand, build_designer_command, execute_prepared_capability_command
from .runtime_lock import project_runtime_lock
from .runtime_profiles import (
    RuntimeProfile,
    load_runtime_profile,
    require_runtime_profile,
    resolve_runtime_profile_path,
)
from .runtime_result import prepare_run_artifacts, publish_summary, sanitize_artifact_logs

CAPABILITY_ID = "check-cf-modules"
CAPABILITY_LABEL = "Check main configuration BSL modules"
DESIGNER_ERRORS_FOUND_EXIT_CODE = 101
DIAGNOSTICS_LIMIT = 100
NO_ERROR_LINES = {
    "No errors found",
    "No syntax errors found!",
    "Ошибок не обнаружено",
    "Синтаксических ошибок не обнаружено!",
}
ORDINARY_MODES = ("ThickClientOrdinaryApplication", "Server", "ExternalConnection")
MANAGED_MODES = (
    "ThinClient",
    "WebClient",
    "Server",
    "ExternalConnection",
    "ThickClientManagedApplication",
    "ThickClientServerManagedApplication",
)
KNOWN_MODES = set(ORDINARY_MODES) | set(MANAGED_MODES) | {"MobileAppClient", "MobileAppServer"}
USAGE = """Usage: check-cf-modules --profile <file> [--source-root <dir>] [--run-root <dir>]
                        [--execution-mode <Mode>]... [--baseline-diagnostics <file>] [--dry-run]
                        [<module.bsl>...]

Compiles main-configuration modules with Designer /CheckModules in the infobase of the profile.
Module paths (inside --source-root, default src/cf) are loaded first with a partial
/LoadConfigFromFiles; the database configuration is not updated. Without module paths the
installed configuration is checked and source identity stays not-verified.
"""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def read_configuration_properties(source_root: Path) -> dict[str, str]:
    """Return scalar properties of ``Configuration.xml`` (Name, Version, CompatibilityMode, ...)."""
    path = source_root / "Configuration.xml"
    try:
        tree = ElementTree.parse(path)
    except (OSError, ElementTree.ParseError) as error:
        raise CommandError(f"cannot read configuration description: {path}: {error}", 2) from error
    for element in tree.getroot().iter():
        if _local_name(element.tag) != "Configuration":
            continue
        for child in element:
            if _local_name(child.tag) == "Properties":
                return {
                    _local_name(item.tag): (item.text or "").strip()
                    for item in child
                    if len(item) == 0 and (item.text or "").strip()
                }
    return {}


def platform_version(binary_path: str) -> str:
    match = re.search(r"(\d+\.\d+\.\d+\.\d+)", binary_path)
    return match.group(1) if match else "unknown"


def default_execution_modes(properties: dict[str, str]) -> list[str]:
    if properties.get("DefaultRunMode") == "OrdinaryApplication":
        return list(ORDINARY_MODES)
    return list(MANAGED_MODES)


def _relative_module(source_root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if path.suffix.lower() != ".bsl" or not path.is_file():
        die(f"module is not an existing .bsl file: {value}", exit_code=2)
    try:
        return path.relative_to(source_root)
    except ValueError:
        die(f"module is outside the configuration source root {source_root}: {value}", exit_code=2)


def partial_load_files(source_root: Path, modules: list[Path]) -> list[str]:
    """Map modules to the files a partial load needs: owner descriptions plus the module itself."""
    files: list[str] = []

    def add(relative: Path) -> None:
        text = relative.as_posix()
        if (source_root / relative).is_file() and text not in files:
            files.append(text)

    for module in modules:
        parts = module.parts
        if parts[0] == "Ext":
            add(Path("Configuration.xml"))
        elif len(parts) >= 2:
            add(Path(parts[0]) / f"{parts[1]}.xml")
        if "Forms" in parts[:-1]:
            index = parts.index("Forms")
            if index + 1 < len(parts) - 1:
                form = Path(*parts[: index + 2])
                add(form.parent / f"{form.name}.xml")
                add(form / "Ext" / "Form.xml")
        add(module)
    return files


def designer_diagnostics(out_log: Path, exit_code: int) -> list[dict[str, Any]]:
    if not out_log.is_file():
        return []
    diagnostics: list[dict[str, Any]] = []
    for raw_line in out_log.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        raw = raw_line.strip()
        if not raw or raw in NO_ERROR_LINES:
            continue
        severity = "warning" if ("Handler missing:" in raw or "Cannot find method " in raw) else "error"
        if severity == "error" and exit_code == 0:
            severity = "warning"
        diagnostic: dict[str, Any] = {"severity": severity, "message": raw, "raw": raw}
        module = re.match(r"^\{([^}(]+)", raw)
        if module:
            diagnostic["module"] = module.group(1).strip()
        diagnostics.append(diagnostic)
    return diagnostics


def blocking_diagnostics(current: list[dict[str, Any]], baseline: list[Any] | None) -> list[dict[str, Any]]:
    if baseline is None:
        return current
    remaining: dict[str, int] = {}
    for item in baseline:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        remaining[key] = remaining.get(key, 0) + 1
    new: list[dict[str, Any]] = []
    for item in current:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if remaining.get(key, 0) > 0:
            remaining[key] -= 1
        else:
            new.append(item)
    return new


def _adapter(profile: RuntimeProfile) -> str:
    return os.environ.get("RUNNER_ADAPTER") or profile.runner_adapter or "direct-platform"


def _prepared(profile: RuntimeProfile, stage: str, command: list[str]) -> PreparedCommand:
    adapter = _adapter(profile)
    return PreparedCommand(
        capability_id=CAPABILITY_ID,
        label=f"{CAPABILITY_LABEL}: {stage}",
        adapter=adapter,
        driver="designer",
        command_source="check-cf-modules-builder",
        executor="adapter-wrapper" if adapter == "direct-platform" and not WINDOWS else "direct",
        command=command,
    )


def _secrets(profile: RuntimeProfile) -> list[str]:
    name = profile.string("infobase", "auth", "passwordEnv")
    value = os.environ.get(name) if name else None
    return [value] if value else []


def _git_revision(root: Path) -> str | None:
    head = root / ".git"
    if not head.exists():
        return None
    result = run_git(["rev-parse", "HEAD"], cwd=root)
    return result.stdout.strip() if result.returncode == 0 else None


def _parse_args(argv: list[str]) -> dict[str, Any]:
    options: dict[str, Any] = {
        "profile": "",
        "source_root": "",
        "run_root": "",
        "modes": [],
        "baseline": "",
        "dry_run": False,
        "modules": [],
    }
    index = 0
    value_options = {
        "--profile": "profile",
        "--source-root": "source_root",
        "--run-root": "run_root",
        "--baseline-diagnostics": "baseline",
    }
    while index < len(argv):
        arg = argv[index]
        if arg in {"-h", "--help"}:
            print(USAGE)
            raise CommandError("help-requested", 0)
        if arg in value_options or arg == "--execution-mode":
            index += 1
            if index >= len(argv):
                die(f"{arg} requires a value", exit_code=2)
            if arg == "--execution-mode":
                mode = argv[index].lstrip("-")
                if mode not in KNOWN_MODES:
                    die(f"unknown execution mode: {argv[index]}", exit_code=2)
                options["modes"].append(mode)
            else:
                options[value_options[arg]] = argv[index]
        elif arg == "--dry-run":
            options["dry_run"] = True
        elif arg.startswith("-"):
            die(f"unknown argument: {arg}", exit_code=2)
        else:
            options["modules"].append(arg)
        index += 1
    return options


def run_check_cf_modules(argv: list[str]) -> int:
    options = _parse_args(argv)
    profile = require_runtime_profile(load_runtime_profile(resolve_runtime_profile_path(options["profile"])))
    root = project_root()
    source_value = options["source_root"] or "src/cf"
    source_root = Path(source_value) if Path(source_value).is_absolute() else root / source_value
    source_root = source_root.resolve()
    if not (source_root / "Configuration.xml").is_file():
        die(f"main configuration source root has no Configuration.xml: {source_root}", exit_code=2)
    properties = read_configuration_properties(source_root)
    if properties.get("ConfigurationExtensionPurpose"):
        die(f"{source_root} is an extension; use check-cfe-config for extensions", exit_code=2)
    modules = [_relative_module(source_root, value) for value in options["modules"]]
    modes = options["modes"] or default_execution_modes(properties)
    baseline_path = Path(options["baseline"]).resolve() if options["baseline"] else None
    baseline: list[Any] | None = None
    if baseline_path is not None:
        try:
            loaded = json.loads(baseline_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CommandError(f"baseline diagnostics cannot be read: {baseline_path}: {error}", 2) from error
        if not isinstance(loaded, list):
            die(f"baseline diagnostics must be a JSON array: {baseline_path}", exit_code=2)
        baseline = loaded

    run_root_value = options["run_root"] or str(root / ".artifacts" / CAPABILITY_ID)
    artifacts = prepare_run_artifacts(run_root_value)
    run_root = artifacts.run_root
    dry_run = bool(options["dry_run"])
    designer_out = run_root / "designer.out.log"
    designer_out.unlink(missing_ok=True)
    commands: dict[str, list[str]] = {}
    load_files: list[str] = []
    if modules:
        load_files = partial_load_files(source_root, modules)
        list_file = run_root / "load-list.txt"
        # Designer expects the list file in UTF-8 with BOM.
        list_file.write_text("\n".join(load_files), encoding="utf-8-sig")
        commands["load"] = build_designer_command(
            profile,
            "/DisableStartupDialogs",
            "/DisableStartupMessages",
            "/Out",
            str(run_root / "load.out.log"),
            "/LoadConfigFromFiles",
            str(source_root),
            "-listFile",
            str(list_file),
            "-Format",
            "Hierarchical",
            "-partial",
            dry_run=dry_run,
        )
    commands["check"] = build_designer_command(
        profile,
        "/DisableStartupDialogs",
        "/DisableStartupMessages",
        "/Out",
        str(designer_out),
        "/CheckModules",
        *(f"-{mode}" for mode in modes),
        dry_run=dry_run,
    )

    started_at = timestamp_utc()
    stage_exit: dict[str, int] = {}
    status = "dry-run"
    exit_code = 0
    diagnostics: list[dict[str, Any]] = []
    blocking: list[dict[str, Any]] = []
    secrets = _secrets(profile)
    if not dry_run:
        status = "success"
        with project_runtime_lock(root, CAPABILITY_ID):
            for stage, command in commands.items():
                stage_root = run_root / stage
                stage_artifacts = prepare_run_artifacts(stage_root)
                stage_exit[stage] = execute_prepared_capability_command(
                    _prepared(profile, stage, command),
                    profile,
                    stage_root,
                    stage_artifacts.stdout_path,
                    stage_artifacts.stderr_path,
                )
                sanitize_artifact_logs(stage_artifacts, secrets)
                if stage == "load" and stage_exit[stage] != 0:
                    status = "failed"
                    exit_code = stage_exit[stage]
                    break
        if "check" in stage_exit:
            designer_exit = stage_exit["check"]
            diagnostics = designer_diagnostics(designer_out, designer_exit)
            blocking = blocking_diagnostics(diagnostics, baseline)
            if blocking or designer_exit not in {0, DESIGNER_ERRORS_FOUND_EXIT_CODE}:
                status = "failed"
                exit_code = designer_exit or 1
            elif designer_exit == DESIGNER_ERRORS_FOUND_EXIT_CODE and baseline is None:
                status = "failed"
                exit_code = designer_exit

    payload: dict[str, Any] = {
        "status": status,
        "capability": {"id": CAPABILITY_ID, "label": CAPABILITY_LABEL},
        "profile_path": str(profile.path),
        "run_root": str(run_root),
        "started_at": started_at,
        "finished_at": timestamp_utc(),
        "exit_code": exit_code,
        "dry_run": dry_run,
        "adapter": _adapter(profile),
        "platform": {
            "binary": profile.string("platform", "binaryPath"),
            "version": platform_version(profile.string("platform", "binaryPath")),
        },
        "configuration": {
            "name": properties.get("Name"),
            "version": properties.get("Version"),
            "compatibility_mode": properties.get("CompatibilityMode") or "unknown",
            "execution_modes": modes,
            "source": "Configuration.xml",
        },
        "modules": [module.as_posix() for module in modules],
        "load": {"files": load_files, "partial": bool(modules)} if modules else None,
        "source_identity": {
            "root": str(source_root),
            "revision": _git_revision(root),
            "loaded_match": "selected-modules-loaded"
            if modules and not dry_run and status != "failed"
            else "not-verified",
        },
        "stage_exit_codes": stage_exit,
        "diagnostics_count": len(diagnostics),
        "blocking_diagnostics_count": len(blocking),
        "diagnostics_truncated": len(diagnostics) > DIAGNOSTICS_LIMIT,
        "diagnostics": diagnostics[:DIAGNOSTICS_LIMIT],
        "baseline_diagnostics": str(baseline_path) if baseline_path else None,
        "execution": {"source": "check-cf-modules-wrapper", "strategy": "designer-check-modules", "commands": commands},
        "artifacts": {
            "summary_json": str(artifacts.summary_path),
            "designer_out_log": str(designer_out),
            "stages": {stage: str(run_root / stage) for stage in commands},
        },
    }
    publish_summary(artifacts, payload, secrets)
    configuration = payload["configuration"]
    print(
        f"check-cf-modules: status={status} platform={payload['platform']['version']} "
        f"compatibility={configuration['compatibility_mode']} modes={','.join(modes)} "
        f"modules={len(modules)} summary={artifacts.summary_path}"
    )
    for item in blocking[:20]:
        print(f"check-cf-modules: {item['raw']}", file=sys.stderr)
    return exit_code
