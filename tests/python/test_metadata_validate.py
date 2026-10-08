"""The extracted validator preserves structural diagnostics without I/O."""

import tests.python.metadata_test_support  # noqa: F401, I001 — runs first: skips the module without pytest, lxml, jsonschema
import builtins
import copy
import json
import shutil
import subprocess
import sys

import pytest
import lxml.etree as etree
from jsonschema import Draft202012Validator

from scripts.python import metadata as editor, metadata_create as create, metadata_validate
from scripts.python import metadata_ops, metadata_borrow as borrow, metadata_object_ops as object_ops
from tests.python.test_metadata_info import LEGACY_KINDS, ROOT, sample, FORM_FIXTURES


def diagnostics(lines):
    return [line for line in lines if line.startswith(("[OK]", "[WARN]", "[ERROR]"))]


@pytest.mark.parametrize(
    "hierarchy_type", ["HierarchyFoldersAndItems", "HierarchyOfItems", "HierarchyItemsOnly", "Invalid"]
)
def test_disabled_hierarchy_retains_type_without_false_warning(tmp_path, hierarchy_type):
    _, _, path = sample(tmp_path, "Catalog")
    root = etree.fromstring(path.read_bytes())
    props = root[0].find("m:Properties", editor.NS)
    props.find("m:Hierarchical", editor.NS).text = "false"
    props.find("m:HierarchyType", editor.NS).text = hierarchy_type
    before = etree.tostring(root)
    report = metadata_validate.object_report(root)
    assert report["warnings"] == 0
    assert (report["errors"] > 0) == (hierarchy_type in ("HierarchyItemsOnly", "Invalid"))
    assert etree.tostring(root) == before


def compare(path, case, *, detailed=True, max_errors=30):
    expected = json.loads(
        (ROOT / "tests/fixtures/metadata-validate/object-diagnostics.json").read_text(encoding="utf-8")
    )[case]
    root = etree.fromstring(path.read_bytes())
    before = etree.tostring(root)
    report = metadata_validate.object_report(
        root, detailed=detailed, max_errors=max_errors, registrar_references=set(), common_modules=set()
    )
    assert diagnostics(report["lines"]) == expected["lines"]
    assert report["errors"] == expected["errors"]
    assert report["errors"] == sum(line.startswith("[ERROR]") for line in report["lines"])
    assert report["warnings"] == sum(line.startswith("[WARN]") for line in report["lines"])
    assert etree.tostring(root) == before
    return report


@pytest.mark.parametrize("kind", LEGACY_KINDS)
def test_structural_diagnostics_match_explicit_report(tmp_path, kind):
    _, _, path = sample(tmp_path, kind)
    compare(path, "kind/" + kind)


def test_subsystem_diagnostics_accept_created_subsystem(tmp_path):
    _, _, path = sample(tmp_path, "Subsystem")
    report = metadata_validate.object_report(
        etree.fromstring(path.read_bytes()),
        detailed=True,
        max_errors=30,
        registrar_references=set(),
        common_modules=set(),
    )
    assert (report["errors"], report["warnings"]) == (0, 0)


def test_common_command_diagnostics_accept_created_command(tmp_path):
    _, _, path = sample(tmp_path, "CommonCommand")
    report = metadata_validate.object_report(
        etree.fromstring(path.read_bytes()),
        detailed=True,
        max_errors=30,
        registrar_references=set(),
        common_modules=set(),
    )
    assert diagnostics(report["lines"]) == [
        "[OK]    1. Root structure: MetaDataObject/CommonCommand, version 2.17",
        "[OK]    2. InternalInfo: absent (correct for CommonCommand)",
        '[OK]    3. Properties: Name="Проверка", Synonym present',
        "[OK]    4. Property values: 1 enum properties checked",
        "[OK]    6. ChildObjects: absent (correct for CommonCommand)",
        "[OK]    10. Cross-property consistency",
    ]
    assert (report["errors"], report["warnings"]) == (0, 0)


@pytest.mark.parametrize(
    "fault",
    [
        "uuid",
        "enum",
        "attribute-type",
        "duplicate",
        "child-kind",
        "generated-type",
        "standard-attribute",
        "ts-uuid",
        "reserved",
    ],
)
def test_invalid_diagnostics_match_explicit_report(tmp_path, fault):
    _, _, path = sample(tmp_path)
    root = etree.fromstring(path.read_bytes())
    node = root[0]
    props = node.find("m:Properties", editor.NS)
    children = node.find("m:ChildObjects", editor.NS)
    attr = children.find("m:Attribute", editor.NS)
    if fault == "uuid":
        node.set("uuid", "wrong")
    elif fault == "enum":
        props.find("m:CodeType", editor.NS).text = "Wrong"
    elif fault == "attribute-type":
        p = attr.find("m:Properties", editor.NS)
        p.remove(p.find("m:Type", editor.NS))
    elif fault == "duplicate":
        children.append(copy.deepcopy(attr))
    elif fault == "child-kind":
        etree.SubElement(children, f"{{{editor.MD}}}Dimension")
    elif fault == "generated-type":
        node.find(".//{http://v8.1c.ru/8.3/xcf/readable}TypeId").text = "wrong"
    elif fault == "standard-attribute":
        props.find(".//{http://v8.1c.ru/8.3/xcf/readable}StandardAttribute").attrib.pop("name")
    elif fault == "ts-uuid":
        children.find("m:TabularSection", editor.NS).attrib.pop("uuid")
    elif fault == "reserved":
        attr.find("m:Properties/m:Name", editor.NS).text = "Ref"
    path.write_bytes(etree.tostring(root))
    report = compare(path, "fault/" + fault)
    assert report["errors"] + report["warnings"] > 0


@pytest.mark.parametrize(
    "tag,value",
    [
        ("Type", "xs:string"),
        ("TypeSet", "cfg:DefinedType.Адрес"),
        ("TypeId", "1376fb02-01a4-4809-8d8d-0e5a9a6ad441"),
    ],
)
def test_attribute_type_representations_are_validated(tmp_path, tag, value):
    _, _, path = sample(tmp_path)
    root = etree.fromstring(path.read_bytes())
    type_node = root.find("m:Catalog/m:ChildObjects/m:Attribute/m:Properties/m:Type", editor.NS)
    type_node.clear()
    etree.SubElement(type_node, f"{{{editor.V8}}}{tag}").text = value

    report = metadata_validate.object_report(root)

    assert report["errors"] == 0


@pytest.mark.parametrize("value", ["wrong", ""])
def test_attribute_type_id_rejects_invalid_uuid(tmp_path, value):
    _, _, path = sample(tmp_path)
    root = etree.fromstring(path.read_bytes())
    type_node = root.find("m:Catalog/m:ChildObjects/m:Attribute/m:Properties/m:Type", editor.NS)
    type_node.clear()
    etree.SubElement(type_node, f"{{{editor.V8}}}TypeId").text = value

    report = metadata_validate.object_report(root)

    assert report["errors"] == 1
    assert any("TypeId has invalid UUID" in line for line in report["lines"])


def test_detailed_and_max_errors(tmp_path):
    _, _, path = sample(tmp_path)
    ordinary = compare(path, "ordinary", detailed=False)
    assert not any(line.startswith("[OK]") for line in ordinary["lines"])
    root = etree.fromstring(path.read_bytes())
    root[0].set("uuid", "wrong")
    root[0].remove(root[0].find("m:InternalInfo", editor.NS))
    path.write_bytes(etree.tostring(root))
    report = compare(path, "max-errors", max_errors=1)
    assert report["stopped"] and report["errors"] == 1


@pytest.mark.parametrize(
    "xml",
    [
        "<wrong/>",
        f'<MetaDataObject xmlns="{editor.MD}"/>',
        f'<MetaDataObject xmlns="{editor.MD}"><Catalog/></MetaDataObject>',
    ],
)
def test_incomplete_xml_is_reported_without_crashing(xml):
    result = metadata_validate.object_report(etree.fromstring(xml.encode()))
    assert result["errors"] > 0


def test_pure_report_no_io_no_mutation(tmp_path, monkeypatch, capsys):
    _, _, path = sample(tmp_path)
    root = etree.fromstring(path.read_bytes())
    before = etree.tostring(root)

    def forbidden(*args, **kwargs):
        raise AssertionError("Pure validator must not perform I/O")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "call", forbidden)
    first = metadata_validate.object_report(root, detailed=True)
    second = metadata_validate.object_report(root, detailed=True)
    assert first == second
    assert etree.tostring(root) == before
    assert capsys.readouterr().out == ""


def test_registrar_context_is_explicit(tmp_path):
    _, logical, path = sample(tmp_path, "AccumulationRegister")
    root = etree.fromstring(path.read_bytes())
    unavailable = metadata_validate.object_report(root)
    missing = metadata_validate.object_report(root, registrar_references=set())
    found = metadata_validate.object_report(root, registrar_references={logical})
    assert any("not-run" in line for line in unavailable["lines"])
    assert any("no registrar document found" in line for line in missing["lines"])
    assert not any("registrar" in line for line in diagnostics(found["lines"]))


def test_method_reference_does_not_claim_bsl_verified(tmp_path):
    _, _, path = sample(tmp_path, "ScheduledJob")
    root = etree.fromstring(path.read_bytes())
    root.find("m:ScheduledJob/m:Properties/m:MethodName", editor.NS).text = "CommonModule.Модуль.Метод"
    unavailable = metadata_validate.object_report(root)
    missing = metadata_validate.object_report(root, common_modules=set())
    present = metadata_validate.object_report(root, common_modules={"Модуль"})
    assert any("not-run" in line for line in unavailable["lines"])
    assert any("CommonModule 'Модуль' not found" in line for line in missing["lines"])
    assert any("not-run" in line for line in present["lines"])
    assert present["warnings"] > 0
    assert not any(line.startswith("[OK]") and "13." in line for line in present["lines"])


def add_object(target, kind, name, **properties):
    config_path = target / "Configuration.xml"
    config = etree.fromstring(config_path.read_bytes())
    etree.SubElement(config.find("m:Configuration/m:ChildObjects", editor.NS), f"{{{editor.MD}}}{kind}").text = name
    config_path.write_bytes(etree.tostring(config))
    path = target / borrow.DIRECTORIES[kind] / (name + ".xml")
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(create.render_object({"type": kind, "name": name, **properties}, config[0].get("uuid"), {}))
    return path


def test_verify_cli_batch_retains_diagnostics(tmp_path, monkeypatch, capsys):
    target, logical, path = sample(tmp_path, "Enum")
    broken = add_object(target, "Catalog", "Сломан")
    tree = etree.fromstring(broken.read_bytes())
    tree[0].set("uuid", "wrong")
    broken.write_bytes(etree.tostring(tree))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}

    def forbidden(*args, **kwargs):
        raise AssertionError("verify must not use helpers or publication")

    monkeypatch.setattr(editor.Snapshot, "stage", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    assert editor.main(["verify", "--root", str(target), "--object", logical]) == 0
    good = json.loads(capsys.readouterr().out)
    Draft202012Validator(metadata_ops.RESULT_SCHEMA).validate(good)
    assert good["status"] == "verified" and good["changes"] is None
    assert good["checks"]["platform"] == good["checks"]["runtime"] == "not-run"
    assert (
        editor.main(
            [
                "verify",
                "--root",
                str(target),
                "--object",
                "Catalog.Сломан",
                "--object",
                logical,
                "--detailed",
                "--max-errors",
                "1",
            ]
        )
        == 4
    )
    captured = capsys.readouterr()
    assert not captured.err and len(captured.out.splitlines()) == 1
    result = json.loads(captured.out)
    Draft202012Validator(metadata_ops.RESULT_SCHEMA).validate(result)
    assert result["status"] == "rejected" and result["changes"] is None
    assert result["error"]["code"] == 4
    first, second = result["checks"]["local"]["objects"]
    assert first["report"]["errors"] == 1 and first["report"]["stopped"]
    assert second["code"] == 0 and any(line.startswith("[OK]") for line in second["report"]["lines"])
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


def test_verify_warning_is_not_success(tmp_path):
    target, logical, path = sample(tmp_path, "Enum")
    tree = etree.fromstring(path.read_bytes())
    tree.attrib.pop("version")
    path.write_bytes(etree.tostring(tree))
    result = editor.verify_objects(editor.Snapshot(target), [logical])
    assert result["code"] == 4
    report = result["objects"][0]["report"]
    assert report["warnings"] > 0 and report["errors"] == 0


@pytest.mark.parametrize("exact", [False, True])
def test_verify_registrar_uses_register_records(tmp_path, exact):
    target, logical, _ = sample(tmp_path, "AccumulationRegister")
    add_object(target, "Document", "Регистратор", synonym=logical, registerRecords=[logical] if exact else [])
    report = editor.verify_objects(editor.Snapshot(target), [logical])["objects"][0]["report"]
    assert any("no registrar document found" in line for line in report["lines"]) == (not exact)


@pytest.mark.parametrize("belonging,expected_error", [("Adopted", False), ("Native", True)])
def test_verify_adopted_document_without_register_records_inherits_base_list(tmp_path, belonging, expected_error):
    target, logical, _ = sample(tmp_path, "AccumulationRegister")
    path = add_object(target, "Document", "НаследующийРегистратор", registerRecords=[logical])
    root = etree.fromstring(path.read_bytes())
    props = root.find("m:Document/m:Properties", editor.NS)
    props.find("m:RegisterRecords", editor.NS).getparent().remove(props.find("m:RegisterRecords", editor.NS))
    etree.SubElement(props, f"{{{editor.MD}}}ObjectBelonging").text = belonging
    if belonging == "Adopted":
        etree.SubElement(
            props, f"{{{editor.MD}}}ExtendedConfigurationObject"
        ).text = "01234567-89ab-cdef-0123-456789abcdef"
    path.write_bytes(etree.tostring(root))

    # The strict mutator reader still rejects a missing list. Only the read-only
    # cross-object verification interprets an adopted omission as inherited.
    with pytest.raises(editor.Rejected):
        object_ops.read_reference_list(root[0], "RegisterRecords")

    result = editor.verify_objects(editor.Snapshot(target), [logical])
    item = result["objects"][0]
    assert (item.get("error") is not None) == expected_error
    if not expected_error:
        assert item["report"]["errors"] == 0
        assert any("no registrar document found" in line for line in item["report"]["lines"])


@pytest.mark.parametrize("belonging", ["Adopted", "Native"])
def test_adopted_document_journal_inherits_registered_documents(tmp_path, belonging):
    _, _, path = sample(tmp_path, "DocumentJournal")
    root = etree.fromstring(path.read_bytes())
    props = root[0].find("m:Properties", editor.NS)
    registered = props.find("m:RegisteredDocuments", editor.NS)
    if registered is not None:
        props.remove(registered)
    etree.SubElement(props, f"{{{editor.MD}}}ObjectBelonging").text = belonging
    report = metadata_validate.object_report(root)
    warned = any("no RegisteredDocuments specified" in line for line in report["lines"])
    assert warned == (belonging == "Native")


def test_child_type_accepts_platform_typeid_and_rejects_malformed_ids(tmp_path):
    _, _, path = sample(tmp_path, "Catalog")
    root = etree.fromstring(path.read_bytes())
    type_el = root.find("m:Catalog/m:ChildObjects/m:Attribute/m:Properties/m:Type", editor.NS)
    type_el[:] = []
    type_id = etree.SubElement(type_el, f"{{{editor.V8}}}TypeId")
    type_id.text = "01234567-89ab-cdef-0123-456789abcdef"
    assert metadata_validate.object_report(root)["errors"] == 0

    type_id.text = "not-a-uuid"
    malformed = metadata_validate.object_report(root)
    assert malformed["errors"] == 1
    assert any("malformed v8:TypeId" in line for line in malformed["lines"])


@pytest.mark.parametrize("fault", ["missing-state", "missing-check-value", "wrong-check-type", "empty-extension"])
def test_child_type_accepts_only_complete_extended_property_shape(tmp_path, fault):
    _, _, path = sample(tmp_path, "Catalog")
    root = etree.fromstring(path.read_bytes())
    type_el = root.find("m:Catalog/m:ChildObjects/m:Attribute/m:Properties/m:Type", editor.NS)
    member = type_el.getparent().getparent()
    internal = etree.SubElement(member, f"{{{editor.MD}}}InternalInfo")
    state = etree.SubElement(internal, f"{{{borrow.XR}}}PropertyState")
    etree.SubElement(state, f"{{{borrow.XR}}}Property").text = "Type"
    etree.SubElement(state, f"{{{borrow.XR}}}State").text = "MultiState"

    type_el.attrib[f"{{{object_ops.XSI}}}type"] = "xr:ExtendedProperty"
    type_el[:] = []
    check_value = etree.SubElement(type_el, f"{{{borrow.XR}}}CheckValue")
    check_value.attrib[f"{{{object_ops.XSI}}}type"] = "v8:TypeDescription"
    extend_value = etree.SubElement(type_el, f"{{{borrow.XR}}}ExtendValue")
    extend_value.attrib[f"{{{object_ops.XSI}}}type"] = "v8:TypeDescription"
    etree.SubElement(extend_value, f"{{{editor.V8}}}Type").text = "xs:string"

    if fault == "missing-state":
        internal.remove(state)
    elif fault == "missing-check-value":
        type_el.remove(check_value)
    elif fault == "wrong-check-type":
        check_value.attrib[f"{{{object_ops.XSI}}}type"] = "xs:string"
    elif fault == "empty-extension":
        extend_value[:] = []

    report = metadata_validate.object_report(root)
    assert report["errors"] == 1
    assert any("malformed xr:ExtendedProperty Type" in line for line in report["lines"])


def test_verify_adopted_register_uses_inherited_document_registrations(tmp_path, monkeypatch):
    base, logical, register_path = sample(tmp_path, "AccumulationRegister")
    add_object(base, "AccumulationRegister", "Другой")
    add_object(base, "Document", "Локальный", registerRecords=["AccumulationRegister.Другой"])
    add_object(base, "Document", "Унаследованный", registerRecords=[logical])
    local_base = editor.metadata((base / "Documents/Локальный.xml").read_bytes(), "Document")
    local_base.find("m:Properties/m:RegisterRecords/xr:Item", {**editor.NS, "xr": borrow.XR}).text = logical
    (base / "Documents/Локальный.xml").write_bytes(
        editor.serialize_like(local_base.getparent(), (base / "Documents/Локальный.xml").read_bytes())
    )
    register_tree = etree.fromstring(register_path.read_bytes())
    standard_attributes = register_tree.find("m:AccumulationRegister/m:Properties/m:StandardAttributes", editor.NS)
    record_type = copy.deepcopy(standard_attributes[0])
    record_type.set("name", "RecordType")
    standard_attributes.append(record_type)
    register_path.write_bytes(etree.tostring(register_tree))
    target = tmp_path / "extension"
    shutil.copytree(base, target)

    target_config = etree.fromstring((target / "Configuration.xml").read_bytes())
    properties = target_config.find("m:Configuration/m:Properties", editor.NS)
    etree.SubElement(properties, f"{{{editor.MD}}}ConfigurationExtensionPurpose").text = "Patch"
    etree.SubElement(properties, f"{{{editor.MD}}}KeepMappingToExtendedConfigurationObjectsByIDs").text = "true"
    registrations = target_config.find("m:Configuration/m:ChildObjects", editor.NS)
    for entry in list(registrations):
        if entry.tag == f"{{{editor.MD}}}Document" and entry.text == "Унаследованный":
            registrations.remove(entry)
    (target / "Configuration.xml").write_bytes(etree.tostring(target_config))

    base_register = editor.metadata(register_path.read_bytes(), "AccumulationRegister")
    current_register_path = target / "AccumulationRegisters/Проверка.xml"
    current_register = editor.metadata(current_register_path.read_bytes(), "AccumulationRegister")
    register_props = current_register.find("m:Properties", editor.NS)
    etree.SubElement(register_props, f"{{{editor.MD}}}ObjectBelonging").text = "Adopted"
    etree.SubElement(register_props, f"{{{editor.MD}}}ExtendedConfigurationObject").text = editor.identity(
        base_register
    )
    current_register_path.write_bytes(
        editor.serialize_like(current_register.getparent(), current_register_path.read_bytes())
    )

    base_document = editor.metadata((base / "Documents/Локальный.xml").read_bytes(), "Document")
    current_document_path = target / "Documents/Локальный.xml"
    current_document = editor.metadata(current_document_path.read_bytes(), "Document")
    document_props = current_document.find("m:Properties", editor.NS)
    etree.SubElement(document_props, f"{{{editor.MD}}}ObjectBelonging").text = "Adopted"
    etree.SubElement(document_props, f"{{{editor.MD}}}ExtendedConfigurationObject").text = editor.identity(
        base_document
    )
    document_props.remove(document_props.find("m:RegisterRecords", editor.NS))
    own_records = etree.SubElement(
        document_props,
        f"{{{editor.MD}}}RegisterRecords",
        nsmap={"xr": borrow.XR, "xsi": "http://www.w3.org/2001/XMLSchema-instance"},
    )
    etree.SubElement(
        own_records, f"{{{borrow.XR}}}Item", {"{http://www.w3.org/2001/XMLSchema-instance}type": "xr:MDObjectRef"}
    ).text = "AccumulationRegister.Другой"
    current_document_path.write_bytes(
        editor.serialize_like(current_document.getparent(), current_document_path.read_bytes())
    )
    (target / "Documents/Унаследованный.xml").unlink()

    captured = {}
    report = metadata_validate.object_report

    def capture(root, **kwargs):
        captured["registrar_references"] = kwargs.get("registrar_references")
        return report(root, **kwargs)

    monkeypatch.setattr(metadata_validate, "object_report", capture)
    result = editor.verify_objects(editor.Snapshot(target), [logical], base_root=base)
    report = result["objects"][0]["report"]
    assert result["code"] == 0
    assert captured["registrar_references"] == {logical, "AccumulationRegister.Другой"}
    assert not any("no registrar document found" in line for line in report["lines"])


@pytest.mark.parametrize(
    "fault", ["type", "unknown-child", "unknown-attribute", "container-attribute", "mixed", "duplicate"]
)
def test_verify_rejects_malformed_registrar_reference(tmp_path, fault):
    target, logical, _ = sample(tmp_path, "AccumulationRegister")
    path = add_object(target, "Document", "Регистратор", registerRecords=[logical])
    root = etree.fromstring(path.read_bytes())
    container = root.find("m:Document/m:Properties/m:RegisterRecords", editor.NS)
    item = container[0]
    if fault == "type":
        item.set("{http://www.w3.org/2001/XMLSchema-instance}type", "xs:string")
    elif fault == "unknown-child":
        etree.SubElement(container, f"{{{editor.MD}}}Unknown")
    elif fault == "unknown-attribute":
        item.set("unknown", "value")
    elif fault == "container-attribute":
        container.set("unknown", "value")
    elif fault == "mixed":
        item.tail = "unknown"
    else:
        container.append(copy.deepcopy(item))
    path.write_bytes(etree.tostring(root))
    result = editor.verify_objects(editor.Snapshot(target), [logical])
    assert result["code"] != 0
    assert "error" in result["objects"][0]


@pytest.mark.parametrize("kind", ["ScheduledJob", "EventSubscription"])
@pytest.mark.parametrize("reference", ["CommonModule.Модуль.Метод", "Модуль.Метод"])
def test_verify_common_module_no_bsl_read(tmp_path, monkeypatch, kind, reference):
    target, logical, path = sample(tmp_path, kind)
    tree = etree.fromstring(path.read_bytes())
    prop = "Handler" if kind == "EventSubscription" else "MethodName"
    tree.find(f"m:{kind}/m:Properties/m:{prop}", editor.NS).text = reference
    path.write_bytes(etree.tostring(tree))
    add_object(target, "CommonModule", "Модуль")
    read = editor.Snapshot.read

    def checked_read(self, alias, path, **kwargs):
        assert not path.endswith(".bsl")
        return read(self, alias, path, **kwargs)

    monkeypatch.setattr(editor.Snapshot, "read", checked_read)
    result = editor.verify_objects(editor.Snapshot(target), [logical])
    assert result["code"] == 4
    assert any("BSL method" in line and "not-run" in line for line in result["objects"][0]["report"]["lines"])


@pytest.mark.parametrize(
    "reference", ["CommonModule..Метод", ".Метод", "CommonModule.Модуль.", "CommonModule.Модуль.Не Метод"]
)
def test_verify_malformed_method_reference(tmp_path, reference):
    target, logical, path = sample(tmp_path, "ScheduledJob")
    root = etree.fromstring(path.read_bytes())
    root.find("m:ScheduledJob/m:Properties/m:MethodName", editor.NS).text = reference
    path.write_bytes(etree.tostring(root))
    report = editor.verify_objects(editor.Snapshot(target), [logical])["objects"][0]["report"]
    assert report["errors"] > 0
    assert any(line.startswith("[ERROR] 13.") for line in report["lines"])


def test_verify_missing_target_does_not_skip_next(tmp_path):
    target, logical, _ = sample(tmp_path, "Enum")
    result = editor.verify_objects(editor.Snapshot(target), ["Catalog.Нет", logical])
    assert result["code"] == 4
    assert result["objects"][0]["error"] == editor.PUBLIC_ERRORS[4]
    assert result["objects"][1]["code"] == 0


@pytest.mark.parametrize("arguments", [["--max-errors", "0"], ["--max-errors", "-1"], ["--unknown"]])
def test_verify_invalid_arguments(tmp_path, capsys, arguments):
    target, logical, _ = sample(tmp_path, "Enum")
    assert editor.main(["verify", "--root", str(target), "--object", logical, *arguments]) == 2
    result = json.loads(capsys.readouterr().out)
    Draft202012Validator(metadata_ops.RESULT_SCHEMA).validate(result)
    assert result["changes"] is None


def test_verify_snapshot_change_rejected(tmp_path, monkeypatch, capsys):
    target, logical, path = sample(tmp_path, "Enum")
    original = metadata_validate.object_report

    def changed(*args, **kwargs):
        report = original(*args, **kwargs)
        path.write_bytes(path.read_bytes() + b"\n")
        return report

    monkeypatch.setattr(metadata_validate, "object_report", changed)
    assert editor.main(["verify", "--root", str(target), "--object", logical]) == 3
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "rejected" and "local" not in result["checks"]


def test_verify_limits(tmp_path, monkeypatch):
    target, logical, _ = sample(tmp_path, "Enum")
    with pytest.raises(editor.Rejected, match="Too many"):
        editor.verify_objects(editor.Snapshot(target), [logical] * 101)
    report = metadata_validate.object_report

    def oversized(*args, **kwargs):
        result = report(*args, **kwargs)
        result["lines"].append("x" * (editor.FILE_LIMIT + 1))
        return result

    monkeypatch.setattr(metadata_validate, "object_report", oversized)
    with pytest.raises(editor.Rejected, match="output limit"):
        editor.verify_objects(editor.Snapshot(target), [logical])


def test_verify_process_envelope(tmp_path):
    target, logical, _ = sample(tmp_path, "Enum")
    process = subprocess.run(
        [sys.executable, "-m", "scripts.python.cli", "metadata", "verify", "--root", str(target), "--object", logical],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        timeout=30,
    )
    assert process.returncode == 0 and not process.stderr
    assert len(process.stdout.splitlines()) == 1
    result = json.loads(process.stdout)
    Draft202012Validator(metadata_ops.RESULT_SCHEMA).validate(result)
    assert result["status"] == "verified"


def compare_form(path, fixture, detailed=True):
    root = etree.fromstring(path.read_bytes())
    before = etree.tostring(root)
    report = metadata_validate.form_report(root, path.parent.parent.name, detailed=detailed)
    # The six input fixtures have nine successful checks each. Expectations
    # are derived from reading the old validator, not its execution.
    expected = ["=== Validation OK: Form.Форма (9 checks) ==="]
    if detailed:
        expected = [
            "=== Validation: Form.Форма ===",
            "",
            "[OK]    Root element: Form version=2.17",
            "[OK]    AutoCommandBar: name='ФормаКоманднаяПанель', id=-1",
            "[OK]    Unique element IDs: 3 elements",
            "[OK]    Unique attribute IDs: 4 entries",
        ]
        if fixture == "borrowed-cfe":
            expected += [
                "[OK]    Companion elements: 3 elements checked",
                "[OK]    DataPath references: 2 base skipped",
                "[OK]    MainAttribute: no main attribute",
                "[OK]    Title: multilingual XML",
                "[OK]    BaseForm: version=2.17",
            ]
        else:
            expected += [
                "[OK]    Unique command IDs: 1 entries",
                "[OK]    Companion elements: 3 elements checked",
                "[OK]    Command actions: 1 commands checked",
                "[OK]    MainAttribute: no main attribute",
                "[OK]    Title: multilingual XML",
            ]
        expected += ["", "=== Result: 0 errors, 0 warnings (9 checks) ==="]
    assert report["lines"] == expected
    assert report["errors"] == report["warnings"] == 0
    assert etree.tostring(root) == before
    return report


@pytest.mark.parametrize("fixture,logical", FORM_FIXTURES)
@pytest.mark.parametrize("detailed", [False, True])
def test_form_verify_matches_explicit_report(tmp_path, fixture, logical, detailed, monkeypatch):
    from scripts.python.metadata_form_ops import form_path

    target = tmp_path / "source"
    shutil.copytree(ROOT / "tests/fixtures/managed-form-cli" / fixture, target)
    path = target / form_path(logical)
    report = compare_form(path, fixture, detailed=detailed)
    base = None
    if fixture == "borrowed-cfe":
        base = tmp_path / "base"
        shutil.copytree(ROOT / "tests/fixtures/managed-form-cli/cf", base)
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    read = editor.Snapshot.read

    def no_bsl(self, alias, path, **kwargs):
        assert not path.endswith(".bsl")
        return read(self, alias, path, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("verify must not invoke legacy helper")

    monkeypatch.setattr(editor.Snapshot, "read", no_bsl)
    monkeypatch.setattr(subprocess, "run", forbidden)
    result = editor.verify_objects(editor.Snapshot(target), [logical], detailed=detailed, base_root=base)
    assert result["objects"][0]["report"] == report
    assert result["objects"][0]["baseLink"] == ("checked" if base else "not-applicable")
    assert result["code"] == (4 if report["errors"] or report["warnings"] else 0)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "fault",
    [
        "version",
        "title",
        "command",
        "datapath",
        "event",
        "action",
        "companion",
        "element-id",
        "attribute-id",
        "command-id",
    ],
)
def test_form_invalid_diagnostics_match_explicit_report(tmp_path, fault):
    from scripts.python.metadata_form_compile import render_form

    from .test_metadata_form_compile import rich_definition

    root = etree.fromstring(render_form(rich_definition()))
    if fault == "version":
        root.set("version", "2.99")
    elif fault == "title":
        title = root.find("f:Title", editor.NS)
        title[:] = []
        title.text = "Неверный заголовок"
    elif fault == "command":
        root.find(".//f:Button[@name='Выполнить']/f:CommandName", editor.NS).text = "Form.Command.Нет"
    elif fault == "datapath":
        root.find(".//f:DataPath", editor.NS).text = "Нет"
    elif fault == "event":
        root.find(".//f:Event", editor.NS).text = ""
    elif fault == "action":
        root.find(".//f:Action", editor.NS).text = ""
    elif fault == "companion":
        node = root.find(".//f:InputField", editor.NS)
        node.remove(node.find("f:ContextMenu", editor.NS))
    elif fault == "element-id":
        node = root.find("f:ChildItems", editor.NS)
        node.append(copy.deepcopy(node[0]))
    elif fault == "attribute-id":
        node = root.find("f:Attributes", editor.NS)
        node.append(copy.deepcopy(node[0]))
    else:
        node = root.find("f:Commands", editor.NS)
        node.append(copy.deepcopy(node[0]))
    path = tmp_path / "Форма" / "Ext" / "Form.xml"
    path.parent.mkdir(parents=True)
    path.write_bytes(etree.tostring(root))
    # Fixed diagnostics from reading the former validator and rich.xml.
    # R34 adds checks for table commands; successful-check lines intentionally
    # remain outside this comparison, as in the former exact=False branch.
    expected = {
        "version": ["[WARN]  Form version='2.99' (expected 2.17 or 2.20)"],
        "title": [
            "[ERROR] Form Title is plain text ('Неверный заголовок') — must be multilingual XML (<v8:item>). Use top-level 'title' key in form.compile DSL."
        ],
        "command": [
            "[ERROR] [Button] 'Выполнить': CommandName='Form.Command.Нет' — command 'Нет' not found in Commands"
        ],
        "datapath": ["[ERROR] [InputField] 'Поле': DataPath='Нет' — attribute 'Нет' not found"],
        "event": ["[ERROR] Form event 'OnOpen': empty handler name"],
        "action": ["[ERROR] Command 'Выполнить': missing or empty Action"],
        "companion": ["[ERROR] [InputField] 'Поле': missing companion <ContextMenu>"],
        "element-id": [
            "[ERROR] Duplicate element id=1: 'Группа' and 'Группа'",
            "[ERROR] Duplicate element id=3: 'Поле' and 'Поле'",
            "[ERROR] Duplicate element id=6: 'Флаг' and 'Флаг'",
            "[ERROR] Duplicate element id=9: 'Режим' and 'Режим'",
            "[ERROR] Duplicate element id=12: 'Ход' and 'Ход'",
            "[ERROR] Duplicate element id=15: 'Надпись' and 'Надпись'",
            "[ERROR] Duplicate element id=18: 'Представление' and 'Представление'",
            "[ERROR] Duplicate element id=21: 'Документ' and 'Документ'",
        ],
        "attribute-id": ["[ERROR] Duplicate attribute id=55: 'Текст' and 'Текст'"],
        "command-id": ["[ERROR] Duplicate command id=64: 'Выполнить' and 'Выполнить'"],
    }[fault]
    before = etree.tostring(root)
    report = metadata_validate.form_report(root, "Форма", detailed=True)
    assert [line for line in report["lines"] if line.startswith(("[ERROR]", "[WARN]"))] == expected
    assert report["errors"] == sum(line.startswith("[ERROR]") for line in expected)
    assert report["warnings"] == sum(line.startswith("[WARN]") for line in expected)
    assert etree.tostring(root) == before


@pytest.mark.parametrize("version", ["2.17", "2.20"])
@pytest.mark.parametrize("fault", ["none", "name", "id", "empty-action"])
def test_inherited_command_action_requires_matching_base_identity(fault, version):
    path = ROOT / "tests/fixtures/managed-form-cli/cf/CommonForms/Форма/Ext/Form.xml"
    root = etree.fromstring(path.read_bytes())
    root.set("version", version)
    base = copy.deepcopy(root)
    base.tag = f"{{{editor.FORM}}}BaseForm"
    root.append(base)
    command = root.find("f:Commands/f:Command", editor.NS)
    action = command.find("f:Action", editor.NS)
    if fault == "empty-action":
        action.text = ""
    else:
        command.remove(action)
    if fault in {"name", "id"}:
        command.set(fault, "Different" if fault == "name" else "1000000")
    before = etree.tostring(root)
    report = metadata_validate.form_report(root, "Форма", detailed=True)
    errors = [line for line in report["lines"] if "missing or empty Action" in line]
    assert bool(errors) == (fault != "none")
    assert not any("Form version=" in line for line in report["lines"] if line.startswith("[WARN]"))
    assert etree.tostring(root) == before


def test_missing_command_bar_is_allowed_only_for_borrowed_form():
    root = etree.parse(
        str(ROOT / "tests/fixtures/managed-form-cli/borrowed-cfe/CommonForms/Форма/Ext/Form.xml")
    ).getroot()
    root.remove(root.find("f:AutoCommandBar", editor.NS))
    before = etree.tostring(root)
    report = metadata_validate.form_report(root, "Форма")
    assert report["errors"] == 0
    assert etree.tostring(root) == before
    root.remove(root.find("f:BaseForm", editor.NS))
    report = metadata_validate.form_report(root, "Форма")
    assert "[ERROR] AutoCommandBar element missing" in report["lines"]


def test_borrowed_form_verify_requires_exact_base(tmp_path, capsys):
    target = tmp_path / "source"
    shutil.copytree(ROOT / "tests/fixtures/managed-form-cli/borrowed-cfe", target)
    base = tmp_path / "base"
    shutil.copytree(ROOT / "tests/fixtures/managed-form-cli/cf", base)
    args = ["verify", "--root", str(target), "--object", "CommonForm.Форма"]
    assert editor.main(args) != 0
    without = json.loads(capsys.readouterr().out)
    assert without["status"] == "rejected"
    assert editor.main([*args, "--base-root", str(base)]) == 0
    valid = json.loads(capsys.readouterr().out)
    Draft202012Validator(metadata_ops.RESULT_SCHEMA).validate(valid)
    assert valid["checks"]["local"]["objects"][0]["baseLink"] == "checked"
    descriptor = base / "CommonForms/Форма.xml"
    root = etree.fromstring(descriptor.read_bytes())
    root[0].set("uuid", "280179ba-92e8-47b4-b0b2-e9bcece0df19")
    descriptor.write_bytes(etree.tostring(root))
    assert editor.main([*args, "--base-root", str(base)]) != 0
    assert json.loads(capsys.readouterr().out)["status"] == "rejected"


def test_verify_mixed_form_object_batch(tmp_path, capsys):
    target = tmp_path / "source"
    shutil.copytree(ROOT / "tests/fixtures/managed-form-cli/cf", target)
    add_object(target, "Enum", "Статусы", values=[{"name": "Первый"}])
    assert (
        editor.main(["verify", "--root", str(target), "--object", "CommonForm.Форма", "--object", "Enum.Статусы"]) == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert [item["object"] for item in result["checks"]["local"]["objects"]] == ["CommonForm.Форма", "Enum.Статусы"]
    assert result["checks"]["platform"] == result["checks"]["runtime"] == "not-run"


@pytest.mark.parametrize("fault", ["command", "id", "event", "companion", "none"])
@pytest.mark.parametrize("container_name", ["AutoCommandBar", "ContextMenu"])
def test_form_checks_nested_table_commands(tmp_path, fault, container_name):
    from scripts.python.metadata_form_compile import render_form

    from .test_metadata_form_compile import rich_definition

    root = etree.fromstring(render_form(rich_definition()))
    button = root.find(".//f:Button[@name='ВыполнитьВТаблице']", editor.NS)
    if container_name == "ContextMenu":
        root.find(".//f:Table/f:ContextMenu", editor.NS).append(button.getparent())
    if fault == "command":
        button.find("f:CommandName", editor.NS).text = "Form.Command.Нет"
    elif fault == "id":
        button.set("id", root.find(".//f:Button[@name='Выполнить']", editor.NS).get("id"))
    elif fault == "event":
        events = etree.SubElement(button, f"{{{editor.FORM}}}Events")
        etree.SubElement(events, f"{{{editor.FORM}}}Event", name="Click")
    elif fault == "companion":
        button.remove(button.find("f:ExtendedTooltip", editor.NS))
    report = metadata_validate.form_report(root, "Форма")
    assert (report["errors"] > 0) == (fault != "none")
    target = tmp_path / "source"
    shutil.copytree(ROOT / "tests/fixtures/managed-form-cli/cf", target)
    (target / "CommonForms/Форма/Ext/Form.xml").write_bytes(etree.tostring(root))
    result = editor.verify_objects(editor.Snapshot(target), ["CommonForm.Форма"])
    assert result["objects"][0]["report"] == report
    assert result["code"] == (0 if fault == "none" else 4)


@pytest.mark.parametrize("fixture,kind", [("epf", "ExternalDataProcessor"), ("erf", "ExternalReport")])
def test_verify_accepts_external_root_object(tmp_path, fixture, kind):
    target = tmp_path / "external"
    shutil.copytree(ROOT / "tests/fixtures/managed-form-cli" / fixture, target)
    path = next(target.glob("*.xml"))
    name = editor.node_name(editor.metadata(path.read_bytes(), kind))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    result = editor.verify_objects(editor.Snapshot(target), [f"{kind}.{name}"])
    assert result["code"] == 0 and result["objects"][0]["report"]["errors"] == 0
    other = "ExternalReport" if kind == "ExternalDataProcessor" else "ExternalDataProcessor"
    assert editor.verify_objects(editor.Snapshot(target), [f"{other}.{name}"])["code"] == 4
    assert editor.verify_objects(editor.Snapshot(target), [f"{kind}.Отсутствует"])["code"] == 2
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


@pytest.mark.parametrize("kind,accepted", [("DataProcessor", True), ("Report", True), ("Catalog", False)])
def test_empty_attribute_type_is_arbitrary_only_for_processors_and_reports(tmp_path, kind, accepted):
    _, _, path = sample(tmp_path, kind)
    root = etree.fromstring(path.read_bytes())
    type_el = root[0].find("m:ChildObjects/m:Attribute/m:Properties/m:Type", editor.NS)
    for child in list(type_el):
        type_el.remove(child)
    type_el.text = None
    report = metadata_validate.object_report(root)
    assert (report["errors"] == 0) == accepted
