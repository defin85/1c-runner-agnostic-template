from __future__ import annotations

import os
import stat
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORE_COMMANDS = ("create-ib", "dump-src", "load-src", "update-db", "diff-src", "load-diff-src", "load-task-src")
CFE_COMMANDS = ("load-cfe", "configure-cfe-runtime-flags", "check-cfe-applicability", "check-cfe-config", "manage-cfe")


class ThinLauncherTests(unittest.TestCase):
    def test_posix_entrypoints_are_executable_in_git(self) -> None:
        paths = (
            "scripts/python/run-python.sh",
            "scripts/platform/bsl-analyzer-mcp.sh",
            "scripts/template/migrate-runtime-profile-v3.sh",
        )
        if os.name != "nt":
            for path in paths:
                self.assertTrue((ROOT / path).stat().st_mode & stat.S_IXUSR, path)
            return
        modes = subprocess.run(
            ["git", "ls-files", "--stage", "--", *paths],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.splitlines()
        self.assertEqual([line.split()[0] for line in modes], ["100755"] * len(paths))

    def test_make_frontends_share_native_runtime_targets(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        powershell = (ROOT / "make.ps1").read_text(encoding="utf-8")
        for target in (
            "create-ib", "dump-src", "load-src", "load-cfe", "manage-cfe",
            "configure-cfe-runtime-flags", "check-cfe-applicability", "check-cfe-config",
            "load-diff-src", "load-task-src", "update-db", "diff-src", "doctor",
            "publish-http", "bsl-analyzer-mcp", "test-bdd", "smoke",
        ):
            self.assertIn(f"{target}:", makefile)
            self.assertIn(f'"{target}" =', powershell)

    def assert_thin_pair(self, command: str, directory: str = "platform") -> None:
        shell = (ROOT / "scripts" / directory / f"{command}.sh").read_text(encoding="utf-8")
        powershell = (ROOT / "scripts" / directory / f"{command}.ps1").read_text(encoding="utf-8")
        self.assertIn("../python/run-python.sh", shell)
        self.assertIn(f'"{command}" "$@"', shell)
        self.assertIn("..\\python\\run-python.ps1", powershell)
        self.assertIn(f'") "{command}" @args', powershell)
        forbidden = ("jq ", "runnerAdapter", "ibcmd", "1cv8", "prepare_", "source ../lib")
        for token in forbidden:
            self.assertNotIn(token, shell)
            self.assertNotIn(token, powershell)

    def test_core_platform_launchers_are_thin_and_paired(self) -> None:
        for command in CORE_COMMANDS:
            with self.subTest(command=command):
                self.assert_thin_pair(command)

    def test_doctor_launchers_are_thin_and_paired(self) -> None:
        self.assert_thin_pair("doctor", "diag")

    def test_cfe_launchers_are_thin_and_paired(self) -> None:
        for command in CFE_COMMANDS:
            with self.subTest(command=command):
                self.assert_thin_pair(command)

    def test_bsl_mcp_launcher_is_thin_and_paired(self) -> None:
        self.assert_thin_pair("bsl-analyzer-mcp")

    def test_http_launcher_is_thin_and_paired(self) -> None:
        self.assert_thin_pair("publish-http")

    def test_test_launchers_are_thin_and_paired(self) -> None:
        for command in ("run-bdd", "run-smoke"):
            with self.subTest(command=command):
                self.assert_thin_pair(command, "test")


if __name__ == "__main__":
    unittest.main()
