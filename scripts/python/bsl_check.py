"""Route a BSL check of selected modules to the authoritative tools.

The router selects modules, finds their single source root and its kind (main configuration,
extension or EPF/ERF export), then sends the modules to:

- ``static``: ``bsl-analyzer-app analyze`` ParseError check of exactly these modules;
- ``platform``: ``check-cf-modules`` (main configuration) or ``check-cfe-config`` (extension)
  in the infobase of the runtime profile.

Neither the router nor its tests read BSL text. When no authoritative tool ran, the result is
``синтаксис: не проверен`` with exit code 3, never a success.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .check_cf_modules import read_configuration_properties
from .common import die, project_root, timestamp_utc
from .external_bsl_check import (
    NOT_CHECKED_EXIT_CODE,
    AnalyzerUnavailableError,
    analyzer_app,
    analyzer_available,
    artifact_name,
    build_analyze_command,
    default_configuration_root,
    path_argument,
    run_analyzer,
)
from .runtime_errors import CommandError
from .runtime_profiles import resolve_runtime_profile_path

MODES = ("full", "fast", "platform")
LAUNCH_FAILED_EXIT_CODE = 127
USAGE = """Usage: check-bsl [--mode full|fast|platform] [--profile <file>] [--configuration-root <dir>]
                 [--run-root <dir>] [--dry-run] <module.bsl>...

Checks the selected BSL modules of one source root:
  static    bsl-analyzer-app analyze (ParseError) of exactly these modules
  platform  check-cf-modules (main configuration) or check-cfe-config (extension) in the
            infobase of the runtime profile; EPF/ERF have no platform module check
Modes: full (static, then platform; default), fast (static only), platform (platform only).
--configuration-root names the main configuration of the target infobase for extension and
EPF/ERF modules (default BSL_CONFIGURATION_ROOT or src/cf).
Exit codes: 0 passed or static-only, 1 failed, 2 invalid selection, 3 not checked or blocked.
"""


@dataclass
class Selection:
    kind: str
    root: Path
    name: str
    modules: list[Path]
    properties: dict[str, str] = field(default_factory=dict)


@dataclass
class Backend:
    status: str
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)


def _resolve_module(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if path.suffix.lower() != ".bsl" or not path.is_file():
        die(f"module is not an existing .bsl file: {value}", exit_code=2)
    return path


def _source_root(module: Path, repo: Path) -> tuple[str, Path]:
    """Find the nearest Configuration.xml ancestor, otherwise the outermost EPF/ERF export."""
    stop = repo.resolve()
    for parent in module.parents:
        if (parent / "Configuration.xml").is_file():
            return "configuration", parent
        if parent == stop or parent == parent.parent:
            break
    external: Path | None = None
    for parent in module.parents:
        if parent == stop or parent == parent.parent:
            break
        if artifact_name(parent) is not None:
            external = parent
    if external is None:
        die(f"module does not belong to a configuration, extension or EPF/ERF export: {module}", exit_code=2)
    return "external", external


def select_modules(values: list[str], repo: Path) -> Selection:
    if not values:
        die("no BSL modules selected", exit_code=2)
    modules: list[Path] = []
    for value in values:
        module = _resolve_module(value)
        if "," in str(module):
            die(f"module path contains a comma and cannot be passed to the analyzer: {module}", exit_code=2)
        if module not in modules:
            modules.append(module)
    roots = {_source_root(module, repo) for module in modules}
    if len(roots) != 1:
        listed = ", ".join(sorted(path_argument(repo, root) for _, root in roots))
        die(f"modules belong to different source roots ({listed}); check one root at a time", exit_code=2)
    [(kind, root)] = roots
    properties: dict[str, str] = {}
    name = root.name
    if kind == "configuration":
        properties = read_configuration_properties(root)
        if properties.get("ConfigurationExtensionPurpose"):
            kind = "extension"
        name = properties.get("Name") or root.name
    else:
        name = artifact_name(root) or root.name
    return Selection(kind, root, name, modules, properties)


def _static(selection: Selection, repo: Path, configuration_root: Path | None, run_root: Path) -> Backend:
    app = analyzer_app()
    if not analyzer_available(app):
        return Backend("not-run", f"{app} is not available")
    base = selection.root if selection.kind == "configuration" else configuration_root
    if base is None:
        return Backend("not-run", "main configuration of the target infobase is unknown; pass --configuration-root")
    extensions = [(selection.name, selection.root)] if selection.kind == "extension" else []
    externals = [(selection.name, selection.root)] if selection.kind == "external" else []
    command = build_analyze_command(app, repo, base, selection.modules, extensions=extensions, externals=externals)
    output = run_root / "static.jsonl"
    try:
        outcome = run_analyzer(repo, command, selection.modules, output, run_root / "static.stderr.log")
    except AnalyzerUnavailableError as error:
        return Backend("not-run", str(error))
    evidence = {
        "command": command,
        "jsonl": str(output),
        "configuration_root": path_argument(repo, base),
        "parse_errors": outcome.parse_errors,
        "covered_modules": outcome.covered,
    }
    if outcome.problems:
        return Backend("failed", "; ".join(outcome.problems), evidence)
    return Backend("passed", f"0 ParseError in {len(selection.modules)} module(s)", evidence)


def _read_summary(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _platform(selection: Selection, repo: Path, profile_input: str, run_root: Path, dry_run: bool) -> Backend:
    if selection.kind == "external":
        return Backend("not-run", "EPF/ERF modules have no platform module check; a build is not a syntax check")
    profile_path = resolve_runtime_profile_path(profile_input)
    if profile_path is None or not profile_path.is_file():
        return Backend("not-run", "runtime profile of the target infobase is not specified")
    platform_root = run_root / "platform"
    args = ["--profile", str(profile_path), "--run-root", str(platform_root)]
    if dry_run:
        args.append("--dry-run")
    try:
        if selection.kind == "configuration":
            from .check_cf_modules import run_check_cf_modules

            source = path_argument(repo, selection.root)
            modules = [str(module) for module in selection.modules]
            exit_code = run_check_cf_modules([*args, "--source-root", source, *modules])
        else:
            from .cfe_runtime import run_cfe_command

            exit_code = run_cfe_command("check-cfe-config", [*args, "--extension", selection.name])
    except CommandError as error:
        return Backend("blocked", str(error))
    summary = _read_summary(platform_root / "summary.json")
    evidence: dict[str, Any] = {"summary_json": str(platform_root / "summary.json"), "exit_code": exit_code}
    for key in ("platform", "configuration", "modules", "source_identity", "diagnostics_count"):
        if key in summary:
            evidence[key] = summary[key]
    if summary.get("status") == "dry-run":
        return Backend("not-run", "dry-run: command prepared, platform not started", evidence)
    if exit_code == LAUNCH_FAILED_EXIT_CODE:
        return Backend("blocked", "platform process could not be started", evidence)
    if exit_code == 0:
        return Backend("passed", "platform check completed without blocking diagnostics", evidence)
    return Backend("failed", f"platform check exited with {exit_code}", evidence)


def overall_status(mode: str, kind: str, static: Backend, platform: Backend) -> str:
    if "failed" in {static.status, platform.status}:
        return "failed"
    if mode == "fast" or kind == "external":
        if static.status == "passed":
            return "passed" if kind == "external" and mode != "fast" else "static-only"
        return "blocked"
    if platform.status == "passed":
        return "passed"
    return "blocked"


def syntax_verdict(static: Backend, platform: Backend) -> str:
    statuses = {static.status, platform.status}
    if "failed" in statuses:
        return "ошибки"
    if "passed" in statuses:
        return "проверен"
    return "не проверен"


def _describe(backend: Backend) -> str:
    details = [backend.reason]
    platform = backend.evidence.get("platform")
    configuration = backend.evidence.get("configuration")
    if isinstance(platform, dict) and isinstance(configuration, dict):
        modes = ",".join(str(item) for item in configuration.get("execution_modes") or [])
        details.append(
            f"platform {platform.get('version')}, compatibility {configuration.get('compatibility_mode')}, "
            f"modes {modes}"
        )
    return "; ".join(item for item in details if item)


def _parse_args(argv: list[str]) -> dict[str, Any]:
    options: dict[str, Any] = {
        "mode": "full",
        "profile": "",
        "configuration_root": "",
        "run_root": "",
        "dry_run": False,
        "modules": [],
    }
    value_options = {
        "--mode": "mode",
        "--profile": "profile",
        "--configuration-root": "configuration_root",
        "--run-root": "run_root",
    }
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in {"-h", "--help"}:
            print(USAGE)
            raise CommandError("help-requested", 0)
        if arg in value_options:
            index += 1
            if index >= len(argv):
                die(f"{arg} requires a value", exit_code=2)
            options[value_options[arg]] = argv[index]
        elif arg == "--dry-run":
            options["dry_run"] = True
        elif arg.startswith("-"):
            die(f"unknown argument: {arg}", exit_code=2)
        else:
            options["modules"].append(arg)
        index += 1
    if options["mode"] not in MODES:
        die(f"unknown mode: {options['mode']} (expected {', '.join(MODES)})", exit_code=2)
    return options


def run_check_bsl(argv: list[str]) -> int:
    options = _parse_args(argv)
    repo = project_root()
    selection = select_modules(options["modules"], repo)
    configuration_value = options["configuration_root"]
    if configuration_value:
        configuration_root = Path(configuration_value)
        if not configuration_root.is_absolute():
            configuration_root = Path.cwd() / configuration_root
        configuration_root = configuration_root.resolve()
        if not (configuration_root / "Configuration.xml").is_file():
            die(f"not a configuration export (expected Configuration.xml): {configuration_value}", exit_code=2)
    else:
        configuration_root = default_configuration_root(repo)
    run_root = Path(options["run_root"] or repo / ".artifacts" / "check-bsl" / time.strftime("%Y%m%dT%H%M%S"))
    run_root = run_root.resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    mode = options["mode"]
    started_at = timestamp_utc()

    static = Backend("not-run", "mode platform")
    if mode != "platform":
        static = _static(selection, repo, configuration_root, run_root)
    platform = Backend("not-run", "mode fast")
    if mode != "fast":
        platform = _platform(selection, repo, options["profile"], run_root, bool(options["dry_run"]))
    overall = overall_status(mode, selection.kind, static, platform)
    syntax = syntax_verdict(static, platform)

    payload: dict[str, Any] = {
        "mode": mode,
        "target": {
            "kind": selection.kind,
            "name": selection.name,
            "root": path_argument(repo, selection.root),
            "compatibility_mode": selection.properties.get("CompatibilityMode")
            or selection.properties.get("ConfigurationExtensionCompatibilityMode"),
        },
        "modules": [path_argument(repo, module) for module in selection.modules],
        "static": {"status": static.status, "reason": static.reason, **static.evidence},
        "platform": {"status": platform.status, "reason": platform.reason, **platform.evidence},
        "overall": overall,
        "syntax": syntax,
        "started_at": started_at,
        "finished_at": timestamp_utc(),
    }
    summary_path = run_root / "summary.json"
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"target: {selection.kind} {selection.name} ({path_argument(repo, selection.root)})")
    print(f"modules: {len(selection.modules)}")
    print(f"mode: {mode}")
    print(f"static: {static.status} — {_describe(static)}")
    print(f"platform: {platform.status} — {_describe(platform)}")
    print(f"overall: {overall}")
    print(f"синтаксис: {syntax}")
    print(f"summary: {summary_path}")
    if overall == "failed":
        for item in static.evidence.get("parse_errors", [])[:20]:
            print(item.get("message", ""), file=sys.stderr)
        return 1
    if overall in {"passed", "static-only"}:
        return 0
    return NOT_CHECKED_EXIT_CODE
