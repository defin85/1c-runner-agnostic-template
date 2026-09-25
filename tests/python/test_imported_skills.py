from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.python.imported_skills import _mirror_claude_skills, _render_agents_skill


class ImportedSkillsTests(unittest.TestCase):
    def test_codex_discovery_description_uses_existing_short_description(self) -> None:
        rendered = _render_agents_skill(
            {
                "name": "cf-edit",
                "description": "Точечное редактирование конфигурации 1С. Используй для изменения свойств и состава объектов.",
                "runtime_kind": "reference",
                "vendor_dir": "skills/cf-edit",
                "preferred_native_skills": [],
            }
        )
        description_line = next(line for line in rendered.splitlines() if line.startswith("description: "))
        description = json.loads(description_line.removeprefix("description: "))

        self.assertLessEqual(len(description), 72)
        self.assertNotIn("Импортированный compatibility skill", description)
        self.assertTrue(description.startswith("Точечное редактирование конфигурации 1С"))

    def test_codex_skill_documents_both_platform_launchers(self) -> None:
        rendered = _render_agents_skill(
            {
                "name": "cf-edit",
                "description": "Точечное редактирование конфигурации 1С.",
                "runtime_kind": "reference",
                "vendor_dir": "skills/cf-edit",
                "preferred_native_skills": [],
            }
        )

        self.assertIn("Repo script: `./scripts/skills/run-imported-skill.sh cf-edit`", rendered)
        self.assertIn("Windows launcher: `./scripts/skills/run-imported-skill.ps1 cf-edit`", rendered)
        self.assertIn("```powershell\n./scripts/skills/run-imported-skill.ps1 cf-edit --help", rendered)


    def test_claude_mirror_copies_source_and_keeps_owned_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / ".agents/skills/alpha"
            (source / "references").mkdir(parents=True)
            (source / "SKILL.md").write_text("---\nname: alpha\ndescription: test\n---\n", encoding="utf-8")
            (source / "references/note.md").write_text("note", encoding="utf-8")
            claude = root / ".claude/skills"
            (claude / "stale").mkdir(parents=True)
            (claude / "stale/SKILL.md").write_text("old", encoding="utf-8")
            (claude / "openspec-apply-change").mkdir()
            (claude / "openspec-apply-change/SKILL.md").write_text("openspec", encoding="utf-8")
            (claude / "README.md").write_text("readme", encoding="utf-8")

            self.assertEqual(_mirror_claude_skills(root, check=True), [".claude/skills/alpha", ".claude/skills/stale"])
            self.assertTrue((claude / "stale").is_dir())

            _mirror_claude_skills(root, check=False)

            self.assertEqual((claude / "alpha/references/note.md").read_text(encoding="utf-8"), "note")
            self.assertFalse((claude / "stale").exists())
            self.assertEqual((claude / "openspec-apply-change/SKILL.md").read_text(encoding="utf-8"), "openspec")
            self.assertEqual((claude / "README.md").read_text(encoding="utf-8"), "readme")
            self.assertEqual(_mirror_claude_skills(root, check=True), [])

            (source / "SKILL.md").write_text("---\nname: alpha\ndescription: changed\n---\n", encoding="utf-8")
            self.assertEqual(_mirror_claude_skills(root, check=True), [".claude/skills/alpha"])

if __name__ == "__main__":
    unittest.main()
