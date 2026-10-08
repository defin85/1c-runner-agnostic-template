from __future__ import annotations

import re
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from scripts.python.cfe_templates import init_cfe_from_template
from scripts.python.common import CommandError

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ROOT = ROOT / "src" / "cfe" / "_templates" / "TemplatePatchExtension"
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def rekeyed_uuids(text: str) -> set[str]:
    text = re.sub(r"<xr:ClassId>[^<]+</xr:ClassId>", "", text)
    return set(UUID_RE.findall(text))


class InitCfeFromTemplateTest(unittest.TestCase):
    def test_init_cfe_from_template_copies_renames_and_rekeys_tree(self) -> None:
        tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        output_root = tmp_path / "cfe"
        name = "МоеТестовоеРасширение"

        with redirect_stdout(StringIO()):
            result = init_cfe_from_template(
                [
                    "--template",
                    "patch",
                    "--name",
                    name,
                    "--synonym",
                    "Мое тестовое расширение",
                    "--version",
                    "2.3.4.5",
                    "--language-uuid",
                    "db4a9ccb-9ef5-4b3c-8577-b6fe5db1b62e",
                    "--output-root",
                    str(output_root),
                ]
            )

        assert result == 0
        target = output_root / name
        assert (target / "Configuration.xml").is_file()
        assert (target / "Languages" / "Русский.xml").is_file()
        assert (target / "Roles" / f"{name}_ОсновнаяРоль.xml").is_file()
        assert (target / "CommonModules" / f"ОбновлениеИнформационнойБазы{name}.xml").is_file()
        assert (target / "CommonModules" / f"ОбновлениеИнформационнойБазы{name}" / "Ext" / "Module.bsl").is_file()
        assert not (target / "Roles" / "TemplatePatchExtension_ОсновнаяРоль.xml").exists()
        assert not (target / "CommonModules" / "ОбновлениеИнформационнойБазыTemplatePatchExtension.xml").exists()

        copied_text = "\n".join(
            read_text(path) for path in target.rglob("*") if path.is_file() and path.suffix.lower() != ".bsl"
        )
        assert "TemplatePatchExtension" not in copied_text
        assert f"<Name>{name}</Name>" in copied_text
        assert f"<Name>{name}_ОсновнаяРоль</Name>" in copied_text
        assert f"<Role>{name}_ОсновнаяРоль</Role>" in copied_text
        assert f"Role.{name}_ОсновнаяРоль" in copied_text
        assert "<v8:content>Мое тестовое расширение</v8:content>" in copied_text
        assert "<Version>2.3.4.5</Version>" in copied_text
        assert (
            "<ExtendedConfigurationObject>db4a9ccb-9ef5-4b3c-8577-b6fe5db1b62e</ExtendedConfigurationObject>"
            in copied_text
        )

        source_text = "\n".join(
            read_text(path) for path in TEMPLATE_ROOT.rglob("*") if path.is_file() and path.suffix.lower() != ".bsl"
        )
        assert rekeyed_uuids(source_text).isdisjoint(rekeyed_uuids(copied_text))

    def test_init_cfe_from_template_keeps_empty_language_uuid_without_target_binding(self) -> None:
        tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        output_root = tmp_path / "cfe"
        name = "NoTargetBindingExtension"

        with redirect_stdout(StringIO()):
            init_cfe_from_template(["--template", "custom", "--name", name, "--output-root", str(output_root)])

        language_xml = read_text(output_root / name / "Languages" / "Русский.xml")
        assert (
            "<ExtendedConfigurationObject>00000000-0000-0000-0000-000000000000</ExtendedConfigurationObject>"
            in language_xml
        )

    def test_init_cfe_from_template_refuses_existing_target(self) -> None:
        tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        output_root = tmp_path / "cfe"
        target = output_root / "ExistingExtension"
        target.mkdir(parents=True)

        with self.assertRaisesRegex(CommandError, "already exists"):
            init_cfe_from_template(
                ["--template", "custom", "--name", "ExistingExtension", "--output-root", str(output_root)]
            )
