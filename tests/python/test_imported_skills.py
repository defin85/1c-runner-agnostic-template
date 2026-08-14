from __future__ import annotations

import json
import unittest

from scripts.python.imported_skills import _render_agents_skill


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


if __name__ == "__main__":
    unittest.main()
