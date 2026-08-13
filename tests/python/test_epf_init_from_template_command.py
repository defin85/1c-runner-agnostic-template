from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from scripts.python.common import CommandError
from scripts.python.epf_templates import init_epf_from_template


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ROOT = ROOT / "src" / "epf" / "_templates" / "TemplateSyncAsyncProcessor"
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


class InitEpfFromTemplateTests(unittest.TestCase):
 def test_copies_renames_and_rekeys_tree(self) -> None:
    temporary = tempfile.TemporaryDirectory()
    self.addCleanup(temporary.cleanup)
    output_root = Path(temporary.name) / "epf"
    name = "МояТестоваяОбработка"

    result = init_epf_from_template(
        [
            "--template",
            "sync-async",
            "--name",
            name,
            "--info",
            "Моя тестовая обработка",
            "--version",
            "2.3",
            "--output-root",
            str(output_root),
        ]
    )

    self.assertEqual(result, 0)
    target = output_root / name
    self.assertTrue((target / f"{name}.xml").is_file())
    self.assertTrue((target / name / "Ext" / "ObjectModule.bsl").is_file())
    self.assertTrue((target / name / "Forms" / "Форма" / "Ext" / "Form" / "Module.bsl").is_file())

    copied_text = "\n".join(read_text(path) for path in target.rglob("*") if path.is_file())
    self.assertNotIn("TemplateSyncAsyncProcessor", copied_text)
    self.assertIn(f"<Name>{name}</Name>", copied_text)
    self.assertIn('РегистрационныеДанные.Вставить("Информация", "Моя тестовая обработка");', copied_text)
    self.assertIn('РегистрационныеДанные.Вставить("Версия", "2.3");', copied_text)
    self.assertIn("ДополнительнаяОбработкаСсылка", copied_text)

    source_text = "\n".join(read_text(path) for path in TEMPLATE_ROOT.rglob("*") if path.is_file())
    self.assertTrue(set(UUID_RE.findall(source_text)).isdisjoint(set(UUID_RE.findall(copied_text))))


 def test_refuses_existing_target(self) -> None:
    temporary = tempfile.TemporaryDirectory()
    self.addCleanup(temporary.cleanup)
    output_root = Path(temporary.name) / "epf"
    target = output_root / "ExistingProcessor"
    target.mkdir(parents=True)

    with self.assertRaisesRegex(CommandError, "already exists"):
        init_epf_from_template(["--template", "sync", "--name", "ExistingProcessor", "--output-root", str(output_root)])

