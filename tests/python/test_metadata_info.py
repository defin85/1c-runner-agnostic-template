"""Inspect preserves the imported reports without executing their CLI in production."""

import tests.python.metadata_test_support  # noqa: F401, I001 — runs first: skips the module without pytest, lxml, jsonschema
from typing import Any
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import lxml.etree as etree

from scripts.python import metadata as editor, metadata_create as create, metadata_info
from scripts.python import metadata_object_ops as objects


ROOT = Path(__file__).parents[2]
ROOT_UUID = "280179ba-92e8-47b4-b0b2-e9bcece0df19"
# Kinds with hand-derived legacy expectations; newer kinds are covered separately.
LEGACY_KINDS = tuple(kind for kind in create.KINDS if kind not in {"CommonCommand", "Subsystem"})


def sample(tmp_path, kind="Catalog"):
    definition: dict[str, Any] = {"type": kind, "name": "Проверка", "synonym": "Заголовок <&>"}
    if kind in objects.ADD_OWNERS["attributes"]:
        definition["attributes"] = [
            {"name": "Партнер", "type": "CatalogRef.Партнеры", "flags": ["req"]},
            {"name": "Описание", "type": "String(20)"},
        ]
    if kind in objects.ADD_OWNERS["tabularSections"]:
        definition["tabularSections"] = [{"name": "Строки", "attributes": [{"name": "Сумма", "type": "Number(15,2)"}]}]
    if kind == "Enum":
        definition["values"] = [{"name": "Первое", "synonym": "Первый вариант"}]
    if kind in objects.REGISTER_KINDS:
        definition.update(
            dimensions=[{"name": "Аналитика", "type": "CatalogRef.Партнеры"}],
            resources=[{"name": "Сумма", "type": "Number(15,2)"}],
        )
    target = tmp_path / "source"
    target.mkdir()
    data = create.render_object(definition, ROOT_UUID, {})
    path = target / objects.borrow.DIRECTORIES[kind] / "Проверка.xml"
    path.parent.mkdir()
    path.write_bytes(data)
    config = etree.Element(f"{{{editor.MD}}}MetaDataObject", nsmap={None: editor.MD}, version="2.17")
    configuration = etree.SubElement(config, f"{{{editor.MD}}}Configuration", uuid=ROOT_UUID)
    props = etree.SubElement(configuration, f"{{{editor.MD}}}Properties")
    etree.SubElement(props, f"{{{editor.MD}}}Name").text = "Тест"
    children = etree.SubElement(configuration, f"{{{editor.MD}}}ChildObjects")
    etree.SubElement(children, f"{{{editor.MD}}}{kind}").text = "Проверка"
    (target / "Configuration.xml").write_bytes(etree.tostring(config))
    return target, kind + ".Проверка", path


@pytest.mark.parametrize("kind", LEGACY_KINDS)
@pytest.mark.parametrize("mode", ["brief", "overview", "full"])
def test_report_matches_explicit_report(tmp_path, kind, mode):
    target, logical, path = sample(tmp_path, kind)
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    expected = json.loads((ROOT / "tests/fixtures/metadata-info/object-reports.json").read_text(encoding="utf-8"))
    assert set(expected) == set(LEGACY_KINDS)
    assert set(expected[kind]) == {"brief", "overview", "full"}
    result = editor.inspect_object(editor.Snapshot(target), logical, mode, limit=0)
    assert result["report"]["lines"] == expected[kind][mode]
    assert result["report"]["nextOffset"] is None
    assert result["object"] == logical
    assert result["uuid"] == editor.identity(editor.metadata(path.read_bytes(), kind))
    assert result["operationChecks"] == "not-run"
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


@pytest.mark.parametrize("mode", ["brief", "overview", "full"])
def test_common_command_report_is_title_only(tmp_path, mode):
    target, logical, _ = sample(tmp_path, "CommonCommand")
    result = editor.inspect_object(editor.Snapshot(target), logical, mode, limit=0)
    assert result["report"]["lines"] == ['=== CommonCommand: Проверка — "Заголовок <&>" ===']


@pytest.mark.parametrize(
    "kind,name,expected",
    [
        (
            "Catalog",
            "Партнер",
            [
                "Реквизит: Партнер",
                "  Тип: СправочникСсылка.Партнеры",
                "  Обязательный: да",
                "  Индексирование: нет",
                "  Значение заполнения: —",
            ],
        ),
        ("Catalog", "Строки", ["ТЧ: Строки (1 колонка):", "  Сумма        Число(15,2)"]),
        (
            "InformationRegister",
            "Аналитика",
            [
                "Измерение: Аналитика",
                "  Тип: СправочникСсылка.Партнеры",
                "  Обязательный: нет",
                "  Индексирование: нет",
                "  Значение заполнения: —",
                "  Ведущее: нет",
                "  Основной отбор: нет",
            ],
        ),
        ("Enum", "Первое", ["Значение перечисления: Первое", '  Синоним: "Первый вариант"']),
    ],
)
def test_drill_matches_explicit_report(tmp_path, kind, name, expected):
    # Fixed expectations from reading the former meta-info drill-down rules.
    target, logical, _ = sample(tmp_path, kind)
    report = editor.inspect_object(editor.Snapshot(target), logical, name=name)["report"]
    assert report["lines"] == expected


def test_inspect_cli_pagination_and_no_legacy(tmp_path, monkeypatch, capsys):
    target, logical, _ = sample(tmp_path)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Legacy execution forbidden")

    monkeypatch.setattr(subprocess, "run", forbidden)
    complete = editor.inspect_object(editor.Snapshot(target), logical, limit=0)
    assert any(item["object"].endswith(".TabularSection.Строки.Attribute.Сумма") for item in complete["members"])
    assert any(item["value"] == "CatalogRef.Партнеры" for item in complete["dependencies"]["items"])
    assert complete["dependencies"]["resolved"] is False
    reconstructed = []
    offset = 0
    while offset is not None:
        assert (
            editor.main(
                ["inspect", "--root", str(target), "--object", logical, "--limit", "2", "--offset", str(offset)]
            )
            == 0
        )
        output = capsys.readouterr()
        assert output.err == "" and len(output.out.splitlines()) == 1
        result = json.loads(output.out)
        assert result["status"] == "inspected"
        assert result["checks"] == {"platform": "not-run", "runtime": "not-run"}
        report = result["changes"]["report"]
        reconstructed.extend(report["lines"])
        offset = report["nextOffset"]
    assert reconstructed == complete["report"]["lines"]
    assert editor.inspect_object(editor.Snapshot(target), logical, offset=1000)["report"]["lines"] == []


@pytest.mark.parametrize("options", [{"limit": -1}, {"offset": -1}, {"name": "НеСуществует"}, {"mode": "unknown"}])
def test_inspect_options_rejected(tmp_path, options):
    target, logical, _ = sample(tmp_path)
    with pytest.raises(editor.Rejected):
        editor.inspect_object(editor.Snapshot(target), logical, **options)


def test_report_is_reentrant_and_unknown_drill_rejected(tmp_path):
    _, _, path = sample(tmp_path, "Constant")
    node = editor.metadata(path.read_bytes(), "Constant")
    assert metadata_info.object_report(node) == metadata_info.object_report(node)
    with pytest.raises(ValueError):
        metadata_info.object_report(node, drill_name="НеСуществует")


def test_inspect_output_is_bounded(tmp_path, monkeypatch):
    target, logical, _ = sample(tmp_path)
    monkeypatch.setattr(metadata_info, "object_report", lambda *_args: ["x" * (editor.FILE_LIMIT + 1)])
    with pytest.raises(editor.Rejected, match="output limit"):
        editor.inspect_object(editor.Snapshot(target), logical)


@pytest.mark.parametrize(
    "kind",
    [
        "Constant",
        "Enum",
        "AccumulationRegister",
        "AccountingRegister",
        "CalculationRegister",
        "DocumentJournal",
        "ChartOfCalculationTypes",
    ],
)
def test_inspect_does_not_advertise_unsupported_form_owner(tmp_path, kind):
    target, logical, _ = sample(tmp_path, kind)
    assert "form.create" not in editor.inspect_object(editor.Snapshot(target), logical)["supportedOperations"]


@pytest.mark.parametrize("fixture,kind", [("epf", "ExternalDataProcessor"), ("erf", "ExternalReport")])
def test_inspect_external_root_does_not_advertise_remove(tmp_path, fixture, kind):
    target = tmp_path / "external"
    shutil.copytree(ROOT / "tests/fixtures/managed-form-cli" / fixture, target)
    path = next(target.glob("*.xml"))
    logical = kind + "." + editor.node_name(editor.metadata(path.read_bytes(), kind))
    result = editor.inspect_object(editor.Snapshot(target), logical)
    assert "object.remove" not in result["supportedOperations"]
    assert "form.create" in result["supportedOperations"]


def test_inspect_xml_comment_is_not_a_dependency(tmp_path):
    target, logical, path = sample(tmp_path)
    before = editor.inspect_object(editor.Snapshot(target), logical)
    root = etree.fromstring(path.read_bytes())
    root[0].append(etree.Comment("Комментарий"))
    path.write_bytes(etree.tostring(root))
    assert editor.inspect_object(editor.Snapshot(target), logical) == before


FORM_FIXTURES = [
    ("cf", "CommonForm.Форма"),
    ("own-cfe", "CommonForm.Форма"),
    ("borrowed-cfe", "CommonForm.Форма"),
    ("own-cfe", "DataProcessor.Владелец.Form.Форма"),
    ("epf", "ExternalDataProcessor.ТестоваяОбработка.Form.Форма"),
    ("erf", "ExternalReport.ТестовыйОтчет.Form.Форма"),
]


@pytest.mark.parametrize("fixture,logical", FORM_FIXTURES)
@pytest.mark.parametrize("expand", ["", "*", "Страница", "Первая"])
def test_form_inspect_matches_explicit_report(tmp_path, fixture, logical, expand):
    from scripts.python.metadata_form_compile import render_form
    from scripts.python.metadata_form_ops import form_path

    from .test_metadata_form_compile import rich_definition

    target = tmp_path / "source"
    shutil.copytree(ROOT / "tests/fixtures/managed-form-cli" / fixture, target)
    path = target / form_path(logical)
    original = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    rich = editor.xml_read(render_form(rich_definition()), original.tag)
    for base in original.findall("f:BaseForm", editor.NS):
        rich.append(base)
    path.write_bytes(etree.tostring(rich))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    # Derived by reading the former form-info renderer and rich.xml, not by
    # executing either renderer. Keep the complete report as an independent oracle.
    context = {
        "CommonForm.Форма": "CommonForms",
        "DataProcessor.Владелец.Form.Форма": "DataProcessors.Владелец",
        "ExternalDataProcessor.ТестоваяОбработка.Form.Форма": "ExternalDataProcessor.ТестоваяОбработка",
        "ExternalReport.ТестовыйОтчет.Form.Форма": "ExternalReport.ТестовыйОтчет",
    }[logical]
    marker = " [EXTENSION]" if fixture == "borrowed-cfe" else ""
    expected = [f'=== Form: Форма{marker} — "Проверка & перенос" ({context}) ===']
    expected += """
Properties: Width=100, AutoTitle=false

Events:
  OnOpen -> ПриОткрытии

Elements:
  ├─ [Group:H] Группа
  │ ├─ [Input] Поле -> Текст [title:Текст] {OnChange}
  │ ├─ [Check] Флаг -> Флаг
  │ ├─ [RadioButtonField] Режим -> Режим
  │ ├─ [ProgressBarField] Ход -> Ход
  │ ├─ [Label] Надпись [title:A < B]
  │ ├─ [LabelField] Представление -> Текст
  │ └─ [SpreadSheetDocumentField] Документ -> Документ
  ├─ [Pages] Страницы
  │ └─ [Page] Страница [title:Первая]{page}
  ├─ [CmdBar] Панель
  │ └─ [Popup] Меню [title:Действия]
  │   └─ [Button] Выполнить -> Выполнить [cmd]
  ├─ [Picture] Картинка
  ├─ [PicField] ПолеКартинки -> Картинка
  └─ [Calendar] Календарь -> Дата

Attributes:
   Текст: string(40)
   Флаг: boolean
   Режим: boolean
   Ход: decimal(10,0)
   Документ: mxl:SpreadsheetDocument
   Картинка: Picture
   Дата: date
   Строки: ValueTable [Текст: string(40)]

Parameters:
  Ключ: string(40) (key)

Commands:
  Выполнить -> ВыполнитьКоманду""".replace(
        "{page}",
        (
            "\n  │   └─ [Table] Таблица -> Строки\n  │     └─ [Input] Колонка -> Строки.Текст"
            if expand
            else " (1 items)"
        ),
    ).splitlines()
    if fixture == "borrowed-cfe":
        expected += ["", "BaseForm: present (version 2.17)"]
    if not expand:
        expected += ["", "Hint: use --expand <name> to expand a collapsed section, --expand * for all"]
    result = editor.inspect_form(editor.Snapshot(target), logical, expand, limit=0)
    assert result["report"]["lines"] == expected
    assert any(item["name"] == "Текст" for item in result["members"])
    assert any(item["value"] == "ВыполнитьКоманду" for item in result["dependencies"]["items"])
    assert result["dependencies"]["resolved"] is False
    assert result["baseLink"] == ("not-checked" if fixture == "borrowed-cfe" else "not-applicable")
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


def test_borrowed_form_inspection_does_not_relax_mutation_context(tmp_path):
    target = tmp_path / "source"
    shutil.copytree(ROOT / "tests/fixtures/managed-form-cli/borrowed-cfe", target)
    result = editor.inspect_form(editor.Snapshot(target), "CommonForm.Форма")
    assert result["baseLink"] == "not-checked"
    with pytest.raises(editor.Rejected, match="base-root"):
        editor.Snapshot(target, "CommonForms/Форма/Ext/Form.xml")


def test_form_inspect_does_not_read_bsl(tmp_path, monkeypatch):
    target = tmp_path / "source"
    shutil.copytree(ROOT / "tests/fixtures/managed-form-cli/cf", target)
    read = editor.Snapshot.read

    def without_bsl(self, alias, path, **kwargs):
        assert not path.endswith(".bsl")
        return read(self, alias, path, **kwargs)

    monkeypatch.setattr(editor.Snapshot, "read", without_bsl)
    assert editor.inspect_form(editor.Snapshot(target), "CommonForm.Форма")["report"]["lines"]


def test_form_inspect_public_cli_and_pagination(tmp_path, capsys, monkeypatch):
    target = tmp_path / "source"
    shutil.copytree(ROOT / "tests/fixtures/managed-form-cli/cf", target)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("No legacy execution")

    monkeypatch.setattr(subprocess, "run", forbidden)
    assert (
        editor.main(["inspect", "--root", str(target), "--object", "CommonForm.Форма", "--expand", "*", "--limit", "3"])
        == 0
    )
    output = capsys.readouterr()
    assert output.err == "" and len(output.out.splitlines()) == 1
    result = json.loads(output.out)
    assert result["checks"] == {"platform": "not-run", "runtime": "not-run"}
    assert result["changes"]["report"]["nextOffset"] == 3
    all_lines = editor.inspect_form(editor.Snapshot(target), "CommonForm.Форма", "*", limit=0)["report"]["lines"]
    rest = editor.inspect_form(editor.Snapshot(target), "CommonForm.Форма", "*", limit=0, offset=3)["report"]["lines"]
    assert result["changes"]["report"]["lines"] + rest == all_lines


@pytest.mark.parametrize("fault", ["version", "descriptor-version", "owner-version", "external-kind"])
def test_form_inspect_rejects_wrong_context(tmp_path, fault):
    target = tmp_path / "source"
    shutil.copytree(ROOT / "tests/fixtures/managed-form-cli/epf", target)
    logical = "ExternalDataProcessor.ТестоваяОбработка.Form.Форма"
    if fault == "external-kind":
        logical = logical.replace("ExternalDataProcessor", "ExternalReport")
    else:
        relative = {
            "version": "ТестоваяОбработка/Forms/Форма/Ext/Form.xml",
            "descriptor-version": "ТестоваяОбработка/Forms/Форма.xml",
            "owner-version": "ТестоваяОбработка.xml",
        }[fault]
        path = target / relative
        tree = etree.fromstring(path.read_bytes())
        tree.set("version", "9.99")
        path.write_bytes(etree.tostring(tree))
    with pytest.raises(editor.Rejected):
        editor.inspect_form(editor.Snapshot(target), logical)
