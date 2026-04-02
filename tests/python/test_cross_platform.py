from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / ".artifacts" / "tests"


def run_command(command: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    final_env = os.environ.copy()
    if env:
        final_env.update(env)
    return subprocess.run(
        command,
        cwd=ROOT,
        env=final_env,
        text=True,
        capture_output=True,
        check=False,
    )


class CrossPlatformSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        shutil.rmtree(ARTIFACTS, ignore_errors=True)
        ARTIFACTS.mkdir(parents=True, exist_ok=True)

    def test_onboard_entrypoint(self) -> None:
        if os.name == "nt":
            result = run_command(["pwsh", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "make.ps1", "codex-onboard"])
        else:
            result = run_command(["bash", "-lc", "./scripts/qa/codex-onboard.sh"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Codex Onboard", result.stdout)

    def test_export_context_check(self) -> None:
        if os.name == "nt":
            result = run_command(["pwsh", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "make.ps1", "export-context-check"])
        else:
            result = run_command(["bash", "-lc", "./scripts/llm/export-context.sh --check"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_doctor_dry_run_summary(self) -> None:
        run_root = ARTIFACTS / "doctor"
        env = {"ONEC_IBCMD_PASSWORD": "dummy"}
        if os.name == "nt":
            command = [
                "pwsh",
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "scripts/diag/doctor.ps1",
                "--profile",
                "env/windows-local.example.json",
                "--run-root",
                str(run_root),
                "--dry-run",
            ]
        else:
            command = [
                "bash",
                "-lc",
                f"./scripts/diag/doctor.sh --profile env/local.example.json --run-root '{run_root.as_posix()}' --dry-run",
            ]
        result = run_command(command, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary_path = run_root / "summary.json"
        self.assertTrue(summary_path.is_file(), f"missing summary: {summary_path}")


if __name__ == "__main__":
    unittest.main()
