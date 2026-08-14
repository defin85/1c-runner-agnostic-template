from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.python.cfe_runtime import build_cfe_commands, run_cfe_command, validate_extension_name
from scripts.python.runtime_errors import CommandError
from scripts.python.runtime_profiles import load_runtime_profile


ROOT = Path(__file__).resolve().parents[2]


class CfeRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = load_runtime_profile(ROOT / "env" / "windows-local.example.json")

    def test_load_cfe_has_import_check_apply_sequence(self) -> None:
        commands = build_cfe_commands("load-cfe", self.profile, "Расширение Тест", dry_run=True)
        self.assertEqual([command[2] for command in commands], ["import", "check", "apply"])
        self.assertTrue(any("--extension=Расширение Тест" == arg for arg in commands[0]))
        self.assertTrue(commands[0][-1].endswith(str(Path("src/cfe/Расширение Тест"))))

    def test_runtime_flags_are_structured(self) -> None:
        command = build_cfe_commands("configure-cfe-runtime-flags", self.profile, "Тест", dry_run=True)[0]
        self.assertIn("--safe-mode=no", command)
        self.assertIn("--unsafe-action-protection=no", command)

    def test_checks_target_exact_extension(self) -> None:
        applicability = build_cfe_commands("check-cfe-applicability", self.profile, "Тест", dry_run=True)[0]
        config = build_cfe_commands("check-cfe-config", self.profile, "Тест", dry_run=True)[0]
        self.assertEqual(applicability[-2:], ["-Extension", "Тест"])
        self.assertEqual(config[-2:], ["-Extension", "Тест"])

    def test_extension_name_rejects_path_traversal(self) -> None:
        for value in ("../foreign", "nested/foreign", "nested\\foreign", ""):
            with self.subTest(value=value), self.assertRaises(CommandError):
                validate_extension_name(value)

    def test_summary_and_logs_redact_resolved_secrets(self) -> None:
        secret = "cfe-secret-value"
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"ONEC_IBCMD_PASSWORD": secret}):
            run_root = Path(temp_dir) / "run"

            def fake_run(*_args: object, stdout_path: Path, stderr_path: Path, **_kwargs: object) -> int:
                Path(stdout_path).write_text(secret, encoding="utf-8")
                Path(stderr_path).write_text(secret, encoding="utf-8")
                return 0

            with patch("scripts.python.cfe_runtime.run_logged", side_effect=fake_run):
                exit_code = run_cfe_command(
                    "load-cfe",
                    ["--profile", str(ROOT / "env" / "local.example.json"), "--extension", "Тест", "--run-root", str(run_root)],
                )
            combined = "".join(
                (run_root / name).read_text(encoding="utf-8")
                for name in ("summary.json", "stdout.log", "stderr.log")
            )
            self.assertEqual(exit_code, 0)
            self.assertNotIn(secret, combined)
            self.assertIn("__REDACTED_SECRET__", combined)

    def test_interruption_publishes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_root = Path(temp_dir) / "run"
            with patch.dict(os.environ, {"ONEC_IBCMD_PASSWORD": "secret"}), patch(
                "scripts.python.cfe_runtime.run_logged", side_effect=KeyboardInterrupt
            ):
                exit_code = run_cfe_command(
                    "load-cfe",
                    ["--profile", str(ROOT / "env" / "local.example.json"), "--extension", "Тест", "--run-root", str(run_root)],
                )
            summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 130)
            self.assertEqual(summary["status"], "interrupted")


if __name__ == "__main__":
    unittest.main()
