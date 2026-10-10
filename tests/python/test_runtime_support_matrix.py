from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.python.qa import validate_runtime_support_matrix
from scripts.python.template_tools import (
    _runtime_support_matrix_json,
    _runtime_support_matrix_md,
    migrate_runtime_support_matrix,
    refresh_generated_project_surface,
    render_runtime_support_matrix_files,
    seed_generated_project_surface,
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


class RuntimeSupportMatrixMigrationTests(unittest.TestCase):
    """Р16: the migration adds only absent platform entries and is idempotent."""

    def legacy_project(self, root: Path) -> tuple[Path, Path]:
        payload = _runtime_support_matrix_json()
        contours = payload["contours"]
        assert isinstance(contours, list)
        for contour in contours:
            del contour["platforms"]
        # A project-owned contour, and one contour where the project already wrote a linux entry.
        contours.append(
            {
                "id": "project-report",
                "layer": "profile-required",
                "status": "operator-local",
                "entrypoint": "make project-report",
                "profileProvenance": "operator-local env/local.json",
                "runbookPath": "docs/agent/operator-local-runbook.md",
                "summary": "Project-owned report contour.",
                "projectNote": "kept",
            }
        )
        contours[3]["platforms"] = {
            "linux": {
                "status": "supported",
                "evidenceClass": "contract-plus-live",
                "evidence": {
                    "fingerprint": "fixture",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "expiresAt": "2099-01-01T00:00:00Z",
                },
            }
        }
        context = root / "automation" / "context"
        context.mkdir(parents=True)
        json_path = context / "runtime-support-matrix.json"
        markdown_path = context / "runtime-support-matrix.md"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
        markdown_path.write_text("# Legacy matrix\n", encoding="utf-8")
        return json_path, markdown_path

    def test_validation_names_migration_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.legacy_project(root)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(validate_runtime_support_matrix(root), 1)
            self.assertIn("missing capability/platform entry", stderr.getvalue())
            self.assertIn("./scripts/template/migrate-runtime-support-matrix.sh", stderr.getvalue())

    def test_migration_adds_only_absent_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path, markdown_path = self.legacy_project(root)
            before = json.loads(json_path.read_text(encoding="utf-8"))

            report = migrate_runtime_support_matrix(root)

            after = json.loads(json_path.read_text(encoding="utf-8"))
            for old, new in zip(before["contours"], after["contours"], strict=True):
                old_platforms = old.pop("platforms", {})
                new_platforms = new.pop("platforms")
                self.assertEqual(old, new)
                for platform, support in old_platforms.items():
                    self.assertEqual(new_platforms[platform], support)
                self.assertEqual(sorted(new_platforms), ["linux", "windows"])
            self.assertEqual(
                {k: v for k, v in before.items() if k != "contours"},
                {k: v for k, v in after.items() if k != "contours"},
            )
            by_id = {
                contour["id"]: contour for contour in json.loads(json_path.read_text(encoding="utf-8"))["contours"]
            }
            self.assertEqual(
                by_id["project-report"]["platforms"]["windows"],
                {"status": "operator-local", "evidenceClass": "contract-plus-live", "evidence": None},
            )
            self.assertEqual(by_id["bdd-warm-service"]["platforms"]["windows"]["status"], "unsupported")
            self.assertNotIn(f"{before['contours'][3]['id']}/linux", report)
            self.assertIn(f"added platform entry (evidence: null): {before['contours'][3]['id']}/windows", report)
            self.assertEqual(
                markdown_path.read_text(encoding="utf-8"),
                _runtime_support_matrix_md(json.loads(json_path.read_text(encoding="utf-8"))),
            )
            self.assertEqual(validate_runtime_support_matrix(root), 0)

    def test_second_run_changes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path, markdown_path = self.legacy_project(root)
            migrate_runtime_support_matrix(root)
            snapshot = (json_path.read_bytes(), markdown_path.read_bytes())

            report = migrate_runtime_support_matrix(root)

            self.assertEqual((json_path.read_bytes(), markdown_path.read_bytes()), snapshot)
            self.assertIn("nothing changed", report)

    def test_complete_matrix_json_is_not_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = root / "automation" / "context"
            context.mkdir(parents=True)
            json_path = context / "runtime-support-matrix.json"
            text = json.dumps(_runtime_support_matrix_json(), separators=(",", ":"))
            json_path.write_text(text, encoding="utf-8")

            report = migrate_runtime_support_matrix(root)

            self.assertEqual(json_path.read_text(encoding="utf-8"), text)
            self.assertIn("rebuilt automation/context/runtime-support-matrix.md from JSON", report)
            self.assertEqual(validate_runtime_support_matrix(root), 0)


class TemplateUpdateSurfaceTests(unittest.TestCase):
    """template-update on Windows runs refresh_generated_project_surface; it must match the POSIX refresh."""

    def test_refresh_keeps_filled_project_owned_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed_generated_project_surface(root, "Fixture", "fixture", "Fixture project")
            context = root / "automation" / "context"
            filled = {
                context / "runtime-support-matrix.json": '{"filled": true}\n',
                context / "runtime-support-matrix.md": "# Filled matrix\n",
                root / "docs" / "agent" / "runtime-quickstart.md": "# Filled quickstart\n",
            }
            for path, text in filled.items():
                path.write_text(text, encoding="utf-8")
            readme = root / "README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + "\nProject notes.\n", encoding="utf-8")
            (root / "docs" / "agent" / "architecture-map.md").unlink()

            refresh_generated_project_surface(root, "Fixture", "fixture", "Fixture project")

            for path, text in filled.items():
                self.assertEqual(path.read_text(encoding="utf-8"), text, path.name)
            self.assertTrue((root / "docs" / "agent" / "architecture-map.md").is_file())
            readme_text = readme.read_text(encoding="utf-8")
            self.assertEqual(readme_text.count("<!-- RUNNER_AGNOSTIC_PROJECT:START -->"), 1)
            self.assertTrue(readme_text.startswith("<!-- RUNNER_AGNOSTIC_PROJECT:START -->"))
            self.assertIn("Project notes.", readme_text)

    def test_refresh_recreates_missing_matrix_from_shared_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            refresh_generated_project_surface(root, "Fixture", "fixture", "")
            context = root / "automation" / "context"
            payload = json.loads((context / "runtime-support-matrix.json").read_text(encoding="utf-8"))
            markdown = context / "runtime-support-matrix.md"
            self.assertEqual(markdown.read_text(encoding="utf-8"), _runtime_support_matrix_md(payload))
            self.assertEqual(validate_runtime_support_matrix(root), 0)
            markdown.unlink()
            refresh_generated_project_surface(root, "Fixture", "fixture", "")
            self.assertEqual(markdown.read_text(encoding="utf-8"), _runtime_support_matrix_md(payload))


if __name__ == "__main__":
    unittest.main()
