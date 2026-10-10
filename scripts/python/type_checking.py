"""Python quality contours: ruff lint, basedpyright types and pytest through the locked uv environment.

Tools come only from the project uv environment (`uv run --locked`), pinned by `uv.lock`.
There is no fallback to globally installed ruff/basedpyright/pytest: a different tool version
would give a different verdict, so a missing `uv` is a hard error with an install hint.

Both tool configurations belong to the project and extend template-managed base files
(design decisions R15, R18): `pyrightconfig.json` -> `scripts/qa/pyright-base.json`,
`ruff.toml` -> `scripts/qa/ruff-base.toml`. The checks here refuse a project config that drops
the base or switches base rules off for template-managed files.
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterable, Sequence
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
# Project-owned ruff config and its template-managed base (design decision R18).
RUFF_CONFIG = "ruff.toml"
RUFF_BASE_CONFIG = "scripts/qa/ruff-base.toml"
TEMPLATE_MANIFEST = "automation/context/template-managed-paths.txt"
# Ruff settings that leave files out of the lint or format check.
RUFF_EXCLUDE_KEYS = (
    ("exclude",),
    ("extend-exclude",),
    ("lint", "exclude"),
    ("format", "exclude"),
)
# Ruff settings that switch rules off for some files; both the `lint` table and the legacy top level.
RUFF_PER_FILE_IGNORE_KEYS = ("per-file-ignores", "extend-per-file-ignores")
RUFF_IGNORE_KEYS = ("ignore", "extend-ignore")
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


def _effective_config(root: Path) -> dict[str, object]:
    """Base config merged with the project config: project keys override base keys, as in basedpyright."""
    config = _load_json_object(root / CONFIG, CONFIG)
    base = _load_json_object(root / BASE_CONFIG, BASE_CONFIG)
    return {**base, **config}


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


def _glob_regex(pattern: str, *, star_crosses_slash: bool) -> re.Pattern[str]:
    """Regex for a glob anchored at the project root: `**`, `*`, `?`, `[...]` and `{a,b}`.

    basedpyright keeps `*` inside one path component; ruff (globset defaults) lets `*` cross `/`.
    """
    star = ".*" if star_crosses_slash else "[^/]*"
    out: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if pattern.startswith("**/", index):
            out.append("(?:.*/)?")
            index += 3
            continue
        if pattern.startswith("**", index):
            out.append(".*")
            index += 2
            continue
        if char == "*":
            out.append(star)
        elif char == "?":
            out.append("." if star_crosses_slash else "[^/]")
        elif char == "[":
            end = pattern.find("]", index + 2)
            if end == -1:
                out.append(re.escape(char))
            else:
                body = pattern[index + 1 : end]
                out.append("[" + ("^" + body[1:] if body.startswith("!") else body) + "]")
                index = end
        elif char == "{":
            end = pattern.find("}", index)
            if end == -1:
                out.append(re.escape(char))
            else:
                options = pattern[index + 1 : end].split(",")
                out.append("(?:" + "|".join(re.escape(option) for option in options) + ")")
                index = end
        else:
            out.append(re.escape(char))
        index += 1
    return re.compile("".join(out))


def _path_prefixes(relative: str) -> list[str]:
    parts = relative.split("/")
    return ["/".join(parts[: count + 1]) for count in range(len(parts))]


def _matches_pyright_exclude(relative: str, patterns: Sequence[str]) -> bool:
    """basedpyright `exclude`: a root-relative glob that matches the path or one of its parent directories."""
    for pattern in patterns:
        normalized = pattern.removeprefix("./").rstrip("/")
        if not normalized:
            continue
        regex = _glob_regex(normalized, star_crosses_slash=False)
        if any(regex.fullmatch(prefix) for prefix in _path_prefixes(relative)):
            return True
    return False


def find_unclassified_python(root: Path, includes: Sequence[str], excludes: Sequence[str] = ()) -> list[str]:
    """Python files outside basedpyright include roots would silently skip the type check.

    Files and directories listed in `exclude` of pyrightconfig.json are excluded deliberately and
    are not reported.
    """
    unclassified: list[str] = []
    for directory, subdirectories, filenames in os.walk(root, topdown=True):
        current = Path(directory)
        kept: list[str] = []
        for name in sorted(subdirectories):
            relative = (current / name).relative_to(root).as_posix()
            if name in SKIPPED_DIRS or relative in SKIPPED_PATHS or _matches_pyright_exclude(relative, excludes):
                continue
            kept.append(name)
        subdirectories[:] = kept
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            relative = (current / name).relative_to(root).as_posix()
            if not _is_under(relative, includes) and not _matches_pyright_exclude(relative, excludes):
                unclassified.append(relative)
    return unclassified


def _load_toml(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise QualityError(f"{label} is missing: {path.name}")
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise QualityError(f"{label} is not valid TOML: {error}") from error


def _table(value: object) -> dict[str, object]:
    return {str(key): item for key, item in value.items()} if isinstance(value, dict) else {}


def _setting(config: dict[str, object], key: tuple[str, ...]) -> object:
    value: object = config
    for part in key:
        value = _table(value).get(part)
    return value


def _ruff_glob_matches(pattern: str, relative: str) -> bool:
    """Whether a ruff path pattern (relative to the project root) matches a file or one of its parents.

    A pattern without `/` matches any path component, as ruff matches it against base names. The
    check is deliberately broad: a pattern that may capture a template file is reported.
    """
    if pattern.startswith("!"):
        return not _ruff_glob_matches(pattern[1:], relative)
    normalized = pattern.removeprefix("./").rstrip("/")
    if not normalized:
        return False
    regex = _glob_regex(normalized, star_crosses_slash=True)
    if "/" not in normalized and any(regex.fullmatch(part) for part in relative.split("/")):
        return True
    return any(regex.fullmatch(prefix) for prefix in _path_prefixes(relative))


def _covers(selector: str, code: str) -> bool:
    return selector == "ALL" or code.startswith(selector)


def _overlaps(code: str, selectors: Iterable[str]) -> bool:
    """A rule code or prefix overlaps a selector when one of them contains the other."""
    return any(_covers(code, selector) or _covers(selector, code) for selector in selectors)


def template_python_paths(root: Path) -> list[str]:
    """Python files the template manages, by the overlay manifest; directory entries are expanded."""
    manifest = root / TEMPLATE_MANIFEST
    if not manifest.is_file():
        return []
    paths: set[str] = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry.endswith("/"):
            directory = root / entry
            if directory.is_dir():
                paths.update(path.relative_to(root).as_posix() for path in directory.rglob("*.py"))
        elif entry.endswith(".py"):
            paths.add(entry)
    return sorted(paths)


def _base_patterns(values: object) -> list[str]:
    """Base config paths are relative to its own directory; return them relative to the project root."""
    base_dir = posixpath.dirname(RUFF_BASE_CONFIG)
    patterns: list[str] = []
    for value in _string_list(values):
        resolved = posixpath.normpath(posixpath.join(base_dir, value))
        if not resolved.startswith("../"):
            patterns.append(resolved)
    return patterns


def check_ruff_config(root: Path) -> None:
    """The project-owned ruff.toml must extend the base and keep its rules for template-managed files.

    Refused: a missing or different `extend`; `select` that drops base selectors (use
    `extend-select`); `ignore` of a base rule (it applies to every file); `per-file-ignores`,
    `exclude`, `extend-exclude`, `lint.exclude`, `format.exclude` or `include` that capture a
    template-managed Python file.
    """
    config = _load_toml(root / RUFF_CONFIG, RUFF_CONFIG)
    extend = str(config.get("extend") or "").removeprefix("./")
    if extend != RUFF_BASE_CONFIG:
        raise QualityError(f'{RUFF_CONFIG} must keep extend = "{RUFF_BASE_CONFIG}" (template-managed base rules)')
    base = _load_toml(root / RUFF_BASE_CONFIG, RUFF_BASE_CONFIG)
    base_select = _string_list(_setting(base, ("lint", "select")) or base.get("select"))
    lint = _table(config.get("lint"))
    problems: list[str] = []

    for table, prefix in ((config, ""), (lint, "lint.")):
        select = table.get("select")
        if select is not None:
            dropped = [code for code in base_select if not any(_covers(p, code) for p in _string_list(select))]
            if dropped:
                problems.append(
                    f"{prefix}select drops base rules {', '.join(dropped)}; add project rules with extend-select"
                )
        for key in RUFF_IGNORE_KEYS:
            ignored = [code for code in _string_list(table.get(key)) if _overlaps(code, base_select)]
            if ignored:
                problems.append(f"{prefix}{key} switches off base rules for every file: {', '.join(ignored)}")

    template_files = template_python_paths(root)
    base_excluded = _base_patterns(base.get("exclude")) + _base_patterns(base.get("extend-exclude"))
    template_files = [path for path in template_files if not any(_ruff_glob_matches(p, path) for p in base_excluded)]

    def captured(pattern: str) -> list[str]:
        return [path for path in template_files if _ruff_glob_matches(pattern, path)]

    for key in RUFF_EXCLUDE_KEYS:
        for pattern in _string_list(_setting(config, key)):
            hits = captured(pattern)
            if hits:
                problems.append(f"{'.'.join(key)} pattern {pattern!r} excludes template files: {', '.join(hits[:3])}")
    for table, prefix in ((config, ""), (lint, "lint.")):
        for key in RUFF_PER_FILE_IGNORE_KEYS:
            for pattern, codes in _table(table.get(key)).items():
                ignored = [code for code in _string_list(codes) if _overlaps(code, base_select)]
                hits = captured(pattern) if ignored else []
                if hits:
                    problems.append(
                        f"{prefix}{key} {pattern!r} switches off base rules {', '.join(ignored)} "
                        f"for template files: {', '.join(hits[:3])}"
                    )
    include = config.get("include")
    if include is not None:
        missed = [
            path for path in template_files if not any(_ruff_glob_matches(p, path) for p in _string_list(include))
        ]
        if missed:
            problems.append(f"include leaves out template files: {', '.join(missed[:3])}; use extend-include")
    if problems:
        raise QualityError(
            f"{RUFF_CONFIG} weakens the template ruff base for template-managed files ({TEMPLATE_MANIFEST}): "
            + "; ".join(problems)
            + ". Narrow the project patterns to project files and fix the reported code instead"
        )


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
        excludes = _string_list(_effective_config(repo_root).get("exclude"))
        unclassified = find_unclassified_python(repo_root, includes, excludes)
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


def _ruff_fix_hint() -> str:
    minimum = REQUIRED_MINIMUMS["ruff"]
    return f'uv add --dev "ruff>={minimum}", then {REGENERATE_REQUIREMENTS}'


def check_ruff_available(root: Path, uv: str) -> None:
    """ruff must be installed in the locked uv environment and not older than the template minimum.

    Without this check a project without ruff in its dev dependencies gets uv's bare
    `Failed to spawn: ruff`.
    """
    result = subprocess.run(
        [uv, "run", "--locked", "ruff", "--version"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        if "Failed to spawn" in output or "No such file" in output:
            raise QualityError(
                f"ruff is not installed in the project uv environment (uv.lock). Fix: {_ruff_fix_hint()}"
            )
        sys.stderr.write(result.stderr)
        raise QualityError("cannot start ruff through uv; is uv.lock in sync with pyproject.toml? Run: uv lock")
    words = result.stdout.split()
    version = words[1] if len(words) >= 2 and words[0] == "ruff" else ""
    minimum = REQUIRED_MINIMUMS["ruff"]
    if not version or _version_key(version) < _version_key(minimum):
        found = version or "an unknown version"
        raise QualityError(f"ruff {found} is below the template minimum {minimum}. Fix: {_ruff_fix_hint()}")


def run_python_lint(root: Path | None = None) -> int:
    repo_root = root or project_root()
    try:
        uv = _uv()
        check_ruff_config(repo_root)
        check_ruff_available(repo_root, uv)
    except (OSError, ValueError, QualityError) as error:
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
