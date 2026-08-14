from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.python.qa import validate_runtime_support_matrix
from scripts.python.template_tools import _runtime_support_matrix_json, _runtime_support_matrix_md


class RuntimeSupportMatrixTests(unittest.TestCase):
    def write_matrix(self, root: Path, payload: dict[str, object]) -> None:
        target = root / "automation" / "context"
        target.mkdir(parents=True, exist_ok=True)
        (target / "runtime-support-matrix.json").write_text(json.dumps(payload), encoding="utf-8")
        (target / "runtime-support-matrix.md").write_text(_runtime_support_matrix_md(payload), encoding="utf-8")

    def test_generated_matrix_is_platform_and_evidence_aware(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = _runtime_support_matrix_json()
            self.write_matrix(root, payload)
            self.assertEqual(validate_runtime_support_matrix(root), 0)
            self.assertEqual(payload["contours"][0]["platforms"]["windows"]["evidenceClass"], "contract-only")

    def test_supported_live_entry_requires_unexpired_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = _runtime_support_matrix_json()
            support = payload["contours"][3]["platforms"]["windows"]
            support["status"] = "supported"
            self.write_matrix(root, payload)
            self.assertEqual(validate_runtime_support_matrix(root), 1)
            support["evidence"] = {"fingerprint": "fixture", "timestamp": "2026-01-01T00:00:00Z", "expiresAt": "2020-01-01T00:00:00Z"}
            self.write_matrix(root, payload)
            self.assertEqual(validate_runtime_support_matrix(root), 1)

    def test_stale_markdown_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = _runtime_support_matrix_json()
            self.write_matrix(root, payload)
            markdown = root / "automation" / "context" / "runtime-support-matrix.md"
            markdown.write_text(markdown.read_text(encoding="utf-8").replace("| `doctor` | `windows` |", "| `doctor` | `other` |"), encoding="utf-8")
            self.assertEqual(validate_runtime_support_matrix(root), 1)


if __name__ == "__main__":
    unittest.main()
