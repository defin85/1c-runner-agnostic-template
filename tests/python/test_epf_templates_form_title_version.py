from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_ROOT = ROOT / "src" / "epf" / "_templates"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def routine_body(text: str, name: str) -> str:
    match = re.search(rf"(Функция|Процедура)\s+{re.escape(name)}\b(.*?)Конец(Функции|Процедуры)", text, re.S)
    if match is None:
        raise AssertionError(f"Не найдена функция/процедура {name}")
    return match.group(2)


def template_roots() -> list[Path]:
    return [
        TEMPLATES_ROOT / "TemplateSyncProcessor" / "TemplateSyncProcessor",
        TEMPLATES_ROOT / "TemplateSyncAsyncProcessor" / "TemplateSyncAsyncProcessor",
    ]


def test_epf_templates_show_processing_version_in_form_title() -> None:
    missing: list[str] = []

    for template_root in template_roots():
        object_module = read_text(template_root / "Ext" / "ObjectModule.bsl")
        form_module = read_text(template_root / "Forms" / "Форма" / "Ext" / "Form" / "Module.bsl")

        registration_body = routine_body(object_module, "СведенияОВнешнейОбработке")
        create_body = routine_body(form_module, "ПриСозданииНаСервере")

        required_fragments = (
            'РегистрационныеДанные.Вставить("Версия", "1.0");',
            'РегистрационныеДанные.Вставить("Информация"',
            'Обработка = РеквизитФормыВЗначение("Объект");',
            "СведенияОбработки = Обработка.СведенияОВнешнейОбработке();",
            'Заголовок = СведенияОбработки.Информация + " (версия " + СведенияОбработки.Версия + ")";',
        )
        combined = registration_body + create_body
        for fragment in required_fragments:
            if fragment not in combined:
                missing.append(f"{template_root.relative_to(ROOT)}: {fragment}")

    assert missing == []
