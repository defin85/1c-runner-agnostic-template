"""The transferred pure compiler preserves the former XML contract."""

import tests.python.metadata_test_support  # noqa: F401, I001 — runs first: skips the module without pytest, lxml, jsonschema
import json
import shutil
from pathlib import Path

import lxml.etree as etree
import pytest

from scripts.python import metadata as editor
from scripts.python.metadata_form_compile import render_form
from scripts.python.metadata_form_ops import form_path
from tests.python.test_metadata_object_ops import rename_owner
from tests.python.test_metadata_form_ops import document_form  # noqa: F401 — pytest fixture, requested by parameter name
from tests.python.test_metadata_object_ops import document_roots  # noqa: F401 — pytest fixture, requested by parameter name


GOLDENS = Path(__file__).parents[1] / "fixtures/metadata-form-compile"


@pytest.mark.parametrize("operation", ["form.compile", "form.edit"])
@pytest.mark.parametrize("add_new", [False, True])
def test_merge_allocates_only_new_ids_at_pool_limit(tmp_path, operation, add_new):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/cf", target)
    logical = "CommonForm.Форма"
    path = target / form_path(logical)
    tree = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    old = tree.find("f:Commands/f:Command", editor.NS)
    old.set("id", str(2147483647 - int(add_new)))
    path.write_bytes(etree.tostring(tree))
    commands = [{"name": "OldCommand", "title": "Старая команда", "action": "OldCommand"}]
    if add_new:
        commands.append({"name": "NewCommand", "action": "NewCommand"})
    request = {
        "schemaVersion": 1,
        "operations": [{"op": operation, "target": logical, "parameters": {"definition": {"commands": commands}}}],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    if add_new:
        assert editor.apply(target, None, plan) == "applied"
        result = editor.xml_read(path.read_bytes(), tree.tag)
        assert result.find('f:Commands/f:Command[@name="NewCommand"]', editor.NS).get("id") == "2147483647"
        assert result.find('f:Commands/f:Command[@name="OldCommand"]', editor.NS).get("id") == old.get("id")
    else:
        assert plan["writes"] == []
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []


def rich_definition():
    return {
        "title": "Проверка & перенос",
        "properties": {"width": 100, "autoTitle": False},
        "events": {"OnOpen": "ПриОткрытии"},
        "excludedCommands": ["Form.StandardCommand.Close"],
        "elements": [
            {
                "group": "horizontal",
                "name": "Группа",
                "showTitle": False,
                "children": [
                    {
                        "input": "Поле",
                        "path": "Текст",
                        "title": "Текст:",
                        "on": ["OnChange"],
                        "handlers": {"OnChange": "Изменить"},
                        "choices": [{"title": "Один", "value": "1"}],
                    },
                    {"check": "Флаг", "path": "Флаг"},
                    {"radio": "Режим", "path": "Режим", "choices": [{"title": "Да", "value": True, "type": "boolean"}]},
                    {"progress": "Ход", "path": "Ход"},
                    {"label": "Надпись", "title": "A < B"},
                    {"labelField": "Представление", "path": "Текст"},
                    {"spreadsheet": "Документ", "path": "Документ"},
                ],
            },
            {
                "pages": "Страницы",
                "children": [
                    {
                        "page": "Страница",
                        "title": "Первая",
                        "children": [
                            {
                                "table": "Таблица",
                                "path": "Строки",
                                "columns": [{"input": "Колонка", "path": "Строки.Текст"}],
                                "commandBarButtons": [{"button": "ВыполнитьВТаблице", "command": "Выполнить"}],
                            },
                        ],
                    }
                ],
            },
            {
                "cmdBar": "Панель",
                "children": [
                    {
                        "popup": "Меню",
                        "title": "Действия",
                        "children": [
                            {"button": "Выполнить", "command": "Выполнить", "defaultButton": True},
                        ],
                    }
                ],
            },
            {"picture": "Картинка", "src": "StdPicture.SaveFile"},
            {"picField": "ПолеКартинки", "path": "Картинка"},
            {"calendar": "Календарь", "path": "Дата"},
        ],
        "attributes": [
            {"name": "Текст", "type": "string(40)"},
            {"name": "Флаг", "type": "boolean"},
            {"name": "Режим", "type": "boolean"},
            {"name": "Ход", "type": "decimal(10,0)"},
            {"name": "Документ", "type": "SpreadsheetDocument"},
            {"name": "Картинка", "type": "Picture"},
            {"name": "Дата", "type": "date"},
            {"name": "Строки", "type": "ValueTable", "columns": [{"name": "Текст", "type": "string(40)"}]},
        ],
        "commands": [{"name": "Выполнить", "title": "Выполнить", "action": "ВыполнитьКоманду"}],
        "parameters": [{"name": "Ключ", "type": "string(40)", "key": True}],
    }


@pytest.mark.parametrize("example", ["rich", "existing-fixture"])
def test_pure_compiler_matches_recorded_output(tmp_path, capsys, example):
    definition = (
        rich_definition()
        if example == "rich"
        else json.loads(
            (Path(__file__).parents[1] / "fixtures/managed-form-cli/form.json").read_text(encoding="utf-8-sig")
        )
    )
    expected = editor.xml_read((GOLDENS / f"{example}.xml").read_bytes(), f"{{{editor.FORM}}}Form")
    actual = render_form(definition)
    assert editor.signature(editor.xml_read(actual, expected.tag)) == editor.signature(expected)
    assert actual == render_form(definition)
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
    assert list(tmp_path.iterdir()) == []


def test_pure_compiler_uses_injected_ids():
    ids = iter(range(1000000, 1001000))
    tree = etree.fromstring(render_form(rich_definition(), allocate_id=lambda: next(ids)))
    allocated = [int(node.get("id")) for node in tree.iter() if node.get("id") not in (None, "-1")]
    assert allocated == list(range(1000000, 1000000 + len(allocated)))


@pytest.mark.parametrize("definition", [{"unknown": True}, {"elements": [{"input": "Поле", "unknown": True}]}])
def test_pure_compiler_rejects_unknown_input(definition):
    with pytest.raises(ValueError):
        render_form(definition)


@pytest.mark.parametrize(
    "layout,logical",
    [
        ("cf", "CommonForm.Форма"),
        ("own-cfe", "CommonForm.Форма"),
        ("epf", "ExternalDataProcessor.ТестоваяОбработка.Form.Форма"),
        ("erf", "ExternalReport.ТестовыйОтчет.Form.Форма"),
    ],
)
def test_compile_plan_preserves_existing_form(tmp_path, layout, logical):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli" / layout, target)
    path = target / form_path(logical)
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    original = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    definition = {
        "title": "Новый заголовок",
        "elements": [
            {
                "group": "vertical",
                "name": "Группа",
                "children": [
                    {"label": "Existing", "title": "Изменено"},
                    {"input": "НовоеПоле", "path": "НовыйРеквизит"},
                ],
            }
        ],
        "attributes": [{"name": "НовыйРеквизит", "type": "string(30)"}],
    }
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "form.compile", "target": logical, "parameters": {"definition": definition}}],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert [write["path"] for write in plan["writes"]] == [form_path(logical)]
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert editor.apply(target, None, plan) == "applied"
    result = editor.xml_read(path.read_bytes(), original.tag)
    for node in original.iter():
        if node.get("id") is not None:
            lineage = [(part.tag, part.get("name")) for part in reversed(list(node.iterancestors()))] + [
                (node.tag, node.get("name"))
            ]
            matches = [
                part
                for part in result.iter()
                if [(ancestor.tag, ancestor.get("name")) for ancestor in reversed(list(part.iterancestors()))]
                + [(part.tag, part.get("name"))]
                == lineage
            ]
            assert len(matches) == 1 and matches[0].get("id") == node.get("id")
    untouched = original.find("f:ChildItems/f:UsualGroup[@name='ТолькоПросмотрГруппа']", editor.NS)
    assert editor.signature(
        result.find("f:ChildItems/f:UsualGroup[@name='ТолькоПросмотрГруппа']", editor.NS)
    ) == editor.signature(untouched)
    assert result.findtext("f:Title/v8:item/v8:content", namespaces=editor.NS) == "Новый заголовок"
    assert result.find("f:Attributes/f:Attribute[@name='НовыйРеквизит']", editor.NS) is not None
    assert all(p.read_bytes() == data for p, data in before.items() if p != path)
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize(
    "initial,direction,expected",
    [
        ("Usual", "vertical", "Usual"),
        ("Usual", "horizontal", "Usual"),
        ("Usual", "collapsible", "Collapsible"),
        ("Collapsible", "vertical", None),
    ],
)
def test_compile_group_preserves_explicit_usual_behavior(tmp_path, initial, direction, expected):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/cf", target)
    logical = "CommonForm.Форма"
    path = target / form_path(logical)
    tree = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    group = tree.find('f:ChildItems/f:UsualGroup[@name="Группа"]', editor.NS)
    etree.SubElement(group, f"{{{editor.FORM}}}Behavior").text = initial
    path.write_bytes(etree.tostring(tree, encoding="utf-8"))
    request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.compile",
                "target": logical,
                "parameters": {
                    "definition": {
                        "elements": [
                            {
                                "group": direction,
                                "name": "Группа",
                                "children": [{"label": "Existing", "title": "Новый заголовок"}],
                            },
                        ]
                    }
                },
            }
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert editor.apply(target, None, plan) == "applied"
    result = editor.xml_read(path.read_bytes(), tree.tag)
    group = result.find('f:ChildItems/f:UsualGroup[@name="Группа"]', editor.NS)
    assert group.findtext("f:Behavior", namespaces=editor.NS) == expected
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []


def test_compile_preserves_dynamic_list_settings(tmp_path):
    target, owner = rename_owner(tmp_path, "Catalog")
    create = {"op": "form.create", "target": owner, "parameters": {"name": "Список", "purpose": "List"}}
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [create]}))
    logical = owner + ".Form.Список"
    path = target / form_path(logical)
    original = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.compile",
                "target": logical,
                "parameters": {
                    "definition": {"title": "Список элементов", "elements": [{"table": "Список", "path": "Список"}]}
                },
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    result = editor.xml_read(path.read_bytes(), original.tag)
    assert editor.signature(result.find("f:Attributes", editor.NS)) == editor.signature(
        original.find("f:Attributes", editor.NS)
    )
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize("purpose,name", [("List", "Список"), ("Object", "Объект")])
@pytest.mark.parametrize(
    "change", [{"title": "Новый заголовок"}, {"savedData": True}, {"type": "string"}, {"main": False}]
)
def test_compile_main_attribute_preserves_identity_and_type(tmp_path, purpose, name, change):
    target, owner = rename_owner(tmp_path, "Catalog")
    create = {"op": "form.create", "target": owner, "parameters": {"name": "Форма", "purpose": purpose}}
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [create]}))
    logical = owner + ".Form.Форма"
    path = target / form_path(logical)
    before = path.read_bytes()
    original = editor.xml_read(before, f"{{{editor.FORM}}}Form")
    attribute_path = "f:Attributes/f:Attribute[@name='" + name + "']"
    old = original.find(attribute_path, editor.NS)
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.compile",
                "target": logical,
                "parameters": {"definition": {"attributes": [{"name": name, **change}]}},
            }
        ],
    }
    if "type" in change or "main" in change:
        with pytest.raises(editor.Rejected):
            editor.plan_make(editor.Snapshot(target), payload)
        assert path.read_bytes() == before
        return
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    result = editor.xml_read(path.read_bytes(), original.tag)
    new = result.find(attribute_path, editor.NS)
    assert new.attrib == old.attrib
    changed_tag = "Title" if "title" in change else "SavedData"
    if "title" in change:
        assert new.findtext("f:Title/v8:item/v8:content", namespaces=editor.NS) == change["title"]
    else:
        assert new.findtext("f:SavedData", namespaces=editor.NS) == "true"
    assert [editor.signature(child) for child in new if etree.QName(child).localname != changed_tag] == [
        editor.signature(child) for child in old if etree.QName(child).localname != changed_tag
    ]
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


def test_compile_borrowed_form_preserves_base_and_module(document_form):  # noqa: F811 — pytest injects the imported fixture by this parameter name
    source, target, relative = document_form
    logical = "Document.Документ.Form.Форма"
    steps = [
        {"op": "object.borrow", "target": "Document.Документ", "parameters": {"baseRoot": str(source)}},
        {"op": "form.borrow", "target": logical, "parameters": {"baseRoot": str(source)}},
    ]
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": steps}))
    path = target / relative
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    original = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    payload = {
        "schemaVersion": 1,
        "operations": steps
        + [
            {
                "op": "form.compile",
                "target": logical,
                "parameters": {"definition": {"elements": [{"label": "НовоеПояснение", "title": "Пояснение"}]}},
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    result = editor.xml_read(path.read_bytes(), original.tag)
    assert editor.signature(result.find("f:BaseForm", editor.NS)) == editor.signature(
        original.find("f:BaseForm", editor.NS)
    )
    added = result.find("f:ChildItems/f:LabelDecoration[@name='НовоеПояснение']", editor.NS)
    assert added is not None
    assert all(int(node.get("id")) >= 1000000 for node in added.iter() if node.get("id"))
    assert all(p.read_bytes() == data for p, data in before.items() if p != path)
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize(
    "elements",
    [
        [{"group": "vertical", "name": "Группа", "children": [{"input": "Existing", "path": "Текст"}]}],
        [{"label": "Новое", "title": "Один"}, {"label": "Новое", "title": "Два"}],
        [{"group": "vertical", "name": "группа"}],
        [
            {"group": "vertical", "name": "Первая", "children": [{"label": "Existing"}]},
            {"group": "vertical", "name": "Вторая", "children": [{"label": "Existing"}]},
        ],
    ],
)
def test_compile_rejects_conflicting_identity_without_writes(tmp_path, elements):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    payload = {
        "schemaVersion": 1,
        "operations": [
            {"op": "form.compile", "target": "CommonForm.Форма", "parameters": {"definition": {"elements": elements}}}
        ],
    }
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


@pytest.mark.parametrize("section", ["attributes", "parameters", "commands"])
def test_compile_rejects_duplicate_description_members(tmp_path, section):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.compile",
                "target": "CommonForm.Форма",
                "parameters": {"definition": {section: [{"name": "Повтор"}, {"name": "Повтор"}]}},
            }
        ],
    }
    with pytest.raises(editor.Rejected, match="Duplicate"):
        editor.plan_make(editor.Snapshot(target), payload)


def test_compile_empty_description_preserves_exact_bytes(tmp_path):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "form.compile", "target": "CommonForm.Форма", "parameters": {"definition": {}}}],
    }
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


def test_compile_rejects_relocation_cycle_without_writes(tmp_path):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    path = target / form_path("CommonForm.Форма")
    tree = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    nodes = editor.named(tree)
    nodes["группа"].find("f:ChildItems", editor.NS).append(nodes["толькопросмотргруппа"])
    path.write_bytes(editor.serialize_like(tree, path.read_bytes()))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.compile",
                "target": "CommonForm.Форма",
                "parameters": {
                    "definition": {
                        "elements": [
                            {
                                "group": "vertical",
                                "name": "Группа",
                                "children": [
                                    {
                                        "group": "vertical",
                                        "name": "ТолькоПросмотрГруппа",
                                        "children": [{"group": "vertical", "name": "Группа"}],
                                    }
                                ],
                            }
                        ]
                    }
                },
            }
        ],
    }
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


def test_compile_preserves_additional_columns(document_form):  # noqa: F811 — pytest injects the imported fixture by this parameter name
    source, _, relative = document_form
    path = source / relative
    original = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    main = original.find("f:Attributes/f:Attribute[@name='Объект']", editor.NS)
    columns = etree.SubElement(main, f"{{{editor.FORM}}}Columns")
    additional = etree.SubElement(columns, f"{{{editor.FORM}}}AdditionalColumns", table="Объект.Товары")
    etree.SubElement(additional, f"{{{editor.FORM}}}Column", name="Сумма", id="200")
    path.write_bytes(editor.serialize_like(original, path.read_bytes()))
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.compile",
                "target": "Document.Документ.Form.Форма",
                "parameters": {"definition": {"title": "Заголовок"}},
            }
        ],
    }
    editor.apply(source, None, editor.plan_make(editor.Snapshot(source), payload))
    result = editor.xml_read(path.read_bytes(), original.tag)
    assert editor.signature(
        result.find("f:Attributes/f:Attribute[@name='Объект']/f:Columns", editor.NS)
    ) == editor.signature(columns)


@pytest.mark.parametrize("source", [None, "StdPicture.Print"])
def test_compile_picture_name_does_not_change_source(tmp_path, source):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    step = {
        "op": "form.compile",
        "target": "CommonForm.Форма",
        "parameters": {"definition": {"elements": [{"picture": "Картинка", "src": "StdPicture.SaveFile"}]}},
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [step]}))
    picture = {"picture": "Картинка"}
    if source is not None:
        picture["src"] = source
    step["parameters"]["definition"]["elements"] = [picture]
    plan = editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [step]})
    editor.apply(target, None, plan)
    form = editor.xml_read((target / form_path("CommonForm.Форма")).read_bytes(), f"{{{editor.FORM}}}Form")
    node = form.find("f:ChildItems/f:PictureDecoration[@name='Картинка']/f:Picture", editor.NS)
    assert node is not None and node[0].text == (source or "StdPicture.SaveFile")
    if source is None:
        assert plan["writes"] == []


@pytest.mark.parametrize(
    "description,tag,property_tag,expected",
    [
        ({"popup": "Меню", "picture": "StdPicture.Print"}, "Popup", "Picture", "StdPicture.Print"),
        ({"page": "Страница", "group": "horizontal"}, "Page", "Group", "Horizontal"),
    ],
)
def test_compile_distinguishes_kind_from_property(tmp_path, description, tag, property_tag, expected):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    definition = {"elements": [description]}
    generated = etree.fromstring(render_form(definition))
    assert generated.find(f"f:ChildItems/f:{tag}", editor.NS) is not None
    initial = generated.find(f"f:ChildItems/f:{tag}/f:{property_tag}", editor.NS)
    assert initial is not None and (initial[0].text if tag == "Popup" else initial.text) == expected
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "form.compile", "target": "CommonForm.Форма", "parameters": {"definition": definition}}],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    description[property_tag[0].lower() + property_tag[1:]] = "StdPicture.SaveFile" if tag == "Popup" else "vertical"
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    tree = editor.xml_read((target / form_path("CommonForm.Форма")).read_bytes(), f"{{{editor.FORM}}}Form")
    node = tree.find(f"f:ChildItems/f:{tag}/f:{property_tag}", editor.NS)
    assert node is not None
    assert (node[0].text if tag == "Popup" else node.text) == ("StdPicture.SaveFile" if tag == "Popup" else "Vertical")
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize("property_name", ["choices", "excludedCommands"])
@pytest.mark.parametrize("unknown", [None, "child", "attribute", "empty-attribute"])
def test_compile_clears_explicit_structured_property(tmp_path, property_name, unknown):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    field = {"input": "Выбор", "path": "Текст", "choices": [{"title": "Один", "value": "1"}]}
    definition = {"elements": [field], "excludedCommands": ["Form.StandardCommand.Close"]}
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "form.compile", "target": "CommonForm.Форма", "parameters": {"definition": definition}}],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    property_path = (
        "f:ChildItems/f:InputField[@name='Выбор']/f:ChoiceList" if property_name == "choices" else "f:CommandSet"
    )
    file = target / form_path("CommonForm.Форма")
    if unknown:
        existing = editor.xml_read(file.read_bytes(), f"{{{editor.FORM}}}Form")
        node = existing.find(property_path, editor.NS)
        if unknown == "child":
            etree.SubElement(node, f"{{{editor.FORM}}}Unknown").text = "Сохранить"
        else:
            if unknown == "empty-attribute":
                for child in list(node):
                    node.remove(child)
            node.set("unknown", "Сохранить")
        file.write_bytes(editor.serialize_like(existing, file.read_bytes()))
    if property_name == "choices":
        field["choices"] = []
    else:
        definition["excludedCommands"] = []
    if unknown:
        before = file.read_bytes()
        with pytest.raises(editor.Rejected, match="Unknown structure"):
            editor.plan_make(editor.Snapshot(target), payload)
        assert file.read_bytes() == before
        return
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    result = editor.xml_read((target / form_path("CommonForm.Форма")).read_bytes(), f"{{{editor.FORM}}}Form")
    assert result.find(property_path, editor.NS) is None
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize("destination", ["ТолькоПросмотрГруппа", "НоваяГруппа"])
def test_compile_relocates_existing_element_without_recreating(tmp_path, destination):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    path = target / form_path("CommonForm.Форма")
    original = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    old = editor.named(original)["existing"]
    expected = editor.signature(old)
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.compile",
                "target": "CommonForm.Форма",
                "parameters": {
                    "definition": {
                        "elements": [{"group": "vertical", "name": destination, "children": [{"label": "Existing"}]}]
                    }
                },
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    result = editor.xml_read(path.read_bytes(), original.tag)
    moved = editor.named(result)["existing"]
    assert moved.getparent().getparent().get("name") == destination
    assert editor.signature(moved) == expected
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize("names", [("ТолькоПросмотрГруппа", "Группа"), ("НоваяГруппа", "Группа")])
def test_compile_respects_explicit_element_order(tmp_path, names):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    path = target / form_path("CommonForm.Форма")
    original = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    original_ids = {key: node.get("id") for key, node in editor.named(original).items()}
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.compile",
                "target": "CommonForm.Форма",
                "parameters": {"definition": {"elements": [{"group": "vertical", "name": name} for name in names]}},
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    result = editor.xml_read(path.read_bytes(), original.tag)
    actual = [node.get("name") for node in result.find("f:ChildItems", editor.NS)]
    assert [name for name in actual if name in names] == list(names)
    assert all(editor.named(result)[key].get("id") == value for key, value in original_ids.items())
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize(
    "initial,change,expected",
    [
        (True, {"title": "Изменено"}, True),
        (False, {"hyperlink": True}, True),
        (True, {"hyperlink": False}, False),
    ],
)
@pytest.mark.parametrize("initial_title", ["Исходный", ""])
def test_compile_label_title_and_hyperlink(tmp_path, initial, change, expected, initial_title):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    step = {
        "op": "form.compile",
        "target": "CommonForm.Форма",
        "parameters": {"definition": {"elements": [{"label": "Ссылка", "title": initial_title, "hyperlink": initial}]}},
    }
    payload = {"schemaVersion": 1, "operations": [step]}
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    step["parameters"]["definition"]["elements"] = [{"label": "Ссылка", **change}]
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    tree = editor.xml_read((target / form_path("CommonForm.Форма")).read_bytes(), f"{{{editor.FORM}}}Form")
    label = editor.named(tree)["ссылка"]
    title = label.find("f:Title", editor.NS)
    if change.get("title", initial_title):
        assert title.get("formatted") == str(expected).lower()
    assert (label.findtext("f:Hyperlink", namespaces=editor.NS) == "true") == expected
    assert (label.findtext("f:Title/v8:item/v8:content", namespaces=editor.NS) or "") == change.get(
        "title", initial_title
    )
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize("kind", ["attribute", "column", "parameter"])
@pytest.mark.parametrize("new_type", ["boolean", "decimal(12,2)"])
@pytest.mark.parametrize("unknown", [None, "child", "attribute"])
def test_compile_changes_explicit_type(tmp_path, kind, new_type, unknown):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    member = {"name": "Значение", "type": "string(20)"}
    definition = (
        {"parameters": [member]}
        if kind == "parameter"
        else {"attributes": [{"name": "Данные", "type": "ValueTable", "columns": [member]}]}
        if kind == "column"
        else {"attributes": [member]}
    )
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "form.compile", "target": "CommonForm.Форма", "parameters": {"definition": definition}}],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    path = target / form_path("CommonForm.Форма")
    original = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    old = original.find(".//*[@name='Значение']")
    if unknown:
        typed = old.find("f:Type", editor.NS)
        if unknown == "child":
            etree.SubElement(typed, f"{{{editor.V8}}}Unknown").text = "Сохранить"
        else:
            typed.set("unknown", "Сохранить")
        path.write_bytes(editor.serialize_like(original, path.read_bytes()))
    member["type"] = new_type
    if unknown:
        before = path.read_bytes()
        with pytest.raises(editor.Rejected, match="Unknown structure"):
            editor.plan_make(editor.Snapshot(target), payload)
        assert path.read_bytes() == before
        return
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    tree = editor.xml_read(path.read_bytes(), original.tag)
    changed = tree.find(".//*[@name='Значение']")
    assert changed.attrib == old.attrib
    assert changed.find("f:Type/v8:StringQualifiers", editor.NS) is None
    assert changed.findtext("f:Type/v8:Type", namespaces=editor.NS) == (
        "xs:boolean" if new_type == "boolean" else "xs:decimal"
    )
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize("unknown", [None, "item-attribute", "content-attribute", "child", "tail"])
@pytest.mark.parametrize("text", ["Новый", ""])
def test_compile_multilingual_title_preserves_unknown_data(tmp_path, unknown, text):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    path = target / form_path("CommonForm.Форма")
    tree = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    title = editor.named(tree)["existing"].find("f:Title", editor.NS)
    russian = title.find("v8:item", editor.NS)
    foreign = etree.SubElement(title, f"{{{editor.V8}}}item")
    etree.SubElement(foreign, f"{{{editor.V8}}}lang").text = "en"
    etree.SubElement(foreign, f"{{{editor.V8}}}content").text = "Keep"
    if unknown == "tail":
        russian.tail = "Keep"
    elif unknown == "child":
        etree.SubElement(russian, f"{{{editor.V8}}}Unknown").text = "Keep"
    elif unknown:
        node = russian if unknown == "item-attribute" else russian.find("v8:content", editor.NS)
        node.set("unknown", "Keep")
    path.write_bytes(editor.serialize_like(tree, path.read_bytes()))
    before = path.read_bytes()
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.compile",
                "target": "CommonForm.Форма",
                "parameters": {"definition": {"elements": [{"label": "Existing", "title": text}]}},
            }
        ],
    }
    if unknown:
        with pytest.raises(editor.Rejected, match="Unknown multilingual"):
            editor.plan_make(editor.Snapshot(target), payload)
        assert path.read_bytes() == before
        return
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    result = editor.xml_read(path.read_bytes(), tree.tag)
    items = editor.named(result)["existing"].findall("f:Title/v8:item", editor.NS)
    assert editor.signature(items[-1]) == editor.signature(foreign)
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, ("xs:boolean", "true")),
        (False, ("xs:boolean", "false")),
        (3, ("xs:decimal", "3")),
        ("да", ("xs:string", "да")),
        # xs:decimal has no exponent: str() would give 1e-07 and 1e+21.
        (1e-07, ("xs:decimal", "0.0000001")),
        (1e21, ("xs:decimal", "1000000000000000000000")),
        (2.50, ("xs:decimal", "2.5")),
        (-0.0, ("xs:decimal", "0")),
        (123456789012345678901234567890, ("xs:decimal", "123456789012345678901234567890")),
    ],
)
def test_compile_infers_choice_value_type_from_json(tmp_path, value, expected):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    field = {"input": "Выбор", "path": "Текст", "choices": [{"title": "Один", "value": value}]}
    payload = {
        "schemaVersion": 1,
        "operations": [
            {"op": "form.compile", "target": "CommonForm.Форма", "parameters": {"definition": {"elements": [field]}}}
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    tree = editor.xml_read((target / form_path("CommonForm.Форма")).read_bytes(), f"{{{editor.FORM}}}Form")
    ns = {**editor.NS, "xr": "http://v8.1c.ru/8.3/xcf/readable"}
    node = tree.find("f:ChildItems/f:InputField[@name='Выбор']/f:ChoiceList/xr:Item/xr:Value/f:Value", ns)
    assert (node.get("{http://www.w3.org/2001/XMLSchema-instance}type"), node.text) == expected
