from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.python.context import render_generated_tree


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
