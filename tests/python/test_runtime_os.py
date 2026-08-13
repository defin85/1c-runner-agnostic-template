from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.python.runtime_errors import CommandError
from scripts.python.runtime_lock import ResourceLock
from scripts.python.runtime_os import ProcessIdentity, identity_matches, manage_service, process_is_alive, service_command
from scripts.python.runtime_process import ProcessResult


class RuntimeOsTests(unittest.TestCase):
    def test_windows_restart_is_stop_then_start(self) -> None:
        calls = []
        with patch("scripts.python.runtime_os.run_process", side_effect=lambda command, **_kwargs: calls.append(command) or ProcessResult(command, 0, "", "")):
            result = manage_service("Apache2.4", "restart", windows=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(calls, [["sc.exe", "stop", "Apache2.4"], ["sc.exe", "start", "Apache2.4"]])

    def test_current_process_is_alive(self) -> None:
        self.assertTrue(process_is_alive(os.getpid()))

    def test_identity_requires_all_fields(self) -> None:
        actual = ProcessIdentity(10, "C:/Program Files/tool.exe", "100")
        self.assertTrue(identity_matches(actual, actual))
        self.assertFalse(identity_matches(actual, ProcessIdentity(10, actual.executable, "101")))

    def test_service_commands_are_platform_specific_argv(self) -> None:
        self.assertEqual(service_command("Apache2.4", "status", windows=True), ["sc.exe", "query", "Apache2.4"])
        self.assertEqual(service_command("apache2", "restart", windows=False), ["systemctl", "restart", "apache2"])

    def test_resource_lock_times_out_and_preserves_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "resource.lock"
            first = ResourceLock(path, {"pid": 1, "operation": "first"}, timeout=0.1)
            second = ResourceLock(path, {"pid": 2, "operation": "second"}, timeout=0.05, poll_interval=0.01)
            with first:
                with self.assertRaisesRegex(CommandError, "timeout"):
                    second.acquire()
                self.assertIn('"operation": "first"', path.read_text(encoding="utf-8"))
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
