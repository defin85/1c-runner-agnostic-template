from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.python.qa import validate_runtime_support_matrix
from scripts.python.template_tools import (
    _runtime_support_matrix_json,
    _runtime_support_matrix_md,
    render_runtime_support_matrix_files,
)


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
            contours = payload["contours"]
            assert isinstance(contours, list)
            self.assertEqual(contours[0]["platforms"]["windows"]["evidenceClass"], "contract-only")

    def test_toolkit_contours_are_honest_about_windows(self) -> None:
        payload = _runtime_support_matrix_json()
        contours = payload["contours"]
        assert isinstance(contours, list)
        by_id = {contour["id"]: contour for contour in contours}
        toolkit = {"check-bsl", "check-cf-modules", "analyze-bsl-external", "run-client", "technological-log"}
        for contour_id in toolkit | {"artifact-storage"}:
            self.assertIn(contour_id, by_id)
            self.assertIn("not been executed on Windows", by_id[contour_id]["summary"])
        for contour_id in toolkit:
            windows = by_id[contour_id]["platforms"]["windows"]
            self.assertEqual(windows["status"], "operator-local")
            self.assertEqual(windows["evidenceClass"], "contract-plus-live")
            self.assertIsNone(windows["evidence"])
        markdown = _runtime_support_matrix_md(payload)
        self.assertIn("| `run-client` | `windows` | `operator-local` |", markdown)

    def test_markdown_keeps_generated_contract_sections(self) -> None:
        markdown = _runtime_support_matrix_md(_runtime_support_matrix_json())
        for text in (
            "## Optional Project-Specific Baseline Extension",
            "automation/context/project-map.md",
            "docs/agent/operator-local-runbook.md",
            "docs/agent/runtime-quickstart.md",
            "docs/agent/generated-project-index.md",
            "docs/agent/generated-project-verification.md",
            "`init-test-tooling`",
            "`install-test-tooling`",
            "`provisioned`",
        ):
            self.assertIn(text, markdown)
        self.assertIn("Windows: обёртки `check-bsl`", markdown)

    def test_render_adds_platforms_to_posix_seed_without_platforms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = _runtime_support_matrix_json()
            for contour in payload["contours"]:
                del contour["platforms"]
            target = root / "automation" / "context"
            target.mkdir(parents=True)
            json_path = target / "runtime-support-matrix.json"
            json_path.write_text(json.dumps(payload), encoding="utf-8")
            render_runtime_support_matrix_files(json_path, target / "runtime-support-matrix.md")
            self.assertEqual(validate_runtime_support_matrix(root), 0)
            rendered = json.loads(json_path.read_text(encoding="utf-8"))
            by_id = {contour["id"]: contour for contour in rendered["contours"]}
            self.assertEqual(by_id["bdd-warm-service"]["platforms"]["windows"]["status"], "unsupported")

    def test_supported_live_entry_requires_unexpired_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = _runtime_support_matrix_json()
            contours = payload["contours"]
            assert isinstance(contours, list)
            support = contours[3]["platforms"]["windows"]
            support["status"] = "supported"
            self.write_matrix(root, payload)
            self.assertEqual(validate_runtime_support_matrix(root), 1)
            support["evidence"] = {
                "fingerprint": "fixture",
                "timestamp": "2026-01-01T00:00:00Z",
                "expiresAt": "2020-01-01T00:00:00Z",
            }
            self.write_matrix(root, payload)
            self.assertEqual(validate_runtime_support_matrix(root), 1)

    def test_stale_markdown_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = _runtime_support_matrix_json()
            self.write_matrix(root, payload)
            markdown = root / "automation" / "context" / "runtime-support-matrix.md"
            markdown.write_text(
                markdown.read_text(encoding="utf-8").replace("| `doctor` | `windows` |", "| `doctor` | `other` |"),
                encoding="utf-8",
            )
            self.assertEqual(validate_runtime_support_matrix(root), 1)


if __name__ == "__main__":
    unittest.main()
