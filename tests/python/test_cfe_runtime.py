from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.python.cfe_runtime import (
    CfeOptions,
    build_cfe_commands,
    classify_config_diagnostics,
    designer_out_diagnostics,
    read_list_file,
    run_cfe_command,
    validate_extension_name,
    validate_manage_cfe,
)
from scripts.python.runtime_errors import CommandError
from scripts.python.runtime_observation import ObservationRequest, ObservationResult
from scripts.python.runtime_profiles import load_runtime_profile, resolve_target_extensions

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

    def _load_cfe(self, project: Path, run_root: Path, *extensions: str) -> int:
        args = ["--profile", str(ROOT / "env" / "local.example.json"), "--run-root", str(run_root)]
        for name in extensions:
            args += ["--extension", name]
        with patch("scripts.python.cfe_runtime.project_root", return_value=project):
            return run_cfe_command("load-cfe", args)

    @staticmethod
    def _project_with_extensions(temp: Path, *names: str) -> Path:
        project = temp / "project"
        for name in names:
            (project / "src" / "cfe" / name).mkdir(parents=True)
        return project

    def test_summary_and_logs_redact_resolved_secrets(self) -> None:
        secret = "cfe-secret-value"
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"ONEC_IBCMD_PASSWORD": secret}):
            project = self._project_with_extensions(Path(temp_dir), "Тест")
            run_root = Path(temp_dir) / "run"

            def fake_run(request: ObservationRequest) -> ObservationResult:
                assert request.stdout_log is not None and request.stderr_log is not None
                request.stdout_log.write_text(secret, encoding="utf-8")
                request.stderr_log.write_text(secret, encoding="utf-8")
                return ObservationResult(0, "completed", "completed", request.run_root / "observation.jsonl")

            with patch("scripts.python.cfe_runtime.run_observed", side_effect=fake_run):
                exit_code = self._load_cfe(project, run_root, "Тест")
            combined = "".join(
                path.read_text(encoding="utf-8") for path in sorted(run_root.rglob("*")) if path.is_file()
            )
            self.assertEqual(exit_code, 0)
            self.assertNotIn(secret, combined)
            self.assertIn("__REDACTED_SECRET__", combined)

    def test_interruption_publishes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = self._project_with_extensions(Path(temp_dir), "Тест")
            run_root = Path(temp_dir) / "run"
            with (
                patch.dict(os.environ, {"ONEC_IBCMD_PASSWORD": "secret"}),
                patch("scripts.python.cfe_runtime.run_observed", side_effect=KeyboardInterrupt),
            ):
                exit_code = self._load_cfe(project, run_root, "Тест")
            summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 130)
            self.assertEqual(summary["status"], "interrupted")

    def test_load_cfe_discovers_extensions_and_stops_at_first_failed_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = self._project_with_extensions(Path(temp_dir), "Второе", "Первое")
            run_root = Path(temp_dir) / "run"
            calls: list[tuple[str, str]] = []

            def fake_run(request: ObservationRequest) -> ObservationResult:
                step = request.run_root.name
                extension = request.run_root.parent.parent.name
                calls.append((extension, step))
                code = 9 if (extension, step) == ("Второе", "check") else 0
                return ObservationResult(code, "completed", "completed", request.run_root / "observation.jsonl")

            with (
                patch.dict(os.environ, {"ONEC_IBCMD_PASSWORD": "secret"}),
                patch("scripts.python.cfe_runtime.run_observed", side_effect=fake_run),
            ):
                exit_code = self._load_cfe(project, run_root)
            summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
            failed = json.loads((run_root / "extensions" / "Второе" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 9)
            self.assertEqual(calls, [("Второе", "import"), ("Второе", "check")])
            self.assertEqual(summary["extension_source"]["selected_names"], ["Второе", "Первое"])
            self.assertEqual(summary["failed_extension"], "Второе")
            self.assertEqual(summary["failed_step"], "check")
            self.assertEqual([item["status"] for item in summary["results"]], ["failed", None])
            self.assertEqual(failed["failure"]["classification"], "extension-sync failed")
            self.assertFalse((run_root / "extensions" / "Первое").exists())

    def test_load_cfe_rejects_missing_or_absent_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            empty = self._project_with_extensions(Path(temp_dir))
            with self.assertRaisesRegex(CommandError, "no extensions found under"):
                self._load_cfe(empty, Path(temp_dir) / "run-empty")
            with self.assertRaisesRegex(CommandError, "extension source not found under"):
                self._load_cfe(empty, Path(temp_dir) / "run-missing", "Нет")

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
            project = self._project_with_extensions(temp, "Тест")
            run_root = temp / "run"
            with (
                patch.dict(os.environ, {"ONEC_OBSERVATION_INTERVAL_SECONDS": "1"}),
                patch("scripts.python.cfe_runtime.project_root", return_value=project),
            ):
                exit_code = run_cfe_command(
                    "check-cfe-config", ["--profile", str(profile), "--extension", "Тест", "--run-root", str(run_root)]
                )
            extension_root = run_root / "extensions" / "Тест"
            events = [
                json.loads(line)
                for line in (extension_root / "observation.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            summary = json.loads((extension_root / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual([events[0]["event"], events[-1]["event"]], ["started", "completed"])
            self.assertEqual(events[0]["capability"], "check-cfe-config")
            self.assertEqual(summary["observation"]["terminalEvent"], "completed")
            self.assertIn("designer-ran", (extension_root / "stdout.log").read_text(encoding="utf-8"))
            self.assertTrue((extension_root / "process.pid").is_file())

    @unittest.skipIf(os.name == "nt", "POSIX shell fixture")
    def test_designer_stall_stops_only_with_wrapper_threshold(self) -> None:
        script = 'printf stage-1 > "$ONEC_OBSERVATION_PROGRESS_FILE"\nsleep 4\nexit 0\n'
        for threshold, expected in (("1", 125), ("", 0)):
            with self.subTest(threshold=threshold), tempfile.TemporaryDirectory() as temp_dir:
                temp = Path(temp_dir)
                profile = self._fake_platform_profile(temp, script)
                project = self._project_with_extensions(temp, "Тест")
                run_root = temp / "run"
                env = {"ONEC_OBSERVATION_INTERVAL_SECONDS": "1", "ONEC_OBSERVATION_STALL_TIMEOUT_SECONDS": threshold}
                with (
                    patch.dict(os.environ, env),
                    patch("scripts.python.cfe_runtime.project_root", return_value=project),
                ):
                    exit_code = run_cfe_command(
                        "check-cfe-applicability",
                        ["--profile", str(profile), "--extension", "Тест", "--run-root", str(run_root)],
                    )
                summary = json.loads((run_root / "extensions" / "Тест" / "summary.json").read_text(encoding="utf-8"))
                self.assertEqual(exit_code, expected)
                self.assertEqual(summary["observation"]["terminalReason"], "stalled" if expected else "completed")

    def test_multi_step_operation_keeps_one_observation_per_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = self._project_with_extensions(Path(temp_dir), "Тест")
            run_root = Path(temp_dir) / "run"
            roots: list[Path] = []

            def fake_run(request: ObservationRequest) -> ObservationResult:
                roots.append(request.run_root)
                return ObservationResult(0, "completed", "completed", request.run_root / "observation.jsonl")

            with (
                patch.dict(os.environ, {"ONEC_IBCMD_PASSWORD": "secret"}),
                patch("scripts.python.cfe_runtime.run_observed", side_effect=fake_run),
            ):
                exit_code = self._load_cfe(project, run_root, "Тест")
            self.assertEqual(exit_code, 0)
            step_root = run_root.resolve() / "extensions" / "Тест" / "steps"
            self.assertEqual(roots, [step_root / name for name in ("import", "check", "apply")])

    def test_check_collects_every_failed_extension_with_designer_out(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = self._project_with_extensions(Path(temp_dir), "Первое", "Второе")
            run_root = Path(temp_dir) / "run"
            commands: list[list[str]] = []

            def fake_run(request: ObservationRequest) -> ObservationResult:
                commands.append(list(request.command))
                out_log = Path(request.command[request.command.index("/Out") + 1])
                failing = request.command[-1] == "Второе"
                out_log.write_text("Cannot find method X\n" if failing else "No errors found\n", encoding="utf-8")
                return ObservationResult(0, "completed", "completed", request.run_root / "observation.jsonl")

            with (
                patch("scripts.python.cfe_runtime.run_observed", side_effect=fake_run),
                patch("scripts.python.cfe_runtime.project_root", return_value=project),
            ):
                exit_code = run_cfe_command(
                    "check-cfe-applicability",
                    ["--profile", str(ROOT / "env" / "local.example.json"), "--run-root", str(run_root)],
                )
            summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
            failed = json.loads((run_root / "extensions" / "Второе" / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 1)
        self.assertEqual([command[-1] for command in commands], ["Второе", "Первое"])
        self.assertEqual(summary["failure"]["extensions"], ["Второе"])
        self.assertEqual([item["status"] for item in summary["results"]], ["failed", "success"])
        self.assertEqual(failed["diagnostics"][0]["severity"], "warning")
        self.assertEqual(failed["blocking_diagnostics_count"], 1)

    def test_config_diagnostics_separate_inherited_handlers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            module = root / "src" / "cf" / "Documents" / "Заказ" / "Forms" / "Форма" / "Ext" / "Form" / "Module.bsl"
            module.parent.mkdir(parents=True)
            module.write_text("Процедура Обновить(Команда)\nКонецПроцедуры\n", encoding="utf-8")
            out_log = root / "out.log"
            out_log.write_text(
                'Расш Документ.Заказ.Форма.Форма.Форма Handler missing:  Обновить "Обновить"\n'
                'Расш Документ.Заказ.Форма.Форма.Форма Handler missing:  Нет "Нет"\n'
                "{Расш Документ.Заказ.МодульОбъекта(1,1)}: Variable is not defined (Икс)\n",
                encoding="utf-8",
            )
            diagnostics = classify_config_diagnostics(root, designer_out_diagnostics(out_log, 0))
        self.assertEqual(
            [item["classification"] for item in diagnostics], ["inherited_handler", "blocking", "blocking"]
        )
        self.assertEqual(
            diagnostics[0]["resolution"]["base_form_module"],
            "src/cf/Documents/Заказ/Forms/Форма/Ext/Form/Module.bsl",
        )
        self.assertEqual(diagnostics[1]["resolution"]["kind"], "unresolved_handler")
        self.assertEqual(diagnostics[2]["severity"], "error")

    def test_target_matrix_selects_extensions_and_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._project_with_extensions(Path(temp_dir), "Общее", "Первое", "Второе")
            matrix = root / "automation" / "context" / "target-matrix.json"
            matrix.parent.mkdir(parents=True)
            matrix.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "targets": [{"id": "one"}, {"id": "two"}],
                        "extensionMatrix": {"one": ["Общее", "Первое"], "two": ["Общее", "Второе"]},
                    }
                ),
                encoding="utf-8",
            )
            available = ["Второе", "Общее", "Первое"]
            source = root / "src" / "cfe"
            selected = resolve_target_extensions(root, "one", "one", [], available, source)
            explicit = resolve_target_extensions(root, "one", "one", ["Общее"], available, source)
            errors = {
                "multi-target workspace requires --target": ("", "one", []),
                "runtime profile target.id is required": ("one", "", []),
                "does not match requested target": ("one", "two", []),
                "not present in target matrix for target=one: Второе": ("one", "one", ["Второе"]),
            }
            for message, (target, profile_target, names) in errors.items():
                with self.subTest(message=message), self.assertRaisesRegex(CommandError, message):
                    resolve_target_extensions(root, target, profile_target, names, available, source)
        self.assertEqual(selected, (["Общее", "Первое"], "one"))
        self.assertEqual(explicit, (["Общее"], "one"))


class CfeOptionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = load_runtime_profile(ROOT / "env" / "windows-local.example.json")

    def test_runtime_flags_accept_security_profile_and_active(self) -> None:
        options = CfeOptions(safe_mode="yes", active="no", security_profile_name="Профиль")
        command = build_cfe_commands(
            "configure-cfe-runtime-flags", self.profile, "Тест", dry_run=True, options=options
        )[0]
        tail = command[command.index("--name=Тест") :]
        self.assertEqual(
            tail,
            [
                "--name=Тест",
                "--security-profile-name=Профиль",
                "--safe-mode=yes",
                "--unsafe-action-protection=no",
                "--active=no",
            ],
        )

    def test_runtime_flags_clear_security_profile(self) -> None:
        options = CfeOptions(clear_security_profile=True)
        command = build_cfe_commands(
            "configure-cfe-runtime-flags", self.profile, "Тест", dry_run=True, options=options
        )[0]
        self.assertIn("--security-profile-name=", command)

    def test_runtime_flags_reject_conflicting_security_profile_options(self) -> None:
        argv = ["--extension", "Тест", "--clear-security-profile", "--security-profile-name", "Профиль"]
        with self.assertRaises(CommandError):
            run_cfe_command("configure-cfe-runtime-flags", argv)
        with self.assertRaises(CommandError):
            run_cfe_command("configure-cfe-runtime-flags", ["--extension", "Тест", "--safe-mode", "maybe"])

    def test_manage_cfe_ibcmd_actions(self) -> None:
        def build(action: str, options: CfeOptions | None = None) -> list[str]:
            return build_cfe_commands("manage-cfe", self.profile, "Тест", action=action, dry_run=True, options=options)[
                0
            ]

        self.assertIn("list", build("list"))
        self.assertEqual(build("activate")[-2:], ["--name=Тест", "--active=yes"])
        self.assertEqual(build("deactivate")[-1], "--active=no")
        self.assertEqual(build("apply")[-2:], ["--extension=Тест", "--force"])
        self.assertEqual(build("delete")[-1], "--name=Тест")
        dump = build("dump", CfeOptions(output="out-dir"))
        self.assertIn("export", dump)
        self.assertTrue(dump[-1].endswith("out-dir"))
        save = build("save", CfeOptions(file="ext.cfe"))
        self.assertIn("save", save)
        self.assertTrue(save[-1].endswith("ext.cfe"))

    def test_manage_cfe_designer_import_uses_partial_list(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            run_root = Path(raw) / "run"
            options = CfeOptions(driver="designer", source=raw, list_file="selected.txt")
            command = build_cfe_commands(
                "manage-cfe", self.profile, "Тест", action="import", dry_run=True, options=options, run_root=run_root
            )[0]
        start = command.index("/LoadConfigFromFiles")
        self.assertEqual(command[start + 2], "-listFile")
        self.assertTrue(command[start + 3].endswith("import-files.txt"))
        self.assertEqual(command[start + 4 : start + 6], ["-partial", "-Extension"])
        self.assertTrue(command[-1].endswith("designer.out.log"))

    def test_manage_cfe_designer_apply_updates_db(self) -> None:
        options = CfeOptions(driver="designer")
        command = build_cfe_commands("manage-cfe", self.profile, "Тест", action="apply", dry_run=True, options=options)[
            0
        ]
        self.assertIn("/UpdateDBCfg", command)
        self.assertEqual(command[command.index("-Extension") + 1], "Тест")

    def test_manage_cfe_validation(self) -> None:
        cases = [
            ("unknown", "Тест", CfeOptions()),
            ("apply", "", CfeOptions()),
            ("list", "Тест", CfeOptions(driver="designer")),
            ("dump", "", CfeOptions()),
            ("list", "", CfeOptions(output="out")),
            ("save", "", CfeOptions()),
            ("import", "Тест", CfeOptions(source="missing-source-dir")),
            ("import", "Тест", CfeOptions(source=".", list_file="files.txt")),
        ]
        for action, extension, options in cases:
            with self.subTest(action=action, options=options), self.assertRaises(CommandError):
                validate_manage_cfe(action, extension, options)

    def test_list_file_entries_stay_inside_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            source = Path(raw) / "src"
            (source / "CommonModules").mkdir(parents=True)
            (source / "Configuration.xml").write_text("<x/>", encoding="utf-8")
            (source / "CommonModules" / "Module.xml").write_text("<x/>", encoding="utf-8")
            list_file = Path(raw) / "files.txt"
            list_file.write_text("Configuration.xml\nCommonModules\\Module.xml\n", encoding="utf-8")
            self.assertEqual(
                read_list_file(str(list_file), str(source)), ["Configuration.xml", "CommonModules/Module.xml"]
            )
            for bad in ("../outside.xml", "/abs/path.xml", "Missing.xml"):
                list_file.write_text(bad + "\n", encoding="utf-8")
                with self.subTest(entry=bad), self.assertRaises(CommandError):
                    read_list_file(str(list_file), str(source))


if __name__ == "__main__":
    unittest.main()
