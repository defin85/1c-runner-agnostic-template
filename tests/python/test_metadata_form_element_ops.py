"""Element-level form edits (E1-E6, E10): only touched XML nodes change.

These tests check the editor's own XML output and refusals. They make no
claim about platform acceptance: checks.platform/runtime stay not-run.
"""

import tests.python.metadata_test_support  # noqa: F401, I001 — runs first: skips the module without pytest, lxml, jsonschema
import copy
import json
from pathlib import Path
import shutil

import lxml.etree as etree
import pytest

from scripts.python import metadata as editor, metadata_form_ops as forms, metadata_validate
from scripts.python.metadata_form_compile import render_form
from tests.python.test_metadata_form_compile import rich_definition


FIXTURES = Path(__file__).parents[1] / "fixtures/managed-form-cli"
FORM = "CommonForms/Форма/Ext/Form.xml"
TARGET = "CommonForm.Форма"


def prepare(tmp_path, layout="own-cfe", rich=False):
    target = tmp_path / "target"
    shutil.copytree(FIXTURES / layout, target)
    if rich:
        (target / FORM).write_bytes(render_form(rich_definition()))
    return target


def payload(*ops):
    return {
        "schemaVersion": 1,
        "operations": [{"op": op, "target": TARGET, "parameters": parameters} for op, parameters in ops],
    }


def plan(target, *ops):
    return editor.plan_make(editor.Snapshot(target), payload(*ops))


def run(target, *ops):
    result = plan(target, *ops)
    assert editor.apply(target, None, result) == "applied"
    return result


def files(target):
    return {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}


def rejected(target, code, *ops):
    before = files(target)
    with pytest.raises(editor.Rejected) as caught:
        plan(target, *ops)
    assert caught.value.code == code
    assert files(target) == before
    return str(caught.value)


def changed(result):
    return [line for line in result["diff"].splitlines() if line[:1] in "+-" and not line.startswith(("+++", "---"))]


def form(target):
    return etree.parse(str(target / FORM)).getroot()


def verify_code(target):
    return editor.verify_objects(editor.Snapshot(target), [TARGET])["code"]


def element_ids(root):
    return [node.get("id") for node in editor.working_nodes(root) if node.get("id") is not None]


# --- E1 form.set-properties -------------------------------------------------


def test_set_visible_is_one_line_and_null_restores_bytes(tmp_path):
    target = prepare(tmp_path)
    original = (target / FORM).read_bytes()
    added = run(target, ("form.set-properties", {"element": "Existing", "properties": {"Visible": False}}))
    assert changed(added) == ["+\t\t\t\t\t<Visible>false</Visible>"]
    toggled = run(target, ("form.set-properties", {"element": "Existing", "properties": {"Visible": True}}))
    assert changed(toggled) == ["-\t\t\t\t\t<Visible>false</Visible>", "+\t\t\t\t\t<Visible>true</Visible>"]
    run(target, ("form.set-properties", {"element": "Existing", "properties": {"Visible": None}}))
    # BOM, declaration spelling, EOL and indentation survive the round trip.
    assert (target / FORM).read_bytes() == original
    assert verify_code(target) == 0


def test_structured_values_multilingual_color_font_picture(tmp_path):
    target = prepare(tmp_path, rich=True)
    run(
        target,
        (
            "form.set-properties",
            {
                "element": "Надпись",
                "properties": {
                    "TextColor": "style:ПоясняющийТекст",
                    "Font": {"ref": "style:ШрифтВажнойНадписи", "bold": True},
                    "ToolTip": {"ru": "Подсказка", "en": "Hint"},
                },
            },
        ),
        (
            "form.set-properties",
            {"element": "Выполнить", "properties": {"Picture": "StdPicture.Execute", "BackColor": "#A0B1C2"}},
        ),
        ("form.set-properties", {"properties": {"Title": "Новый заголовок"}}),
    )
    root = form(target)
    label = root.find(".//f:LabelDecoration[@name='Надпись']", editor.NS)
    assert label.findtext("f:TextColor", namespaces=editor.NS) == "style:ПоясняющийТекст"
    assert label.find("f:Font", editor.NS).attrib == {
        "ref": "style:ШрифтВажнойНадписи",
        "bold": "true",
        "kind": "StyleItem",
    }
    assert [
        item.findtext("v8:lang", namespaces=editor.NS) for item in label.findall("f:ToolTip/v8:item", editor.NS)
    ] == ["ru", "en"]
    button = root.find(".//f:Button[@name='Выполнить']", editor.NS)
    assert button.findtext("f:Picture/xr:Ref", namespaces={**editor.NS, "xr": forms.XR}) == "StdPicture.Execute"
    assert root.findtext("f:Title/v8:item/v8:content", namespaces=editor.NS) == "Новый заголовок"
    assert verify_code(target) == 0


@pytest.mark.parametrize(
    ("element", "properties", "code", "named"),
    [
        ("Existing", {"Unknown": True}, 2, "Unknown"),
        ("Группа", {"Group": "Diagonal"}, 2, "Group"),
        ("Existing", {"TextColor": "red"}, 2, "TextColor"),
        ("Existing", {"name": "Другое"}, 2, "name"),
        ("Группа", {"ChildItems": []}, 2, "ChildItems"),
    ],
)
def test_set_properties_rejections_name_the_property(tmp_path, element, properties, code, named):
    target = prepare(tmp_path)
    message = rejected(target, code, ("form.set-properties", {"element": element, "properties": properties}))
    assert named in message


@pytest.mark.parametrize("prop", ["ChoiceList", "CommandSet"])
def test_choice_list_and_tables_are_rejected_with_name(tmp_path, prop):
    target = prepare(tmp_path, rich=True)
    assert prop in rejected(target, 2, ("form.set-properties", {"element": "Поле", "properties": {prop: []}}))


def test_cli_prints_rejected_property_name(tmp_path, capsys):
    target = prepare(tmp_path)
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(payload(("form.set-properties", {"element": "Existing", "properties": {"Nonexistent": 1}}))),
        encoding="utf-8",
    )
    code = editor.main(["plan", "--root", str(target), "--request", str(request), "--out", str(tmp_path / "plan.json")])
    result = json.loads(capsys.readouterr().out)
    assert code == 2 and result["error"]["code"] == 2
    assert "Nonexistent" in result["error"]["message"]


# --- AvailableTypes (ДоступныеТипы поля ввода, не ОграничениеТипа) ---------------


def available_types(target, element):
    field = form(target).find(f".//f:InputField[@name='{element}']", editor.NS)
    return [node.text for node in field.findall("f:AvailableTypes/v8:Type", editor.NS)]


def test_available_types_round_trip_touches_only_the_restriction(tmp_path):
    target = prepare(tmp_path, rich=True)
    original = (target / FORM).read_bytes()
    ids = element_ids(form(target))
    added = run(target, ("form.set-properties", {"element": "Поле", "properties": {"AvailableTypes": "boolean"}}))
    lines = changed(added)
    assert [line.replace("\t", "") for line in lines] == [
        "+<AvailableTypes>",
        "+<v8:Type>xs:boolean</v8:Type>",
        "+</AvailableTypes>",
    ]
    assert available_types(target, "Поле") == ["xs:boolean"]
    assert element_ids(form(target)) == ids
    assert verify_code(target) == 0
    # The same restriction again is a no-op, a list spelling gives the same node.
    assert (
        changed(
            plan(target, ("form.set-properties", {"element": "Поле", "properties": {"AvailableTypes": ["boolean"]}}))
        )
        == []
    )
    run(target, ("form.set-properties", {"element": "Поле", "properties": {"AvailableTypes": None}}))
    assert (target / FORM).read_bytes() == original


def test_available_types_several_types_and_replacement(tmp_path):
    target = prepare(tmp_path, rich=True)
    run(target, ("form.set-properties", {"element": "Поле", "properties": {"AvailableTypes": "boolean | string(10)"}}))
    assert available_types(target, "Поле") == ["xs:boolean", "xs:string"]
    replaced = run(target, ("form.set-properties", {"element": "Поле", "properties": {"AvailableTypes": ["boolean"]}}))
    assert changed(replaced) and all(line.startswith("-") for line in changed(replaced))
    assert available_types(target, "Поле") == ["xs:boolean"]
    assert verify_code(target) == 0


@pytest.mark.parametrize("spelling", ["CatalogRef.ВидыРасчетов", "cfg:CatalogRef.ВидыРасчетов"])
def test_available_types_reference_requires_the_object_in_the_extension(tmp_path, spelling):
    target = prepare(tmp_path, rich=True)
    message = rejected(
        target, 3, ("form.set-properties", {"element": "Поле", "properties": {"AvailableTypes": spelling}})
    )
    assert "Catalog.ВидыРасчетов" in message


@pytest.mark.parametrize("value", ["", [], ["CatalogRef.<Имя>"], 5])
def test_available_types_invalid_spelling_is_rejected_with_name(tmp_path, value):
    target = prepare(tmp_path, rich=True)
    assert "AvailableTypes" in rejected(
        target, 2, ("form.set-properties", {"element": "Поле", "properties": {"AvailableTypes": value}})
    )


# --- borrowed forms: BaseForm nodes are read-only -----------------------------


def borrowed(tmp_path):
    target = prepare(tmp_path, "borrowed-cfe")
    base = tmp_path / "base"
    shutil.copytree(FIXTURES / "cf", base)
    # The exact base recorded in the fixture's BaseForm (see test_managed_form.clone).
    recorded = form(target).find("f:BaseForm", editor.NS)
    root = etree.fromstring((base / FORM).read_bytes())
    root[:] = [copy.deepcopy(child) for child in recorded]
    (base / FORM).write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    return target, ("form.borrow", {"baseRoot": str(base)})


@pytest.mark.parametrize(
    "operation",
    [
        ("form.set-properties", {"element": "Existing", "properties": {"Visible": False}}),
        ("form.move-element", {"element": "Existing", "into": "ТолькоПросмотрГруппа"}),
        ("form.remove-element", {"element": "Группа"}),
        ("form.set-attribute", {"name": "Текст", "type": "string(10)"}),
        ("form.set-attribute", {"name": "Текст", "remove": True}),
    ],
)
def test_borrowed_base_nodes_are_rejected(tmp_path, operation):
    target, borrow = borrowed(tmp_path)
    rejected(target, 3, borrow, operation)


def test_borrowed_own_element_is_editable_and_base_kept(tmp_path):
    target, borrow = borrowed(tmp_path)
    base_before = etree.tostring(form(target).find("f:BaseForm", editor.NS))
    run(target, borrow, ("form.set-properties", {"element": "ТолькоПросмотрГруппа", "properties": {"Visible": False}}))
    root = form(target)
    assert root.findtext(".//f:UsualGroup[@name='ТолькоПросмотрГруппа']/f:Visible", namespaces=editor.NS) == "false"
    assert etree.tostring(root.find("f:BaseForm", editor.NS)) == base_before


def test_borrowed_form_without_base_context_names_the_cause(tmp_path, capsys):
    target, _ = borrowed(tmp_path)
    message = rejected(
        target, 3, ("form.set-properties", {"element": "ТолькоПросмотрГруппа", "properties": {"Visible": False}})
    )
    assert "include form borrow" in message and TARGET in message
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            payload(("form.set-properties", {"element": "ТолькоПросмотрГруппа", "properties": {"Visible": False}}))
        ),
        encoding="utf-8",
    )
    code = editor.main(["plan", "--root", str(target), "--request", str(request), "--out", str(tmp_path / "plan.json")])
    result = json.loads(capsys.readouterr().out)
    assert code == 3 and "include form borrow" in result["error"]["message"]


@pytest.mark.parametrize(
    "operation",
    [
        ("form.edit", {"definition": {"elements": [{"label": "Надпись"}]}}),
        ("form.add-input", {"name": "Поле", "attribute": "Текст", "title": "Поле", "parent": "ТолькоПросмотрГруппа"}),
    ],
)
def test_borrowed_form_edit_and_add_input_without_base_name_the_target(tmp_path, operation):
    target, _ = borrowed(tmp_path)
    message = rejected(target, 3, operation)
    assert "include form borrow" in message and TARGET in message


# --- E2 form.move-element -----------------------------------------------------


def test_button_moves_into_table_command_bar_with_ids(tmp_path):
    target = prepare(tmp_path, rich=True)
    before = form(target)
    button = before.find(".//f:Button[@name='Выполнить']", editor.NS)
    ids = [node.get("id") for node in button.iter() if node.get("id")]
    bar = before.find(".//f:Table[@name='Таблица']/f:AutoCommandBar", editor.NS).get("name")
    run(target, ("form.move-element", {"element": "Выполнить", "into": bar}))
    after = form(target)
    moved = after.find(f".//f:AutoCommandBar[@name='{bar}']/f:ChildItems/f:Button[@name='Выполнить']", editor.NS)
    assert moved is not None
    assert [node.get("id") for node in moved.iter() if node.get("id")] == ids
    assert sorted(element_ids(after)) == sorted(element_ids(before))
    # The emptied popup loses its ChildItems; the rest of the form is untouched.
    assert after.find(".//f:Popup[@name='Меню']/f:ChildItems", editor.NS) is None
    assert verify_code(target) == 0


def test_move_after_and_before_keep_order(tmp_path):
    target = prepare(tmp_path, rich=True)
    run(target, ("form.move-element", {"element": "Флаг", "after": "Документ"}))
    run(target, ("form.move-element", {"element": "Надпись", "before": "Поле"}))
    group = form(target).find(".//f:UsualGroup[@name='Группа']/f:ChildItems", editor.NS)
    names = [child.get("name") for child in group]
    assert names[0] == "Надпись" and names[-1] == "Флаг"
    assert verify_code(target) == 0


@pytest.mark.parametrize(
    ("parameters", "code"),
    [
        ({"element": "Группа", "into": "Группа"}, 2),
        ({"element": "Страницы", "into": "Страница"}, 2),
        ({"element": "Поле", "into": "Меню"}, 2),
        ({"element": "Страница", "into": "Группа"}, 2),
        ({"element": "Поле", "after": "НетТакого"}, 3),
    ],
)
def test_move_rejections_leave_files(tmp_path, parameters, code):
    target = prepare(tmp_path, rich=True)
    rejected(target, code, ("form.move-element", parameters))


# --- E3 form.remove-element ---------------------------------------------------


def test_remove_group_with_two_fields_only_touches_its_subtree(tmp_path):
    target = prepare(tmp_path)
    run(
        target,
        (
            "form.edit",
            {
                "definition": {
                    "into": "ТолькоПросмотрГруппа",
                    "elements": [{"input": "Первое", "path": "Текст"}, {"check": "Второе", "path": "Флаг"}],
                }
            },
        ),
    )
    before = form(target)
    removed = before.find(".//f:UsualGroup[@name='ТолькоПросмотрГруппа']", editor.NS)
    gone = {node.get("name") for node in removed.iter() if node.get("id")}
    result = run(target, ("form.remove-element", {"element": "ТолькоПросмотрГруппа"}))
    assert all(line.startswith("-") for line in changed(result))
    after = form(target)
    assert {node.get("name") for node in editor.working_nodes(after)} == (
        {node.get("name") for node in editor.working_nodes(before)} - gone
    )
    assert verify_code(target) == 0


def test_remove_referenced_by_conditional_appearance_lists_owner(tmp_path):
    target = prepare(tmp_path, rich=True)
    root = form(target)
    appearance = etree.fromstring(
        '<ConditionalAppearance xmlns="http://v8.1c.ru/8.3/xcf/logform"'
        ' xmlns:dcsset="http://v8.1c.ru/8.1/data-composition-system/settings">'
        "<dcsset:item><dcsset:selection><dcsset:item><dcsset:field>Поле</dcsset:field></dcsset:item>"
        "</dcsset:selection></dcsset:item></ConditionalAppearance>"
    )
    root.find("f:Attributes", editor.NS).addprevious(appearance)
    (target / FORM).write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    message = rejected(target, 3, ("form.remove-element", {"element": "Поле"}))
    assert "ConditionalAppearance" in message


def test_remove_button_referenced_by_command_name(tmp_path):
    target = prepare(tmp_path, rich=True)
    root = form(target)
    button = root.find(".//f:Button[@name='Выполнить']", editor.NS)
    button.find("f:CommandName", editor.NS).text = "Form.Item.Таблица.StandardCommand.Add"
    (target / FORM).write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    assert "Выполнить" in rejected(target, 3, ("form.remove-element", {"element": "Таблица"}))


def test_remove_table_referenced_by_detached_addition(tmp_path):
    # Designer places a list's search string outside the table and links it by <AdditionSource><Item>.
    target = prepare(tmp_path, rich=True)
    root = form(target)
    addition = etree.fromstring(
        '<SearchStringAddition xmlns="http://v8.1c.ru/8.3/xcf/logform" name="ПоискТаблицы" id="900">'
        "<AdditionSource><Item>Таблица</Item><Type>SearchStringRepresentation</Type></AdditionSource>"
        '<ContextMenu name="ПоискТаблицыКонтекстноеМеню" id="901"/>'
        '<ExtendedTooltip name="ПоискТаблицыРасширеннаяПодсказка" id="902"/></SearchStringAddition>'
    )
    root.find("f:ChildItems", editor.NS).append(addition)
    (target / FORM).write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    assert "ПоискТаблицы" in rejected(target, 3, ("form.remove-element", {"element": "Таблица"}))


def test_remove_table_referenced_by_current_data_path(tmp_path):
    target = prepare(tmp_path, rich=True)
    root = form(target)
    root.find(".//f:InputField[@name='Поле']/f:DataPath", editor.NS).text = "Items.Таблица.CurrentData.Текст"
    (target / FORM).write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    assert verify_code(target) == 0
    assert "Поле" in rejected(target, 3, ("form.remove-element", {"element": "Таблица"}))


def test_remove_column_referenced_through_current_data_path(tmp_path):
    target = prepare(tmp_path, rich=True)
    run(
        target,
        ("form.remove-element", {"element": "Колонка"}),
        ("form.set-properties", {"element": "Поле", "properties": {"DataPath": "Items.Таблица.CurrentData.Текст"}}),
    )
    message = rejected(
        target, 3, ("form.set-attribute", {"name": "Строки", "columns": [{"name": "Текст", "remove": True}]})
    )
    assert "Поле" in message


def test_current_data_path_resolves_through_the_table(tmp_path):
    target = prepare(tmp_path, rich=True)
    run(
        target,
        ("form.set-properties", {"element": "Поле", "properties": {"DataPath": "Items.Таблица.CurrentData.Текст"}}),
    )
    assert form(target).find(".//f:InputField[@name='Поле']/f:DataPath", editor.NS).text == (
        "Items.Таблица.CurrentData.Текст"
    )
    assert verify_code(target) == 0
    for path in ("Items.Нет.CurrentData.Текст", "Items.Поле.CurrentData.Текст", "Items.Таблица.Текст"):
        message = rejected(target, 3, ("form.set-properties", {"element": "Поле", "properties": {"DataPath": path}}))
        assert "Data path table not found" in message
    root = form(target)
    root.find(".//f:InputField[@name='Поле']/f:DataPath", editor.NS).text = "Items.Нет.CurrentData.Текст"
    (target / FORM).write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    assert verify_code(target) == 4


def test_remove_reports_orphan_handlers_without_touching_module(tmp_path):
    target = prepare(tmp_path, rich=True)
    module = target / "CommonForms/Форма/Ext/Form/Module.bsl"
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text("&НаКлиенте\nПроцедура Изменить(Элемент)\nКонецПроцедуры\n", encoding="utf-8")
    code = module.read_bytes()
    result = run(target, ("form.remove-element", {"element": "Поле"}))
    dependencies = result["pendingDependencies"]
    assert any("Изменить" in item.get("targets", []) for item in dependencies)
    assert module.read_bytes() == code


# --- form.rename-element --------------------------------------------------------


def _duplicate_field(target, selector="f:InputField[@name='Поле']", first_id=900):
    root = form(target)
    copy_node = copy.deepcopy(root.find(".//" + selector, editor.NS))
    for number, part in enumerate(node for node in copy_node.iter() if node.get("id") is not None):
        part.set("id", str(first_id + number))
    root.find("f:ChildItems", editor.NS).append(copy_node)
    (target / FORM).write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    return copy_node.get("id")


def test_rename_repairs_duplicate_element_name_by_id(tmp_path):
    target = prepare(tmp_path, rich=True)
    duplicate = _duplicate_field(target)
    assert "Поле" not in rejected(
        target, 4, ("form.set-properties", {"element": "Поле", "properties": {"Visible": False}})
    )
    rejected(target, 3, ("form.rename-element", {"element": "Поле", "newName": "ПолеКопия"}))
    before = element_ids(form(target))
    result = run(target, ("form.rename-element", {"element": "Поле", "id": int(duplicate), "newName": "ПолеКопия"}))
    assert all("ПолеКопия" in line for line in changed(result) if line.startswith("+<") and "<?xml" not in line)
    root = form(target)
    renamed = root.find(f".//f:InputField[@id='{duplicate}']", editor.NS)
    assert renamed.get("name") == "ПолеКопия"
    assert {part.get("name") for part in renamed if part.get("id")} == {
        "ПолеКопияКонтекстноеМеню",
        "ПолеКопияРасширеннаяПодсказка",
    }
    assert element_ids(root) == before
    assert editor.named(root)
    assert verify_code(target) == 0


def test_rename_rejects_existing_name(tmp_path):
    target = prepare(tmp_path, rich=True)
    rejected(target, 3, ("form.rename-element", {"element": "Поле", "newName": "Таблица"}))


def test_rename_rejects_referenced_element_and_lists_owner(tmp_path):
    target = prepare(tmp_path, rich=True)
    run(
        target,
        ("form.set-properties", {"element": "Поле", "properties": {"DataPath": "Items.Таблица.CurrentData.Текст"}}),
    )
    message = rejected(target, 3, ("form.rename-element", {"element": "Таблица", "newName": "ТаблицаНовая"}))
    assert "Element is referenced by" in message and "Поле" in message


def test_rename_repairs_triple_duplicate_in_two_steps(tmp_path):
    target = prepare(tmp_path, rich=True)
    duplicate = _duplicate_field(target)
    root = form(target)
    third = copy.deepcopy(root.find(f".//f:InputField[@id='{duplicate}']", editor.NS))
    for number, part in enumerate(node for node in third.iter() if node.get("id") is not None):
        part.set("id", str(950 + number))
    root.find("f:ChildItems", editor.NS).append(third)
    (target / FORM).write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    # Other operations still refuse a form with duplicates.
    rejected(target, 4, ("form.set-properties", {"element": "Флаг", "properties": {"Visible": False}}))
    run(target, ("form.rename-element", {"element": "Поле", "id": int(duplicate), "newName": "ПолеКопия"}))
    assert "поле" in editor.duplicate_names(form(target))
    run(target, ("form.rename-element", {"element": "Поле", "id": 950, "newName": "ПолеКопия2"}))
    assert editor.named(form(target))
    assert verify_code(target) == 0


def test_rename_repairs_several_duplicate_names_one_by_one(tmp_path):
    target = prepare(tmp_path, rich=True)
    field = _duplicate_field(target)
    flag = _duplicate_field(target, "f:CheckBoxField[@name='Флаг']", 960)
    rejected(
        target,
        4,
        (
            "form.edit",
            {"definition": {"formEvents": [{"name": "OnCreateAtServer", "handler": "ПриСозданииНаСервере"}]}},
        ),
    )
    run(target, ("form.rename-element", {"element": "Поле", "id": int(field), "newName": "ПолеКопия"}))
    assert editor.duplicate_names(form(target)) == {"флаг", "флагконтекстноеменю"}
    # A rename may not create a new duplicate while others still wait.
    rejected(target, 3, ("form.rename-element", {"element": "Флаг", "id": int(flag), "newName": "ПолеКопия"}))
    run(
        target,
        ("form.rename-element", {"element": "Флаг", "id": int(flag), "newName": "ФлагКопия"}),
        (
            "form.edit",
            {"definition": {"formEvents": [{"name": "OnCreateAtServer", "handler": "ПриСозданииНаСервере"}]}},
        ),
    )
    assert editor.named(form(target))
    assert verify_code(target) == 0


@pytest.mark.parametrize(
    "parameters",
    [
        {"element": "Existing", "newName": "ExistingНовый"},
        {"element": "ТолькоПросмотрГруппа", "newName": "Existing"},
    ],
)
def test_rename_rejects_base_form_names(tmp_path, parameters):
    target, borrow = borrowed(tmp_path)
    assert "Base form element is read-only" in rejected(target, 3, borrow, ("form.rename-element", parameters))


def test_rename_lists_module_for_review_without_touching_it(tmp_path):
    target = prepare(tmp_path, rich=True)
    module = target / "CommonForms/Форма/Ext/Form/Module.bsl"
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text("&НаКлиенте\nПроцедура ПолеПриИзменении(Элемент)\nКонецПроцедуры\n", encoding="utf-8")
    code = module.read_bytes()
    result = run(target, ("form.rename-element", {"element": "Поле", "newName": "ПолеНовое"}))
    assert any(
        item.get("reason") == "bsl-review" and "Поле" in item.get("targets", [])
        for item in result["pendingDependencies"]
    )
    assert module.read_bytes() == code
    assert form(target).find(".//f:InputField[@name='ПолеНовое']", editor.NS) is not None


# --- E4 form.set-attribute ----------------------------------------------------


def test_attribute_type_change_touches_only_type(tmp_path):
    target = prepare(tmp_path)
    result = run(target, ("form.set-attribute", {"name": "Текст", "type": "string(50)"}))
    assert changed(result) == ["-\t\t\t\t\t<v8:Length>100</v8:Length>", "+\t\t\t\t\t<v8:Length>50</v8:Length>"]
    run(target, ("form.set-attribute", {"name": "Число", "type": "string(10) | boolean"}))
    typed = form(target).find("f:Attributes/f:Attribute[@name='Число']/f:Type", editor.NS)
    assert sorted(node.text for node in typed.findall("v8:Type", editor.NS)) == ["xs:boolean", "xs:string"]
    # A reference type to an object absent from the tree is refused, as in form.compile.
    rejected(target, 3, ("form.set-attribute", {"name": "Число", "type": "CatalogRef.Номенклатура"}))
    assert verify_code(target) == 0


def test_attribute_new_with_columns_title_and_flags(tmp_path):
    target = prepare(tmp_path)
    run(
        target,
        (
            "form.set-attribute",
            {
                "name": "Строки",
                "type": "ValueTable",
                "title": {"ru": "Строки", "en": "Rows"},
                "savedData": True,
                "fillChecking": "ShowError",
                "columns": [{"name": "Сумма", "type": "number(15,2)"}],
            },
        ),
    )
    root = form(target)
    attribute = root.find("f:Attributes/f:Attribute[@name='Строки']", editor.NS)
    assert attribute.findtext("f:Columns/f:Column/f:Type/v8:Type", namespaces=editor.NS) == "xs:decimal"
    assert attribute.findtext("f:SavedData", namespaces=editor.NS) == "true"
    run(target, ("form.set-attribute", {"name": "Строки", "columns": [{"name": "Сумма", "remove": True}]}))
    assert form(target).find("f:Attributes/f:Attribute[@name='Строки']/f:Columns/f:Column", editor.NS) is None
    assert verify_code(target) == 0


def test_remove_attribute_bound_to_field_lists_fields(tmp_path):
    target = prepare(tmp_path, rich=True)
    message = rejected(target, 3, ("form.set-attribute", {"name": "Текст", "remove": True}))
    assert "Поле" in message and "Представление" in message


def test_second_main_attribute_is_rejected(tmp_path):
    target = prepare(tmp_path)
    run(target, ("form.set-attribute", {"name": "Число", "main": True}))
    assert "Second main attribute" in rejected(target, 3, ("form.set-attribute", {"name": "Флаг", "main": True}))


def test_unbound_attribute_is_removed(tmp_path):
    target = prepare(tmp_path)
    result = run(target, ("form.set-attribute", {"name": "Дата", "remove": True}))
    assert all(line.startswith("-") for line in changed(result))
    assert form(target).find("f:Attributes/f:Attribute[@name='Дата']", editor.NS) is None


# --- E5 form.set-command ------------------------------------------------------


def test_command_title_change_touches_only_title(tmp_path):
    target = prepare(tmp_path)
    result = run(target, ("form.set-command", {"name": "OldCommand", "title": "Новая команда"}))
    assert changed(result) == [
        "-\t\t\t\t\t<v8:content>Старая команда</v8:content>",
        "+\t\t\t\t\t<v8:content>Новая команда</v8:content>",
    ]


def test_command_new_and_flags_without_module_changes(tmp_path):
    target = prepare(tmp_path)
    before = {path: data for path, data in files(target).items() if path.endswith(".bsl")}
    run(
        target,
        (
            "form.set-command",
            {
                "name": "Выполнить",
                "action": "Выполнить",
                "shortcut": "Ctrl+Enter",
                "representation": "Text",
                "modifiesSavedData": True,
                "currentRowUse": "Use",
            },
        ),
    )
    command = form(target).find("f:Commands/f:Command[@name='Выполнить']", editor.NS)
    assert command.findtext("f:Action", namespaces=editor.NS) == "Выполнить"
    assert command.findtext("f:ModifiesSavedData", namespaces=editor.NS) == "true"
    assert {path: data for path, data in files(target).items() if path.endswith(".bsl")} == before


def test_remove_command_used_by_button_lists_buttons(tmp_path):
    target = prepare(tmp_path, rich=True)
    message = rejected(target, 3, ("form.set-command", {"name": "Выполнить", "remove": True}))
    assert "Выполнить" in message and "ВыполнитьВТаблице" in message


# --- form.remove-event --------------------------------------------------------


def _module(target, text):
    module = target / "CommonForms/Форма/Ext/Form/Module.bsl"
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text(text, encoding="utf-8")
    return module


def test_remove_form_event_touches_only_the_event_and_keeps_module(tmp_path):
    target = prepare(tmp_path, rich=True)
    module = _module(target, "&НаКлиенте\nПроцедура ПриОткрытии(Отказ)\nКонецПроцедуры\n")
    code = module.read_bytes()
    before = form(target)
    result = run(target, ("form.remove-event", {"name": "OnOpen"}))
    assert [line[0] + line[1:].strip() for line in changed(result)] == [
        "-<Events>",
        '-<Event name="OnOpen">ПриОткрытии</Event>',
        "-</Events>",
    ]
    assert any("ПриОткрытии" in item.get("targets", []) for item in result["pendingDependencies"])
    assert module.read_bytes() == code
    after = form(target)
    assert after.find("f:Events", editor.NS) is None
    assert element_ids(after) == element_ids(before)
    assert verify_code(target) == 0
    # Repeating the same request after apply writes nothing.
    assert plan(target, ("form.remove-event", {"name": "OnOpen"}))["writes"] == []


def test_remove_one_of_several_form_events_keeps_the_others(tmp_path):
    target = prepare(tmp_path, rich=True)
    run(
        target,
        (
            "form.edit",
            {"definition": {"formEvents": [{"name": "OnCreateAtServer", "handler": "ПриСозданииНаСервере"}]}},
        ),
    )
    result = run(target, ("form.remove-event", {"name": "OnOpen"}))
    assert [line[0] + line[1:].strip() for line in changed(result)] == ['-<Event name="OnOpen">ПриОткрытии</Event>']
    events = form(target).findall("f:Events/f:Event", editor.NS)
    assert [(node.get("name"), node.text) for node in events] == [("OnCreateAtServer", "ПриСозданииНаСервере")]


def test_remove_element_event_by_element_name(tmp_path):
    target = prepare(tmp_path, rich=True)
    result = run(target, ("form.remove-event", {"name": "OnChange", "element": "Поле"}))
    assert '-<Event name="OnChange">Изменить</Event>' in [line[0] + line[1:].strip() for line in changed(result)]
    field = form(target).find(".//f:InputField[@name='Поле']", editor.NS)
    assert field.find("f:Events", editor.NS) is None
    assert form(target).find("f:Events/f:Event", editor.NS).get("name") == "OnOpen"


def test_remove_event_rejects_unknown_element(tmp_path):
    target = prepare(tmp_path, rich=True)
    rejected(target, 3, ("form.remove-event", {"name": "OnChange", "element": "НетТакого"}))


# --- E6 form.edit: new kinds and before ---------------------------------------


@pytest.mark.parametrize(
    ("into", "description", "tag"),
    [
        ("Группа", {"radio": "Новое", "path": "Текст"}, "RadioButtonField"),
        ("Группа", {"textDocument": "Новое"}, "TextDocumentField"),
        ("Группа", {"spreadsheet": "Новое"}, "SpreadSheetDocumentField"),
        ("Группа", {"formattedDocument": "Новое"}, "FormattedDocumentField"),
        ("Группа", {"chart": "Новое"}, "ChartField"),
        ("Таблица", {"columnGroup": "Новое", "group": "horizontal"}, "ColumnGroup"),
        ("Панель", {"buttonGroup": "Новое"}, "ButtonGroup"),
        ("Группа", {"input": "Новое", "path": "Текст"}, "InputField"),
        ("Группа", {"check": "Новое", "path": "Флаг"}, "CheckBoxField"),
        ("Группа", {"label": "Новое"}, "LabelDecoration"),
        ("Группа", {"picture": "Новое"}, "PictureDecoration"),
        ("Группа", {"group": "vertical", "name": "Новое"}, "UsualGroup"),
    ],
)
def test_edit_creates_each_kind_with_companions_and_unique_ids(tmp_path, into, description, tag):
    target = prepare(tmp_path, rich=True)
    result = run(target, ("form.edit", {"definition": {"into": into, "elements": [description]}}))
    root = form(target)
    node = root.find(f".//f:{tag}[@name='Новое']", editor.NS)
    assert node is not None
    ids = element_ids(root)
    assert len(ids) == len(set(ids))
    report = metadata_validate.form_report(root, "Форма", detailed=True)
    assert report["errors"] == report["warnings"] == 0
    assert verify_code(target) == 0
    # New lines are indented like their siblings; nothing else moves.
    assert all(line.startswith("+") for line in changed(result))
    assert all(line[1:].startswith("\t") for line in changed(result))


def test_edit_before_keeps_listed_order(tmp_path):
    target = prepare(tmp_path)
    run(
        target,
        ("form.edit", {"definition": {"before": "Existing", "elements": [{"label": "Первая"}, {"label": "Вторая"}]}}),
    )
    group = form(target).find(".//f:UsualGroup[@name='Группа']/f:ChildItems", editor.NS)
    assert [child.get("name") for child in group] == ["Первая", "Вторая", "Existing"]
    assert verify_code(target) == 0


def test_edit_rejects_kind_the_container_cannot_hold(tmp_path):
    target = prepare(tmp_path)
    message = rejected(
        target,
        2,
        (
            "form.edit",
            {"definition": {"into": "Группа", "elements": [{"columnGroup": "Колонки", "group": "horizontal"}]}},
        ),
    )
    assert "ColumnGroup" in message


# --- E10 verify and inspect ---------------------------------------------------


def break_form(root, fault):
    if fault == "element-id":
        items = root.find("f:ChildItems", editor.NS)
        items[1].set("id", items[0].get("id"))
    elif fault == "companion":
        node = root.find(".//f:InputField", editor.NS)
        node.remove(node.find("f:ContextMenu", editor.NS))
    elif fault == "datapath":
        root.find(".//f:InputField/f:DataPath", editor.NS).text = "Нет"
    elif fault == "button":
        root.find(".//f:Button[@name='Выполнить']/f:CommandName", editor.NS).text = "Form.Command.Нет"
    elif fault == "event":
        root.find(".//f:InputField/f:Events/f:Event", editor.NS).text = ""
    elif fault == "main":
        for attribute in root.findall("f:Attributes/f:Attribute", editor.NS)[:2]:
            etree.SubElement(attribute, f"{{{editor.FORM}}}MainAttribute").text = "true"
    else:
        root.set("version", "2.99")


@pytest.mark.parametrize("fault", ["element-id", "companion", "datapath", "button", "event", "main", "version"])
def test_verify_returns_code_4_for_each_violation(tmp_path, fault):
    target = prepare(tmp_path, rich=True)
    assert verify_code(target) == 0
    root = form(target)
    break_form(root, fault)
    (target / FORM).write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    assert verify_code(target) == 4


def test_inspect_lists_name_kind_parent_and_data_path(tmp_path):
    target = prepare(tmp_path, rich=True)
    report = editor.inspect_form(editor.Snapshot(target), TARGET)
    elements = report["elements"]
    by_name = {item["name"]: item for item in elements}
    assert by_name["Поле"]["kind"] == "InputField"
    assert by_name["Поле"]["parent"] == "Группа"
    assert by_name["Поле"]["dataPath"] == "Текст"
    assert by_name["Колонка"]["parent"] == "Таблица"
    # As in BslEdit listElements, command bar contents are not part of the item tree.
    assert "ВыполнитьВТаблице" not in by_name
    assert set(forms.ELEMENT_OPERATIONS) <= set(report["supportedOperations"])


# --- form.set-command remove with id: duplicated command ------------------------


def _duplicate_command(target, name="Выполнить", action=None):
    root = form(target)
    commands = root.find("f:Commands", editor.NS)
    original = commands.find(f"f:Command[@name='{name}']", editor.NS)
    copy_node = copy.deepcopy(original)
    copy_node.set("id", str(max(int(node.get("id")) for node in root.iter() if (node.get("id") or "").isdigit()) + 1))
    if action is not None:
        copy_node.find("f:Action", editor.NS).text = action
    commands.append(copy_node)
    (target / FORM).write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    return original.get("id"), copy_node.get("id")


def test_remove_duplicate_command_copy_by_id_keeps_references(tmp_path):
    target = prepare(tmp_path, rich=True)
    kept, duplicate = _duplicate_command(target)
    assert "Ambiguous form command" in rejected(target, 3, ("form.set-command", {"name": "Выполнить", "remove": True}))
    before = element_ids(form(target))
    run(target, ("form.set-command", {"name": "Выполнить", "id": int(duplicate), "remove": True}))
    root = form(target)
    assert [node.get("id") for node in root.findall("f:Commands/f:Command[@name='Выполнить']", editor.NS)] == [kept]
    assert element_ids(root) == before
    assert any((node.text or "").strip() == "Form.Command.Выполнить" for node in root.iter())
    assert verify_code(target) == 0
    # Repeating the request is a no-op: nothing to write, the kept copy is untouched.
    assert (
        plan(target, ("form.set-command", {"name": "Выполнить", "id": int(duplicate), "remove": True}))["writes"] == []
    )


def test_remove_duplicate_command_rejects_differing_copies(tmp_path):
    target = prepare(tmp_path, rich=True)
    _, duplicate = _duplicate_command(target, action="ВыполнитьИначе")
    assert "Duplicate commands differ" in rejected(
        target, 3, ("form.set-command", {"name": "Выполнить", "id": int(duplicate), "remove": True})
    )


def test_command_id_requires_remove_and_a_duplicate(tmp_path):
    target = prepare(tmp_path, rich=True)
    kept = form(target).find("f:Commands/f:Command[@name='Выполнить']", editor.NS).get("id")
    with pytest.raises(editor.Rejected):
        plan(target, ("form.set-command", {"name": "Выполнить", "id": int(kept), "title": "Иначе"}))
    assert "Command is not duplicated" in rejected(
        target, 3, ("form.set-command", {"name": "Выполнить", "id": int(kept), "remove": True})
    )
