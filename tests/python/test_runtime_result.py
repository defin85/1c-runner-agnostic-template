from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.python.runtime_result import (
    evaluate_postcondition,
    prepare_run_artifacts,
    publish_summary,
    sanitize_artifact_logs,
)


class RuntimeResultTests(unittest.TestCase):
    def test_run_root_contains_required_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = prepare_run_artifacts(Path(temp_dir) / "run root")
            publish_summary(artifacts, {"status": "success"})
            self.assertTrue(artifacts.summary_path.is_file())
            self.assertTrue(artifacts.stdout_path.is_file())
            self.assertTrue(artifacts.stderr_path.is_file())

    def test_secret_is_removed_from_summary_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = prepare_run_artifacts(temp_dir)
            secret = "пароль-секрет"
            artifacts.stdout_path.write_text(f"argv --password={secret}", encoding="utf-8")
            artifacts.stderr_path.write_text(f"error {secret}", encoding="utf-8")
            sanitize_artifact_logs(artifacts, [secret])
            publish_summary(artifacts, {"diagnostic_argv": ["tool", secret]}, [secret])
            combined = artifacts.stdout_path.read_text(encoding="utf-8") + artifacts.stderr_path.read_text(encoding="utf-8") + artifacts.summary_path.read_text(encoding="utf-8")
            self.assertNotIn(secret, combined)
            self.assertIn("__REDACTED_SECRET__", combined)

    def test_failed_postcondition_overrides_zero_tool_exit(self) -> None:
        status, exit_code, reason = evaluate_postcondition(
            lambda: False,
            failure_message="expected file was not produced",
            tool_exit_code=0,
        )
        self.assertEqual(status, "failed")
        self.assertNotEqual(exit_code, 0)
        self.assertEqual(reason, "expected file was not produced")


if __name__ == "__main__":
    unittest.main()
