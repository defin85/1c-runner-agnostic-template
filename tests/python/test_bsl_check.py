from __future__ import annotations

import contextlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts.python import bsl_check, check_cf_modules, external_bsl_check
from scripts.python.bsl_check import Backend, overall_status, select_modules, syntax_verdict
from scripts.python.check_cf_modules import (
    MANAGED_MODES,
    ORDINARY_MODES,
    blocking_diagnostics,
    default_execution_modes,
    designer_diagnostics,
    partial_load_files,
    platform_version,
    read_configuration_properties,
)
from scripts.python.runtime_errors import CommandError

ROOT = Path(__file__).resolve().parents[2]
POSIX_ONLY = unittest.skipIf(os.name == "nt", "POSIX executable fixture")

CONFIGURATION_XML = """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">
  <Configuration>
    <Properties>
      <Name>{name}</Name>
      <Version>1.0.0.1</Version>
      {extra}
      <ChildObjects/>
    </Properties>
  </Configuration>
</MetaDataObject>
"""

FAKE_ANALYZER = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_ANALYZER_ARGV"], "w", encoding="utf-8") as stream:
    json.dump(args, stream)
changed = args[args.index("--changed-files") + 1].split(",")
broken = os.environ.get("FAKE_ANALYZER_BROKEN", "")
for path in changed:
    diagnostics = []
    if broken and path.endswith(broken):
        diagnostics.append({"code": "ParseError", "severity": "error", "message": "unexpected token",
                            "start_line": 2, "start_column": 4})
    print(json.dumps({"type": "file", "path": path, "diagnostics": diagnostics}))
print(json.dumps({"type": "done", "failed_files": 0}))
"""


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def configuration(root: Path, name: str, extra: str = "") -> Path:
    return write(root / "Configuration.xml", CONFIGURATION_XML.format(name=name, extra=extra))


def make_executable(path: Path, text: str) -> Path:
    write(path, text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class FixtureRepo(unittest.TestCase):
    """A throwaway repository with a main configuration, an extension and a managed EPF export."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.repo = Path(self._temp.name).resolve()
        cf = self.repo / "src" / "cf"
        configuration(
            cf,
            "DemoConfiguration",
            "<CompatibilityMode>Version8_3_24</CompatibilityMode><DefaultRunMode>ManagedApplication</DefaultRunMode>",
        )
        write(cf / "CommonModules" / "Common.xml", "<x/>")
        self.common = write(cf / "CommonModules" / "Common" / "Ext" / "Module.bsl", "Procedure A()\nEndProcedure\n")
        write(cf / "Documents" / "Order.xml", "<x/>")
        write(cf / "Documents" / "Order" / "Forms" / "Main.xml", "<x/>")
        write(cf / "Documents" / "Order" / "Forms" / "Main" / "Ext" / "Form.xml", "<x/>")
        self.form = write(cf / "Documents" / "Order" / "Forms" / "Main" / "Ext" / "Form" / "Module.bsl", "")
        self.session = write(cf / "Ext" / "SessionModule.bsl", "")
        cfe = self.repo / "src" / "cfe" / "DemoExtension"
        configuration(
            cfe, "DemoExtension", "<ConfigurationExtensionPurpose>Customization</ConfigurationExtensionPurpose>"
        )
        self.extension_module = write(cfe / "CommonModules" / "Patch" / "Ext" / "Module.bsl", "")
        epf = self.repo / "src" / "epf" / "managed" / "Report"
        write(epf / "DemoReport.xml", "<x/>")
        self.epf_module = write(epf / "DemoReport" / "Ext" / "ObjectModule.bsl", "")
        self.env = patch.dict(os.environ, {}, clear=False)
        self.env.start()
        for name in ("BSL_ANALYZER_APP", "BSL_CONFIGURATION_ROOT"):
            os.environ.pop(name, None)

    def tearDown(self) -> None:
        self.env.stop()
        self._temp.cleanup()

    def analyzer(self, broken: str = "") -> Path:
        app = make_executable(self.repo / "tools" / "fake-analyzer", FAKE_ANALYZER)
        os.environ["BSL_ANALYZER_APP"] = str(app)
        os.environ["FAKE_ANALYZER_ARGV"] = str(self.repo / "analyzer-argv.json")
        os.environ["FAKE_ANALYZER_BROKEN"] = broken
        return app

    def analyzer_argv(self) -> list[str]:
        return json.loads((self.repo / "analyzer-argv.json").read_text(encoding="utf-8"))

    def check_bsl(self, *argv: str) -> tuple[int, str, dict[str, Any]]:
        run_root = self.repo / ".artifacts" / "check"
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch.object(bsl_check, "project_root", return_value=self.repo),
            patch.object(check_cf_modules, "project_root", return_value=self.repo),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            try:
                code = bsl_check.run_check_bsl(["--run-root", str(run_root), *argv])
            except CommandError as error:
                return error.exit_code, str(error), {}
        summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
        return code, stdout.getvalue(), summary


class SelectionTests(FixtureRepo):
    def test_configuration_extension_and_external_roots(self) -> None:
        selection = select_modules([str(self.common), str(self.form)], self.repo)
        self.assertEqual((selection.kind, selection.name), ("configuration", "DemoConfiguration"))
        self.assertEqual(selection.root, self.repo / "src" / "cf")
        self.assertEqual(len(selection.modules), 2)
        extension = select_modules([str(self.extension_module)], self.repo)
        self.assertEqual((extension.kind, extension.name), ("extension", "DemoExtension"))
        external = select_modules([str(self.epf_module)], self.repo)
        self.assertEqual((external.kind, external.name), ("external", "DemoReport"))
        self.assertEqual(external.root, self.repo / "src" / "epf" / "managed" / "Report")

    def test_mixed_roots_and_bad_paths_are_rejected_with_code_2(self) -> None:
        cases = (
            [str(self.common), str(self.extension_module)],
            [str(self.repo / "missing.bsl")],
            [str(write(self.repo / "loose" / "Module.bsl", ""))],
            [],
        )
        for values in cases:
            with self.subTest(values=values), self.assertRaises(CommandError) as raised:
                select_modules(values, self.repo)
            self.assertEqual(raised.exception.exit_code, 2)


class VerdictTests(unittest.TestCase):
    def test_overall_and_syntax_matrix(self) -> None:
        passed, failed, skipped = Backend("passed", ""), Backend("failed", ""), Backend("not-run", "")
        blocked = Backend("blocked", "")
        cases = (
            ("full", "configuration", passed, passed, "passed", "проверен"),
            ("full", "configuration", passed, skipped, "blocked", "проверен"),
            ("full", "configuration", skipped, blocked, "blocked", "не проверен"),
            ("full", "configuration", passed, failed, "failed", "ошибки"),
            ("fast", "configuration", passed, skipped, "static-only", "проверен"),
            ("fast", "extension", skipped, skipped, "blocked", "не проверен"),
            ("full", "external", passed, skipped, "passed", "проверен"),
            ("fast", "external", passed, skipped, "static-only", "проверен"),
            ("platform", "configuration", skipped, passed, "passed", "проверен"),
        )
        for mode, kind, static, platform, overall, syntax in cases:
            with self.subTest(mode=mode, kind=kind, static=static.status, platform=platform.status):
                self.assertEqual(overall_status(mode, kind, static, platform), overall)
                self.assertEqual(syntax_verdict(static, platform), syntax)


class RoutingTests(FixtureRepo):
    def test_without_analyzer_and_profile_syntax_is_not_checked(self) -> None:
        os.environ["BSL_ANALYZER_APP"] = str(self.repo / "missing-analyzer")
        code, output, summary = self.check_bsl(str(self.common))
        self.assertEqual(code, 3)
        self.assertIn("синтаксис: не проверен", output)
        self.assertEqual(summary["static"]["status"], "not-run")
        self.assertEqual(summary["platform"]["status"], "not-run")

    @POSIX_ONLY
    def test_configuration_static_pass_checks_exactly_selected_modules(self) -> None:
        self.analyzer()
        code, output, summary = self.check_bsl("--mode", "fast", str(self.common), str(self.form))
        self.assertEqual(code, 0, output)
        argv = self.analyzer_argv()
        self.assertEqual(argv[argv.index("--configuration-root") + 1], "src/cf")
        self.assertEqual(
            argv[argv.index("--changed-files") + 1].split(","),
            [
                "src/cf/CommonModules/Common/Ext/Module.bsl",
                "src/cf/Documents/Order/Forms/Main/Ext/Form/Module.bsl",
            ],
        )
        self.assertNotIn("--extension", argv)
        self.assertNotIn("--external", argv)
        self.assertEqual(summary["overall"], "static-only")
        self.assertIn("синтаксис: проверен", output)

    @POSIX_ONLY
    def test_extension_is_declared_over_main_configuration(self) -> None:
        self.analyzer()
        code, _output, _summary = self.check_bsl("--mode", "fast", str(self.extension_module))
        self.assertEqual(code, 0)
        argv = self.analyzer_argv()
        self.assertEqual(argv[argv.index("--configuration-root") + 1], "src/cf")
        self.assertEqual(argv[argv.index("--extension") + 1], "DemoExtension=src/cfe/DemoExtension")

    @POSIX_ONLY
    def test_external_artifact_without_platform_check(self) -> None:
        self.analyzer()
        code, output, summary = self.check_bsl(str(self.epf_module))
        self.assertEqual(code, 0, output)
        argv = self.analyzer_argv()
        self.assertEqual(
            argv[argv.index("--external") + 1], f"DemoReport={self.repo / 'src' / 'epf' / 'managed' / 'Report'}"
        )
        self.assertEqual(summary["platform"]["status"], "not-run")
        self.assertEqual(summary["overall"], "passed")

    @POSIX_ONLY
    def test_parse_error_fails_the_check(self) -> None:
        self.analyzer(broken="Common/Ext/Module.bsl")
        code, output, summary = self.check_bsl("--mode", "fast", str(self.common))
        self.assertEqual(code, 1)
        self.assertIn("синтаксис: ошибки", output)
        self.assertEqual(len(summary["static"]["parse_errors"]), 1)

    def test_extension_without_main_configuration_is_not_checked(self) -> None:
        (self.repo / "src" / "cf" / "Configuration.xml").unlink()
        self.analyzer()
        code, output, summary = self.check_bsl("--mode", "fast", str(self.extension_module))
        self.assertEqual(code, 3)
        self.assertIn("--configuration-root", summary["static"]["reason"])
        self.assertIn("синтаксис: не проверен", output)

    def test_platform_dry_run_reports_versions_and_partial_load(self) -> None:
        os.environ["BSL_ANALYZER_APP"] = str(self.repo / "missing-analyzer")
        profile = ROOT / "env" / "local.example.json"
        code, output, summary = self.check_bsl("--profile", str(profile), "--dry-run", str(self.common))
        self.assertEqual(code, 3)
        platform = summary["platform"]
        self.assertEqual(platform["status"], "not-run")
        self.assertRegex(platform["platform"]["version"], r"^\d+\.\d+\.\d+\.\d+$")
        self.assertEqual(platform["configuration"]["compatibility_mode"], "Version8_3_24")
        self.assertEqual(platform["configuration"]["execution_modes"], list(MANAGED_MODES))
        self.assertEqual(platform["source_identity"]["loaded_match"], "not-verified")
        self.assertIn("compatibility Version8_3_24", output)
        details = json.loads(Path(platform["summary_json"]).read_text(encoding="utf-8"))
        load, check = details["execution"]["commands"]["load"], details["execution"]["commands"]["check"]
        self.assertIn("/LoadConfigFromFiles", load)
        self.assertIn("-partial", load)
        self.assertIn("/CheckModules", check)
        self.assertEqual(
            details["load"]["files"],
            ["CommonModules/Common.xml", "CommonModules/Common/Ext/Module.bsl"],
        )

    def test_extension_platform_check_routes_to_check_cfe_config(self) -> None:
        os.environ["BSL_ANALYZER_APP"] = str(self.repo / "missing-analyzer")
        profile = ROOT / "env" / "local.example.json"
        with patch("scripts.python.cfe_runtime.run_cfe_command", return_value=0) as cfe:
            code, _output, summary = self.check_bsl("--profile", str(profile), str(self.extension_module))
        self.assertEqual(cfe.call_args.args[0], "check-cfe-config")
        self.assertIn("DemoExtension", cfe.call_args.args[1])
        self.assertEqual(summary["platform"]["status"], "passed")
        self.assertEqual(code, 0)


class CheckCfModulesTests(FixtureRepo):
    def test_configuration_properties_and_modes(self) -> None:
        properties = read_configuration_properties(self.repo / "src" / "cf")
        self.assertEqual(properties["CompatibilityMode"], "Version8_3_24")
        self.assertEqual(default_execution_modes(properties), list(MANAGED_MODES))
        self.assertEqual(default_execution_modes({"DefaultRunMode": "OrdinaryApplication"}), list(ORDINARY_MODES))
        self.assertEqual(platform_version("/opt/x/8.3.27.1859/1cv8"), "8.3.27.1859")
        self.assertEqual(platform_version("1cv8"), "unknown")

    def test_partial_load_files_cover_owner_descriptions(self) -> None:
        source = self.repo / "src" / "cf"
        files = partial_load_files(
            source,
            [
                self.form.relative_to(source),
                self.session.relative_to(source),
                self.common.relative_to(source),
            ],
        )
        self.assertEqual(
            files,
            [
                "Documents/Order.xml",
                "Documents/Order/Forms/Main.xml",
                "Documents/Order/Forms/Main/Ext/Form.xml",
                "Documents/Order/Forms/Main/Ext/Form/Module.bsl",
                "Configuration.xml",
                "Ext/SessionModule.bsl",
                "CommonModules/Common.xml",
                "CommonModules/Common/Ext/Module.bsl",
            ],
        )

    def test_designer_diagnostics_and_baseline(self) -> None:
        log = write(
            self.repo / "out.log",
            "Ошибок не обнаружено\n{CommonModule.Common.Module(3,5)}: Syntax error\nHandler missing: OnOpen\n",
        )
        diagnostics = designer_diagnostics(log, 101)
        self.assertEqual([item["severity"] for item in diagnostics], ["error", "warning"])
        self.assertEqual(diagnostics[0]["module"], "CommonModule.Common.Module")
        self.assertEqual(blocking_diagnostics(diagnostics, None), diagnostics)
        self.assertEqual(blocking_diagnostics(diagnostics, [diagnostics[0]]), [diagnostics[1]])
        self.assertEqual(designer_diagnostics(self.repo / "absent.log", 0), [])

    def test_extension_root_is_rejected(self) -> None:
        profile = ROOT / "env" / "local.example.json"
        with (
            patch.object(check_cf_modules, "project_root", return_value=self.repo),
            self.assertRaisesRegex(CommandError, "check-cfe-config") as raised,
        ):
            check_cf_modules.run_check_cf_modules(
                ["--profile", str(profile), "--source-root", "src/cfe/DemoExtension", "--dry-run"]
            )
        self.assertEqual(raised.exception.exit_code, 2)

    @POSIX_ONLY
    def test_fake_designer_run_loads_selected_modules_then_checks(self) -> None:
        script = (
            'out=""; prev=""\n'
            'for arg in "$@"; do [ "$prev" = "/Out" ] && out="$arg"; prev="$arg"; done\n'
            'echo "$*" >> "$FAKE_DESIGNER_CALLS"\n'
            'case "$*" in *CheckModules*) printf "%s\\n" "$FAKE_DESIGNER_OUTPUT" > "$out"; exit "$FAKE_DESIGNER_EXIT";; esac\n'
            "exit 0\n"
        )
        binary = make_executable(self.repo / "platform" / "8.3.27.1859" / "1cv8", "#!/bin/sh\n" + script)
        payload = json.loads((ROOT / "env" / "local.example.json").read_text(encoding="utf-8"))
        payload["platform"]["binaryPath"] = str(binary)
        profile = write(self.repo / "profile.json", json.dumps(payload))
        calls = self.repo / "designer-calls.log"
        cases = (
            ("Ошибок не обнаружено", "0", 0, "success"),
            ("{CommonModule.Common.Module(1,1)}: Error", "101", 101, "failed"),
        )
        for output, designer_exit, expected_exit, expected_status in cases:
            with self.subTest(designer_exit=designer_exit):
                calls.unlink(missing_ok=True)
                run_root = self.repo / ".artifacts" / f"designer-{designer_exit}"
                env = {
                    "FAKE_DESIGNER_CALLS": str(calls),
                    "FAKE_DESIGNER_OUTPUT": output,
                    "FAKE_DESIGNER_EXIT": designer_exit,
                    "ONEC_OBSERVATION_INTERVAL_SECONDS": "1",
                }
                with (
                    patch.dict(os.environ, env),
                    patch.object(check_cf_modules, "project_root", return_value=self.repo),
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    code = check_cf_modules.run_check_cf_modules(
                        ["--profile", str(profile), "--run-root", str(run_root), str(self.common)]
                    )
                summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
                lines = calls.read_text(encoding="utf-8").splitlines()
                self.assertEqual(code, expected_exit)
                self.assertEqual(summary["status"], expected_status)
                self.assertEqual(len(lines), 2)
                self.assertIn("/LoadConfigFromFiles", lines[0])
                self.assertIn("/CheckModules", lines[1])
                self.assertEqual(summary["platform"]["version"], "8.3.27.1859")
                expected_match = "selected-modules-loaded" if expected_status == "success" else "not-verified"
                self.assertEqual(summary["source_identity"]["loaded_match"], expected_match)


class ExternalCheckTests(FixtureRepo):
    def run_external(self, *args: str) -> int:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                return external_bsl_check.run_external_check(list(args), root=self.repo)
            except CommandError as error:
                return error.exit_code

    def test_unavailable_analyzer_returns_not_checked(self) -> None:
        os.environ["BSL_ANALYZER_APP"] = str(self.repo / "missing-analyzer")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = external_bsl_check.run_external_check(["--all-managed"], root=self.repo)
        self.assertEqual(code, 3)
        self.assertIn("синтаксис: не проверен", stderr.getvalue())

    @POSIX_ONLY
    def test_declared_extension_and_explicit_configuration_root(self) -> None:
        self.analyzer()
        code = self.run_external(
            "--configuration-root",
            str(self.repo / "src" / "cf"),
            "--declare-extension",
            str(self.repo / "src" / "cfe" / "DemoExtension"),
            "--run-root",
            str(self.repo / ".artifacts" / "external"),
            "DemoReport",
        )
        self.assertEqual(code, 0)
        argv = self.analyzer_argv()
        self.assertIn("DemoExtension=src/cfe/DemoExtension", argv)
        self.assertEqual(
            argv[argv.index("--changed-files") + 1], "src/epf/managed/Report/DemoReport/Ext/ObjectModule.bsl"
        )

    def test_ordinary_exports_and_missing_configuration_are_rejected(self) -> None:
        ordinary = self.repo / "src" / "epf" / "ordinary" / "Old"
        write(ordinary / "Old.xml", "<x/>")
        write(ordinary / "Old" / "Ext" / "ObjectModule.bsl", "")
        self.assertEqual(self.run_external(str(ordinary)), 2)
        (self.repo / "src" / "cf" / "Configuration.xml").unlink()
        self.assertEqual(self.run_external("DemoReport"), 2)

    def test_plan_passes_splits_duplicate_names(self) -> None:
        first = external_bsl_check.Artifact("Same", self.repo / "a", (self.repo / "a" / "m.bsl",))
        second = external_bsl_check.Artifact("Same", self.repo / "b", (self.repo / "b" / "m.bsl",))
        other = external_bsl_check.Artifact("Other", self.repo / "c", (self.repo / "c" / "m.bsl",))
        passes = external_bsl_check.plan_passes(self.repo, [first, second, other])
        self.assertEqual([[item.name for item in batch] for batch in passes], [["Same", "Other"], ["Same"]])


class WrapperTests(unittest.TestCase):
    def test_wrappers_are_thin_and_paired(self) -> None:
        for directory, command in (
            ("qa", "check-bsl"),
            ("qa", "analyze-bsl-external"),
            ("platform", "check-cf-modules"),
        ):
            with self.subTest(command=command):
                shell = ROOT / "scripts" / directory / f"{command}.sh"
                powershell = ROOT / "scripts" / directory / f"{command}.ps1"
                self.assertIn(f'run-python.sh" "{command}" "$@"', shell.read_text(encoding="utf-8"))
                self.assertIn(f'run-python.ps1") "{command}" @args', powershell.read_text(encoding="utf-8"))
                if sys.platform != "win32":
                    self.assertTrue(os.access(shell, os.X_OK))


if __name__ == "__main__":
    unittest.main()
