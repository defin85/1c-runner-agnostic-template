from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.python.runtime_paths import resolve_project_tree_path
from scripts.python.runtime_profiles import load_runtime_profile
from scripts.python.runtime_secrets import build_redacted_context, resolve_secret_value


class RuntimePrimitiveTests(unittest.TestCase):
    def test_profile_accepts_utf8_crlf_and_space_in_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime profile ") as temp_dir:
            profile_path = Path(temp_dir) / "профиль 1С.json"
            payload = {"schemaVersion": 3, "profileName": "Локальная База"}
            profile_path.write_bytes((json.dumps(payload, ensure_ascii=False, indent=2) + "\r\n").encode("utf-8"))

            profile = load_runtime_profile(profile_path)

            self.assertIsNotNone(profile)
            self.assertEqual(profile.name, "Локальная База")
            self.assertEqual(profile.path, profile_path.resolve())

    def test_project_path_preserves_spaces_and_cyrillic(self) -> None:
        path = resolve_project_tree_path("src/cf/Тестовая база/Configuration.xml")
        self.assertTrue(str(path).endswith(str(Path("src/cf/Тестовая база/Configuration.xml"))))

    def test_secret_is_resolved_without_entering_redacted_context(self) -> None:
        payload = {
            "schemaVersion": 3,
            "profileName": "safe",
            "infobase": {"auth": {"mode": "explicit", "passwordEnv": "ONEC_PASSWORD"}},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "profile.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            profile = load_runtime_profile(path)
            with patch.dict(os.environ, {"ONEC_PASSWORD": "highly-secret-value"}):
                self.assertEqual(resolve_secret_value("ONEC_PASSWORD"), "highly-secret-value")
                self.assertNotIn("highly-secret-value", json.dumps(build_redacted_context(profile)))

    def test_missing_secret_has_stable_dry_run_placeholder(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resolve_secret_value("MISSING_SECRET", dry_run=True), "__REDACTED_SECRET__")


if __name__ == "__main__":
    unittest.main()
