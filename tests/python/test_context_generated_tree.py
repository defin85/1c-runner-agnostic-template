from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.python.common import CommandError
from scripts.python.context import render_generated_metadata, render_generated_tree


def touch(root: Path, rel: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")


class GeneratedTreeTests(unittest.TestCase):
    def test_tree_is_depth_limited_and_hides_build_output(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for rel in (
                "src/cf/Catalogs/Item/Ext/ObjectModule.bsl",
                ".artifacts/run/summary.json",
                ".build/out.cf",
                "scripts/__pycache__/mod.cpython-312.pyc",
                "env/local.json",
                "automation/context/source-tree.generated.txt",
                "automation/context/project-map.md",
            ):
                touch(root, rel)
            lines = render_generated_tree(root).splitlines()
        self.assertEqual(lines[:3], ["# Generated Project Tree", "", "."])
        self.assertIn("./src/cf/Catalogs/Item", lines)
        self.assertNotIn("./src/cf/Catalogs/Item/Ext", lines)
        self.assertIn("./automation/context/project-map.md", lines)
        for hidden in (".artifacts", ".build", "__pycache__", "env/local.json", "source-tree.generated.txt"):
            self.assertFalse(any(hidden in line for line in lines), hidden)

    def test_tree_uses_git_visibility_when_index_exists(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            touch(root, ".gitignore")
            (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
            touch(root, "ignored/file.txt")
            touch(root, "docs/README.md")
            lines = render_generated_tree(root).splitlines()
        self.assertIn("./docs/README.md", lines)
        self.assertNotIn("./ignored", lines)


if __name__ == "__main__":
    unittest.main()


class GeneratedMetadataTests(unittest.TestCase):
    def test_inventory_lists_stay_on_one_line(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            touch(root, "src/cf/CommonModules/Shared/Ext/Module.bsl")
            text = render_generated_metadata(root)
        self.assertIn('"configurationRoots": ["src/cf", "src/cfe", "src/epf", "src/erf"]', text)
        self.assertIn('"commonModules": ["src/cf/CommonModules/Shared"]', text)
        self.assertIsNone(json.loads(text)["targetMetadata"])

    def test_target_metadata_is_exported_and_stale_matrix_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "src" / "cf" / "one").mkdir(parents=True)
            (root / "src" / "cf" / "one" / "Configuration.xml").write_text(
                '<Configuration name="One" uuid="one-id" />', encoding="utf-8"
            )
            (root / "src" / "cfe" / "Ext").mkdir(parents=True)
            matrix = {"schemaVersion": 1, "targets": [{"id": "one"}], "extensionMatrix": {"one": ["Ext"]}}
            touch(root, "automation/context/target-matrix.json")
            (root / "automation" / "context" / "target-matrix.json").write_text(json.dumps(matrix), encoding="utf-8")
            metadata = json.loads(render_generated_metadata(root))["targetMetadata"]
            matrix["extensionMatrix"]["one"].append("Missing")
            (root / "automation" / "context" / "target-matrix.json").write_text(json.dumps(matrix), encoding="utf-8")
            with self.assertRaisesRegex(CommandError, "target matrix extension not found under src/cfe: Missing"):
                render_generated_metadata(root)
        self.assertEqual(metadata["targets"][0]["sourcePath"], "src/cf/one")
        self.assertEqual(metadata["targets"][0]["configuration"]["name"], "One")
        self.assertEqual(metadata["extensionMatrix"], {"one": ["Ext"]})
