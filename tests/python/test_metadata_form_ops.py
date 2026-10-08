"""Scalar and object-bound fields through the ordered metadata plan."""

from tests.python.metadata_test_support import designer_export, present  # noqa: I001 — runs first: skips the module without pytest, lxml, jsonschema
from typing import Any
from pathlib import Path
import shutil
import uuid

import lxml.etree as etree
import pytest

from scripts.python import metadata as editor, metadata_form_ops as forms
from tests.python.test_metadata_object_ops import document_roots, request, rename_owner  # noqa: F401 — pytest fixture, requested by parameter name
from tests.python.test_metadata_borrow import roots  # noqa: F401 — pytest fixture, requested by parameter name


FIXTURES = Path(__file__).parents[1] / "fixtures/managed-form-cli"


def test_edit_preserves_repeated_choice_parameter_names(tmp_path):
    target = tmp_path / "target"
    shutil.copytree(FIXTURES / "own-cfe", target)
    logical = "CommonForm.Форма"
    path = target / forms.form_path(logical)
    form = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    field = editor.named(form)["existing"]
    parameters = etree.SubElement(field, f"{{{editor.FORM}}}ChoiceParameters")
    for value in ("false", "true"):
        item = etree.SubElement(parameters, f"{{{editor.V8}}}item", name="Отбор.Забалансовый")
        etree.SubElement(item, f"{{{editor.V8}}}value").text = value
    path.write_bytes(editor.serialize_like(form, path.read_bytes()))
    before = editor.signature(field)
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.edit",
                "target": logical,
                "parameters": {"definition": {"elements": [{"label": "НовоеПояснение", "title": "Ф4"}]}},
            }
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    result = editor.xml_read(path.read_bytes(), form.tag)
    assert editor.signature(editor.named(result)["existing"]) == before
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    duplicate = etree.SubElement(
        result.find("f:ChildItems", editor.NS), f"{{{editor.FORM}}}InputField", name="Existing", id="99999"
    )
    assert duplicate is not None
    with pytest.raises(editor.Rejected, match="Duplicate existing element name"):
        editor.named(result)


@pytest.mark.parametrize("kind", ["Catalog", "ExternalDataProcessor", "ExternalReport"])
def test_remove_form_exact_files_default_and_repeat(tmp_path, kind):
    from scripts.python import metadata_object_ops as objects

    target, logical = rename_owner(tmp_path, kind)
    setup = {
        "schemaVersion": 1,
        "operations": [
            {"op": "form.create", "target": logical, "parameters": {"name": "Удаляемая", "setDefault": True}}
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), setup))
    form_target = logical + ".Form.Удаляемая"
    path = forms.form_path(form_target)
    descriptor, _, _, _ = editor.layout(path)
    folder = descriptor.removesuffix(".xml") + "/"
    # Nonempty code inside the removed subtree is not a surviving dependency.
    (target / (path[:-4] + "/Module.bsl")).write_text("ВременныйОбработчик();", encoding="utf-8")
    before = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    _, _, owner_path, _ = objects.read_object(editor.Snapshot(target), logical)
    payload = {"schemaVersion": 1, "operations": [{"op": "form.remove", "target": form_target, "parameters": {}}]}
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    removed = {p for p in before if p == descriptor or p.startswith(folder)}
    assert {item["path"] for item in plan["writes"]} == removed | {owner_path}
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    assert not any((target / p).exists() for p in removed)
    _, owner, _, _ = objects.read_object(editor.Snapshot(target), logical)
    assert not owner.findall("m:ChildObjects/m:Form", editor.NS)
    default = "DefaultForm" if kind.startswith("External") else "DefaultObjectForm"
    assert not editor.prop(owner, default)
    assert all((target / p).read_bytes() == data for p, data in before.items() if p not in removed | {owner_path})


@pytest.mark.parametrize("layout", ["cf", "own-cfe"])
@pytest.mark.parametrize("fault", [None, "property", "nested", "attribute", "tail", "leaf-tail"])
def test_remove_common_form_registration_and_repeat(tmp_path, layout, fault):
    target = tmp_path / "target"
    target.mkdir()
    config_bytes = (FIXTURES / layout / "Configuration.xml").read_bytes()
    config = editor.metadata(config_bytes, "Configuration")
    children = config.find("m:ChildObjects", editor.NS)
    for child in list(children):
        if child.tag != f"{{{editor.MD}}}CommonForm":
            children.remove(child)
    properties = config.find("m:Properties", editor.NS)
    if fault == "property":
        etree.SubElement(properties, f"{{{editor.MD}}}UnknownProperty").text = "opaque"
    elif fault == "nested":
        field = properties.find("m:UsedMobileApplicationFunctionalities", editor.NS)
        if field is None:
            field = etree.SubElement(properties, f"{{{editor.MD}}}UsedMobileApplicationFunctionalities")
        etree.SubElement(field, "{http://v8.1c.ru/8.2/managed-application/core}Unknown").text = "opaque"
    elif fault == "attribute":
        properties.find("m:Name", editor.NS).set("unknown", "opaque")
    elif fault in {"tail", "leaf-tail"}:
        field = properties.find("m:UsedMobileApplicationFunctionalities", editor.NS)
        if field is None:
            field = etree.SubElement(properties, f"{{{editor.MD}}}UsedMobileApplicationFunctionalities")
            app = "http://v8.1c.ru/8.2/managed-application/core"
            item = etree.SubElement(field, f"{{{app}}}functionality")
            etree.SubElement(item, f"{{{app}}}functionality").text = "Geolocation"
            etree.SubElement(item, f"{{{app}}}use").text = "false"
        node = field[0] if fault == "tail" else field[0][0]
        node.tail = "CommonForm.Форма"
    (target / "Configuration.xml").write_bytes(editor.serialize_like(config.getparent(), config_bytes))
    shutil.copytree(FIXTURES / layout / "CommonForms", target / "CommonForms")
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "form.remove", "target": "CommonForm.Форма", "parameters": {}}],
    }
    if fault:
        before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
        with pytest.raises(editor.Rejected):
            editor.plan_make(editor.Snapshot(target), payload)
        assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
        return
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    assert {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()} == {"Configuration.xml"}
    actual = editor.metadata((target / "Configuration.xml").read_bytes(), "Configuration")
    assert not actual.findall("m:ChildObjects/m:CommonForm", editor.NS)


@pytest.mark.parametrize(
    "fault",
    [
        "reference",
        "bsl",
        "unknown",
        "registration",
        "descriptor",
        "template",
        "body",
        "registration-attribute",
        "registration-tail",
    ],
)
def test_remove_form_rejects_surviving_dependencies_and_mismatch(tmp_path, fault):
    from scripts.python import metadata_object_ops as objects

    target, logical = rename_owner(tmp_path, "ExternalDataProcessor")
    setup = {
        "schemaVersion": 1,
        "operations": [
            {"op": "form.create", "target": logical, "parameters": {"name": "Удаляемая", "setDefault": True}}
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), setup))
    form_target = logical + ".Form.Удаляемая"
    _, owner, owner_path, original = objects.read_object(editor.Snapshot(target), logical)
    if fault == "reference":
        node = owner.find("m:Properties/m:AuxiliaryForm", editor.NS)
        if node is None:
            node = etree.SubElement(owner.find("m:Properties", editor.NS), f"{{{editor.MD}}}AuxiliaryForm")
        node.text = form_target
    elif fault == "registration":
        owner.find("m:ChildObjects", editor.NS).remove(owner.find("m:ChildObjects/m:Form", editor.NS))
    elif fault == "registration-attribute":
        owner.find("m:ChildObjects/m:Form", editor.NS).set("unknown", "opaque")
    elif fault == "registration-tail":
        owner.find("m:ChildObjects/m:Form", editor.NS).tail = "opaque"
    elif fault == "descriptor":
        descriptor, _, _, _ = editor.layout(forms.form_path(form_target))
        (target / descriptor).unlink()
    elif fault == "body":
        (target / forms.form_path(form_target)).unlink()
    elif fault == "template":
        directory = target / forms.form_path(form_target).rsplit("/Ext/", 1)[0] / "Templates"
        directory.mkdir()
        (directory / "Макет.bin").write_bytes(b"opaque")
    elif fault == "bsl":
        (target / "Module.bsl").write_text("НеисследованныйКод();", encoding="utf-8")
    else:
        (target / "Unknown.xml").write_bytes(b"<Unknown/>")
    (target / owner_path).write_bytes(editor.serialize_like(owner.getparent(), original))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    payload = {"schemaVersion": 1, "operations": [{"op": "form.remove", "target": form_target, "parameters": {}}]}
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "kind,purpose",
    [
        (kind, purpose)
        for kind in (
            "Catalog",
            "Document",
            "ChartOfAccounts",
            "ChartOfCharacteristicTypes",
            "ExchangePlan",
            "BusinessProcess",
            "Task",
        )
        for purpose in ("List", "Choice")
    ]
    + [("InformationRegister", "List"), ("InformationRegister", "Record")],
)
def test_create_form_purpose_matrix(tmp_path, kind, purpose):
    target, logical = rename_owner(tmp_path, kind)
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.create",
                "target": logical,
                "parameters": {"name": "НоваяФорма", "purpose": purpose, "setDefault": True},
            }
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    path = forms.form_path(logical + ".Form.НоваяФорма")
    form = editor.xml_read((target / path).read_bytes(), f"{{{editor.FORM}}}Form")
    main = form.find("f:Attributes/f:Attribute", editor.NS)
    assert main.get("name") == ("Запись" if purpose == "Record" else "Список")
    if purpose != "Record":
        assert main.findtext("f:Settings/f:MainTable", namespaces=editor.NS) == logical
    owner = editor.metadata((target / (path.split("/Forms/")[0] + ".xml")).read_bytes(), kind)
    assert editor.prop(owner, "Default" + purpose + "Form") == logical + ".Form.НоваяФорма"


@pytest.mark.parametrize(
    "kind,purpose",
    [
        (kind, purpose)
        for kind in ("DataProcessor", "Report", "ExternalDataProcessor", "ExternalReport")
        for purpose in ("List", "Choice", "Record")
    ]
    + [("Catalog", "Record"), ("InformationRegister", "Choice")],
)
def test_create_form_rejects_invalid_purpose(tmp_path, kind, purpose):
    target, logical = rename_owner(tmp_path, kind)
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    payload = {
        "schemaVersion": 1,
        "operations": [
            {"op": "form.create", "target": logical, "parameters": {"name": "НоваяФорма", "purpose": purpose}}
        ],
    }
    with pytest.raises(editor.Rejected, match="owner/purpose"):
        editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


@pytest.mark.parametrize("set_default", [False, True])
@pytest.mark.parametrize("adopted", [False, True])
def test_create_form_preserves_or_replaces_default(document_roots, set_default, adopted):  # noqa: F811 — pytest injects the imported fixture by this parameter name
    from scripts.python import metadata_create as create

    source, target = document_roots
    source_path = source / "Documents/Документ.xml"
    source_path.write_bytes(create.render_object({"type": "Document", "name": "Документ"}, str(uuid.uuid4()), {}))
    owner = editor.metadata(source_path.read_bytes(), "Document")
    old_default = "Document.Документ.Form.ПрежняяФорма"
    owner.find("m:Properties/m:DefaultListForm", editor.NS).text = old_default
    source_path.write_bytes(etree.tostring(owner.getparent()))
    borrow_step = {"op": "object.borrow", "target": "Document.Документ", "parameters": {"baseRoot": str(source)}}
    editor.apply(
        target, None, editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [borrow_step]})
    )
    owner_path = target / "Documents/Документ.xml"
    if not adopted:
        owner.find("m:Properties", editor.NS).insert(0, etree.Element(f"{{{editor.MD}}}ObjectBelonging"))
        owner.find("m:Properties/m:ObjectBelonging", editor.NS).text = "Native"
        owner_path.write_bytes(etree.tostring(owner.getparent()))
    payload = {
        "schemaVersion": 1,
        "operations": ([borrow_step] if adopted else [])
        + [
            {
                "op": "form.create",
                "target": "Document.Документ",
                "parameters": {"name": "НоваяФорма", "purpose": "List", "setDefault": set_default},
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    result = editor.metadata(owner_path.read_bytes(), "Document")
    actual = editor.prop(result, "DefaultListForm") or editor.prop(owner, "DefaultListForm")
    assert actual == ("Document.Документ.Form.НоваяФорма" if set_default else old_default)
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize("fault", ["duplicate-table", "custom-query"])
def test_dynamic_form_repeat_rejects_changed_settings(tmp_path, fault):
    target, logical = rename_owner(tmp_path, "Catalog")
    payload = {
        "schemaVersion": 1,
        "operations": [
            {"op": "form.create", "target": logical, "parameters": {"name": "НоваяФорма", "purpose": "List"}}
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    path = target / forms.form_path(logical + ".Form.НоваяФорма")
    form = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    settings = form.find("f:Attributes/f:Attribute/f:Settings", editor.NS)
    etree.SubElement(
        settings, f"{{{editor.FORM}}}" + ("MainTable" if fault == "duplicate-table" else "CustomQuery")
    ).text = "Catalog.Другой" if fault == "duplicate-table" else "true"
    path.write_bytes(editor.serialize_like(form, path.read_bytes()))
    with pytest.raises(editor.Rejected, match="dynamic list"):
        editor.plan_make(editor.Snapshot(target), payload)


@pytest.mark.parametrize("problem", [None, "missing-base", "base-collision"])
def test_create_form_for_adopted_owner(document_roots, problem):  # noqa: F811 — pytest injects the imported fixture by this parameter name
    from scripts.python import metadata_create as create

    source, target = document_roots
    source_path = source / "Documents/Документ.xml"
    source_path.write_bytes(create.render_object({"type": "Document", "name": "Документ"}, str(uuid.uuid4()), {}))
    if problem == "base-collision":
        owner = editor.metadata(source_path.read_bytes(), "Document")
        etree.SubElement(owner.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}Form").text = "НоваяФорма"
        source_path.write_bytes(etree.tostring(owner.getparent()))
    source_bytes = source_path.read_bytes()
    borrow_step = {"op": "object.borrow", "target": "Document.Документ", "parameters": {"baseRoot": str(source)}}
    editor.apply(
        target, None, editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [borrow_step]})
    )
    operation = {
        "op": "form.create",
        "target": "Document.Документ",
        "parameters": {"name": "НоваяФорма", "purpose": "List", "setDefault": True},
    }
    payload = {"schemaVersion": 1, "operations": ([borrow_step] if problem != "missing-base" else []) + [operation]}
    if problem:
        with pytest.raises(editor.Rejected):
            editor.plan_make(editor.Snapshot(target), payload)
    else:
        plan = editor.plan_make(editor.Snapshot(target), payload)
        assert editor.apply(target, None, plan) == "applied"
        assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    assert source_path.read_bytes() == source_bytes


@pytest.mark.parametrize(
    "kind",
    [
        "Catalog",
        "Document",
        "DataProcessor",
        "Report",
        "ExternalDataProcessor",
        "ExternalReport",
        "ChartOfAccounts",
        "ChartOfCharacteristicTypes",
        "ExchangePlan",
        "BusinessProcess",
        "Task",
        "InformationRegister",
    ],
)
def test_create_object_form_owner_matrix(tmp_path, kind):
    target, logical = rename_owner(tmp_path, kind)
    payload = {
        "schemaVersion": 1,
        "operations": [
            {"op": "form.create", "target": logical, "parameters": {"name": "НоваяФорма", "purpose": "Object"}}
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    form_path = forms.form_path(logical + ".Form.НоваяФорма")
    form = editor.xml_read((target / form_path).read_bytes(), f"{{{editor.FORM}}}Form")
    main = form.find("f:Attributes/f:Attribute", editor.NS)
    expected = "InformationRegisterRecordManager" if kind == "InformationRegister" else kind + "Object"
    assert main.get("name") == "Объект"
    assert main.findtext("f:Type/v8:Type", namespaces=editor.NS) == "cfg:" + expected + ".Владелец"
    module = target / (form_path[:-4] + "/Module.bsl")
    module.write_bytes(b"// preserved module\r\n")
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.fixture
def document_form(document_roots):  # noqa: F811 — pytest injects the imported fixture by this parameter name
    source, target = document_roots
    stem = "Documents/Документ/Forms/Форма"
    shutil.copytree(source / "CommonForms/Форма", source / stem)
    descriptor = editor.metadata((source / "CommonForms/Форма.xml").read_bytes(), "CommonForm")
    descriptor.tag = f"{{{editor.MD}}}Form"
    descriptor.set("uuid", str(uuid.uuid4()))
    (source / (stem + ".xml")).write_bytes(etree.tostring(descriptor.getparent()))
    path = source / "Documents/Документ.xml"
    owner = editor.metadata(path.read_bytes(), "Document")
    etree.SubElement(owner.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}Form").text = "Форма"
    path.write_bytes(editor.serialize_like(owner.getparent(), path.read_bytes()))
    path = source / stem / "Ext/Form.xml"
    form = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    attribute = etree.SubElement(
        form.find("f:Attributes", editor.NS), f"{{{editor.FORM}}}Attribute", name="Объект", id="100"
    )
    typed = etree.SubElement(attribute, f"{{{editor.FORM}}}Type")
    etree.SubElement(typed, f"{{{editor.V8}}}Type").text = "cfg:DocumentObject.Документ"
    etree.SubElement(attribute, f"{{{editor.FORM}}}MainAttribute").text = "true"
    path.write_bytes(editor.serialize_like(form, path.read_bytes()))
    return source, target, stem + "/Ext/Form.xml"


def field_operation(target="Document.Документ.Form.Форма", attribute="Объект.цф_Поле"):
    return {
        "op": "form.add-input",
        "target": target,
        "parameters": {
            "name": "цф_Поле",
            "attribute": attribute,
            "title": "Новое поле",
            "parent": "Группа",
            "after": "Existing",
        },
    }


def full_request(source, value_type):
    payload = request(source, [{"name": "цф_Поле", "type": value_type}])
    payload["operations"].extend(
        [
            {"op": "form.borrow", "target": "Document.Документ.Form.Форма", "parameters": {"baseRoot": str(source)}},
            field_operation(),
        ]
    )
    return payload


@pytest.mark.parametrize("value_type", ["String(125)", "Number(15,2,nonneg)", "Boolean", "Date"])
def test_document_field_full_sequence(document_form, value_type):
    source, target, path = document_form
    payload = full_request(source, value_type)
    original = editor.xml_read((source / path).read_bytes(), f"{{{editor.FORM}}}Form")
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert not (target / path).exists()
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    form = editor.xml_read((target / path).read_bytes(), f"{{{editor.FORM}}}Form")
    field = editor.named(form)["цф_поле"]
    assert etree.QName(field).localname == ("CheckBoxField" if value_type == "Boolean" else "InputField")
    assert field.findtext("f:DataPath", namespaces=editor.NS) == "Объект.цф_Поле"
    assert all(int(node.get("id")) >= 1000000 for node in field.iter() if node.get("id"))
    for binding in original.xpath(".//f:Events | ./f:Commands/f:Command/f:Action", namespaces=editor.NS):
        binding.getparent().remove(binding)
    base = form.find("f:BaseForm", editor.NS)
    base.tag = original.tag
    assert editor.signature(base) == editor.signature(original)
    form.remove(base)
    field.getparent().remove(field)
    assert editor.signature(form) == editor.signature(original)
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize(
    "layout,target_name",
    [
        ("cf", "CommonForm.Форма"),
        ("own-cfe", "CommonForm.Форма"),
        ("epf", "ExternalDataProcessor.ТестоваяОбработка.Form.Форма"),
        ("erf", "ExternalReport.ТестовыйОтчет.Form.Форма"),
        ("own-cfe", "DataProcessor.Владелец.Form.Форма"),
    ],
)
@pytest.mark.parametrize("attribute", ["Текст", "Число", "Флаг", "Дата"])
def test_scalar_field_existing_layouts(tmp_path, layout, target_name, attribute):
    target = tmp_path / "target"
    shutil.copytree(FIXTURES / layout, target)
    path = forms.form_path(target_name)
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    payload = {"schemaVersion": 1, "operations": [field_operation(target_name, attribute)]}
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert [write["path"] for write in plan["writes"]] == [path]
    editor.apply(target, None, plan)
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    for file, data in before.items():
        if file != target / path:
            assert file.read_bytes() == data


@pytest.mark.parametrize(
    "fault", ["missing-attribute", "missing-anchor", "wrong-parent", "wrong-main", "wrong-owner", "union"]
)
def test_object_field_rejects_invalid_binding(document_form, fault):
    source, target, path = document_form
    payload = full_request(source, "Boolean")
    if fault == "missing-attribute":
        payload["operations"][-1]["parameters"]["attribute"] = "Объект.Отсутствует"
    elif fault == "missing-anchor":
        payload["operations"][-1]["parameters"]["after"] = "Отсутствует"
    elif fault == "wrong-parent":
        payload["operations"][-1]["parameters"]["parent"] = "ТолькоПросмотрГруппа"
    else:
        form = editor.xml_read((source / path).read_bytes(), f"{{{editor.FORM}}}Form")
        main = form.find("f:Attributes/f:Attribute[@name='Объект']", editor.NS)
        if fault == "wrong-main":
            main.find("f:MainAttribute", editor.NS).text = "false"
        elif fault == "wrong-owner":
            main.find("f:Type/v8:Type", editor.NS).text = "cfg:DataProcessorObject.Владелец"
        else:
            etree.SubElement(main.find("f:Type", editor.NS), f"{{{editor.V8}}}Type").text = "xs:string"
        (source / path).write_bytes(editor.serialize_like(form, (source / path).read_bytes()))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


def test_selected_bp_goods_form_complete_file_plan(roots):  # noqa: F811 — pytest injects the imported fixture by this parameter name
    _, target = roots
    for file in target.rglob("*.xml"):
        tree = etree.fromstring(file.read_bytes())
        tree.set("version", "2.20")
        file.write_bytes(etree.tostring(tree))
    source = designer_export("Documents/ПоступлениеТоваровУслуг/Forms/ФормаДокументаТовары/Ext/Form.xml")
    owner = "Document.ПоступлениеТоваровУслуг"
    logical = owner + ".Form.ФормаДокументаТовары"
    path = forms.form_path(logical)
    snapshot = editor.Snapshot(target)
    alias = snapshot.source_root(source)
    original = editor.xml_read(present(snapshot.read(alias, path)), f"{{{editor.FORM}}}Form")
    anchor = original.find("f:ChildItems", editor.NS)[-1].get("name")
    attributes = [
        {"name": "цф_Проверка" + str(index), "type": value}
        for index, value in enumerate(["String(125)", "Number(15,2,nonneg)", "Boolean", "Date"])
    ]
    operations = [
        {"op": "object.borrow", "target": owner, "parameters": {"baseRoot": str(source)}},
        {"op": "object.edit", "target": owner, "parameters": {"definition": {"add": {"attributes": attributes}}}},
        {"op": "form.borrow", "target": logical, "parameters": {"baseRoot": str(source)}},
    ]
    for attribute in attributes:
        name = attribute["name"]
        operation = field_operation(logical, "Объект." + name)
        operation["parameters"].update(name=name, parent="$root", after=anchor)
        operations.append(operation)
        anchor = name
    plan = editor.plan_make(snapshot, {"schemaVersion": 1, "operations": operations})
    candidate = editor.xml_read(present(snapshot.read("target", path)), f"{{{editor.FORM}}}Form")
    for binding in original.xpath(".//f:Events | ./f:Commands/f:Command/f:Action", namespaces=editor.NS):
        binding.getparent().remove(binding)
    # Native borrowed-form samples serialize the inherited Help binding as 0.
    standard_commands = original.xpath(
        './/f:CommandName[starts-with(text(), "Form.StandardCommand.")]', namespaces=editor.NS
    )
    assert [node.text for node in standard_commands] == ["Form.StandardCommand.Help"]
    standard_commands[0].text = "0"
    base = candidate.find("f:BaseForm", editor.NS)
    base.tag = original.tag
    assert editor.signature(base) == editor.signature(original)
    candidate.remove(base)
    names = editor.named(candidate)
    for index, attribute in enumerate(attributes):
        field = names[attribute["name"].casefold()]
        assert etree.QName(field).localname == ("CheckBoxField" if index == 2 else "InputField")
        field.getparent().remove(field)
    assert editor.signature(candidate) == editor.signature(original)
    assert plan["checks"]["platform"] == plan["checks"]["runtime"] == "not-run"
    assert not (target / "Documents").exists()
    snapshot.unchanged()


def test_external_kind_mismatch_rejected(tmp_path):
    target = tmp_path / "target"
    shutil.copytree(FIXTURES / "erf", target)
    payload = {
        "schemaVersion": 1,
        "operations": [field_operation("ExternalDataProcessor.ТестовыйОтчет.Form.Форма", "Текст")],
    }
    with pytest.raises(editor.Rejected, match="kind mismatch"):
        editor.plan_make(editor.Snapshot(target), payload)


@pytest.mark.parametrize(
    "layout,logical",
    [
        ("cf", "CommonForm.Форма"),
        ("own-cfe", "CommonForm.Форма"),
        ("epf", "ExternalDataProcessor.ТестоваяОбработка.Form.Форма"),
        ("erf", "ExternalReport.ТестовыйОтчет.Form.Форма"),
    ],
)
@pytest.mark.parametrize(
    "position", [{}, {"into": "Группа"}, {"after": "Existing"}, {"into": "Группа", "after": "Existing"}]
)
def test_edit_adds_members_at_exact_position(tmp_path, layout, logical, position):
    target = tmp_path / "target"
    shutil.copytree(FIXTURES / layout, target)
    path = target / forms.form_path(logical)
    original = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    definition = {
        **position,
        "elements": [
            {"input": "НовоеПоле", "path": "НовоеЗначение", "title": "Новое"},
            {"label": "Пояснение", "title": "Проверка"},
        ],
        "attributes": [{"name": "НовоеЗначение", "type": "string(30)"}],
    }
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "form.edit", "target": logical, "parameters": {"definition": definition}}],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    editor.apply(target, None, plan)
    result = editor.xml_read(path.read_bytes(), original.tag)
    nodes = editor.named(result)
    field = nodes["новоеполе"]
    container = field.getparent()
    assert container.getparent().get("name") == ("Группа" if position else None)
    siblings = [node.get("name") for node in container]
    assert siblings[siblings.index("НовоеПоле") + 1] == "Пояснение"
    if "after" in position:
        assert siblings[siblings.index("Existing") + 1] == "НовоеПоле"
    for key, old in editor.named(original).items():
        assert nodes[key].get("id") == old.get("id")
    assert editor.signature(nodes["existing"]) == editor.signature(editor.named(original)["existing"])
    assert all(p.read_bytes() == data for p, data in before.items() if p != path)
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize(
    "position,elements",
    [
        ({"into": "НетГруппы"}, [{"label": "Новое"}]),
        ({"into": "группа"}, [{"label": "Новое"}]),
        ({"into": "Existing"}, [{"label": "Новое"}]),
        ({"after": "НетЭлемента"}, [{"label": "Новое"}]),
        ({"into": "Группа", "after": "ТолькоПросмотрГруппа"}, [{"label": "Новое"}]),
        ({}, [{"label": "Existing", "title": "Подмена"}]),
    ],
)
def test_edit_rejects_conflicting_placement(tmp_path, position, elements):
    target = tmp_path / "target"
    shutil.copytree(FIXTURES / "own-cfe", target)
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.edit",
                "target": "CommonForm.Форма",
                "parameters": {"definition": {**position, "elements": elements}},
            }
        ],
    }
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


def test_edit_borrowed_form_preserves_base(document_form):
    source, target, relative = document_form
    logical = "Document.Документ.Form.Форма"
    steps = [
        {"op": "object.borrow", "target": "Document.Документ", "parameters": {"baseRoot": str(source)}},
        {"op": "form.borrow", "target": logical, "parameters": {"baseRoot": str(source)}},
    ]
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": steps}))
    path = target / relative
    original = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    steps.append(
        {
            "op": "form.edit",
            "target": logical,
            "parameters": {
                "definition": {
                    "into": "Группа",
                    "after": "Existing",
                    "elements": [{"label": "Пояснение", "title": "Добавлено"}],
                }
            },
        }
    )
    payload = {"schemaVersion": 1, "operations": steps}
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    result = editor.xml_read(path.read_bytes(), original.tag)
    assert editor.signature(result.find("f:BaseForm", editor.NS)) == editor.signature(
        original.find("f:BaseForm", editor.NS)
    )
    added = editor.named(result)["пояснение"]
    assert all(int(node.get("id")) >= 1000000 for node in added.iter() if node.get("id"))
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


def test_edit_mixed_addition_checks_final_position(tmp_path):
    target = tmp_path / "target"
    shutil.copytree(FIXTURES / "own-cfe", target)
    definition: dict[str, Any] = {"elements": [{"label": "A"}, {"label": "B"}]}
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "form.edit", "target": "CommonForm.Форма", "parameters": {"definition": definition}}],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    definition.update({"after": "A", "elements": [{"label": "X"}, {"label": "B"}]})
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    path = target / forms.form_path("CommonForm.Форма")
    tree = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    names = [node.get("name") for node in tree.find("f:ChildItems", editor.NS)]
    assert names[-3:] == ["A", "X", "B"]
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    definition.update({"after": "B", "elements": [{"label": "A"}]})
    before = path.read_bytes()
    with pytest.raises(editor.Rejected, match="placement conflicts"):
        editor.plan_make(editor.Snapshot(target), payload)
    assert path.read_bytes() == before


def test_edit_actions_and_events_without_bsl_changes(tmp_path):
    target = tmp_path / "target"
    shutil.copytree(FIXTURES / "own-cfe", target)
    path = target / forms.form_path("CommonForm.Форма")
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    definition = {
        "commands": [
            {
                "name": "Команда",
                "title": "Команда",
                "actions": [{"handler": "До", "callType": "Before"}, {"handler": "После", "callType": "After"}],
            },
            {"name": "Одиночная", "action": "Вызвать", "callType": "Override"},
        ],
        "formEvents": [
            {"name": "OnOpen", "handler": "ДоОткрытия", "callType": "Before"},
            {"name": "OnOpen", "handler": "ПослеОткрытия", "callType": "After"},
        ],
        "elementEvents": [{"element": "Existing", "name": "Click", "handler": "Нажатие", "callType": "After"}],
        "elements": [
            {
                "input": "ПолеСобытий",
                "path": "Текст",
                "on": [{"event": "OnChange", "handler": "Изменено", "callType": "After"}, "Clearing"],
                "handlers": {"Clearing": "Очистить"},
            }
        ],
    }
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "form.edit", "target": "CommonForm.Форма", "parameters": {"definition": definition}}],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    tree = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    actions = tree.findall("f:Commands/f:Command[@name='Команда']/f:Action", editor.NS)
    assert [(node.get("callType"), node.text) for node in actions] == [("Before", "До"), ("After", "После")]
    action = tree.find("f:Commands/f:Command[@name='Одиночная']/f:Action", editor.NS)
    assert (action.get("callType"), action.text) == ("Override", "Вызвать")
    assert [(node.get("callType"), node.text) for node in tree.findall("f:Events/f:Event", editor.NS)] == [
        ("Before", "ДоОткрытия"),
        ("After", "ПослеОткрытия"),
    ]
    nodes = editor.named(tree)
    assert nodes["existing"].findtext("f:Events/f:Event", namespaces=editor.NS) == "Нажатие"
    assert [
        (node.get("name"), node.get("callType"), node.text)
        for node in nodes["полесобытий"].findall("f:Events/f:Event", editor.NS)
    ] == [("OnChange", "After", "Изменено"), ("Clearing", None, "Очистить")]
    assert all(p.read_bytes() == data for p, data in before.items() if p != path)
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize("section", ["commands", "formEvents", "elementEvents"])
def test_edit_adds_event_slot_and_rejects_conflict(tmp_path, section):
    target = tmp_path / "target"
    shutil.copytree(FIXTURES / "own-cfe", target)
    entry: dict[str, Any] = (
        {"name": "Команда", "actions": [{"handler": "До", "callType": "Before"}]}
        if section == "commands"
        else {"name": "Click" if section == "elementEvents" else "OnOpen", "handler": "До", "callType": "Before"}
    )
    if section == "elementEvents":
        entry["element"] = "Existing"
    definition = {section: [entry]}
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "form.edit", "target": "CommonForm.Форма", "parameters": {"definition": definition}}],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    slot = entry["actions"][0] if section == "commands" else entry
    slot.update({"handler": "После", "callType": "After"})
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    path = target / forms.form_path("CommonForm.Форма")
    tree = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    query = {
        "commands": "f:Commands/f:Command[@name='Команда']/f:Action",
        "formEvents": "f:Events/f:Event",
        "elementEvents": ".//f:LabelDecoration[@name='Existing']/f:Events/f:Event",
    }[section]
    assert [(node.get("callType"), node.text) for node in tree.findall(query, editor.NS)] == [
        ("Before", "До"),
        ("After", "После"),
    ]
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    before = path.read_bytes()
    slot["handler"] = "Подмена"
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), payload)
    assert path.read_bytes() == before


@pytest.mark.parametrize("unknown", ["attribute", "child", "duplicate"])
def test_edit_rejects_ambiguous_or_unknown_event_structure(tmp_path, unknown):
    target = tmp_path / "target"
    shutil.copytree(FIXTURES / "own-cfe", target)
    path = target / forms.form_path("CommonForm.Форма")
    tree = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    events = etree.SubElement(tree, f"{{{editor.FORM}}}Events")
    event = etree.SubElement(events, f"{{{editor.FORM}}}Event", name="OnOpen", callType="Before")
    event.text = "До"
    if unknown == "attribute":
        event.set("unknown", "Keep")
    elif unknown == "child":
        etree.SubElement(event, f"{{{editor.FORM}}}Unknown").text = "Keep"
    else:
        etree.SubElement(events, event.tag, **event.attrib).text = event.text
    path.write_bytes(editor.serialize_like(tree, path.read_bytes()))
    before = path.read_bytes()
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.edit",
                "target": "CommonForm.Форма",
                "parameters": {
                    "definition": {"formEvents": [{"name": "OnOpen", "handler": "После", "callType": "After"}]}
                },
            }
        ],
    }
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), payload)
    assert path.read_bytes() == before


def test_edit_adds_nested_event_without_changing_parent(tmp_path):
    target = tmp_path / "target"
    shutil.copytree(FIXTURES / "own-cfe", target)
    field: dict[str, Any] = {"input": "F", "path": "Текст", "title": "Прежний"}
    definition = {"elements": [{"group": "vertical", "name": "G", "children": [field]}]}
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "form.edit", "target": "CommonForm.Форма", "parameters": {"definition": definition}}],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    path = target / forms.form_path("CommonForm.Форма")
    old = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    field["on"] = [{"event": "OnChange", "handler": "Изменено", "callType": "After"}]
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    result = editor.xml_read(path.read_bytes(), old.tag)
    added = editor.named(result)["f"].find("f:Events", editor.NS)
    assert added.findtext("f:Event", namespaces=editor.NS) == "Изменено"
    added.getparent().remove(added)
    assert editor.signature(result) == editor.signature(old)
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    before = path.read_bytes()
    field["title"] = "Подмена"
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), payload)
    assert path.read_bytes() == before


@pytest.mark.parametrize("operation,expected", [("form.edit", "Сумма: "), ("form.compile", "Сумма:")])
def test_edit_preserves_literal_input_title(tmp_path, operation, expected):
    target = tmp_path / "target"
    shutil.copytree(FIXTURES / "own-cfe", target)
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": operation,
                "target": "CommonForm.Форма",
                "parameters": {"definition": {"elements": [{"input": "Поле", "path": "Текст", "title": "Сумма: "}]}},
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    path = target / forms.form_path("CommonForm.Форма")
    tree = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    assert editor.named(tree)["поле"].findtext("f:Title/v8:item/v8:content", namespaces=editor.NS) == expected
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize("section", ["commands", "formEvents", "elementEvents", "elements"])
def test_edit_handler_repeat_with_inherited_namespace(tmp_path, section):
    target = tmp_path / "target"
    shutil.copytree(FIXTURES / "own-cfe", target)
    path = target / forms.form_path("CommonForm.Форма")
    original = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    root = etree.Element(original.tag, nsmap={**original.nsmap, "custom": "urn:custom"})
    root.attrib.update(original.attrib)
    root.text = original.text
    root.extend(original)
    path.write_bytes(editor.serialize_like(root, path.read_bytes()))
    entries = {
        "commands": {"name": "НоваяКоманда", "action": "Обработчик", "callType": "After"},
        "formEvents": {"name": "OnOpen", "handler": "Обработчик", "callType": "After"},
        "elementEvents": {"element": "Existing", "name": "Click", "handler": "Обработчик", "callType": "After"},
        "elements": {
            "input": "ПолеСобытия",
            "path": "Текст",
            "on": [{"event": "OnChange", "handler": "Обработчик", "callType": "After"}],
        },
    }
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.edit",
                "target": "CommonForm.Форма",
                "parameters": {"definition": {section: [entries[section]]}},
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    before = path.read_bytes()
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    assert path.read_bytes() == before
    assert editor.xml_read(before, original.tag).nsmap["custom"] == "urn:custom"


HELP_XML = (
    '﻿<?xml version="1.0" encoding="UTF-8"?>\n<Help xmlns="http://v8.1c.ru/8.3/xcf/extrnprops" '
    'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'version="2.20">\n\t<Page>ru</Page>\n</Help>'
).encode()


@pytest.mark.parametrize(
    "fault",
    [None, "unreviewed-bsl", "unreviewed-template", "stale-review", "unlisted-page", "help-xml", "form-help-only"],
)
def test_remove_external_form_keeps_owner_help_and_reviewed_code(tmp_path, fault):
    """Owner help is not a form dependency; surviving code and DCS need an explicit hash review."""
    import hashlib

    target, logical = rename_owner(tmp_path, "ExternalReport")
    setup = {
        "schemaVersion": 1,
        "operations": [{"op": "form.create", "target": logical, "parameters": {"name": "Удаляемая"}}],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), setup))
    help_xml = HELP_XML.replace(b"<Page>ru</Page>", b"<Unknown>ru</Unknown>") if fault == "help-xml" else HELP_XML
    (target / "Владелец/Ext/Help").mkdir(parents=True)
    (target / "Владелец/Ext/Help.xml").write_bytes(help_xml)
    (target / "Владелец/Ext/Help" / ("en.html" if fault == "unlisted-page" else "ru.html")).write_bytes(
        "<html><body>Справка: ФормаОтчета</body></html>".encode()
    )
    if fault == "form-help-only":
        # Help of another object is not the owner's help and stays opaque.
        (target / "Другой/Ext").mkdir(parents=True)
        (target / "Другой/Ext/Help.xml").write_bytes(HELP_XML)
    module = "Владелец/Ext/ObjectModule.bsl"
    template = "Владелец/Templates/Схема/Ext/Template.xml"
    (target / module).write_text("Функция СведенияОВнешнейОбработке() Экспорт\nКонецФункции\n", encoding="utf-8")
    (target / template).parent.mkdir(parents=True)
    (target / template).write_bytes(
        b'<DataCompositionSchema xmlns="http://v8.1c.ru/8.1/data-composition-system/schema"/>'
    )
    reviewed = [
        {
            "path": path,
            "sha256": hashlib.sha256((target / path).read_bytes()).hexdigest(),
            "reason": "нет ссылок на форму",
        }
        for path in (module, template)
        if not (fault == "unreviewed-bsl" and path == module or fault == "unreviewed-template" and path == template)
    ]
    if fault == "stale-review":
        reviewed[0]["sha256"] = "0" * 64
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.remove",
                "target": logical + ".Form.Удаляемая",
                "parameters": {"reviewedDependencies": reviewed},
            }
        ],
    }
    before = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    if fault:
        with pytest.raises(editor.Rejected):
            editor.plan_make(editor.Snapshot(target), payload)
        assert before == {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}
        return
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert {item["path"] for item in plan["writes"]} == {"Владелец.xml"} | {
        p for p in before if p.startswith("Владелец/Forms/")
    }
    assert editor.apply(target, None, plan) == "applied"
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    after = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert {p: data for p, data in before.items() if not p.startswith("Владелец/Forms/") and p != "Владелец.xml"} == {
        p: data for p, data in after.items() if p != "Владелец.xml"
    }
