from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.python import imported_skills
from scripts.python.imported_skills import _mirror_claude_skills, _render_agents_skill
from scripts.python.runtime_errors import CommandError
from scripts.python.runtime_observation import ObservationRequest, ObservationResult

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_PROFILE = ROOT / "env" / "local.example.json"


class ImportedSkillsTests(unittest.TestCase):
    def test_codex_discovery_description_uses_existing_short_description(self) -> None:
        rendered = _render_agents_skill(
            {
                "name": "cf-edit",
                "description": "Точечное редактирование конфигурации 1С. Используй для изменения свойств и состава объектов.",
                "runtime_kind": "reference",
                "vendor_dir": "skills/cf-edit",
                "preferred_native_skills": [],
            }
        )
        description_line = next(line for line in rendered.splitlines() if line.startswith("description: "))
        description = json.loads(description_line.removeprefix("description: "))

        self.assertLessEqual(len(description), 72)
        self.assertNotIn("Импортированный compatibility skill", description)
        self.assertTrue(description.startswith("Точечное редактирование конфигурации 1С"))

    def test_codex_skill_documents_both_platform_launchers(self) -> None:
        rendered = _render_agents_skill(
            {
                "name": "cf-edit",
                "description": "Точечное редактирование конфигурации 1С.",
                "runtime_kind": "reference",
                "vendor_dir": "skills/cf-edit",
                "preferred_native_skills": [],
            }
        )

        self.assertIn("Repo script: `./scripts/skills/run-imported-skill.sh cf-edit`", rendered)
        self.assertIn("Windows launcher: `./scripts/skills/run-imported-skill.ps1 cf-edit`", rendered)
        self.assertIn("```powershell\n./scripts/skills/run-imported-skill.ps1 cf-edit --help", rendered)

    def test_claude_mirror_copies_source_and_keeps_owned_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / ".agents/skills/alpha"
            (source / "references").mkdir(parents=True)
            (source / "SKILL.md").write_text("---\nname: alpha\ndescription: test\n---\n", encoding="utf-8")
            (source / "references/note.md").write_text("note", encoding="utf-8")
            claude = root / ".claude/skills"
            (claude / "stale").mkdir(parents=True)
            (claude / "stale/SKILL.md").write_text("old", encoding="utf-8")
            (claude / "openspec-apply-change").mkdir()
            (claude / "openspec-apply-change/SKILL.md").write_text("openspec", encoding="utf-8")
            (claude / "README.md").write_text("readme", encoding="utf-8")

            self.assertEqual(_mirror_claude_skills(root, check=True), [".claude/skills/alpha", ".claude/skills/stale"])
            self.assertTrue((claude / "stale").is_dir())

            _mirror_claude_skills(root, check=False)

            self.assertEqual((claude / "alpha/references/note.md").read_text(encoding="utf-8"), "note")
            self.assertFalse((claude / "stale").exists())
            self.assertEqual((claude / "openspec-apply-change/SKILL.md").read_text(encoding="utf-8"), "openspec")
            self.assertEqual((claude / "README.md").read_text(encoding="utf-8"), "readme")
            self.assertEqual(_mirror_claude_skills(root, check=True), [])

            (source / "SKILL.md").write_text("---\nname: alpha\ndescription: changed\n---\n", encoding="utf-8")
            self.assertEqual(_mirror_claude_skills(root, check=True), [".claude/skills/alpha"])


def _write_profile(path: Path, **capabilities: object) -> Path:
    payload = json.loads(EXAMPLE_PROFILE.read_text(encoding="utf-8"))
    payload["capabilities"].update(capabilities)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_external_source(root: Path) -> Path:
    root_xml = root / "src" / "Demo.xml"
    module = root / "src" / "Demo" / "Ext" / "ObjectModule.bsl"
    module.parent.mkdir(parents=True)
    root_xml.write_text("<MetaDataObject/>", encoding="utf-8")
    module.write_bytes("Процедура Тест()\nКонецПроцедуры\n".encode())
    return root_xml


class ImportedProfileDispatchTests(unittest.TestCase):
    def test_manifest_routes_platform_skills_through_profile(self) -> None:
        manifest = json.loads(imported_skills.IMPORT_MANIFEST.read_text(encoding="utf-8"))
        kinds = {entry["name"]: entry["runtime_kind"] for entry in manifest["skills"]}
        for name in (
            "db-load-cf",
            "db-dump-cf",
            "db-load-xml",
            "db-dump-xml",
            "epf-build",
            "epf-dump",
            "erf-build",
            "erf-dump",
        ):
            self.assertEqual(kinds[name], "profile-ibcmd", name)
        for name in ("db-create", "db-update", "db-load-git", "db-run"):
            self.assertEqual(kinds[name], "native-alias", name)
        self.assertFalse(imported_skills.RETIRED_METADATA_SKILLS & kinds.keys())

    def test_profile_operation_dry_run_builds_ibcmd_command_without_designer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            cf = temp / "input.cf"
            cf.write_bytes(b"cf")
            run_root = temp / "run"
            exit_code = imported_skills.run_imported_skill(
                "db-load-cf",
                [
                    "-Profile",
                    str(EXAMPLE_PROFILE),
                    "-RunRoot",
                    str(run_root),
                    "-InputFile",
                    str(cf),
                    "-Extension",
                    "Тест",
                    "-DryRun",
                ],
            )
            summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
            command = summary["execution"]["commands"][0]
            self.assertEqual(exit_code, 0)
            self.assertEqual(summary["status"], "dry-run")
            self.assertEqual(summary["capability"]["id"], "imported-db-load-cf")
            self.assertEqual(command[1:3], ["config", "load"])
            self.assertEqual(command[-2:], ["--extension=Тест", str(cf.resolve())])
            self.assertFalse(any("1cv8" in Path(part).name for part in command))

    def test_profile_operation_rejects_legacy_designer_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out = Path(temp_dir) / "out.epf"
            with patch("subprocess.Popen", side_effect=AssertionError("must not start")):
                exit_code = imported_skills.run_imported_skill(
                    "epf-build", ["-V8Path", "/opt/1cv8", "-SourceFile", "x.xml", "-OutputFile", str(out)]
                )
            self.assertEqual(exit_code, 2)

    def test_external_build_is_observed_with_expected_artifact_and_hidden_password(self) -> None:
        secret = "imported-secret-value"
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            root_xml = _write_external_source(temp)
            output = temp / "out" / "Demo.epf"
            run_root = temp / "run"
            requests: list[ObservationRequest] = []

            def fake_observed(request: ObservationRequest) -> ObservationResult:
                requests.append(request)
                sources = Path(str(request.command[-1]))
                module = sources / "Demo" / "Ext" / "ObjectModule.bsl"
                assert module.read_bytes().startswith(b"\xef\xbb\xbf")
                assert request.stdout_log is not None
                request.stdout_log.write_text(f"ibcmd {secret}", encoding="utf-8")
                output.write_bytes(b"epf")
                return ObservationResult(0, "completed", "completed", request.run_root / "observation.jsonl")

            with (
                patch.dict(os.environ, {"ONEC_IBCMD_PASSWORD": secret, "ONEC_OBSERVATION_STALL_TIMEOUT_SECONDS": "7"}),
                patch("scripts.python.cfe_runtime.run_observed", side_effect=fake_observed),
            ):
                exit_code = imported_skills.run_imported_skill(
                    "epf-build",
                    [
                        "-Profile",
                        str(EXAMPLE_PROFILE),
                        "-RunRoot",
                        str(run_root),
                        "-SourceFile",
                        str(root_xml),
                        "-OutputFile",
                        str(output),
                    ],
                )
            self.assertEqual(exit_code, 0)
            request = requests[0]
            self.assertEqual(request.capability, "imported-epf-build")
            self.assertEqual(request.expected_result, output.resolve())
            self.assertEqual(request.stall_timeout_seconds, 7.0)
            self.assertIn("config", request.command)
            self.assertIn(f"--out={output.resolve()}", request.command)
            self.assertFalse(
                (root_xml.parent / "Demo" / "Ext" / "ObjectModule.bsl").read_bytes().startswith(b"\xef\xbb\xbf")
            )
            combined = "".join((run_root / name).read_text(encoding="utf-8") for name in ("summary.json", "stdout.log"))
            self.assertNotIn(secret, combined)

    def test_external_dump_uses_ibcmd_export_of_the_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            artifact = temp / "Demo.erf"
            artifact.write_bytes(b"erf")
            run_root = temp / "run"
            exit_code = imported_skills.run_imported_skill(
                "erf-dump",
                [
                    "-Profile",
                    str(EXAMPLE_PROFILE),
                    "-RunRoot",
                    str(run_root),
                    "-InputFile",
                    str(artifact),
                    "-OutputDir",
                    str(temp / "xml"),
                    "-DryRun",
                ],
            )
            command = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))["execution"]["commands"][0]
            self.assertEqual(exit_code, 0)
            self.assertEqual(command[1:3], ["config", "export"])
            self.assertEqual(command[-2:], [f"--file={artifact.resolve()}", str((temp / "xml").resolve())])

    def test_db_run_proxies_to_run_client_and_rejects_legacy_launch(self) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            return subprocess.CompletedProcess(command, 0)

        with patch("scripts.python.imported_skills.subprocess.run", side_effect=fake_run):
            self.assertEqual(imported_skills.run_imported_skill("db-run", ["--profile", "env/local.json"]), 0)
            with self.assertRaises(CommandError):
                imported_skills.run_imported_skill("db-run", ["-InfoBasePath", "/ib", "-Password", "x"])
        self.assertEqual(len(calls), 1)
        delegate = "run-client.ps1" if os.name == "nt" else "run-client.sh"
        self.assertTrue(any(str(part).endswith(delegate) for part in calls[0]))
        self.assertEqual(calls[0][-2:], ["--profile", "env/local.json"])

    def test_native_aliases_require_ibcmd_driver(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            designer = _write_profile(temp / "designer.json", createIb={"driver": "designer"})
            ibcmd = _write_profile(temp / "ibcmd.json", createIb={"driver": "ibcmd"})
            with patch("scripts.python.imported_skills.run_process") as run_process:
                run_process.return_value = subprocess.CompletedProcess([], 0, "", "")
                with self.assertRaises(CommandError):
                    imported_skills.run_imported_skill("db-create", ["--profile", str(designer)])
                run_process.assert_not_called()
                self.assertEqual(imported_skills.run_imported_skill("db-create", ["--profile", str(ibcmd)]), 0)
            self.assertEqual(run_process.call_args.args[0][-2:], ["--profile", str(ibcmd)])

    def test_platform_skill_documents_profile_and_observation(self) -> None:
        manifest = json.loads(imported_skills.IMPORT_MANIFEST.read_text(encoding="utf-8"))
        entries = {entry["name"]: entry for entry in manifest["skills"]}
        build = _render_agents_skill(entries["epf-build"])
        reference = _render_agents_skill(entries["cf-edit"])
        self.assertIn("## Наблюдение запуска", build)
        self.assertIn("ONEC_OBSERVATION_STALL_TIMEOUT_SECONDS", build)
        self.assertIn("-Profile <json>", build)
        self.assertNotIn("## Наблюдение запуска", reference)


if __name__ == "__main__":
    unittest.main()
