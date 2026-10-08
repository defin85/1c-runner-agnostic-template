"""Local v8std cache: fetch stores pages outside Git, search reads only the cache."""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.python import v8std

ROOT = Path(__file__).resolve().parents[2]

HDOC = '<html><a href="/db/content/v8std/src/std456/i8100001.htm">source</a></html>'
SOURCE = (
    "<html><head><title>Демо стандарт :: v8std</title></head>"
    "<body><p>#std456 Перед первым обращением проверяйте ссылку на пустое значение.</p>"
    "<script>ignored()</script></body></html>"
)


class V8StdTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cache = Path(self.enterContext(tempfile.TemporaryDirectory())) / "cache"
        self.enterContext(patch.dict(os.environ, {"V8STD_CACHE_ROOT": str(self.cache)}))

    def test_default_cache_is_ignored_by_git(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("V8STD_CACHE_ROOT", None)
            self.assertEqual(ROOT / ".artifacts" / "v8std", v8std.cache_root())
        if shutil.which("git") is None or not (ROOT / ".git").exists():
            self.skipTest("git checkout is not available")
        completed = subprocess.run(["git", "check-ignore", "-q", ".artifacts/v8std/std456.json"], cwd=ROOT, check=False)
        self.assertEqual(0, completed.returncode)

    def test_normalize_input_accepts_number_id_and_path(self) -> None:
        expected = "https://its.1c.ru/db/v8std/content/456/hdoc"
        self.assertEqual(expected, v8std.normalize_input("456"))
        self.assertEqual(expected, v8std.normalize_input("std456"))
        self.assertEqual(expected, v8std.normalize_input("#std456"))
        self.assertEqual("https://its.1c.ru/db/v8std/content/1/hdoc", v8std.normalize_input("/db/v8std/content/1/hdoc"))

    def test_fetch_writes_only_cache_and_search_finds_text(self) -> None:
        pages = {
            "https://its.1c.ru/db/v8std/content/456/hdoc": HDOC,
            "https://its.1c.ru/db/content/v8std/src/std456/i8100001.htm": SOURCE,
        }
        with patch.object(v8std, "read_url", side_effect=pages.__getitem__), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(0, v8std.main(["fetch", "456"]))
        self.assertIn("std456: Демо стандарт", out.getvalue())
        self.assertEqual({"std456.json", "std456.txt"}, {path.name for path in self.cache.iterdir()})
        self.assertNotIn("ignored()", (self.cache / "std456.txt").read_text(encoding="utf-8"))

        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(0, v8std.main(["search", "пустое значение"]))
        self.assertIn("i8100001.htm", out.getvalue())

    def test_search_without_match_returns_error(self) -> None:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err:
            self.assertEqual(1, v8std.main(["search", "нет такого текста"]))
        self.assertIn("nothing found", err.getvalue())

    @unittest.skipIf(os.name == "nt", "Bash wrappers are POSIX entrypoints")
    def test_wrappers_show_help(self) -> None:
        for name in ("v8std-fetch", "v8std-search"):
            completed = subprocess.run(
                [str(ROOT / "scripts/tools" / name), "--help"], capture_output=True, text=True, check=False
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertIn("usage: v8std", completed.stdout)


if __name__ == "__main__":
    unittest.main()
