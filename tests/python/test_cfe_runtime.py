from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.python.cfe_runtime import build_cfe_commands, run_cfe_command, validate_extension_name
from scripts.python.runtime_errors import CommandError
from scripts.python.runtime_observation import ObservationRequest, ObservationResult
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

            def fake_run(request: ObservationRequest) -> ObservationResult:
                assert request.stdout_log is not None and request.stderr_log is not None
                request.stdout_log.write_text(secret, encoding="utf-8")
                request.stderr_log.write_text(secret, encoding="utf-8")
                return ObservationResult(0, "completed", "completed", request.run_root / "observation.jsonl")

            with patch("scripts.python.cfe_runtime.run_observed", side_effect=fake_run):
                exit_code = run_cfe_command(
                    "load-cfe",
                    [
                        "--profile",
                        str(ROOT / "env" / "local.example.json"),
                        "--extension",
                        "Тест",
                        "--run-root",
                        str(run_root),
                    ],
                )
            combined = "".join(
                (run_root / name).read_text(encoding="utf-8") for name in ("summary.json", "stdout.log", "stderr.log")
            )
            self.assertEqual(exit_code, 0)
            self.assertNotIn(secret, combined)
            self.assertIn("__REDACTED_SECRET__", combined)

    def test_interruption_publishes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_root = Path(temp_dir) / "run"
            with (
                patch.dict(os.environ, {"ONEC_IBCMD_PASSWORD": "secret"}),
                patch("scripts.python.cfe_runtime.run_observed", side_effect=KeyboardInterrupt),
            ):
                exit_code = run_cfe_command(
                    "load-cfe",
                    [
                        "--profile",
                        str(ROOT / "env" / "local.example.json"),
                        "--extension",
                        "Тест",
                        "--run-root",
                        str(run_root),
                    ],
                )
            summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 130)
            self.assertEqual(summary["status"], "interrupted")

    def _fake_platform_profile(self, temp: Path, script: str) -> Path:
        binary = temp / "bin" / "1cv8"
        binary.parent.mkdir()
        binary.write_text("#!/bin/sh\n" + script, encoding="utf-8")
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
        payload = json.loads((ROOT / "env" / "local.example.json").read_text(encoding="utf-8"))
        payload["platform"]["binaryPath"] = str(binary)
        profile = temp / "profile.json"
        profile.write_text(json.dumps(payload), encoding="utf-8")
        return profile

    @unittest.skipIf(os.name == "nt", "POSIX shell fixture")
    def test_designer_check_is_observed_and_summarized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            profile = self._fake_platform_profile(temp, "echo designer-ran\nexit 0\n")
            run_root = temp / "run"
            with patch.dict(os.environ, {"ONEC_OBSERVATION_INTERVAL_SECONDS": "1"}):
                exit_code = run_cfe_command(
                    "check-cfe-config", ["--profile", str(profile), "--extension", "Тест", "--run-root", str(run_root)]
                )
            events = [
                json.loads(line) for line in (run_root / "observation.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual([events[0]["event"], events[-1]["event"]], ["started", "completed"])
            self.assertEqual(events[0]["capability"], "check-cfe-config")
            self.assertEqual(summary["observation"]["terminalEvent"], "completed")
            self.assertIn("designer-ran", (run_root / "stdout.log").read_text(encoding="utf-8"))
            self.assertTrue((run_root / "process.pid").is_file())

    @unittest.skipIf(os.name == "nt", "POSIX shell fixture")
    def test_designer_stall_stops_only_with_wrapper_threshold(self) -> None:
        script = 'printf stage-1 > "$ONEC_OBSERVATION_PROGRESS_FILE"\nsleep 4\nexit 0\n'
        for threshold, expected in (("1", 125), ("", 0)):
            with self.subTest(threshold=threshold), tempfile.TemporaryDirectory() as temp_dir:
                temp = Path(temp_dir)
                profile = self._fake_platform_profile(temp, script)
                run_root = temp / "run"
                env = {"ONEC_OBSERVATION_INTERVAL_SECONDS": "1", "ONEC_OBSERVATION_STALL_TIMEOUT_SECONDS": threshold}
                with patch.dict(os.environ, env):
                    exit_code = run_cfe_command(
                        "check-cfe-applicability",
                        ["--profile", str(profile), "--extension", "Тест", "--run-root", str(run_root)],
                    )
                summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
                self.assertEqual(exit_code, expected)
                self.assertEqual(summary["observation"]["terminalReason"], "stalled" if expected else "completed")

    def test_multi_step_operation_keeps_one_observation_per_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_root = Path(temp_dir) / "run"
            roots: list[Path] = []

            def fake_run(request: ObservationRequest) -> ObservationResult:
                roots.append(request.run_root)
                return ObservationResult(0, "completed", "completed", request.run_root / "observation.jsonl")

            with (
                patch.dict(os.environ, {"ONEC_IBCMD_PASSWORD": "secret"}),
                patch("scripts.python.cfe_runtime.run_observed", side_effect=fake_run),
            ):
                exit_code = run_cfe_command(
                    "load-cfe",
                    [
                        "--profile",
                        str(ROOT / "env" / "local.example.json"),
                        "--extension",
                        "Тест",
                        "--run-root",
                        str(run_root),
                    ],
                )
            self.assertEqual(exit_code, 0)
            self.assertEqual(roots, [run_root / "steps" / name for name in ("01", "02", "03")])


if __name__ == "__main__":
    unittest.main()
