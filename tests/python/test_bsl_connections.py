from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts.python.bsl_connections import resolve_profile_connections, user_env_name
from scripts.python.bsl_mcp_runtime import load_runtime_connections, run_bsl_analyzer_mcp
from scripts.python.runtime_errors import CommandError
from scripts.python.runtime_process import ProcessResult

PASSWORD_ENV = "BSL_CONNECTIONS_FIXTURE_PASSWORD"


def write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def profile(root: Path, user: object = "Operator", password_env: object = PASSWORD_ENV) -> Path:
    auth = {"mode": "user-password", "user": user, "passwordEnv": password_env}
    return write_json(root / "env" / "dev.json", {"infobase": {"mode": "file", "auth": auth}})


class ResolveProfileConnectionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_profile_entry_becomes_env_references(self) -> None:
        profile(self.root)
        registry = {"connections": {"dev-base": {"profile": "env/dev.json", "label": "dev"}}}
        resolved, users = resolve_profile_connections(registry, self.root)
        entry = resolved["connections"]["dev-base"]
        self.assertEqual(user_env_name("dev-base"), "BSL_ONEC_USER__DEV_BASE")
        self.assertEqual(entry, {"label": "dev", "user_env": "BSL_ONEC_USER__DEV_BASE", "password_env": PASSWORD_ENV})
        self.assertEqual(users, {"BSL_ONEC_USER__DEV_BASE": "Operator"})
        self.assertNotIn("profile", json.dumps(resolved))

    def test_invalid_entries_are_rejected(self) -> None:
        profile(self.root)
        cases: list[tuple[dict[str, Any], str]] = [
            ({"profile": "env/dev.json", "user_env": "X"}, "cannot be combined"),
            ({"profile": "env/missing.json"}, "cannot be read"),
            ({"user_env": "X", "password": "inline"}, "passwords are not allowed"),
        ]
        for entry, message in cases:
            with self.subTest(entry=entry), self.assertRaisesRegex(CommandError, message):
                resolve_profile_connections({"connections": {"base": entry}}, self.root)
        for user, password_env in ((None, PASSWORD_ENV), ("Operator", None)):
            profile(self.root, user, password_env)
            with self.subTest(user=user), self.assertRaisesRegex(CommandError, "infobase.auth.user/passwordEnv"):
                resolve_profile_connections({"connections": {"base": {"profile": "env/dev.json"}}}, self.root)

    def test_runtime_connections_require_available_password(self) -> None:
        profile(self.root)
        registry = write_json(self.root / "registry.json", {"connections": {"dev": {"profile": "env/dev.json"}}})
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load_runtime_connections(registry, self.root), ({}, {}))
        with patch.dict(os.environ, {PASSWORD_ENV: "value"}, clear=True):
            available, users = load_runtime_connections(registry, self.root)
        self.assertEqual(list(available), ["dev"])
        self.assertEqual(users, {"BSL_ONEC_USER__DEV": "Operator"})

    def test_mcp_launcher_passes_profile_user_without_password(self) -> None:
        source = self.root / "src" / "cf"
        source.mkdir(parents=True)
        (source / "Configuration.xml").write_text("", encoding="utf-8")
        profile(self.root)
        registry = write_json(self.root / "registry.json", {"connections": {"dev": {"profile": "env/dev.json"}}})
        captured: dict[str, Any] = {}

        def fake_run(command: list[str], **kwargs: Any) -> ProcessResult:
            env = kwargs["env"]
            captured["env"] = env
            captured["registry"] = json.loads(Path(env["BSL_ONEC_CONNECTIONS_FILE"]).read_text(encoding="utf-8"))
            return ProcessResult(command, 0, "", "")

        with (
            patch("scripts.python.bsl_mcp_runtime.project_root", return_value=self.root),
            patch("scripts.python.bsl_mcp_runtime.resolve_analyzer_executable", return_value="bsl-analyzer-app"),
            patch("scripts.python.bsl_mcp_runtime.embedding_is_ready", return_value=False),
            patch("scripts.python.bsl_mcp_runtime.run_process", side_effect=fake_run),
            patch.dict(
                os.environ,
                {"BSL_ONEC_CONNECTIONS_FILE": str(registry), PASSWORD_ENV: "secret-value"},
                clear=True,
            ),
        ):
            self.assertEqual(run_bsl_analyzer_mcp([]), 0)
        self.assertEqual(captured["env"]["BSL_ONEC_USER__DEV"], "Operator")
        self.assertEqual(
            captured["registry"],
            {"connections": {"dev": {"user_env": "BSL_ONEC_USER__DEV", "password_env": PASSWORD_ENV}}},
        )
        self.assertNotIn("secret-value", json.dumps(captured["registry"]))


if __name__ == "__main__":
    unittest.main()
