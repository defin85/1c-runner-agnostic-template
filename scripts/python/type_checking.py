"""Python quality contours: ruff lint, basedpyright types and pytest through the locked uv environment.

Tools come only from the project uv environment (`uv run --locked`), pinned by `uv.lock`.
There is no fallback to globally installed ruff/basedpyright/pytest: a different tool version
would give a different verdict, so a missing `uv` is a hard error with an install hint.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    print("error: internal module; run scripts/qa/type-check.sh or scripts/qa/python-lint.sh", file=sys.stderr)
    raise SystemExit(2)

from .common import project_root

# Minimum tool versions required by the template. The project owns pyproject.toml, uv.lock and
# requirements-dev.txt (design decision R15) and may pin newer versions, never older ones.
REQUIRED_MINIMUMS = {
    "basedpyright": "1.39.9",
    "ruff": "0.16.10",
    "pytest": "9.0.2",
}
CONFIG = "pyrightconfig.json"
# Template-managed base rules; the project-owned pyrightconfig.json extends it and adds its roots.
BASE_CONFIG = "scripts/qa/pyright-base.json"
# basedpyright modes at least as strict as `standard`.
ALLOWED_MODES = frozenset({"standard", "strict", "recommended", "all"})
# Settings a project config may not use: they record or hide accepted errors.
FORBIDDEN_PROJECT_KEYS = frozenset({"baselineFile", "ignore"})
REQUIREMENTS = "requirements-dev.txt"
EXPORT_ARGS = (
    "export",
    "--locked",
    "--format",
    "requirements-txt",
    "--no-hashes",
    "--no-emit-project",
    "--no-annotate",
)
REGENERATE_REQUIREMENTS = "uv " + " ".join(EXPORT_ARGS) + f" --output-file {REQUIREMENTS}"
UV_INSTALL_HINT = "install uv (https://docs.astral.sh/uv/getting-started/installation/) and rerun"
# Baselines are forbidden (design decision R10): accepted errors must be fixed, not recorded.
# basedpyright reads `.basedpyright/baseline.json` automatically, so that location is checked too.
BASELINE_PATTERNS = ("basedpyright-baseline*", ".basedpyright/baseline*")
REQUIRED_EXCLUDES = frozenset({"automation/vendor", ".venv"})
# Directories never scanned for unclassified Python files: VCS, tool caches, local
# environments, run artifacts and vendored upstream code.
SKIPPED_DIRS = frozenset({".git", ".venv", "node_modules", "__pycache__", ".artifacts"})
SKIPPED_PATHS = frozenset({"automation/vendor"})

# Fast pytest subset for `make agent-verify`; the full suite runs in CI and `make verify-python-tests`.
# Measured 2026-10-08: the full suite takes ~230 s, and these six metadata CLI operation suites take
# ~165 s of it (object_ops alone ~107 s). Everything else, including the lighter metadata suites,
# stays in the fast run (~65 s).
PYTEST_ROOT = "tests/python"
PYTEST_SLOW_FILES = (
    "tests/python/test_metadata_object_ops.py",
    "tests/python/test_metadata_form_ops.py",
    "tests/python/test_metadata_borrow.py",
    "tests/python/test_metadata_form_element_ops.py",
    "tests/python/test_metadata_create.py",
    "tests/python/test_metadata_form_compile.py",
)


class QualityError(RuntimeError):
    pass


def _uv() -> str:
    uv = shutil.which("uv")
    if not uv:
        raise QualityError(f"uv is not installed; {UV_INSTALL_HINT}")
    return uv


def _run(command: Sequence[str], root: Path) -> int:
    return subprocess.run(list(command), cwd=root, check=False).returncode


def _load_json_object(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise QualityError(f"{label} is missing: {path.name}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise QualityError(f"{label} must contain a JSON object")
    return {str(key): value for key, value in payload.items()}


def _string_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def check_no_baseline(root: Path) -> None:
    found = sorted(path.relative_to(root).as_posix() for pattern in BASELINE_PATTERNS for path in root.glob(pattern))
    if found:
        raise QualityError(
            "basedpyright baseline files are not allowed; fix the type errors and remove: " + ", ".join(found)
        )


def _is_rule(key: str) -> bool:
    return key.startswith("report")


def check_config(root: Path) -> list[str]:
    """Validate the effective basedpyright configuration and return its include roots.

    The project-owned pyrightconfig.json must extend the template-managed BASE_CONFIG. Project keys
    override base keys, exactly as basedpyright merges `extends`.
    """
    config = _load_json_object(root / CONFIG, CONFIG)
    extends = str(config.get("extends") or "").removeprefix("./")
    if extends != BASE_CONFIG:
        raise QualityError(f'{CONFIG} must keep "extends": "{BASE_CONFIG}" (template-managed base rules)')
    base = _load_json_object(root / BASE_CONFIG, BASE_CONFIG)
    forbidden = sorted(key for key in FORBIDDEN_PROJECT_KEYS if key in config or key in base)
    if forbidden:
        raise QualityError(f"{CONFIG} must not configure: {', '.join(forbidden)}; fix the reported errors instead")
    effective = {**base, **config}
    mode = effective.get("typeCheckingMode")
    if mode not in ALLOWED_MODES:
        raise QualityError(
            f"typeCheckingMode {mode!r} is weaker than standard; allowed: {', '.join(sorted(ALLOWED_MODES))}"
        )
    disabled = sorted(key for key, value in base.items() if _is_rule(key) and value in {False, "none"})
    # A project may only tighten rules: any other level hides errors or turns them into warnings.
    weakened = sorted(key for key, value in config.items() if _is_rule(key) and value not in {True, "error"})
    if disabled or weakened:
        raise QualityError(f"{CONFIG} disables basedpyright rules: {', '.join(disabled + weakened)}")
    excludes = set(_string_list(effective.get("exclude")))
    missing_excludes = sorted(REQUIRED_EXCLUDES - excludes)
    if missing_excludes:
        raise QualityError(f"{CONFIG} must exclude: {', '.join(missing_excludes)}")
    includes = _string_list(effective.get("include"))
    if not includes:
        raise QualityError(f"{CONFIG} must list include roots")
    return includes


def _is_under(relative: str, roots: Sequence[str]) -> bool:
    return any(relative == root or relative.startswith(root.rstrip("/") + "/") for root in roots)


def find_unclassified_python(root: Path, includes: Sequence[str]) -> list[str]:
    """Python files outside basedpyright include roots would silently skip the type check."""
    unclassified: list[str] = []
    for directory, subdirectories, filenames in os.walk(root, topdown=True):
        current = Path(directory)
        subdirectories[:] = sorted(
            name
            for name in subdirectories
            if name not in SKIPPED_DIRS and (current / name).relative_to(root).as_posix() not in SKIPPED_PATHS
        )
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            relative = (current / name).relative_to(root).as_posix()
            if not _is_under(relative, includes):
                unclassified.append(relative)
    return unclassified


def _requirement_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def _version_key(version: str) -> tuple[int, ...]:
    """Numeric release key: `1.39.9` -> (1, 39, 9); pre-release suffixes are ignored."""
    parts: list[int] = []
    for part in version.split("."):
        digits = ""
        for char in part:
            if not char.isdigit():
                break
            digits += char
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def _pinned_versions(lines: Sequence[str]) -> dict[str, str]:
    pinned: dict[str, str] = {}
    for line in lines:
        requirement = line.split(";", 1)[0].strip()
        if "==" in requirement:
            name, version = requirement.split("==", 1)
            pinned[name.strip().lower().replace("_", "-")] = version.strip()
    return pinned


def check_minimum_pins(lines: Sequence[str]) -> None:
    pinned = _pinned_versions(lines)
    problems: list[str] = []
    fixes: list[str] = []
    for name, minimum in REQUIRED_MINIMUMS.items():
        version = pinned.get(name)
        if version is None:
            problems.append(f"{name} is not pinned")
        elif _version_key(version) < _version_key(minimum):
            problems.append(f"{name} {version} is below the template minimum {minimum}")
        else:
            continue
        fixes.append(f'"{name}>={minimum}"')
    if problems:
        raise QualityError(
            f"{REQUIREMENTS}: {'; '.join(problems)}. Fix: uv add --dev {' '.join(fixes)}, then {REGENERATE_REQUIREMENTS}"
        )


def check_requirements_export(root: Path, uv: str) -> None:
    """requirements-dev.txt is a derived export of uv.lock; a stale copy is an error."""
    path = root / REQUIREMENTS
    if not path.is_file():
        raise QualityError(f"{REQUIREMENTS} is missing; regenerate it: {REGENERATE_REQUIREMENTS}")
    current = _requirement_lines(path.read_text(encoding="utf-8"))
    check_minimum_pins(current)
    result = subprocess.run([uv, *EXPORT_ARGS], cwd=root, check=False, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise QualityError(
            f"uv export failed; is uv.lock in sync with pyproject.toml? Run: uv lock, then {REGENERATE_REQUIREMENTS}"
        )
    if _requirement_lines(result.stdout) != current:
        raise QualityError(f"{REQUIREMENTS} is stale relative to uv.lock; regenerate it: {REGENERATE_REQUIREMENTS}")


def _fail(error: Exception) -> int:
    print(f"error: {error}", file=sys.stderr)
    return 1


def run_type_check(root: Path | None = None) -> int:
    repo_root = root or project_root()
    try:
        check_no_baseline(repo_root)
        includes = check_config(repo_root)
        unclassified = find_unclassified_python(repo_root, includes)
        if unclassified:
            raise QualityError(
                f"Python files outside {CONFIG} include roots are not type-checked; add their root to "
                f"include (or exclude it deliberately): {', '.join(unclassified)}"
            )
        uv = _uv()
        check_requirements_export(repo_root, uv)
    except (OSError, ValueError, QualityError) as error:
        return _fail(error)
    return _run([uv, "run", "--locked", "basedpyright", "--project", CONFIG], repo_root)


def run_python_lint(root: Path | None = None) -> int:
    repo_root = root or project_root()
    try:
        uv = _uv()
    except QualityError as error:
        return _fail(error)
    check_status = _run([uv, "run", "--locked", "ruff", "check", "."], repo_root)
    format_status = _run([uv, "run", "--locked", "ruff", "format", "--check", "."], repo_root)
    return check_status or format_status


def run_python_tests(args: Sequence[str] = (), root: Path | None = None) -> int:
    """Run pytest from the uv environment; `--fast` skips PYTEST_SLOW_FILES, other args pass through."""
    repo_root = root or project_root()
    try:
        uv = _uv()
    except QualityError as error:
        return _fail(error)
    extra = [arg for arg in args if arg != "--fast"]
    command = [uv, "run", "--locked", "python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    if "--fast" in args:
        command += [f"--ignore={path}" for path in PYTEST_SLOW_FILES]
    command += extra or [PYTEST_ROOT]
    return _run(command, repo_root)


def run_python_tests_fast(root: Path | None = None) -> int:
    return run_python_tests(["--fast"], root)
