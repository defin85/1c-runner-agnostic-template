from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.python.qa import _RUNTIME_DETAIL_PATTERN, check_skill_bindings


class SkillBindingsTests(unittest.TestCase):
    def test_stale_claude_mirror_is_reported_with_fix_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".agents" / "skills").mkdir(parents=True)
            (root / ".claude" / "skills").mkdir(parents=True)
            stderr = io.StringIO()
            with (
                patch("scripts.python.imported_skills.claude_skill_mirror_drift", return_value=[".claude/skills/demo"]),
                contextlib.redirect_stderr(stderr),
            ):
                status = check_skill_bindings(root)

        self.assertEqual(status, 1)
        self.assertIn("stale Claude skill mirror: .claude/skills/demo; run make sync-claude-skills", stderr.getvalue())

    def test_runtime_detail_pattern_matches_rac_only_as_a_word(self) -> None:
        self.assertIsNone(_RUNTIME_DETAIL_PATTERN.search("Run `trac info` to inspect the ticket."))
        self.assertIsNone(_RUNTIME_DETAIL_PATTERN.search("Use the bracket notation."))
        self.assertIsNotNone(_RUNTIME_DETAIL_PATTERN.search("Call rac infobase summary list."))
        self.assertIsNotNone(_RUNTIME_DETAIL_PATTERN.search("`rac cluster list`"))
        self.assertIsNotNone(_RUNTIME_DETAIL_PATTERN.search("powershell.exe -File run.ps1"))


if __name__ == "__main__":
    unittest.main()
