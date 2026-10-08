"""Pure creation rendering: deterministic identity and rich type safety."""

from tests.python.metadata_test_support import designer_export, present  # noqa: I001 — runs first: skips the module without pytest, lxml, jsonschema
import json
from pathlib import Path
import shutil

import pytest
import lxml.etree as etree

from scripts.python import metadata as editor, metadata_create as create


ROOT_UUID = "280179ba-92e8-47b4-b0b2-e9bcece0df19"


def recorded_output(family, kind, definition):
    root = Path(__file__).parents[1] / "fixtures/metadata-create"
    provenance = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
    assert provenance[f"{family}/{kind}"]["definition"] == definition
    return root / family / kind


def own_extension(tmp_path, *dependencies):
    """Copy the own CFE fixture and create its explicit direct type dependencies.

    Automatic adoption is disabled, so a referenced object must exist before the
    checked plan; creating it separately keeps the checked plan's writes exact.
    """
    target = tmp_path / "extension"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    if dependencies:
        operations = [
            {
                "op": "object.create",
                "target": reference,
                "parameters": {"definition": {"type": reference.split(".")[0], "name": reference.split(".")[1]}},
            }
            for reference in dependencies
        ]
        plan = editor.plan_make(editor.Snapshot(target), {"schemaVersion": 1, "operations": operations})
        assert editor.apply(target, None, plan) == "applied"
    return target


def xml_content(node):
    """Compare structure and QName values, excluding intentionally new IDs."""
    text = (node.text or "").strip()
    if node.tag in {
        f"{{{create.borrow.XR}}}TypeId",
        f"{{{create.borrow.XR}}}ValueId",
        f"{{{create.borrow.XR}}}ThisNode",
    }:
        text = "<identity>"
    if node.tag in {f"{{{editor.V8}}}Type", f"{{{editor.V8}}}TypeSet"} and ":" in text:
        prefix, local = text.split(":", 1)
        text = "{" + node.nsmap[prefix] + "}" + local
    return node.tag, {k: v for k, v in node.attrib.items() if k != "uuid"}, text, [xml_content(child) for child in node]


@pytest.mark.parametrize("kind", create.KINDS)
def test_minimal_render(kind):
    definition = {"type": kind, "name": "Проверка", "synonym": "Тест <&>", "comment": "Комментарий <&>"}
    first = create.render_object(definition, ROOT_UUID, {}, extension=True)
    assert first == create.render_object(definition, ROOT_UUID, {}, extension=True)
    root = etree.fromstring(first)
    assert root.get("version") == "2.17"
    properties = root[0].find(f"{{{editor.MD}}}Properties")
    assert properties.findtext(f"{{{editor.MD}}}ObjectBelonging") == "Native"
    assert properties.findtext(f"{{{editor.MD}}}Comment") == definition["comment"]
    assert (
        properties.findtext(f"{{{editor.MD}}}Synonym/{{{editor.V8}}}item/{{{editor.V8}}}content")
        == definition["synonym"]
    )
    assert b"\r" not in first


@pytest.mark.parametrize(
    "kind",
    [
        "Catalog",
        "ChartOfAccounts",
        "ChartOfCharacteristicTypes",
        "ChartOfCalculationTypes",
        "ExchangePlan",
    ],
)
@pytest.mark.parametrize(
    ("code_length", "description_length", "expected"),
    [
        (0, 25, ["Description"]),
        (9, 0, ["Code"]),
        (0, 0, []),
    ],
)
def test_catalog_style_input_by_string_only_includes_enabled_fields(kind, code_length, description_length, expected):
    definition = {"type": kind, "name": "БезКода", "codeLength": code_length, "descriptionLength": description_length}
    root = etree.fromstring(create.render_object(definition, ROOT_UUID, {}))
    owner = root[0]
    fields = owner.find(f"{{{editor.MD}}}Properties/{{{editor.MD}}}InputByString")
    assert [node.text.rsplit(".", 1)[-1] for node in fields] == expected
    assert all(node.text.startswith(f"{kind}.БезКода.StandardAttribute.") for node in fields)


def test_composite_type_preserves_qualifiers():
    node = create.type_node("String(0) + Number(15,2,nonneg) + Date + CatalogRef.Партнеры + DefinedType.Адрес")
    assert node.findtext(f"{{{editor.V8}}}StringQualifiers/{{{editor.V8}}}Length") == "0"
    assert node.findtext(f"{{{editor.V8}}}NumberQualifiers/{{{editor.V8}}}AllowedSign") == "Nonnegative"
    assert node.findtext(f"{{{editor.V8}}}DateQualifiers/{{{editor.V8}}}DateFractions") == "Date"
    assert node.findtext(f"{{{editor.V8}}}TypeSet") == "cfg:DefinedType.Адрес"


def test_characteristic_type_set_is_rendered():
    node = create.type_node("Characteristic.ВидыСубконтоХозрасчетные")
    assert len(node) == 1
    assert node[0].tag == f"{{{editor.V8}}}TypeSet"
    assert node[0].text == "cfg:Characteristic.ВидыСубконтоХозрасчетные"


def test_value_storage_and_binary_data_keep_distinct_xml_types():
    storage = create.type_node("ValueStorage")
    binary = create.type_node("BinaryData")

    assert len(storage) == len(binary) == 1
    assert storage[0].tag == binary[0].tag == f"{{{editor.V8}}}Type"
    assert storage[0].text == "v8:ValueStorage"
    assert storage[0].nsmap["v8"] == editor.V8
    assert binary[0].text == "xs:base64Binary"
    assert binary[0].nsmap["xs"] == editor.XS


@pytest.mark.parametrize("value", ["Unknown", "CatalogRef.X<bad>", "String(5) + String(10)", "Date + DateTime"])
def test_invalid_type_rejected(value):
    with pytest.raises(editor.Rejected):
        create.type_node(value)


def test_enum_value_identity_is_independent_of_order():
    values = [{"name": "Первое", "synonym": "Первое <&>", "comment": "Комментарий"}, {"name": "Второе"}]

    def render(items):
        return etree.fromstring(
            create.render_object({"type": "Enum", "name": "Варианты", "values": items}, ROOT_UUID, {})
        )

    first, second = render(values), render(list(reversed(values)))

    def identities(root):
        return {
            node.findtext(f"{{{editor.MD}}}Properties/{{{editor.MD}}}Name"): node.get("uuid")
            for node in root.findall(f".//{{{editor.MD}}}EnumValue")
        }

    assert identities(first) == identities(second)
    assert len(set(identities(first).values())) == 2
    assert (
        first.findtext(f".//{{{editor.MD}}}EnumValue/{{{editor.MD}}}Properties/{{{editor.MD}}}Comment") == "Комментарий"
    )
    with pytest.raises(editor.Rejected, match="duplicate"):
        render([{"name": "Значение"}, {"name": "значение"}])


@pytest.mark.parametrize("kind", ["Catalog", "Document"])
def test_attributes_and_sections(kind):
    definition = {
        "type": kind,
        "name": "Тест",
        "attributes": [
            {"name": "Партнер", "type": "CatalogRef.Партнеры", "flags": ["req"]},
            {"name": "Описание", "type": "String(0)", "comment": "Полный текст"},
        ],
        "tabularSections": [
            {
                "name": "Строки",
                "synonym": "Позиции",
                "attributes": [{"name": "Сумма", "type": "Number(15,2)", "flags": ["index"]}],
            }
        ],
    }
    data = create.render_object(definition, ROOT_UUID, {})
    root = etree.fromstring(data)
    assert data == create.render_object(definition, ROOT_UUID, {})
    nodes = root.findall(f".//{{{editor.MD}}}Attribute")
    assert len(nodes) == 3
    assert (
        nodes[0]
        .find(f"{{{editor.MD}}}Properties/{{{editor.MD}}}FillValue")
        .get("{http://www.w3.org/2001/XMLSchema-instance}nil")
        == "true"
    )
    assert nodes[0].findtext(f"{{{editor.MD}}}Properties/{{{editor.MD}}}FillChecking") == "ShowError"
    assert nodes[1].findtext(f"{{{editor.MD}}}Properties/{{{editor.MD}}}Comment") == "Полный текст"
    assert nodes[2].find(f"{{{editor.MD}}}Properties/{{{editor.MD}}}FillValue") is None
    assert nodes[2].findtext(f"{{{editor.MD}}}Properties/{{{editor.MD}}}Indexing") == "Index"
    table = root.find(f".//{{{editor.MD}}}TabularSection")
    assert (
        table.findtext(f"{{{editor.MD}}}Properties/{{{editor.MD}}}Synonym/{{{editor.V8}}}item/{{{editor.V8}}}content")
        == "Позиции"
    )
    assert len(table.findall(f"{{{editor.MD}}}InternalInfo/*")) == 2
    ids = root.xpath("//@uuid | //xr:TypeId/text() | //xr:ValueId/text()", namespaces={"xr": create.borrow.XR})
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("name", ["Code", "код", "Ref", "Ссылка"])
def test_reserved_attribute_rejected(name):
    with pytest.raises(editor.Rejected, match="child name"):
        create.render_object({"type": "Catalog", "name": "Тест", "attributes": [{"name": name}]}, ROOT_UUID, {})


@pytest.mark.parametrize("kind", create.KINDS)
def test_creation_plan_apply_repeat_and_conflict(tmp_path, kind):
    target = tmp_path / "extension"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    definition = {"type": kind, "name": "НовыйОбъект"}
    payload = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.create", "target": kind + ".НовыйОбъект", "parameters": {"definition": definition}}
        ],
    }
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    directory = target / create.borrow.DIRECTORIES[kind] / definition["name"]
    for module in directory.rglob("*.bsl"):
        assert module.read_bytes() == b""
        module.write_bytes(b"// preserved user module\n")
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    after = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    definition["comment"] = "Different intent"
    with pytest.raises(editor.Rejected, match="Existing object differs"):
        editor.plan_make(editor.Snapshot(target), payload)
    assert after == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


def test_create_then_add_same_attribute_uses_common_identity(tmp_path):
    target = tmp_path / "extension"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    attribute = {"name": "Поле", "type": "Boolean"}
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.create",
                "target": "Document.Новый",
                "parameters": {"definition": {"type": "Document", "name": "Новый", "attributes": [attribute]}},
            },
            {
                "op": "object.edit",
                "target": "Document.Новый",
                "parameters": {"definition": {"add": {"attributes": [attribute]}}},
            },
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


def test_section_identity_uses_common_borrow_keys():
    data = create.render_object(
        {"type": "Document", "name": "Тест", "tabularSections": [{"name": "Строки"}]}, ROOT_UUID, {}
    )
    section = etree.fromstring(data).find(f".//{{{editor.MD}}}TabularSection")
    logical = "Document.Тест.TabularSection.Строки"
    assert section.get("uuid") == editor.allocate_uuid(ROOT_UUID, "TabularSection", logical, "object", {})
    for generated in section.find(f"{{{editor.MD}}}InternalInfo"):
        for part in generated:
            assert part.text == editor.allocate_uuid(
                ROOT_UUID, "TabularSection", logical, generated.get("name") + ":" + etree.QName(part).localname, {}
            )


@pytest.mark.parametrize("placement", ["after", "before"])
def test_enum_creation_does_not_ignore_placement(placement):
    with pytest.raises(ValueError, match="Invalid object operation parameters"):
        create.schema.normalize_parameters(
            "object.create",
            {"definition": {"type": "Enum", "name": "Варианты", "values": [{"name": "Первое", placement: "Второе"}]}},
        )


@pytest.mark.parametrize("problem", ["orphan", "registered-without-file", "unregistered-file", "case"])
def test_creation_rejects_inconsistent_target_without_writes(tmp_path, problem):
    target = tmp_path / "extension"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    directory = target / "Enums/Варианты"
    definition = {"type": "Enum", "name": "Варианты"}
    if problem == "orphan":
        directory.mkdir(parents=True)
        (directory / "user.txt").write_bytes(b"preserve")
    if problem == "unregistered-file":
        directory.parent.mkdir(exist_ok=True)
        directory.with_suffix(".xml").write_bytes(create.render_object(definition, ROOT_UUID, {}))
    if problem in {"registered-without-file", "case"}:
        path = target / "Configuration.xml"
        config = editor.metadata(path.read_bytes(), "Configuration")
        etree.SubElement(config.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}Enum").text = (
            "варианты" if problem == "case" else "Варианты"
        )
        path.write_bytes(editor.serialize_like(config.getparent(), path.read_bytes()))
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected):
        editor.plan_make(
            editor.Snapshot(target),
            {
                "schemaVersion": 1,
                "operations": [
                    {"op": "object.create", "target": "Enum.Варианты", "parameters": {"definition": definition}}
                ],
            },
        )
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


@pytest.mark.parametrize("kind", [kind for kind in create.KINDS if kind not in {"CommonCommand", "Subsystem"}])
def test_minimal_properties_match_original_generator(tmp_path, kind):
    # Recorded legacy output is independent of the new generator.
    definition = {"type": kind, "name": "Сравнение"}
    if kind == "Constant":
        # The old CLI confuses object kind with value type when omitted.
        definition["valueType"] = "String"
    output = recorded_output("minimal", kind, definition)
    legacy = etree.parse(str(output / create.borrow.DIRECTORIES[kind] / "Сравнение.xml"))
    actual = etree.fromstring(create.render_object(definition, ROOT_UUID, {}))

    def content(node):
        return node.tag, dict(node.attrib), (node.text or "").strip(), [content(child) for child in node]

    expected = legacy.getroot()[0].find(f"{{{editor.MD}}}Properties")
    assert content(actual[0].find(f"{{{editor.MD}}}Properties")) == content(expected)


@pytest.mark.parametrize("kind", create.REGISTERS)
def test_register_members_match_legacy_and_replay(tmp_path, kind):
    fields = {
        "InformationRegister": {"periodicity": "Month", "writeMode": "RecorderSubordinate"},
        "AccumulationRegister": {"registerType": "Turnovers", "enableTotalsSplitting": False},
        "AccountingRegister": {"chartOfAccounts": "ChartOfAccounts.Хозрасчетный", "correspondence": True},
        "CalculationRegister": {
            "chartOfCalculationTypes": "ChartOfCalculationTypes.Начисления",
            "actionPeriod": True,
            "basePeriod": True,
            "schedule": "InformationRegister.Графики",
            "scheduleValue": "InformationRegister.Графики.Resource.Значение",
            "scheduleDate": "InformationRegister.Графики.Dimension.Дата",
        },
    }[kind]
    flags = ["req", "index"]
    if kind == "InformationRegister":
        flags += ["master", "mainfilter", "denyincomplete"]
    elif kind == "AccumulationRegister":
        flags += ["denyincomplete", "nouseintotals"]
    definition = {
        "type": kind,
        "name": "НовыйРегистр",
        **fields,
        "dimensions": [{"name": "Партнер", "type": "CatalogRef.Партнеры", "flags": flags}],
        "resources": [{"name": "Сумма", "type": "Number(15,2,nonneg)", "flags": ["req"]}],
        "attributes": [{"name": "Описание", "type": "String(25)"}],
    }
    legacy_dir = recorded_output("register", kind, definition)
    expected = etree.parse(str(legacy_dir / create.borrow.DIRECTORIES[kind] / "НовыйРегистр.xml")).getroot()
    actual = etree.fromstring(create.render_object(definition, ROOT_UUID, {}))
    assert xml_content(actual) == xml_content(expected)
    target = own_extension(tmp_path, "Catalog.Партнеры")
    payload = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.create", "target": kind + ".НовыйРегистр", "parameters": {"definition": definition}}
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    module = target / create.borrow.DIRECTORIES[kind] / "НовыйРегистр/Ext/RecordSetModule.bsl"
    assert module.read_bytes() == b""
    module.write_bytes(b"// user module\n")
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    assert module.read_bytes() == b"// user module\n"


@pytest.mark.parametrize(
    "kind,field,value",
    [
        ("AccountingRegister", "chartOfAccounts", "Catalog.Счета"),
        ("CalculationRegister", "chartOfCalculationTypes", "Bad<xml>"),
        ("CalculationRegister", "schedule", "InformationRegister.X.Bad"),
        ("CalculationRegister", "scheduleValue", "InformationRegister.X.Resource"),
    ],
)
def test_invalid_register_references_rejected(kind, field, value):
    with pytest.raises(editor.Rejected, match="reference"):
        create.render_object({"type": kind, "name": "Проверка", field: value}, ROOT_UUID, {})


@pytest.mark.parametrize("kind", create.REGISTERS)
def test_register_child_names_and_unsupported_flags_rejected(kind):
    for definition in [
        {"dimensions": [{"name": "Поле", "type": "Boolean"}], "resources": [{"name": "поле"}]},
        {"resources": [{"name": "Сумма", "flags": ["master"]}]},
        {"dimensions": [{"name": "Регистратор"}]},
        {"dimensions": [{"name": "Поле", "type": "Unknown"}]},
    ]:
        with pytest.raises(editor.Rejected):
            create.render_object({"type": kind, "name": "Проверка", **definition}, ROOT_UUID, {})


@pytest.mark.parametrize(
    "kind,name,rejected",
    [
        ("AccumulationRegister", "ВидРасчета", False),
        ("InformationRegister", "Счет", False),
        ("CalculationRegister", "ВидРасчета", True),
        ("AccountingRegister", "Счет", True),
    ],
)
def test_register_standard_names_are_reserved_only_for_their_register_kind(kind, name, rejected):
    definition = {"type": kind, "name": "Проверка", "attributes": [{"name": name, "type": "String"}]}

    if rejected:
        with pytest.raises(editor.Rejected, match="child name"):
            create.render_object(definition, ROOT_UUID, {})
    else:
        create.render_object(definition, ROOT_UUID, {})


@pytest.mark.parametrize("kind", create.CHARTS)
def test_chart_children_and_properties_match_legacy(tmp_path, kind):
    fields = {
        "ChartOfAccounts": {
            "extDimensionTypes": "ChartOfCharacteristicTypes.ВидыСубконто",
            "accountingFlags": ["Количественный"],
            "extDimensionAccountingFlags": ["Суммовой"],
            "codeMask": "##.##",
            "maxExtDimensionCount": 3,
        },
        "ChartOfCharacteristicTypes": {
            "characteristicExtValues": "Catalog.Значения",
            "valueTypes": ["Boolean", "String(40)", "CatalogRef.Партнеры"],
        },
        "ChartOfCalculationTypes": {
            "dependenceOnCalculationTypes": "RequireCalculationTypes",
            "baseCalculationTypes": ["ChartOfCalculationTypes.Базовый"],
            "actionPeriodUse": True,
        },
    }[kind]
    definition = {
        "type": kind,
        "name": "НовыйПлан",
        **fields,
        "attributes": [{"name": "Описание", "type": "String(25)"}],
        "tabularSections": [{"name": "Строки", "attributes": [{"name": "Значение", "type": "Boolean"}]}],
    }
    output = recorded_output("chart", kind, definition)
    expected = etree.parse(str(output / create.borrow.DIRECTORIES[kind] / "НовыйПлан.xml")).getroot()
    actual = etree.fromstring(create.render_object(definition, ROOT_UUID, {}))
    if kind == "ChartOfCharacteristicTypes":
        # Correct the known old-generator defect against actual platform XML.
        for generated in expected.findall(f".//{{{create.borrow.XR}}}GeneratedType"):
            if generated.get("category") == "Characteristic":
                generated.set("name", "Characteristic.НовыйПлан")
    assert xml_content(actual) == xml_content(expected)
    assert create.render_object(definition, ROOT_UUID, {}) == create.render_object(definition, ROOT_UUID, {})


@pytest.mark.parametrize(
    "kind,name",
    [
        ("ChartOfAccounts", "Хозрасчетный"),
        ("ChartOfCharacteristicTypes", "КатегорииНовостей"),
        ("ChartOfCalculationTypes", "Начисления"),
    ],
)
def test_chart_generated_types_match_real_source(kind, name):
    relative = create.borrow.DIRECTORIES[kind] + "/" + name + ".xml"
    path = designer_export(relative) / relative
    source = etree.parse(str(path)).getroot()
    actual = etree.fromstring(create.render_object({"type": kind, "name": name}, ROOT_UUID, {}))

    def types(root):
        return [
            dict(node.attrib)
            for node in root.findall(f"./*/{{{editor.MD}}}InternalInfo/{{{create.borrow.XR}}}GeneratedType")
        ]

    assert types(actual) == types(source)


def test_chart_rejects_collisions_and_preserves_mask():
    for value in [
        {"accountingFlags": ["Флаг", "флаг"]},
        {"accountingFlags": ["Код"]},
        {"tabularSections": [{"name": "ExtDimensionTypes"}]},
        {"extDimensionTypes": "Catalog.Неверно"},
    ]:
        with pytest.raises(editor.Rejected):
            create.render_object({"type": "ChartOfAccounts", "name": "План", **value}, ROOT_UUID, {})
    root = etree.fromstring(
        create.render_object({"type": "ChartOfAccounts", "name": "План", "codeMask": "<&>"}, ROOT_UUID, {})
    )
    assert root.findtext(f".//{{{editor.MD}}}CodeMask") == "<&>"


@pytest.mark.parametrize("kind", ["BusinessProcess", "Task", "ExchangePlan"])
def test_process_task_exchange_complete_files_and_legacy(tmp_path, kind):
    fields = {
        "BusinessProcess": {"task": "Task.Задача", "numberLength": 12},
        "Task": {
            "addressing": "InformationRegister.Исполнители",
            "mainAddressingAttribute": "Task.Новый.AddressingAttribute.Исполнитель",
            "currentPerformer": "SessionParameter.Пользователь",
            "addressingAttributes": [
                {
                    "name": "Исполнитель",
                    "type": "CatalogRef.Пользователи",
                    "addressingDimension": "InformationRegister.Исполнители.Dimension.Пользователь",
                }
            ],
        },
        "ExchangePlan": {"distributedInfoBase": True, "includeConfigurationExtensions": True},
    }[kind]
    definition = {
        "type": kind,
        "name": "Новый",
        **fields,
        "attributes": [{"name": "Описание", "type": "String(40)"}],
        "tabularSections": [{"name": "Строки", "attributes": [{"name": "Значение", "type": "Boolean"}]}],
    }
    output = recorded_output("process", kind, definition)
    expected = etree.parse(str(output / create.borrow.DIRECTORIES[kind] / "Новый.xml")).getroot()
    actual = etree.fromstring(create.render_object(definition, ROOT_UUID, {}))
    assert xml_content(actual) == xml_content(expected)
    target = own_extension(tmp_path, *(["Catalog.Пользователи"] if kind == "Task" else []))
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "object.create", "target": kind + ".Новый", "parameters": {"definition": definition}}],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    directory = create.borrow.DIRECTORIES[kind] + "/Новый"
    expected_files = {directory + ".xml", directory + "/Ext/ObjectModule.bsl"}
    special = {"BusinessProcess": "Flowchart.xml", "ExchangePlan": "Content.xml"}.get(kind)
    special_path, before = None, None
    if special:
        expected_files.add(directory + "/Ext/" + special)
        special_path = target / directory / "Ext" / special
        original_special = etree.parse(str(output / directory / "Ext" / special)).getroot()
        assert xml_content(etree.parse(str(special_path)).getroot()) == xml_content(original_special)
        content = etree.parse(str(special_path))
        content.getroot().append(etree.Comment("preserved user content"))
        special_path.write_bytes(etree.tostring(content))
        before = special_path.read_bytes()
    assert {
        str(p.relative_to(target)).replace("\\", "/")
        for p in target.rglob("*")
        if p.is_file() and str(p.relative_to(target)).replace("\\", "/").startswith(directory)
    } == expected_files
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    if special:
        assert present(special_path).read_bytes() == before


@pytest.mark.parametrize(
    "kind,fields",
    [
        ("BusinessProcess", {"task": "Catalog.Задачи"}),
        ("Task", {"addressing": "Catalog.Адресация"}),
        ("Task", {"currentPerformer": "SessionParameter.Bad<value>"}),
        ("Task", {"mainAddressingAttribute": "Task.Новый.AddressingAttribute.Нет"}),
        ("Task", {"addressingAttributes": [{"name": "Адрес", "addressingDimension": "Bad"}]}),
        ("Task", {"addressingAttributes": [{"name": "Адрес", "flags": ["req"]}]}),
        ("ExchangePlan", {"attributes": [{"name": "ЭтотУзел"}]}),
    ],
)
def test_process_task_exchange_invalid_inputs(kind, fields):
    with pytest.raises(editor.Rejected):
        create.render_object({"type": kind, "name": "Новый", **fields}, ROOT_UUID, {})


@pytest.mark.parametrize(
    "kind,name",
    [
        ("BusinessProcess", "Задание"),
        ("Task", "ЗадачаИсполнителя"),
        ("ExchangePlan", "МобильноеПриложениеПредприниматель"),
    ],
)
def test_process_task_exchange_types_match_real_source(kind, name):
    relative = create.borrow.DIRECTORIES[kind] + "/" + name + ".xml"
    source = etree.parse(str(designer_export(relative) / relative)).getroot()
    actual = etree.fromstring(create.render_object({"type": kind, "name": name}, ROOT_UUID, {}))
    assert xml_content(actual[0].find(f"{{{editor.MD}}}InternalInfo")) == xml_content(
        source[0].find(f"{{{editor.MD}}}InternalInfo")
    )


@pytest.mark.parametrize(
    "kind",
    [
        "Report",
        "DataProcessor",
        "DocumentJournal",
        "CommonModule",
        "ScheduledJob",
        "EventSubscription",
        "HTTPService",
        "WebService",
    ],
)
def test_reporting_and_automation_complete_xml_and_files(tmp_path, kind):
    definition = {"type": kind, "name": "Новый"}
    if kind in {"Report", "DataProcessor", "DocumentJournal"}:
        definition.update(defaultForm=kind + ".Новый.Form.Основная", auxiliaryForm="CommonForm.Дополнительная")
    if kind == "DocumentJournal":
        definition.update(
            registeredDocuments=["Document.Заказ"],
            columns=[{"name": "Партнер", "indexing": "Index", "references": ["Document.Заказ.Attribute.Партнер"]}],
        )
    elif kind in {"Report", "DataProcessor"}:
        definition.update(
            attributes=[{"name": "Фильтр", "type": "CatalogRef.Партнеры", "flags": ["req"]}],
            tabularSections=[{"name": "Строки", "attributes": [{"name": "Сумма", "type": "Number(15,2)"}]}],
        )
    elif kind == "CommonModule":
        definition.update(server=True, externalConnection=True, privileged=True, returnValuesReuse="DuringRequest")
    elif kind == "ScheduledJob":
        definition.update(
            methodName="Служебный.Выполнить",
            description="Описание <&>",
            key="Ключ <&>",
            use=True,
            predefined=True,
            restartCountOnFailure=0,
            restartIntervalOnFailure=20,
        )
    elif kind == "EventSubscription":
        definition.update(
            source=["DocumentObject.Заказ", "CatalogObject.Партнеры", "DocumentManager"],
            event="OnWrite",
            handler="CommonModule.Служебный.ПриЗаписи",
        )
    elif kind == "HTTPService":
        definition.update(
            rootURL="api",
            reuseSessions="AutoUse",
            sessionMaxAge=60,
            urlTemplates={
                "Users": {"template": "/users/{id}", "methods": {"Read": "GET", "Write": "POST"}},
                "Health": {"template": "/health"},
            },
        )
    elif kind == "WebService":
        definition.update(
            namespace="https://example.test/service",
            xdtoPackages=(
                "<xr:Item><xr:Presentation/><xr:CheckState>0</xr:CheckState>"
                '<xr:Value xsi:type="xr:MDObjectRef">XDTOPackage.Пакет</xr:Value></xr:Item>'
            ),
            operations={
                "Read": {
                    "returnType": "xs:boolean",
                    "handler": "Чтение",
                    "nillable": True,
                    "transactioned": True,
                    "parameters": {
                        "Id": {"type": "xs:long", "nillable": False},
                        "Error": {"type": "xs:string", "direction": "Out"},
                    },
                },
                "Version": {"returnType": "xs:string"},
            },
        )
    if kind == "Report":
        definition.update(
            mainDataCompositionSchema="Report.Новый.Template.Схема", defaultSettingsForm="Report.Новый.Form.Настройки"
        )
    output = recorded_output("automation", kind, definition)
    expected = etree.parse(str(output / create.borrow.DIRECTORIES[kind] / "Новый.xml")).getroot()
    actual = etree.fromstring(create.render_object(definition, ROOT_UUID, {}))
    assert xml_content(actual) == xml_content(expected)
    dependencies = {
        "Report": ["Catalog.Партнеры"],
        "DataProcessor": ["Catalog.Партнеры"],
        "EventSubscription": ["Document.Заказ", "Catalog.Партнеры"],
    }.get(kind, [])
    target = own_extension(tmp_path, *dependencies)
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "object.create", "target": kind + ".Новый", "parameters": {"definition": definition}}],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    directory = create.borrow.DIRECTORIES[kind] + "/Новый"
    files = {"Configuration.xml", directory + ".xml"}
    if kind in {"Report", "DataProcessor"}:
        files.update(directory + "/Ext/" + name + ".bsl" for name in ("ObjectModule", "ManagerModule"))
    elif kind in {"CommonModule", "HTTPService", "WebService"}:
        files.add(directory + "/Ext/Module.bsl")
    assert {item["path"] for item in plan["writes"]} == files
    assert editor.apply(target, None, plan) == "applied"
    for module in (target / directory).rglob("*.bsl"):
        module.write_bytes(b"// user module\n")
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    assert not list(target.rglob("Templates"))


@pytest.mark.parametrize(
    "kind,fields",
    [
        ("Report", {"defaultForm": "Report.Other.Form.X"}),
        ("Report", {"mainDataCompositionSchema": "Bad"}),
        ("DataProcessor", {"auxiliaryForm": "CommonForm.X<bad>"}),
        ("DataProcessor", {"attributes": [{"name": "Поле", "flags": ["index"]}]}),
        ("DocumentJournal", {"registeredDocuments": ["Catalog.Заказ"]}),
        ("DocumentJournal", {"columns": [{"name": "Дата"}]}),
        ("DocumentJournal", {"columns": [{"name": "Поле", "references": ["Catalog.X.Attribute.Y"]}]}),
    ],
)
def test_report_processor_journal_invalid_inputs(kind, fields):
    with pytest.raises(editor.Rejected):
        create.render_object({"type": kind, "name": "Новый", **fields}, ROOT_UUID, {})


@pytest.mark.parametrize(
    "context,enabled",
    [
        ("server", {"Server", "ServerCall"}),
        ("serverCall", {"Server", "ServerCall"}),
        ("client", {"ClientManagedApplication"}),
        ("serverClient", {"Server", "ClientManagedApplication"}),
    ],
)
def test_common_module_context(context, enabled):
    node = editor.metadata(
        create.render_object({"type": "CommonModule", "name": "Модуль", "context": context}, ROOT_UUID, {}),
        "CommonModule",
    )
    assert {
        name for name in (*create.borrow.COMMON_MODULE_PROPERTIES, "Privileged") if editor.prop(node, name) == "true"
    } == enabled


@pytest.mark.parametrize(
    "kind,fields",
    [
        ("CommonModule", {"context": "unknown"}),
        ("CommonModule", {"context": "server", "server": False}),
        ("CommonModule", {"context": "client", "privileged": True}),
        ("ScheduledJob", {"methodName": "Недопустимо"}),
        ("EventSubscription", {"source": ["DocumentObject.X<bad>"]}),
        ("EventSubscription", {"source": ["UnknownType.X"]}),
        ("EventSubscription", {"event": "OnWrite<bad>"}),
        ("EventSubscription", {"handler": "Other.Module.Method"}),
    ],
)
def test_automation_invalid_inputs(kind, fields):
    with pytest.raises(editor.Rejected):
        create.render_object({"type": kind, "name": "Новый", **fields}, ROOT_UUID, {})


@pytest.mark.parametrize(
    "kind,fields",
    [
        ("HTTPService", {"urlTemplates": {"X": {}, "x": {}}}),
        ("HTTPService", {"urlTemplates": {"X": {"methods": {"Read": "GET<bad>"}}}}),
        ("HTTPService", {"urlTemplates": {"X": {"methods": {"Read": "GET", "read": "POST"}}}}),
        ("WebService", {"operations": {"Read": {"returnType": "missing:Type"}}}),
        ("WebService", {"operations": {"Read": {"handler": "Invalid.Handler"}}}),
        ("WebService", {"operations": {"Read": {"parameters": {"P": {"direction": "Bad"}}}}}),
        ("WebService", {"operations": {"Read": {"parameters": {"P": {}, "p": {}}}}}),
        ("WebService", {"xdtoPackages": "</XDTOPackages><Injected/>"}),
        ("WebService", {"xdtoPackages": "<xr:Item><xr:Value>Unknown.X</xr:Value></xr:Item>"}),
    ],
)
def test_service_invalid_inputs(kind, fields):
    with pytest.raises(editor.Rejected):
        create.render_object({"type": kind, "name": "Новый", **fields}, ROOT_UUID, {})


def test_xdto_package_rejects_rebound_type_namespace():
    packages = (
        "<xr:Item><xr:Presentation/><xr:CheckState>0</xr:CheckState>"
        '<p:Value xmlns:p="http://v8.1c.ru/8.3/xcf/readable" xmlns:xr="urn:wrong" '
        'xsi:type="xr:MDObjectRef">XDTOPackage.Пакет</p:Value></xr:Item>'
    )
    with pytest.raises(editor.Rejected):
        create.render_object({"type": "WebService", "name": "Service", "xdtoPackages": packages}, ROOT_UUID, {})


@pytest.mark.parametrize(
    "kind,collection,definitions",
    [
        ("HTTPService", "urlTemplates", {"A": {"methods": {"Read": "GET"}}, "B": {"methods": {"Read": "GET"}}}),
        ("WebService", "operations", {"A": {"parameters": {"Value": {}}}, "B": {"parameters": {"Value": {}}}}),
    ],
)
def test_service_nested_identity_is_stable(kind, collection, definitions):
    def render(values):
        return etree.fromstring(
            create.render_object({"type": kind, "name": "Service", collection: values}, ROOT_UUID, {})
        )

    first = render(definitions)
    second = render(dict(reversed(list(definitions.items()))))
    assert etree.tostring(first) == etree.tostring(second)
    ids = first.xpath("//@uuid")
    assert len(ids) == len(set(ids)) == 5
    assert len(create.KINDS) == 25 and set(create.KINDS) == set(create.schema.OBJECT_TYPES)


def test_process_task_batch_and_broken_special_file(tmp_path):
    target = tmp_path / "extension"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", target)
    definitions = [
        {"type": "Task", "name": "Исполнение"},
        {"type": "BusinessProcess", "name": "Процесс", "task": "Task.Исполнение"},
        {"type": "ExchangePlan", "name": "Обмен"},
    ]
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "object.create", "target": "$root", "parameters": {"definition": definitions}}],
    }
    assert editor.apply(target, None, editor.plan_make(editor.Snapshot(target), payload)) == "applied"
    process = editor.metadata((target / "BusinessProcesses/Процесс.xml").read_bytes(), "BusinessProcess")
    assert editor.prop(process, "Task") == "Task.Исполнение"
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    special = target / "ExchangePlans/Обмен/Ext/Content.xml"
    special.write_bytes(b"<WrongRoot/>")
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


# Own extension command saved by Designer 8.3.27 (Демо_ДиагностикаСеанса in Демо_Адаптация).
NATIVE_COMMON_COMMAND = """<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core" version="2.20">
<CommonCommand uuid="785c55d2-a15f-46ea-8a1a-ea7d3bd2b72b"><Properties>
<ObjectBelonging>Native</ObjectBelonging><Name>Демо_ДиагностикаСеанса</Name>
<Synonym><v8:item><v8:lang>ru</v8:lang><v8:content>Диагностика сеанса</v8:content></v8:item></Synonym>
<Comment/><Group>ActionsPanelTools</Group><Representation>Auto</Representation><ToolTip/><Picture/><Shortcut/>
<IncludeHelpInContents>false</IncludeHelpInContents><CommandParameterType/><ParameterUseMode>Single</ParameterUseMode>
<ModifiesData>false</ModifiesData><OnMainServerUnavalableBehavior>Auto</OnMainServerUnavalableBehavior>
</Properties></CommonCommand></MetaDataObject>"""


def test_common_command_matches_designer_properties():
    definition = {"type": "CommonCommand", "name": "Демо_ДиагностикаСеанса", "synonym": "Диагностика сеанса"}
    actual = etree.fromstring(create.render_object(definition, ROOT_UUID, {}, extension=True))
    expected = etree.fromstring(NATIVE_COMMON_COMMAND.encode())
    properties = f"{{{editor.MD}}}Properties"
    assert xml_content(actual[0].find(properties)) == xml_content(expected[0].find(properties))
    assert not len(actual[0].findall(f"{{{editor.MD}}}ChildObjects"))


def test_common_command_create_writes_parameter_type_module_and_replays(tmp_path):
    target = own_extension(tmp_path, "Catalog.Партнеры")
    definition = {
        "type": "CommonCommand",
        "name": "НаОсновании",
        "synonym": "Создать",
        "group": "FormCommandBarCreateBasedOn",
        "representation": "Text",
        "parameterTypes": ["CatalogRef.Партнеры", "String(10)"],
        "parameterUseMode": "Multiple",
        "modifiesData": True,
    }
    payload = {
        "schemaVersion": 1,
        "operations": [
            {"op": "object.create", "target": "CommonCommand.НаОсновании", "parameters": {"definition": definition}}
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert {item["path"] for item in plan["writes"]} == {
        "CommonCommands/НаОсновании.xml",
        "CommonCommands/НаОсновании/Ext/CommandModule.bsl",
        "Configuration.xml",
    }
    assert editor.apply(target, None, plan) == "applied"
    owner = editor.metadata((target / "CommonCommands/НаОсновании.xml").read_bytes(), "CommonCommand")
    props = owner.find("m:Properties", editor.NS)
    assert [
        props.findtext(f"m:{name}", namespaces=editor.NS)
        for name in ("Group", "Representation", "ParameterUseMode", "ModifiesData")
    ] == ["FormCommandBarCreateBasedOn", "Text", "Multiple", "true"]
    types = props.find("m:CommandParameterType", editor.NS)
    assert [etree.QName(node).localname for node in types] == ["Type", "Type", "StringQualifiers"]
    assert types[0].text.split(":")[1] == "CatalogRef.Партнеры"
    assert (target / "CommonCommands/НаОсновании/Ext/CommandModule.bsl").read_bytes() == b""
    config = editor.metadata((target / "Configuration.xml").read_bytes(), "Configuration")
    assert [node.text for node in config.findall("m:ChildObjects/m:CommonCommand", editor.NS)] == ["НаОсновании"]
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize("group", ["", "Панель", "CommandGroup.", "CommandGroup.Моя.Лишняя", "Other.Моя"])
def test_common_command_rejects_invalid_group(group):
    with pytest.raises(editor.Rejected):
        create.render_object({"type": "CommonCommand", "name": "Команда", "group": group}, ROOT_UUID, {})


# Own extension subsystem saved by Designer 8.3.27 (Демо_Диагностика in Демо_Адаптация).
NATIVE_SUBSYSTEM = """<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.20">
<Subsystem uuid="8fb787db-8a7c-4db6-8459-7433b2a03ddc"><Properties>
<ObjectBelonging>Native</ObjectBelonging><Name>Демо_Диагностика</Name>
<Synonym><v8:item><v8:lang>ru</v8:lang><v8:content>Диагностика</v8:content></v8:item></Synonym>
<Comment/><IncludeHelpInContents>false</IncludeHelpInContents><IncludeInCommandInterface>true</IncludeInCommandInterface>
<UseOneCommand>false</UseOneCommand><Explanation/><Picture/>
<Content><xr:Item xsi:type="xr:MDObjectRef">CommonCommand.Демо_ДиагностикаСеанса</xr:Item></Content>
</Properties><ChildObjects/></Subsystem></MetaDataObject>"""


def test_subsystem_matches_designer_properties():
    definition = {
        "type": "Subsystem",
        "name": "Демо_Диагностика",
        "synonym": "Диагностика",
        "content": ["CommonCommand.Демо_ДиагностикаСеанса"],
    }
    actual = etree.fromstring(create.render_object(definition, ROOT_UUID, {}, extension=True))
    expected = etree.fromstring(NATIVE_SUBSYSTEM.encode())
    assert xml_content(actual[0]) == xml_content(expected[0])


def test_subsystem_content_requires_registered_objects_and_replays(tmp_path):
    target = own_extension(tmp_path)
    definition = {
        "type": "Subsystem",
        "name": "Раздел",
        "synonym": "Раздел",
        "explanation": "Пояснение",
        "content": ["DataProcessor.Владелец", "Catalog.Партнеры"],
    }
    payload = {
        "schemaVersion": 1,
        "operations": [{"op": "object.create", "target": "Subsystem.Раздел", "parameters": {"definition": definition}}],
    }
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected, match="not registered: Catalog.Партнеры"):
        editor.plan_make(editor.Snapshot(target), payload)
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    payload["operations"].insert(
        0,
        {
            "op": "object.create",
            "target": "Catalog.Партнеры",
            "parameters": {"definition": {"type": "Catalog", "name": "Партнеры"}},
        },
    )
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert {item["path"] for item in plan["writes"]} >= {"Subsystems/Раздел.xml", "Configuration.xml"}
    assert not any(item["path"].startswith("Subsystems/Раздел/") for item in plan["writes"])
    assert editor.apply(target, None, plan) == "applied"
    owner = editor.metadata((target / "Subsystems/Раздел.xml").read_bytes(), "Subsystem")
    assert [
        item.text for item in owner.findall("m:Properties/m:Content/xr:Item", {**editor.NS, "xr": create.borrow.XR})
    ] == ["DataProcessor.Владелец", "Catalog.Партнеры"]
    assert (
        owner.findtext("m:Properties/m:Explanation/v8:item/v8:content", namespaces={**editor.NS, "v8": editor.V8})
        == "Пояснение"
    )
    config = editor.metadata((target / "Configuration.xml").read_bytes(), "Configuration")
    assert [node.text for node in config.findall("m:ChildObjects/m:Subsystem", editor.NS)] == ["Раздел"]
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


@pytest.mark.parametrize(
    "fields",
    [
        {"content": ["Document.А", "document.а"]},
        {"content": ["Документ.А"]},
        {"picture": "Catalog.Картинка"},
        {"useOneCommand": True, "content": ["Document.А", "Document.Б"]},
    ],
)
def test_subsystem_rejects_invalid_definition(fields):
    with pytest.raises(editor.Rejected):
        create.render_object({"type": "Subsystem", "name": "Раздел", **fields}, ROOT_UUID, {})


def test_subsystem_picture_reference():
    root = etree.fromstring(
        create.render_object(
            {"type": "Subsystem", "name": "Раздел", "picture": "CommonPicture.Значок"}, ROOT_UUID, {}, extension=True
        )
    )
    picture = root[0].find("m:Properties/m:Picture", editor.NS)
    assert [(etree.QName(node).localname, node.text) for node in picture] == [
        ("Ref", "CommonPicture.Значок"),
        ("LoadTransparent", "false"),
    ]
