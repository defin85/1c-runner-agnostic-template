from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.python.runtime_errors import CommandError
from scripts.python.runtime_process import resolve_executable, run_process


class RuntimeProcessTests(unittest.TestCase):
    def test_argv_preserves_spaces_and_cyrillic(self) -> None:
        value = "C:\\Каталог с пробелом\\файл.xml"
        result = run_process(
            [sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.argv[1].encode('utf-8'))", value],
            check=True,
        )
        self.assertEqual(result.stdout.strip(), value)

    def test_exit_code_is_preserved(self) -> None:
        result = run_process([sys.executable, "-c", "raise SystemExit(17)"])
        self.assertEqual(result.returncode, 17)
        self.assertFalse(result.timed_out)

    def test_timeout_returns_stable_exit_code(self) -> None:
        result = run_process([sys.executable, "-c", "import time; time.sleep(2)"], timeout=0.05)
        self.assertEqual(result.returncode, 124)
        self.assertTrue(result.timed_out)

    def test_windows_resolver_selects_cmd_and_ignores_ps1(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "npm.ps1").write_text("blocked", encoding="utf-8")
            (root / "npm.cmd").write_text("@echo off", encoding="utf-8")
            resolved = resolve_executable(
                "npm",
                windows=True,
                search_path=str(root),
                pathext=".PS1;.CMD;.EXE",
            )
            self.assertEqual(Path(resolved).name.lower(), "npm.cmd")

    def test_windows_resolver_rejects_explicit_ps1(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            shim = Path(temp_dir) / "npm.ps1"
            shim.write_text("blocked", encoding="utf-8")
            with self.assertRaisesRegex(CommandError, "PowerShell shim"):
                resolve_executable(str(shim), windows=True)


if __name__ == "__main__":
    unittest.main()
