from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.python.runtime_selection import select_source_path


class RuntimeSelectionTests(unittest.TestCase):
    def test_exact_source_root_accepts_windows_separators_and_unicode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "src" / "cf" / "Каталог с пробелом" / "Модуль.bsl"
            target.parent.mkdir(parents=True)
            target.write_text("", encoding="utf-8")
            result = select_source_path(root, "src/cf", "src\\cf\\Каталог с пробелом\\Модуль.bsl")
            self.assertEqual(result.relative_path, "Каталог с пробелом/Модуль.bsl")
            self.assertIsNone(result.reason)

    def test_sibling_with_same_prefix_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "src" / "cf-other" / "Configuration.xml"
            target.parent.mkdir(parents=True)
            target.write_text("", encoding="utf-8")
            result = select_source_path(root, "src/cf", "src/cf-other/Configuration.xml")
            self.assertEqual(result.reason, "outside-source-tree")

    def test_deleted_file_is_not_selected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = select_source_path(Path(temp_dir), "src/cf", "src/cf/Deleted.xml", deleted=True)
            self.assertEqual(result.reason, "missing-or-deleted")


if __name__ == "__main__":
    unittest.main()
