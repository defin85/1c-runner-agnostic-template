"""Optional modules: project-owned paths that appear only after `make optional-module-init`.

Blueprint format (design D1). The template ships each module as
`automation/optional/<module>/files/<project-relative path>`: every file under `files/` is copied to the
same project-relative path. Other files in `automation/optional/<module>/` (for example `README.md`)
describe the blueprint and are not copied. Every blueprint path must lie under one of the module
targets declared in `OPTIONAL_MODULE_TARGETS`; a declared target without a `*` must be present in the
blueprint, and a `*` target must match at least one blueprint entry. Symbolic links are not allowed.
A skill directory `.agents/skills/<name>/` is also mirrored to `.claude/skills/<name>/`.

`optional-module-init` checks every target before writing, refuses to overwrite anything, removes what
it copied when a step fails and registers the materialized paths in the project preserve list
`automation/context/template-update-preserve-paths.txt`, so `template-update` never writes them.

Template-shipped skills may name module paths before the module is enabled in a generated project.
Checks treat such a path as absent-by-design while the module root does not exist, and verify it normally
once the module is materialized.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath

from .common import die, project_root

# Project-owned roots created by `make optional-module-init MODULE=<name>` (design D1).
# A trailing slash marks a directory root; other entries are single files. A `*` is allowed only in the
# last segment and expands to the matching blueprint entries.
OPTIONAL_MODULE_TARGETS: dict[str, tuple[str, ...]] = {
    "customer-site-operations": ("infra/site/", "docs/infra/site/", ".agents/skills/site-*/"),
    "kd21-migration": (
        "migration/kd21/",
        "docs/agent/kd21-rules-workbench-runbook.md",
        ".agents/skills/1c-prepare-manual-migration-bases/",
    ),
}

# Fixed extension directories created by `init-test-tooling` under `src/cfe/`.
TEST_TOOLING_TARGETS: tuple[str, ...] = ("src/cfe/VATestContour/", "src/cfe/YAxUnit/", "src/cfe/VAExtension/")

OPTIONAL_ROOT_RELPATH = "automation/optional"
BLUEPRINT_FILES_DIRNAME = "files"
PRESERVE_RELPATH = "automation/context/template-update-preserve-paths.txt"
AGENTS_SKILLS_PREFIX = ".agents/skills/"
CLAUDE_SKILLS_PREFIX = ".claude/skills/"


def optional_target_roots() -> tuple[str, ...]:
    roots = [target for targets in OPTIONAL_MODULE_TARGETS.values() for target in targets]
    return (*roots, *TEST_TOOLING_TARGETS)


def _matched_root(normalized: str, root: str) -> str | None:
    """Return the concrete root that `normalized` lies in, expanding a `*` in the root's last segment."""
    root_parts = root.rstrip("/").split("/")
    path_parts = normalized.split("/")
    if len(path_parts) < len(root_parts):
        return None
    if not all(fnmatch.fnmatchcase(part, pattern) for part, pattern in zip(path_parts, root_parts, strict=False)):
        return None
    if len(path_parts) > len(root_parts) and not root.endswith("/"):
        return None
    concrete = "/".join(path_parts[: len(root_parts)])
    return concrete + "/" if root.endswith("/") else concrete


def owning_optional_root(rel: str) -> str | None:
    normalized = rel.removeprefix("./").replace("\\", "/")
    for root in optional_target_roots():
        matched = _matched_root(normalized, root)
        if matched is not None:
            return matched
    return None


def is_unmaterialized_optional_path(repo_root: Path, rel: str) -> bool:
    root = owning_optional_root(rel)
    return root is not None and not (repo_root / root.rstrip("/")).exists()


def blueprint_files_dir(repo_root: Path, module: str) -> Path:
    return repo_root / OPTIONAL_ROOT_RELPATH / module / BLUEPRINT_FILES_DIRNAME


def _relative(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def _blueprint_entries(files_dir: Path) -> list[str]:
    entries: list[str] = []
    for current, dirnames, filenames in os.walk(files_dir):
        current_path = Path(current)
        for name in sorted(dirnames) + sorted(filenames):
            path = current_path / name
            if path.is_symlink():
                die(f"symbolic links are not allowed in an optional module blueprint: {path}")
            if path.is_file():
                entries.append(_relative(path, files_dir))
        dirnames.sort()
    return sorted(entries)


def _expand_target(files_dir: Path, module: str, target: str) -> list[str]:
    is_dir = target.endswith("/")
    rel = target.rstrip("/")
    parent, _, last = rel.rpartition("/")
    if "*" in parent:
        die(f"optional module {module}: `*` is allowed only in the last target segment: {target}")
    if "*" not in last:
        source = files_dir / rel
        if not (source.is_dir() if is_dir else source.is_file()):
            kind = "directory" if is_dir else "file"
            die(f"optional module {module}: blueprint lacks declared target {kind} {target} ({source})")
        return [target]
    parent_dir = files_dir / parent if parent else files_dir
    matches = (
        sorted(
            path.name
            for path in parent_dir.iterdir()
            if fnmatch.fnmatchcase(path.name, last) and (path.is_dir() if is_dir else path.is_file())
        )
        if parent_dir.is_dir()
        else []
    )
    if not matches:
        die(f"optional module {module}: blueprint has no entry for declared target {target}")
    prefix = f"{parent}/" if parent else ""
    return [f"{prefix}{name}{'/' if is_dir else ''}" for name in matches]


def module_targets(repo_root: Path, module: str) -> list[tuple[str, str]]:
    """Return `(blueprint relpath, project target)` pairs for one module in copy order.

    Directory entries keep a trailing slash. A skill directory is followed by its `.claude/skills/` mirror.
    """
    if module not in OPTIONAL_MODULE_TARGETS:
        known = ", ".join(sorted(OPTIONAL_MODULE_TARGETS))
        die(f"unknown optional module: {module or '<empty>'}; known modules: {known}")
    files_dir = blueprint_files_dir(repo_root, module)
    if files_dir.is_symlink() or not files_dir.is_dir():
        die(f"optional module blueprint is missing: {_relative(files_dir, repo_root)}")
    roots = [root for target in OPTIONAL_MODULE_TARGETS[module] for root in _expand_target(files_dir, module, target)]
    for entry in _blueprint_entries(files_dir):
        if not any(_matched_root(entry, root) is not None for root in roots):
            declared = ", ".join(OPTIONAL_MODULE_TARGETS[module])
            die(f"optional module {module}: blueprint path {entry} lies outside declared targets: {declared}")
    pairs: list[tuple[str, str]] = []
    for root in roots:
        pairs.append((root, root))
        if root.startswith(AGENTS_SKILLS_PREFIX) and root.endswith("/"):
            pairs.append((root, CLAUDE_SKILLS_PREFIX + root.removeprefix(AGENTS_SKILLS_PREFIX)))
    return pairs


def _check_no_symlink_ancestors(repo_root: Path, target: str) -> None:
    current = repo_root
    for part in PurePosixPath(target.rstrip("/")).parts[:-1]:
        current /= part
        if current.is_symlink():
            die(f"symbolic links are not allowed in an optional module target path: {current}")


def _read_preserve(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


def _register_preserved(preserve_file: Path, module: str, targets: list[str]) -> None:
    original = _read_preserve(preserve_file)
    text = original.decode("utf-8") if original is not None else ""
    present = {line.strip() for line in text.splitlines()}
    missing = [target for target in targets if target not in present]
    if not missing:
        return
    if text and not text.endswith("\n"):
        text += "\n"
    text += f"# Optional module {module}: materialized by `make optional-module-init`, owned by the project.\n"
    text += "".join(f"{target}\n" for target in missing)
    preserve_file.parent.mkdir(parents=True, exist_ok=True)
    fd, staged_name = tempfile.mkstemp(prefix=".preserve-", dir=preserve_file.parent)
    staged = Path(staged_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(staged, preserve_file)
    finally:
        staged.unlink(missing_ok=True)


def _restore_preserve(preserve_file: Path, original: bytes | None) -> None:
    if original is None:
        preserve_file.unlink(missing_ok=True)
    elif _read_preserve(preserve_file) != original:
        preserve_file.write_bytes(original)


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists() or path.is_symlink():
        path.unlink(missing_ok=True)


def _ensure_parent(path: Path, created: list[Path]) -> None:
    missing: list[Path] = []
    current = path.parent
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir()
        created.append(directory)


def materialize_module(repo_root: Path, module: str) -> list[str]:
    """Copy one module blueprint into its project-owned targets; return the materialized targets."""
    pairs = module_targets(repo_root, module)
    files_dir = blueprint_files_dir(repo_root, module)
    existing = []
    for _source, target in pairs:
        _check_no_symlink_ancestors(repo_root, target)
        path = repo_root / target.rstrip("/")
        if path.exists() or path.is_symlink():
            existing.append(target)
    if existing:
        die(f"optional module {module} is not initialized: target paths already exist: {', '.join(existing)}")

    preserve_file = repo_root / PRESERVE_RELPATH
    original_preserve = _read_preserve(preserve_file)
    staging = Path(tempfile.mkdtemp(prefix=".optional-module-init.", dir=repo_root))
    published: list[Path] = []
    created_dirs: list[Path] = []
    try:
        for index, (source, _target) in enumerate(pairs):
            source_path = files_dir / source.rstrip("/")
            staged = staging / str(index)
            if source.endswith("/"):
                shutil.copytree(source_path, staged)
            else:
                shutil.copy2(source_path, staged)
        for index, (_source, target) in enumerate(pairs):
            path = repo_root / target.rstrip("/")
            _ensure_parent(path, created_dirs)
            os.replace(staging / str(index), path)
            published.append(path)
        _register_preserved(preserve_file, module, [target for _source, target in pairs])
    except BaseException:
        for path in reversed(published):
            _remove_path(path)
        for directory in reversed(created_dirs):
            try:
                directory.rmdir()
            except OSError:
                pass
        _restore_preserve(preserve_file, original_preserve)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return [target for _source, target in pairs]


def optional_module_init(argv: list[str], *, root: Path | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="optional-module-init",
        description="Copy an optional module blueprint from automation/optional/<module>/files/ "
        "into project-owned paths.",
    )
    parser.add_argument("module", nargs="?", default="", help="module name: " + ", ".join(OPTIONAL_MODULE_TARGETS))
    args = parser.parse_args(argv)
    if not args.module:
        known = ", ".join(sorted(OPTIONAL_MODULE_TARGETS))
        die(f"optional module name is required (make optional-module-init MODULE=<name>); known modules: {known}")
    repo_root = root or project_root()
    targets = materialize_module(repo_root, args.module)
    print(f"[optional-module-init] materialized {args.module}:")
    for target in targets:
        print(f"  {target}")
    print(f"[optional-module-init] registered these paths as project-owned in {PRESERVE_RELPATH}")
    return 0
