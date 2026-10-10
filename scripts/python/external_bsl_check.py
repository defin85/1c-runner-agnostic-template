"""ParseError check of BSL modules through ``bsl-analyzer-app analyze``.

The wrapper only selects directories and modules, builds analyzer arguments and reads the analyzer
jsonl output. BSL syntax is decided by the analyzer alone; this module never reads BSL text.
When the analyzer is not installed the result is ``синтаксис: не проверен`` with exit code 3.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .common import die, project_root
from .runtime_errors import CommandError

NOT_CHECKED_EXIT_CODE = 3
NOT_CHECKED_LINE = "синтаксис: не проверен"

USAGE = """Usage: analyze-bsl-external (--all-managed | <Имя|каталог>... | --extension <каталог>...)
                            [--configuration-root <каталог>] [--declare-extension <каталог>]...
                            [--run-root <каталог>]

Проверяет модули внешних обработок и отчётов командой bsl-analyzer-app analyze --external
вместе с основной конфигурацией и объявленными расширениями. Завершается с кодом 1 при любом
ParseError и с кодом 3 (синтаксис: не проверен), если анализатор недоступен.

  --all-managed               все артефакты src/epf/managed/* и src/erf/managed/*
  <Имя>                       каталог src/{epf,erf}/managed/<Имя> или src/{epf,erf}/<Имя>
                              (по имени каталога либо внутреннему имени <Имя>.xml)
  <каталог>                   каталог выгрузки: <Имя>.xml рядом с подкаталогом <Имя>/
  --configuration-root <к>    выгрузка основной конфигурации целевой ИБ (Configuration.xml);
                              по умолчанию BSL_CONFIGURATION_ROOT или src/cf
  --declare-extension <к>     объявить анализатору расширение целевой ИБ без проверки его модулей
  --extension <каталог>       объявить расширение и проверить его модули
  --run-root <путь>           куда сохранить jsonl анализатора
                              (по умолчанию .artifacts/analyze-bsl-external/<время>)

Каталоги ordinary/ не проверяются: ORDINARY_EXCLUSION_REASON
"""

MANAGED_ROOTS = ("src/epf/managed", "src/erf/managed")
NAME_ROOTS = ("src/epf/managed", "src/erf/managed", "src/epf", "src/erf")
ORDINARY_ROOTS = ("src/epf/ordinary", "src/erf/ordinary")
ORDINARY_EXCLUSION_REASON = (
    "ordinary/ хранит неизменяемую Designer-выгрузку обычных форм и не проверяется: "
    "модули обычных форм лежат внутри Form.bin, а исходная конфигурация может не иметь "
    "Configuration.xml для --configuration-root. Проверяйте адаптированную копию в managed/."
)
# Margin below the Windows command line limit (32767 characters).
COMMAND_BUDGET = 24000


class AnalyzerUnavailableError(CommandError):
    def __init__(self, message: str) -> None:
        super().__init__(message, NOT_CHECKED_EXIT_CODE)


@dataclass(frozen=True)
class Artifact:
    name: str
    directory: Path
    modules: tuple[Path, ...]


@dataclass
class AnalyzerOutcome:
    problems: list[str] = field(default_factory=list)
    parse_errors: list[dict[str, Any]] = field(default_factory=list)
    covered: int = 0
    # Every reported diagnostic as (resolved module path, raw analyzer finding), ParseError included.
    diagnostics: list[tuple[Path, dict[str, Any]]] = field(default_factory=list)


def analyzer_app() -> str:
    return os.environ.get("BSL_ANALYZER_APP", "bsl-analyzer-app")


def analyzer_available(app: str) -> bool:
    if shutil.which(app) is not None:
        return True
    path = Path(app)
    return path.is_file() and os.access(path, os.X_OK)


def default_configuration_root(root: Path) -> Path | None:
    configured = os.environ.get("BSL_CONFIGURATION_ROOT")
    candidate = Path(configured) if configured else Path("src/cf")
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve() if (candidate / "Configuration.xml").is_file() else None


def require_configuration_root(root: Path, value: str | None) -> Path:
    if value:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        candidate = candidate.resolve()
        if not (candidate / "Configuration.xml").is_file():
            die(f"not a configuration export (expected Configuration.xml): {value}", exit_code=2)
        return candidate
    found = default_configuration_root(root)
    if found is None:
        die("configuration root is required: pass --configuration-root or set BSL_CONFIGURATION_ROOT", exit_code=2)
    return found


def path_argument(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _artifact_dirs(base_dir: Path) -> list[Path]:
    # Hidden service directories (for example .<Имя>.metadata-state) are not exports.
    if not base_dir.is_dir():
        return []
    return sorted(path for path in base_dir.iterdir() if path.is_dir() and not path.name.startswith("."))


def artifact_name(directory: Path) -> str | None:
    names = sorted(item.stem for item in directory.glob("*.xml") if item.is_file() and (directory / item.stem).is_dir())
    return names[0] if len(names) == 1 else None


def _check_module_paths(modules: Iterable[Path]) -> None:
    for module in modules:
        if "," in str(module):
            die(f"module path contains a comma and cannot be passed to --changed-files: {module}", exit_code=2)


def load_artifact(directory: Path) -> Artifact:
    directory = directory.resolve()
    name = artifact_name(directory)
    if name is None:
        die(f"not an EPF/ERF export (expected one <Имя>.xml beside <Имя>/): {directory}", exit_code=2)
    modules = tuple(sorted((directory / name).rglob("*.bsl")))
    if not modules:
        die(f"EPF/ERF export contains no BSL modules: {directory}", exit_code=2)
    _check_module_paths(modules)
    return Artifact(name, directory, modules)


def load_extension(value: str | Path, *, require_modules: bool = True) -> Artifact:
    directory = Path(value)
    if not directory.is_absolute():
        directory = Path.cwd() / directory
    directory = directory.resolve()
    if not (directory / "Configuration.xml").is_file():
        die(f"not an extension export (expected Configuration.xml): {value}", exit_code=2)
    modules = tuple(
        sorted(
            path
            for path in directory.rglob("*.bsl")
            if not any(part.startswith(".") for part in path.relative_to(directory).parts)
        )
    )
    if require_modules and not modules:
        die(f"extension export contains no BSL modules: {directory}", exit_code=2)
    _check_module_paths(modules)
    return Artifact(directory.name, directory, modules)


def _is_ordinary(root: Path, directory: Path) -> bool:
    resolved = directory.resolve()
    return any(resolved.is_relative_to((root / item).resolve()) for item in ORDINARY_ROOTS)


def _resolve_by_name(root: Path, value: str) -> Path:
    matches: list[Path] = []
    for base in NAME_ROOTS:
        for candidate in _artifact_dirs(root / base):
            if candidate.name in {"managed", "ordinary"}:
                continue
            if candidate.name == value or artifact_name(candidate) == value:
                matches.append(candidate)
    unique = sorted({path.resolve() for path in matches})
    if not unique:
        if any((root / base / value).is_dir() for base in ORDINARY_ROOTS):
            die(f"artifact {value} exists only in ordinary/: {ORDINARY_EXCLUSION_REASON}", exit_code=2)
        die(f"EPF/ERF artifact not found: {value}", exit_code=2)
    if len(unique) > 1:
        listed = ", ".join(path.relative_to(root.resolve()).as_posix() for path in unique)
        die(f"artifact name {value} is ambiguous ({listed}); pass the directory explicitly", exit_code=2)
    return unique[0]


def select_artifacts(root: Path, values: list[str], all_managed: bool, allow_empty: bool = False) -> list[Artifact]:
    directories: list[Path] = []
    if all_managed:
        for base in MANAGED_ROOTS:
            directories.extend(_artifact_dirs(root / base))
    for value in values:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        if candidate.is_dir() and artifact_name(candidate) is not None:
            directories.append(candidate)
        elif "/" in value or "\\" in value or candidate.is_dir():
            die(f"not an EPF/ERF export (expected one <Имя>.xml beside <Имя>/): {value}", exit_code=2)
        else:
            directories.append(_resolve_by_name(root, value))
    for directory in directories:
        if _is_ordinary(root, directory):
            die(f"{directory}: {ORDINARY_EXCLUSION_REASON}", exit_code=2)
    seen: set[Path] = set()
    artifacts: list[Artifact] = []
    for directory in directories:
        resolved = directory.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        artifacts.append(load_artifact(resolved))
    if not artifacts and not allow_empty:
        die("no EPF/ERF artifacts selected", exit_code=2)
    return artifacts


def plan_passes(root: Path, artifacts: list[Artifact], budget: int = COMMAND_BUDGET) -> list[list[Artifact]]:
    """Split the selection into analyzer runs with unique --external names and a bounded command length."""
    passes: list[list[Artifact]] = []
    used: list[int] = []
    for artifact in artifacts:
        size = sum(len(path_argument(root, module)) + 1 for module in artifact.modules)
        size += len(artifact.name) + len(str(artifact.directory)) + 16
        for index, selected in enumerate(passes):
            if all(item.name != artifact.name for item in selected) and used[index] + size <= budget:
                selected.append(artifact)
                used[index] += size
                break
        else:
            passes.append([artifact])
            used.append(size)
    return passes


def build_analyze_command(
    app: str,
    root: Path,
    configuration_root: Path,
    modules: Sequence[Path],
    *,
    extensions: Sequence[tuple[str, Path]] = (),
    externals: Sequence[tuple[str, Path]] = (),
) -> list[str]:
    """Build one analyzer run: declared extensions and externals, ParseError of ``modules`` only."""
    command = [app, "analyze"]
    if (root / "bsl-analyzer.toml").is_file():
        command += ["-c", "bsl-analyzer.toml"]
    command += ["--configuration-root", path_argument(root, configuration_root)]
    for name, directory in extensions:
        command += ["--extension", f"{name}={path_argument(root, directory)}"]
    for name, directory in externals:
        command += ["--external", f"{name}={directory}"]
    command += [
        "--incremental",
        "--changed-files",
        ",".join(path_argument(root, module) for module in modules),
        "--only-diagnostic",
        "ParseError",
        "--format",
        "jsonl",
        "-q",
    ]
    return command


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def run_analyzer(
    root: Path, command: list[str], expected: Iterable[Path], output: Path, errors: Path
) -> AnalyzerOutcome:
    """Run the analyzer and read its jsonl; raise ``AnalyzerUnavailableError`` if it cannot start."""
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("w", encoding="utf-8") as stdout, errors.open("w", encoding="utf-8") as stderr:
            completed = subprocess.run(command, cwd=root, stdout=stdout, stderr=stderr, check=False)
    except OSError as error:
        raise AnalyzerUnavailableError(f"bsl-analyzer-app cannot be started: {error}") from error
    outcome = AnalyzerOutcome()
    if completed.returncode:
        outcome.problems.append(f"bsl-analyzer-app exited with {completed.returncode}; see {errors}")
    events: list[dict[str, Any]] = []
    for line in output.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            events.append(_as_dict(json.loads(line)))
        except json.JSONDecodeError:
            outcome.problems.append(f"invalid analyzer jsonl line in {output}")
    expected_paths = {module.resolve() for module in expected}
    covered: set[Path] = set()
    for event in events:
        if event.get("type") != "file":
            continue
        path = Path(str(event.get("path", "")))
        if not path.is_absolute():
            path = root / path
        covered.add(path.resolve())
        for value in _as_list(event.get("diagnostics")):
            finding = _as_dict(value)
            outcome.diagnostics.append((path.resolve(), finding))
            if finding.get("code") != "ParseError":
                continue
            line_number = finding.get("start_line")
            column = finding.get("start_column")
            location = (
                f":{line_number + 1}:{column + 1 if isinstance(column, int) else 1}"
                if isinstance(line_number, int)
                else ""
            )
            message = f"{path}{location}: ParseError {finding.get('severity', '')}: {finding.get('message', '')}"
            outcome.parse_errors.append({"path": str(path), "message": message})
            print(message, file=sys.stderr)
    outcome.covered = len(covered & expected_paths)
    for module in sorted(expected_paths - covered):
        outcome.problems.append(f"module was not analyzed: {module}")
    done = [event for event in events if event.get("type") == "done"]
    if len(done) != 1 or done[0].get("failed_files") != 0:
        outcome.problems.append(f"analyzer did not report a complete run (done.failed_files=0); see {output}")
    if outcome.parse_errors:
        outcome.problems.append(f"{len(outcome.parse_errors)} ParseError diagnostic(s)")
    return outcome


def check_external_artifacts(
    root: Path,
    values: list[str],
    all_managed: bool,
    run_root: Path | None = None,
    extension_values: list[str] | None = None,
    *,
    configuration_root: Path | None = None,
    declared_extension_values: list[str] | None = None,
) -> int:
    app = analyzer_app()
    configuration = configuration_root or require_configuration_root(root, None)
    declared: list[Artifact] = [
        load_extension(value, require_modules=False) for value in declared_extension_values or []
    ]
    extensions: list[Artifact] = []
    for value in extension_values or []:
        extension = load_extension(value)
        if any(item.name == extension.name for item in (*declared, *extensions)):
            die(f"extension {extension.name} is passed more than once", exit_code=2)
        extensions.append(extension)
    artifacts = select_artifacts(root, values, all_managed, allow_empty=bool(extensions))
    if not analyzer_available(app):
        print(f"External BSL check: {NOT_CHECKED_LINE} — {app} is not available", file=sys.stderr)
        return NOT_CHECKED_EXIT_CODE
    passes = plan_passes(root, artifacts) or [[]]
    names: dict[str, int] = {}
    for artifact in artifacts:
        names[artifact.name] = names.get(artifact.name, 0) + 1
    duplicates = sorted(name for name, count in names.items() if count > 1)
    if run_root is None:
        run_root = root / ".artifacts/analyze-bsl-external" / time.strftime("%Y%m%dT%H%M%S")
    run_root.mkdir(parents=True, exist_ok=True)
    modules = sum(len(artifact.modules) for artifact in (*extensions, *artifacts))
    print(
        f"External BSL check: {len(artifacts)} artifacts, {len(extensions)} extensions, "
        f"{modules} modules, {len(passes)} analyzer pass(es)"
        + (f"; duplicate names split across passes: {', '.join(duplicates)}" if duplicates else ""),
        flush=True,
    )
    declared_pairs = [(item.name, item.directory) for item in (*declared, *extensions)]
    all_problems: list[str] = []
    total_parse_errors = 0
    for index, selected in enumerate(passes, 1):
        # Extension modules are checked in the first run and declared in every run.
        checked = tuple(extensions) if index == 1 else ()
        expected = [module for artifact in (*checked, *selected) for module in artifact.modules]
        command = build_analyze_command(
            app,
            root,
            configuration,
            expected,
            extensions=declared_pairs,
            externals=[(artifact.name, artifact.directory) for artifact in selected],
        )
        try:
            outcome = run_analyzer(
                root, command, expected, run_root / f"pass-{index}.jsonl", run_root / f"pass-{index}.stderr.log"
            )
        except AnalyzerUnavailableError as error:
            print(f"External BSL check: {NOT_CHECKED_LINE} — {error}", file=sys.stderr)
            return NOT_CHECKED_EXIT_CODE
        total_parse_errors += len(outcome.parse_errors)
        all_problems.extend(f"pass {index}: {problem}" for problem in outcome.problems)
    if all_problems:
        for problem in all_problems:
            print(f"External BSL check failed: {problem}", file=sys.stderr)
        print(f"External BSL check failed: {total_parse_errors} ParseError; evidence: {run_root}", file=sys.stderr)
        return 1
    print(
        f"External BSL check passed: {len(artifacts)} artifacts, {len(extensions)} extensions, "
        f"{modules} modules, 0 ParseError; evidence: {run_root}"
    )
    return 0


def _option_value(args: list[str], index: int, name: str) -> tuple[str, int]:
    arg = args[index]
    if arg.startswith(f"{name}="):
        return arg.split("=", 1)[1], index
    index += 1
    if index >= len(args):
        die(f"{name} requires a value", exit_code=2)
    return args[index], index


def run_external_check(args: list[str], root: Path | None = None) -> int:
    if not args or args in (["-h"], ["--help"]):
        print(USAGE.replace("ORDINARY_EXCLUSION_REASON", ORDINARY_EXCLUSION_REASON))
        return 0 if args else 2
    values: list[str] = []
    all_managed = False
    run_root: Path | None = None
    configuration_value: str | None = None
    extension_values: list[str] = []
    declared_values: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        option = arg.split("=", 1)[0]
        if arg == "--all-managed":
            all_managed = True
        elif option == "--run-root":
            value, index = _option_value(args, index, option)
            run_root = Path(value).resolve()
        elif option == "--extension":
            value, index = _option_value(args, index, option)
            extension_values.append(value)
        elif option == "--declare-extension":
            value, index = _option_value(args, index, option)
            declared_values.append(value)
        elif option == "--configuration-root":
            configuration_value, index = _option_value(args, index, option)
        elif arg.startswith("-"):
            die(f"Unknown argument for analyze-bsl-external: {arg}", exit_code=2)
        else:
            values.append(arg)
        index += 1
    repo = root or project_root()
    return check_external_artifacts(
        repo,
        values,
        all_managed,
        run_root,
        extension_values,
        configuration_root=require_configuration_root(repo, configuration_value),
        declared_extension_values=declared_values,
    )
