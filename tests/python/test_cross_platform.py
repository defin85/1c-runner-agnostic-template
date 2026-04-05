from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.python.context import render_generated_tree


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / ".artifacts" / "tests"


def is_source_repo() -> bool:
    return all(
        (
            ROOT / rel
        ).is_file()
        for rel in (
            "openspec/specs/agent-runtime-toolkit/spec.md",
            "openspec/specs/project-scoped-skills/spec.md",
            "openspec/specs/template-ci-contours/spec.md",
        )
    )


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
        self.assertIn("Codex controls:", result.stdout)
        if is_source_repo():
            self.assertIn("Repository role: template-source", result.stdout)
            self.assertIn("Canonical onboarding router: docs/agent/index.md", result.stdout)
            self.assertIn("Generated-project router reference: docs/agent/generated-project-index.md", result.stdout)
            self.assertIn("Execution plan starters: docs/exec-plans/TEMPLATE.md, docs/exec-plans/EXAMPLE.md", result.stdout)
            self.assertNotIn("Recommended skills:", result.stdout)
            self.assertNotIn("AI-readiness:", result.stdout)
        else:
            self.assertIn("Repository role: generated-project", result.stdout)
            self.assertIn("Recommended skills:", result.stdout)
            self.assertIn("AI-readiness:", result.stdout)

    def test_export_context_check(self) -> None:
        if os.name == "nt":
            result = run_command(["pwsh", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "make.ps1", "export-context-check"])
        else:
            result = run_command(["bash", "-lc", "./scripts/llm/export-context.sh --check"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_python_generated_tree_excludes_local_sandbox_dir(self) -> None:
        generated_root = ARTIFACTS / "generated-tree-private-filter"
        shutil.rmtree(generated_root, ignore_errors=True)
        (generated_root / "env" / ".local").mkdir(parents=True, exist_ok=True)
        (generated_root / "env" / ".local" / "README.md").write_text("private\n", encoding="utf-8")
        (generated_root / "env" / "README.md").write_text("shared\n", encoding="utf-8")

        rendered = render_generated_tree(generated_root)

        self.assertIn("./env", rendered)
        self.assertIn("./env/README.md", rendered)
        self.assertNotIn("./env/.local\n", rendered)
        self.assertNotIn("./env/.local/README.md", rendered)

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

    def test_imported_skill_surface(self) -> None:
        manifest_path = ROOT / "automation" / "vendor" / "cc-1c-skills" / "imported-skills.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        skills = payload.get("skills", [])
        self.assertEqual(len(skills), 67)
        for entry in skills:
            name = entry["name"]
            self.assertTrue((ROOT / ".agents" / "skills" / name / "SKILL.md").is_file(), f"missing Codex skill: {name}")
            self.assertTrue((ROOT / ".claude" / "skills" / name / "SKILL.md").is_file(), f"missing Claude skill: {name}")
            self.assertTrue((ROOT / "automation" / "vendor" / "cc-1c-skills" / entry["vendor_dir"]).is_dir(), f"missing vendored skill dir: {name}")
            codex_text = (ROOT / ".agents" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(f"Repo script: `./scripts/skills/run-imported-skill.sh {name}`", codex_text)

    def test_reference_dispatcher(self) -> None:
        if os.name == "nt":
            command = [
                "pwsh",
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "scripts/skills/run-imported-skill.ps1",
                "form-patterns",
            ]
        else:
            command = [
                "bash",
                "-lc",
                "./scripts/skills/run-imported-skill.sh form-patterns",
            ]
        result = run_command(command)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Imported skill: form-patterns", result.stdout)
        self.assertIn("Runtime kind: reference", result.stdout)

    def test_imported_skill_readiness_contract(self) -> None:
        if os.name == "nt":
            command = [
                "pwsh",
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "scripts/skills/run-imported-skill.ps1",
                "--readiness",
                "--json",
            ]
        else:
            command = ["bash", "-lc", "./scripts/skills/run-imported-skill.sh --readiness --json"]
        result = run_command(command)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["canonicalTarget"], "make imported-skills-readiness")
        self.assertEqual(payload["representative"]["python"]["representative_skill"], "cf-edit")
        self.assertEqual(payload["representative"]["node"]["representative_skill"], "web-test")


if __name__ == "__main__":
    unittest.main()
