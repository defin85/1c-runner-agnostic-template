"""Project-owned extension points of template-managed entrypoints.

- `Makefile.project` / `make.project.ps1`: project targets included by `Makefile` / `make.ps1`.
- `scripts/qa/agent-verify.d/`: project steps that `agent-verify` runs after the template baseline.
- A marked block inside `.gitignore`, `.gitattributes` and `.contextignore`: project lines that
  `template-update` carries over when it refreshes the template part of these files.

The template never ships these project-owned paths; they are listed in
`automation/context/template-update-preserve-paths.txt` so overlay sync never writes them.

Seed-once Python environment (design decision R15): `pyproject.toml`, `uv.lock`,
`requirements-dev.txt` and `pyrightconfig.json` ship with the template, reach a generated
project through `copier copy` (or through `template-update` when the project lacks them),
and afterwards belong to the project: overlay sync never overwrites them.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from .common import CommandError, run_process

AGENT_VERIFY_STEPS_RELPATH = "scripts/qa/agent-verify.d"
PROJECT_BLOCK_BEGIN = "# >>> project-owned block: template-update keeps the lines up to the closing marker >>>"
PROJECT_BLOCK_END = "# <<< project-owned block <<<"
PROJECT_BLOCK_FILES = frozenset({".gitignore", ".gitattributes", ".contextignore"})
_IGNORED_STEP_SUFFIXES = frozenset({".md", ".txt"})
# Keep in sync with PROJECT_OWNED_PYTHON_SEED_PATHS in scripts/template/lib-overlay.sh.
PROJECT_OWNED_PYTHON_SEED_PATHS = ("pyproject.toml", "uv.lock", "requirements-dev.txt", "pyrightconfig.json")


def _block_bounds(lines: list[str], label: str) -> tuple[int, int] | None:
    begins = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == PROJECT_BLOCK_BEGIN]
    ends = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == PROJECT_BLOCK_END]
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1 or begins[0] > ends[0]:
        raise CommandError(
            f"{label}: project-owned block must have exactly one opening and one closing marker in this order"
        )
    return begins[0], ends[0]


def merge_project_block(template_text: str, current_text: str, rel: str) -> str:
    """Return the template file content with the project-owned block taken from the current file."""
    current_lines = current_text.splitlines(keepends=True)
    current_bounds = _block_bounds(current_lines, f"{rel} (project)")
    template_lines = template_text.splitlines(keepends=True)
    template_bounds = _block_bounds(template_lines, f"{rel} (template release)")
    if current_bounds is None:
        return template_text
    block = current_lines[current_bounds[0] : current_bounds[1] + 1]
    if not block[-1].endswith("\n"):
        block[-1] += "\n"
    if template_bounds is None:
        prefix = template_text if not template_text or template_text.endswith("\n") else template_text + "\n"
        return prefix + "".join(block)
    return "".join(template_lines[: template_bounds[0]] + block + template_lines[template_bounds[1] + 1 :])


def copy_with_project_block(source_path: Path, target_path: Path, rel: str) -> bool:
    """Copy a template file; return True when the project-owned block was merged instead."""
    if rel not in PROJECT_BLOCK_FILES or not target_path.is_file():
        return False
    merged = merge_project_block(source_path.read_text(encoding="utf-8"), target_path.read_text(encoding="utf-8"), rel)
    with target_path.open("w", encoding="utf-8", newline="") as stream:
        stream.write(merged)
    shutil.copymode(source_path, target_path)
    return True


def seed_missing_project_files(source_root: Path, target_root: Path, *, dry_run: bool = False) -> list[str]:
    """Copy seed-once project files from a template release only when the project lacks them."""
    seeded: list[str] = []
    for rel in PROJECT_OWNED_PYTHON_SEED_PATHS:
        source_path = source_root / rel
        target_path = target_root / rel
        if target_path.exists() or not source_path.is_file():
            continue
        seeded.append(rel)
        if dry_run:
            print(f"seed {rel}")
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
    return seeded


def is_preserved(rel: str, preserve_entries: set[str]) -> bool:
    """Exact preserve entries match one path; entries ending with `/` match a whole directory."""
    if rel in preserve_entries:
        return True
    return any(entry.endswith("/") and rel.startswith(entry) for entry in preserve_entries)


def _powershell() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def _step_command(step: Path) -> list[str] | None:
    suffix = step.suffix.lower()
    if suffix == ".py":
        return [sys.executable, str(step)]
    if suffix == ".sh":
        return None if os.name == "nt" else ["bash", str(step)]
    if suffix == ".ps1":
        shell = _powershell() if os.name == "nt" else None
        return None if shell is None else [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(step)]
    raise CommandError(f"unsupported agent-verify project step (use .py, .sh or .ps1): {step}")


def run_project_verify_steps(repo_root: Path) -> int:
    """Run project-owned agent-verify steps in name order; stop at the first failure."""
    steps_dir = repo_root / AGENT_VERIFY_STEPS_RELPATH
    if not steps_dir.is_dir():
        return 0
    steps = sorted(
        path
        for path in steps_dir.iterdir()
        if path.is_file() and not path.name.startswith(".") and path.suffix.lower() not in _IGNORED_STEP_SUFFIXES
    )
    for step in steps:
        rel = step.relative_to(repo_root).as_posix()
        command = _step_command(step)
        if command is None:
            print(f"==> Skip project agent-verify step for another platform: {rel}", flush=True)
            continue
        print(f"==> Project agent-verify step: {rel}", flush=True)
        returncode = run_process(command, cwd=repo_root, check=False, capture_output=False).returncode
        if returncode != 0:
            print(f"project agent-verify step failed with exit code {returncode}: {rel}", file=sys.stderr)
            return returncode
    return 0
