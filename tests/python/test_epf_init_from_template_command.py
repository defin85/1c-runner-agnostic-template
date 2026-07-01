from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.python.common import CommandError
from scripts.python.epf_templates import init_epf_from_template


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ROOT = ROOT / "src" / "epf" / "_templates" / "TemplateSyncAsyncProcessor"
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def test_init_epf_from_template_copies_renames_and_rekeys_tree(tmp_path: Path) -> None:
    output_root = tmp_path / "epf"
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

    assert result == 0
    target = output_root / name
    assert (target / f"{name}.xml").is_file()
    assert (target / name / "Ext" / "ObjectModule.bsl").is_file()
    assert (target / name / "Forms" / "Форма" / "Ext" / "Form" / "Module.bsl").is_file()

    copied_text = "\n".join(read_text(path) for path in target.rglob("*") if path.is_file())
    assert "TemplateSyncAsyncProcessor" not in copied_text
    assert f"<Name>{name}</Name>" in copied_text
    assert 'РегистрационныеДанные.Вставить("Информация", "Моя тестовая обработка");' in copied_text
    assert 'РегистрационныеДанные.Вставить("Версия", "2.3");' in copied_text
    assert "ДополнительнаяОбработкаСсылка" in copied_text

    source_text = "\n".join(read_text(path) for path in TEMPLATE_ROOT.rglob("*") if path.is_file())
    assert set(UUID_RE.findall(source_text)).isdisjoint(set(UUID_RE.findall(copied_text)))


def test_init_epf_from_template_refuses_existing_target(tmp_path: Path) -> None:
    output_root = tmp_path / "epf"
    target = output_root / "ExistingProcessor"
    target.mkdir(parents=True)

    with pytest.raises(CommandError, match="already exists"):
        init_epf_from_template(["--template", "sync", "--name", "ExistingProcessor", "--output-root", str(output_root)])

