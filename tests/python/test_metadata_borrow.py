"""Object-shell adoption against Designer XML fixtures and the real Snapshot."""

from tests.python.metadata_test_support import designer_export, present  # noqa: I001 — runs first: skips the module without pytest, lxml, jsonschema
from pathlib import Path
import copy
import shutil
import uuid

import lxml.etree as etree
import pytest

from scripts.python import metadata as editor
from scripts.python import metadata_borrow as borrow, metadata_create as create


FIXTURES = Path(__file__).parents[1] / "fixtures/managed-form-cli"
TYPE_NS = {**editor.NS, "xr": borrow.XR}


@pytest.fixture
def roots(tmp_path):
    source, target = tmp_path / "base", tmp_path / "extension"
    shutil.copytree(FIXTURES / "cf", source)
    # Only the existing language is retained; other fixtures are not relevant
    # to the new object shell, but full Configuration properties are preserved.
    target.mkdir()
    shutil.copytree(FIXTURES / "own-cfe/Languages", target / "Languages")
    config = etree.fromstring((FIXTURES / "own-cfe/Configuration.xml").read_bytes())
    children = config.find("m:Configuration/m:ChildObjects", editor.NS)
    for child in list(children):
        if child.tag != f"{{{editor.MD}}}Language":
            children.remove(child)
    (target / "Configuration.xml").write_bytes(etree.tostring(config, encoding="UTF-8", xml_declaration=True))
    return source, target


def operation(source, target="DataProcessor.Владелец"):
    return {"op": "object.borrow", "target": target, "parameters": {"baseRoot": str(source)}}


def persist_for_next_snapshot(snapshot):
    for path, data in snapshot.writes.items():
        destination = snapshot.roots["target"] / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        assert data is not None
        destination.write_bytes(data)


def type_extension_fixture(roots):
    source, target = roots
    config_path = source / "Configuration.xml"
    config_bytes = config_path.read_bytes()
    config = editor.metadata(config_bytes, "Configuration")
    config_id = editor.identity(config)
    definitions = [
        {
            "type": "Catalog",
            "name": "ФизическиеЛица",
            "attributes": [{"name": name, "type": "String(50)"} for name in ("Фамилия", "Имя", "Отчество")],
        },
        {
            "type": "InformationRegister",
            "name": "ФИОФизическихЛиц",
            "resources": [{"name": name, "type": "String(50)"} for name in ("Фамилия", "Имя", "Отчество")],
        },
        {
            "type": "InformationRegister",
            "name": "ДокументыФизическихЛиц",
            "resources": [{"name": "КемВыдан", "type": "String(200)"}],
        },
        {
            "type": "ChartOfCharacteristicTypes",
            "name": "ВидыСубконтоХозрасчетные",
            "valueTypes": ["CatalogRef.Демо_БазовыйТип"],
        },
    ]
    registrations = []
    for definition in definitions:
        kind, name = definition["type"], definition["name"]
        directory = borrow.DIRECTORIES[kind]
        (source / directory).mkdir(parents=True, exist_ok=True)
        (source / f"{directory}/{name}.xml").write_bytes(create.render_object(definition, config_id, {}))
        registrations.append((kind, name))
    children = config.find("m:ChildObjects", editor.NS)
    for kind, name in registrations:
        etree.SubElement(children, f"{{{editor.MD}}}{kind}").text = name
    config_path.write_bytes(editor.serialize_like(config.getparent(), config_bytes))

    members = (
        [("Catalog", "ФизическиеЛица", "Attribute", name, "String(60)") for name in ("Фамилия", "Имя", "Отчество")]
        + [
            ("InformationRegister", "ФИОФизическихЛиц", "Resource", name, "String(60)")
            for name in ("Фамилия", "Имя", "Отчество")
        ]
        + [("InformationRegister", "ДокументыФизическихЛиц", "Resource", "КемВыдан", "String(0)")]
    )
    operations = [
        {
            "op": "member.extend-type",
            "target": f"{owner_kind}.{owner_name}.{member_kind}.{member_name}",
            "parameters": {"baseRoot": str(source), "type": requested_type},
        }
        for owner_kind, owner_name, member_kind, member_name, requested_type in members
    ]
    chart = "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные"
    operations.extend(
        [
            {
                "op": "object.create",
                "target": "Catalog.Демо_ТипДляРасширения",
                "parameters": {"definition": {"type": "Catalog", "name": "Демо_ТипДляРасширения"}},
            },
            {"op": "object.borrow", "target": chart, "parameters": {"baseRoot": str(source)}},
            {
                "op": "object.extend-type",
                "target": chart,
                "parameters": {"baseRoot": str(source), "types": ["CatalogRef.Демо_ТипДляРасширения"]},
            },
        ]
    )
    return source, target, {"schemaVersion": 1, "operations": operations}, members, chart


def test_member_extend_type_borrows_then_widens_attribute_and_resource_without_changing_base(roots):
    source, target = roots
    config_path = source / "Configuration.xml"
    config_bytes = config_path.read_bytes()
    config = editor.metadata(config_bytes, "Configuration")
    config_id = editor.identity(config)
    cases = [
        ("Catalog", "ФизическиеЛица", "attributes", "Attribute", "Фамилия", "String(50)", "String(60)", 60),
        (
            "InformationRegister",
            "ДокументыФизическихЛиц",
            "resources",
            "Resource",
            "КемВыдан",
            "String(200)",
            "String(0)",
            0,
        ),
    ]
    targets = []
    for owner_kind, owner_name, collection, member_kind, member_name, source_type, target_type, target_length in cases:
        definition = {"type": owner_kind, "name": owner_name, collection: [{"name": member_name, "type": source_type}]}
        data = create.render_object(definition, config_id, {})
        directory = borrow.DIRECTORIES[owner_kind]
        (source / directory).mkdir(parents=True, exist_ok=True)
        (source / f"{directory}/{owner_name}.xml").write_bytes(data)
        etree.SubElement(config.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}{owner_kind}").text = owner_name
        targets.append((owner_kind, owner_name, member_kind, member_name, target_type, target_length))
    config_path.write_bytes(editor.serialize_like(config.getparent(), config_bytes))
    original_source = {
        path.relative_to(source).as_posix(): path.read_bytes() for path in source.rglob("*") if path.is_file()
    }

    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "member.extend-type",
                "target": f"{owner_kind}.{owner_name}.{member_kind}.{member_name}",
                "parameters": {"baseRoot": str(source), "type": target_type},
            }
            for owner_kind, owner_name, member_kind, member_name, target_type, _ in targets
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    assert {
        path.relative_to(source).as_posix(): path.read_bytes() for path in source.rglob("*") if path.is_file()
    } == original_source

    for owner_kind, owner_name, member_kind, member_name, _target_type, target_length in targets:
        directory = borrow.DIRECTORIES[owner_kind]
        base = editor.metadata((source / f"{directory}/{owner_name}.xml").read_bytes(), owner_kind)
        adopted = editor.metadata((target / f"{directory}/{owner_name}.xml").read_bytes(), owner_kind)
        base_member = borrow._member(base, member_kind, member_name)
        adopted_member = borrow._member(adopted, member_kind, member_name)
        assert editor.prop(adopted_member, "ObjectBelonging") == "Adopted"
        assert editor.prop(adopted_member, "ExtendedConfigurationObject") == editor.identity(base_member)
        assert editor.identity(adopted_member) != editor.identity(base_member)
        typed = present(adopted_member).find("m:Properties/m:Type", editor.NS)
        assert typed.get("{http://www.w3.org/2001/XMLSchema-instance}type") == "xr:ExtendedProperty"
        assert [child.tag for child in typed] == [f"{{{borrow.XR}}}ExtendValue"]
        assert typed[0].get("{http://www.w3.org/2001/XMLSchema-instance}type") == "v8:TypeDescription"
        assert typed[0].get("{http://www.w3.org/2001/XMLSchema-instance}type") == "v8:TypeDescription"
        assert typed[0].findtext("v8:Type", namespaces=editor.NS) == "xs:string"
        assert typed[0].findtext("v8:StringQualifiers/v8:Length", namespaces=editor.NS) == str(target_length)
        assert typed[0].findtext("v8:StringQualifiers/v8:AllowedLength", namespaces=editor.NS) == "Variable"
        state = present(adopted_member).find("m:InternalInfo/xr:PropertyState", TYPE_NS)
        assert state.findtext("xr:Property", namespaces=TYPE_NS) == "Type"
        assert state.findtext("xr:State", namespaces=TYPE_NS) == "MultiState"
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []

    before_target = {
        path.relative_to(target).as_posix(): path.read_bytes() for path in target.rglob("*") if path.is_file()
    }
    narrowing = {
        "schemaVersion": 1,
        "operations": [{**payload["operations"][0], "parameters": {"baseRoot": str(source), "type": "String(0)"}}],
    }
    with pytest.raises(editor.Rejected, match="Existing adopted string extension differs"):
        editor.plan_make(editor.Snapshot(target), narrowing)
    assert {
        path.relative_to(target).as_posix(): path.read_bytes() for path in target.rglob("*") if path.is_file()
    } == before_target

    owner_path = target / "Catalogs/ФизическиеЛица.xml"
    owner_bytes = owner_path.read_bytes()
    owner = editor.metadata(owner_bytes, "Catalog")
    member = borrow._member(owner, "Attribute", "Фамилия")
    present(member).find("m:Properties/m:ExtendedConfigurationObject", editor.NS).text = str(uuid.uuid4())
    owner_path.write_bytes(editor.serialize_like(owner.getparent(), owner_bytes))
    conflicting_target = {
        path.relative_to(target).as_posix(): path.read_bytes() for path in target.rglob("*") if path.is_file()
    }
    with pytest.raises(editor.Rejected, match="Existing member has a conflicting base link"):
        editor.plan_make(editor.Snapshot(target), payload)
    assert {
        path.relative_to(target).as_posix(): path.read_bytes() for path in target.rglob("*") if path.is_file()
    } == conflicting_target

    owner_path.write_bytes(owner_bytes)
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "already-applied"
    owner_bytes = owner_path.read_bytes()
    owner = editor.metadata(owner_bytes, "Catalog")
    member = borrow._member(owner, "Attribute", "Фамилия")
    present(member).find("m:Properties/m:ExtendedConfigurationObject", editor.NS).getparent().remove(
        present(member).find("m:Properties/m:ExtendedConfigurationObject", editor.NS)
    )
    owner_path.write_bytes(editor.serialize_like(owner.getparent(), owner_bytes))
    with pytest.raises(editor.Rejected, match="conflicting base link"):
        editor.plan_make(editor.Snapshot(target), payload)


def test_member_extend_type_adds_reference_and_string_union_to_attributes_and_tabular_section(roots):
    source, target = roots
    config_path = source / "Configuration.xml"
    config_bytes = config_path.read_bytes()
    config = editor.metadata(config_bytes, "Configuration")
    config_id = editor.identity(config)
    definitions = [
        {"type": "Enum", "name": "ОсновныеВиды", "values": [{"name": "Первый"}]},
        {"type": "Enum", "name": "ДемоВиды", "values": [{"name": "Второй"}]},
        {"type": "Catalog", "name": "Файлы", "attributes": [{"name": "Описание", "type": "String(50)"}]},
        {
            "type": "Document",
            "name": "Контейнер",
            "attributes": [{"name": "Вид", "type": "EnumRef.ОсновныеВиды"}, {"name": "Код", "type": "String(50)"}],
            "tabularSections": [{"name": "Документы", "attributes": [{"name": "Файл", "type": "CatalogRef.Файлы"}]}],
        },
    ]
    for definition in definitions:
        kind, name = definition["type"], definition["name"]
        directory = borrow.DIRECTORIES[kind]
        (source / directory).mkdir(parents=True, exist_ok=True)
        (source / f"{directory}/{name}.xml").write_bytes(create.render_object(definition, config_id, {}))
        etree.SubElement(config.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}{kind}").text = name
    config_path.write_bytes(editor.serialize_like(config.getparent(), config_bytes))
    source_before = {
        path.relative_to(source).as_posix(): path.read_bytes() for path in source.rglob("*") if path.is_file()
    }

    operations = [
        {"op": "object.borrow", "target": "Enum.ОсновныеВиды", "parameters": {"baseRoot": str(source)}},
        {"op": "object.borrow", "target": "Enum.ДемоВиды", "parameters": {"baseRoot": str(source)}},
        {"op": "object.borrow", "target": "Catalog.Файлы", "parameters": {"baseRoot": str(source)}},
        {
            "op": "member.extend-type",
            "target": "Document.Контейнер.Attribute.Вид",
            "parameters": {"baseRoot": str(source), "type": "EnumRef.ДемоВиды"},
        },
        {
            "op": "member.extend-type",
            "target": "Document.Контейнер.Attribute.Код",
            "parameters": {"baseRoot": str(source), "type": "String(0)"},
        },
        {
            "op": "member.extend-type",
            "target": "Document.Контейнер.TabularSection.Документы.Attribute.Файл",
            "parameters": {"baseRoot": str(source), "type": "String(15)"},
        },
    ]
    payload = {"schemaVersion": 1, "operations": operations}
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    assert {
        path.relative_to(source).as_posix(): path.read_bytes() for path in source.rglob("*") if path.is_file()
    } == source_before

    owner = editor.metadata((target / "Documents/Контейнер.xml").read_bytes(), "Document")
    source_owner = editor.metadata((source / "Documents/Контейнер.xml").read_bytes(), "Document")
    checks = [
        (
            borrow._member(owner, "Attribute", "Вид"),
            borrow._member(source_owner, "Attribute", "Вид"),
            "cfg:EnumRef.ДемоВиды",
            None,
        ),
        (borrow._member(owner, "Attribute", "Код"), borrow._member(source_owner, "Attribute", "Код"), "xs:string", "0"),
        (
            borrow._member(borrow._member(owner, "TabularSection", "Документы"), "Attribute", "Файл"),
            borrow._member(borrow._member(source_owner, "TabularSection", "Документы"), "Attribute", "Файл"),
            "xs:string",
            "15",
        ),
    ]
    for node, source_node, type_text, length in checks:
        assert editor.prop(node, "ObjectBelonging") == "Adopted"
        assert editor.prop(node, "ExtendedConfigurationObject") == editor.identity(source_node)
        extension = node.find("m:Properties/m:Type/xr:ExtendValue", TYPE_NS)
        assert extension is not None
        assert extension.findtext("v8:Type", namespaces=editor.NS) == type_text
        if length:
            assert extension.findtext("v8:StringQualifiers/v8:Length", namespaces=editor.NS) == length
    base_ts = checks[-1][1]
    assert base_ts.findtext("m:Properties/m:Type/v8:Type", namespaces=editor.NS) == "cfg:CatalogRef.Файлы"


def test_chart_type_extension_appends_explicit_refs_without_replacing_base_or_existing_types(roots):
    source, target = roots
    config_path = source / "Configuration.xml"
    config_bytes = config_path.read_bytes()
    config = editor.metadata(config_bytes, "Configuration")
    chart_name = "ВидыСубконтоХозрасчетные"
    chart_logical = "ChartOfCharacteristicTypes." + chart_name
    base_types = ["CatalogRef.Субконто", "DocumentRef.Поступление"]
    chart = create.render_object(
        {"type": "ChartOfCharacteristicTypes", "name": chart_name, "valueTypes": base_types},
        editor.identity(config),
        {},
    )
    (source / "ChartsOfCharacteristicTypes").mkdir()
    (source / f"ChartsOfCharacteristicTypes/{chart_name}.xml").write_bytes(chart)
    etree.SubElement(
        config.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}ChartOfCharacteristicTypes"
    ).text = chart_name
    config_path.write_bytes(editor.serialize_like(config.getparent(), config_bytes))
    source_before = {
        path.relative_to(source).as_posix(): path.read_bytes() for path in source.rglob("*") if path.is_file()
    }

    first = "CatalogRef.Демо_ВидыРасчетов"
    second = "CatalogRef.Демо_Заказы"
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.create",
                "target": "Catalog.Демо_ВидыРасчетов",
                "parameters": {"definition": {"type": "Catalog", "name": "Демо_ВидыРасчетов"}},
            },
            {"op": "object.borrow", "target": chart_logical, "parameters": {"baseRoot": str(source)}},
            {
                "op": "object.extend-type",
                "target": chart_logical,
                "parameters": {"baseRoot": str(source), "types": [first]},
            },
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []

    chart_path = target / "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные.xml"
    adopted = editor.metadata(chart_path.read_bytes(), "ChartOfCharacteristicTypes")
    identity = editor.identity(adopted)
    generated_ids = [
        (node.tag, node.text)
        for node in adopted.iter()
        if node.tag in {f"{{{borrow.XR}}}TypeId", f"{{{borrow.XR}}}ValueId"}
    ]
    type_property = adopted.find("m:Properties/m:Type", editor.NS)
    assert type_property.get("{http://www.w3.org/2001/XMLSchema-instance}type") == "xr:ExtendedProperty"
    assert [node.text for node in type_property.findall(f"{{{borrow.XR}}}ExtendValue/{{{editor.V8}}}Type")] == [
        "cfg:" + first
    ]
    assert [child.tag for child in type_property] == [f"{{{borrow.XR}}}ExtendValue"]
    assert type_property[0].get("{http://www.w3.org/2001/XMLSchema-instance}type") == "v8:TypeDescription"
    state = adopted.find("m:InternalInfo/xr:PropertyState", TYPE_NS)
    assert state.findtext("xr:Property", namespaces=TYPE_NS) == "Type"
    assert state.findtext("xr:State", namespaces=TYPE_NS) == "MultiState"

    second_payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.create",
                "target": "Catalog.Демо_Заказы",
                "parameters": {"definition": {"type": "Catalog", "name": "Демо_Заказы"}},
            },
            {"op": "object.borrow", "target": chart_logical, "parameters": {"baseRoot": str(source)}},
            {
                "op": "object.extend-type",
                "target": chart_logical,
                "parameters": {"baseRoot": str(source), "types": [second]},
            },
        ],
    }
    second_plan = editor.plan_make(editor.Snapshot(target), second_payload)
    assert editor.apply(target, None, second_plan) == "applied"
    assert editor.apply(target, None, second_plan) == "already-applied"
    assert editor.plan_make(editor.Snapshot(target), second_payload)["writes"] == []
    adopted = editor.metadata(chart_path.read_bytes(), "ChartOfCharacteristicTypes")
    type_property = adopted.find("m:Properties/m:Type", editor.NS)
    assert [node.text for node in type_property.findall(f"{{{borrow.XR}}}ExtendValue/{{{editor.V8}}}Type")] == [
        "cfg:" + first,
        "cfg:" + second,
    ]
    assert editor.identity(adopted) == identity
    assert [
        (node.tag, node.text)
        for node in adopted.iter()
        if node.tag in {f"{{{borrow.XR}}}TypeId", f"{{{borrow.XR}}}ValueId"}
    ] == generated_ids
    assert {
        path.relative_to(source).as_posix(): path.read_bytes() for path in source.rglob("*") if path.is_file()
    } == source_before


def test_object_extend_type_removes_only_exact_base_check_on_explicit_request(roots):
    source, target, payload, _, chart = type_extension_fixture(roots)
    create_payload = {"schemaVersion": 1, "operations": payload["operations"][-3:]}
    create_plan = editor.plan_make(editor.Snapshot(target), create_payload)
    assert editor.apply(target, None, create_plan) == "applied"

    chart_path = target / "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные.xml"
    source_chart_path = source / "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные.xml"
    source_chart = editor.metadata(source_chart_path.read_bytes(), "ChartOfCharacteristicTypes")
    base_type = source_chart.find("m:Properties/m:Type", editor.NS)
    target_before = chart_path.read_bytes()
    target_chart = editor.metadata(target_before, "ChartOfCharacteristicTypes")
    target_type = target_chart.find("m:Properties/m:Type", editor.NS)
    check = etree.Element(
        f"{{{borrow.XR}}}CheckValue", attrib={"{http://www.w3.org/2001/XMLSchema-instance}type": "v8:TypeDescription"}
    )
    for child in base_type:
        check.append(copy.deepcopy(child))
    target_type.insert(0, check)
    chart_path.write_bytes(editor.serialize_like(target_chart.getparent(), target_before))
    exact_check_bytes = chart_path.read_bytes()

    parameters = {"baseRoot": str(source), "types": ["CatalogRef.Демо_ТипДляРасширения"]}
    default_request = {
        "schemaVersion": 1,
        "operations": [{"op": "object.extend-type", "target": chart, "parameters": parameters}],
    }
    assert editor.plan_make(editor.Snapshot(target), default_request)["writes"] == []
    assert chart_path.read_bytes() == exact_check_bytes
    assert (
        editor.metadata(chart_path.read_bytes(), "ChartOfCharacteristicTypes").find(
            "m:Properties/m:Type/xr:CheckValue", TYPE_NS
        )
        is not None
    )

    remove_request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.extend-type",
                "target": chart,
                "parameters": {**parameters, "checkBaseType": False},
            }
        ],
    }
    remove_plan = editor.plan_make(editor.Snapshot(target), remove_request)
    assert [write["path"] for write in remove_plan["writes"]] == [
        "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные.xml"
    ]
    planned_chart = editor.metadata(
        present(editor.state_bytes(remove_plan["writes"][0]["after"])), "ChartOfCharacteristicTypes"
    )
    planned_type = planned_chart.find("m:Properties/m:Type", editor.NS)
    assert planned_type.find("xr:CheckValue", TYPE_NS) is None
    assert [node.text for node in planned_type.findall("xr:ExtendValue/v8:Type", TYPE_NS)] == [
        "cfg:CatalogRef.Демо_ТипДляРасширения"
    ]
    assert editor.apply(target, None, remove_plan) == "applied"
    assert editor.plan_make(editor.Snapshot(target), remove_request)["writes"] == []

    repaired_bytes = chart_path.read_bytes()
    repaired_chart = editor.metadata(repaired_bytes, "ChartOfCharacteristicTypes")
    repaired_type = repaired_chart.find("m:Properties/m:Type", editor.NS)
    bad_check = etree.Element(
        f"{{{borrow.XR}}}CheckValue", attrib={"{http://www.w3.org/2001/XMLSchema-instance}type": "v8:TypeDescription"}
    )
    etree.SubElement(bad_check, f"{{{editor.V8}}}Type").text = "cfg:CatalogRef.ДругойТип"
    repaired_type.insert(0, bad_check)
    chart_path.write_bytes(editor.serialize_like(repaired_chart.getparent(), repaired_bytes))
    invalid_before = chart_path.read_bytes()
    with pytest.raises(editor.Rejected, match="Adopted Type CheckValue differs from base Type"):
        editor.plan_make(editor.Snapshot(target), remove_request)
    assert chart_path.read_bytes() == invalid_before


@pytest.mark.parametrize("old_shape", ["missing-state", "empty-check"])
def test_type_extension_handlers_repair_exact_legacy_format_for_all_eight_nodes(roots, old_shape):
    source, target, payload, members, chart = type_extension_fixture(roots)
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"

    owners = {(kind, name) for kind, name, *_ in members}
    owners.add(("ChartOfCharacteristicTypes", chart.split(".")[1]))
    identities = {}
    extension_contents = {}
    extension_count = 0
    for kind, name in owners:
        path = f"{borrow.DIRECTORIES[kind]}/{name}.xml"
        owner = editor.metadata((target / path).read_bytes(), kind)
        identities[path] = editor.identity(owner)
        type_nodes = owner.findall(".//m:Type", editor.NS)
        for typed in type_nodes:
            if typed.get("{http://www.w3.org/2001/XMLSchema-instance}type") == "xr:ExtendedProperty":
                assert [child.tag for child in typed] == [f"{{{borrow.XR}}}ExtendValue"]
                extension_contents.setdefault(path, []).append(etree.tostring(typed[0]))
                extension_count += 1
                if old_shape == "empty-check":
                    check = etree.Element(
                        f"{{{borrow.XR}}}CheckValue",
                        attrib={"{http://www.w3.org/2001/XMLSchema-instance}type": "v8:TypeDescription"},
                    )
                    typed.insert(0, check)
                typed_owner = typed.getparent().getparent()
                internal = typed_owner.find("m:InternalInfo", editor.NS)
                for state in list(internal.findall("xr:PropertyState", TYPE_NS)):
                    if old_shape == "missing-state" and state.findtext("xr:Property", namespaces=TYPE_NS) == "Type":
                        internal.remove(state)
        (target / path).write_bytes(editor.serialize_like(owner.getparent(), (target / path).read_bytes()))

    assert extension_count == 8
    repair_plan = editor.plan_make(editor.Snapshot(target), payload)
    assert len(repair_plan["writes"]) == 4
    assert editor.apply(target, None, repair_plan) == "applied"
    assert editor.apply(target, None, repair_plan) == "already-applied"
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []

    for kind, name in owners:
        path = f"{borrow.DIRECTORIES[kind]}/{name}.xml"
        owner = editor.metadata((target / path).read_bytes(), kind)
        assert editor.identity(owner) == identities[path]
        extensions = [
            typed
            for typed in owner.findall(".//m:Type", editor.NS)
            if typed.get("{http://www.w3.org/2001/XMLSchema-instance}type") == "xr:ExtendedProperty"
        ]
        repaired_contents = []
        for typed in extensions:
            assert [child.tag for child in typed] == [f"{{{borrow.XR}}}ExtendValue"]
            repaired_contents.append(etree.tostring(typed[0]))
            state_owner = typed.getparent().getparent()
            state = state_owner.find("m:InternalInfo/xr:PropertyState", TYPE_NS)
            assert state.findtext("xr:Property", namespaces=TYPE_NS) == "Type"
            assert state.findtext("xr:State", namespaces=TYPE_NS) == "MultiState"
        assert repaired_contents == extension_contents[path]


@pytest.mark.parametrize(
    ("owner_family", "bad_marker"),
    [
        ("member", "unexpected-child"),
        ("member", "conflicting-state"),
        ("chart", "unexpected-child"),
        ("chart", "conflicting-state"),
        ("member", "nonempty-check"),
        ("chart", "nonempty-check"),
    ],
)
def test_type_extension_handlers_reject_other_malformed_extensions(roots, owner_family, bad_marker):
    source, target, payload, members, chart = type_extension_fixture(roots)
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    if owner_family == "member":
        owner_kind, owner_name, member_kind, member_name, _ = members[0]
        member = member_kind, member_name
    else:
        owner_kind, owner_name = "ChartOfCharacteristicTypes", chart.split(".")[1]
        member = None
    owner_path = target / f"{borrow.DIRECTORIES[owner_kind]}/{owner_name}.xml"
    owner_bytes = owner_path.read_bytes()
    owner = editor.metadata(owner_bytes, owner_kind)
    target_owner = borrow._member(owner, *member) if member else owner
    typed = present(target_owner).find("m:Properties/m:Type", editor.NS)
    if bad_marker == "unexpected-child":
        etree.SubElement(typed, f"{{{borrow.XR}}}Unexpected")
    elif bad_marker == "nonempty-check":
        check = etree.Element(
            f"{{{borrow.XR}}}CheckValue",
            attrib={"{http://www.w3.org/2001/XMLSchema-instance}type": "v8:TypeDescription"},
        )
        etree.SubElement(check, f"{{{editor.V8}}}Type").text = "xs:string"
        typed.insert(0, check)
    else:
        state = etree.SubElement(
            present(target_owner).find("m:InternalInfo", editor.NS), f"{{{borrow.XR}}}PropertyState"
        )
        etree.SubElement(state, f"{{{borrow.XR}}}Property").text = "Type"
        etree.SubElement(state, f"{{{borrow.XR}}}State").text = "Checked"
    owner_path.write_bytes(editor.serialize_like(owner.getparent(), owner_bytes))
    conflict_before = {
        path.relative_to(target).as_posix(): path.read_bytes() for path in target.rglob("*") if path.is_file()
    }
    with pytest.raises(
        editor.Rejected,
        match="Unsupported Type extension state|Conflicting Type property state|Unsupported Type check value|Adopted Type CheckValue differs from base Type",
    ):
        editor.plan_make(editor.Snapshot(target), payload)
    assert {
        path.relative_to(target).as_posix(): path.read_bytes() for path in target.rglob("*") if path.is_file()
    } == conflict_before


def test_report_shell_requires_children_and_repairs_earlier_shell(roots):
    source, target = roots
    config_path = source / "Configuration.xml"
    config = etree.fromstring(config_path.read_bytes())
    config.find(".//m:ChildObjects/m:DataProcessor", editor.NS).tag = f"{{{editor.MD}}}Report"
    config_path.write_bytes(etree.tostring(config))
    report = etree.fromstring((source / "DataProcessors/Владелец.xml").read_bytes())
    report.find("m:DataProcessor", editor.NS).tag = f"{{{editor.MD}}}Report"
    (source / "Reports").mkdir()
    (source / "Reports/Владелец.xml").write_bytes(etree.tostring(report))
    request = operation(source, "Report.Владелец")
    snapshot = editor.Snapshot(target)
    borrow.borrow_object(snapshot, request)
    persist_for_next_snapshot(snapshot)
    path = target / "Reports/Владелец.xml"
    node = editor.metadata(path.read_bytes(), "Report")
    children = node.find("m:ChildObjects", editor.NS)
    assert children is not None and len(children) == 0
    node.remove(children)
    path.write_bytes(etree.tostring(node.getparent()))
    repair = editor.Snapshot(target)
    borrow.borrow_object(repair, request)
    assert set(repair.writes) == {"Reports/Владелец.xml"}
    persist_for_next_snapshot(repair)
    repeated = editor.Snapshot(target)
    borrow.borrow_object(repeated, request)
    assert repeated.writes == {}


def test_explicit_restore_registration_preserves_adopted_files(roots):
    source, target = roots
    snapshot = editor.Snapshot(target)
    borrow.borrow_object(snapshot, operation(source))
    persist_for_next_snapshot(snapshot)
    path = target / "Configuration.xml"
    config = editor.metadata(path.read_bytes(), "Configuration")
    children = config.find("m:ChildObjects", editor.NS)
    children.remove(children.find("m:DataProcessor", editor.NS))
    path.write_bytes(etree.tostring(config.getparent()))
    before = (target / "DataProcessors/Владелец.xml").read_bytes()
    with pytest.raises(editor.Rejected, match="registration/file mismatch"):
        borrow.borrow_object(editor.Snapshot(target), operation(source))
    restore = operation(source)
    restore["parameters"]["restoreRegistration"] = True
    plan = editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [restore]})
    assert editor.apply(target, None, plan) == "applied"
    assert (target / "DataProcessors/Владелец.xml").read_bytes() == before
    again = editor.Snapshot(target)
    borrow.borrow_object(again, restore)
    assert again.writes == {}
    node = editor.metadata(before, "DataProcessor")
    node.find("m:Properties/m:ExtendedConfigurationObject", editor.NS).text = str(uuid.uuid4())
    (target / "DataProcessors/Владелец.xml").write_bytes(etree.tostring(node.getparent()))
    with pytest.raises(editor.Rejected, match="conflicting base link"):
        borrow.borrow_object(editor.Snapshot(target), restore)


@pytest.fixture(params=["common", "owner"])
def form_roots(roots, request):
    source, target = roots
    common_stem = "CommonForms/Форма"
    stem, logical = common_stem, "CommonForm.Форма"
    if request.param == "owner":
        stem, logical = "DataProcessors/Владелец/Forms/Форма", "DataProcessor.Владелец.Form.Форма"
        shutil.copytree(source / common_stem, source / stem)
        descriptor = editor.metadata((source / (common_stem + ".xml")).read_bytes(), "CommonForm")
        descriptor.tag = f"{{{editor.MD}}}Form"
        descriptor.set("uuid", str(uuid.uuid4()))
        (source / (stem + ".xml")).write_bytes(etree.tostring(descriptor.getparent()))
        path = source / "DataProcessors/Владелец.xml"
        owner = editor.metadata(path.read_bytes(), "DataProcessor")
        etree.SubElement(owner.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}Form").text = "Форма"
        path.write_bytes(etree.tostring(owner.getparent()))
    return source, target, stem, {"op": "form.borrow", "target": logical, "parameters": {"baseRoot": str(source)}}


def test_module_only_borrow_uses_target_format_and_preserves_existing(form_roots):
    source, target, stem, operation = form_roots
    path = source / (stem + "/Ext/Form.xml")
    form = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
    target_config = editor.metadata((target / "Configuration.xml").read_bytes(), "Configuration")
    version = target_config.getparent().get("version")
    form.set("version", "2.20" if version == "2.17" else "2.17")
    etree.SubElement(form, f"{{{editor.FORM}}}UnsupportedNewProperty").text = "not copied"
    path.write_bytes(etree.tostring(form))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected, match="format differs"):
        editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [operation]})
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    operation["parameters"]["moduleOnly"] = True
    plan = editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [operation]})
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    delta = editor.xml_read((target / (stem + "/Ext/Form.xml")).read_bytes(), f"{{{editor.FORM}}}Form")
    assert delta.get("version") == version
    assert [node.tag for node in delta] == [f"{{{editor.FORM}}}BaseForm"]
    assert delta[0].get("version") == version and len(delta[0]) == 0
    assert (target / (stem + "/Ext/Form/Module.bsl")).read_bytes() == b""
    assert editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [operation]})["writes"] == []
    operation["parameters"]["borrowMainAttribute"] = "Form"
    with pytest.raises(editor.Rejected, match="cannot include main attribute"):
        editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [operation]})


@pytest.mark.parametrize("version", ["2.17", "2.20"])
def test_form_borrow_preserves_tree_and_repeat_changes(form_roots, version):
    source, target, stem, operation = form_roots
    for directory in (source, target):
        for file in directory.rglob("*.xml"):
            tree = etree.fromstring(file.read_bytes())
            if tree.get("version") in {"2.17", "2.20"}:
                tree.set("version", version)
                file.write_bytes(etree.tostring(tree))
    path, module = stem + "/Ext/Form.xml", stem + "/Ext/Form/Module.bsl"
    source_form = etree.fromstring((source / path).read_bytes())
    for parent in (source_form, source_form.find("f:ChildItems/f:UsualGroup", editor.NS)):
        events = etree.SubElement(parent, f"{{{editor.FORM}}}Events")
        etree.SubElement(events, f"{{{editor.FORM}}}Event", name="OnCreateAtServer").text = "BaseHandler"
    (source / path).write_bytes(etree.tostring(source_form))
    before = {p: p.read_bytes() for p in source.rglob("*") if p.is_file()}
    request = {"schemaVersion": 1, "operations": [operation]}
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    original = editor.xml_read(before[source / path], f"{{{editor.FORM}}}Form")
    # Only inherited bindings differ from the source; other bytes/trees below
    # still establish preservation, not platform execution of those handlers.
    for binding in original.xpath(".//f:Events | ./f:Commands/f:Command/f:Action", namespaces=editor.NS):
        binding.getparent().remove(binding)
    form = editor.xml_read((target / path).read_bytes(), f"{{{editor.FORM}}}Form")
    base = form.find("f:BaseForm", editor.NS)
    base.tag = original.tag
    assert editor.signature(base) == editor.signature(original)
    form.remove(base)
    assert editor.signature(form) == editor.signature(original)
    for file in target.rglob("*.xml"):
        tree = etree.fromstring(file.read_bytes())
        if tree.tag in {f"{{{editor.MD}}}MetaDataObject", f"{{{editor.FORM}}}Form"}:
            assert tree.get("version") == version
    assert (target / module).read_bytes() == b""
    # Preserve extension edits and BSL; neither belongs to repeated borrowing.
    modified = editor.xml_read((target / path).read_bytes(), f"{{{editor.FORM}}}Form")
    modified.find("f:AutoCommandBar/f:Autofill", editor.NS).text = "true"
    events = etree.SubElement(modified, f"{{{editor.FORM}}}Events")
    etree.SubElement(events, f"{{{editor.FORM}}}Event", name="OnOpen", callType="After").text = "ExtensionHandler"
    etree.SubElement(
        modified.find("f:Commands/f:Command", editor.NS), f"{{{editor.FORM}}}Action", callType="Before"
    ).text = "ExtensionAction"
    (target / path).write_bytes(editor.serialize_like(modified, (target / path).read_bytes()))
    (target / module).write_bytes(b"\xef\xbb\xbf// existing extension module\r\n")
    repeat = editor.plan_make(editor.Snapshot(target), request)
    assert repeat["writes"] == []
    assert before == {p: p.read_bytes() for p in source.rglob("*") if p.is_file()}


@pytest.mark.parametrize("form_roots", ["common"], indirect=True)
def test_form_borrow_generic_document_ref_passes_plan_apply_and_verify(form_roots):
    source, target, stem, operation = form_roots
    path = source / stem / "Ext/Form.xml"
    original = path.read_bytes()
    form = editor.xml_read(original, f"{{{editor.FORM}}}Form")
    attribute = etree.SubElement(
        form.find(f"{{{editor.FORM}}}Attributes"),
        f"{{{editor.FORM}}}Attribute",
        name="РасшифровкаПлатежаСделка",
        id="999",
    )
    typed = etree.SubElement(attribute, f"{{{editor.FORM}}}Type")
    etree.SubElement(typed, f"{{{editor.V8}}}TypeSet").text = "cfg:DocumentRef"
    path.write_bytes(editor.serialize_like(form, original))

    plan = editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [operation]})
    assert editor.apply(target, None, plan) == "applied"
    assert editor.verify_plan(target, plan)[0] == "after"
    borrowed = editor.xml_read((target / stem / "Ext/Form.xml").read_bytes(), f"{{{editor.FORM}}}Form")
    assert borrowed.findtext(".//v8:TypeSet", namespaces=editor.NS) == "cfg:DocumentRef"


def test_form_borrow_native_command_projection_and_bounded_repair(form_roots):
    source, target, stem, operation = form_roots
    path = stem + "/Ext/Form.xml"
    source_path = source / path
    source_bytes = source_path.read_bytes()
    source_form = editor.xml_read(source_bytes, f"{{{editor.FORM}}}Form")
    command_bar = source_form.find("f:AutoCommandBar", editor.NS)
    children = etree.SubElement(command_bar, f"{{{editor.FORM}}}ChildItems")
    for name, command, node_id in (
        ("Провести", "Form.StandardCommand.Post", "991"),
        ("ИзменитьФорму", "Form.StandardCommand.CustomizeForm", "992"),
    ):
        button = etree.SubElement(children, f"{{{editor.FORM}}}Button", name=name, id=node_id)
        etree.SubElement(button, f"{{{editor.FORM}}}CommandName").text = command
    command_set = etree.SubElement(source_form, f"{{{editor.FORM}}}CommandSet")
    etree.SubElement(command_set, f"{{{editor.FORM}}}ExcludedCommand").text = "Copy"
    source_path.write_bytes(editor.serialize_like(source_form, source_bytes))

    request = {"schemaVersion": 1, "operations": [operation]}
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.verify_plan(target, plan)[0] == "after"
    borrowed_path = target / path
    borrowed = editor.xml_read(borrowed_path.read_bytes(), f"{{{editor.FORM}}}Form")
    assert [node.text for node in borrowed.findall(".//f:CommandName", editor.NS)] == ["0", "0", "0", "0"]
    assert borrowed.findtext("f:CommandSet/f:ExcludedCommand", namespaces=editor.NS) == "Copy"
    assert [node.text for node in borrowed.findall("f:BaseForm/f:CommandSet/f:ExcludedCommand", editor.NS)] == ["Copy"]

    # Model a form already borrowed by the old projection, with local edits.
    for form_tree in (borrowed, borrowed.find("f:BaseForm", editor.NS)):
        for node in form_tree.findall(".//f:CommandName", editor.NS):
            if node.getparent().get("id") == "991":
                node.text = "Form.StandardCommand.Post"
            elif node.getparent().get("id") == "992":
                node.text = "Form.StandardCommand.CustomizeForm"
    user_item = etree.SubElement(
        borrowed.find("f:ChildItems", editor.NS), f"{{{editor.FORM}}}UsualGroup", name="UserAdded", id="1000000"
    )
    etree.SubElement(user_item, f"{{{editor.FORM}}}Title").text = "Пользовательское поле"
    events = etree.SubElement(borrowed, f"{{{editor.FORM}}}Events")
    etree.SubElement(events, f"{{{editor.FORM}}}Event", name="OnOpen").text = "ExtensionHandler"
    borrowed_path.write_bytes(editor.serialize_like(borrowed, borrowed_path.read_bytes()))
    module_path = target / stem / "Ext/Form/Module.bsl"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_bytes(b"// user-owned BSL\n")
    before_repair = borrowed_path.read_bytes()

    repair_request = {
        "schemaVersion": 1,
        "operations": [
            {
                **operation,
                "parameters": {**operation["parameters"], "repairNativeCommandProjection": True},
            }
        ],
    }
    repair_plan = editor.plan_make(editor.Snapshot(target), repair_request)
    assert [write["path"] for write in repair_plan["writes"]] == [path]
    assert editor.apply(target, None, repair_plan) == "applied"
    assert editor.verify_plan(target, repair_plan)[0] == "after"
    repaired = editor.xml_read(borrowed_path.read_bytes(), f"{{{editor.FORM}}}Form")
    assert [node.text for node in repaired.findall(".//f:CommandName", editor.NS)] == ["0", "0", "0", "0"]
    assert editor.named(repaired)["useradded"].get("id") == "1000000"
    assert repaired.findtext("f:Events/f:Event", namespaces=editor.NS) == "ExtensionHandler"
    assert repaired.findtext("f:CommandSet/f:ExcludedCommand", namespaces=editor.NS) == "Copy"
    assert module_path.read_bytes() == b"// user-owned BSL\n"
    before_tree = editor.xml_read(before_repair, f"{{{editor.FORM}}}Form")
    for form_tree in (before_tree, before_tree.find("f:BaseForm", editor.NS)):
        for node in form_tree.findall(".//f:CommandName", editor.NS):
            node.text = "0"
    assert editor.signature(repaired) == editor.signature(before_tree)
    assert editor.plan_make(editor.Snapshot(target), repair_request)["writes"] == []

    # A command changed independently is not silently normalized.
    repaired.find(".//f:CommandName", editor.NS).text = "Custom.Command"
    borrowed_path.write_bytes(editor.serialize_like(repaired, borrowed_path.read_bytes()))
    conflict_before = borrowed_path.read_bytes()
    with pytest.raises(editor.Rejected, match="binding changed"):
        editor.plan_make(editor.Snapshot(target), repair_request)
    assert borrowed_path.read_bytes() == conflict_before


@pytest.mark.parametrize("form_roots", ["owner"], indirect=True)
def test_form_borrow_explicit_native_main_attribute_projection_repeatplan(form_roots):
    source, target, stem, operation = form_roots
    source_path = source / stem / "Ext/Form.xml"
    source_bytes = source_path.read_bytes()
    form = editor.xml_read(source_bytes, f"{{{editor.FORM}}}Form")
    attributes = form.find("f:Attributes", editor.NS)
    main = etree.SubElement(attributes, f"{{{editor.FORM}}}Attribute", name="Объект", id="1")
    typed = etree.SubElement(main, f"{{{editor.FORM}}}Type")
    etree.SubElement(typed, f"{{{editor.V8}}}Type").text = "cfg:DataProcessorObject.Владелец"
    etree.SubElement(main, f"{{{editor.FORM}}}MainAttribute").text = "true"
    etree.SubElement(main, f"{{{editor.FORM}}}SavedData").text = "true"
    use_always = etree.SubElement(main, f"{{{editor.FORM}}}UseAlways")
    etree.SubElement(use_always, f"{{{editor.FORM}}}Field", id="71").text = "Объект"
    source_path.write_bytes(editor.serialize_like(form, source_bytes))

    borrowed_path = target / stem / "Ext/Form.xml"
    initial = editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [operation]})
    assert editor.apply(target, None, initial) == "applied"
    borrowed = editor.xml_read(borrowed_path.read_bytes(), f"{{{editor.FORM}}}Form")
    # Model a pre-projection adopted form with user-owned edits and an old main ID.
    etree.SubElement(
        borrowed.find("f:Attributes", editor.NS), f"{{{editor.FORM}}}Attribute", name="ЛокальныйРеквизит", id="1000000"
    )
    events = etree.SubElement(borrowed, f"{{{editor.FORM}}}Events")
    etree.SubElement(events, f"{{{editor.FORM}}}Event", name="OnOpen").text = "LocalHandler"
    borrowed_path.write_bytes(editor.serialize_like(borrowed, borrowed_path.read_bytes()))
    module_path = target / stem / "Ext/Form/Module.bsl"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_bytes(b"// local module\n")
    request = {
        "schemaVersion": 1,
        "operations": [
            {
                **operation,
                "parameters": {**operation["parameters"], "repairNativeMainAttributeProjection": True},
            }
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert [write["path"] for write in plan["writes"]] == [stem + "/Ext/Form.xml"]
    assert editor.apply(target, None, plan) == "applied"
    assert editor.verify_plan(target, plan)[0] == "after"
    borrowed = editor.xml_read(borrowed_path.read_bytes(), f"{{{editor.FORM}}}Form")
    for root in (borrowed, borrowed.find("f:BaseForm", editor.NS)):
        mains = borrow._native_main_attributes(root)
        assert len(mains) == 1 and mains[0].get("id") == "1000001"
    repaired_main = borrow._native_main_attributes(borrowed)[0]
    assert repaired_main.find("f:UseAlways/f:Field", editor.NS).get("id") == "71"
    local_attribute = next(
        node
        for node in borrowed.findall("f:Attributes/f:Attribute", editor.NS)
        if node.get("name") == "ЛокальныйРеквизит"
    )
    assert local_attribute.get("id") == "1000000"
    assert borrowed.findtext("f:Events/f:Event", namespaces=editor.NS) == "LocalHandler"
    assert module_path.read_bytes() == b"// local module\n"
    repeat = editor.plan_make(editor.Snapshot(target), request)
    assert repeat["writes"] == []
    assert module_path.read_bytes() == b"// local module\n"

    # A changed child ID belongs to the main attribute's source definition and conflicts.
    repaired_main.find("f:UseAlways/f:Field", editor.NS).set("id", "72")
    borrowed_path.write_bytes(editor.serialize_like(borrowed, borrowed_path.read_bytes()))
    with pytest.raises(editor.Rejected, match="Main attribute properties changed"):
        editor.plan_make(editor.Snapshot(target), request)
    repaired_main.find("f:UseAlways/f:Field", editor.NS).set("id", "71")
    etree.SubElement(
        borrowed.find("f:ChildItems", editor.NS),
        f"{{{editor.FORM}}}UsualGroup",
        name="ConflictingElement",
        id="1000001",
    )
    borrowed_path.write_bytes(editor.serialize_like(borrowed, borrowed_path.read_bytes()))
    with pytest.raises(editor.Rejected, match="collides with another form element"):
        editor.plan_make(editor.Snapshot(target), request)


@pytest.mark.parametrize("form_roots", ["owner"], indirect=True)
def test_form_registration_precedes_adopted_owner_command(form_roots):
    source, target, stem, operation = form_roots
    owner_request = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.borrow", "target": "DataProcessor.Владелец", "parameters": {"baseRoot": str(source)}}
        ],
    }
    assert editor.apply(target, None, editor.plan_make(editor.Snapshot(target), owner_request)) == "applied"
    path = target / "DataProcessors/Владелец.xml"
    data = path.read_bytes()
    root = editor.xml_read(data, f"{{{editor.MD}}}MetaDataObject")
    owner = root.find("m:DataProcessor", editor.NS)
    children = owner.find("m:ChildObjects", editor.NS)
    if children is None:
        children = etree.SubElement(owner, f"{{{editor.MD}}}ChildObjects")
    command = etree.SubElement(children, f"{{{editor.MD}}}Command", uuid=str(uuid.uuid4()))
    props = etree.SubElement(command, f"{{{editor.MD}}}Properties")
    etree.SubElement(props, f"{{{editor.MD}}}Name").text = "Команда"
    path.write_bytes(editor.serialize_like(root, data))
    plan = editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [operation]})
    assert editor.apply(target, None, plan) == "applied"
    owner = editor.metadata(path.read_bytes(), "DataProcessor")
    order = [
        etree.QName(child).localname for child in owner.find("m:ChildObjects", editor.NS) if isinstance(child.tag, str)
    ]
    assert order[-2:] == ["Form", "Command"]


def test_form_borrow_selected_commands_repairs_partial_projection(form_roots):
    source, target, stem, operation = form_roots
    source_path = source / (stem + "/Ext/Form.xml")
    source_form = editor.xml_read(source_path.read_bytes(), f"{{{editor.FORM}}}Form")
    commands = source_form.find("f:Commands", editor.NS)
    if commands is None:
        commands = etree.SubElement(source_form, f"{{{editor.FORM}}}Commands")
    for name, command_id in [("ChosenCommand", "20"), ("OtherCommand", "21")]:
        command = etree.SubElement(commands, f"{{{editor.FORM}}}Command", name=name, id=command_id)
        etree.SubElement(command, f"{{{editor.FORM}}}Action").text = name
    events = etree.SubElement(source_form, f"{{{editor.FORM}}}Events")
    etree.SubElement(events, f"{{{editor.FORM}}}Event", name="OnOpen").text = "BaseOpen"
    source_path.write_bytes(editor.serialize_like(source_form, source_path.read_bytes()))

    initial = editor.Snapshot(target)
    borrow.borrow_form(initial, operation)
    persist_for_next_snapshot(initial)

    target_path = target / (stem + "/Ext/Form.xml")
    module_path = target / (stem + "/Ext/Form/Module.bsl")
    module_before = module_path.read_bytes()
    target_form = editor.xml_read(target_path.read_bytes(), f"{{{editor.FORM}}}Form")
    untouched_before = editor.signature(target_form.find(".//*[@name='Existing']", editor.NS))
    for path in ("f:Commands", "f:BaseForm/f:Commands"):
        container = target_form.find(path, editor.NS)
        container.getparent().remove(container)
    target_path.write_bytes(editor.serialize_like(target_form, target_path.read_bytes()))

    request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.borrow",
                "target": operation["target"],
                "parameters": {"baseRoot": str(source), "commands": ["ChosenCommand"], "inheritEvents": ["OnOpen"]},
            }
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert {item["path"] for item in plan["writes"]} == {stem + "/Ext/Form.xml"}
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []

    result = editor.xml_read(target_path.read_bytes(), f"{{{editor.FORM}}}Form")
    for path in ("f:Commands", "f:BaseForm/f:Commands"):
        command = result.find(path + "/f:Command[@name='ChosenCommand']", editor.NS)
        assert command is not None and command.get("id") == "20"
        assert command.find("f:Action", editor.NS) is None
    assert result.find("f:Events/f:Event[@name='OnOpen']", editor.NS) is None
    assert result.find("f:BaseForm/f:Events/f:Event[@name='OnOpen']", editor.NS) is None
    assert module_path.read_bytes() == module_before
    assert editor.signature(result.find(".//*[@name='Existing']", editor.NS)) == untouched_before

    missing = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.borrow",
                "target": operation["target"],
                "parameters": {"baseRoot": str(source), "commands": ["MissingCommand"]},
            }
        ],
    }
    with pytest.raises(editor.Rejected, match="Selected base form command is missing"):
        editor.plan_make(editor.Snapshot(target), missing)

    clean = target_path.read_bytes()
    conflict_id = editor.xml_read(clean, f"{{{editor.FORM}}}Form")
    commands = conflict_id.find("f:Commands", editor.NS)
    etree.SubElement(commands, f"{{{editor.FORM}}}Command", name="ConflictingName", id="21")
    target_path.write_bytes(editor.serialize_like(conflict_id, clean))
    conflict = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.borrow",
                "target": operation["target"],
                "parameters": {"baseRoot": str(source), "commands": ["OtherCommand"]},
            }
        ],
    }
    with pytest.raises(editor.Rejected, match="Conflicting existing form command ID"):
        editor.plan_make(editor.Snapshot(target), conflict)

    conflict_content = editor.xml_read(clean, f"{{{editor.FORM}}}Form")
    commands = conflict_content.find("f:Commands", editor.NS)
    different = etree.SubElement(commands, f"{{{editor.FORM}}}Command", name="OtherCommand", id="21")
    title = etree.SubElement(different, f"{{{editor.FORM}}}Title")
    item = etree.SubElement(title, f"{{{editor.V8}}}item")
    etree.SubElement(item, f"{{{editor.V8}}}lang").text = "ru"
    etree.SubElement(item, f"{{{editor.V8}}}content").text = "different"
    target_path.write_bytes(editor.serialize_like(conflict_content, clean))
    with pytest.raises(editor.Rejected, match="Conflicting existing form command"):
        editor.plan_make(editor.Snapshot(target), conflict)


def test_form_borrow_inherit_events_removes_exact_projection_only(form_roots):
    source, target, stem, operation = form_roots
    source_path = source / (stem + "/Ext/Form.xml")
    source_bytes = source_path.read_bytes()
    source_form = editor.xml_read(source_bytes, f"{{{editor.FORM}}}Form")
    events = source_form.find("f:Events", editor.NS)
    if events is None:
        events = etree.SubElement(source_form, f"{{{editor.FORM}}}Events")
    for name, handler in [("OnOpen", "BaseOpen"), ("OnCreateAtServer", "BaseCreate")]:
        etree.SubElement(events, f"{{{editor.FORM}}}Event", name=name).text = handler
    source_path.write_bytes(editor.serialize_like(source_form, source_bytes))

    initial = editor.Snapshot(target)
    borrow.borrow_form(initial, operation)
    persist_for_next_snapshot(initial)
    target_path = target / (stem + "/Ext/Form.xml")
    module_path = target / (stem + "/Ext/Form/Module.bsl")
    module_bytes = b"// extension module\r\n"
    module_path.write_bytes(module_bytes)
    target_bytes = target_path.read_bytes()
    target_form = editor.xml_read(target_bytes, f"{{{editor.FORM}}}Form")
    base = target_form.find("f:BaseForm", editor.NS)
    root_events = etree.SubElement(target_form, f"{{{editor.FORM}}}Events")
    for name, handler in [("OnOpen", "BaseOpen"), ("OnCreateAtServer", "BaseCreate"), ("OnClose", "CustomClose")]:
        etree.SubElement(root_events, f"{{{editor.FORM}}}Event", name=name).text = handler
    base_events = etree.SubElement(base, f"{{{editor.FORM}}}Events")
    for name, handler in [("OnOpen", "BaseOpen"), ("OnCreateAtServer", "BaseCreate")]:
        etree.SubElement(base_events, f"{{{editor.FORM}}}Event", name=name).text = handler
    target_path.write_bytes(editor.serialize_like(target_form, target_bytes))

    request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "form.borrow",
                "target": operation["target"],
                "parameters": {"baseRoot": str(source), "inheritEvents": ["OnOpen", "OnCreateAtServer"]},
            }
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert {item["path"] for item in plan["writes"]} == {stem + "/Ext/Form.xml"}
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []
    result = editor.xml_read(target_path.read_bytes(), f"{{{editor.FORM}}}Form")
    assert result.find("f:Events/f:Event[@name='OnOpen']", editor.NS) is None
    assert result.find("f:Events/f:Event[@name='OnCreateAtServer']", editor.NS) is None
    assert result.find("f:Events/f:Event[@name='OnClose']", editor.NS) is not None
    assert result.find("f:BaseForm/f:Events/f:Event[@name='OnOpen']", editor.NS) is None
    assert result.find("f:BaseForm/f:Events/f:Event[@name='OnCreateAtServer']", editor.NS) is None
    assert module_path.read_bytes() == module_bytes

    clean = target_path.read_bytes()
    conflict_form = editor.xml_read(clean, f"{{{editor.FORM}}}Form")
    conflict_events = conflict_form.find("f:Events", editor.NS)
    etree.SubElement(conflict_events, f"{{{editor.FORM}}}Event", name="OnOpen", callType="After").text = "ExtensionOpen"
    target_path.write_bytes(editor.serialize_like(conflict_form, clean))
    with pytest.raises(editor.Rejected, match="Conflicting existing inherited form event"):
        editor.plan_make(editor.Snapshot(target), request)


def test_module_only_borrow_preserves_sparse_form_and_existing_module(form_roots):
    source, target, stem, operation = form_roots
    path, module = stem + "/Ext/Form.xml", stem + "/Ext/Form/Module.bsl"
    form = etree.fromstring((source / path).read_bytes())
    form.set("version", "2.20")
    etree.SubElement(form, f"{{{editor.FORM}}}UnknownLayoutProperty").text = "do not copy"
    (source / path).write_bytes(etree.tostring(form))
    before = {p: p.read_bytes() for p in source.rglob("*") if p.is_file()}
    request = {"schemaVersion": 1, "operations": [operation]}
    with pytest.raises(editor.Rejected, match="format differs"):
        editor.plan_make(editor.Snapshot(target), request)
    operation["parameters"]["moduleOnly"] = True
    if operation["target"].startswith("DataProcessor."):
        owner_request = {
            "schemaVersion": 1,
            "operations": [
                {"op": "object.borrow", "target": "DataProcessor.Владелец", "parameters": {"baseRoot": str(source)}}
            ],
        }
        editor.apply(target, None, editor.plan_make(editor.Snapshot(target), owner_request))
    (target / module).parent.mkdir(parents=True)
    (target / module).write_bytes(b"// preserve extension module\n")
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert editor.apply(target, None, plan) == "applied"
    delta = etree.fromstring((target / path).read_bytes())
    assert delta.get("version") == "2.17"
    assert [etree.QName(child).localname for child in delta] == ["BaseForm"]
    assert len(delta[0]) == 0 and delta[0].get("version") == "2.17"
    repeat = editor.plan_make(editor.Snapshot(target), request)
    assert repeat["writes"] == []
    assert (target / module).read_bytes() == b"// preserve extension module\n"
    assert before == {p: p.read_bytes() for p in source.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "fault",
    ["base-changed", "wrong-link", "orphan", "ordinary", "case-registration", "ambiguous-container", "format-mismatch"],
)
def test_form_borrow_rejects_conflicting_or_unsupported_source(form_roots, fault):
    source, target, stem, operation = form_roots
    request = {"schemaVersion": 1, "operations": [operation]}
    if fault == "format-mismatch":
        path = source / stem / "Ext/Form.xml"
        form = etree.fromstring(path.read_bytes())
        form.set("version", "2.20")
        path.write_bytes(etree.tostring(form))
    if fault in {"base-changed", "wrong-link"}:
        editor.apply(target, None, editor.plan_make(editor.Snapshot(target), request))
    if fault == "base-changed":
        path = source / stem / "Ext/Form.xml"
        form = editor.xml_read(path.read_bytes(), f"{{{editor.FORM}}}Form")
        form.find("f:AutoCommandBar/f:Autofill", editor.NS).text = "true"
        path.write_bytes(editor.serialize_like(form, path.read_bytes()))
    elif fault == "orphan":
        path = target / stem / "Ext/Form/Module.bsl"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"// preserve")
    elif fault in {"case-registration", "ambiguous-container"}:
        common = operation["target"].startswith("CommonForm.")
        path = source / ("Configuration.xml" if common else "DataProcessors/Владелец.xml")
        owner = editor.metadata(path.read_bytes(), "Configuration" if common else "DataProcessor")
        if fault == "case-registration":
            etree.SubElement(
                owner.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}" + ("CommonForm" if common else "Form")
            ).text = "ФОРМА"
        else:
            etree.SubElement(owner, f"{{{editor.MD}}}ChildObjects")
        path.write_bytes(editor.serialize_like(owner.getparent(), path.read_bytes()))
    elif fault in {"wrong-link", "ordinary"}:
        path = (target if fault == "wrong-link" else source) / (stem + ".xml")
        node = editor.xml_read(path.read_bytes(), f"{{{editor.MD}}}MetaDataObject")[0]
        key = "ExtendedConfigurationObject" if fault == "wrong-link" else "FormType"
        node.find(f"m:Properties/m:{key}", editor.NS).text = str(uuid.uuid4()) if fault == "wrong-link" else "Ordinary"
        path.write_bytes(editor.serialize_like(node.getparent(), path.read_bytes()))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), request)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


def section_request(source):
    return {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "tabular-section.borrow",
                "target": "DataProcessor.Владелец.TabularSection.Строки",
                "parameters": {"baseRoot": str(source)},
            }
        ],
    }


@pytest.fixture
def section_roots(roots):
    source, target = roots
    path = source / "DataProcessors/Владелец.xml"
    tree = editor.xml_read(path.read_bytes(), f"{{{editor.MD}}}MetaDataObject")
    owner = tree.find("m:DataProcessor", editor.NS)
    children = owner.find("m:ChildObjects", editor.NS)
    if children is None:
        children = etree.SubElement(owner, f"{{{editor.MD}}}ChildObjects")
    section = etree.SubElement(children, f"{{{editor.MD}}}TabularSection", uuid=str(uuid.uuid4()))
    internal = etree.SubElement(section, f"{{{editor.MD}}}InternalInfo")
    for category in ("TabularSection", "TabularSectionRow"):
        generated = etree.SubElement(
            internal,
            f"{{{borrow.XR}}}GeneratedType",
            name="DataProcessor" + category + ".Владелец.Строки",
            category=category,
        )
        for role in ("TypeId", "ValueId"):
            etree.SubElement(generated, f"{{{borrow.XR}}}{role}").text = str(uuid.uuid4())
    properties = etree.SubElement(section, f"{{{editor.MD}}}Properties")
    etree.SubElement(properties, f"{{{editor.MD}}}Name").text = "Строки"
    attrs = etree.SubElement(section, f"{{{editor.MD}}}ChildObjects")
    attribute = etree.SubElement(attrs, f"{{{editor.MD}}}Attribute", uuid=str(uuid.uuid4()))
    properties = etree.SubElement(attribute, f"{{{editor.MD}}}Properties")
    etree.SubElement(properties, f"{{{editor.MD}}}Name").text = "ИсходныйРеквизит"
    path.write_bytes(etree.tostring(tree, encoding="UTF-8", xml_declaration=True))
    return source, target


def test_section_borrow_is_direct_empty_deterministic_and_preserves_repeat(section_roots):
    source, target = section_roots
    request = section_request(source)
    first = editor.plan_make(editor.Snapshot(target), request)
    second = editor.plan_make(editor.Snapshot(target), request)
    assert first == second
    assert editor.apply(target, None, first) == "applied"
    path = target / "DataProcessors/Владелец.xml"
    tree = etree.fromstring(path.read_bytes())
    owner = tree.find("m:DataProcessor", editor.NS)
    sections = owner.findall("m:ChildObjects/m:TabularSection", editor.NS)
    assert len(sections) == 1
    section = sections[0]
    assert len(section.find("m:ChildObjects", editor.NS)) == 0
    original = editor.metadata((source / "DataProcessors/Владелец.xml").read_bytes(), "DataProcessor")
    original_section = original.find("m:ChildObjects/m:TabularSection", editor.NS)
    assert editor.prop(section, "ExtendedConfigurationObject") == editor.identity(original_section)
    assert editor.identity(section) != editor.identity(original_section)
    assert len(section.findall(f"m:InternalInfo/{{{borrow.XR}}}GeneratedType", editor.NS)) == 2
    attribute = etree.SubElement(
        section.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}Attribute", uuid=str(uuid.uuid4())
    )
    props = etree.SubElement(attribute, f"{{{editor.MD}}}Properties")
    etree.SubElement(props, f"{{{editor.MD}}}Name").text = "СобственныйРеквизит"
    path.write_bytes(etree.tostring(tree, encoding="UTF-8"))
    before = path.read_bytes()
    repeat = editor.plan_make(editor.Snapshot(target), request)
    assert repeat["writes"] == []
    assert editor.apply(target, None, repeat) == "already-applied"
    assert path.read_bytes() == before


@pytest.mark.parametrize("fault", ["wrong-link", "duplicate", "missing", "case"])
def test_section_conflicts_do_not_write(section_roots, fault):
    source, target = section_roots
    request = section_request(source)
    plan = editor.plan_make(editor.Snapshot(target), request)
    editor.apply(target, None, plan)
    path = (source if fault in {"missing", "case"} else target) / "DataProcessors/Владелец.xml"
    tree = etree.fromstring(path.read_bytes())
    section = tree.find("m:DataProcessor/m:ChildObjects/m:TabularSection", editor.NS)
    if fault == "wrong-link":
        section.find("m:Properties/m:ExtendedConfigurationObject", editor.NS).text = str(uuid.uuid4())
    elif fault == "duplicate":
        import copy

        section.getparent().append(copy.deepcopy(section))
    elif fault == "missing":
        section.getparent().remove(section)
    else:
        section.find("m:Properties/m:Name", editor.NS).text = "СТРОКИ"
    path.write_bytes(etree.tostring(tree, encoding="UTF-8"))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), request)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


@pytest.fixture
def dependency_form(section_roots):
    source, target = section_roots
    namespaces = {None: editor.MD, "v8": editor.V8, "xs": editor.XS, "cfg": borrow.CFG, "xr": borrow.XR}

    def attribute(parent, name, value):
        node = etree.SubElement(parent, f"{{{editor.MD}}}Attribute", uuid=str(uuid.uuid4()))
        props = etree.SubElement(node, f"{{{editor.MD}}}Properties")
        etree.SubElement(props, f"{{{editor.MD}}}Name").text = name
        typed = etree.SubElement(props, f"{{{editor.MD}}}Type")
        etree.SubElement(typed, f"{{{editor.V8}}}Type").text = value
        return node

    config_path = source / "Configuration.xml"
    config = etree.fromstring(config_path.read_bytes())
    registrations = config.find("m:Configuration/m:ChildObjects", editor.NS)
    for kind, name in [("Catalog", "Предметы"), ("Enum", "Режимы"), ("CommonPicture", "Значок"), ("StyleItem", "Цвет")]:
        root = etree.Element(f"{{{editor.MD}}}MetaDataObject", nsmap=namespaces, version="2.17")
        owner = etree.SubElement(root, f"{{{editor.MD}}}{kind}", uuid=str(uuid.uuid4()))
        props = etree.SubElement(owner, f"{{{editor.MD}}}Properties")
        etree.SubElement(props, f"{{{editor.MD}}}Name").text = name
        children = etree.SubElement(owner, f"{{{editor.MD}}}ChildObjects")
        if kind == "Catalog":
            attribute(children, "Артикул", "xs:string")
        if kind == "Enum":
            value = etree.SubElement(children, f"{{{editor.MD}}}EnumValue", uuid=str(uuid.uuid4()))
            value_props = etree.SubElement(value, f"{{{editor.MD}}}Properties")
            etree.SubElement(value_props, f"{{{editor.MD}}}Name").text = "Первый"
        path = source / borrow.DIRECTORIES[kind] / (name + ".xml")
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(etree.tostring(root, encoding="UTF-8"))
        etree.SubElement(registrations, f"{{{editor.MD}}}{kind}").text = name
    config_path.write_bytes(etree.tostring(config, encoding="UTF-8"))
    path = source / "DataProcessors/Владелец.xml"
    root = etree.fromstring(path.read_bytes())
    children = root.find("m:DataProcessor/m:ChildObjects", editor.NS)
    attribute(children, "НеИспользуется", "xs:boolean")
    attribute(children, "Режим", "cfg:EnumRef.Режимы")
    section = children.find("m:TabularSection/m:ChildObjects", editor.NS)
    props = section.find("m:Attribute/m:Properties", editor.NS)
    typed = etree.SubElement(props, f"{{{editor.MD}}}Type")
    etree.SubElement(typed, f"{{{editor.V8}}}Type").text = "xs:string"
    attribute(section, "Предмет", "cfg:CatalogRef.Предметы")
    path.write_bytes(etree.tostring(root, encoding="UTF-8"))
    form = etree.fromstring(
        (
            '''<Form xmlns="'''
            + editor.FORM
            + '''" xmlns:cfg="'''
            + borrow.CFG
            + '''"
        xmlns:v8="'''
            + editor.V8
            + '''" xmlns:xs="'''
            + editor.XS
            + '''" xmlns:xr="'''
            + borrow.XR
            + '''"
        xmlns:style="'''
            + borrow.STYLE
            + """" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.17">
        <ChildItems><InputField name="Предмет" id="1"><DataPath>Объект.Строки.Предмет.Артикул</DataPath>
        <Picture><xr:Ref>CommonPicture.Значок</xr:Ref></Picture><TextColor>style:Цвет</TextColor></InputField>
        <InputField name="Расчетное" id="2"><DataPath>Объект.Строки.Расчетное</DataPath></InputField></ChildItems>
        <Attributes><Attribute name="Объект" id="1"><Type><v8:Type>cfg:DataProcessorObject.Владелец</v8:Type></Type>
        <MainAttribute>true</MainAttribute><UseAlways><Field>Объект.Режим</Field></UseAlways>
        <Columns><AdditionalColumns table="Объект.Строки"><Column name="Расчетное"><Type><v8:Type>xs:decimal</v8:Type>
        </Type></Column></AdditionalColumns></Columns></Attribute></Attributes>
        <Value xsi:type="xr:DesignTimeRef">Enum.Режимы.EnumValue.Первый</Value>
        </Form>"""
        ).encode("utf-8")
    )
    return source, target, form


@pytest.mark.parametrize("mode", ["Form", "All"])
def test_form_dependencies_preserve_xml_and_resolve_deep_and_virtual_columns(dependency_form, mode):
    source, target, form = dependency_form
    before = etree.tostring(form)
    snapshot = editor.Snapshot(target)
    resolved = borrow.borrow_form_dependencies(snapshot, source, "DataProcessor.Владелец", form, mode)
    assert resolved == [
        "Catalog.Предметы",
        "CommonPicture.Значок",
        "DataProcessor.Владелец",
        "Enum.Режимы",
        "StyleItem.Цвет",
    ]
    assert etree.tostring(form) == before
    assert not (target / "DataProcessors").exists()
    owner = editor.metadata(present(snapshot.read("target", "DataProcessors/Владелец.xml")), "DataProcessor")
    assert (borrow._member(owner, "Attribute", "НеИспользуется", optional=True) is not None) == (mode == "All")
    section = borrow._member(owner, "TabularSection", "Строки")
    assert borrow._member(section, "Attribute", "Расчетное", optional=True) is None
    reference = borrow._member(section, "Attribute", "Предмет")
    typed = present(reference).find("m:Properties/m:Type/v8:Type", editor.NS)
    assert typed.text == "cfg:CatalogRef.Предметы" and typed.nsmap["cfg"] == borrow.CFG
    catalog = editor.metadata(present(snapshot.read("target", "Catalogs/Предметы.xml")), "Catalog")
    assert borrow._member(catalog, "Attribute", "Артикул") is not None
    enum = editor.metadata(present(snapshot.read("target", "Enums/Режимы.xml")), "Enum")
    assert borrow._member(enum, "EnumValue", "Первый") is not None
    persist_for_next_snapshot(snapshot)
    again = editor.Snapshot(target)
    borrow.borrow_form_dependencies(again, source, "DataProcessor.Владелец", form, mode)
    assert again.writes == {}


def test_form_empty_enum_reference_preserves_xml_and_identity(dependency_form):
    source, target, form = dependency_form
    form.find("f:Value", editor.NS).text = "Enum.Режимы.EmptyRef"
    before = etree.tostring(form)
    snapshot = editor.Snapshot(target)
    borrow.borrow_form_dependencies(snapshot, source, "DataProcessor.Владелец", form)
    enum = editor.metadata(present(snapshot.read("target", "Enums/Режимы.xml")), "Enum")
    assert borrow._member(enum, "EnumValue", "Первый", optional=True) is None
    assert etree.tostring(form) == before
    persist_for_next_snapshot(snapshot)
    again = editor.Snapshot(target)
    borrow.borrow_form_dependencies(again, source, "DataProcessor.Владелец", form)
    assert again.writes == {}


def test_form_generic_document_ref_typeset_is_preserved_and_unknown_bare_family_rejected(dependency_form):
    source, target, form = dependency_form
    attribute = etree.SubElement(
        form.find("f:Attributes", editor.NS), f"{{{editor.FORM}}}Attribute", name="РасшифровкаПлатежаСделка", id="4"
    )
    typed = etree.SubElement(attribute, f"{{{editor.FORM}}}Type")
    type_set = etree.SubElement(typed, f"{{{editor.V8}}}TypeSet")
    type_set.text = "cfg:DocumentRef"
    original_form = etree.tostring(form)

    snapshot = editor.Snapshot(target)
    borrow.borrow_form_dependencies(snapshot, source, "DataProcessor.Владелец", form)
    assert etree.tostring(form) == original_form

    type_set.text = "cfg:UnknownRef"
    with pytest.raises(editor.Rejected, match="Unsupported metadata type: cfg:UnknownRef"):
        borrow.borrow_form_dependencies(editor.Snapshot(target), source, "DataProcessor.Владелец", form)


def test_form_type_link_resolves_chart_reference_and_rejects_item_outside_maximum(dependency_form):
    source, target, form = dependency_form
    chart_name = "ТестовыйПланСчетов"
    config_path = source / "Configuration.xml"
    config_bytes = config_path.read_bytes()
    config_root = editor.xml_read(config_bytes, f"{{{editor.MD}}}MetaDataObject")
    config = config_root.find(f"{{{editor.MD}}}Configuration")
    config_id = editor.identity(config)
    etree.SubElement(config.find(f"{{{editor.MD}}}ChildObjects"), f"{{{editor.MD}}}ChartOfAccounts").text = chart_name
    config_path.write_bytes(editor.serialize_like(config_root, config_bytes))
    chart_path = source / f"ChartsOfAccounts/{chart_name}.xml"
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.write_bytes(
        create.render_object(
            {
                "type": "ChartOfAccounts",
                "name": chart_name,
                "maxExtDimensionCount": 2,
            },
            config_id,
            {},
        )
    )

    attributes = form.find(f"{{{editor.FORM}}}Attributes")
    account = etree.SubElement(attributes, f"{{{editor.FORM}}}Attribute", name="СчетУчета", id="3")
    typed = etree.SubElement(account, f"{{{editor.FORM}}}Type")
    etree.SubElement(typed, f"{{{editor.V8}}}Type").text = f"cfg:ChartOfAccountsRef.{chart_name}"
    control = form.find('.//f:InputField[@name="Расчетное"]', editor.NS)
    link = etree.SubElement(control, f"{{{editor.FORM}}}TypeLink")
    etree.SubElement(link, f"{{{borrow.XR}}}DataPath").text = "СчетУчета"
    link_item = etree.SubElement(link, f"{{{borrow.XR}}}LinkItem")
    link_item.text = "2"
    original_form = etree.tostring(form)

    snapshot = editor.Snapshot(target)
    dependencies = borrow.borrow_form_dependencies(snapshot, source, "DataProcessor.Владелец", form)
    assert f"ChartOfAccounts.{chart_name}" in dependencies
    assert etree.tostring(form) == original_form
    base_chart = editor.metadata((source / f"ChartsOfAccounts/{chart_name}.xml").read_bytes(), "ChartOfAccounts")
    assert editor.prop(base_chart, "MaxExtDimensionCount") == "2"
    snapshot.unchanged()

    link_item.text = "3"
    with pytest.raises(editor.Rejected, match="TypeLink item exceeds chart extra-dimension count"):
        borrow.borrow_form_dependencies(editor.Snapshot(target), source, "DataProcessor.Владелец", form)

    link_item.text = "2"
    typed.find(f"{{{editor.V8}}}Type").text = f"cfg:ChartOfAccountsObject.{chart_name}"
    with pytest.raises(editor.Rejected, match="Unsupported TypeLink data type"):
        borrow.borrow_form_dependencies(editor.Snapshot(target), source, "DataProcessor.Владелец", form)


def test_form_type_link_to_current_row_field_resolves_through_table_data_path(dependency_form):
    source, target, form = dependency_form
    table = etree.SubElement(form.find("f:ChildItems", editor.NS), f"{{{editor.FORM}}}Table", name="Строки", id="3")
    etree.SubElement(table, f"{{{editor.FORM}}}DataPath").text = "Объект.Строки"
    control = form.find('.//f:InputField[@name="Расчетное"]', editor.NS)
    link = etree.SubElement(control, f"{{{editor.FORM}}}TypeLink")
    path = etree.SubElement(link, f"{{{borrow.XR}}}DataPath")
    path.text = "Items.Строки.CurrentData.Расчетное"
    link_item = etree.SubElement(link, f"{{{borrow.XR}}}LinkItem")
    link_item.text = "0"
    original_form = etree.tostring(form)

    snapshot = editor.Snapshot(target)
    dependencies = borrow.borrow_form_dependencies(snapshot, source, "DataProcessor.Владелец", form)
    assert "Catalog.Предметы" in dependencies
    assert etree.tostring(form) == original_form
    persist_for_next_snapshot(snapshot)
    again = editor.Snapshot(target)
    borrow.borrow_form_dependencies(again, source, "DataProcessor.Владелец", form)
    assert again.writes == {}

    # The linked field is walked as a data path of the table rows.
    path.text = "Items.Строки.CurrentData.Отсутствует"
    with pytest.raises(editor.Rejected, match="Unresolved data path"):
        borrow.borrow_form_dependencies(editor.Snapshot(target), source, "DataProcessor.Владелец", form)
    for bad_path, bad_item, message in [
        ("Items.НетТакой.CurrentData.Расчетное", "0", "Unresolved TypeLink form item"),
        ("Items.Предмет.CurrentData.Расчетное", "0", "Unresolved TypeLink form item"),
        ("Items.Строки.CurrentData.Расчетное", "1", "Invalid TypeLink reference"),
        ("Items.Строки.Расчетное", "0", "Invalid TypeLink reference"),
    ]:
        path.text, link_item.text = bad_path, bad_item
        with pytest.raises(editor.Rejected, match=message):
            borrow.borrow_form_dependencies(editor.Snapshot(target), source, "DataProcessor.Владелец", form)


def _add_object_command(source, group):
    config_path = source / "Configuration.xml"
    config = etree.fromstring(config_path.read_bytes())
    registrations = config.find("m:Configuration/m:ChildObjects", editor.NS)
    root = etree.Element(f"{{{editor.MD}}}MetaDataObject", nsmap={None: editor.MD, "v8": editor.V8}, version="2.17")
    owner = etree.SubElement(root, f"{{{editor.MD}}}CommandGroup", uuid=str(uuid.uuid4()))
    etree.SubElement(etree.SubElement(owner, f"{{{editor.MD}}}Properties"), f"{{{editor.MD}}}Name").text = "Действия"
    path = source / borrow.DIRECTORIES["CommandGroup"] / "Действия.xml"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(etree.tostring(root, encoding="UTF-8"))
    etree.SubElement(registrations, f"{{{editor.MD}}}CommandGroup").text = "Действия"
    config_path.write_bytes(etree.tostring(config, encoding="UTF-8"))
    path = source / "Catalogs/Предметы.xml"
    root = etree.fromstring(path.read_bytes())
    children = root.find("m:Catalog/m:ChildObjects", editor.NS)
    command = etree.SubElement(children, f"{{{editor.MD}}}Command", uuid=str(uuid.uuid4()))
    props = etree.SubElement(command, f"{{{editor.MD}}}Properties")
    etree.SubElement(props, f"{{{editor.MD}}}Name").text = "Открыть"
    if group is not None:
        etree.SubElement(props, f"{{{editor.MD}}}Group").text = group
    etree.SubElement(props, f"{{{editor.MD}}}ModifiesData").text = "false"
    path.write_bytes(etree.tostring(root, encoding="UTF-8"))
    return command.get("uuid")


@pytest.mark.parametrize("group", ["CommandGroup.Действия", "FormNavigationPanelGoTo"])
def test_form_object_command_adopts_owner_command_and_group(dependency_form, group):
    source, target, form = dependency_form
    source_id = _add_object_command(source, group)
    interface = etree.SubElement(form, f"{{{editor.FORM}}}CommandInterface")
    item = etree.SubElement(
        etree.SubElement(etree.SubElement(interface, f"{{{editor.FORM}}}NavigationPanel"), f"{{{editor.FORM}}}Items"),
        f"{{{editor.FORM}}}Item",
    )
    etree.SubElement(item, f"{{{editor.FORM}}}Command").text = "Catalog.Предметы.Command.Открыть"
    original_form = etree.tostring(form)

    snapshot = editor.Snapshot(target)
    dependencies = borrow.borrow_form_dependencies(snapshot, source, "DataProcessor.Владелец", form)
    assert ("CommandGroup.Действия" in dependencies) == (group == "CommandGroup.Действия")
    assert etree.tostring(form) == original_form
    catalog = editor.metadata(present(snapshot.read("target", "Catalogs/Предметы.xml")), "Catalog")
    adopted = borrow._member(catalog, "Command", "Открыть")
    assert present(adopted).get("uuid") != source_id
    assert present(adopted).find("m:InternalInfo", editor.NS) is not None
    properties = present(adopted).find("m:Properties", editor.NS)
    assert [(etree.QName(child).localname, child.text) for child in properties] == [
        ("ObjectBelonging", "Adopted"),
        ("Name", "Открыть"),
        ("Comment", None),
        ("ExtendedConfigurationObject", source_id),
        ("Group", group),
    ]
    persist_for_next_snapshot(snapshot)
    again = editor.Snapshot(target)
    borrow.borrow_form_dependencies(again, source, "DataProcessor.Владелец", form)
    assert again.writes == {}


def test_form_object_command_rejects_missing_command_or_group(dependency_form):
    source, target, form = dependency_form
    _add_object_command(source, None)
    interface = etree.SubElement(form, f"{{{editor.FORM}}}CommandInterface")
    command = etree.SubElement(interface, f"{{{editor.FORM}}}Command")
    command.text = "Catalog.Предметы.Command.Открыть"
    with pytest.raises(editor.Rejected, match="Missing or ambiguous command Group"):
        borrow.borrow_form_dependencies(editor.Snapshot(target), source, "DataProcessor.Владелец", form)
    command.text = "Catalog.Предметы.Command.Нет"
    with pytest.raises(editor.Rejected, match="Missing or ambiguous Command.Нет"):
        borrow.borrow_form_dependencies(editor.Snapshot(target), source, "DataProcessor.Владелец", form)
    command.text = "Catalog.Предметы.Command"
    with pytest.raises(editor.Rejected, match="Unsupported metadata command"):
        borrow.borrow_form_dependencies(editor.Snapshot(target), source, "DataProcessor.Владелец", form)


@pytest.mark.parametrize("column", ["TotalПредмет", "TotalОтсутствует"])
def test_tabular_column_total_path_resolves_to_existing_attribute(dependency_form, column):
    source, target, form = dependency_form
    form.find('.//f:InputField[@name="Расчетное"]/f:DataPath', editor.NS).text = "Объект.Строки." + column
    snapshot = editor.Snapshot(target)
    if column == "TotalОтсутствует":
        with pytest.raises(editor.Rejected, match="Unresolved data path"):
            borrow.borrow_form_dependencies(snapshot, source, "DataProcessor.Владелец", form)
        return
    borrow.borrow_form_dependencies(snapshot, source, "DataProcessor.Владелец", form)
    owner = editor.metadata(present(snapshot.read("target", "DataProcessors/Владелец.xml")), "DataProcessor")
    assert borrow._member(borrow._member(owner, "TabularSection", "Строки"), "Attribute", "Предмет") is not None


@pytest.mark.parametrize(
    "fault",
    [
        "unknown-path",
        "missing-picture",
        "missing-value",
        "unknown-type",
        "unknown-namespace",
        "type-link",
        "wrong-standard",
        "duplicate-column",
    ],
)
def test_unresolved_form_dependencies_do_not_change_sources(dependency_form, fault):
    source, target, form = dependency_form
    if fault == "unknown-path":
        form.find(".//f:DataPath", editor.NS).text = "Объект.Отсутствует"
    elif fault == "missing-picture":
        form.find(f".//{{{borrow.XR}}}Ref").text = "CommonPicture.Отсутствует"
    elif fault == "missing-value":
        form.find("f:Value", editor.NS).text = "Enum.Режимы.EnumValue.Отсутствует"
    elif fault == "unknown-type":
        form.find(".//v8:Type", editor.NS).text = "cfg:UnknownType.Отсутствует"
    elif fault == "unknown-namespace":
        node = etree.SubElement(form, f"{{{editor.V8}}}Type", nsmap={"unknown": "urn:unknown"})
        node.text = "unknown:Type"
    elif fault == "type-link":
        link = etree.SubElement(form, f"{{{editor.FORM}}}TypeLink")
        etree.SubElement(link, f"{{{borrow.XR}}}DataPath").text = "Отсутствует"
    elif fault == "wrong-standard":
        form.find(".//f:DataPath", editor.NS).text = "Объект.LineNumber"
    else:
        import copy

        column = form.find(".//f:AdditionalColumns/f:Column", editor.NS)
        column.getparent().append(copy.deepcopy(column))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected):
        borrow.borrow_form_dependencies(editor.Snapshot(target), source, "DataProcessor.Владелец", form)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


@pytest.mark.parametrize("missing", [False, True])
def test_reference_path_without_main_attribute(dependency_form, missing):
    source, target, form = dependency_form
    attributes = form.find("f:Attributes", editor.NS)
    for node in list(attributes):
        attributes.remove(node)
    attribute = etree.SubElement(attributes, f"{{{editor.FORM}}}Attribute", name="Предмет", id="90")
    typed = etree.SubElement(attribute, f"{{{editor.FORM}}}Type")
    etree.SubElement(typed, f"{{{editor.V8}}}Type").text = "cfg:CatalogRef.Предметы"
    for node in form.iter():
        if node.tag in {f"{{{editor.FORM}}}DataPath", f"{{{editor.FORM}}}Field"}:
            node.text = "Предмет." + ("Отсутствует" if missing else "Артикул")
    snapshot = editor.Snapshot(target)
    if missing:
        with pytest.raises(editor.Rejected, match="Unresolved data path"):
            borrow.borrow_form_dependencies(snapshot, source, None, form)
    else:
        borrow.borrow_form_dependencies(snapshot, source, None, form)
        catalog = editor.metadata(present(snapshot.read("target", "Catalogs/Предметы.xml")), "Catalog")
        assert borrow._member(catalog, "Attribute", "Артикул") is not None
    assert not (target / "Catalogs").exists()


def test_selected_bp_goods_form_borrow_projection(roots):
    _fixture_source, target = roots
    source = designer_export("Documents/ПоступлениеТоваровУслуг/Forms/ФормаДокументаТовары/Ext/Form.xml")
    for file in target.rglob("*.xml"):
        tree = etree.fromstring(file.read_bytes())
        tree.set("version", "2.20")
        file.write_bytes(etree.tostring(tree))
    snapshot = editor.Snapshot(target)
    alias = snapshot.source_root(source)
    path = "Documents/ПоступлениеТоваровУслуг/Forms/ФормаДокументаТовары/Ext/Form.xml"
    form = editor.xml_read(present(snapshot.read(alias, path)), f"{{{editor.FORM}}}Form")
    before = etree.tostring(form)
    borrow.borrow_form(
        snapshot,
        {
            "op": "form.borrow",
            "target": "Document.ПоступлениеТоваровУслуг.Form.ФормаДокументаТовары",
            "parameters": {"baseRoot": str(source)},
        },
    )
    for dependency in [
        "Documents/ПоступлениеТоваровУслуг.xml",
        "Catalogs/Номенклатура.xml",
        "ChartsOfAccounts/Хозрасчетный.xml",
        "CommonPictures/ПрослеживаемыйТовар.xml",
        "CommonCommands/ПоказатьДвиженияДокумента.xml",
        "CommonCommands/СвязанныеДокументы.xml",
        "CommonCommands/ПрисоединенныеФайлыБП.xml",
        "CommonCommands/ДополнительныеСведенияКоманднаяПанель.xml",
        "CommonCommands/ИсторияИзменений.xml",
        "CommandGroups/Печать.xml",
        "Documents/ЗаявлениеОВвозеТоваров.xml",
    ]:
        assert dependency in snapshot.writes
    candidate = editor.xml_read(present(snapshot.read("target", path)), f"{{{editor.FORM}}}Form")
    base = candidate.find("f:BaseForm", editor.NS)
    assert candidate.get("version") == base.get("version") == "2.20"
    assert etree.tostring(form) == before
    for binding in form.xpath(".//f:Events | ./f:Commands/f:Command/f:Action", namespaces=editor.NS):
        binding.getparent().remove(binding)
    # These are the exact command references Designer normalized in the
    # successful native adopted-form probes, including the separate Help probe.
    native_command_refs = {
        "Form.StandardCommand.PostAndClose",
        "Form.StandardCommand.Post",
        "Form.StandardCommand.Reread",
        "Form.StandardCommand.CustomizeForm",
        "Form.StandardCommand.Help",
    }
    for command in form.findall(".//f:CommandName", editor.NS):
        if command.text in native_command_refs:
            command.text = "0"
    base.tag = form.tag
    assert editor.signature(base) == editor.signature(form)
    candidate.remove(base)
    assert editor.signature(candidate) == editor.signature(form)
    owner = editor.metadata(present(snapshot.read("target", "Documents/ПоступлениеТоваровУслуг.xml")), "Document")
    goods = borrow._member(owner, "TabularSection", "Товары")
    assert borrow._member(goods, "Attribute", "Всего", optional=True) is None
    assert borrow._member(owner, "TabularSection", "Услуги") is not None
    assert not (target / "Documents").exists()
    command_owner = editor.metadata(
        present(snapshot.read("target", "Documents/ЗаявлениеОВвозеТоваров.xml")), "Document"
    )
    assert editor.prop(command_owner, "UseStandardCommands") == "true"
    source_command = editor.metadata(present(snapshot.read(alias, "Documents/ЗаявлениеОВвозеТоваров.xml")), "Document")
    expected = etree.Element(f"{{{editor.MD}}}Properties", nsmap=command_owner.nsmap)
    import copy

    expected.append(copy.deepcopy(source_command.find("m:Properties/m:BasedOn", editor.NS)))
    assert editor.signature(command_owner.find("m:Properties/m:BasedOn", editor.NS)) == editor.signature(expected[0])
    snapshot.unchanged()


@pytest.mark.parametrize("cyclic", [False, True])
@pytest.mark.parametrize(
    "kind,family", [("DefinedType", "DefinedType"), ("ChartOfCharacteristicTypes", "Characteristic")]
)
def test_type_sets_are_followed_or_rejected_on_cycles(dependency_form, cyclic, kind, family):
    source, target, form = dependency_form
    config_path = source / "Configuration.xml"
    config = etree.fromstring(config_path.read_bytes())
    etree.SubElement(
        config.find("m:Configuration/m:ChildObjects", editor.NS), f"{{{editor.MD}}}{kind}"
    ).text = "Предмет"
    config_path.write_bytes(etree.tostring(config, encoding="UTF-8"))
    root = etree.Element(
        f"{{{editor.MD}}}MetaDataObject", version="2.17", nsmap={None: editor.MD, "cfg": borrow.CFG, "v8": editor.V8}
    )
    definition = etree.SubElement(root, f"{{{editor.MD}}}{kind}", uuid=str(uuid.uuid4()))
    properties = etree.SubElement(definition, f"{{{editor.MD}}}Properties")
    etree.SubElement(properties, f"{{{editor.MD}}}Name").text = "Предмет"
    typed = etree.SubElement(properties, f"{{{editor.MD}}}Type")
    etree.SubElement(typed, f"{{{editor.V8}}}" + ("TypeSet" if cyclic else "Type")).text = (
        f"cfg:{family}.Предмет" if cyclic else "cfg:CatalogRef.Предметы"
    )
    directory = source / borrow.DIRECTORIES[kind]
    directory.mkdir()
    (directory / "Предмет.xml").write_bytes(etree.tostring(root, encoding="UTF-8"))
    path = source / "DataProcessors/Владелец.xml"
    owner = etree.fromstring(path.read_bytes())
    section = owner.find("m:DataProcessor/m:ChildObjects/m:TabularSection", editor.NS)
    attribute = borrow._member(section, "Attribute", "Предмет")
    value = present(attribute).find("m:Properties/m:Type/v8:Type", editor.NS)
    value.tag, value.text = f"{{{editor.V8}}}TypeSet", f"cfg:{family}.Предмет"
    path.write_bytes(etree.tostring(owner, encoding="UTF-8"))
    snapshot = editor.Snapshot(target)
    if cyclic:
        with pytest.raises(editor.Rejected, match="Cyclic type set"):
            borrow.borrow_form_dependencies(snapshot, source, "DataProcessor.Владелец", form)
    else:
        resolved = borrow.borrow_form_dependencies(snapshot, source, "DataProcessor.Владелец", form)
        assert kind + ".Предмет" in resolved
        catalog = editor.metadata(present(snapshot.read("target", "Catalogs/Предметы.xml")), "Catalog")
        assert borrow._member(catalog, "Attribute", "Артикул") is not None


def test_borrow_is_deterministic_stages_only_and_repeated_borrow_preserves_bsl(roots):
    source, target = roots
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    first, second = editor.Snapshot(target), editor.Snapshot(target)
    borrow.borrow_object(first, operation(source))
    borrow.borrow_object(second, operation(source))
    assert first.writes == second.writes
    assert set(first.writes) == {"Configuration.xml", "DataProcessors/Владелец.xml"}
    adopted = editor.metadata(present(first.writes["DataProcessors/Владелец.xml"]), "DataProcessor")
    base = editor.metadata((source / "DataProcessors/Владелец.xml").read_bytes(), "DataProcessor")
    assert editor.prop(adopted, "ObjectBelonging") == "Adopted"
    assert editor.prop(adopted, "ExtendedConfigurationObject") == editor.identity(base)
    assert editor.identity(adopted) != editor.identity(base)
    assert {p: p.read_bytes() for p in target.rglob("*") if p.is_file()} == before
    # Repeating in the ordered in-memory view must not replace its first shell.
    written = dict(first.writes)
    borrow.borrow_object(first, operation(source))
    assert first.writes == written
    persist_for_next_snapshot(first)
    module = target / "DataProcessors/Владелец/Ext/ObjectModule.bsl"
    module.parent.mkdir(parents=True)
    module.write_bytes(b"\xef\xbb\xbf// retain all module bytes\r\n")
    again = editor.Snapshot(target)
    borrow.borrow_object(again, operation(source))
    assert again.writes == {}
    assert module.read_bytes() == b"\xef\xbb\xbf// retain all module bytes\r\n"


def test_register_borrowed_object_requires_exact_adoption_and_is_idempotent(roots):
    source, target = roots
    kind, name = "Document", "РегламентнаяОперация"
    path = f"{borrow.DIRECTORIES[kind]}/{name}.xml"
    base_config_path = source / "Configuration.xml"
    base_config_bytes = base_config_path.read_bytes()
    base_config = editor.metadata(base_config_bytes, "Configuration")
    etree.SubElement(base_config.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}{kind}").text = name
    base_config_path.write_bytes(editor.serialize_like(base_config.getparent(), base_config_bytes))
    (source / borrow.DIRECTORIES[kind]).mkdir()
    (source / path).write_bytes(create.render_object({"type": kind, "name": name}, editor.identity(base_config), {}))
    source_before = {
        item.relative_to(source).as_posix(): item.read_bytes() for item in source.rglob("*") if item.is_file()
    }

    borrow_plan = editor.plan_make(
        editor.Snapshot(target), {"schemaVersion": 1, "operations": [operation(source, kind + "." + name)]}
    )
    assert editor.apply(target, None, borrow_plan) == "applied"
    target_descriptor = target / path
    descriptor_bytes = target_descriptor.read_bytes()
    config_path = target / "Configuration.xml"
    config_bytes = config_path.read_bytes()
    config = editor.metadata(config_bytes, "Configuration")
    registration = config.find("m:ChildObjects/m:Document", editor.NS)
    assert registration is not None and registration.text == name
    registration.getparent().remove(registration)
    config_path.write_bytes(editor.serialize_like(config.getparent(), config_bytes))
    request = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.register-borrowed", "target": kind + "." + name, "parameters": {"baseRoot": str(source)}}
        ],
    }

    plan = editor.plan_make(editor.Snapshot(target), request)
    assert [entry["path"] for entry in plan["writes"]] == ["Configuration.xml"]
    assert editor.apply(target, None, plan) == "applied"
    assert target_descriptor.read_bytes() == descriptor_bytes
    config = editor.metadata(config_path.read_bytes(), "Configuration")
    assert [(node.tag, node.text) for node in config.findall("m:ChildObjects/m:Document", editor.NS)] == [
        (f"{{{editor.MD}}}Document", name)
    ]
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []

    config_bytes = config_path.read_bytes()
    config = editor.metadata(config_bytes, "Configuration")
    config.find("m:ChildObjects/m:Document", editor.NS).getparent().remove(
        config.find("m:ChildObjects/m:Document", editor.NS)
    )
    config_path.write_bytes(editor.serialize_like(config.getparent(), config_bytes))
    adopted = editor.metadata(descriptor_bytes, kind)
    adopted.find("m:Properties/m:ExtendedConfigurationObject", editor.NS).text = str(uuid.uuid4())
    target_descriptor.write_bytes(editor.serialize_like(adopted.getparent(), descriptor_bytes))
    before = {item.relative_to(target).as_posix(): item.read_bytes() for item in target.rglob("*") if item.is_file()}
    with pytest.raises(editor.Rejected, match="Existing object has a conflicting base link"):
        editor.plan_make(editor.Snapshot(target), request)
    assert {
        item.relative_to(target).as_posix(): item.read_bytes() for item in target.rglob("*") if item.is_file()
    } == before

    target_descriptor.write_bytes(descriptor_bytes)
    target_descriptor.unlink()
    before = {item.relative_to(target).as_posix(): item.read_bytes() for item in target.rglob("*") if item.is_file()}
    with pytest.raises(editor.Rejected, match="Missing adopted object descriptor"):
        editor.plan_make(editor.Snapshot(target), request)
    assert {
        item.relative_to(target).as_posix(): item.read_bytes() for item in target.rglob("*") if item.is_file()
    } == before
    assert {
        item.relative_to(source).as_posix(): item.read_bytes() for item in source.rglob("*") if item.is_file()
    } == source_before


@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
@pytest.mark.parametrize("eol", [b"\n", b"\r\n"])
def test_borrow_preserves_configuration_encoding_and_noop_bytes(roots, bom, eol):
    source, target = roots
    path = target / "Configuration.xml"
    original = path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n").encode("utf-8")
    path.write_bytes(bom + original.replace(b"\n", eol))
    request = {"schemaVersion": 1, "operations": [operation(source)]}
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert editor.apply(target, None, plan) == "applied"
    result = path.read_bytes()
    assert result.startswith(b"\xef\xbb\xbf") == bool(bom)
    assert (b"\r\n" in result) == (eol == b"\r\n")
    assert eol != b"\r\n" or b"\n" not in result.replace(b"\r\n", b"")
    shell = (target / "DataProcessors/Владелец.xml").read_bytes()
    assert not shell.startswith(b"\xef\xbb\xbf") and b"\r" not in shell
    repeat = editor.plan_make(editor.Snapshot(target), request)
    assert repeat["writes"] == []
    assert editor.apply(target, None, repeat) == "already-applied"
    assert path.read_bytes() == result


@pytest.mark.parametrize("fault", ["mixed-eol", "dtd"])
def test_borrow_rejects_unsafe_xml_before_writing(roots, fault):
    source, target = roots
    path = target / "Configuration.xml"
    data = path.read_bytes()
    if fault == "mixed-eol":
        data = data.replace(b"\n", b"\r\n", 1) + b"\n"
    else:
        data = data.replace(b"<MetaDataObject", b"<!DOCTYPE MetaDataObject><MetaDataObject", 1)
    path.write_bytes(data)
    before = {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [operation(source)]})
    assert before == {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()}


@pytest.mark.parametrize("replacement", ["Native", "wrong-link"])
def test_existing_native_or_wrong_base_is_conflict_without_staging(roots, replacement):
    source, target = roots
    snapshot = editor.Snapshot(target)
    borrow.borrow_object(snapshot, operation(source))
    persist_for_next_snapshot(snapshot)
    path = target / "DataProcessors/Владелец.xml"
    node = editor.metadata(path.read_bytes(), "DataProcessor")
    key = "ObjectBelonging" if replacement == "Native" else "ExtendedConfigurationObject"
    node.find(f"m:Properties/m:{key}", editor.NS).text = replacement
    path.write_bytes(etree.tostring(node.getparent()))
    snapshot = editor.Snapshot(target)
    with pytest.raises(editor.Rejected, match="conflicting base link"):
        borrow.borrow_object(snapshot, operation(source))
    assert snapshot.writes == {}


@pytest.mark.parametrize(
    "target_name", ["CommonTemplate.Макет", "CommonForm.Форма", "DataProcessor.Владелец.Form.Форма"]
)
def test_excluded_templates_and_separate_form_operation_rejected(roots, target_name):
    source, target = roots
    snapshot = editor.Snapshot(target)
    with pytest.raises(editor.Rejected):
        borrow.borrow_object(snapshot, operation(source, target_name))
    assert snapshot.writes == {}


def test_source_name_and_registration_are_checked(roots):
    source, target = roots
    path = source / "DataProcessors/Владелец.xml"
    node = editor.metadata(path.read_bytes(), "DataProcessor")
    node.find("m:Properties/m:Name", editor.NS).text = "Другой"
    path.write_bytes(etree.tostring(node.getparent()))
    snapshot = editor.Snapshot(target)
    with pytest.raises(editor.Rejected, match="name mismatch"):
        borrow.borrow_object(snapshot, operation(source))
    assert snapshot.writes == {}


def test_predicted_uuid_collision_in_another_descriptor_is_rejected(roots):
    source, target = roots
    config = editor.metadata((target / "Configuration.xml").read_bytes(), "Configuration")
    collision = editor.allocate_uuid(editor.identity(config), "DataProcessor", "DataProcessor.Владелец", "object", {})
    language_path = target / "Languages/Русский.xml"
    language = editor.metadata(language_path.read_bytes(), "Language")
    language.set("uuid", collision)
    language_path.write_bytes(etree.tostring(language.getparent()))
    snapshot = editor.Snapshot(target)
    with pytest.raises(editor.Rejected, match="Generated UUID collision"):
        borrow.borrow_object(snapshot, operation(source))
    assert snapshot.writes == {}


def test_configuration_bom_crlf_and_existing_values_survive(roots):
    source, target = roots
    path = target / "Configuration.xml"
    data = b"\xef\xbb\xbf" + path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    path.write_bytes(data)
    before = editor.metadata(data, "Configuration")
    snapshot = editor.Snapshot(target)
    borrow.borrow_object(snapshot, operation(source))
    candidate = snapshot.writes["Configuration.xml"]
    assert present(candidate).startswith(b"\xef\xbb\xbf")
    assert b"\n" not in present(candidate).replace(b"\r\n", b"")
    after = editor.metadata(present(candidate), "Configuration")
    assert editor.signature(before.find("m:Properties", editor.NS)) == editor.signature(
        after.find("m:Properties", editor.NS)
    )
    assert before.get("uuid") == after.get("uuid")


def test_uuid_allocation_is_independent_of_plan_and_source_directory(roots, tmp_path):
    source, target = roots
    copied = tmp_path / "other-source"
    shutil.copytree(source, copied)
    snapshots = [editor.Snapshot(target), editor.Snapshot(target)]
    borrow.borrow_object(snapshots[0], operation(source))
    borrow.borrow_object(snapshots[1], operation(copied))
    assert snapshots[0].writes == snapshots[1].writes
    node = editor.metadata(present(snapshots[0].writes["DataProcessors/Владелец.xml"]), "DataProcessor")
    assert uuid.UUID(node.get("uuid")).version == 5


@pytest.mark.parametrize("kind", ["ExchangePlan", "CommonModule", "Document", "ChartOfCalculationTypes"])
def test_generated_shell_roles_and_common_module_flags(roots, kind):
    source, target = roots
    base = editor.metadata((source / "Configuration.xml").read_bytes(), "Configuration")
    registration = etree.SubElement(base.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}{kind}")
    registration.text = "Тест"
    (source / "Configuration.xml").write_bytes(etree.tostring(base.getparent()))
    root = etree.Element(f"{{{editor.MD}}}MetaDataObject", nsmap={None: editor.MD}, version="2.20")
    node = etree.SubElement(root, f"{{{editor.MD}}}{kind}", uuid=str(uuid.uuid4()))
    properties = etree.SubElement(node, f"{{{editor.MD}}}Properties")
    etree.SubElement(properties, f"{{{editor.MD}}}Name").text = "Тест"
    if kind == "CommonModule":
        for index, key in enumerate(borrow.COMMON_MODULE_PROPERTIES):
            etree.SubElement(properties, f"{{{editor.MD}}}{key}").text = "true" if index % 2 else "false"
    directory = source / borrow.DIRECTORIES[kind]
    directory.mkdir(exist_ok=True)
    (directory / "Тест.xml").write_bytes(etree.tostring(root))
    snapshot = editor.Snapshot(target)
    borrow.borrow_object(snapshot, operation(source, kind + ".Тест"))
    after = editor.metadata(present(snapshot.writes[f"{borrow.DIRECTORIES[kind]}/Тест.xml"]), kind)
    if kind == "CommonModule":
        assert [editor.prop(after, key) for key in borrow.COMMON_MODULE_PROPERTIES] == ["false", "true"] * 3
    else:
        generated = after.findall(f"m:InternalInfo/{{{borrow.XR}}}GeneratedType", editor.NS)
        assert [(item.get("name"), item.get("category")) for item in generated] == [
            (prefix + ".Тест", category) for prefix, category in borrow.GENERATED_TYPES[kind]
        ]
        ids = [
            element.text
            for element in after.iter()
            if element.tag in {f"{{{borrow.XR}}}TypeId", f"{{{borrow.XR}}}ValueId", f"{{{borrow.XR}}}ThisNode"}
        ]
        assert len(ids) == len(set(ids))
        assert all(uuid.UUID(value).version == 5 for value in ids)


@pytest.mark.parametrize("missing", ["base-registration", "target-descriptor", "mapping"])
def test_inconsistent_roots_fail_without_candidates(roots, missing):
    source, target = roots
    path = (source if missing == "base-registration" else target) / "Configuration.xml"
    config = editor.metadata(path.read_bytes(), "Configuration")
    children = config.find("m:ChildObjects", editor.NS)
    if missing == "base-registration":
        children.remove(children.find("m:DataProcessor", editor.NS))
    elif missing == "target-descriptor":
        etree.SubElement(children, f"{{{editor.MD}}}DataProcessor").text = "Владелец"
    else:
        config.find("m:Properties/m:KeepMappingToExtendedConfigurationObjectsByIDs", editor.NS).text = "false"
    path.write_bytes(etree.tostring(config.getparent()))
    snapshot = editor.Snapshot(target)
    with pytest.raises(editor.Rejected):
        borrow.borrow_object(snapshot, operation(source))
    assert snapshot.writes == {}


def test_real_borrow_through_plan_cli_and_preimage_replay(roots, tmp_path, capsys):
    import json

    source, target = roots
    request_path, plan_path = tmp_path / "request.json", tmp_path / "plan.json"
    request_path.write_text(json.dumps({"schemaVersion": 1, "operations": [operation(source)]}), encoding="utf-8")
    assert editor.main(["plan", "--root", str(target), "--request", str(request_path), "--out", str(plan_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "planned"
    assert report["checks"] == {"platform": "not-run", "runtime": "not-run"}
    assert not (target / "DataProcessors/Владелец.xml").exists()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    state, _snapshot = editor.verify_plan(target, plan)
    assert state == "before"
    assert editor.main(["apply", "--root", str(target), "--plan", str(plan_path)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "applied"
    assert editor.main(["apply", "--root", str(target), "--plan", str(plan_path)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "already-applied"
    assert editor.verify_plan(target, plan)[0] == "after"
    repeat = editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [operation(source)]})
    assert repeat["writes"] == [] and repeat["diff"] == ""
    assert editor.verify_plan(target, repeat)[0] == "after"
    source_descriptor = source / "DataProcessors/Владелец.xml"
    source_descriptor.write_bytes(source_descriptor.read_bytes() + b"\n")
    with pytest.raises(editor.Rejected):
        editor.verify_plan(target, plan)


@pytest.mark.parametrize("crash", ["journal", "temporary", "before", "first", "last"])
def test_process_crash_recovers_real_borrow(roots, tmp_path, crash):
    import json
    import subprocess
    import sys

    source, target = roots
    plan = editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [operation(source)]})
    plan_path = tmp_path / "crash-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    program = """import json,os,sys
from pathlib import Path
from scripts.python import metadata as m
root=Path(sys.argv[1]); plan=json.loads(Path(sys.argv[2]).read_text()); crash=sys.argv[3]
replace=os.replace
def interrupt(source,target):
 target=Path(target)
 if crash=='before' and target.is_relative_to(root): os._exit(81)
 replace(source,target)
 if crash=='journal' and target.name=='journal.json': os._exit(81)
 if crash=='first' and target==root/'Configuration.xml': os._exit(81)
 if crash=='last' and target.name==plan['writes'][-1]['path'].split('/')[-1]: os._exit(81)
os.replace=interrupt
if crash=='temporary':
 def partial(target,data,mode,temporary):
  with temporary.open('xb') as stream:
   stream.write(data[:11]); stream.flush(); os.fsync(stream.fileno())
  os._exit(81)
 m._replace_bytes=partial
m.apply(root,None,plan)
"""
    process = subprocess.run(
        [sys.executable, "-c", program, str(target), str(plan_path), crash],
        cwd=editor.PROJECT_ROOT,
        capture_output=True,
        timeout=30,
    )
    assert process.returncode == 81, process.stderr
    journal = target.with_name("." + target.name + ".metadata-state") / "journal.json"
    assert journal.exists()
    assert editor.apply(target, None, plan) == ("already-applied" if crash == "last" else "applied")
    assert editor.verify_plan(target, plan)[0] == "after"
    assert not journal.exists()
    assert not list(target.rglob(".metadata-*.tmp"))


@pytest.mark.parametrize(
    ("tag", "style"),
    [
        ("BackColor", "ToolTipBackColor"),
        ("Font", "LargeTextFont"),
        ("BorderColor", "BorderColor"),
        ("TextColor", "FormTextColor"),
    ],
)
def test_form_platform_style_is_not_adopted(dependency_form, tag, style):
    source, target, form = dependency_form
    control = form.find('.//f:InputField[@name="Расчетное"]', editor.NS)
    etree.SubElement(control, f"{{{editor.FORM}}}{tag}").text = "style:" + style
    snapshot = editor.Snapshot(target)
    dependencies = borrow.borrow_form_dependencies(snapshot, source, "DataProcessor.Владелец", form)
    assert "StyleItem." + style not in dependencies
    assert snapshot.read("target", f"StyleItems/{style}.xml", optional=True) is None


def _native_projection_source(source, stem):
    """Owner form with the parts Designer drops or rewrites in a native projection."""
    owner_path = source / "DataProcessors/Владелец.xml"
    owner = editor.metadata(owner_path.read_bytes(), "DataProcessor")
    children = owner.find("m:ChildObjects", editor.NS)
    attribute_uuid = str(uuid.uuid4())
    attribute = etree.Element(f"{{{editor.MD}}}Attribute", uuid=attribute_uuid)
    etree.SubElement(
        etree.SubElement(attribute, f"{{{editor.MD}}}Properties"), f"{{{editor.MD}}}Name"
    ).text = "Реквизит"
    children.insert(0, attribute)
    owner_path.write_bytes(etree.tostring(owner.getparent()))
    path = source / stem / "Ext/Form.xml"
    data = path.read_bytes()
    form = editor.xml_read(data, f"{{{editor.FORM}}}Form")
    main = etree.SubElement(form.find("f:Attributes", editor.NS), f"{{{editor.FORM}}}Attribute", name="Объект", id="1")
    etree.SubElement(
        etree.SubElement(main, f"{{{editor.FORM}}}Type"), f"{{{editor.V8}}}Type"
    ).text = "cfg:DataProcessorObject.Владелец"
    etree.SubElement(main, f"{{{editor.FORM}}}MainAttribute").text = "true"
    field = etree.SubElement(form.find("f:ChildItems", editor.NS), f"{{{editor.FORM}}}InputField", name="Поле", id="20")
    etree.SubElement(field, f"{{{editor.FORM}}}DataPath").text = "Объект.Реквизит"
    # Designer also drops table title/footer paths (СчетНаОплатуПокупателю, R234).
    for name in ("TitleDataPath", "FooterDataPath"):
        etree.SubElement(field, f"{{{editor.FORM}}}{name}").text = "Объект.Реквизит"
    links = etree.SubElement(field, f"{{{editor.FORM}}}ChoiceParameterLinks")
    for value in ("Текст", "Объект.Реквизит"):
        link = etree.SubElement(links, f"{{{borrow.XR}}}Link")
        etree.SubElement(link, f"{{{borrow.XR}}}Name").text = "Отбор.Владелец"
        etree.SubElement(link, f"{{{borrow.XR}}}DataPath").text = value
    button = etree.SubElement(form.find("f:AutoCommandBar", editor.NS), f"{{{editor.FORM}}}ChildItems")
    button = etree.SubElement(button, f"{{{editor.FORM}}}Button", name="Кнопка", id="21")
    etree.SubElement(button, f"{{{editor.FORM}}}CommandName").text = "Form.Command.OldCommand"
    path.write_bytes(editor.serialize_like(form, data))
    return path, attribute_uuid


@pytest.mark.parametrize("form_roots", ["owner"], indirect=True)
def test_form_borrow_native_projection_matches_designer_and_allows_extension_main(form_roots):
    source, target, stem, operation = form_roots
    _, attribute_uuid = _native_projection_source(source, stem)
    operation["parameters"]["nativeProjection"] = True
    request = {"schemaVersion": 1, "operations": [operation]}
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert editor.apply(target, None, plan) == "applied"
    borrowed = editor.xml_read((target / stem / "Ext/Form.xml").read_bytes(), f"{{{editor.FORM}}}Form")
    base = borrowed.find("f:BaseForm", editor.NS)
    for root in (borrowed, base):
        assert [
            root.findall(f".//f:{name}", editor.NS) for name in ("DataPath", "TitleDataPath", "FooterDataPath")
        ] == [[]] * 3
        assert [root.find(f"f:{name}", editor.NS) for name in ("Commands", "Parameters", "CommandInterface")] == [
            None
        ] * 3
        assert [len(node) for node in root.findall("f:Attributes", editor.NS)] == [0]
        assert {node.text for node in root.findall(".//f:CommandName", editor.NS)} == {"0"}
        assert [node.text for node in root.findall("f:ChildItems//xr:DataPath", TYPE_NS)] == [
            "6",
            f"1/0:{attribute_uuid}",
        ]
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []

    def add_main(type_name):
        return {
            "schemaVersion": 1,
            "operations": [
                operation,
                {
                    "op": "form.edit",
                    "target": operation["target"],
                    "parameters": {
                        "definition": {
                            "attributes": [{"name": "Объект", "type": type_name, "main": True, "savedData": True}]
                        }
                    },
                },
            ],
        }

    with pytest.raises(editor.Rejected, match="Main form attribute identity/type"):
        editor.plan_make(editor.Snapshot(target), add_main("CatalogObject.Другой"))
    edited = editor.plan_make(editor.Snapshot(target), add_main("DataProcessorObject.Владелец"))
    assert editor.apply(target, None, edited) == "applied"
    assert editor.plan_make(editor.Snapshot(target), add_main("DataProcessorObject.Владелец"))["writes"] == []
    borrowed = editor.xml_read((target / stem / "Ext/Form.xml").read_bytes(), f"{{{editor.FORM}}}Form")
    assert [len(node) for node in borrowed.findall("f:BaseForm/f:Attributes", editor.NS)] == [0]
    assert len(borrow._native_main_attributes(borrowed)) == 1


@pytest.mark.parametrize("form_roots", ["owner"], indirect=True)
def test_form_edit_places_new_form_events_before_element_tree(form_roots):
    source, target, stem, operation = form_roots
    _native_projection_source(source, stem)
    operation["parameters"]["nativeProjection"] = True
    request = {
        "schemaVersion": 1,
        "operations": [
            operation,
            {
                "op": "form.edit",
                "target": operation["target"],
                "parameters": {
                    "definition": {
                        "formEvents": [{"name": "OnCreateAtServer", "handler": "ПриСозданииПосле", "callType": "After"}]
                    }
                },
            },
        ],
    }
    assert editor.apply(target, None, editor.plan_make(editor.Snapshot(target), request)) == "applied"
    borrowed = editor.xml_read((target / stem / "Ext/Form.xml").read_bytes(), f"{{{editor.FORM}}}Form")
    names = [etree.QName(child).localname for child in borrowed if isinstance(child.tag, str)]
    # Designer order: AutoCommandBar, Events, element tree, ..., BaseForm.
    assert (
        names.index("AutoCommandBar") + 1 == names.index("Events") < names.index("ChildItems") < names.index("BaseForm")
    )
    assert [
        (event.get("name"), event.get("callType"), event.text) for event in borrowed.find("f:Events", editor.NS)
    ] == [("OnCreateAtServer", "After", "ПриСозданииПосле")]
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []


@pytest.mark.parametrize("form_roots", ["owner"], indirect=True)
@pytest.mark.parametrize(
    "damage,message",
    [
        ("path", "Unsupported native projection path"),
        ("appearance", "ConditionalAppearance"),
        ("moduleOnly", "cannot be combined"),
        ("repairNativeCommandProjection", "cannot be combined"),
    ],
)
def test_form_borrow_native_projection_rejects_unknown_parts(form_roots, damage, message):
    source, target, stem, operation = form_roots
    path, _ = _native_projection_source(source, stem)
    if damage in ("path", "appearance"):
        data = path.read_bytes()
        form = editor.xml_read(data, f"{{{editor.FORM}}}Form")
        if damage == "path":
            next(form.iter(f"{{{borrow.XR}}}DataPath")).text = "Items.Поле.CurrentData.Реквизит"
        else:
            etree.SubElement(form, f"{{{editor.FORM}}}ConditionalAppearance")
        path.write_bytes(editor.serialize_like(form, data))
    else:
        operation["parameters"][damage] = True
    operation["parameters"]["nativeProjection"] = True
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected, match=message):
        editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": [operation]})
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
