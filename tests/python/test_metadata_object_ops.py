"""Document attributes through the shared ordered plan, without a live database."""

from tests.python.metadata_test_support import present  # noqa: I001 — runs first: skips the module without pytest, lxml, jsonschema
from typing import Any
import base64
import copy
import json
import re
import shutil
import uuid
from pathlib import Path

import lxml.etree as etree
import pytest

from scripts.python import (
    metadata as editor,
    metadata_borrow as borrow,
    metadata_object_ops as ops,
    metadata_ops,
    metadata_create as create,
)
from tests.python.test_metadata_catalog import RECORDED_CREATE_TYPES, RECORDED_REMOVE_TYPES


@pytest.fixture
def document_roots(tmp_path):
    fixtures = Path(__file__).parents[1] / "fixtures/managed-form-cli"
    source, target = tmp_path / "base", tmp_path / "extension"
    shutil.copytree(fixtures / "cf", source)
    shutil.copytree(fixtures / "own-cfe", target)
    config_path = source / "Configuration.xml"
    config = editor.metadata(config_path.read_bytes(), "Configuration")
    etree.SubElement(config.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}Document").text = "Документ"
    config_path.write_bytes(editor.serialize_like(config.getparent(), config_path.read_bytes()))
    root = etree.Element(f"{{{editor.MD}}}MetaDataObject", nsmap={None: editor.MD}, version="2.20")
    document = etree.SubElement(root, f"{{{editor.MD}}}Document", uuid=str(uuid.uuid4()))
    properties = etree.SubElement(document, f"{{{editor.MD}}}Properties")
    etree.SubElement(properties, f"{{{editor.MD}}}Name").text = "Документ"
    etree.SubElement(document, f"{{{editor.MD}}}ChildObjects")
    (source / "Documents").mkdir()
    (source / "Documents/Документ.xml").write_bytes(etree.tostring(root))
    return source, target


def request(source, attributes):
    return {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.borrow", "target": "Document.Документ", "parameters": {"baseRoot": str(source)}},
            {
                "op": "object.edit",
                "target": "Document.Документ",
                "parameters": {"definition": {"add": {"attributes": attributes}}},
            },
        ],
    }


@pytest.mark.parametrize(
    "value_type,primitive",
    [
        ("String(125)", "string"),
        ("Number(15,2,nonneg)", "decimal"),
        ("Boolean", "boolean"),
        ("Date", "dateTime"),
        ("DateTime", "dateTime"),
    ],
)
def test_document_attribute_plan_apply_and_preservation(document_roots, value_type, primitive):
    source, target = document_roots
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    payload = request(
        source, [{"name": "цф_Поле", "type": value_type, "synonym": "Новое поле", "comment": "Комментарий"}]
    )
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    document = editor.metadata((target / "Documents/Документ.xml").read_bytes(), "Document")
    attribute = borrow._member(document, "Attribute", "цф_Поле")
    assert editor.prop(attribute, "Comment") == "Комментарий"
    assert present(attribute).find("m:Properties/m:Type/v8:Type", editor.NS).text == "xs:" + primitive
    assert uuid.UUID(editor.identity(attribute)).version == 5
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    for path, data in before.items():
        if path.name != "Configuration.xml":
            assert path.read_bytes() == data


def test_type_union_preserves_fixed_string_and_generic_refs_through_plan_apply(tmp_path):
    target, logical = native_owner(tmp_path, "Catalog")
    value_type = (
        "String(36,fixed) + Number(15,2,nonneg) + Boolean + CatalogRef + DocumentRef + "
        "ChartOfAccountsRef + ChartOfCharacteristicTypesRef + ChartOfCalculationTypesRef + "
        "BusinessProcessRef + TaskRef + ExchangePlanRef + AnyRef"
    )
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"definition": {"add": {"attributes": [{"name": "Типы", "type": value_type}]}}},
            }
        ],
    }
    descriptor = target / "Catalogs/ВладелецТеста.xml"
    before = descriptor.read_bytes()
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert descriptor.read_bytes() == before
    assert editor.apply(target, None, plan) == "applied"
    owner = editor.metadata(descriptor.read_bytes(), "Catalog")
    attribute = borrow._member(owner, "Attribute", "Типы")
    typed = present(attribute).find("m:Properties/m:Type", editor.NS)
    assert typed.findtext("v8:StringQualifiers/v8:Length", namespaces=editor.NS) == "36"
    assert typed.findtext("v8:StringQualifiers/v8:AllowedLength", namespaces=editor.NS) == "Fixed"
    assert typed.findtext("v8:NumberQualifiers/v8:AllowedSign", namespaces=editor.NS) == "Nonnegative"
    assert [node.text for node in typed if node.tag == f"{{{editor.V8}}}Type"] == [
        "xs:string",
        "xs:decimal",
        "xs:boolean",
        "cfg:CatalogRef",
        "cfg:DocumentRef",
        "cfg:ChartOfAccountsRef",
        "cfg:ChartOfCharacteristicTypesRef",
        "cfg:ChartOfCalculationTypesRef",
        "cfg:BusinessProcessRef",
        "cfg:TaskRef",
        "cfg:ExchangePlanRef",
        "cfg:AnyRef",
    ]
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []

    before_unknown = descriptor.read_bytes()
    unknown = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {
                    "definition": {"add": {"attributes": [{"name": "НеизвестныйТип", "type": "UnknownRef"}]}}
                },
            }
        ],
    }
    with pytest.raises(editor.Rejected, match="Attribute type is not connected"):
        editor.plan_make(editor.Snapshot(target), unknown)
    assert descriptor.read_bytes() == before_unknown

    malformed = editor.metadata(before_unknown, "Catalog")
    malformed_attribute = borrow._member(malformed, "Attribute", "Типы")
    any_ref = next(
        node
        for node in present(malformed_attribute).findall("m:Properties/m:Type/v8:Type", editor.NS)
        if node.text == "cfg:AnyRef"
    )
    any_ref.tag = f"{{{editor.V8}}}TypeSet"
    descriptor.write_bytes(editor.serialize_like(malformed.getparent(), before_unknown))
    before_malformed_edit = descriptor.read_bytes()
    malformed_request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"definition": {"add": {"attributes": [{"name": "ЕщеОдно", "type": "String(10)"}]}}},
            }
        ],
    }
    # The malformed TypeSet is already present in the input snapshot. Unchanged
    # legacy Type nodes are preserved when another attribute is added.
    preserved_plan = editor.plan_make(editor.Snapshot(target), malformed_request)
    assert preserved_plan["writes"]
    assert descriptor.read_bytes() == before_malformed_edit


def recorded_edit_case(key):
    path = Path(__file__).parents[1] / "fixtures/metadata-edit/children.xml"
    root = etree.fromstring(path.read_bytes())
    cases = root.findall("m:Case", editor.NS)
    selected = [case for case in cases if case.get("key") == key]
    assert len(selected) == 1, key
    return selected[0]


def test_document_scalar_properties_match_recorded_xml():
    identity = str(uuid.uuid4())

    def content(node):
        return node.tag, dict(node.attrib), node.text if not len(node) else None, [content(child) for child in node]

    for value in ["String", "String(0)", "String(125)", "Number", "Number(15,2,nonneg)", "Boolean", "Date", "DateTime"]:
        definition = {"name": "НовоеПоле", "type": value, "flags": ["req", "index"]}
        expected = recorded_edit_case("scalar")[0]
        expected.set("uuid", identity)
        properties = expected.find("m:Properties", editor.NS)
        for replacement in list(recorded_edit_case("type/" + value)):
            properties.replace(properties.find(replacement.tag), replacement)
        assert content(ops.attribute_node(definition, identity)) == content(expected)


def test_ordered_attributes_use_current_snapshot(document_roots, monkeypatch):
    source, target = document_roots
    contexts = []
    normalize = metadata_ops.normalize_operation

    def record_context(operation, *, properties=None):
        if operation["op"] == "object.edit":
            contexts.append(properties)
        return normalize(operation, properties=properties)

    monkeypatch.setattr(metadata_ops, "normalize_operation", record_context)
    payload = request(source, [{"name": "Первый", "type": "Boolean"}])
    payload["operations"].append(
        {
            "op": "object.edit",
            "target": "Document.Документ",
            "parameters": {"operation": "add-attribute", "value": "Второй: Number(12,3) >> after Первый"},
        }
    )
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert "attributes.Первый" not in contexts[0]
    assert "attributes.Первый" in contexts[1]
    editor.apply(target, None, plan)
    document = editor.metadata((target / "Documents/Документ.xml").read_bytes(), "Document")
    attributes = document.findall("m:ChildObjects/m:Attribute", editor.NS)
    assert [editor.node_name(node) for node in attributes] == ["Первый", "Второй"]
    assert len({editor.identity(node) for node in attributes}) == 2
    assert "attributes.Второй" in ops.property_context(editor.Snapshot(target), "Document.Документ")
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize(
    "attribute",
    [
        {"name": "Ref", "type": "String"},
        {"name": "Номер", "type": "Number"},
        {"name": "Поле", "type": "Unsupported"},
        {"name": "Поле", "type": "Number(0,0)"},
        {"name": "Поле", "type": "Number(39,0)"},
        {"name": "Поле", "type": "Number(3,4)"},
        {"name": "Поле", "type": "Boolean", "after": "Отсутствует"},
        {"name": "Поле", "type": "Boolean", "flags": ["master"]},
        {"name": "Поле", "type": "Boolean", "flags": ["index", "indexadditional"]},
    ],
)
def test_invalid_attribute_has_no_disk_writes(document_roots, attribute):
    source, target = document_roots
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), request(source, [attribute]))
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


def test_changed_definition_conflicts_and_preserves_existing(document_roots):
    source, target = document_roots
    payload = request(source, [{"name": "Поле", "type": "Boolean"}])
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    before = (target / "Documents/Документ.xml").read_bytes()
    payload["operations"][1]["parameters"]["definition"]["add"]["attributes"][0]["type"] = "String"
    with pytest.raises(editor.Rejected, match="Existing attribute differs"):
        editor.plan_make(editor.Snapshot(target), payload)
    assert (target / "Documents/Документ.xml").read_bytes() == before


def test_attributes_keep_canonical_position_and_validate_repeat_anchor(document_roots):
    source, target = document_roots
    payload = request(source, [{"name": "Первый", "type": "Boolean"}])
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    path = target / "Documents/Документ.xml"
    document = editor.metadata(path.read_bytes(), "Document")
    children = document.find("m:ChildObjects", editor.NS)
    etree.SubElement(children, f"{{{editor.MD}}}Form").text = "Форма"
    path.write_bytes(editor.serialize_like(document.getparent(), path.read_bytes()))
    payload = request(source, [{"name": "Второй", "type": "Boolean"}])
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    document = editor.metadata(path.read_bytes(), "Document")
    assert [etree.QName(node).localname for node in document.find("m:ChildObjects", editor.NS)] == [
        "Attribute",
        "Attribute",
        "Form",
    ]
    attribute = payload["operations"][1]["parameters"]["definition"]["add"]["attributes"][0]
    attribute["after"] = "Отсутствует"
    with pytest.raises(editor.Rejected, match="anchor"):
        editor.plan_make(editor.Snapshot(target), payload)
    attribute["after"] = "Форма"
    with pytest.raises(editor.Rejected, match="anchor"):
        editor.plan_make(editor.Snapshot(target), payload)


def test_unborrowed_base_attribute_name_is_not_available(document_roots):
    source, target = document_roots
    path = source / "Documents/Документ.xml"
    base = editor.metadata(path.read_bytes(), "Document")
    attribute = etree.SubElement(
        base.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}Attribute", uuid=str(uuid.uuid4())
    )
    properties = etree.SubElement(attribute, f"{{{editor.MD}}}Properties")
    etree.SubElement(properties, f"{{{editor.MD}}}Name").text = "Комментарий"
    path.write_bytes(editor.serialize_like(base.getparent(), path.read_bytes()))
    with pytest.raises(editor.Rejected, match="reserved attribute name"):
        editor.plan_make(editor.Snapshot(target), request(source, [{"name": "комментарий", "type": "String"}]))
    assert not (target / "Documents/Документ.xml").exists()


def test_existing_adopted_document_requires_base_read_context(document_roots):
    source, target = document_roots
    payload = request(source, [{"name": "Поле", "type": "Boolean"}])
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    payload["operations"] = payload["operations"][1:]
    with pytest.raises(editor.Rejected, match="Exact base context required"):
        editor.plan_make(editor.Snapshot(target), payload)


def test_edit_ignores_unchanged_unresolved_type_but_checks_new_type(document_roots):
    source, target = document_roots
    borrow_request = {
        "schemaVersion": 1,
        "operations": [{"op": "object.borrow", "target": "Document.Документ", "parameters": {"baseRoot": str(source)}}],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), borrow_request))
    path = target / "Documents/Документ.xml"
    document = editor.metadata(path.read_bytes(), "Document")
    typed = etree.Element(f"{{{editor.MD}}}Type", nsmap={"v8": editor.V8, "cfg": borrow.CFG})
    etree.SubElement(typed, f"{{{editor.V8}}}Type").text = "cfg:CatalogRef.СтарыйТип"
    existing = ops.attribute_node({"name": "СтарыйТип"}, str(uuid.uuid4()), typed=typed)
    document.find("m:ChildObjects", editor.NS).insert(0, existing)
    path.write_bytes(editor.serialize_like(document.getparent(), path.read_bytes()))

    payload = request(source, [{"name": "НовыйТип", "type": "Boolean", "before": "СтарыйТип"}])
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert any(item["path"] == "Documents/Документ.xml" for item in plan["writes"])
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []

    changed = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.borrow", "target": "Document.Документ", "parameters": {"baseRoot": str(source)}},
            {
                "op": "object.edit",
                "target": "Document.Документ",
                "parameters": {
                    "definition": {"modify": {"attributes": {"СтарыйТип": {"type": "CatalogRef.НовыйТип"}}}}
                },
            },
        ],
    }
    with pytest.raises(editor.TypeDependencyRejected, match="Catalog.НовыйТип"):
        editor.plan_make(editor.Snapshot(target), changed)

    before = path.read_bytes()
    snapshot = editor.Snapshot(target)
    current = editor.metadata(present(snapshot.read("target", "Documents/Документ.xml")), "Document")
    old = borrow._member(current, "Attribute", "СтарыйТип")
    present(old).set("uuid", str(uuid.uuid4()))
    snapshot.stage("Documents/Документ.xml", editor.serialize_like(current.getparent(), before))
    with pytest.raises(editor.TypeDependencyRejected, match="Catalog.СтарыйТип"):
        editor.check_type_dependencies(snapshot)
    assert path.read_bytes() == before

    before = path.read_bytes()
    snapshot = editor.Snapshot(target)
    current = editor.metadata(present(snapshot.read("target", "Documents/Документ.xml")), "Document")
    typed = etree.Element(f"{{{editor.MD}}}Type", nsmap={"v8": editor.V8, "cfg": borrow.CFG})
    etree.SubElement(typed, f"{{{editor.V8}}}Type").text = "cfg:CatalogRef.СтарыйТип"
    added = ops.attribute_node({"name": "НовыйРеквизит"}, str(uuid.uuid4()), typed=typed)
    current.find("m:ChildObjects", editor.NS).insert(0, added)
    snapshot.stage("Documents/Документ.xml", editor.serialize_like(current.getparent(), before))
    with pytest.raises(editor.TypeDependencyRejected, match="Catalog.СтарыйТип"):
        editor.check_type_dependencies(snapshot)
    assert path.read_bytes() == before

    before = path.read_bytes()
    snapshot = editor.Snapshot(target)
    current = editor.metadata(present(snapshot.read("target", "Documents/Документ.xml")), "Document")
    old = borrow._member(current, "Attribute", "СтарыйТип")
    type_node = present(old).find("m:Properties/m:Type/v8:Type", editor.NS)
    replacement = etree.Element(f"{{{editor.V8}}}Type", nsmap={"v8": editor.V8, "cfg": editor.XS})
    replacement.text = type_node.text
    type_node.getparent().replace(type_node, replacement)
    serialized = editor.serialize_like(current.getparent(), before)
    assert borrow.CFG.encode() in serialized
    serialized = serialized.replace(borrow.CFG.encode(), editor.XS.encode())
    remapped = editor.metadata(serialized, "Document")
    remapped_type = present(borrow._member(remapped, "Attribute", "СтарыйТип")).find(
        "m:Properties/m:Type/v8:Type", editor.NS
    )
    original = editor.metadata(before, "Document")
    original_type = present(borrow._member(original, "Attribute", "СтарыйТип")).find(
        "m:Properties/m:Type/v8:Type", editor.NS
    )
    assert remapped_type.nsmap["cfg"] == editor.XS
    assert editor.signature(remapped_type) != editor.signature(original_type)
    snapshot.stage("Documents/Документ.xml", serialized)
    with pytest.raises(editor.Rejected):
        editor.check_type_dependencies(snapshot)
    assert path.read_bytes() == before


def native_owner(tmp_path, kind, *dependencies):
    """Create an own owner; ``dependencies`` are explicit referenced objects.

    Automatic adoption of type dependencies is disabled, so a test that adds a
    reference type creates the referenced object beforehand. External artifacts
    have no configuration tree and ignore them.
    """
    target = tmp_path / "target"
    fixtures = Path(__file__).parents[1] / "fixtures/managed-form-cli"
    if kind in {"ExternalReport", "ExternalDataProcessor"}:
        fixture, name = ("erf", "ТестовыйОтчет") if kind == "ExternalReport" else ("epf", "ТестоваяОбработка")
        shutil.copytree(fixtures / fixture, target)
    else:
        name = "ВладелецТеста"
        shutil.copytree(fixtures / "own-cfe", target)
        payload = {
            "schemaVersion": 1,
            "operations": [
                {
                    "op": "object.create",
                    "target": kind + "." + name,
                    "parameters": {"definition": {"type": kind, "name": name}},
                }
            ],
        }
        payload["operations"] += [
            {
                "op": "object.create",
                "target": reference,
                "parameters": {"definition": {"type": reference.split(".")[0], "name": reference.split(".")[1]}},
            }
            for reference in dependencies
        ]
        assert editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload)) == "applied"
    return target, kind + "." + name


def test_rename_dependency_shape_accepts_type_reduction_mode_only_on_standard_attribute():
    def catalog_root():
        data = create.render_object({"type": "Catalog", "name": "Проверка"}, str(uuid.uuid4()), {})
        return editor.xml_read(data, f"{{{editor.MD}}}MetaDataObject")

    root = catalog_root()
    standard = root.find(".//xr:StandardAttribute", {**editor.NS, "xr": borrow.XR})
    etree.SubElement(standard, f"{{{borrow.XR}}}TypeReductionMode").text = "TransformValues"
    ops.rename_descriptor_shape(root)

    invalid_value = catalog_root()
    standard = invalid_value.find(".//xr:StandardAttribute", {**editor.NS, "xr": borrow.XR})
    etree.SubElement(standard, f"{{{borrow.XR}}}TypeReductionMode").text = "Unexpected"
    with pytest.raises(editor.Rejected, match="Invalid standard attribute TypeReductionMode"):
        ops.rename_descriptor_shape(invalid_value)

    invalid_position = catalog_root()
    children = invalid_position.find(".//m:ChildObjects", editor.NS)
    etree.SubElement(children, f"{{{borrow.XR}}}TypeReductionMode").text = "TransformValues"
    with pytest.raises(editor.Rejected, match="Unsupported rename dependency structure: TypeReductionMode"):
        ops.rename_descriptor_shape(invalid_position)


def test_rename_dependency_shape_accepts_line_number_length_only_on_tabular_section_properties():
    def catalog_root():
        data = create.render_object(
            {"type": "Catalog", "name": "Проверка", "tabularSections": [{"name": "Строки"}]}, str(uuid.uuid4()), {}
        )
        return editor.xml_read(data, f"{{{editor.MD}}}MetaDataObject")

    root = catalog_root()
    properties = root.find(".//m:TabularSection/m:Properties", editor.NS)
    etree.SubElement(properties, f"{{{editor.MD}}}LineNumberLength").text = "9"
    ops.rename_descriptor_shape(root)

    invalid_value = catalog_root()
    properties = invalid_value.find(".//m:TabularSection/m:Properties", editor.NS)
    etree.SubElement(properties, f"{{{editor.MD}}}LineNumberLength").text = "nine"
    with pytest.raises(editor.Rejected, match="Invalid tabular section LineNumberLength"):
        ops.rename_descriptor_shape(invalid_value)

    invalid_position = catalog_root()
    properties = invalid_position.find(".//m:Properties", editor.NS)
    etree.SubElement(properties, f"{{{editor.MD}}}LineNumberLength").text = "9"
    with pytest.raises(editor.Rejected, match="Unsupported rename dependency structure: LineNumberLength"):
        ops.rename_descriptor_shape(invalid_position)


def test_rename_dependency_shape_accepts_type_id_only_on_attribute_type():
    def catalog_root():
        data = create.render_object(
            {"type": "Catalog", "name": "Проверка", "attributes": [{"name": "Счет", "type": "String(10)"}]},
            str(uuid.uuid4()),
            {},
        )
        return editor.xml_read(data, f"{{{editor.MD}}}MetaDataObject")

    root = catalog_root()
    typed = root.find(".//m:ChildObjects/m:Attribute/m:Properties/m:Type", editor.NS)
    etree.SubElement(typed, f"{{{editor.V8}}}TypeId").text = "6f58a5c7-f511-498f-abeb-390cf5afab39"
    ops.rename_descriptor_shape(root)

    invalid_value = catalog_root()
    typed = invalid_value.find(".//m:ChildObjects/m:Attribute/m:Properties/m:Type", editor.NS)
    etree.SubElement(typed, f"{{{editor.V8}}}TypeId").text = "not-a-uuid"
    with pytest.raises(editor.Rejected, match="Invalid attribute TypeId"):
        ops.rename_descriptor_shape(invalid_value)

    invalid_position = catalog_root()
    typed = invalid_position.find("m:Catalog/m:Properties", editor.NS)
    etree.SubElement(typed, f"{{{editor.V8}}}TypeId").text = "6f58a5c7-f511-498f-abeb-390cf5afab39"
    with pytest.raises(editor.Rejected, match="Unsupported rename dependency structure: TypeId"):
        ops.rename_descriptor_shape(invalid_position)


def test_scheduled_job_schedule_xml_is_parsed_as_a_known_dependency_shape():
    xml = (
        b'<JobSchedule xmlns="http://v8.1c.ru/8.3/xcf/extrnprops" '
        b'xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" version="2.20">'
        b'<Schedule BeginDate="0001-01-01" EndDate="0001-01-01" BeginTime="00:00:00" '
        b'EndTime="00:00:00" CompletionTime="00:00:00" CompletionInterval="0" '
        b'RepeatPeriodInDay="300" RepeatPause="0" WeekDayInMonth="0" DayInMonth="0" '
        b'WeeksPeriod="1" DaysRepeatPeriod="1"><ent:WeekDays>1 2 3 4 5 6 7</ent:WeekDays>'
        b"<ent:Months>1 2 3 4 5 6 7 8 9 10 11 12</ent:Months></Schedule></JobSchedule>"
    )
    assert (
        ops.read_job_schedule(xml, "ScheduledJobs/Job/Ext/Schedule.xml").tag
        == "{http://v8.1c.ru/8.3/xcf/extrnprops}JobSchedule"
    )
    invalid = xml.replace(b"<ent:Months>", b"<ent:Unexpected>").replace(b"</ent:Months>", b"</ent:Unexpected>")
    with pytest.raises(editor.Rejected, match="Unsupported ScheduledJob Schedule.xml"):
        ops.read_job_schedule(invalid, "ScheduledJobs/Job/Ext/Schedule.xml")


def rename_owner(tmp_path, kind):
    target = tmp_path / "target"
    target.mkdir()
    if kind in {"ExternalReport", "ExternalDataProcessor"}:
        base_kind = kind.removeprefix("External")
        owner = editor.metadata(
            create.render_object({"type": base_kind, "name": "Владелец"}, str(uuid.uuid4()), {}), base_kind
        )
        owner.tag = f"{{{editor.MD}}}{kind}"
        (target / "Владелец.xml").write_bytes(etree.tostring(owner.getparent()))
        return target, kind + ".Владелец"
    original = (Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe/Configuration.xml").read_bytes()
    config = editor.metadata(original, "Configuration")
    config.find("m:ChildObjects", editor.NS)[:] = []
    (target / "Configuration.xml").write_bytes(editor.serialize_like(config.getparent(), original))
    logical = kind + ".Владелец"
    payload = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.create", "target": logical, "parameters": {"definition": {"type": kind, "name": "Владелец"}}}
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    return target, logical


def legacy_fragment(tmp_path):
    target = tmp_path / "legacy-main-config"
    target.mkdir()
    module_name = "Демо_ПрототипОбменаСервер"
    module = editor.metadata(
        create.render_object(
            {
                "type": "CommonModule",
                "name": module_name,
                "server": True,
                "serverCall": True,
                "privileged": True,
            },
            str(uuid.uuid4()),
            {},
        ),
        "CommonModule",
    )
    module_path = target / "CommonModules" / (module_name + ".xml")
    module_path.parent.mkdir()
    module_path.write_bytes(etree.tostring(module.getparent(), xml_declaration=True, encoding="UTF-8"))
    module_uuid = editor.identity(module)
    bsl_path = target / "CommonModules" / module_name / "Ext/Module.bsl"
    bsl_path.parent.mkdir(parents=True)
    bsl_bytes = f"// {module_name}.Вызвать();\r\n".encode()
    bsl_path.write_bytes(bsl_bytes)

    job = create.render_object(
        {
            "type": "ScheduledJob",
            "name": "Демо_ПрямойОбменСистем",
            "methodName": f"CommonModule.{module_name}.ВыполнитьПрямойОбменПоРасписанию",
        },
        str(uuid.uuid4()),
        {},
    )
    job_path = target / "ScheduledJobs/Демо_ПрямойОбменСистем.xml"
    job_path.parent.mkdir()
    job_path.write_bytes(job)
    manifest = {
        "schemaVersion": 1,
        "packageId": "test.legacy-fragment",
        "packageVersion": 1,
        "entries": [
            {
                "kind": "CommonModule",
                "name": module_name,
                "root": "CommonModules/" + module_name,
                "operation": "add-or-update",
            },
            {
                "kind": "ScheduledJob",
                "name": "Демо_ПрямойОбменСистем",
                "root": "ScheduledJobs/Демо_ПрямойОбменСистем",
                "operation": "add-or-update",
            },
        ],
    }
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target, module_name, module_uuid, bsl_path.relative_to(target).as_posix(), bsl_bytes


def test_manifest_fragment_common_module_rename_updates_registration_and_metadata_refs(tmp_path):
    target, old_name, module_uuid, bsl_path, bsl_bytes = legacy_fragment(tmp_path)
    new_name = "Демо_ОбменСистемПолныеПрава"
    request_payload = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.rename", "target": "CommonModule." + old_name, "parameters": {"name": new_name}},
            {
                "op": "object.edit",
                "target": "CommonModule." + new_name,
                "parameters": {"definition": {"modify": {"properties": {"ServerCall": False}}}},
            },
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), request_payload)
    assert {write["path"] for write in plan["writes"]} == {
        "CommonModules/" + old_name + ".xml",
        "CommonModules/" + new_name + ".xml",
        "CommonModules/" + old_name + "/Ext/Module.bsl",
        "CommonModules/" + new_name + "/Ext/Module.bsl",
        "ScheduledJobs/Демо_ПрямойОбменСистем.xml",
        "manifest.json",
    }
    assert plan["checks"]["dependencies"] == "pending"
    assert any(
        item["path"] == "CommonModules/" + new_name + "/Ext/Module.bsl"
        and item["targets"] == ["CommonModule." + new_name]
        for item in plan["pendingDependencies"]
    )
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"

    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    assert any(
        item["kind"] == "CommonModule" and item["name"] == new_name and item["root"] == "CommonModules/" + new_name
        for item in manifest["entries"]
    )
    assert not (target / ("CommonModules/" + old_name + ".xml")).exists()
    _, renamed, path, _ = ops.read_object(editor.Snapshot(target), "CommonModule." + new_name)
    assert path == "CommonModules/" + new_name + ".xml"
    assert editor.identity(renamed) == module_uuid
    assert editor.prop(renamed, "Privileged") == "true"
    assert editor.prop(renamed, "ServerCall") == "false"
    assert (target / ("CommonModules/" + new_name + "/Ext/Module.bsl")).read_bytes() == bsl_bytes
    scheduled_job = editor.metadata((target / "ScheduledJobs/Демо_ПрямойОбменСистем.xml").read_bytes(), "ScheduledJob")
    assert editor.prop(scheduled_job, "MethodName") == f"CommonModule.{new_name}.ВыполнитьПрямойОбменПоРасписанию"
    assert editor.verify_objects(editor.Snapshot(target), ["CommonModule." + new_name])["code"] == 0


@pytest.mark.parametrize(
    "kind",
    [
        *borrow._OBJECT_KINDS,
        "Report",
        "DataProcessor",
        "Enum",
        *ops.REGISTER_KINDS,
        "DocumentJournal",
        "Constant",
        "ExternalReport",
        "ExternalDataProcessor",
    ],
)
@pytest.mark.parametrize("registration", ["Form", "Command"])
def test_edit_form_registration_only_owner_matrix(tmp_path, kind, registration):
    target, logical = rename_owner(tmp_path, kind)
    _, _, owner_path, _ = ops.read_object(editor.Snapshot(target), logical)
    before = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}

    def payload(action):
        return {
            "schemaVersion": 1,
            "operations": [
                {
                    "op": "object.edit",
                    "target": logical,
                    "parameters": {"operation": action + "-" + registration.lower(), "value": "ФормаЭлемента"},
                }
            ],
        }

    if kind == "Constant" and registration == "Command":
        with pytest.raises(editor.Rejected):
            editor.plan_make(editor.Snapshot(target), payload("add"))
        assert before == {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}
        return
    add_plan = editor.plan_make(editor.Snapshot(target), payload("add"))
    assert [item["path"] for item in add_plan["writes"]] == [owner_path]
    editor.apply(target, None, add_plan)
    assert editor.plan_make(editor.Snapshot(target), payload("add"))["writes"] == []
    _, owner, _, _ = ops.read_object(editor.Snapshot(target), logical)
    assert [item.text for item in owner.findall("m:ChildObjects/m:" + registration, editor.NS)] == ["ФормаЭлемента"]
    assert {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()} == set(before)
    remove_plan = editor.plan_make(editor.Snapshot(target), payload("remove"))
    assert [item["path"] for item in remove_plan["writes"]] == [owner_path]
    editor.apply(target, None, remove_plan)
    assert editor.plan_make(editor.Snapshot(target), payload("remove"))["writes"] == []
    assert all((target / p).read_bytes() == data for p, data in before.items() if p != owner_path)


@pytest.mark.parametrize("default", [False, True])
def test_edit_form_registration_preserves_files_and_default(tmp_path, default):
    target, logical = rename_owner(tmp_path, "Catalog")
    setup = {
        "schemaVersion": 1,
        "operations": [
            {"op": "form.create", "target": logical, "parameters": {"name": "ФормаЭлемента", "setDefault": default}}
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), setup))
    (target / "Catalogs/Владелец/Forms/ФормаЭлемента/Ext/Form/Module.bsl").write_text("Обработчик();", encoding="utf-8")
    if not default:
        _, owner, path, data = ops.read_object(editor.Snapshot(target), logical)
        owner.find("m:Properties/m:DefaultObjectForm", editor.NS).text = None
        (target / path).write_bytes(editor.serialize_like(owner.getparent(), data))
    before = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}

    def payload(action):
        return {
            "schemaVersion": 1,
            "operations": [
                {
                    "op": "object.edit",
                    "target": logical,
                    "parameters": {"definition": {action: {"forms": ["ФормаЭлемента"]}}},
                }
            ],
        }

    assert editor.plan_make(editor.Snapshot(target), payload("add"))["writes"] == []
    if default:
        with pytest.raises(editor.Rejected):
            editor.plan_make(editor.Snapshot(target), payload("remove"))
        assert all((target / p).read_bytes() == data for p, data in before.items())
    else:
        plan = editor.plan_make(editor.Snapshot(target), payload("remove"))
        assert [item["path"] for item in plan["writes"]] == ["Catalogs/Владелец.xml"]
        editor.apply(target, None, plan)
        assert editor.plan_make(editor.Snapshot(target), payload("remove"))["writes"] == []
        assert all((target / p).read_bytes() == data for p, data in before.items() if p != "Catalogs/Владелец.xml")
        editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload("add")))
        assert editor.plan_make(editor.Snapshot(target), payload("add"))["writes"] == []


@pytest.mark.parametrize("action", ["add", "remove"])
@pytest.mark.parametrize("fault", ["attribute", "tail", "case", "duplicate"])
@pytest.mark.parametrize("registration", ["Form", "Command"])
def test_edit_form_registration_rejects_ambiguous_node(tmp_path, action, fault, registration):
    target, logical = rename_owner(tmp_path, "Catalog")
    _, owner, path, data = ops.read_object(editor.Snapshot(target), logical)
    children = owner.find("m:ChildObjects", editor.NS)
    node = etree.SubElement(children, f"{{{editor.MD}}}{registration}")
    node.text = "форма" if fault == "case" else "Форма"
    if fault == "attribute":
        node.set("unknown", "opaque")
    elif fault == "tail":
        node.tail = "opaque"
    elif fault == "duplicate":
        etree.SubElement(children, node.tag).text = node.text
    (target / path).write_bytes(editor.serialize_like(owner.getparent(), data))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"operation": action + "-" + registration.lower(), "value": "Форма"},
            }
        ],
    }
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


@pytest.mark.parametrize("set_reference", [False, True])
def test_edit_form_registration_checks_final_definition(tmp_path, set_reference):
    target, logical = rename_owner(tmp_path, "Catalog")
    setup = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.edit", "target": logical, "parameters": {"operation": "add-form", "value": "Форма"}}
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), setup))
    _, owner, path, data = ops.read_object(editor.Snapshot(target), logical)
    reference = logical + ".Form.Форма"
    owner.find("m:Properties/m:DefaultObjectForm", editor.NS).text = None if set_reference else reference
    (target / path).write_bytes(editor.serialize_like(owner.getparent(), data))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {
                    "definition": {
                        "remove": {"forms": ["Форма"]},
                        "modify": {"properties": {"DefaultObjectForm": reference if set_reference else ""}},
                    }
                },
            }
        ],
    }
    if set_reference:
        with pytest.raises(editor.Rejected):
            editor.plan_make(editor.Snapshot(target), payload)
        assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    else:
        editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
        _, result, _, _ = ops.read_object(editor.Snapshot(target), logical)
        assert not result.findall("m:ChildObjects/m:Form", editor.NS)
        assert not editor.prop(result, "DefaultObjectForm")
        assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize("referenced", [False, True])
def test_edit_command_registration_preserves_files(tmp_path, referenced):
    target, logical = rename_owner(tmp_path, "Catalog")

    def payload(action):
        return {
            "schemaVersion": 1,
            "operations": [
                {
                    "op": "object.edit",
                    "target": logical,
                    "parameters": {"definition": {action: {"commands": ["Действие"]}}},
                }
            ],
        }

    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload("add")))
    folder = target / "Catalogs/Владелец/Commands"
    module = folder / "Действие/Ext/CommandModule.bsl"
    module.parent.mkdir(parents=True)
    module.write_bytes("Обработчик();".encode())
    descriptor = etree.Element(f"{{{editor.MD}}}MetaDataObject", nsmap={None: editor.MD}, version="2.17")
    command = etree.SubElement(descriptor, f"{{{editor.MD}}}Command", uuid=str(uuid.uuid4()))
    props = etree.SubElement(command, f"{{{editor.MD}}}Properties")
    etree.SubElement(props, f"{{{editor.MD}}}Name").text = "Действие"
    (folder / "Действие.xml").write_bytes(etree.tostring(descriptor))
    if referenced:
        _, owner, path, data = ops.read_object(editor.Snapshot(target), logical)
        owner.find("m:Properties/m:DefaultObjectForm", editor.NS).text = logical + ".Command.Действие"
        (target / path).write_bytes(editor.serialize_like(owner.getparent(), data))
    before = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert editor.plan_make(editor.Snapshot(target), payload("add"))["writes"] == []
    if referenced:
        with pytest.raises(editor.Rejected):
            editor.plan_make(editor.Snapshot(target), payload("remove"))
        assert all((target / p).read_bytes() == data for p, data in before.items())
    else:
        plan = editor.plan_make(editor.Snapshot(target), payload("remove"))
        assert [item["path"] for item in plan["writes"]] == ["Catalogs/Владелец.xml"]
        editor.apply(target, None, plan)
        assert editor.plan_make(editor.Snapshot(target), payload("remove"))["writes"] == []
        assert all((target / p).read_bytes() == data for p, data in before.items() if p != "Catalogs/Владелец.xml")


@pytest.mark.parametrize("kind", metadata_ops.OBJECT_TYPES)
@pytest.mark.parametrize("keep_files", [False, True])
def test_remove_object_created_types_exact_snapshot(tmp_path, kind, keep_files):
    target, logical = rename_owner(tmp_path, kind)
    path = borrow.DIRECTORIES[kind] + "/Владелец.xml"
    folder = path.removesuffix(".xml") + "/"
    before = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "object.remove", "target": logical, "parameters": {"keepFiles": keep_files}}],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    removed = set() if keep_files else {p for p in before if p == path or p.startswith(folder)}
    assert {item["path"] for item in plan["writes"]} == removed | {"Configuration.xml"}
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    config = editor.metadata((target / "Configuration.xml").read_bytes(), "Configuration")
    assert not borrow._linked(borrow._registrations(config), kind, "Владелец")
    assert all(not (target / p).exists() for p in removed)
    assert all(
        (target / p).read_bytes() == data for p, data in before.items() if p not in removed | {"Configuration.xml"}
    )
    if keep_files:
        with pytest.raises(editor.Rejected):
            editor.plan_make(editor.Snapshot(target), payload)
    else:
        assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


def test_remove_object_dependency_reader_accepts_tabular_section_line_number_length(tmp_path):
    target, logical = rename_owner(tmp_path, "Catalog")
    other_name = "ДругойКаталог"
    other_data = create.render_object(
        {"type": "Catalog", "name": other_name, "tabularSections": [{"name": "Строки"}]}, str(uuid.uuid4()), {}
    )
    other_root = editor.xml_read(other_data, f"{{{editor.MD}}}MetaDataObject")
    properties = other_root.find(".//m:TabularSection/m:Properties", editor.NS)
    etree.SubElement(properties, f"{{{editor.MD}}}LineNumberLength").text = "9"
    other_path = target / "Catalogs" / (other_name + ".xml")
    other_path.write_bytes(etree.tostring(other_root, encoding="UTF-8", xml_declaration=True))
    config_path = target / "Configuration.xml"
    config_data = config_path.read_bytes()
    config = editor.metadata(config_data, "Configuration")
    etree.SubElement(config.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}Catalog").text = other_name
    config_path.write_bytes(editor.serialize_like(config.getparent(), config_data))

    before = {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}
    request = {"schemaVersion": 1, "operations": [{"op": "object.remove", "target": logical, "parameters": {}}]}
    plan = editor.plan_make(editor.Snapshot(target), request)

    expected = {
        path.relative_to(target).as_posix()
        for path in before
        if path.relative_to(target).as_posix() == "Configuration.xml"
        or path.relative_to(target).as_posix().startswith("Catalogs/Владелец")
    }
    assert {write["path"] for write in plan["writes"]} == expected
    assert before == {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}


def test_remove_object_dependency_reader_accepts_attribute_type_id(tmp_path):
    target, logical = rename_owner(tmp_path, "Catalog")
    other_name = "ДругойКаталог"
    other_data = create.render_object(
        {"type": "Catalog", "name": other_name, "attributes": [{"name": "Счет", "type": "String(10)"}]},
        str(uuid.uuid4()),
        {},
    )
    other_root = editor.xml_read(other_data, f"{{{editor.MD}}}MetaDataObject")
    typed = other_root.find(".//m:ChildObjects/m:Attribute/m:Properties/m:Type", editor.NS)
    etree.SubElement(typed, f"{{{editor.V8}}}TypeId").text = "6f58a5c7-f511-498f-abeb-390cf5afab39"
    other_path = target / "Catalogs" / (other_name + ".xml")
    other_path.write_bytes(etree.tostring(other_root, encoding="UTF-8", xml_declaration=True))
    config_path = target / "Configuration.xml"
    config_data = config_path.read_bytes()
    config = editor.metadata(config_data, "Configuration")
    etree.SubElement(config.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}Catalog").text = other_name
    config_path.write_bytes(editor.serialize_like(config.getparent(), config_data))

    before = {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}
    request = {"schemaVersion": 1, "operations": [{"op": "object.remove", "target": logical, "parameters": {}}]}
    plan = editor.plan_make(editor.Snapshot(target), request)

    expected = {
        path.relative_to(target).as_posix()
        for path in before
        if path.relative_to(target).as_posix() == "Configuration.xml"
        or path.relative_to(target).as_posix().startswith("Catalogs/Владелец")
    }
    assert {write["path"] for write in plan["writes"]} == expected
    assert before == {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}

    removed = editor.xml_read((target / "Catalogs/Владелец.xml").read_bytes(), f"{{{editor.MD}}}MetaDataObject")
    generated_id = removed.findtext(f".//{{{borrow.XR}}}GeneratedType/{{{borrow.XR}}}TypeId")
    assert generated_id
    typed.find(f"{{{editor.V8}}}TypeId").text = generated_id
    other_path.write_bytes(etree.tostring(other_root, encoding="UTF-8", xml_declaration=True))
    with pytest.raises(editor.Rejected, match="Cannot remove referenced UUID"):
        editor.plan_make(editor.Snapshot(target), request)


def test_remove_reads_reviewed_predefined_data_and_keeps_reference_guard(tmp_path):
    target, logical = rename_owner(tmp_path, "Catalog")
    relative = "Catalogs/Другой/Ext/Predefined.xml"
    path = target / relative
    path.parent.mkdir(parents=True)
    namespace = "http://v8.1c.ru/8.3/xcf/predef"
    root = etree.Element(f"{{{namespace}}}PredefinedData", version="2.20")
    item = etree.SubElement(root, f"{{{namespace}}}Item")
    typed = etree.SubElement(item, f"{{{namespace}}}Type")
    value = etree.SubElement(typed, f"{{{editor.V8}}}Type", nsmap={"cfg": borrow.CFG})
    value.text = "xs:string"
    path.write_bytes(etree.tostring(root))
    request = {"schemaVersion": 1, "operations": [{"op": "object.remove", "target": logical, "parameters": {}}]}
    with pytest.raises(editor.Rejected, match="Cannot prove dependencies in opaque artifact"):
        editor.plan_make(editor.Snapshot(target), request)
    request["operations"][0]["parameters"]["reviewedDependencies"] = [
        {"path": relative, "sha256": editor.digest(path.read_bytes()), "reason": "Reviewed predefined values"}
    ]
    assert editor.plan_make(editor.Snapshot(target), request)["writes"]
    value.text = "cfg:CatalogRef.Владелец"
    path.write_bytes(etree.tostring(root))
    request["operations"][0]["parameters"]["reviewedDependencies"][0]["sha256"] = editor.digest(path.read_bytes())
    with pytest.raises(editor.Rejected, match="Cannot remove referenced metadata type"):
        editor.plan_make(editor.Snapshot(target), request)


def test_dependency_shape_accepts_configuration_property_state(tmp_path):
    target, _ = rename_owner(tmp_path, "Catalog")
    root = editor.xml_read((target / "Configuration.xml").read_bytes(), f"{{{editor.MD}}}MetaDataObject")
    internal = root[0].find(f"{{{editor.MD}}}InternalInfo")
    assert internal is not None
    state = etree.SubElement(internal, f"{{{borrow.XR}}}PropertyState")
    etree.SubElement(state, f"{{{borrow.XR}}}Property").text = "Name"
    etree.SubElement(state, f"{{{borrow.XR}}}State").text = "Extended"
    ops.rename_descriptor_shape(root)
    etree.SubElement(state, f"{{{borrow.XR}}}Unknown")
    with pytest.raises(editor.Rejected, match="Unknown configuration property state structure"):
        ops.rename_descriptor_shape(root)


@pytest.mark.parametrize("keep_files", [False, True])
@pytest.mark.parametrize(
    "fault",
    [
        "reference",
        "bsl",
        "unknown",
        "template",
        "registration",
        "descriptor",
        "registration-attribute",
        "registration-tail",
    ],
)
def test_remove_object_rejects_dependency_or_mismatch(tmp_path, keep_files, fault):
    target, logical = rename_owner(tmp_path, "Catalog")
    if fault == "reference":
        payload = {
            "schemaVersion": 1,
            "operations": [
                {
                    "op": "object.create",
                    "target": "Document.Ссылка",
                    "parameters": {
                        "definition": {
                            "type": "Document",
                            "name": "Ссылка",
                            "attributes": [{"name": "Поле", "type": "CatalogRef.Владелец"}],
                        }
                    },
                }
            ],
        }
        editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    elif fault == "bsl":
        (target / "Module.bsl").write_text("НепроверенныйКод();", encoding="utf-8")
    elif fault == "unknown":
        (target / "Unknown.xml").write_bytes(b"<Unknown/>")
    elif fault == "template":
        directory = target / "Catalogs/Владелец/Templates"
        directory.mkdir(parents=True)
        (directory / "Макет.bin").write_bytes(b"opaque")
    elif fault.startswith("registration"):
        path = target / "Configuration.xml"
        config = editor.metadata(path.read_bytes(), "Configuration")
        children = config.find("m:ChildObjects", editor.NS)
        if fault == "registration":
            children[:] = []
        elif fault == "registration-attribute":
            children[0].set("unknown", "opaque")
        else:
            children[0].tail = "opaque"
        path.write_bytes(editor.serialize_like(config.getparent(), path.read_bytes()))
    else:
        (target / "Catalogs/Владелец.xml").unlink()
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "object.remove", "target": logical, "parameters": {"keepFiles": keep_files}}],
    }
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


def test_remove_object_accepts_only_currently_reviewed_opaque_dependencies(tmp_path):
    target, logical = rename_owner(tmp_path, "Catalog")
    dependency = target / "CommonModules/Посторонний/Ext/Module.bsl"
    dependency.parent.mkdir(parents=True)
    dependency.write_text("НепроверенныйКод();", encoding="utf-8")
    relative = dependency.relative_to(target).as_posix()
    item = {"path": relative, "sha256": editor.digest(dependency.read_bytes()), "reason": "reviewed"}
    opaque = target / "DataProcessors/Посторонний/Ext/Template.txt"
    opaque.parent.mkdir(parents=True)
    opaque.write_bytes(b"opaque")
    opaque_item = {
        "path": opaque.relative_to(target).as_posix(),
        "sha256": editor.digest(opaque.read_bytes()),
        "reason": "reviewed",
    }
    request = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.remove", "target": logical, "parameters": {"reviewedDependencies": [item, opaque_item]}}
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert relative not in {write["path"] for write in plan["writes"]}
    with pytest.raises(editor.Rejected):
        editor.plan_make(
            editor.Snapshot(target),
            {"schemaVersion": 1, "operations": [{"op": "object.remove", "target": logical, "parameters": {}}]},
        )
    with pytest.raises(editor.Rejected):
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [
                    {"op": "object.remove", "target": logical, "parameters": {"reviewedDependencies": [item]}}
                ],
            },
        )

    for replacement in (
        {**item, "sha256": "0" * 64},
        {**item, "reason": " "},
        {**item, "path": "CommonModules/Нет/Ext/Module.bsl", "sha256": item["sha256"]},
    ):
        bad = {
            "schemaVersion": 1,
            "operations": [
                {
                    "op": "object.remove",
                    "target": logical,
                    "parameters": {"reviewedDependencies": [replacement, opaque_item]},
                }
            ],
        }
        with pytest.raises(editor.Rejected):
            editor.plan_make(editor.Snapshot(target), bad)

    duplicate = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.remove",
                "target": logical,
                "parameters": {"reviewedDependencies": [item, opaque_item, {**item, "reason": "second review"}]},
            }
        ],
    }
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), duplicate)
    extraneous = {
        "path": "Configuration.xml",
        "sha256": editor.digest((target / "Configuration.xml").read_bytes()),
        "reason": "not opaque",
    }
    with pytest.raises(editor.Rejected, match="Extraneous reviewed dependency"):
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [
                    {
                        "op": "object.remove",
                        "target": logical,
                        "parameters": {"reviewedDependencies": [item, opaque_item, extraneous]},
                    }
                ],
            },
        )


def test_remove_object_review_does_not_bypass_managed_form_references(tmp_path):
    target, logical = rename_owner(tmp_path, "Catalog")
    other = "Catalog.Другой"
    editor.apply(
        target,
        None,
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [
                    {
                        "op": "object.create",
                        "target": other,
                        "parameters": {"definition": {"type": "Catalog", "name": "Другой"}},
                    },
                    {
                        "op": "form.create",
                        "target": other,
                        "parameters": {"name": "Форма", "purpose": "List", "setDefault": False},
                    },
                ],
            },
        ),
    )
    path = target / "Catalogs/Другой/Forms/Форма/Ext/Form.xml"
    body = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    attribute = etree.SubElement(
        body.find("f:Attributes", editor.NS), f"{{{editor.FORM}}}Attribute", name="Ссылка", id="900"
    )
    typed = etree.SubElement(attribute, f"{{{editor.FORM}}}Type")
    etree.SubElement(typed, f"{{{editor.V8}}}Type", nsmap={"cfg": borrow.CFG}).text = "cfg:CatalogRef.Владелец"
    path.write_bytes(editor.serialize_like(body, path.read_bytes()))
    item = {
        "path": path.relative_to(target).as_posix(),
        "sha256": editor.digest(path.read_bytes()),
        "reason": "reviewed",
    }
    request = {
        "schemaVersion": 1,
        "operations": [{"op": "object.remove", "target": logical, "parameters": {"reviewedDependencies": [item]}}],
    }
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), request)


def test_remove_object_review_does_not_bypass_role_rights_references(tmp_path):
    target, logical = rename_owner(tmp_path, "Catalog")
    path = target / "Roles/Роль/Ext/Rights.xml"
    path.parent.mkdir(parents=True)
    path.write_text(
        '<Rights xmlns="http://v8.1c.ru/8.2/roles" version="2.17">'
        "<object><name>Catalog.Владелец</name></object></Rights>",
        encoding="utf-8",
    )
    item = {
        "path": path.relative_to(target).as_posix(),
        "sha256": editor.digest(path.read_bytes()),
        "reason": "reviewed",
    }
    request = {
        "schemaVersion": 1,
        "operations": [{"op": "object.remove", "target": logical, "parameters": {"reviewedDependencies": [item]}}],
    }
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), request)


def test_remove_object_review_does_not_bypass_exchange_plan_content(tmp_path):
    target, logical, content_path = _exchange_plan_content_fixture(tmp_path)
    item = {
        "path": content_path.relative_to(target).as_posix(),
        "sha256": editor.digest(content_path.read_bytes()),
        "reason": "reviewed",
    }
    request = {
        "schemaVersion": 1,
        "operations": [{"op": "object.remove", "target": logical, "parameters": {"reviewedDependencies": [item]}}],
    }
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), request)


def test_object_edit_remove_uses_hash_review_but_still_checks_references(tmp_path):
    target, logical = native_owner(tmp_path, "Catalog")
    editor.apply(
        target,
        None,
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [
                    {
                        "op": "object.edit",
                        "target": logical,
                        "parameters": {
                            "definition": {"add": {"attributes": [{"name": "Удаляемый", "type": "String(20)"}]}}
                        },
                    }
                ],
            },
        ),
    )

    dependency_path = target / "Catalogs/Чужой.xml"
    dependency_data = create.render_object({"type": "Catalog", "name": "Чужой"}, str(uuid.uuid4()), {})
    dependency = editor.xml_read(dependency_data, f"{{{editor.MD}}}MetaDataObject")
    owner = dependency[0]
    properties = owner.find("m:Properties", editor.NS)
    etree.SubElement(properties, f"{{{editor.MD}}}ExtensionSpecificProperty").text = "reviewed opaque shape"
    dependency_path.write_bytes(etree.tostring(dependency, xml_declaration=True, encoding="UTF-8"))
    relative = dependency_path.relative_to(target).as_posix()
    review = {
        "path": relative,
        "sha256": editor.digest(dependency_path.read_bytes()),
        "reason": "Reviewed source descriptor",
    }
    owner_folder = target / "Catalogs/ВладелецТеста"
    fixture_reviews = [
        {
            "path": path.relative_to(target).as_posix(),
            "sha256": editor.digest(path.read_bytes()),
            "reason": "Reviewed fixture dependency",
        }
        for path in target.rglob("*")
        if path.is_file()
        and path not in {owner_folder.with_suffix(".xml"), dependency_path}
        and owner_folder not in path.parents
        and (
            path.suffix.lower() != ".xml"
            or path.as_posix().endswith("/Ext/Form.xml")
            or path.as_posix().endswith("/Ext/Rights.xml")
            or path.as_posix().endswith("/Ext/Content.xml")
        )
    ]

    def request(reviews):
        return {
            "schemaVersion": 1,
            "operations": [
                {
                    "op": "object.edit",
                    "target": logical,
                    "parameters": {
                        "definition": {"remove": {"attributes": ["Удаляемый"]}},
                        "reviewedDependencies": reviews,
                    },
                }
            ],
        }

    with pytest.raises(editor.Rejected, match="Unsupported rename dependency structure"):
        editor.plan_make(editor.Snapshot(target), request([]))
    all_reviews = [review, *fixture_reviews]
    assert editor.plan_make(editor.Snapshot(target), request(all_reviews))["writes"]

    stale = {**review, "sha256": "0" * 64}
    with pytest.raises(editor.Rejected, match="Stale reviewed dependency"):
        editor.plan_make(editor.Snapshot(target), request([stale, *fixture_reviews]))

    # Review scopes shape inspection only: an old child name in any XML text
    # or attribute still blocks the removal.
    dependency = editor.xml_read(dependency_path.read_bytes(), f"{{{editor.MD}}}MetaDataObject")
    properties = dependency[0].find("m:Properties", editor.NS)
    properties.find("m:ExtensionSpecificProperty", editor.NS).set("dependency", "Удаляемый")
    dependency_path.write_bytes(etree.tostring(dependency, xml_declaration=True, encoding="UTF-8"))
    refreshed = {**review, "sha256": editor.digest(dependency_path.read_bytes())}
    with pytest.raises(editor.Rejected, match="Unresolved rename attribute dependency"):
        editor.plan_make(editor.Snapshot(target), request([refreshed, *fixture_reviews]))


def test_remove_object_accepts_populated_exchange_plan_without_target_reference(tmp_path):
    target, logical, content_path = _exchange_plan_content_fixture(tmp_path)
    content = editor.xml_read(
        content_path.read_bytes(), f"{{{create.SPECIAL_FILES['ExchangePlan'][1]}}}ExchangePlanContent"
    )
    content[0].find(f"{{{create.SPECIAL_FILES['ExchangePlan'][1]}}}Metadata").text = "Catalog.Еще"
    content_path.write_bytes(editor.serialize_like(content, content_path.read_bytes()))
    item = {
        "path": content_path.relative_to(target).as_posix(),
        "sha256": editor.digest(content_path.read_bytes()),
        "reason": "reviewed",
    }
    request = {
        "schemaVersion": 1,
        "operations": [{"op": "object.remove", "target": logical, "parameters": {"reviewedDependencies": [item]}}],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert "Configuration.xml" in {write["path"] for write in plan["writes"]}


@pytest.mark.parametrize("kind", sorted(RECORDED_REMOVE_TYPES - RECORDED_CREATE_TYPES - {"CommonTemplate"}))
def test_remove_object_additional_legacy_types(tmp_path, kind):
    target, _ = rename_owner(tmp_path, "Catalog")
    name = "Удаляемый"
    directory = borrow.DIRECTORIES.get(kind, "Languages" if kind == "Language" else None)
    assert directory is not None
    path = target / directory / (name + ".xml")
    path.parent.mkdir(exist_ok=True)
    root = etree.Element(f"{{{editor.MD}}}MetaDataObject", nsmap={None: editor.MD}, version="2.17")
    owner = etree.SubElement(root, f"{{{editor.MD}}}{kind}", uuid=str(uuid.uuid4()))
    properties = etree.SubElement(owner, f"{{{editor.MD}}}Properties")
    etree.SubElement(properties, f"{{{editor.MD}}}Name").text = name
    etree.SubElement(owner, f"{{{editor.MD}}}ChildObjects")
    path.write_bytes(etree.tostring(root))
    config_path = target / "Configuration.xml"
    config = editor.metadata(config_path.read_bytes(), "Configuration")
    etree.SubElement(config.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}{kind}").text = name
    config_path.write_bytes(editor.serialize_like(config.getparent(), config_path.read_bytes()))
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "object.remove", "target": kind + "." + name, "parameters": {}}],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    assert not path.exists()
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize("keep_files", [False, True])
@pytest.mark.parametrize(
    "fault", [None, "tail", "item-tail", "empty-reference", "short-reference", "unknown-reference"]
)
def test_remove_object_cleans_only_exact_nested_subsystem_content(tmp_path, keep_files, fault):
    target, logical = rename_owner(tmp_path, "Catalog")
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.create",
                "target": "Document.Другой",
                "parameters": {"definition": {"type": "Document", "name": "Другой"}},
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    config_path = target / "Configuration.xml"
    config = editor.metadata(config_path.read_bytes(), "Configuration")
    etree.SubElement(config.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}Subsystem").text = "Раздел"
    config_path.write_bytes(editor.serialize_like(config.getparent(), config_path.read_bytes()))
    paths = ["Subsystems/Раздел.xml", "Subsystems/Раздел/Subsystems/Вложенная.xml"]
    for relative in paths:
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        root = etree.Element(
            f"{{{editor.MD}}}MetaDataObject",
            nsmap={None: editor.MD, "xr": borrow.XR, "xsi": "http://www.w3.org/2001/XMLSchema-instance"},
            version="2.17",
        )
        subsystem = etree.SubElement(root, f"{{{editor.MD}}}Subsystem", uuid=str(uuid.uuid4()))
        props = etree.SubElement(subsystem, f"{{{editor.MD}}}Properties")
        etree.SubElement(props, f"{{{editor.MD}}}Name").text = path.stem
        etree.SubElement(props, f"{{{editor.MD}}}Comment").text = logical
        content = etree.SubElement(props, f"{{{editor.MD}}}Content")
        for value in (logical, "Document.Другой"):
            etree.SubElement(
                content, f"{{{borrow.XR}}}Item", {"{http://www.w3.org/2001/XMLSchema-instance}type": "xr:MDObjectRef"}
            ).text = value
        if fault in {"tail", "item-tail"}:
            (content if fault == "tail" else content[0]).tail = logical
        elif fault:
            content[1].text = {
                "empty-reference": "",
                "short-reference": "Catalog",
                "unknown-reference": "Unknown.Другой",
            }[fault]
        children = etree.SubElement(subsystem, f"{{{editor.MD}}}ChildObjects")
        if path.stem == "Раздел":
            etree.SubElement(children, f"{{{editor.MD}}}Subsystem").text = "Вложенная"
        path.write_bytes(etree.tostring(root))
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "object.remove", "target": logical, "parameters": {"keepFiles": keep_files}}],
    }
    if fault:
        before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
        with pytest.raises(editor.Rejected):
            editor.plan_make(editor.Snapshot(target), payload)
        assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
        return
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    for relative in paths:
        subsystem = editor.metadata((target / relative).read_bytes(), "Subsystem")
        assert [item.text for item in subsystem.findall("m:Properties/m:Content/*", editor.NS)] == ["Document.Другой"]
        assert editor.prop(subsystem, "Comment") == logical


@pytest.mark.parametrize(
    "property_name,alias,owner_kind",
    [
        ("Owners", "owner", "Catalog"),
        ("RegisterRecords", "registerRecord", "Document"),
        ("BasedOn", "basedOn", "Catalog"),
        ("InputByString", "inputByString", "Catalog"),
    ],
)
@pytest.mark.parametrize("action", ["add", "remove", "set"])
def test_reference_lists_actions_repeat_and_preserve(tmp_path, property_name, alias, owner_kind, action):
    target, logical = rename_owner(tmp_path, owner_kind)
    ref_kind = "InformationRegister" if property_name == "RegisterRecords" else "Catalog"
    create_steps = [
        {
            "op": "object.create",
            "target": ref_kind + "." + name,
            "parameters": {"definition": {"type": ref_kind, "name": name}},
        }
        for name in ("Первый", "Второй")
    ]
    editor.apply(
        target, None, editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": create_steps})
    )
    references = (
        [logical + ".StandardAttribute.Code", logical + ".StandardAttribute.Description"]
        if property_name == "InputByString"
        else [ref_kind + ".Первый", ref_kind + ".Второй"]
    )

    def payload(parameters):
        return {"schemaVersion": 1, "operations": [{"op": "object.edit", "target": logical, "parameters": parameters}]}

    initial = payload({"definition": {"modify": {"properties": {property_name: references[:1]}}}})
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), initial))
    _, before_owner, owner_path, _ = ops.read_object(editor.Snapshot(target), logical)
    before = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    request_values = references[:1] if action == "remove" else references[1:]
    plural = {"owner": "owners", "registerRecord": "registerRecords"}.get(alias) or alias
    request = payload(
        {"operation": action + "-" + (plural if action == "set" else alias), "value": " ;; ".join(request_values)}
    )
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []
    _, after, _, _ = ops.read_object(editor.Snapshot(target), logical)
    values = after.find(f"m:Properties/m:{property_name}", editor.NS)
    assert [node.text for node in values] == (
        references if action == "add" else [] if action == "remove" else references[1:]
    )
    assert editor.identity(after) == editor.identity(before_owner)
    for node in values:
        assert node.tag == f"{{{borrow.XR}}}" + ("Field" if property_name == "InputByString" else "Item")
        if property_name != "InputByString":
            prefix, local = node.get(f"{{{ops.XSI}}}type").split(":")
            assert node.nsmap[prefix] == borrow.XR and local == "MDObjectRef"
    assert all((target / path).read_bytes() == data for path, data in before.items() if path != owner_path)


def test_input_by_string_removes_disabled_standard_code_and_keeps_final_validation(tmp_path):
    target, logical = rename_owner(tmp_path, "Catalog")
    _, owner, path, original = ops.read_object(editor.Snapshot(target), logical)
    owner.find("m:Properties/m:CodeLength", editor.NS).text = "0"
    identity = editor.identity(owner)
    (target / path).write_bytes(editor.serialize_like(owner.getparent(), original))

    remove = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {
                    "definition": {
                        "_complex": [
                            {
                                "action": "remove",
                                "property": "InputByString",
                                "values": [logical + ".StandardAttribute.Code"],
                            }
                        ]
                    }
                },
            }
        ],
    }
    before = (target / path).read_bytes()
    plan = editor.plan_make(editor.Snapshot(target), remove)
    assert (target / path).read_bytes() == before
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    _, repaired, _, _ = ops.read_object(editor.Snapshot(target), logical)
    assert editor.identity(repaired) == identity
    assert editor.prop(repaired, "CodeLength") == "0"
    assert ops.read_reference_list(repaired, "InputByString")[1] == [logical + ".StandardAttribute.Description"]
    assert editor.plan_make(editor.Snapshot(target), remove)["writes"] == []

    add_disabled = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {
                    "definition": {
                        "_complex": [
                            {
                                "action": "add",
                                "property": "InputByString",
                                "values": [logical + ".StandardAttribute.Code"],
                            }
                        ]
                    }
                },
            }
        ],
    }
    after = (target / path).read_bytes()
    with pytest.raises(editor.Rejected, match="Disabled standard input attribute"):
        editor.plan_make(editor.Snapshot(target), add_disabled)
    assert (target / path).read_bytes() == after


def test_borrowed_document_adds_missing_register_records_list_and_keeps_strict_validation(document_roots):
    source, target = document_roots
    base_register = "ИсходныйРегистратор"
    added_register = "НовыйРегистратор"
    second_register = "ВторойРегистратор"
    base_register_path = "InformationRegister." + base_register
    added_register_path = "InformationRegister." + added_register
    config_path = source / "Configuration.xml"
    config_bytes = config_path.read_bytes()
    config = editor.metadata(config_bytes, "Configuration")
    borrow._register(borrow._registrations(config), "InformationRegister", base_register)
    config_path.write_bytes(editor.serialize_like(config.getparent(), config_bytes))
    (source / "InformationRegisters").mkdir()
    (source / f"InformationRegisters/{base_register}.xml").write_bytes(
        create.render_object({"type": "InformationRegister", "name": base_register}, editor.identity(config), {})
    )
    document_path = source / "Documents/Документ.xml"
    base_document = editor.metadata(document_path.read_bytes(), "Document")
    base_records = etree.SubElement(base_document.find("m:Properties", editor.NS), f"{{{editor.MD}}}RegisterRecords")
    etree.SubElement(
        base_records, f"{{{borrow.XR}}}Item", nsmap={"xr": borrow.XR}, attrib={f"{{{ops.XSI}}}type": "xr:MDObjectRef"}
    ).text = base_register_path
    document_path.write_bytes(editor.serialize_like(base_document.getparent(), document_path.read_bytes()))
    base_bytes = {
        path.relative_to(source).as_posix(): path.read_bytes() for path in source.rglob("*") if path.is_file()
    }
    payload = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.borrow", "target": "Document.Документ", "parameters": {"baseRoot": str(source)}},
            {
                "op": "object.create",
                "target": added_register_path,
                "parameters": {"definition": {"type": "InformationRegister", "name": added_register}},
            },
            {
                "op": "object.edit",
                "target": "Document.Документ",
                "parameters": {
                    "definition": {
                        "_complex": [{"action": "add", "property": "RegisterRecords", "values": [added_register_path]}]
                    }
                },
            },
        ],
    }

    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []

    document = editor.metadata((target / "Documents/Документ.xml").read_bytes(), "Document")
    container, values = ops.read_reference_list(document, "RegisterRecords")
    assert container.tag == f"{{{editor.MD}}}RegisterRecords"
    assert values == [added_register_path]
    second_path = "InformationRegister." + second_register
    second_add = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.borrow", "target": "Document.Документ", "parameters": {"baseRoot": str(source)}},
            {
                "op": "object.create",
                "target": second_path,
                "parameters": {"definition": {"type": "InformationRegister", "name": second_register}},
            },
            {
                "op": "object.edit",
                "target": "Document.Документ",
                "parameters": {
                    "definition": {
                        "_complex": [{"action": "add", "property": "RegisterRecords", "values": [second_path]}]
                    }
                },
            },
        ],
    }
    second_plan = editor.plan_make(editor.Snapshot(target), second_add)
    assert editor.apply(target, None, second_plan) == "applied"
    assert editor.apply(target, None, second_plan) == "already-applied"
    document = editor.metadata((target / "Documents/Документ.xml").read_bytes(), "Document")
    assert ops.read_reference_list(document, "RegisterRecords")[1] == [added_register_path, second_path]
    assert editor.plan_make(editor.Snapshot(target), second_add)["writes"] == []
    assert {
        path.relative_to(source).as_posix(): path.read_bytes() for path in source.rglob("*") if path.is_file()
    } == base_bytes

    base_document = editor.metadata(document_path.read_bytes(), "Document")
    assert ops.read_reference_list(base_document, "RegisterRecords")[1] == [base_register_path]
    missing_base_list = etree.fromstring(etree.tostring(base_document))
    missing_base_list.find("m:Properties/m:RegisterRecords", editor.NS).getparent().remove(
        missing_base_list.find("m:Properties/m:RegisterRecords", editor.NS)
    )
    with pytest.raises(editor.Rejected, match="Missing or ambiguous reference list"):
        ops.read_reference_list(missing_base_list, "RegisterRecords")
    missing_list = etree.fromstring(etree.tostring(document))
    missing_list.find("m:Properties/m:RegisterRecords", editor.NS).getparent().remove(
        missing_list.find("m:Properties/m:RegisterRecords", editor.NS)
    )
    original_missing = etree.tostring(missing_list)
    with pytest.raises(editor.Rejected, match="Missing or ambiguous reference list"):
        ops.edit_reference_list(editor.Snapshot(target), missing_list, "RegisterRecords", "add", [added_register_path])
    assert etree.tostring(missing_list) == original_missing
    with pytest.raises(editor.Rejected, match="Missing or ambiguous reference list"):
        ops.edit_reference_list(
            editor.Snapshot(target), missing_list, "RegisterRecords", "set", [added_register_path], base_document
        )
    assert etree.tostring(missing_list) == original_missing

    duplicate = etree.fromstring(etree.tostring(document))
    duplicate_container = duplicate.find("m:Properties/m:RegisterRecords", editor.NS)
    duplicate_container.append(etree.fromstring(etree.tostring(duplicate_container[0])))
    with pytest.raises(editor.Rejected, match="duplicate"):
        ops.edit_reference_list(
            editor.Snapshot(target), duplicate, "RegisterRecords", "add", [added_register_path], base_document
        )

    malformed = etree.fromstring(etree.tostring(document))
    malformed_container = malformed.find("m:Properties/m:RegisterRecords", editor.NS)
    malformed_container[0].tag = f"{{{editor.MD}}}Field"
    with pytest.raises(editor.Rejected, match="reference list item"):
        ops.edit_reference_list(
            editor.Snapshot(target), malformed, "RegisterRecords", "add", [added_register_path], base_document
        )


@pytest.mark.parametrize("values", [["Catalog.Нет"], ["Catalog.Владелец", "Catalog.владелец"], ["Catalog.владелец"]])
def test_reference_lists_reject_unknown_or_ambiguous_without_writes(tmp_path, values):
    target, logical = rename_owner(tmp_path, "Catalog")
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"definition": {"_complex": [{"action": "set", "property": "Owners", "values": values}]}},
            }
        ],
    }
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), request)
    assert all(p.read_bytes() == data for p, data in before.items())


def test_input_list_rejects_duplicate_standard_attribute(tmp_path):
    target, logical = rename_owner(tmp_path, "Catalog")
    _, owner, path, original = ops.read_object(editor.Snapshot(target), logical)
    standards = owner.find("m:Properties/m:StandardAttributes", editor.NS)
    standards.append(etree.fromstring(etree.tostring(standards[0])))
    (target / path).write_bytes(editor.serialize_like(owner.getparent(), original))
    before = (target / path).read_bytes()
    request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {
                    "operation": "set-inputByString",
                    "value": logical + ".StandardAttribute." + standards[0].get("name"),
                },
            }
        ],
    }
    with pytest.raises(editor.Rejected, match="ambiguous"):
        editor.plan_make(editor.Snapshot(target), request)
    assert (target / path).read_bytes() == before


@pytest.mark.parametrize("mode", ["valid", "wrong-uuid", "native"])
def test_input_list_borrowed_attribute_identity(document_roots, mode):
    source, target = document_roots
    source_file = source / "Documents/Документ.xml"
    source_file.write_bytes(
        create.render_object(
            {"type": "Document", "name": "Документ", "attributes": [{"name": "Поле", "type": "String(25)"}]},
            str(uuid.uuid4()),
            {},
        )
    )
    borrow_step = {"op": "object.borrow", "target": "Document.Документ", "parameters": {"baseRoot": str(source)}}
    editor.apply(
        target, None, editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [borrow_step]})
    )
    _, owner, path, original = ops.read_object(editor.Snapshot(target), "Document.Документ")
    source_owner = editor.metadata(source_file.read_bytes(), "Document")
    member = source_owner.find("m:ChildObjects/m:Attribute", editor.NS)
    inherited_id = editor.identity(member)
    member.set("uuid", str(uuid.uuid4()))
    props = member.find("m:Properties", editor.NS)
    etree.SubElement(props, f"{{{editor.MD}}}ObjectBelonging").text = "Native" if mode == "native" else "Adopted"
    etree.SubElement(props, f"{{{editor.MD}}}ExtendedConfigurationObject").text = (
        str(uuid.uuid4()) if mode == "wrong-uuid" else inherited_id
    )
    owner.find("m:ChildObjects", editor.NS).append(member)
    etree.SubElement(owner.find("m:Properties", editor.NS), f"{{{editor.MD}}}InputByString")
    (target / path).write_bytes(editor.serialize_like(owner.getparent(), original))
    before = (target / path).read_bytes()
    request = {
        "schemaVersion": 1,
        "operations": [
            borrow_step,
            {
                "op": "object.edit",
                "target": "Document.Документ",
                "parameters": {"operation": "set-inputByString", "value": "Attribute.Поле"},
            },
        ],
    }
    if mode != "valid":
        with pytest.raises(editor.Rejected, match="input attribute"):
            editor.plan_make(editor.Snapshot(target), request)
        assert (target / path).read_bytes() == before
    else:
        plan = editor.plan_make(editor.Snapshot(target), request)
        assert editor.apply(target, None, plan) == "applied"
        assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []


@pytest.mark.parametrize(
    "problem", ["qname", "child", "unregistered", "foreign-field", "missing-field", "disabled-field"]
)
def test_reference_list_rejects_invalid_structure_and_links(tmp_path, problem):
    target, logical = rename_owner(tmp_path, "Catalog")
    _, owner, path, original = ops.read_object(editor.Snapshot(target), logical)
    operation, value = "set-owners", logical
    container = owner.find("m:Properties/m:Owners", editor.NS)
    if problem == "qname":
        item = etree.SubElement(container, f"{{{borrow.XR}}}Item", nsmap={"bad": "urn:wrong"})
        item.set(f"{{{ops.XSI}}}type", "bad:MDObjectRef")
        item.text = logical
    elif problem == "child":
        etree.SubElement(container, f"{{{borrow.XR}}}Field").text = logical
    elif problem == "unregistered":
        (target / "Catalogs/НеЗарегистрирован.xml").write_bytes(
            create.render_object({"type": "Catalog", "name": "НеЗарегистрирован"}, str(uuid.uuid4()), {})
        )
        value = "Catalog.НеЗарегистрирован"
    else:
        operation = "set-inputByString"
        value = {
            "foreign-field": "Catalog.Чужой.StandardAttribute.Code",
            "missing-field": logical + ".Attribute.Нет",
            "disabled-field": logical + ".StandardAttribute.Code",
        }[problem]
        if problem == "disabled-field":
            owner.find("m:Properties/m:CodeLength", editor.NS).text = "0"
    (target / path).write_bytes(editor.serialize_like(owner.getparent(), original))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    request = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.edit", "target": logical, "parameters": {"operation": operation, "value": value}}
        ],
    }
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), request)
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.mark.parametrize(
    "kind,collection,operation,value",
    [
        ("Catalog", "attributes", "attribute", "Поле"),
        ("Catalog", "tabularSections", "ts", "Строки"),
        ("InformationRegister", "dimensions", "dimension", "Измерение"),
        ("InformationRegister", "resources", "resource", "Ресурс"),
        ("Enum", "enumValues", "enumValue", "Вариант"),
        ("DocumentJournal", "columns", "column", "Колонка"),
        ("Catalog", "tabularSections", "ts-attribute", "Строки.Поле"),
    ],
)
def test_remove_children_preserves_other_files_and_repeats(tmp_path, kind, collection, operation, value):
    target, logical = rename_owner(tmp_path, kind)
    member = {"name": value.split(".")[0]}
    if operation == "ts-attribute":
        member["attributes"] = [{"name": "Поле", "type": "String"}]
    addition = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.edit", "target": logical, "parameters": {"definition": {"add": {collection: [member]}}}}
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), addition))
    _, owner, path, _ = ops.read_object(editor.Snapshot(target), logical)
    identity = editor.identity(owner)
    before = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    request = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.edit", "target": logical, "parameters": {"operation": "remove-" + operation, "value": value}}
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []
    _, owner, _, _ = ops.read_object(editor.Snapshot(target), logical)
    assert editor.identity(owner) == identity
    assert all((target / name).read_bytes() == data for name, data in before.items() if name != path)
    removed_path = (
        "m:ChildObjects/m:TabularSection/m:ChildObjects/m:Attribute"
        if operation == "ts-attribute"
        else f"m:ChildObjects/m:{ops.ADD_KINDS[collection]}"
    )
    assert not owner.findall(removed_path, editor.NS)


@pytest.mark.parametrize("obstacle", ["reference", "bsl", "unknown-xml", "adopted"])
def test_remove_children_rejects_dependencies_without_writes(tmp_path, obstacle):
    target, logical = rename_owner(tmp_path, "Catalog")
    add = {
        "op": "object.edit",
        "target": logical,
        "parameters": {"operation": "add-attribute", "value": "Поле: String"},
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [add]}))
    _, owner, path, original = ops.read_object(editor.Snapshot(target), logical)
    if obstacle == "reference":
        etree.SubElement(owner.find("m:Properties/m:InputByString", editor.NS), f"{{{borrow.XR}}}Field").text = (
            logical + ".Attribute.Поле"
        )
    elif obstacle == "adopted":
        props = owner.find("m:ChildObjects/m:Attribute/m:Properties", editor.NS)
        etree.SubElement(props, f"{{{editor.MD}}}ObjectBelonging").text = "Adopted"
    elif obstacle == "bsl":
        (target / "Module.bsl").write_text("НепроверенныйКод();", encoding="utf-8")
    else:
        (target / "Unknown.xml").write_bytes(b"<Unknown/>")
    (target / path).write_bytes(editor.serialize_like(owner.getparent(), original))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    request = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.edit", "target": logical, "parameters": {"operation": "remove-attribute", "value": "Поле"}}
        ],
    }
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), request)
    assert all(p.read_bytes() == data for p, data in before.items())


def test_remove_child_reviewed_bsl_is_explicit_and_still_checks_xml_references(tmp_path):
    def prepare(root, reference=False):
        root.mkdir()
        target, logical = rename_owner(root, "Catalog")
        add = {
            "op": "object.edit",
            "target": logical,
            "parameters": {"definition": {"add": {"attributes": [{"name": "Поле", "type": "String"}]}}},
        }
        editor.apply(target, None, editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [add]}))
        _, owner, path, original = ops.read_object(editor.Snapshot(target), logical)
        if reference:
            field = owner.find("m:Properties/m:InputByString", editor.NS)
            etree.SubElement(field, f"{{{borrow.XR}}}Field").text = logical + ".Attribute.Поле"
            (target / path).write_bytes(editor.serialize_like(owner.getparent(), original))
        bsl = target / "Catalogs/Владелец/Ext/ObjectModule.bsl"
        bsl.parent.mkdir(parents=True, exist_ok=True)
        bsl.write_text("НепроверенныйКод();", encoding="utf-8")
        review = {
            "path": bsl.relative_to(target).as_posix(),
            "sha256": editor.digest(bsl.read_bytes()),
            "reason": "Проверен для удаления реквизита",
        }
        request = {
            "schemaVersion": 1,
            "operations": [
                {
                    "op": "object.edit",
                    "target": logical,
                    "parameters": {"definition": {"remove": {"attributes": ["Поле"]}}},
                }
            ],
        }
        return target, logical, request, review

    target, logical, request, review = prepare(tmp_path / "without-review")
    with pytest.raises(editor.Rejected, match="Cannot prove dependencies in BSL"):
        editor.plan_make(editor.Snapshot(target), request)

    target, logical, request, review = prepare(tmp_path / "reviewed")
    request["operations"][0]["parameters"]["reviewedDependencies"] = [review]
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert editor.apply(target, None, plan) == "applied"
    _, owner, _, _ = ops.read_object(editor.Snapshot(target), logical)
    assert borrow._member(owner, "Attribute", "Поле", optional=True) is None

    target, _, request, review = prepare(tmp_path / "stale")
    request["operations"][0]["parameters"]["reviewedDependencies"] = [{**review, "sha256": "0" * 64}]
    with pytest.raises(editor.Rejected, match="Stale reviewed dependency"):
        editor.plan_make(editor.Snapshot(target), request)

    target, _, request, review = prepare(tmp_path / "unused-review")
    config = target / "Configuration.xml"
    request["operations"][0]["parameters"]["reviewedDependencies"] = [
        review,
        {"path": "Configuration.xml", "sha256": editor.digest(config.read_bytes()), "reason": "Лишний путь"},
    ]
    with pytest.raises(editor.Rejected, match="Extraneous reviewed dependency"):
        editor.plan_make(editor.Snapshot(target), request)

    target, _, request, review = prepare(tmp_path / "xml-reference", reference=True)
    request["operations"][0]["parameters"]["reviewedDependencies"] = [review]
    with pytest.raises(editor.Rejected, match="Cannot remove referenced"):
        editor.plan_make(editor.Snapshot(target), request)


@pytest.mark.parametrize("reference", ["nested", "generated"])
def test_remove_section_rejects_external_references(tmp_path, reference):
    target, logical = rename_owner(tmp_path, "Catalog")
    setup = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"operation": "add-ts", "value": "Строки: Поле: String"},
            },
            {
                "op": "object.create",
                "target": "Document.Ссылки",
                "parameters": {
                    "definition": {
                        "type": "Document",
                        "name": "Ссылки",
                        "attributes": [{"name": "Контроль", "type": "String"}],
                    }
                },
            },
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), setup))
    _, document, path, original = ops.read_object(editor.Snapshot(target), "Document.Ссылки")
    if reference == "nested":
        etree.SubElement(document.find("m:Properties/m:DataLockFields", editor.NS), f"{{{borrow.XR}}}Field").text = (
            logical + ".TabularSection.Строки.Attribute.Поле"
        )
    else:
        document.find(
            "m:ChildObjects/m:Attribute/m:Properties/m:Type/v8:Type", editor.NS
        ).text = "cfg:CatalogTabularSection.Владелец.Строки"
    (target / path).write_bytes(editor.serialize_like(document.getparent(), original))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    request = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.edit", "target": logical, "parameters": {"operation": "remove-ts", "value": "Строки"}}
        ],
    }
    with pytest.raises(editor.Rejected, match="Cannot remove referenced"):
        editor.plan_make(editor.Snapshot(target), request)
    assert all(p.read_bytes() == data for p, data in before.items())


def test_remove_child_after_explicit_reference_removal(tmp_path):
    target, logical = rename_owner(tmp_path, "Catalog")

    def step(operation, value):
        return {"op": "object.edit", "target": logical, "parameters": {"operation": operation, "value": value}}

    setup = {
        "schemaVersion": 1,
        "operations": [step("add-attribute", "Поле: String"), step("add-inputByString", "Attribute.Поле")],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), setup))
    request = {
        "schemaVersion": 1,
        "operations": [step("remove-inputByString", "Attribute.Поле"), step("remove-attribute", "Поле")],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"


@pytest.mark.parametrize("reference", [True, False])
@pytest.mark.parametrize("uuid_format", ["canonical", "hex", "braces", "urn"])
def test_remove_enum_value_checks_uuid_reference_not_comment(tmp_path, reference, uuid_format):
    target, logical = rename_owner(tmp_path, "Enum")
    setup = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.edit", "target": logical, "parameters": {"operation": "add-enumValue", "value": "Вариант"}},
            {
                "op": "object.create",
                "target": "Document.Ссылки",
                "parameters": {
                    "definition": {
                        "type": "Document",
                        "name": "Ссылки",
                        "attributes": [{"name": "Поле", "type": "EnumRef.Владелец"}],
                    }
                },
            },
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), setup))
    _, enum, _, _ = ops.read_object(editor.Snapshot(target), logical)
    identity = editor.identity(borrow._member(enum, "EnumValue", "Вариант"))
    identity = {
        "canonical": identity,
        "hex": uuid.UUID(identity).hex,
        "braces": "{" + identity.upper() + "}",
        "urn": uuid.UUID(identity).urn,
    }[uuid_format]
    _, document, path, original = ops.read_object(editor.Snapshot(target), "Document.Ссылки")
    props = document.find("m:ChildObjects/m:Attribute/m:Properties", editor.NS)
    if reference:
        value = props.find("m:FillValue", editor.NS)
        value.attrib.clear()
        value.set(f"{{{ops.XSI}}}type", "cfg:EnumRef.Владелец")
        value.text = identity
    else:
        props.find("m:Comment", editor.NS).text = identity
    (target / path).write_bytes(editor.serialize_like(document.getparent(), original))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"operation": "remove-enumValue", "value": "Вариант"},
            }
        ],
    }
    if reference:
        with pytest.raises(editor.Rejected, match="UUID"):
            editor.plan_make(editor.Snapshot(target), request)
        assert all(p.read_bytes() == data for p, data in before.items())
    else:
        assert editor.apply(target, None, editor.plan_make(editor.Snapshot(target), request)) == "applied"
        assert (target / path).read_bytes() == before[target / path]


def xml_content(node):
    text = (node.text or "").strip()
    if node.tag == f"{{{editor.V8}}}Type" and ":" in text:
        prefix, name = text.split(":", 1)
        text = "{" + node.nsmap[prefix] + "}" + name
    return node.tag, dict(node.attrib), text, [xml_content(child) for child in node]


@pytest.mark.parametrize("collection,kind", [(key, kind) for key, kinds in ops.ADD_OWNERS.items() for kind in kinds])
def test_add_child_all_owners_matches_recorded_xml_and_preserves_files(tmp_path, collection, kind):
    target, logical = native_owner(tmp_path, kind, *(["Catalog.Контрагенты"] if collection == "dimensions" else []))
    member: dict[str, Any] = {"name": "НовоеПоле"}
    if collection == "attributes":
        member.update(type="UUID")
    elif collection == "dimensions":
        member.update(type="CatalogRef.Контрагенты", flags=["req", "index"])
    elif collection == "resources":
        member.update(type="Number(15,2)", flags=["req"])
    elif collection == "columns":
        member.update(indexing="Index", references=["Document.Документ.Attribute.Контрагент"])
    elif collection == "tabularSections":
        member["attributes"] = [{"name": "Значение", "type": "UUID", "flags": ["req"]}]
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    payload = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.edit", "target": logical, "parameters": {"definition": {"add": {collection: [member]}}}}
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert len(plan["writes"]) == 1
    assert editor.apply(target, None, plan) == "applied"
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    _, owner, path, _ = ops.read_object(editor.Snapshot(target), logical)
    node = owner.find(f"m:ChildObjects/m:{ops.ADD_KINDS[collection]}", editor.NS)
    if collection == "attributes":
        context = (
            "catalog"
            if kind == "Catalog"
            else "register"
            if kind in ops.REGISTER_KINDS
            else "processor"
            if kind in {"Report", "DataProcessor", "ExternalReport", "ExternalDataProcessor"}
            else "document"
        )
        key = collection + "/" + context
    elif collection in {"dimensions", "resources"}:
        key = collection + "/" + (kind if kind in {"InformationRegister", "AccumulationRegister"} else "other")
    elif collection == "tabularSections":
        context = (
            "catalog"
            if kind == "Catalog"
            else "processor"
            if kind in {"Report", "DataProcessor", "ExternalReport", "ExternalDataProcessor"}
            else "other"
        )
        key = collection + "/" + context
    else:
        key = collection + "/" + kind
    expected = recorded_edit_case(key)[0]
    for generated in expected.findall("m:InternalInfo/xr:GeneratedType", {**editor.NS, "xr": borrow.XR}):
        generated.set(
            "name", generated.get("name").replace("{{kind}}", kind).replace("{{name}}", logical.split(".")[1])
        )
    # Match only identities, as when the former builder received actual UUIDs.
    identity_tags = {f"{{{borrow.XR}}}TypeId", f"{{{borrow.XR}}}ValueId"}
    actual_ids = [
        part.get("uuid") or part.text for part in node.iter() if part.get("uuid") or part.tag in identity_tags
    ]
    expected_ids = [part for part in expected.iter() if part.get("uuid") or part.tag in identity_tags]
    assert len(actual_ids) == len(expected_ids)
    for part, identity in zip(expected_ids, actual_ids, strict=False):
        if part.get("uuid"):
            part.set("uuid", identity)
        else:
            part.text = identity
    assert xml_content(node) == xml_content(expected)
    for file, data in before.items():
        if file != target / path:
            assert file.read_bytes() == data


@pytest.mark.parametrize(
    "kind,collection",
    [
        ("Catalog", "dimensions"),
        ("Enum", "attributes"),
        ("DocumentJournal", "resources"),
        ("ExternalReport", "enumValues"),
    ],
)
def test_invalid_child_owner_rejected_without_write(tmp_path, kind, collection):
    target, logical = native_owner(tmp_path, kind)
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected):
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [
                    {
                        "op": "object.edit",
                        "target": logical,
                        "parameters": {"definition": {"add": {collection: [{"name": "Поле"}]}}},
                    }
                ],
            },
        )
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


def test_create_then_edit_batch_repeats_without_replacing_children(tmp_path):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.create",
                "target": "Catalog.Объект",
                "parameters": {"definition": {"type": "Catalog", "name": "Объект"}},
            },
            {
                "op": "object.edit",
                "target": "Catalog.Объект",
                "parameters": {"definition": {"add": {"attributes": [{"name": "Поле", "type": "UUID"}]}}},
            },
        ],
    }
    assert editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload)) == "applied"
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


@pytest.mark.parametrize("mutation", ["foreign-kind", "missing", "changed", "reordered"])
def test_repeated_create_rejects_invalid_or_changed_children(tmp_path, mutation):
    target = tmp_path / "target"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.create",
                "target": "Catalog.Объект",
                "parameters": {
                    "definition": {
                        "type": "Catalog",
                        "name": "Объект",
                        "attributes": [{"name": "Первое", "type": "String(10)"}, {"name": "Второе", "type": "Boolean"}],
                    }
                },
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    path = target / "Catalogs/Объект.xml"
    original = path.read_bytes()
    owner = editor.metadata(original, "Catalog")
    children = owner.find("m:ChildObjects", editor.NS)
    if mutation == "foreign-kind":
        child = etree.SubElement(children, f"{{{editor.MD}}}Dimension", uuid=str(uuid.uuid4()))
        properties = etree.SubElement(child, f"{{{editor.MD}}}Properties")
        etree.SubElement(properties, f"{{{editor.MD}}}Name").text = "Постороннее"
    elif mutation == "missing":
        children.remove(children[0])
    elif mutation == "changed":
        children[0].find("m:Properties/m:Comment", editor.NS).text = "Изменено"
    else:
        children.append(children[0])
    path.write_bytes(editor.serialize_like(owner.getparent(), original))
    before = path.read_bytes()
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), payload)
    assert path.read_bytes() == before


@pytest.mark.parametrize("kind", ops.ADD_OWNERS["tabularSections"])
def test_section_add_then_nested_add_preserves_identity_and_repeats(tmp_path, kind):
    target, logical = native_owner(tmp_path, kind)
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"operation": "add-ts", "value": "Строки: Первое: String(10)"},
            },
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"operation": "add-ts-attribute", "value": "Строки.Второе: Boolean << before Первое"},
            },
        ],
    }
    assert editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload)) == "applied"
    config, owner, path, _ = ops.read_object(editor.Snapshot(target), logical)
    section = borrow._member(owner, "TabularSection", "Строки")
    attributes = present(section).findall("m:ChildObjects/m:Attribute", editor.NS)
    assert [editor.node_name(node) for node in attributes] == ["Второе", "Первое"]
    for attribute in attributes:
        assert editor.identity(attribute) == editor.allocate_uuid(
            editor.identity(config),
            "Attribute",
            logical + ".TabularSection.Строки.Attribute." + editor.node_name(attribute),
            "object",
            {},
        )
    types = present(section).findall(f"m:InternalInfo/{{{borrow.XR}}}GeneratedType", editor.NS)
    assert [node.get("name") for node in types] == [
        kind + suffix + "." + logical.split(".")[1] + ".Строки" for suffix in ("TabularSection", "TabularSectionRow")
    ]
    for generated in types:
        for role in ("TypeId", "ValueId"):
            assert generated.findtext(f"{{{borrow.XR}}}{role}") == editor.allocate_uuid(
                editor.identity(config),
                "TabularSection",
                logical + ".TabularSection.Строки",
                generated.get("name") + ":" + role,
                {},
            )
    context = ops.property_context(editor.Snapshot(target), logical)
    assert "Type" in context["tabularSections.Строки.attributes.Второе"]
    before = (target / path).read_bytes()
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    assert (target / path).read_bytes() == before
    payload["operations"][1]["parameters"]["value"] = "Строки.Третье: Boolean >> after Отсутствует"
    with pytest.raises(editor.Rejected, match="anchor"):
        editor.plan_make(editor.Snapshot(target), payload)


def test_create_section_then_add_nested_attribute_repeats(tmp_path):
    target, logical = native_owner(tmp_path, "Catalog")
    section = {"name": "Строки", "attributes": [{"name": "Первое", "type": "String"}]}
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.create",
                "target": "Catalog.Другой",
                "parameters": {"definition": {"type": "Catalog", "name": "Другой", "tabularSections": [section]}},
            },
            {
                "op": "object.edit",
                "target": "Catalog.Другой",
                "parameters": {"operation": "add-ts-attribute", "value": "Строки.Второе: Boolean"},
            },
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize("kind", ops.ADD_OWNERS["tabularSections"])
def test_modify_section_and_nested_properties_preserves_ids_and_repeats(tmp_path, kind):
    target, logical = native_owner(tmp_path, kind)
    initial = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"operation": "add-ts", "value": "Строки: Поле: String(10)"},
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), initial))
    _, owner, path, _ = ops.read_object(editor.Snapshot(target), logical)
    section = borrow._member(owner, "TabularSection", "Строки")
    ids = [
        node.get("uuid") or node.text
        for node in present(section).iter()
        if node.get("uuid") or node.tag in {f"{{{borrow.XR}}}TypeId", f"{{{borrow.XR}}}ValueId"}
    ]
    files = {p: p.read_bytes() for p in target.rglob("*") if p.is_file() and p != target / path}
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"operation": "modify-ts", "value": "Строки: synonym=Позиции, Comment=Изменено"},
            },
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {
                    "operation": "modify-ts-attribute",
                    "value": "Строки.Поле: type=String(25), synonym=Значение",
                },
            },
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    _, owner, _, _ = ops.read_object(editor.Snapshot(target), logical)
    section = borrow._member(owner, "TabularSection", "Строки")
    assert [
        node.get("uuid") or node.text
        for node in present(section).iter()
        if node.get("uuid") or node.tag in {f"{{{borrow.XR}}}TypeId", f"{{{borrow.XR}}}ValueId"}
    ] == ids
    assert editor.prop(section, "Comment") == "Изменено"
    attribute = borrow._member(section, "Attribute", "Поле")
    assert (
        present(attribute).findtext("m:Properties/m:Type/v8:StringQualifiers/v8:Length", namespaces=editor.NS) == "25"
    )
    assert files == {p: p.read_bytes() for p in target.rglob("*") if p.is_file() and p != target / path}


@pytest.mark.parametrize("kind", ops.ADD_OWNERS["tabularSections"])
def test_modify_section_and_nested_rename_preserves_generated_ids(tmp_path, kind):
    target, logical = rename_owner(tmp_path, kind)
    initial = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"operation": "add-ts", "value": "Строки: Поле: String(10)"},
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), initial))
    _, owner, path, original = ops.read_object(editor.Snapshot(target), logical)
    section = borrow._member(owner, "TabularSection", "Строки")
    ids = [
        node.get("uuid") or node.text
        for node in present(section).iter()
        if node.get("uuid") or node.tag in {f"{{{borrow.XR}}}TypeId", f"{{{borrow.XR}}}ValueId"}
    ]
    fields = owner.find("m:Properties/m:DataLockFields", editor.NS)
    if fields is not None:
        etree.SubElement(fields, f"{{{borrow.XR}}}Field").text = logical + ".TabularSection.Строки.Attribute.Поле"
        (target / path).write_bytes(editor.serialize_like(owner.getparent(), original))
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"operation": "modify-ts-attribute", "value": "Строки.Поле: name=НовоеПоле"},
            },
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"operation": "modify-ts", "value": "Строки: Name=Позиции"},
            },
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    _, owner, _, _ = ops.read_object(editor.Snapshot(target), logical)
    section = borrow._member(owner, "TabularSection", "Позиции")
    assert borrow._member(section, "Attribute", "НовоеПоле") is not None
    assert [
        node.get("uuid") or node.text
        for node in present(section).iter()
        if node.get("uuid") or node.tag in {f"{{{borrow.XR}}}TypeId", f"{{{borrow.XR}}}ValueId"}
    ] == ids
    assert all(node.get("name").endswith(".Позиции") for node in present(section).iter(f"{{{borrow.XR}}}GeneratedType"))
    fields = owner.find("m:Properties/m:DataLockFields", editor.NS)
    if fields is not None:
        assert fields[-1].text == logical + ".TabularSection.Позиции.Attribute.НовоеПоле"


@pytest.mark.parametrize(
    "parameters",
    [
        {"operation": "modify-ts", "value": "Нет: synonym=Новое"},
        {"operation": "modify-ts-attribute", "value": "Строки.Нет: synonym=Новое"},
        {"operation": "modify-ts", "value": "Строки: UnknownProperty=Новое"},
        {"operation": "modify-ts", "value": "Строки: Name=Занято"},
        {"operation": "modify-ts-attribute", "value": "Строки.Поле: Name=НомерСтроки"},
        {"definition": {"modify": {"tabularSections": {"Строки": {"modify": {}}}}}},
        {"definition": {"modify": {"tabularSections": {"Строки": {"modify": {"Поле": {}}}}}}},
    ],
)
def test_modify_section_rejects_invalid_request_without_writes(tmp_path, parameters):
    target, logical = rename_owner(tmp_path, "Catalog")
    initial = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"operation": "add-ts", "value": "Строки: Поле: String(10);; Занято"},
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), initial))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    payload = {"schemaVersion": 1, "operations": [{"op": "object.edit", "target": logical, "parameters": parameters}]}
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


def test_modify_section_composes_add_nested_edit_and_rename_in_one_step(tmp_path):
    target, logical = rename_owner(tmp_path, "Catalog")
    initial = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"operation": "add-ts", "value": "Строки: Поле: String(10)"},
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), initial))
    _, owner, _, _ = ops.read_object(editor.Snapshot(target), logical)
    original_id = editor.identity(
        borrow._member(borrow._member(owner, "TabularSection", "Строки"), "Attribute", "Поле")
    )
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {
                    "definition": {
                        "modify": {
                            "tabularSections": {
                                "Строки": {
                                    "add": [{"name": "Дополнительное", "type": "Boolean"}],
                                    "modify": {"Поле": {"name": "Code", "type": "String(25)"}},
                                    "Name": "Позиции",
                                    "synonym": "Новый заголовок",
                                }
                            }
                        }
                    }
                },
            }
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    _, owner, _, _ = ops.read_object(editor.Snapshot(target), logical)
    section = borrow._member(owner, "TabularSection", "Позиции")
    field = borrow._member(section, "Attribute", "Code")
    assert editor.identity(field) == original_id
    assert present(field).findtext("m:Properties/m:Type/v8:StringQualifiers/v8:Length", namespaces=editor.NS) == "25"
    assert borrow._member(section, "Attribute", "Дополнительное") is not None
    assert (
        present(section).findtext("m:Properties/m:Synonym/v8:item/v8:content", namespaces=editor.NS)
        == "Новый заголовок"
    )


def test_modify_borrowed_section_preserves_source_and_rejects_rename(document_roots):
    source, target = document_roots
    source_path = source / "Documents/Документ.xml"
    source_path.write_bytes(
        create.render_object(
            {"type": "Document", "name": "Документ", "tabularSections": [{"name": "Строки"}]}, str(uuid.uuid4()), {}
        )
    )
    before = source_path.read_bytes()
    borrow_step = {
        "op": "tabular-section.borrow",
        "target": "Document.Документ.TabularSection.Строки",
        "parameters": {"baseRoot": str(source)},
    }
    edit_step = {
        "op": "object.edit",
        "target": "Document.Документ",
        "parameters": {"operation": "modify-ts", "value": "Строки: Comment=Комментарий расширения"},
    }
    payload = {"schemaVersion": 1, "operations": [borrow_step, edit_step]}
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    assert source_path.read_bytes() == before
    edit_step["parameters"]["value"] = "Строки: synonym=Другое представление"
    with pytest.raises(editor.Rejected, match="Missing or ambiguous property: Synonym"):
        editor.plan_make(editor.Snapshot(target), payload)
    edit_step["parameters"]["value"] = "Строки: name=НовоеИмя"
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), payload)
    assert source_path.read_bytes() == before


@pytest.mark.parametrize("name", ["Новое", "Исходное", "LineNumber", "номерстроки"])
def test_borrowed_section_requires_exact_base_and_free_attribute(document_roots, name):
    source, target = document_roots
    path = source / "Documents/Документ.xml"
    definition = {
        "type": "Document",
        "name": "Документ",
        "tabularSections": [{"name": "Строки", "attributes": [{"name": "Исходное", "type": "String"}]}],
    }
    path.write_bytes(create.render_object(definition, str(uuid.uuid4()), {}))
    before = path.read_bytes()
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "tabular-section.borrow",
                "target": "Document.Документ.TabularSection.Строки",
                "parameters": {"baseRoot": str(source)},
            },
            {
                "op": "object.edit",
                "target": "Document.Документ",
                "parameters": {"operation": "add-ts-attribute", "value": "Строки." + name + ": Boolean"},
            },
        ],
    }
    if name == "Новое":
        editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
        assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
        with pytest.raises(editor.Rejected, match="Exact base context"):
            editor.plan_make(editor.Snapshot(target), {**payload, "operations": payload["operations"][1:]})
    else:
        with pytest.raises(editor.Rejected, match="reserved"):
            editor.plan_make(editor.Snapshot(target), payload)
        assert not (target / "Documents/Документ.xml").exists()
    assert path.read_bytes() == before


@pytest.mark.parametrize("kind", ["Enum", "InformationRegister", "DocumentJournal"])
def test_section_invalid_owner_rejected(tmp_path, kind):
    target, logical = native_owner(tmp_path, kind)
    for parameters in (
        {"operation": "add-ts", "value": "Строки"},
        {"operation": "add-ts-attribute", "value": "Строки.Поле: Boolean"},
    ):
        with pytest.raises(editor.Rejected, match="Child kind"):
            editor.plan_make(
                editor.Snapshot(target),
                {
                    "schemaVersion": 1,
                    "operations": [{"op": "object.edit", "target": logical, "parameters": parameters}],
                },
            )


@pytest.mark.parametrize("kind", ops.CONNECTED_EDIT_OBJECT_TYPES)
def test_modify_owner_property_preserves_structure_and_repeats(tmp_path, kind):
    target, logical = native_owner(tmp_path, kind)
    _, before_owner, path, original = ops.read_object(editor.Snapshot(target), logical)
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"definition": {"modify": {"properties": {"Comment": "Изменено <&>"}}}},
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    _, after_owner, _, _ = ops.read_object(editor.Snapshot(target), logical)
    assert editor.prop(after_owner, "Comment") == "Изменено <&>"
    assert editor.identity(after_owner) == editor.identity(before_owner)
    after_owner.find("m:Properties/m:Comment", editor.NS).text = editor.prop(before_owner, "Comment") or None
    assert editor.signature(after_owner) == editor.signature(before_owner)
    before = (target / path).read_bytes()
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    assert (target / path).read_bytes() == before


@pytest.mark.parametrize(
    "collection,kind",
    [
        ("attributes", "Catalog"),
        ("dimensions", "InformationRegister"),
        ("resources", "AccumulationRegister"),
        ("enumValues", "Enum"),
        ("columns", "DocumentJournal"),
    ],
)
def test_rename_child_preserves_identity_synonym_and_replays(tmp_path, collection, kind):
    target, logical = rename_owner(tmp_path, kind)
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"definition": {"add": {collection: [{"name": "Поле", "synonym": "Поле"}]}}},
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    _, owner, path, original = ops.read_object(editor.Snapshot(target), logical)
    child = borrow._member(owner, ops.ADD_KINDS[collection], "Поле")
    expected = editor.signature(child)
    if kind == "Catalog":
        etree.SubElement(owner.find("m:Properties/m:InputByString", editor.NS), f"{{{borrow.XR}}}Field").text = (
            logical + ".Attribute.Поле"
        )
        (target / path).write_bytes(editor.serialize_like(owner.getparent(), original))
    payload["operations"][0]["parameters"] = {"definition": {"modify": {collection: {"Поле": {"name": "НовоеПоле"}}}}}
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    _, owner, _, _ = ops.read_object(editor.Snapshot(target), logical)
    child = borrow._member(owner, ops.ADD_KINDS[collection], "НовоеПоле")
    present(child).find("m:Properties/m:Name", editor.NS).text = "Поле"
    assert editor.signature(child) == expected
    if kind == "Catalog":
        assert owner.find("m:Properties/m:InputByString", editor.NS)[-1].text == logical + ".Attribute.НовоеПоле"
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), payload)


@pytest.mark.parametrize(
    "obstacle",
    [
        "collision",
        "adopted",
        "bsl",
        "binary",
        "form",
        "unknown-reference",
        "unknown-expression",
        "configuration-child",
        "reference-case",
        "case",
        "alias",
        "standard",
        "standard-ru",
    ],
)
def test_rename_child_rejects_unproven_dependencies_without_writes(tmp_path, obstacle):
    target, logical = rename_owner(tmp_path, "Catalog")
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"definition": {"add": {"attributes": [{"name": "Поле"}, {"name": "Занято"}]}}},
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    _, owner, path, original = ops.read_object(editor.Snapshot(target), logical)
    if obstacle == "adopted":
        etree.SubElement(
            present(borrow._member(owner, "Attribute", "Поле")).find("m:Properties", editor.NS),
            f"{{{editor.MD}}}ObjectBelonging",
        ).text = "Adopted"
    elif obstacle == "unknown-reference":
        etree.SubElement(owner.find("m:Properties", editor.NS), f"{{{editor.MD}}}UnknownPath").text = (
            logical + ".Attribute.Поле"
        )
    elif obstacle == "unknown-expression":
        etree.SubElement(
            owner.find("m:Properties", editor.NS), f"{{{editor.MD}}}UnknownExpression"
        ).text = 'Объект["По" + "ле"]'
    elif obstacle == "reference-case":
        etree.SubElement(owner.find("m:Properties/m:InputByString", editor.NS), f"{{{borrow.XR}}}Field").text = (
            logical + ".Attribute.поле"
        )
    elif obstacle == "configuration-child":
        config_path = target / "Configuration.xml"
        config_bytes = config_path.read_bytes()
        config = editor.metadata(config_bytes, "Configuration")
        etree.SubElement(
            config.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}UnknownExpression"
        ).text = '"По" + "ле"'
        config_path.write_bytes(editor.serialize_like(config.getparent(), config_bytes))
    elif obstacle in {"bsl", "binary", "form"}:
        extra = {
            "bsl": ("Module.bsl", "ВызватьДинамически();".encode()),
            "binary": ("Form.bin", b"opaque"),
            "form": ("Form.xml", f'<Form xmlns="{editor.FORM}"/>'.encode()),
        }[obstacle]
        (target / extra[0]).write_bytes(extra[1])
    (target / path).write_bytes(editor.serialize_like(owner.getparent(), original))
    changes = {
        "Name": {"collision": "Занято", "case": "поле", "standard": "Code", "standard-ru": "Код"}.get(
            obstacle, "НовоеПоле"
        )
    }
    if obstacle == "alias":
        changes["name"] = "НовоеПоле"
    payload["operations"][0]["parameters"] = {"definition": {"modify": {"attributes": {"Поле": changes}}}}
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


def test_rename_child_updates_cross_object_reference_and_guards_read_closure(tmp_path):
    target, logical = rename_owner(tmp_path, "Document")
    initial = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"definition": {"add": {"attributes": [{"name": "Поле"}]}}},
            },
            {
                "op": "object.create",
                "target": "DocumentJournal.Журнал",
                "parameters": {
                    "definition": {
                        "type": "DocumentJournal",
                        "name": "Журнал",
                        "columns": [{"name": "Колонка", "references": [logical + ".Attribute.Поле"]}],
                    }
                },
            },
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), initial))
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"definition": {"modify": {"attributes": {"Поле": {"Name": "НовоеПоле"}}}}},
            }
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert {item["path"] for item in plan["writes"]} == {"Documents/Владелец.xml", "DocumentJournals/Журнал.xml"}
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    journal = editor.metadata((target / "DocumentJournals/Журнал.xml").read_bytes(), "DocumentJournal")
    reference = journal.find(f"m:ChildObjects/m:Column/m:Properties/m:References/{{{borrow.XR}}}Item", editor.NS)
    assert reference.text == logical + ".Attribute.НовоеПоле"
    (target / "Unexpected.bsl").write_bytes("ДинамическаяЗависимость();".encode())
    with pytest.raises(editor.Rejected):
        editor.apply(target, None, plan)


@pytest.mark.parametrize("kind", ["Configuration", "Language"])
def test_rename_shape_rejects_unknown_registration_leaf(kind):
    root = etree.Element(f"{{{editor.MD}}}MetaDataObject", version="2.17")
    owner = etree.SubElement(root, f"{{{editor.MD}}}{kind}", uuid=str(uuid.uuid4()))
    children = etree.SubElement(owner, f"{{{editor.MD}}}ChildObjects")
    etree.SubElement(children, f"{{{editor.MD}}}UnknownExpression").text = '"По" + "ле"'
    with pytest.raises(editor.Rejected):
        ops.rename_descriptor_shape(root)


def test_rename_shape_accepts_standard_attribute_type_reduction_mode():
    root = etree.Element(f"{{{editor.MD}}}MetaDataObject", version="2.20")
    owner = etree.SubElement(root, f"{{{editor.MD}}}Catalog", uuid=str(uuid.uuid4()))
    properties = etree.SubElement(owner, f"{{{editor.MD}}}Properties")
    etree.SubElement(properties, f"{{{editor.MD}}}Name").text = "Владелец"
    standard_attributes = etree.SubElement(properties, f"{{{editor.MD}}}StandardAttributes")
    standard = etree.SubElement(standard_attributes, f"{{{borrow.XR}}}StandardAttribute", name="Code")
    etree.SubElement(standard, f"{{{borrow.XR}}}TypeReductionMode").text = "TransformValues"
    ops.rename_descriptor_shape(root)


@pytest.mark.parametrize("kind", ["CommonPicture", "StyleItem"])
def test_rename_shape_accepts_only_adopted_visual_shell(kind):
    base = etree.Element(f"{{{editor.MD}}}{kind}", uuid=str(uuid.uuid4()))
    root = editor.xml_read(
        borrow._shell(kind, "Оформление", base, str(uuid.uuid4()), {}), f"{{{editor.MD}}}MetaDataObject"
    )
    ops.rename_descriptor_shape(root)
    properties = root[0].find("m:Properties", editor.NS)
    etree.SubElement(properties, f"{{{editor.MD}}}UnknownReference").text = "Catalog.Чужой"
    with pytest.raises(editor.Rejected, match="Unsupported rename dependency structure"):
        ops.rename_descriptor_shape(root)


def test_rename_shape_accepts_configuration_module_property_state():
    source = Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe/Configuration.xml"
    root = editor.xml_read(source.read_bytes(), f"{{{editor.MD}}}MetaDataObject")
    internal = root[0].find("m:InternalInfo", editor.NS)
    if internal is None:
        internal = etree.SubElement(root[0], f"{{{editor.MD}}}InternalInfo")
    state = etree.SubElement(internal, f"{{{borrow.XR}}}PropertyState")
    etree.SubElement(state, f"{{{borrow.XR}}}Property").text = "ManagedApplicationModule"
    etree.SubElement(state, f"{{{borrow.XR}}}State").text = "Extended"
    ops.rename_descriptor_shape(root)
    etree.SubElement(state, f"{{{borrow.XR}}}UnknownReference")
    with pytest.raises(editor.Rejected, match="Unknown (configuration )?property state structure"):
        ops.rename_descriptor_shape(root)


def test_dependency_shape_accepts_only_empty_exchange_plan_characteristics():
    root = editor.xml_read(
        create.render_object({"type": "ExchangePlan", "name": "План"}, str(uuid.uuid4()), {}),
        f"{{{editor.MD}}}MetaDataObject",
    )
    field = etree.SubElement(root[0].find("m:Properties", editor.NS), f"{{{editor.MD}}}Characteristics")
    ops.rename_descriptor_shape(root)
    etree.SubElement(field, f"{{{editor.MD}}}UnknownReference")
    with pytest.raises(editor.Rejected, match="Unsupported nonempty Characteristics"):
        ops.rename_descriptor_shape(root)
    field.clear()
    field.text = "Не пусто"
    with pytest.raises(editor.Rejected, match="Unsupported nonempty Characteristics"):
        ops.rename_descriptor_shape(root)


def test_rename_shape_accepts_native_dependency_descriptor_fields():
    def root_for(kind, name):
        root = etree.Element(f"{{{editor.MD}}}MetaDataObject", version="2.20")
        owner = etree.SubElement(root, f"{{{editor.MD}}}{kind}", uuid=str(uuid.uuid4()))
        properties = etree.SubElement(owner, f"{{{editor.MD}}}Properties")
        etree.SubElement(properties, f"{{{editor.MD}}}Name").text = name
        etree.SubElement(owner, f"{{{editor.MD}}}ChildObjects")
        return root, owner, properties

    root, owner, properties = root_for("Catalog", "Каталог")
    sections = etree.SubElement(owner.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}TabularSection")
    section_properties = etree.SubElement(sections, f"{{{editor.MD}}}Properties")
    etree.SubElement(section_properties, f"{{{editor.MD}}}Name").text = "Таблица"
    etree.SubElement(section_properties, f"{{{editor.MD}}}LineNumberLength").text = "9"
    ops.rename_descriptor_shape(root)

    root, owner, properties = root_for("InformationRegister", "Регистр")
    dimensions = etree.SubElement(owner.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}Dimension")
    dimension_properties = etree.SubElement(dimensions, f"{{{editor.MD}}}Properties")
    etree.SubElement(dimension_properties, f"{{{editor.MD}}}Name").text = "Измерение"
    etree.SubElement(dimension_properties, f"{{{editor.MD}}}TypeReductionMode").text = "TransformValues"
    ops.rename_descriptor_shape(root)

    root, owner, properties = root_for("Document", "Документ")
    attributes = etree.SubElement(owner.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}Attribute")
    attribute_properties = etree.SubElement(attributes, f"{{{editor.MD}}}Properties")
    etree.SubElement(attribute_properties, f"{{{editor.MD}}}Name").text = "Реквизит"
    typed = etree.SubElement(attribute_properties, f"{{{editor.MD}}}Type")
    etree.SubElement(typed, f"{{{editor.V8}}}TypeId").text = str(uuid.uuid4())
    ops.rename_descriptor_shape(root)

    root, owner, properties = root_for("CommonModule", "Модуль")
    owner.remove(owner.find("m:ChildObjects", editor.NS))
    etree.SubElement(owner, f"{{{editor.MD}}}InternalInfo")
    ops.rename_descriptor_shape(root)

    root, owner, properties = root_for("Enum", "Перечисление")
    internal = etree.SubElement(owner, f"{{{editor.MD}}}InternalInfo")
    generated = etree.SubElement(internal, f"{{{borrow.XR}}}GeneratedType", name="EnumRef.Перечисление", category="Ref")
    etree.SubElement(generated, f"{{{borrow.XR}}}TypeId").text = str(uuid.uuid4())
    etree.SubElement(generated, f"{{{borrow.XR}}}ValueId").text = str(uuid.uuid4())
    enum_value = etree.SubElement(owner.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}EnumValue")
    etree.SubElement(enum_value, f"{{{editor.MD}}}InternalInfo")
    ops.rename_descriptor_shape(root)

    root, owner, properties = root_for("EventSubscription", "Подписка")
    owner.remove(owner.find("m:ChildObjects", editor.NS))
    source = etree.SubElement(properties, f"{{{editor.MD}}}Source")
    etree.SubElement(source, f"{{{editor.V8}}}TypeId").text = str(uuid.uuid4())
    ops.rename_descriptor_shape(root)

    root, owner, properties = root_for("ChartOfCharacteristicTypes", "ВидыСубконто")
    typed = etree.Element(
        f"{{{editor.MD}}}Type", nsmap={"v8": editor.V8, "cfg": borrow.CFG, "xr": borrow.XR, "xsi": ops.XSI}
    )
    typed.set(f"{{{ops.XSI}}}type", "xr:ExtendedProperty")
    extended = etree.SubElement(typed, f"{{{borrow.XR}}}ExtendValue", {f"{{{ops.XSI}}}type": "v8:TypeDescription"})
    etree.SubElement(extended, f"{{{editor.V8}}}Type").text = "cfg:CatalogRef.Заказы"
    properties.append(typed)
    ops.rename_descriptor_shape(root)


@pytest.mark.parametrize("kind", create.KINDS)
def test_rename_root_preserves_ids_and_moves_files_atomically(tmp_path, kind):
    target, logical = rename_owner(tmp_path, kind)
    _, before_owner, old_path, _ = ops.read_object(editor.Snapshot(target), logical)
    before_ids = [
        (node.tag, node.get("uuid"), node.text if etree.QName(node).localname in {"TypeId", "ValueId"} else None)
        for node in before_owner.iter()
        if isinstance(node.tag, str)
    ]
    synonym = etree.tostring(before_owner.find("m:Properties/m:Synonym", editor.NS))
    modules = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*.bsl")}
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"definition": {"modify": {"properties": {"Name": "НовоеИмя"}}}},
            }
        ],
    }
    before_files = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert before_files == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    assert not (target / old_path).exists()
    _, after_owner, new_path, _ = ops.read_object(editor.Snapshot(target), kind + ".НовоеИмя")
    assert new_path == old_path.replace("/Владелец.xml", "/НовоеИмя.xml")
    after_ids = [
        (node.tag, node.get("uuid"), node.text if etree.QName(node).localname in {"TypeId", "ValueId"} else None)
        for node in after_owner.iter()
        if isinstance(node.tag, str)
    ]
    assert after_ids == before_ids
    assert etree.tostring(after_owner.find("m:Properties/m:Synonym", editor.NS)) == synonym
    for property_name in ("Key", "RootURL", "Description"):
        assert editor.prop(after_owner, property_name) == editor.prop(before_owner, property_name)
    for path, data in modules.items():
        moved = path.replace("/Владелец/", "/НовоеИмя/")
        assert not (target / path).exists()
        assert (target / moved).read_bytes() == data
    assert all(
        part.get("name").split(".")[1] == "НовоеИмя" for part in after_owner.iter(f"{{{borrow.XR}}}GeneratedType")
    )


@pytest.mark.parametrize("kind", ops.RENAME_OBJECT_TYPES)
def test_explicit_rename_reuses_existing_plan_and_replays(tmp_path, kind):
    target, logical = rename_owner(tmp_path, kind)
    operation = {"op": "object.rename", "target": logical, "parameters": {"name": "НовоеИмя"}}
    request = {"schemaVersion": 1, "operations": [operation]}
    legacy = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"definition": {"modify": {"properties": {"Name": "НовоеИмя"}}}},
            }
        ],
    }
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    plan = editor.plan_make(editor.Snapshot(target), request)
    previous = editor.plan_make(editor.Snapshot(target), legacy)
    assert plan["writes"] == previous["writes"]
    assert plan["manifest"] == previous["manifest"]
    assert plan["request"] == request
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"


def test_common_module_rename_updates_platform_config_dump_info_and_reviews_source_json(tmp_path):
    # Flat ConfigDumpInfo entries and an xUnit provenance file in the shape Designer and the template write.
    dependency_fixtures = Path(__file__).parents[1] / "fixtures/metadata-edit/rename-dependencies"
    old_name = "Демо_ТестыПрототипаОбмена"
    new_name = "Демо_ТестыОбменаСистем"
    logical = "CommonModule." + old_name
    moved = "CommonModules/" + new_name + ".xml"
    target, _ = rename_owner(tmp_path, "CommonModule")
    owner_path = target / "CommonModules/Владелец.xml"
    owner_bytes = owner_path.read_bytes()
    owner = editor.metadata(owner_bytes, "CommonModule")
    owner.find("m:Properties/m:Name", editor.NS).text = old_name
    owner_path.rename(target / ("CommonModules/" + old_name + ".xml"))
    (target / ("CommonModules/" + old_name + ".xml")).write_bytes(editor.serialize_like(owner.getparent(), owner_bytes))
    config_path = target / "Configuration.xml"
    config_bytes = config_path.read_bytes()
    config_root = editor.xml_read(config_bytes, f"{{{editor.MD}}}MetaDataObject")
    config_root.find("m:Configuration/m:ChildObjects/m:CommonModule", editor.NS).text = old_name
    config_path.write_bytes(editor.serialize_like(config_root, config_bytes))
    dump_path = target / "ConfigDumpInfo.xml"
    source_path = target / "SOURCE.json"
    dump_before = (dependency_fixtures / "ConfigDumpInfo.xml").read_bytes()
    # Узкий формат читателя: только плоские записи; вложенные записи заимствованных
    # объектов из реальной выгрузки отбрасываются, читатель отклоняет их отдельно.
    dump_root = editor.xml_read(dump_before, f"{{{ops.DUMPINFO}}}ConfigDumpInfo")
    for item in [item for item in dump_root[0] if len(item)]:
        dump_root[0].remove(item)
    dump_before = editor.serialize_like(dump_root, dump_before)
    dump_root = ops.read_config_dump_info(dump_before, "ConfigDumpInfo.xml")
    identity_before = editor.identity(owner)
    for name_value, id_value, version in (
        (logical, identity_before, "a" * 40),
        (logical + ".Module", identity_before + ".0", "b" * 40),
    ):
        etree.SubElement(
            dump_root[0], f"{{{ops.DUMPINFO}}}Metadata", name=name_value, id=id_value, configVersion=version
        )
    dump_path.write_bytes(editor.serialize_like(dump_root, dump_before))
    dump_before = dump_path.read_bytes()
    shutil.copyfile(dependency_fixtures / "SOURCE.json", source_path)
    source_before = source_path.read_bytes()
    old_entries = ops.read_config_dump_info(dump_before, "ConfigDumpInfo.xml")
    old_versions = [(item.get("name"), item.get("id"), item.get("configVersion")) for item in old_entries[0]]

    def rename_request(reviewed=True):
        parameters: dict[str, Any] = {"name": new_name}
        if reviewed:
            parameters["reviewedDependencies"] = [
                {
                    "path": "SOURCE.json",
                    "sha256": editor.digest(source_path.read_bytes()),
                    "reason": "Reviewed provenance; it has no metadata reference",
                }
            ]
        return {
            "schemaVersion": 1,
            "operations": [{"op": "object.rename", "target": logical, "parameters": parameters}],
        }

    with pytest.raises(editor.Rejected, match="Cannot prove dependencies in SOURCE.json"):
        editor.plan_make(editor.Snapshot(target), rename_request(reviewed=False))

    unknown_root = ops.read_config_dump_info(dump_before, "ConfigDumpInfo.xml")
    unknown_root.set("futureAttribute", "unsupported")
    dump_path.write_bytes(editor.serialize_like(unknown_root, dump_before))
    unknown_before = {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}
    with pytest.raises(editor.Rejected, match="Unsupported ConfigDumpInfo structure"):
        editor.plan_make(editor.Snapshot(target), rename_request())
    assert unknown_before == {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}
    dump_path.write_bytes(dump_before)

    provenance = json.loads(source_before.decode("utf-8"))
    provenance["removedApplicationTest"] = logical
    source_path.write_text(json.dumps(provenance, ensure_ascii=False), encoding="utf-8")
    referenced_before = {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}
    with pytest.raises(editor.Rejected, match="Unresolved rename dependency: SOURCE.json"):
        editor.plan_make(editor.Snapshot(target), rename_request())
    assert referenced_before == {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}
    source_path.write_bytes(source_before)

    source_path.write_bytes(b'{"duplicate":"safe","duplicate":"CommonModule.old"}')
    duplicate_before = {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}
    with pytest.raises(editor.Rejected, match="Duplicate JSON key"):
        editor.plan_make(editor.Snapshot(target), rename_request())
    assert duplicate_before == {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}
    source_path.write_bytes(source_before)

    plan = editor.plan_make(editor.Snapshot(target), rename_request())
    assert dump_path.read_bytes() == dump_before
    assert source_path.read_bytes() == source_before
    dump_write = next(item for item in plan["writes"] if item["path"] == "ConfigDumpInfo.xml")
    after_dump = ops.read_config_dump_info(base64.b64decode(dump_write["after"]["data"]), "ConfigDumpInfo.xml")
    after_versions = [(item.get("name"), item.get("id"), item.get("configVersion")) for item in after_dump[0]]
    assert after_dump.attrib == old_entries.attrib
    assert after_versions == [
        (
            "CommonModule." + new_name
            if name == logical
            else "CommonModule." + new_name + ".Module"
            if name == logical + ".Module"
            else name,
            identity,
            version,
        )
        for name, identity, version in old_versions
    ]
    assert all(name != logical and name != logical + ".Module" for name, _, _ in after_versions)
    module_write = next(item for item in plan["writes"] if item["path"] == moved)
    owner_after = editor.metadata(base64.b64decode(module_write["after"]["data"]), "CommonModule")
    assert editor.identity(owner_after) == identity_before
    assert "SOURCE.json" not in {item["path"] for item in plan["writes"]}
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    assert source_path.read_bytes() == source_before


@pytest.mark.parametrize("kind", ["ExternalDataProcessor", "ExternalReport"])
def test_external_rename_keeps_designer_contained_object(tmp_path, kind):
    target, logical = rename_owner(tmp_path, kind)
    path = target / "Владелец.xml"
    owner = editor.metadata(path.read_bytes(), kind)
    internal = owner.find("m:InternalInfo", editor.NS)
    contained = etree.Element(f"{{{borrow.XR}}}ContainedObject")
    etree.SubElement(contained, f"{{{borrow.XR}}}ClassId").text = str(uuid.uuid4())
    etree.SubElement(contained, f"{{{borrow.XR}}}ObjectId").text = str(uuid.uuid4())
    internal.insert(0, contained)
    path.write_bytes(etree.tostring(owner.getparent()))
    before = etree.tostring(contained)
    request = {
        "schemaVersion": 1,
        "operations": [{"op": "object.rename", "target": logical, "parameters": {"name": "НовоеИмя"}}],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert editor.apply(target, None, plan) == "applied"
    assert not path.exists()
    renamed = editor.metadata((target / "НовоеИмя.xml").read_bytes(), kind)
    assert etree.tostring(renamed.find("m:InternalInfo/xr:ContainedObject", {**editor.NS, "xr": borrow.XR})) == before
    assert editor.node_name(renamed) == "НовоеИмя"
    extra = copy.deepcopy(contained)
    etree.SubElement(extra, f"{{{borrow.XR}}}Unknown")
    renamed.find("m:InternalInfo", editor.NS).insert(0, extra)
    (target / "НовоеИмя.xml").write_bytes(etree.tostring(renamed.getparent()))
    with pytest.raises(editor.Rejected):
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [{"op": "object.rename", "target": kind + ".НовоеИмя", "parameters": {"name": "Другое"}}],
            },
        )


@pytest.mark.parametrize("obstacle", ["kind", "parameters", "collision"])
def test_explicit_rename_rejects_without_source_writes(tmp_path, obstacle):
    kind = "Document" if obstacle == "kind" else "Catalog"
    target, logical = rename_owner(tmp_path, kind)
    parameters: dict[str, Any] = {"name": "НовоеИмя"}
    if obstacle == "parameters":
        parameters["force"] = True
    elif obstacle == "collision":
        (target / "Catalogs/НовоеИмя.xml").write_bytes((target / "Catalogs/Владелец.xml").read_bytes())
    request = {"schemaVersion": 1, "operations": [{"op": "object.rename", "target": logical, "parameters": parameters}]}
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), request)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


def test_structural_rename_records_opaque_dependencies_and_preserves_bytes(tmp_path):
    target, logical = rename_owner(tmp_path, "Catalog")
    folder = target / "Catalogs/Владелец/Ext"
    folder.mkdir(parents=True, exist_ok=True)
    module = folder / "ObjectModule.bsl"
    module.write_bytes("ДинамическийВызов();".encode())
    (folder / "Unknown.bin").write_bytes(b"opaque")
    request = {
        "schemaVersion": 1,
        "operations": [{"op": "object.rename", "target": logical, "parameters": {"name": "НовоеИмя"}}],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    pending = {item["path"]: item for item in plan["pendingDependencies"]}
    moved = "Catalogs/НовоеИмя/Ext/ObjectModule.bsl"
    assert pending[moved]["sha256"] == editor.digest(module.read_bytes())
    assert pending[moved]["targets"] == [logical]
    assert pending[moved]["reason"] == "bsl-review"
    assert plan["checks"]["dependencies"] == "pending"
    assert plan["checks"]["structure"] == "supported-descriptors-only"
    assert editor.apply(target, None, plan) == "applied"
    assert (target / moved).read_bytes() == "ДинамическийВызов();".encode()
    assert editor.apply(target, None, plan) == "already-applied"


@pytest.mark.parametrize("kind", ["Form", "CommonForm", "CommonCommand", "CommonTemplate"])
@pytest.mark.parametrize("empty_internal", [False, True])
def test_rename_reads_form_descriptors_but_not_root_analyzer_cache(tmp_path, kind, empty_internal):
    target, logical = rename_owner(tmp_path, "Catalog")
    cache = target / ".build"
    cache.mkdir()
    (cache / "bsl-graph.db").write_bytes(b"opaque-cache")
    descriptor = target / ("Catalogs/Владелец/Forms/Форма.xml" if kind == "Form" else kind + "s/Форма.xml")
    descriptor.parent.mkdir(parents=True, exist_ok=True)
    root = etree.Element(f"{{{editor.MD}}}MetaDataObject", nsmap={None: editor.MD}, version="2.17")
    node = etree.SubElement(root, f"{{{editor.MD}}}{kind}", uuid=str(uuid.uuid4()))
    if empty_internal and kind in {"Form", "CommonForm"}:
        etree.SubElement(node, f"{{{editor.MD}}}InternalInfo")
    props = etree.SubElement(node, f"{{{editor.MD}}}Properties")
    etree.SubElement(props, f"{{{editor.MD}}}Name").text = "Форма"
    if kind == "CommonTemplate":
        etree.SubElement(props, f"{{{editor.MD}}}TemplateType").text = "TextDocument"
    elif kind == "CommonCommand":
        etree.SubElement(props, f"{{{editor.MD}}}CommandParameterType")
    else:
        etree.SubElement(props, f"{{{editor.MD}}}FormType").text = "Managed"
    original = etree.tostring(root)
    descriptor.write_bytes(original)
    template_body = None
    if kind == "CommonTemplate":
        template_body = descriptor.with_suffix("") / "Ext/Template.txt"
        template_body.parent.mkdir(parents=True)
        template_body.write_bytes(b"opaque-template-content")
    request = {
        "schemaVersion": 1,
        "operations": [{"op": "object.rename", "target": logical, "parameters": {"name": "НовоеИмя"}}],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert editor.apply(target, None, plan) == "applied"
    final = target / ("Catalogs/НовоеИмя/Forms/Форма.xml" if kind == "Form" else kind + "s/Форма.xml")
    assert final.read_bytes() == original
    if kind == "CommonTemplate":
        template_body = present(template_body)
        assert template_body.read_bytes() == b"opaque-template-content"
        assert any(
            item["path"] == template_body.relative_to(target).as_posix()
            and item["reason"] == "embedded-artifact-review"
            for item in plan["pendingDependencies"]
        )
    (cache / "bsl-graph.db").write_bytes(b"updated-cache")
    assert editor.apply(target, None, plan) == "already-applied"
    if empty_internal and kind in {"Form", "CommonForm"}:
        internal = node.find("m:InternalInfo", editor.NS)
        etree.SubElement(internal, f"{{{editor.MD}}}UnknownReference").text = "Catalog.НовоеИмя"
        final.write_bytes(etree.tostring(root))
        with pytest.raises(editor.Rejected):
            editor.plan_make(
                editor.Snapshot(target),
                {
                    "schemaVersion": 1,
                    "operations": [
                        {"op": "object.rename", "target": "Catalog.НовоеИмя", "parameters": {"name": "ДругоеИмя"}}
                    ],
                },
            )
        internal.remove(internal[0])
    etree.SubElement(props, f"{{{editor.MD}}}UnknownReference").text = "Catalog.НовоеИмя"
    final.write_bytes(etree.tostring(root))
    with pytest.raises(editor.Rejected):
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [
                    {"op": "object.rename", "target": "Catalog.НовоеИмя", "parameters": {"name": "ДругоеИмя"}}
                ],
            },
        )


@pytest.mark.parametrize(
    "kind,property_name",
    [
        ("Catalog", "DefaultObjectForm"),
        ("Catalog", "AuxiliaryObjectForm"),
        ("InformationRegister", "DefaultRecordForm"),
        ("InformationRegister", "AuxiliaryRecordForm"),
    ],
)
def test_rename_updates_default_form_reference_without_replacing_form(tmp_path, kind, property_name):
    target, logical = rename_owner(tmp_path, kind)
    directory = borrow.DIRECTORIES[kind]
    source = target / directory / "Владелец.xml"
    original = source.read_bytes()
    node = editor.metadata(original, kind)
    reference = node.find("m:Properties/m:" + property_name, editor.NS)
    reference.text = logical + ".Form.Форма"
    source.write_bytes(editor.serialize_like(node.getparent(), original))
    plan = editor.plan_make(
        editor.Snapshot(target),
        {
            "schemaVersion": 1,
            "operations": [{"op": "object.rename", "target": logical, "parameters": {"name": "НовоеИмя"}}],
        },
    )
    after = next(item for item in plan["writes"] if item["path"] == directory + "/НовоеИмя.xml")
    import base64

    renamed = editor.metadata(base64.b64decode(after["after"]["data"]), kind)
    assert editor.prop(renamed, property_name) == kind + ".НовоеИмя.Form.Форма"
    assert editor.identity(renamed) == editor.identity(node)
    reference.text = "CommonModule.Посторонний.Form.Форма"
    source.write_bytes(editor.serialize_like(node.getparent(), original))
    with pytest.raises(editor.Rejected):
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [{"op": "object.rename", "target": logical, "parameters": {"name": "НовоеИмя"}}],
            },
        )


def _rename_form_fixture(tmp_path):
    target, logical = rename_owner(tmp_path, "Catalog")
    form_target = logical + ".Form.Форма"
    create_request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.create",
                "target": logical,
                "parameters": {"name": "Форма", "synonym": "Форма", "purpose": "List", "setDefault": False},
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), create_request))
    physical = Path("Catalogs/Владелец/Forms/Форма/Ext/Form.xml")
    body_path = target / physical
    body_bytes = body_path.read_bytes()
    body = editor.xml_read(body_bytes, f"{{{editor.FORM}}}Form")
    attributes = body.find("f:Attributes", editor.NS)
    reference = etree.SubElement(attributes, f"{{{editor.FORM}}}Attribute", name="Ссылка", id="900")
    reference_type = etree.SubElement(reference, f"{{{editor.FORM}}}Type")
    etree.SubElement(reference_type, f"{{{editor.V8}}}Type", nsmap={"cfg": borrow.CFG}).text = "cfg:CatalogRef.Владелец"
    table = etree.SubElement(attributes, f"{{{editor.FORM}}}Attribute", name="Таблица", id="901")
    columns = etree.SubElement(table, f"{{{editor.FORM}}}Columns")
    column = etree.SubElement(columns, f"{{{editor.FORM}}}Column", name="Владелец", id="902")
    column_type = etree.SubElement(column, f"{{{editor.FORM}}}Type")
    etree.SubElement(column_type, f"{{{editor.V8}}}Type", nsmap={"cfg": borrow.CFG}).text = "cfg:CatalogObject.Владелец"
    parameters = etree.SubElement(body, f"{{{editor.FORM}}}Parameters")
    parameter = etree.SubElement(parameters, f"{{{editor.FORM}}}Parameter", name="Параметр", id="903")
    parameter_type = etree.SubElement(parameter, f"{{{editor.FORM}}}Type")
    etree.SubElement(parameter_type, f"{{{editor.V8}}}Type", nsmap={"cfg": borrow.CFG}).text = "cfg:CatalogRef.Владелец"
    etree.SubElement(body.find("f:ChildItems", editor.NS), f"{{{editor.FORM}}}Unrelated", id="904").text = "keep"
    body_path.write_bytes(editor.serialize_like(body, body_bytes))
    return target, logical, form_target, body_path


def test_explicit_rename_rewrites_selected_form_types_main_table_and_preserves_ids(tmp_path):
    target, logical, form_target, body_path = _rename_form_fixture(tmp_path)
    before = body_path.read_bytes()
    before_body = editor.xml_read(before, f"{{{editor.FORM}}}Form")
    before_ids = [(node.tag, node.get("id")) for node in before_body.iter() if node.get("id")]
    request = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.rename", "target": logical, "parameters": {"name": "НовоеИмя", "forms": [form_target]}}
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    renamed_path = "Catalogs/НовоеИмя/Forms/Форма/Ext/Form.xml"
    after_item = next(item for item in plan["writes"] if item["path"] == renamed_path)
    import base64

    after = editor.xml_read(base64.b64decode(after_item["after"]["data"]), f"{{{editor.FORM}}}Form")
    assert [(node.tag, node.get("id")) for node in after.iter() if node.get("id")] == before_ids
    assert after.findtext("f:ChildItems/f:Unrelated", namespaces=editor.NS) == "keep"
    assert (
        after.findtext('f:Attributes/f:Attribute[@name="Ссылка"]/f:Type/v8:Type', namespaces=editor.NS)
        == "cfg:CatalogRef.НовоеИмя"
    )
    assert (
        after.findtext(
            'f:Attributes/f:Attribute[@name="Таблица"]/f:Columns/f:Column/f:Type/v8:Type', namespaces=editor.NS
        )
        == "cfg:CatalogObject.НовоеИмя"
    )
    assert after.findtext("f:Parameters/f:Parameter/f:Type/v8:Type", namespaces=editor.NS) == "cfg:CatalogRef.НовоеИмя"
    assert (
        after.findtext('f:Attributes/f:Attribute[@name="Список"]/f:Settings/f:MainTable', namespaces=editor.NS)
        == "Catalog.НовоеИмя"
    )
    assert any(item["path"] == renamed_path for item in plan["pendingDependencies"])


def test_explicit_rename_without_forms_keeps_form_body_and_rejects_ambiguous_or_bad_refs(tmp_path):
    target, logical, form_target, body_path = _rename_form_fixture(tmp_path)
    before = body_path.read_bytes()
    request = {
        "schemaVersion": 1,
        "operations": [{"op": "object.rename", "target": logical, "parameters": {"name": "НовоеИмя"}}],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    import base64

    moved = next(item for item in plan["writes"] if item["path"] == "Catalogs/НовоеИмя/Forms/Форма/Ext/Form.xml")
    assert base64.b64decode(moved["after"]["data"]) == before

    duplicate = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.rename",
                "target": logical,
                "parameters": {"name": "НовоеИмя", "forms": [form_target, form_target.lower()]},
            }
        ],
    }
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), duplicate)

    body = editor.xml_read(before, f"{{{editor.FORM}}}Form")
    bad_type = body.find('f:Attributes/f:Attribute[@name="Ссылка"]/f:Type/v8:Type', editor.NS)
    bad_type.text = "bad:CatalogRef.Владелец"
    body_path.write_bytes(editor.serialize_like(body, before))
    bad = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.rename", "target": logical, "parameters": {"name": "НовоеИмя", "forms": [form_target]}}
        ],
    }
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), bad)


def test_pending_review_cannot_be_removed_or_made_stale(tmp_path):
    import copy

    target, logical = rename_owner(tmp_path, "Catalog")
    module = target / "Module.bsl"
    module.write_bytes(b"opaque")
    request = {
        "schemaVersion": 1,
        "operations": [{"op": "object.rename", "target": logical, "parameters": {"name": "НовоеИмя"}}],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    tampered = copy.deepcopy(plan)
    del tampered["pendingDependencies"]
    tampered["checks"] = {"structure": "passed", "platform": "not-run", "runtime": "not-run"}
    with pytest.raises(editor.Rejected):
        editor.apply(target, None, tampered)
    module.write_bytes(b"changed")
    with pytest.raises(editor.Rejected):
        editor.apply(target, None, plan)
    assert (target / "Catalogs/Владелец.xml").exists()


def test_rename_preserves_mixed_eol_and_checks_only_changed_types(tmp_path):
    target, logical = rename_owner(tmp_path, "Catalog")
    source = target / "Catalogs/Владелец.xml"
    owner = editor.metadata(source.read_bytes(), "Catalog")
    # An existing dependency can belong to the base configuration and must not
    # become a new adoption requirement just because the owner is renamed.
    attribute = etree.SubElement(
        owner.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}Attribute", uuid=str(uuid.uuid4())
    )
    props = etree.SubElement(attribute, f"{{{editor.MD}}}Properties")
    etree.SubElement(props, f"{{{editor.MD}}}Name").text = "СтароеПоле"
    typed = etree.SubElement(props, f"{{{editor.MD}}}Type")
    etree.SubElement(typed, f"{{{editor.V8}}}Type", nsmap={"cfg": borrow.CFG}).text = "cfg:CatalogRef.ВБазе"
    etree.indent(owner.getparent(), space="\t")
    source.write_bytes(editor.serialize_like(owner.getparent(), source.read_bytes()))
    config = target / "Configuration.xml"
    config.write_bytes(config.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n", 1))
    before = config.read_bytes()
    plan = editor.plan_make(
        editor.Snapshot(target),
        {
            "schemaVersion": 1,
            "operations": [{"op": "object.rename", "target": logical, "parameters": {"name": "НовоеИмя"}}],
        },
    )
    assert editor.apply(target, None, plan) == "applied"
    assert config.read_bytes() == before.replace("Владелец".encode(), "НовоеИмя".encode())
    assert editor.apply(target, None, plan) == "already-applied"


def test_mixed_eol_serializer_still_rejects_changed_layout():
    original = b'<?xml version="1.0" encoding="UTF-8"?>\r\n<Root>\n<A/>\r\n</Root>\n'
    root = editor.xml_read(original, "Root")
    root[0].tail = "\n\n"
    with pytest.raises(editor.Rejected, match="Mixed EOL layout changed"):
        editor.serialize_like(root, original, preserve_mixed_eol=True)


def test_batch_rename_retains_pending_targets_at_final_path(tmp_path):
    target, logical = rename_owner(tmp_path, "Catalog")
    request = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.rename", "target": logical, "parameters": {"name": "Промежуточное"}},
            {"op": "object.rename", "target": "Catalog.Промежуточное", "parameters": {"name": "Итоговое"}},
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    pending = next(
        item for item in plan["pendingDependencies"] if item["path"] == "Catalogs/Итоговое/Ext/ObjectModule.bsl"
    )
    assert pending["targets"] == sorted([logical, "Catalog.Промежуточное"])
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"


def test_structural_rename_still_rejects_ambiguous_descriptor(tmp_path):
    target, logical = rename_owner(tmp_path, "Catalog")
    source = target / "Catalogs/Владелец.xml"
    data = source.read_bytes()
    owner = editor.metadata(data, "Catalog")
    etree.SubElement(owner.find("m:Properties", editor.NS), f"{{{editor.MD}}}UnknownReference").text = logical
    source.write_bytes(editor.serialize_like(owner.getparent(), data))
    before = source.read_bytes()
    with pytest.raises(editor.Rejected):
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [{"op": "object.rename", "target": logical, "parameters": {"name": "НовоеИмя"}}],
            },
        )
    assert source.read_bytes() == before


def test_rename_root_updates_types_and_tabular_generated_names(tmp_path):
    target, logical = rename_owner(tmp_path, "Catalog")
    initial = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {
                    "definition": {"add": {"tabularSections": [{"name": "Строки", "attributes": [{"name": "Поле"}]}]}}
                },
            },
            {
                "op": "object.create",
                "target": "Document.Документ",
                "parameters": {
                    "definition": {
                        "type": "Document",
                        "name": "Документ",
                        "attributes": [{"name": "Каталог", "type": "CatalogRef.Владелец"}],
                    }
                },
            },
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), initial))
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {
                    "definition": {"modify": {"properties": {"Name": "НовоеИмя", "Comment": "Явное изменение"}}}
                },
            }
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    _, owner, _, _ = ops.read_object(editor.Snapshot(target), "Catalog.НовоеИмя")
    assert editor.prop(owner, "Comment") == "Явное изменение"
    assert all(part.get("name").split(".")[1] == "НовоеИмя" for part in owner.iter(f"{{{borrow.XR}}}GeneratedType"))
    _, document, _, _ = ops.read_object(editor.Snapshot(target), "Document.Документ")
    typed = document.find("m:ChildObjects/m:Attribute/m:Properties/m:Type/v8:Type", editor.NS)
    assert typed.text == "cfg:CatalogRef.НовоеИмя" and typed.nsmap["cfg"] == borrow.CFG


@pytest.mark.parametrize("obstacle", ["file", "folder", "registration", "case", "adopted", "module", "type-case"])
def test_rename_root_rejects_unsafe_destination_and_dependencies(tmp_path, obstacle):
    target, logical = rename_owner(tmp_path, "Catalog")
    _, owner, path, original = ops.read_object(editor.Snapshot(target), logical)
    if obstacle == "file":
        (target / "Catalogs/НовоеИмя.xml").write_bytes(original)
    elif obstacle == "folder":
        (target / "Catalogs/НовоеИмя").mkdir()
    elif obstacle == "registration":
        config_path = target / "Configuration.xml"
        config_bytes = config_path.read_bytes()
        config = editor.metadata(config_bytes, "Configuration")
        etree.SubElement(config.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}Catalog").text = "НовоеИмя"
        config_path.write_bytes(editor.serialize_like(config.getparent(), config_bytes))
    elif obstacle == "adopted":
        owner.find("m:Properties/m:ObjectBelonging", editor.NS).text = "Adopted"
        (target / path).write_bytes(editor.serialize_like(owner.getparent(), original))
    elif obstacle == "module":
        (target / "Module.bsl").write_bytes("ДинамическийВызов();".encode())
    elif obstacle == "type-case":
        # The editor no longer writes an unresolved case variant itself, so the
        # existing reference is changed on disk as a user edit would do.
        other = {
            "schemaVersion": 1,
            "operations": [
                {
                    "op": "object.create",
                    "target": "Document.Документ",
                    "parameters": {
                        "definition": {
                            "type": "Document",
                            "name": "Документ",
                            "attributes": [{"name": "Поле", "type": "CatalogRef.Владелец"}],
                        }
                    },
                }
            ],
        }
        assert editor.apply(target, None, editor.plan_make(editor.Snapshot(target), other)) == "applied"
        document_path = target / "Documents/Документ.xml"
        document_bytes = document_path.read_bytes()
        document = editor.metadata(document_bytes, "Document")
        typed = document.find("m:ChildObjects/m:Attribute/m:Properties/m:Type/v8:Type", editor.NS)
        assert typed.text == "cfg:CatalogRef.Владелец"
        typed.text = "cfg:CatalogRef.владелец"
        document_path.write_bytes(editor.serialize_like(document.getparent(), document_bytes))
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {
                    "definition": {"modify": {"properties": {"Name": "владелец" if obstacle == "case" else "НовоеИмя"}}}
                },
            }
        ],
    }
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected, match="Case-ambiguous type reference" if obstacle == "type-case" else None):
        editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


@pytest.mark.parametrize("kind", ["ExternalReport", "ExternalDataProcessor"])
def test_rename_external_root_moves_empty_module_without_rewriting_bytes(tmp_path, kind):
    target = tmp_path / "target"
    target.mkdir()
    logical = kind + ".Владелец"
    base_kind = kind.removeprefix("External")
    owner = editor.metadata(
        create.render_object({"type": base_kind, "name": "Владелец"}, str(uuid.uuid4()), {}), base_kind
    )
    owner.tag = f"{{{editor.MD}}}{kind}"
    (target / "Владелец.xml").write_bytes(etree.tostring(owner.getparent()))
    module_path = target / "Владелец/Ext/ObjectModule.bsl"
    module_path.parent.mkdir(parents=True)
    module_bytes = b"\xef\xbb\xbf\r\n \t\r\n"
    module_path.write_bytes(module_bytes)
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"definition": {"modify": {"properties": {"Name": "НовоеИмя"}}}},
            }
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    assert not (target / "Владелец.xml").exists() and not module_path.exists()
    assert (target / "НовоеИмя/Ext/ObjectModule.bsl").read_bytes() == module_bytes
    _, renamed, _, _ = ops.read_object(editor.Snapshot(target), kind + ".НовоеИмя")
    assert editor.identity(renamed) == editor.identity(owner)


@pytest.mark.parametrize("kind", create.SPECIAL_FILES)
def test_rename_root_rejects_populated_special_artifacts(tmp_path, kind):
    target, logical = rename_owner(tmp_path, kind)
    special = create.SPECIAL_FILES[kind]
    path = (
        target
        / borrow.DIRECTORIES[kind]
        / "Владелец/Ext"
        / ("Content.xml" if kind == "ExchangePlan" else "Flowchart.xml")
    )
    root = editor.xml_read(path.read_bytes(), f"{{{special[1]}}}{special[0]}")
    etree.SubElement(root, f"{{{special[1]}}}UnknownDependency")
    path.write_bytes(etree.tostring(root))
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"definition": {"modify": {"properties": {"Name": "НовоеИмя"}}}},
            }
        ],
    }
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    # Exchange plan content has a strict reader for its Item list (populated
    # content is supported with review); an unknown element is not an Item.
    expected = (
        "Unsupported ExchangePlan Content.xml item: "
        if kind == "ExchangePlan"
        else "Cannot prove dependencies in populated special XML: "
    )
    with pytest.raises(editor.Rejected, match=expected + re.escape(path.relative_to(target).as_posix())):
        editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


def _exchange_plan_content_fixture(tmp_path, duplicate=False):
    target, logical = rename_owner(tmp_path, "Catalog")
    exchange_target = "ExchangePlan.План"
    editor.apply(
        target,
        None,
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [
                    {
                        "op": "object.create",
                        "target": exchange_target,
                        "parameters": {"definition": {"type": "ExchangePlan", "name": "План"}},
                    }
                ],
            },
        ),
    )
    namespace = create.SPECIAL_FILES["ExchangePlan"][1]
    content_path = target / "ExchangePlans/План/Ext/Content.xml"
    original = content_path.read_bytes()
    root = editor.xml_read(original, f"{{{namespace}}}ExchangePlanContent")

    def add_item(value, auto_record):
        item = etree.SubElement(root, f"{{{namespace}}}Item")
        etree.SubElement(item, f"{{{namespace}}}Metadata").text = value
        etree.SubElement(item, f"{{{namespace}}}AutoRecord").text = auto_record

    add_item(logical, "Deny")
    if duplicate:
        add_item(logical, "Allow")
    else:
        add_item("Catalog.Другое", "Allow")
    content_path.write_bytes(editor.serialize_like(root, original))
    return target, logical, content_path


def test_explicit_rename_rewrites_exchange_plan_content_and_preserves_auto_record(tmp_path, capsys):
    target, logical, content_path = _exchange_plan_content_fixture(tmp_path)
    request = {
        "schemaVersion": 1,
        "operations": [{"op": "object.rename", "target": logical, "parameters": {"name": "НовоеИмя"}}],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    import base64

    item = next(entry for entry in plan["writes"] if entry["path"] == "ExchangePlans/План/Ext/Content.xml")
    namespace = create.SPECIAL_FILES["ExchangePlan"][1]
    content = editor.xml_read(base64.b64decode(item["after"]["data"]), f"{{{namespace}}}ExchangePlanContent")
    values = [
        (node.findtext(f"{{{namespace}}}Metadata"), node.findtext(f"{{{namespace}}}AutoRecord")) for node in content
    ]
    assert values == [("Catalog.НовоеИмя", "Deny"), ("Catalog.Другое", "Allow")]
    assert not any(
        entry["path"] == "ExchangePlans/План/Ext/Content.xml" for entry in plan.get("pendingDependencies", [])
    )
    progress = capsys.readouterr()
    assert not progress.out
    assert "metadata: plan operation 1/1" in progress.err
    assert "metadata: plan snapshot preconditions" in progress.err


def test_explicit_rename_rejects_ambiguous_exchange_plan_content_before_writes(tmp_path):
    target, logical, content_path = _exchange_plan_content_fixture(tmp_path, duplicate=True)
    before = {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}
    request = {
        "schemaVersion": 1,
        "operations": [{"op": "object.rename", "target": logical, "parameters": {"name": "НовоеИмя"}}],
    }
    with pytest.raises(editor.Rejected, match="Ambiguous duplicate ExchangePlan metadata reference"):
        editor.plan_make(editor.Snapshot(target), request)
    assert before == {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}
    assert content_path.exists()


def test_edit_content_renames_exchange_plan_references_idempotently(tmp_path):
    target, _, content_path = _exchange_plan_content_fixture(tmp_path)
    namespace = create.SPECIAL_FILES["ExchangePlan"][1]
    root = editor.xml_read(content_path.read_bytes(), f"{{{namespace}}}ExchangePlanContent")
    root[0].find(f"{{{namespace}}}Metadata").text = "Catalog.Демо_ЗаказыИсточника"
    content_path.write_bytes(editor.serialize_like(root, content_path.read_bytes()))
    create_request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.create",
                "target": "Catalog.Заказы",
                "parameters": {"definition": {"type": "Catalog", "name": "Заказы"}},
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), create_request))
    request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": "ExchangePlan.План",
                "parameters": {"definition": {"contentRenames": {"Catalog.Демо_ЗаказыИсточника": "Catalog.Заказы"}}},
            }
        ],
    }

    plan = editor.plan_make(editor.Snapshot(target), request)
    content_write = next(entry for entry in plan["writes"] if entry["path"] == "ExchangePlans/План/Ext/Content.xml")
    editor.apply(target, None, plan)
    content = editor.xml_read(content_path.read_bytes(), f"{{{namespace}}}ExchangePlanContent")
    assert [
        (item.findtext(f"{{{namespace}}}Metadata"), item.findtext(f"{{{namespace}}}AutoRecord")) for item in content
    ] == [("Catalog.Заказы", "Deny"), ("Catalog.Другое", "Allow")]
    assert content_write["path"] == "ExchangePlans/План/Ext/Content.xml"
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []

    content = editor.xml_read(content_path.read_bytes(), f"{{{namespace}}}ExchangePlanContent")
    content[1].find(f"{{{namespace}}}Metadata").text = "Catalog.Демо_ЗаказыИсточника"
    content_path.write_bytes(editor.serialize_like(content, content_path.read_bytes()))
    collision_before = content_path.read_bytes()
    with pytest.raises(editor.Rejected, match="ExchangePlan content rename target already exists"):
        editor.plan_make(editor.Snapshot(target), request)
    assert content_path.read_bytes() == collision_before

    content[1].find(f"{{{namespace}}}Metadata").text = "Catalog.Другое"
    content_path.write_bytes(editor.serialize_like(content, content_path.read_bytes()))
    editor.apply(
        target,
        None,
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [
                    {
                        "op": "object.create",
                        "target": "Catalog.БезСсылки",
                        "parameters": {"definition": {"type": "Catalog", "name": "БезСсылки"}},
                    }
                ],
            },
        ),
    )
    before = content_path.read_bytes()
    missing_both = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": "ExchangePlan.План",
                "parameters": {"definition": {"contentRenames": {"Catalog.Отсутствующий": "Catalog.БезСсылки"}}},
            }
        ],
    }
    with pytest.raises(editor.Rejected, match="Neither old nor new ExchangePlan metadata reference exists"):
        editor.plan_make(editor.Snapshot(target), missing_both)
    assert content_path.read_bytes() == before

    cross_kind = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": "ExchangePlan.План",
                "parameters": {"definition": {"contentRenames": {"Catalog.Заказы": "Document.Заказы"}}},
            }
        ],
    }
    with pytest.raises(editor.Rejected, match="must keep the metadata kind"):
        editor.plan_make(editor.Snapshot(target), cross_kind)
    assert content_path.read_bytes() == before


def test_edit_content_deduplicates_exchange_plan_items_and_rejects_auto_record_conflict(tmp_path):
    target, _, content_path = _exchange_plan_content_fixture(tmp_path)
    editor.apply(
        target,
        None,
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [
                    {
                        "op": "object.create",
                        "target": "Catalog.Заказы",
                        "parameters": {"definition": {"type": "Catalog", "name": "Заказы"}},
                    }
                ],
            },
        ),
    )
    namespace = create.SPECIAL_FILES["ExchangePlan"][1]
    root = editor.xml_read(content_path.read_bytes(), f"{{{namespace}}}ExchangePlanContent")
    root[:] = []
    values = [("Catalog.Демо_ЗаказыИсточника", "Deny"), ("Catalog.Заказы", "Deny")]
    values.extend((f"Catalog.Позиция{index}", "Deny") for index in range(28))
    values.extend((f"Catalog.Позиция{index}", "Deny") for index in range(10))
    for name, auto_record in values:
        item = etree.SubElement(root, f"{{{namespace}}}Item")
        etree.SubElement(item, f"{{{namespace}}}Metadata").text = name
        etree.SubElement(item, f"{{{namespace}}}AutoRecord").text = auto_record
    content_path.write_bytes(editor.serialize_like(root, content_path.read_bytes()))

    request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": "ExchangePlan.План",
                "parameters": {
                    "definition": {
                        "contentRenames": {"Catalog.Демо_ЗаказыИсточника": "Catalog.Заказы"},
                        "contentDeduplicate": True,
                    }
                },
            }
        ],
    }
    before_plan = content_path.read_bytes()
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert content_path.read_bytes() == before_plan
    assert any(entry["path"] == "ExchangePlans/План/Ext/Content.xml" for entry in plan["writes"])
    editor.apply(target, None, plan)
    content = editor.xml_read(content_path.read_bytes(), f"{{{namespace}}}ExchangePlanContent")
    rows = [
        (item.findtext(f"{{{namespace}}}Metadata"), item.findtext(f"{{{namespace}}}AutoRecord")) for item in content
    ]
    assert len(values) == 40
    assert len(rows) == 29
    assert len({name.casefold() for name, _ in rows}) == 29
    assert rows[0] == ("Catalog.Заказы", "Deny")
    assert all(auto_record == "Deny" for _, auto_record in rows)
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []

    conflict = editor.xml_read(content_path.read_bytes(), f"{{{namespace}}}ExchangePlanContent")
    item = etree.SubElement(conflict, f"{{{namespace}}}Item")
    etree.SubElement(item, f"{{{namespace}}}Metadata").text = "Catalog.Демо_ЗаказыИсточника"
    etree.SubElement(item, f"{{{namespace}}}AutoRecord").text = "Allow"
    content_path.write_bytes(editor.serialize_like(conflict, content_path.read_bytes()))
    before_rejection = content_path.read_bytes()
    with pytest.raises(editor.Rejected, match="Conflicting duplicate ExchangePlan metadata reference"):
        editor.plan_make(editor.Snapshot(target), request)
    assert content_path.read_bytes() == before_rejection


def test_object_edit_retargets_exchange_plan_content_and_preserves_item_order(tmp_path):
    target, source, content_path = _exchange_plan_content_fixture(tmp_path)
    destination = "Catalog.Назначение"
    editor.apply(
        target,
        None,
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [
                    {
                        "op": "object.create",
                        "target": destination,
                        "parameters": {"definition": {"type": "Catalog", "name": "Назначение"}},
                    }
                ],
            },
        ),
    )
    namespace = create.SPECIAL_FILES["ExchangePlan"][1]
    original = content_path.read_bytes()
    content = editor.xml_read(original, f"{{{namespace}}}ExchangePlanContent")
    duplicate = etree.SubElement(content, f"{{{namespace}}}Item")
    etree.SubElement(duplicate, f"{{{namespace}}}Metadata").text = destination
    etree.SubElement(duplicate, f"{{{namespace}}}AutoRecord").text = "Deny"
    unrelated_duplicate = etree.SubElement(content, f"{{{namespace}}}Item")
    etree.SubElement(unrelated_duplicate, f"{{{namespace}}}Metadata").text = "Catalog.Другое"
    etree.SubElement(unrelated_duplicate, f"{{{namespace}}}AutoRecord").text = "Allow"
    content_path.write_bytes(editor.serialize_like(content, original))
    request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": "ExchangePlan.План",
                "parameters": {
                    "definition": {
                        "exchangePlanContent": {
                            "replaceMetadata": {"from": source, "to": destination},
                        }
                    },
                },
            }
        ],
    }
    before = content_path.read_bytes()
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert content_path.read_bytes() == before
    assert [item["path"] for item in plan["writes"]] == [
        "ExchangePlans/План/Ext/Content.xml",
    ]
    assert editor.apply(target, None, plan) == "applied"
    content = editor.xml_read(content_path.read_bytes(), f"{{{namespace}}}ExchangePlanContent")
    values = [
        (node.findtext(f"{{{namespace}}}Metadata"), node.findtext(f"{{{namespace}}}AutoRecord")) for node in content
    ]
    assert values == [
        (destination, "Deny"),
        ("Catalog.Другое", "Allow"),
        ("Catalog.Другое", "Allow"),
    ]


def test_object_edit_rejects_unknown_exchange_plan_content_target(tmp_path):
    target, source, content_path = _exchange_plan_content_fixture(tmp_path)
    before = {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}
    request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": "ExchangePlan.План",
                "parameters": {
                    "definition": {
                        "exchangePlanContent": {
                            "replaceMetadata": {"from": source, "to": "Catalog.Неизвестный"},
                        }
                    },
                },
            }
        ],
    }
    with pytest.raises(editor.Rejected, match="Object registration missing"):
        editor.plan_make(editor.Snapshot(target), request)
    assert before == {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}
    assert content_path.exists()


def test_edit_exchange_plan_content_removes_and_deduplicates_with_empty_repeat_plan(tmp_path):
    target, logical, content_path = _exchange_plan_content_fixture(tmp_path)
    namespace = create.SPECIAL_FILES["ExchangePlan"][1]
    original = content_path.read_bytes()
    root = editor.xml_read(original, f"{{{namespace}}}ExchangePlanContent")

    def add_item(value, auto_record):
        item = etree.SubElement(root, f"{{{namespace}}}Item")
        etree.SubElement(item, f"{{{namespace}}}Metadata").text = value
        etree.SubElement(item, f"{{{namespace}}}AutoRecord").text = auto_record

    add_item("Catalog.Другое", "Allow")
    add_item("Catalog.Удаляемый", "Deny")
    content_path.write_bytes(editor.serialize_like(root, original))
    request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "exchange-plan.edit-content",
                "target": "ExchangePlan.План",
                "parameters": {"remove": ["Catalog.Удаляемый"], "deduplicate": True},
            }
        ],
    }

    plan = editor.plan_make(editor.Snapshot(target), request)
    assert [entry["path"] for entry in plan["writes"]] == ["ExchangePlans/План/Ext/Content.xml"]
    assert editor.apply(target, None, plan) == "applied"
    repeat = editor.plan_make(editor.Snapshot(target), request)
    assert repeat["writes"] == []

    content = ops.read_exchange_plan_content(content_path.read_bytes(), str(content_path))
    values = [
        (node.findtext(f"{{{namespace}}}Metadata"), node.findtext(f"{{{namespace}}}AutoRecord")) for node in content
    ]
    assert values == [("Catalog.Владелец", "Deny"), ("Catalog.Другое", "Allow")]


def test_edit_exchange_plan_content_rejects_conflicting_auto_record_before_writes(tmp_path):
    target, _, content_path = _exchange_plan_content_fixture(tmp_path, duplicate=True)
    before = {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}
    request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "exchange-plan.edit-content",
                "target": "ExchangePlan.План",
                "parameters": {"remove": ["Catalog.Владелец"], "deduplicate": True},
            }
        ],
    }
    with pytest.raises(editor.Rejected, match="Conflicting duplicate ExchangePlan AutoRecord"):
        editor.plan_make(editor.Snapshot(target), request)
    assert before == {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}
    assert content_path.exists()


@pytest.mark.parametrize(
    "kind,dependent,expected",
    [
        (
            "CommonModule",
            {"type": "ScheduledJob", "name": "Задание", "methodName": "Владелец.Выполнить"},
            ("m:Properties/m:MethodName", "CommonModule.НовоеИмя.Выполнить"),
        ),
        (
            "CommonModule",
            {"type": "EventSubscription", "name": "Подписка", "handler": "Владелец.Выполнить"},
            ("m:Properties/m:Handler", "CommonModule.НовоеИмя.Выполнить"),
        ),
        (
            "Catalog",
            {"type": "EventSubscription", "name": "Подписка", "source": ["CatalogObject.Владелец"]},
            ("m:Properties/m:Source/v8:Type", "cfg:CatalogObject.НовоеИмя"),
        ),
        (
            "DefinedType",
            {"type": "Document", "name": "Документ", "attributes": [{"name": "Поле", "type": "DefinedType.Владелец"}]},
            ("m:ChildObjects/m:Attribute/m:Properties/m:Type/v8:TypeSet", "cfg:DefinedType.НовоеИмя"),
        ),
    ],
)
def test_rename_root_updates_explicit_metadata_dependencies(tmp_path, kind, dependent, expected):
    target, logical = rename_owner(tmp_path, kind)
    dependent_target = dependent["type"] + "." + dependent["name"]
    initial = {
        "schemaVersion": 1,
        "operations": [{"op": "object.create", "target": dependent_target, "parameters": {"definition": dependent}}],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), initial))
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"definition": {"modify": {"properties": {"Name": "НовоеИмя"}}}},
            }
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    _, owner, _, _ = ops.read_object(editor.Snapshot(target), dependent_target)
    assert owner.find(expected[0], editor.NS).text == expected[1]


def _common_module_rename_with_opaque_dependency(tmp_path, value):
    target, logical = rename_owner(tmp_path, "CommonModule")
    dependency_target = "Document.Документ"
    editor.apply(
        target,
        None,
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [
                    {
                        "op": "object.create",
                        "target": dependency_target,
                        "parameters": {"definition": {"type": "Document", "name": "Документ"}},
                    }
                ],
            },
        ),
    )
    path = target / "Documents/Документ.xml"
    data = path.read_bytes()
    root = editor.xml_read(data, f"{{{editor.MD}}}MetaDataObject")
    properties = root.find("m:Document/m:Properties", editor.NS)
    etree.SubElement(properties, f"{{{editor.MD}}}ExtensionSpecificProperty").text = value
    path.write_bytes(editor.serialize_like(root, data))
    relative = path.relative_to(target).as_posix()
    return target, logical, path, relative


def test_common_module_structural_rename_requires_hash_review_and_preserves_opaque_descriptor(tmp_path):
    target, logical, dependency, relative = _common_module_rename_with_opaque_dependency(
        tmp_path, "Opaque metadata value"
    )
    original = dependency.read_bytes()
    request_payload = {
        "schemaVersion": 1,
        "operations": [{"op": "object.rename", "target": logical, "parameters": {"name": "НовоеИмя"}}],
    }
    with pytest.raises(editor.Rejected, match="Unsupported rename dependency structure"):
        editor.plan_make(editor.Snapshot(target), request_payload)
    review = {"path": relative, "sha256": editor.digest(original), "reason": "Reviewed opaque fixture"}
    request_payload["operations"][0]["parameters"]["reviewedDependencies"] = [{**review, "sha256": "0" * 64}]
    with pytest.raises(editor.Rejected, match="Stale reviewed dependency"):
        editor.plan_make(editor.Snapshot(target), request_payload)
    request_payload["operations"][0]["parameters"]["reviewedDependencies"] = [review]
    plan = editor.plan_make(editor.Snapshot(target), request_payload)
    assert relative not in {item["path"] for item in plan["writes"]}
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    assert dependency.read_bytes() == original


def test_common_module_structural_rename_rejects_old_name_in_reviewed_opaque_descriptor(tmp_path):
    target, logical, dependency, relative = _common_module_rename_with_opaque_dependency(
        tmp_path, "CommonModule.Владелец.Метод"
    )
    original = dependency.read_bytes()
    request_payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.rename",
                "target": logical,
                "parameters": {
                    "name": "НовоеИмя",
                    "reviewedDependencies": [
                        {"path": relative, "sha256": editor.digest(original), "reason": "Reviewed opaque fixture"}
                    ],
                },
            }
        ],
    }
    with pytest.raises(editor.Rejected, match="Unresolved rename dependency"):
        editor.plan_make(editor.Snapshot(target), request_payload)
    assert dependency.read_bytes() == original


def test_rename_root_then_edit_replays_and_rolls_back_partial_move(tmp_path, monkeypatch):
    target, logical = rename_owner(tmp_path, "Catalog")
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"definition": {"modify": {"properties": {"Name": "НовоеИмя"}}}},
            },
            {
                "op": "object.edit",
                "target": "Catalog.НовоеИмя",
                "parameters": {
                    "definition": {"add": {"attributes": [{"name": "ПолеПослеПереноса", "type": "Boolean"}]}}
                },
            },
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    before_directories = {p for p in target.rglob("*") if p.is_dir()}
    replace = editor._replace_bytes
    pending = True

    def fail(path, *args):
        nonlocal pending
        replace(path, *args)
        if pending and path == target / "Catalogs/НовоеИмя.xml":
            pending = False
            raise OSError("injected partial rename")

    monkeypatch.setattr(editor, "_replace_bytes", fail)
    with pytest.raises(OSError, match="injected partial rename"):
        editor.apply(target, None, plan)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert before_directories == {p for p in target.rglob("*") if p.is_dir()}
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    _, renamed, _, _ = ops.read_object(editor.Snapshot(target), "Catalog.НовоеИмя")
    assert borrow._member(renamed, "Attribute", "ПолеПослеПереноса") is not None


@pytest.mark.parametrize(
    "collection,kind",
    [
        ("attributes", "Catalog"),
        ("dimensions", "InformationRegister"),
        ("resources", "AccumulationRegister"),
        ("enumValues", "Enum"),
        ("columns", "DocumentJournal"),
    ],
)
def test_modify_children_preserves_translations_identity_and_repeats(tmp_path, collection, kind):
    typed = collection in {"attributes", "dimensions", "resources"}
    target, logical = native_owner(tmp_path, kind, *(["Catalog.Партнеры"] if typed else []))
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"definition": {"add": {collection: [{"name": "Поле"}]}}},
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    _, owner, path, original = ops.read_object(editor.Snapshot(target), logical)
    child = borrow._member(owner, ops.ADD_KINDS[collection], "Поле")
    identity = editor.identity(child)
    synonym = present(child).find("m:Properties/m:Synonym", editor.NS)
    item = etree.SubElement(synonym, f"{{{editor.V8}}}item")
    etree.SubElement(item, f"{{{editor.V8}}}lang").text = "en"
    etree.SubElement(item, f"{{{editor.V8}}}content").text = "Keep translation"
    (target / path).write_bytes(editor.serialize_like(owner.getparent(), original))
    changes = {"synonym": "Новый заголовок"}
    if collection in {"attributes", "dimensions", "resources"}:
        changes["type"] = "String(30) + Number(12,2) + CatalogRef.Партнеры"
    payload["operations"][0]["parameters"] = {"definition": {"modify": {collection: {"Поле": changes}}}}
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    _, changed, _, _ = ops.read_object(editor.Snapshot(target), logical)
    child = borrow._member(changed, ops.ADD_KINDS[collection], "Поле")
    assert editor.identity(child) == identity
    translations = {item[0].text: item[1].text for item in present(child).find("m:Properties/m:Synonym", editor.NS)}
    assert translations == {"ru": "Новый заголовок", "en": "Keep translation"}
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


def test_modify_type_preserves_compatible_value_and_requires_explicit_incompatible_change(tmp_path):
    target, logical = native_owner(tmp_path, "Document")

    def request(definition):
        return {
            "schemaVersion": 1,
            "operations": [{"op": "object.edit", "target": logical, "parameters": {"definition": definition}}],
        }

    initial = request({"add": {"attributes": [{"name": "Поле", "type": "String(10)"}]}})
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), initial))
    for changes in ({"FillValue": "abc"}, {"Type": "String(20)"}):
        payload = request({"modify": {"attributes": {"Поле": changes}}})
        editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
        assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    _, owner, path, _ = ops.read_object(editor.Snapshot(target), logical)
    before = (target / path).read_bytes()
    for changes in ({"type": "String(2)"}, {"type": "Boolean"}, {"Type": "Number(10,2)"}):
        with pytest.raises(editor.Rejected, match="FillValue"):
            editor.plan_make(editor.Snapshot(target), request({"modify": {"attributes": {"Поле": changes}}}))
        assert (target / path).read_bytes() == before
    payload = request({"modify": {"attributes": {"Поле": {"Type": "Boolean", "FillValue": False}}}})
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload))
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize(
    "changes",
    [
        {"StandardAttributes": "broken"},
        {"DataLockFields": "broken"},
        {"Name": "Другой"},
        {"Synonym": "One", "synonym": "Two"},
        {"ObjectBelonging": "Adopted"},
    ],
)
def test_modify_rejects_structural_or_identity_corruption(tmp_path, changes):
    target, logical = native_owner(tmp_path, "Catalog")
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected):
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [
                    {
                        "op": "object.edit",
                        "target": logical,
                        "parameters": {"definition": {"modify": {"properties": changes}}},
                    }
                ],
            },
        )
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "value,value_type,valid",
    [
        ("12.34", "Number(4,2)", True),
        ("12.345", "Number(4,2)", False),
        ("-1", "Number(4,0,nonneg)", False),
        ("100", "Number(4,2)", False),
        ("12345678901234567890123456789012345678", "Number(38,0)", True),
        ("1e2", "Number(4,0)", False),
    ],
)
def test_typed_fill_numeric_qualifiers(value, value_type, valid):
    typed = create.type_node(value_type)
    fill = etree.Element(
        f"{{{editor.MD}}}FillValue", nsmap={"xs": editor.XS}, attrib={f"{{{ops.XSI}}}type": "xs:decimal"}
    )
    fill.text = value
    if valid:
        ops.check_fill_value(fill, typed)
    else:
        with pytest.raises(editor.Rejected):
            ops.check_fill_value(fill, typed)


@pytest.mark.parametrize("property_name", ["RegisteredDocuments", "References", "BaseCalculationTypes"])
def test_empty_reference_container_cannot_be_replaced_with_scalar(tmp_path, property_name):
    kind = "ChartOfCalculationTypes" if property_name == "BaseCalculationTypes" else "DocumentJournal"
    target, logical = native_owner(tmp_path, kind)
    if property_name == "References":
        initial = {
            "schemaVersion": 1,
            "operations": [
                {
                    "op": "object.edit",
                    "target": logical,
                    "parameters": {"definition": {"add": {"columns": [{"name": "Поле"}]}}},
                }
            ],
        }
        editor.apply(target, None, editor.plan_make(editor.Snapshot(target), initial))
        modifications = {"columns": {"Поле": {"References": "broken"}}}
    else:
        modifications = {"properties": {property_name: "broken"}}
    payload = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.edit", "target": logical, "parameters": {"definition": {"modify": modifications}}}
        ],
    }
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected, match="Structured"):
        editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "primitive,value_type,value",
    [
        ("dateTime", "DateTime", "2026-01-01"),
        ("dateTime", "DateTime", "2026-01-01 12:00:00"),
        ("dateTime", "DateTime", "2026-01-01T12:00:00+15:00"),
        ("decimal", "Number(10,2)", "١٢.٣"),
    ],
)
def test_typed_value_rejects_non_xml_lexical_forms(primitive, value_type, value):
    fill = etree.Element(
        f"{{{editor.MD}}}FillValue", nsmap={"xs": editor.XS}, attrib={f"{{{ops.XSI}}}type": "xs:" + primitive}
    )
    fill.text = value
    with pytest.raises(editor.Rejected):
        ops.check_fill_value(fill, create.type_node(value_type))


@pytest.mark.parametrize(
    "value_type,value,valid",
    [
        ("DateTime", "2026-01-01T12:00:00", True),
        ("DateTime", "2026-01-01T12:00:00.1234567Z", True),
        ("DateTime", "2026-02-30T00:00:00", False),
        ("Date", "2026-01-01T00:00:00", True),
        ("Date", "2026-01-01T00:00:00.0000001", False),
        ("Date", "2026-01-01T12:00:00", False),
    ],
)
def test_typed_date_value_preserves_lexeme_and_checks_qualifiers(value_type, value, valid):
    fill = etree.Element(
        f"{{{editor.MD}}}FillValue", nsmap={"xs": editor.XS}, attrib={f"{{{ops.XSI}}}type": "xs:dateTime"}
    )
    fill.text = value
    if valid:
        ops.check_fill_value(fill, create.type_node(value_type))
        assert fill.text == value
    else:
        with pytest.raises(editor.Rejected):
            ops.check_fill_value(fill, create.type_node(value_type))


def test_add_types_appends_reference_types_and_keeps_type_ids(tmp_path):
    target, logical = native_owner(tmp_path, "Document", "Document.Основание", "Document.План")
    descriptor = target / "Documents/ВладелецТеста.xml"
    initial = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {
                    "definition": {"add": {"attributes": [{"name": "Основание", "type": "DocumentRef.Основание"}]}}
                },
            }
        ],
    }
    assert editor.apply(target, None, editor.plan_make(editor.Snapshot(target), initial)) == "applied"
    # Platform dumps may reference base-configuration types by TypeId only.
    data = descriptor.read_bytes()
    owner = editor.metadata(data, "Document")
    typed = present(borrow._member(owner, "Attribute", "Основание")).find("m:Properties/m:Type", editor.NS)
    type_id = etree.SubElement(typed, f"{{{editor.V8}}}TypeId")
    type_id.text = "0291eee4-6903-4a8d-9c2b-436842baae31"
    descriptor.write_bytes(editor.serialize_like(owner.getparent(), data))

    def payload(changes):
        return {
            "schemaVersion": 1,
            "operations": [
                {
                    "op": "object.edit",
                    "target": logical,
                    "parameters": {"definition": {"modify": {"attributes": {"Основание": changes}}}},
                }
            ],
        }

    plan = editor.plan_make(editor.Snapshot(target), payload({"addTypes": ["DocumentRef.План"]}))
    assert [item["path"] for item in plan["writes"]] == ["Documents/ВладелецТеста.xml"]
    assert editor.apply(target, None, plan) == "applied"
    typed = present(
        borrow._member(editor.metadata(descriptor.read_bytes(), "Document"), "Attribute", "Основание")
    ).find("m:Properties/m:Type", editor.NS)
    assert [(child.tag.rpartition("}")[2], child.text) for child in typed] == [
        ("Type", "cfg:DocumentRef.Основание"),
        ("Type", "cfg:DocumentRef.План"),
        ("TypeId", "0291eee4-6903-4a8d-9c2b-436842baae31"),
    ]

    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    for changes in (
        {"addTypes": ["DocumentRef.План"]},
        {"addTypes": ["String(10)"]},
        {"addTypes": []},
        {"addTypes": ["DocumentRef.План"], "type": "DocumentRef.План"},
    ):
        with pytest.raises(editor.Rejected):
            editor.plan_make(editor.Snapshot(target), payload(changes))
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


def _designer_member_shape(attribute, *, multi_state=False):
    """Mirror Designer serialization of an adopted member: empty InternalInfo,
    or PropertyState Type/MultiState with the type wrapped as ExtendedProperty."""
    internal = etree.Element(f"{{{editor.MD}}}InternalInfo")
    attribute.insert(0, internal)
    if not multi_state:
        return
    state = etree.SubElement(internal, f"{{{borrow.XR}}}PropertyState")
    etree.SubElement(state, f"{{{borrow.XR}}}Property").text = "Type"
    etree.SubElement(state, f"{{{borrow.XR}}}State").text = "MultiState"
    typed = attribute.find("m:Properties/m:Type", editor.NS)
    parts = list(typed)
    typed[:] = []
    typed.set(f"{{{XSI}}}type", "xr:ExtendedProperty")
    extended = etree.SubElement(typed, f"{{{borrow.XR}}}ExtendValue", {f"{{{XSI}}}type": "v8:TypeDescription"})
    extended.extend(parts)


XSI = "http://www.w3.org/2001/XMLSchema-instance"


def test_rename_dependency_shape_accepts_designer_member_internal_info():
    def catalog_root():
        data = create.render_object(
            {
                "type": "Catalog",
                "name": "Проверка",
                "attributes": [{"name": "Поле", "type": "String(10)"}, {"name": "Фамилия", "type": "String(60)"}],
                "tabularSections": [{"name": "Строки", "attributes": [{"name": "Вид", "type": "String(5)"}]}],
            },
            str(uuid.uuid4()),
            {},
        )
        return editor.xml_read(data, f"{{{editor.MD}}}MetaDataObject")

    root = catalog_root()
    first, second = root.findall("m:Catalog/m:ChildObjects/m:Attribute", editor.NS)
    _designer_member_shape(first)
    _designer_member_shape(second, multi_state=True)
    _designer_member_shape(root.find(".//m:TabularSection/m:ChildObjects/m:Attribute", editor.NS), multi_state=True)
    ops.rename_descriptor_shape(root)

    invalid_state = catalog_root()
    attribute = invalid_state.find("m:Catalog/m:ChildObjects/m:Attribute", editor.NS)
    _designer_member_shape(attribute, multi_state=True)
    etree.SubElement(
        attribute.find("m:InternalInfo/xr:PropertyState", {**editor.NS, "xr": borrow.XR}), f"{{{borrow.XR}}}Extra"
    )
    with pytest.raises(editor.Rejected, match="Unknown member property state structure"):
        ops.rename_descriptor_shape(invalid_state)

    extended_without_state = catalog_root()
    attribute = extended_without_state.find("m:Catalog/m:ChildObjects/m:Attribute", editor.NS)
    _designer_member_shape(attribute, multi_state=True)
    attribute.find("m:InternalInfo", editor.NS)[:] = []
    with pytest.raises(editor.Rejected, match="Unsupported rename dependency attributes: type"):
        ops.rename_descriptor_shape(extended_without_state)

    invalid_position = catalog_root()
    properties = invalid_position.find("m:Catalog/m:ChildObjects/m:Attribute/m:Properties", editor.NS)
    etree.SubElement(properties, f"{{{editor.MD}}}InternalInfo")
    with pytest.raises(editor.Rejected, match="Unsupported rename dependency structure: InternalInfo"):
        ops.rename_descriptor_shape(invalid_position)


def test_remove_tabular_attribute_accepts_designer_adopted_members_in_dependencies(tmp_path):
    target, logical = rename_owner(tmp_path, "Catalog")
    editor.apply(
        target,
        None,
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [
                    {
                        "op": "object.edit",
                        "target": logical,
                        "parameters": {
                            "definition": {
                                "add": {
                                    "tabularSections": [
                                        {
                                            "name": "Строки",
                                            "attributes": [
                                                {"name": "Оставить", "type": "String(10)"},
                                                {"name": "Удаляемый", "type": "String(10)"},
                                            ],
                                        }
                                    ]
                                }
                            }
                        },
                    },
                    {
                        "op": "object.create",
                        "target": "Catalog.Зависимый",
                        "parameters": {
                            "definition": {
                                "type": "Catalog",
                                "name": "Зависимый",
                                "attributes": [
                                    {"name": "Фамилия", "type": "String(60)"},
                                    {"name": "Код2", "type": "String(9)"},
                                ],
                            }
                        },
                    },
                ],
            },
        ),
    )
    dependency_path = target / "Catalogs/Зависимый.xml"
    original = dependency_path.read_bytes()
    dependency = editor.metadata(original, "Catalog")
    first, second = dependency.findall("m:ChildObjects/m:Attribute", editor.NS)
    _designer_member_shape(first, multi_state=True)
    _designer_member_shape(second)
    dependency_path.write_bytes(editor.serialize_like(dependency.getparent(), original))

    _, owner, path, _ = ops.read_object(editor.Snapshot(target), logical)
    identities = {editor.identity(item) for item in owner.iter() if item.get("uuid")}
    kept = borrow._member(borrow._member(owner, "TabularSection", "Строки"), "Attribute", "Оставить")
    before = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": logical,
                "parameters": {"definition": {"modify": {"tabularSections": {"Строки": {"remove": ["Удаляемый"]}}}}},
            }
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert [write["path"] for write in plan["writes"]] == [path]
    assert editor.apply(target, None, plan) == "applied"
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []
    assert all((target / name).read_bytes() == data for name, data in before.items() if name != path)
    _, owner, _, _ = ops.read_object(editor.Snapshot(target), logical)
    section = borrow._member(owner, "TabularSection", "Строки")
    assert [editor.node_name(item) for item in present(section).findall("m:ChildObjects/m:Attribute", editor.NS)] == [
        "Оставить"
    ]
    assert editor.identity(borrow._member(section, "Attribute", "Оставить")) == editor.identity(kept)
    removed = {editor.identity(item) for item in owner.iter() if item.get("uuid")}
    assert removed < identities and len(identities - removed) == 1


@pytest.mark.parametrize("kind", ["ExternalDataProcessor", "ExternalReport"])
def test_external_rename_rewrites_attribute_link_by_type(tmp_path, kind):
    target = tmp_path / "target"
    target.mkdir()
    base_kind = kind.removeprefix("External")
    owner = editor.metadata(
        create.render_object(
            {"type": base_kind, "name": "Владелец", "attributes": [{"name": "Контрагент"}, {"name": "Договор"}]},
            str(uuid.uuid4()),
            {},
        ),
        base_kind,
    )
    owner.tag = f"{{{editor.MD}}}{kind}"
    attribute = next(node for node in owner.iter(f"{{{editor.MD}}}Attribute") if editor.node_name(node) == "Договор")
    link = attribute.find("m:Properties/m:LinkByType", editor.NS)
    etree.SubElement(link, f"{{{borrow.XR}}}DataPath").text = kind + ".Владелец.Attribute.Контрагент"
    etree.SubElement(link, f"{{{borrow.XR}}}LinkItem").text = "0"
    (target / "Владелец.xml").write_bytes(etree.tostring(owner.getparent()))
    request = {
        "schemaVersion": 1,
        "operations": [{"op": "object.rename", "target": kind + ".Владелец", "parameters": {"name": "НовоеИмя"}}],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert editor.apply(target, None, plan) == "applied"
    renamed = editor.metadata((target / "НовоеИмя.xml").read_bytes(), kind)
    paths = [node.text for node in renamed.iter(f"{{{borrow.XR}}}DataPath")]
    assert paths == [kind + ".НовоеИмя.Attribute.Контрагент"]
    assert [node.text for node in renamed.iter(f"{{{borrow.XR}}}LinkItem")] == ["0"]
    # Any other LinkByType content stays outside the supported rename structure.
    link = next(node for node in renamed.iter(f"{{{editor.MD}}}LinkByType") if len(node))
    etree.SubElement(link, f"{{{borrow.XR}}}Unknown")
    (target / "НовоеИмя.xml").write_bytes(etree.tostring(renamed.getparent()))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected):
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [{"op": "object.rename", "target": kind + ".НовоеИмя", "parameters": {"name": "Другое"}}],
            },
        )
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
