"""load-diff-src and load-task-src publish summary.json and stderr diagnostics on every failure."""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts.python.runtime import run_load_diff_src, run_load_task_src
from scripts.python.runtime_errors import CommandError

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "env" / "local.example.json"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _summary(run_root: Path) -> dict[str, Any]:
    return json.loads((run_root / "summary.json").read_text(encoding="utf-8"))


class LoadWrapperFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name)
        self.repo = self.temp / "repo"
        (self.repo / "src" / "cf").mkdir(parents=True)
        (self.repo / "README.outside").write_text("outside\n", encoding="utf-8")
        _git(self.repo, "init", "-q")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-q", "-m", "initial")
        root_patch = patch("scripts.python.runtime.project_root", return_value=self.repo)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def _fail(self, runner: Any, argv: list[str]) -> tuple[CommandError, str]:
        stderr = io.StringIO()
        with redirect_stderr(stderr), self.assertRaises(CommandError) as raised:
            runner(argv)
        return raised.exception, stderr.getvalue()

    def _run(self, runner: Any, argv: list[str]) -> tuple[int, str]:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = runner(argv)
        return code, stderr.getvalue()

    def test_diff_empty_selection_reports_error_in_stderr_and_log(self) -> None:
        run_root = self.temp / "run"
        code, stderr = self._run(run_load_diff_src, ["--profile", str(PROFILE), "--run-root", str(run_root)])
        message = "error: no eligible changed files inside source tree"
        self.assertEqual(code, 65)
        self.assertIn(message, stderr)
        self.assertIn(message, (run_root / "stderr.log").read_text(encoding="utf-8"))
        self.assertEqual(_summary(run_root)["status"], "failed")

    def test_diff_files_argument_writes_failed_summary(self) -> None:
        run_root = self.temp / "run"
        error, _ = self._fail(run_load_diff_src, ["--run-root", str(run_root), "--files", "Catalogs/Items.xml"])
        summary = _summary(run_root)
        self.assertIn("--files is not supported", str(error))
        self.assertEqual((summary["status"], summary["delegated"]), ("failed", None))
        self.assertNotEqual(summary["exit_code"], 0)
        self.assertEqual(summary["selection"]["error"], str(error))
        self.assertIn(f"error: {error}", (run_root / "stderr.log").read_text(encoding="utf-8"))

    def test_diff_profile_errors_write_failed_summary(self) -> None:
        legacy = self.temp / "legacy.json"
        legacy.write_text(json.dumps({"schemaVersion": 2, "runnerAdapter": "direct-platform"}), encoding="utf-8")
        for profile, expected in (
            (self.temp / "missing.json", "runtime profile not found: "),
            (legacy, "runtime profile schemaVersion=2 is no longer supported"),
        ):
            with self.subTest(profile=profile.name):
                run_root = self.temp / f"run-{profile.stem}"
                error, _ = self._fail(run_load_diff_src, ["--profile", str(profile), "--run-root", str(run_root)])
                summary = _summary(run_root)
                self.assertTrue(str(error).startswith(expected))
                self.assertEqual(summary["status"], "failed")
                self.assertTrue(summary["selection"]["error"].startswith(expected))

    def test_missing_git_is_reported_in_summary(self) -> None:
        run_root = self.temp / "run"
        with patch("scripts.python.runtime.shutil.which", return_value=None):
            error, _ = self._fail(run_load_diff_src, ["--profile", str(PROFILE), "--run-root", str(run_root)])
        self.assertEqual(str(error), "command not found: git")
        self.assertEqual(_summary(run_root)["selection"]["error"], "command not found: git")

    def test_help_does_not_write_summary(self) -> None:
        run_root = self.temp / "run"
        for runner in (run_load_diff_src, run_load_task_src):
            with self.subTest(runner=runner.__name__):
                error, _ = self._fail(runner, ["--run-root", str(run_root), "--help"])
                self.assertEqual(str(error), "help-requested")
                self.assertFalse((run_root / "summary.json").exists())

    def test_task_selector_conflict_writes_summary_with_selector(self) -> None:
        run_root = self.temp / "run"
        argv = ["--profile", str(PROFILE), "--run-root", str(run_root), "--work-item", "1002", "--range", "HEAD"]
        error, _ = self._fail(run_load_task_src, argv)
        summary = _summary(run_root)
        self.assertEqual(str(error), "load-task-src requires exactly one selector")
        self.assertEqual(summary["selection"]["selector"], {"mode": "work-item", "value": "1002"})
        self.assertEqual(summary["selection"]["error"], str(error))
        self.assertIsNone(summary["delegated"])

    def test_task_without_matching_commits_reports_error(self) -> None:
        run_root = self.temp / "run"
        argv = ["--profile", str(PROFILE), "--run-root", str(run_root), "--work-item", "9999"]
        code, stderr = self._run(run_load_task_src, argv)
        self.assertEqual(code, 65)
        self.assertIn("error: no commits matched selector", stderr)
        self.assertIn("error: no commits matched selector", (run_root / "stderr.log").read_text(encoding="utf-8"))
        self.assertEqual(_summary(run_root)["selection"]["error"], "no commits matched selector")


if __name__ == "__main__":
    unittest.main()
