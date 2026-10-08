"""Catalog description conversion: exact source preservation, no platform claim."""

import tests.python.metadata_test_support  # noqa: F401, I001 — runs first: skips the module without pytest, lxml, jsonschema
import copy
from pathlib import Path
import shutil
import uuid

import lxml.etree as etree
import pytest

from scripts.python import metadata as editor, metadata_object_ops as ops
from tests.python.test_metadata_borrow import roots  # noqa: F401 — pytest fixture, requested by parameter name


SOURCE_NAME = "ДемоСправочник"
# Ordinary-form catalog exported by Designer from an 8.2 configuration, renamed for the template.
RESEARCH = Path(__file__).parents[1] / "fixtures/metadata-edit/ordinary-catalog/Catalogs"
SOURCE = "Catalog." + SOURCE_NAME
TARGET = "Catalog.цф_" + SOURCE_NAME
ATTRIBUTE = SOURCE + ".Attribute.НаименованиеПолное"
FORM = SOURCE + ".Form.ФормаЭлемента"
ROOT_UUID = "c4644903-3846-48f2-8c33-5b1aee4a3d68"


def source_node():
    return editor.metadata((RESEARCH / (SOURCE_NAME + ".xml")).read_bytes(), "Catalog")


def convert(source, **overrides):
    options = dict(target=TARGET, root_uuid=ROOT_UUID, occupied={}, include=[ATTRIBUTE], exclude=[FORM], mapping={})
    options.update(overrides)
    return ops.catalog_description(source, **options)


def content(node):
    return node.tag, dict(node.attrib), (node.text or "").strip(), [content(child) for child in node]


def test_exact_source_conversion_preserves_every_property():
    source = source_node()
    before = etree.tostring(source.getparent())
    data = convert(source)
    assert data == convert(source)
    assert before == etree.tostring(source.getparent())
    target = editor.metadata(data, "Catalog")
    assert target.getparent().get("version") == "2.17"
    assert editor.prop(target, "ObjectBelonging") == "Native"
    for original in source.find("m:Properties", editor.NS):
        copied = target.find("m:Properties/" + original.tag, editor.NS)
        expected = copy.deepcopy(original)
        if etree.QName(original).localname == "Name":
            expected.text = TARGET.split(".")[-1]
        elif etree.QName(original).localname == "InputByString":
            for field in expected:
                field.text = TARGET + field.text[len(SOURCE) :]
        elif etree.QName(original).localname == "DefaultObjectForm":
            expected.text = None
        assert content(copied) == content(expected)
    original = source.find("m:ChildObjects/m:Attribute", editor.NS)
    copied = target.find("m:ChildObjects/m:Attribute", editor.NS)
    assert content(copied[0]) == content(original[0])
    assert uuid.UUID(copied.get("uuid")).version == 5
    assert uuid.UUID(target.get("uuid")).version == 5
    assert copied.get("uuid") != original.get("uuid")
    assert target.find("m:ChildObjects/m:Form", editor.NS) is None
    assert not target.find("m:Properties/m:Type", editor.NS)


def test_explicit_root_and_attribute_mapping():
    new_target = "Catalog.цф_ДругоеИмя"
    target = editor.metadata(
        convert(
            source_node(),
            target=new_target,
            mapping={SOURCE: new_target, ATTRIBUTE: new_target + ".Attribute.НовоеПолноеНаименование"},
        ),
        "Catalog",
    )
    assert editor.node_name(target) == "цф_ДругоеИмя"
    assert editor.node_name(target.find("m:ChildObjects/m:Attribute", editor.NS)) == "НовоеПолноеНаименование"


@pytest.mark.parametrize(
    "name",
    [
        "Code",
        "description",
        "КОД",
        "Наименование",
        "Ссылка",
        "ЭтоГруппа",
        "PredefinedDataName",
        "ИмяПредопределенныхДанных",
    ],
)
def test_standard_attribute_mapping_is_rejected(name):
    with pytest.raises(editor.Rejected, match="Reserved Catalog attribute name"):
        convert(source_node(), mapping={ATTRIBUTE: TARGET + ".Attribute." + name})
    source = source_node()
    source.find("m:ChildObjects/m:Attribute/m:Properties/m:Name", editor.NS).text = name
    with pytest.raises(editor.Rejected, match="Reserved Catalog attribute name"):
        convert(source, include=[SOURCE + ".Attribute." + name])


@pytest.mark.parametrize(
    "fault",
    [
        "version",
        "property",
        "nested-property",
        "attribute-property",
        "type-qualifier",
        "unaccounted-form",
        "include-form",
        "unknown-exclusion",
        "mapping",
        "external-reference",
        "internal-info",
        "generated-type",
        "typed-reference",
        "child-registration",
    ],
)
def test_unsupported_description_fails_without_source_mutation(fault):
    source = source_node()
    options = {}
    if fault == "version":
        source.getparent().set("version", "2.21")
    elif fault == "property":
        etree.SubElement(source.find("m:Properties", editor.NS), f"{{{editor.MD}}}Unknown")
    elif fault == "nested-property":
        etree.SubElement(source.find("m:Properties/m:Comment", editor.NS), f"{{{editor.MD}}}Unknown")
    elif fault == "attribute-property":
        etree.SubElement(source.find("m:ChildObjects/m:Attribute/m:Properties", editor.NS), f"{{{editor.MD}}}Unknown")
    elif fault == "type-qualifier":
        source.find(
            "m:ChildObjects/m:Attribute/m:Properties/m:Type/v8:StringQualifiers/v8:AllowedLength", editor.NS
        ).text = "Unknown"
    elif fault == "unaccounted-form":
        options["exclude"] = []
    elif fault == "include-form":
        options.update(include=[ATTRIBUTE, FORM], exclude=[])
    elif fault == "unknown-exclusion":
        options["exclude"] = [FORM, SOURCE + ".Template.Missing"]
    elif fault == "mapping":
        options["mapping"] = {ATTRIBUTE: "Catalog.Other.Attribute.Name"}
    elif fault == "internal-info":
        etree.SubElement(source[0], f"{{{editor.MD}}}Unknown")
    elif fault == "generated-type":
        source[0][0].set("category", "Unknown")
    elif fault == "typed-reference":
        source.find("m:ChildObjects/m:Attribute/m:Properties/m:FillValue", editor.NS).set(
            "{http://www.w3.org/2001/XMLSchema-instance}type", "cfg:CatalogRef.Other"
        )
    elif fault == "child-registration":
        source.find("m:ChildObjects/m:Form", editor.NS).set("unknown", "ignored")
    else:
        source.find("m:Properties/m:InputByString", editor.NS)[0].text = "Catalog.Other.StandardAttribute.Code"
    before = etree.tostring(source.getparent())
    with pytest.raises(editor.Rejected):
        convert(source, **options)
    assert etree.tostring(source.getparent()) == before


@pytest.fixture
def copy_roots(roots):  # noqa: F811 — pytest injects the imported fixture by this parameter name
    source, target = roots
    research = RESEARCH
    (source / "Catalogs").mkdir()
    shutil.copyfile(research / (SOURCE_NAME + ".xml"), source / "Catalogs" / (SOURCE_NAME + ".xml"))
    shutil.copytree(research / SOURCE_NAME, source / "Catalogs" / SOURCE_NAME)
    path = source / "Configuration.xml"
    config = editor.metadata(path.read_bytes(), "Configuration")
    etree.SubElement(config.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}Catalog").text = SOURCE_NAME
    path.write_bytes(editor.serialize_like(config.getparent(), path.read_bytes()))
    return source, target


def copy_request(source):
    return {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.copy-description",
                "target": "Catalog.MF_" + SOURCE_NAME,
                "parameters": {
                    "sourceRoot": str(source),
                    "source": SOURCE,
                    "prefix": "MF_",
                    "include": [ATTRIBUTE],
                    "exclude": [FORM],
                },
            }
        ],
    }


def test_description_plan_apply_repeat_preserves_modules(copy_roots):
    source, target = copy_roots
    before = {str(p.relative_to(source)): p.read_bytes() for p in source.rglob("*") if p.is_file()}
    request = copy_request(source)
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert not (target / "Catalogs").exists()
    assert plan["checks"]["platform"] == plan["checks"]["runtime"] == "not-run"
    assert plan["request"]["operations"][0]["parameters"]["exclude"] == [FORM]
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    module = target / "Catalogs" / ("MF_" + SOURCE_NAME) / "Ext/ObjectModule.bsl"
    assert module.read_bytes() == b""
    module.write_bytes(b"// existing user code\r\n")
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []
    assert module.read_bytes() == b"// existing user code\r\n"
    assert before == {str(p.relative_to(source)): p.read_bytes() for p in source.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "fault",
    [
        "prefix",
        "target-name",
        "target-version",
        "unregistered-source",
        "unknown-file",
        "unaccounted-module",
        "included-module",
        "orphan-target",
    ],
)
def test_description_plan_rejects_incomplete_context(copy_roots, fault):
    source, target = copy_roots
    request = copy_request(source)
    parameters = request["operations"][0]["parameters"]
    if fault == "prefix":
        parameters["prefix"] = "Other_"
    elif fault == "target-name":
        request["operations"][0]["target"] = "Catalog.ShortName"
    elif fault in {"target-version", "unregistered-source"}:
        path = (target if fault == "target-version" else source) / "Configuration.xml"
        config = editor.metadata(path.read_bytes(), "Configuration")
        if fault == "target-version":
            config.getparent().set("version", "2.20")
        else:
            children = config.find("m:ChildObjects", editor.NS)
            children.remove(children.find("m:Catalog", editor.NS))
        path.write_bytes(editor.serialize_like(config.getparent(), path.read_bytes()))
    elif fault == "unknown-file":
        (source / "Catalogs" / SOURCE_NAME / "unknown.txt").write_text("unexpected")
    elif fault in {"unaccounted-module", "included-module"}:
        folder = source / "Catalogs" / SOURCE_NAME / "Ext"
        folder.mkdir()
        (folder / "ObjectModule.bsl").write_bytes(b"// do not infer conversion")
        if fault == "included-module":
            parameters["include"].append(SOURCE + ".Module.ObjectModule")
    else:
        folder = target / "Catalogs" / ("MF_" + SOURCE_NAME)
        folder.mkdir(parents=True)
        (folder / "unrelated.txt").write_bytes(b"preserve")
    before = {str(p.relative_to(target)): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), request)
    assert before == {str(p.relative_to(target)): p.read_bytes() for p in target.rglob("*") if p.is_file()}


def test_changed_excluded_source_invalidates_plan(copy_roots):
    source, target = copy_roots
    plan = editor.plan_make(editor.Snapshot(target), copy_request(source))
    path = source / "Catalogs" / SOURCE_NAME / "Forms/ФормаЭлемента.xml"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(editor.Rejected):
        editor.apply(target, None, plan)
    assert not (target / "Catalogs").exists()


def test_explicit_module_exclusion_and_existing_description_conflict(copy_roots):
    source, target = copy_roots
    folder = source / "Catalogs" / SOURCE_NAME / "Ext"
    folder.mkdir()
    (folder / "ObjectModule.bsl").write_bytes(b"// original module excluded")
    request = copy_request(source)
    request["operations"][0]["parameters"]["exclude"].append(SOURCE + ".Module.ObjectModule")
    plan = editor.plan_make(editor.Snapshot(target), request)
    editor.apply(target, None, plan)
    path = target / "Catalogs" / ("MF_" + SOURCE_NAME + ".xml")
    node = editor.metadata(path.read_bytes(), "Catalog")
    node.find("m:Properties/m:Comment", editor.NS).text = "User modification"
    path.write_bytes(editor.serialize_like(node.getparent(), path.read_bytes()))
    before = path.read_bytes()
    with pytest.raises(editor.Rejected, match="refusing replacement"):
        editor.plan_make(editor.Snapshot(target), request)
    assert path.read_bytes() == before


def test_exact_research_source_plan(copy_roots):
    source, target = copy_roots
    snapshot = editor.Snapshot(target)
    plan = editor.plan_make(snapshot, form_request(source))
    assert len(plan["writes"]) == 6  # owner/config/module and managed form descriptor/body/module
    assert not (target / "Catalogs").exists()
    snapshot.unchanged()


def form_request(source):
    request = copy_request(source)
    owner = request["operations"][0]["target"]
    request["operations"].append(
        {
            "op": "form.create",
            "target": owner,
            "parameters": {
                "name": "ФормаЭлемента",
                "synonym": "Форма элемента",
                "purpose": "Object",
                "setDefault": True,
            },
        }
    )
    after = None
    for name, attribute, title in [
        ("Код", "Code", "Код"),
        ("Наименование", "Description", "Наименование"),
        ("НаименованиеПолное", "НаименованиеПолное", "Наименование полное"),
    ]:
        parameters = {"name": name, "attribute": "Объект." + attribute, "title": title, "parent": "$root"}
        if after:
            parameters["after"] = after
        request["operations"].append(
            {"op": "form.add-input", "target": owner + ".Form.ФормаЭлемента", "parameters": parameters}
        )
        after = name
    return request


def test_full_catalog_form_file_sequence(copy_roots):
    source, target = copy_roots
    request = form_request(source)
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert len(plan["writes"]) == 6
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    owner = request["operations"][0]["target"]
    descriptor = target / "Catalogs" / (owner.split(".")[1] + ".xml")
    assert (
        editor.prop(editor.metadata(descriptor.read_bytes(), "Catalog"), "DefaultObjectForm")
        == owner + ".Form.ФормаЭлемента"
    )
    form_path = descriptor.with_suffix("") / "Forms/ФормаЭлемента/Ext/Form.xml"
    form = editor.xml_read(form_path.read_bytes(), f"{{{editor.FORM}}}Form")
    assert [node.findtext("f:DataPath", namespaces=editor.NS) for node in form.find("f:ChildItems", editor.NS)] == [
        "Объект.Code",
        "Объект.Description",
        "Объект.НаименованиеПолное",
    ]
    assert form.findtext("f:AutoCommandBar/f:Autofill", namespaces=editor.NS) == "true"
    assert form.find("f:Events", editor.NS) is None
    module = form_path.with_suffix("") / "Module.bsl"
    assert module.read_bytes() == b""
    module.write_bytes(b"// preserved user module\r\n")
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "fault", ["purpose", "disabled-code", "disabled-description", "wrong-code-type", "orphan-form"]
)
def test_form_creation_rejects_invalid_context(copy_roots, fault):
    source, target = copy_roots
    request = form_request(source)
    if fault == "purpose":
        request["operations"][1]["parameters"]["purpose"] = "List"
    elif fault == "orphan-form":
        editor.apply(target, None, editor.plan_make(editor.Snapshot(target), copy_request(source)))
        path = target / "Catalogs" / ("MF_" + SOURCE_NAME) / "Forms/ФормаЭлемента/Ext"
        path.mkdir(parents=True)
        (path / "Form.xml").write_bytes(b"preserve")
    else:
        path = source / "Catalogs" / (SOURCE_NAME + ".xml")
        source_object = editor.metadata(path.read_bytes(), "Catalog")
        name = {
            "disabled-code": "CodeLength",
            "disabled-description": "DescriptionLength",
            "wrong-code-type": "CodeType",
        }[fault]
        source_object.find("m:Properties/m:" + name, editor.NS).text = "Unknown" if fault == "wrong-code-type" else "0"
        path.write_bytes(editor.serialize_like(source_object.getparent(), path.read_bytes()))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), request)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
