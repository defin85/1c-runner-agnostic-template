from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.python import optional_modules
from scripts.python.common import CommandError
from scripts.python.optional_modules import (
    PRESERVE_RELPATH,
    is_unmaterialized_optional_path,
    materialize_module,
    module_targets,
    optional_module_init,
    owning_optional_root,
)

SITE = "customer-site-operations"
SITE_TARGETS = [
    "infra/site/",
    "docs/infra/site/",
    ".agents/skills/site-backup/",
    ".claude/skills/site-backup/",
    ".agents/skills/site-restore/",
    ".claude/skills/site-restore/",
]
PRESERVE_BEFORE = "# Project-owned paths.\nMakefile.project\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _site_blueprint(root: Path) -> Path:
    files = root / "automation" / "optional" / SITE / "files"
    _write(root / "automation" / "optional" / SITE / "README.md", "blueprint notes, not copied\n")
    _write(files / "infra" / "site" / "profiles" / "example.json", "{}\n")
    _write(files / "infra" / "site" / "server" / "wrapper.py", "print('ok')\n")
    _write(files / "docs" / "infra" / "site" / "README.md", "# Site\n")
    _write(files / ".agents" / "skills" / "site-backup" / "SKILL.md", "backup\n")
    _write(files / ".agents" / "skills" / "site-restore" / "SKILL.md", "restore\n")
    _write(root / PRESERVE_RELPATH, PRESERVE_BEFORE)
    return files


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "automation/optional" not in path.as_posix()
    }


class OptionalModuleTargetsTests(unittest.TestCase):
    def test_glob_target_expands_to_blueprint_skills_with_claude_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _site_blueprint(root)
            self.assertEqual([target for _source, target in module_targets(root, SITE)], SITE_TARGETS)

    def test_unknown_module_lists_known_modules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, self.assertRaises(CommandError) as raised:
            module_targets(Path(temp_dir), "unknown")
        self.assertIn("unknown optional module: unknown", str(raised.exception))
        self.assertIn("kd21-migration", str(raised.exception))

    def test_missing_blueprint_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, self.assertRaises(CommandError) as raised:
            module_targets(Path(temp_dir), "kd21-migration")
        self.assertIn(
            "optional module blueprint is missing: automation/optional/kd21-migration/files", str(raised.exception)
        )

    def test_blueprint_without_declared_target_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            files = _site_blueprint(root)
            for path in sorted((files / "docs").rglob("*"), reverse=True):
                path.unlink() if path.is_file() else path.rmdir()
            (files / "docs").rmdir()
            with self.assertRaises(CommandError) as raised:
                module_targets(root, SITE)
        self.assertIn("blueprint lacks declared target directory docs/infra/site/", str(raised.exception))

    def test_blueprint_path_outside_targets_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            files = _site_blueprint(root)
            _write(files / "scripts" / "stray.sh", "exit 0\n")
            with self.assertRaises(CommandError) as raised:
                module_targets(root, SITE)
        self.assertIn("blueprint path scripts/stray.sh lies outside declared targets", str(raised.exception))

    @unittest.skipIf(os.name == "nt", "creating symbolic links needs extra privileges on Windows")
    def test_blueprint_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            files = _site_blueprint(root)
            (files / "infra" / "site" / "link").symlink_to(files / "infra" / "site" / "profiles")
            with self.assertRaises(CommandError) as raised:
                module_targets(root, SITE)
        self.assertIn("symbolic links are not allowed", str(raised.exception))

    def test_owning_root_expands_glob_targets(self) -> None:
        self.assertEqual(owning_optional_root("infra/site/server/wrapper.py"), "infra/site/")
        self.assertEqual(owning_optional_root(".agents/skills/site-backup/SKILL.md"), ".agents/skills/site-backup/")
        self.assertEqual(
            owning_optional_root("docs/agent/kd21-rules-workbench-runbook.md"),
            "docs/agent/kd21-rules-workbench-runbook.md",
        )
        self.assertIsNone(owning_optional_root("docs/agent/kd21-rules-workbench-runbook.md/extra"))
        self.assertIsNone(owning_optional_root("infra/other/file"))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertTrue(is_unmaterialized_optional_path(root, "./migration/kd21/run.sh"))
            (root / "migration" / "kd21").mkdir(parents=True)
            self.assertFalse(is_unmaterialized_optional_path(root, "migration/kd21/run.sh"))


class MaterializeModuleTests(unittest.TestCase):
    def test_first_init_copies_blueprint_and_registers_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _site_blueprint(root)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(optional_module_init([SITE], root=root), 0)

            self.assertEqual((root / "infra/site/server/wrapper.py").read_text(encoding="utf-8"), "print('ok')\n")
            self.assertEqual((root / "docs/infra/site/README.md").read_text(encoding="utf-8"), "# Site\n")
            self.assertEqual((root / ".claude/skills/site-backup/SKILL.md").read_text(encoding="utf-8"), "backup\n")
            self.assertFalse((root / "README.md").exists())
            preserve = (root / PRESERVE_RELPATH).read_text(encoding="utf-8")
            self.assertTrue(preserve.startswith(PRESERVE_BEFORE))
            self.assertEqual(preserve.splitlines()[3:], SITE_TARGETS)
            self.assertEqual([path.name for path in root.iterdir() if path.name.startswith(".optional-module")], [])
            self.assertIn("infra/site/", stdout.getvalue())

    def test_repeated_init_fails_without_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _site_blueprint(root)
            with contextlib.redirect_stdout(io.StringIO()):
                optional_module_init([SITE], root=root)
            (root / "infra/site/profiles/example.json").write_text('{"project": true}\n', encoding="utf-8")
            before = _tree(root)
            with self.assertRaises(CommandError) as raised:
                materialize_module(root, SITE)
            self.assertEqual(_tree(root), before)
        self.assertIn("target paths already exist: infra/site/, docs/infra/site/", str(raised.exception))

    def test_single_existing_target_blocks_whole_module(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _site_blueprint(root)
            _write(root / ".claude/skills/site-restore/SKILL.md", "project copy\n")
            before = _tree(root)
            with self.assertRaises(CommandError) as raised:
                materialize_module(root, SITE)
            self.assertEqual(_tree(root), before)
            self.assertFalse((root / "infra").exists())
        self.assertIn(".claude/skills/site-restore/", str(raised.exception))

    def test_failure_while_publishing_removes_copied_paths_and_created_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _site_blueprint(root)
            _write(root / "docs" / "infra", "a file where the module needs a directory\n")
            before = _tree(root)
            with self.assertRaises(OSError):
                materialize_module(root, SITE)
            self.assertEqual(_tree(root), before)
            self.assertFalse((root / "infra").exists())
            self.assertFalse((root / ".agents").exists())
            self.assertEqual([path.name for path in root.iterdir() if path.name.startswith(".optional-module")], [])

    def test_failure_while_registering_restores_preserve_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _site_blueprint(root)
            before = _tree(root)

            def broken_register(preserve_file: Path, module: str, targets: list[str]) -> None:
                preserve_file.write_text("partially written\n", encoding="utf-8")
                raise OSError("disk full")

            with patch.object(optional_modules, "_register_preserved", broken_register), self.assertRaises(OSError):
                materialize_module(root, SITE)
            self.assertEqual(_tree(root), before)
            for target in SITE_TARGETS:
                self.assertFalse((root / target.rstrip("/")).exists(), target)

    def test_failure_while_staging_leaves_project_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _site_blueprint(root)
            before = _tree(root)
            with patch.object(optional_modules.shutil, "copytree", side_effect=OSError("read error")):
                with self.assertRaises(OSError):
                    materialize_module(root, SITE)
            self.assertEqual(_tree(root), before)
            self.assertEqual([path.name for path in root.iterdir() if path.name.startswith(".optional-module")], [])

    def test_missing_module_argument_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, self.assertRaises(CommandError) as raised:
            optional_module_init([], root=Path(temp_dir))
        self.assertIn("make optional-module-init MODULE=<name>", str(raised.exception))


class OverlaySyncPreserveTests(unittest.TestCase):
    def test_python_overlay_sync_honors_project_preserve_list(self) -> None:
        from scripts.python.template_tools import sync_overlay_manifests

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(root / "release" / "infra/site/README.md", "template\n")
            _write(root / "release" / "scripts/tool.sh", "template\n")
            _write(root / "project" / "infra/site/README.md", "project\n")
            _write(root / "next.txt", "infra/site/README.md\nscripts/tool.sh\n")
            _write(root / "release-preserve.txt", "Makefile.project\n")
            _write(root / "project-preserve.txt", "# Optional module\ninfra/site/\n")
            sync_overlay_manifests(
                root / "release",
                root / "project",
                root / "missing.txt",
                root / "next.txt",
                [root / "release-preserve.txt", root / "project-preserve.txt"],
            )
            self.assertEqual((root / "project/infra/site/README.md").read_text(encoding="utf-8"), "project\n")
            self.assertEqual((root / "project/scripts/tool.sh").read_text(encoding="utf-8"), "template\n")


if __name__ == "__main__":
    unittest.main()
