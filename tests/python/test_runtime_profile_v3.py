from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.python.common import CommandError
from scripts.python.runtime import load_runtime_profile
from scripts.python.template_tools import migrate_runtime_profile_v3


class RuntimeProfileV3Tests(unittest.TestCase):
    def write_profile(self, root: Path, payload: dict[str, object]) -> Path:
        path = root / "profile.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_local_execution_is_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_profile(
                Path(directory),
                {"schemaVersion": 3, "profileName": "local", "capabilities": {}},
            )
            profile = load_runtime_profile(path)
        self.assertIsNotNone(profile)
        self.assertEqual(profile.runner_adapter, "direct-platform")

    def test_remote_windows_is_an_explicit_transport(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_profile(
                Path(directory),
                {
                    "schemaVersion": 3,
                    "profileName": "remote",
                    "transport": {"kind": "remote-windows"},
                    "capabilities": {},
                },
            )
            profile = load_runtime_profile(path)
        self.assertIsNotNone(profile)
        self.assertEqual(profile.runner_adapter, "remote-windows")

    def test_unknown_transport_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_profile(
                Path(directory),
                {
                    "schemaVersion": 3,
                    "transport": {"kind": "unknown"},
                    "capabilities": {},
                },
            )
            with self.assertRaisesRegex(CommandError, "unsupported transport.kind=unknown"):
                load_runtime_profile(path)

    def test_windows_rejects_posix_only_platform_features(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "profile.json"
            path.write_text(json.dumps({"schemaVersion": 3, "platform": {"xpra": {"enabled": True}}}), encoding="utf-8")
            with patch("scripts.python.runtime_profiles.os.name", "nt"):
                with self.assertRaisesRegex(CommandError, "POSIX-only"):
                    load_runtime_profile(path)

    def test_profile_defined_command_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_profile(
                Path(directory),
                {
                    "schemaVersion": 3,
                    "capabilities": {"smoke": {"command": ["echo", "ok"]}},
                },
            )
            with self.assertRaisesRegex(CommandError, "does not support profile-defined command"):
                load_runtime_profile(path)

    def test_schema_v2_migration_report_removes_local_adapter_and_default_diff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_profile(
                Path(directory),
                {
                    "schemaVersion": 2,
                    "profileName": "legacy-v2",
                    "runnerAdapter": "direct-platform",
                    "capabilities": {
                        "diffSrc": {"command": ["git", "diff", "--", "./src"]},
                        "loadSrc": {"driver": "ibcmd", "sourceDir": "./src/cf"},
                    },
                },
            )
            report = json.loads(migrate_runtime_profile_v3(path))
        self.assertEqual(report["status"], "dry-run")
        self.assertEqual(report["targetSchemaVersion"], 3)
        self.assertNotIn("runnerAdapter", report["profile"])
        self.assertNotIn("transport", report["profile"])
        self.assertNotIn("command", report["profile"]["capabilities"]["diffSrc"])

    def test_schema_v2_shell_orchestration_is_not_partially_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_profile(
                Path(directory),
                {
                    "schemaVersion": 2,
                    "runnerAdapter": "direct-platform",
                    "capabilities": {"smoke": {"command": ["bash", "-lc", "echo ok"]}},
                },
            )
            with self.assertRaisesRegex(CommandError, "without a supported schemaVersion=3 backend"):
                migrate_runtime_profile_v3(path)

    def test_schema_v2_remote_adapter_becomes_transport(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_profile(
                Path(directory),
                {
                    "schemaVersion": 2,
                    "runnerAdapter": "remote-windows",
                    "capabilities": {},
                },
            )
            report = json.loads(migrate_runtime_profile_v3(path))
        self.assertEqual(
            report["profile"]["transport"],
            {"kind": "remote-windows"},
        )


if __name__ == "__main__":
    unittest.main()
