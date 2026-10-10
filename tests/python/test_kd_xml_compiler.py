from __future__ import annotations

import ast
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.migration.kd_xml_compiler import ReleaseError, compile_release
from scripts.migration.kd_xml_compiler.release import validate_matrix

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "scripts" / "migration" / "kd_xml_compiler"
FIXTURE = ROOT / "tests" / "fixtures" / "kd21"


def _fixture_scenario() -> dict:
    return json.loads((FIXTURE / "scenario" / "scenario.json").read_text(encoding="utf-8"))


def _matrix() -> dict:
    return json.loads((FIXTURE / "scenario" / "matrix.json").read_text(encoding="utf-8"))


def _build(scenario: dict, output: Path) -> dict:
    return compile_release(
        scenario,
        output,
        source_structure=ROOT / scenario["inputs"]["sourceStructure"],
        target_structure=ROOT / scenario["inputs"]["targetStructure"],
        matrix=_matrix(),
    )


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.append("." * node.level + module)
    return names


def boundary_violations(core: Path) -> list[str]:
    """Imports of the stage executor or of anything outside the core and the standard library."""
    violations: list[str] = []
    for path in sorted(core.glob("*.py")):
        for name in _imports(path):
            if name.startswith("."):
                continue
            top = name.split(".")[0]
            if name.startswith("scripts") or "kd_cycle" in name or top not in _stdlib():
                violations.append(f"{path.name}: {name}")
    return violations


def _stdlib() -> frozenset[str]:
    import sys

    return frozenset(sys.stdlib_module_names) | {"__future__"}


class CompilerBoundaryTest(unittest.TestCase):
    def test_core_imports_only_itself_and_stdlib(self) -> None:
        self.assertEqual(boundary_violations(CORE), [])

    def test_boundary_check_names_the_importing_module(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            core = Path(temp_dir)
            shutil.copytree(CORE, core, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
            (core / "leak.py").write_text("from scripts.migration import kd_cycle_common\n", encoding="utf-8")
            self.assertEqual(boundary_violations(core), ["leak.py: scripts.migration"])


class CompilerReleaseTest(unittest.TestCase):
    def test_two_builds_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir) / "run-a" / "release"
            second = Path(second_dir) / "other" / "place" / "release"
            manifest = _build(_fixture_scenario(), first)
            _build(_fixture_scenario(), second)
            self.assertEqual(len(manifest["files"]), 5)
            self.assertEqual(len(manifest["archives"]), 3)
            names = sorted(path.relative_to(first).as_posix() for path in first.rglob("*") if path.is_file())
            self.assertEqual(
                names,
                sorted(path.relative_to(second).as_posix() for path in second.rglob("*") if path.is_file()),
            )
            self.assertIn("manifest.json", names)
            for name in names:
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes(), name)
            manifest_text = (first / "manifest.json").read_text(encoding="utf-8")
            self.assertNotIn(first_dir, manifest_text)
            self.assertEqual(set(json.loads(manifest_text)), set(manifest))
            with zipfile.ZipFile(first / "target" / "Rules.zip") as archive:
                self.assertEqual(
                    archive.namelist(), ["ExchangeRules.xml", "CorrespondentExchangeRules.xml", "RegistrationRules.xml"]
                )
                self.assertEqual(
                    archive.read("ExchangeRules.xml"), (first / "target" / "ExchangeRules.xml").read_bytes()
                )

    def test_documents_follow_kd_201(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            release = Path(temp_dir) / "release"
            _build(_fixture_scenario(), release)
            forward = (release / "source" / "ExchangeRules.xml").read_bytes().decode("utf-8-sig")
            self.assertTrue(forward.startswith("<ПравилаОбмена>\r\n"))
            self.assertIn('<ВерсияФормата РежимСовместимости="РежимСовместимостиСБСП21">2.01</ВерсияФормата>', forward)
            self.assertIn("<Наименование>DEMO_SOURCE_TARGET_TECHNICAL_FORWARD</Наименование>", forward)
            self.assertEqual(
                forward, (release / "target" / "CorrespondentExchangeRules.xml").read_bytes().decode("utf-8-sig")
            )
            registration = (release / "source" / "RegistrationRules.xml").read_text(encoding="utf-8")
            self.assertIn('Имя="ОбменИсточникПриемник"', registration)

    def test_changed_structure_stops_before_writing(self) -> None:
        scenario = _fixture_scenario()
        scenario["inputs"]["sourceStructureSha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp_dir:
            release = Path(temp_dir) / "release"
            with self.assertRaises(ReleaseError) as raised:
                _build(scenario, release)
            self.assertIn("source.xml", str(raised.exception))
            self.assertFalse(release.exists())

    def test_version_mismatch_is_refused(self) -> None:
        scenario = _fixture_scenario()
        scenario["versions"]["target"] = "9.9.9.9"
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ReleaseError, "target structure version"):
                _build(scenario, Path(temp_dir) / "release")

    def test_matrix_must_cover_every_document_role(self) -> None:
        matrix = _matrix()
        matrix["files"] = matrix["files"][:4]
        with self.assertRaisesRegex(ReleaseError, "target-registration"):
            validate_matrix(matrix)
        matrix = _matrix()
        matrix["archives"][0]["members"] = ["../secret.xml"]
        with self.assertRaisesRegex(ReleaseError, "inside the release"):
            validate_matrix(matrix)


if __name__ == "__main__":
    unittest.main()
