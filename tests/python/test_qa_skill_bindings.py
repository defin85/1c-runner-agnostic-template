from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.python.qa import check_skill_bindings


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


if __name__ == "__main__":
    unittest.main()
