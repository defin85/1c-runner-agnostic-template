"""template-update stops on a broken target matrix without changing the project and seeds missing files (R22)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.python.common import CommandError
from scripts.python.template_tools import template_update_preflight, update_template

MATRIX_RELPATH = "automation/context/target-matrix.json"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _matrix(root: Path, extensions: list[str]) -> None:
    payload = {
        "schemaVersion": 1,
        "targets": [{"id": "main", "sourcePath": "src/cf/main"}],
        "extensionMatrix": {"main": extensions},
    }
    _write(root, MATRIX_RELPATH, json.dumps(payload, indent=2) + "\n")


def _project(root: Path, extensions: list[str]) -> Path:
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _write(root, "src/cf/main/Configuration.xml", "<MetaDataObject/>\n")
    _write(root, "src/cfe/ProjectExtension/Configuration.xml", "<MetaDataObject/>\n")
    _write(root, ".gitignore", "*.local\n")
    _matrix(root, extensions)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "project")
    return root


def test_preflight_accepts_existing_paths(tmp_path: Path) -> None:
    root = _project(tmp_path / "project", ["ProjectExtension"])
    template_update_preflight(root)


def test_preflight_names_missing_extension_and_migration_step(tmp_path: Path) -> None:
    root = _project(tmp_path / "project", ["ProjectExtension", "MissingExtension"])
    with pytest.raises(CommandError) as error:
        template_update_preflight(root)
    message = str(error.value)
    assert "target matrix extension not found under src/cfe: MissingExtension" in message
    assert "docs/migrations/project-toolkit-update.md" in message
    assert "step 6" in message


def test_preflight_names_missing_source_path(tmp_path: Path) -> None:
    root = _project(tmp_path / "project", [])
    payload = json.loads((root / MATRIX_RELPATH).read_text(encoding="utf-8"))
    payload["targets"].append({"id": "absent", "sourcePath": "src/cf/absent"})
    _write(root, MATRIX_RELPATH, json.dumps(payload))
    with pytest.raises(CommandError, match="target source path not found: src/cf/absent"):
        template_update_preflight(root)


def test_preflight_restores_half_applied_overlay_to_head(tmp_path: Path) -> None:
    root = _project(tmp_path / "project", ["MissingExtension"])
    _write(root, ".template-overlay-version", "v-next\n")  # untracked file written by the previous script
    _write(root, "src/cf/main/Configuration.xml", "<changed/>\n")  # tracked file changed by the overlay
    _write(root, "scripts/new_tool.py", "print('overlay')\n")  # untracked file added by the overlay
    _write(root, "operator.local", "keep\n")  # ignored file of the operator
    with pytest.raises(CommandError) as error:
        template_update_preflight(root, restore_on_failure=True)
    assert "restored to HEAD" in str(error.value)
    assert _git(root, "status", "--porcelain") == ""
    assert (root / "src/cf/main/Configuration.xml").read_text(encoding="utf-8") == "<MetaDataObject/>\n"
    assert not (root / ".template-overlay-version").exists()
    assert not (root / "scripts").exists()
    assert (root / "operator.local").read_text(encoding="utf-8") == "keep\n"


def _template_release(root: Path, tag: str) -> Path:
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _write(root, "automation/context/template-managed-paths.txt", "template-file.txt\n")
    _write(root, "template-file.txt", f"{tag}\n")
    _write(root, "ruff.toml", 'extend = "scripts/qa/ruff-base.toml"\n')
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", tag)
    _git(root, "tag", tag)
    return root


def _generated_project(root: Path, template: Path, version: str, extensions: list[str]) -> Path:
    _project(root, extensions)
    _write(root, ".copier-answers.yml", f"_commit: v0.1.0\n_src_path: {template}\nproject_name: Demo\n")
    _write(root, ".template-overlay-version", f"{version}\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "answers")
    return root


def test_update_template_refuses_broken_matrix_before_overlay(tmp_path: Path) -> None:
    template = _template_release(tmp_path / "template", "v0.2.0")
    root = _generated_project(tmp_path / "project", template, "v0.1.0", ["MissingExtension"])
    with pytest.raises(CommandError, match="MissingExtension"):
        update_template("v0.2.0", root=root)
    assert _git(root, "status", "--porcelain") == ""
    assert not (root / "template-file.txt").exists()
    assert not (root / "ruff.toml").exists()


def test_repeated_update_template_seeds_missing_ruff_config(tmp_path: Path) -> None:
    template = _template_release(tmp_path / "template", "v0.2.0")
    root = _generated_project(tmp_path / "project", template, "v0.2.0", ["ProjectExtension"])
    assert update_template("v0.2.0", root=root) == 0
    assert (root / "ruff.toml").read_text(encoding="utf-8") == 'extend = "scripts/qa/ruff-base.toml"\n'
    _write(root, "ruff.toml", 'extend = "scripts/qa/ruff-base.toml"\nline-length = 100\n')
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "project ruff settings")
    assert update_template("v0.2.0", root=root) == 0
    assert "line-length = 100" in (root / "ruff.toml").read_text(encoding="utf-8")
