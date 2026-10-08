from tests.python.metadata_test_support import present  # noqa: I001 — runs first: skips the module without pytest, lxml, jsonschema
import json
import uuid

import pytest
import lxml.etree as etree

from scripts.python import metadata as editor
from scripts.python import metadata_borrow as borrow
from scripts.python import metadata_predefined as predefined


MD = editor.MD
EXT = "http://v8.1c.ru/8.3/xcf/predef"
BASE_ID = "3796bdf5-5d0b-4232-b22e-6d2cd8beb488"
EXT_ID = "b36cf290-be7e-4e00-b443-cd18a2855fd0"
CHART_ID = "b490baa9-d6a4-4563-a61e-2e2cc4bb8d3a"
TYPE_ID = "aa86f7cf-1223-4caf-96f0-9536651632c1"
CHART_NAME = "Хозрасчетный"
TYPE_NAME = "ВидыСубконтоХозрасчетные"
CHARACTERISTIC_CHART = "ChartOfCharacteristicTypes"
ACCOUNT_FLAGS = {"Валютный": False, "Количественный": True, "УчетПоПодразделениям": False, "НалоговыйУчет": False}
DIMENSION_FLAGS = {"Суммовой": True, "Валютный": True, "Количественный": True}


def _properties(node, values):
    props = etree.SubElement(node, f"{{{MD}}}Properties")
    for name, value in values.items():
        etree.SubElement(props, f"{{{MD}}}{name}").text = value
    return props


def _chart(root, belonging, object_uuid, *, base_uuid=None):
    node = etree.Element(f"{{{MD}}}MetaDataObject", nsmap={None: MD, "v8": editor.V8, "xs": editor.XS}, version="2.20")
    chart = etree.SubElement(node, f"{{{MD}}}ChartOfAccounts", uuid=object_uuid)
    internal = etree.SubElement(chart, f"{{{MD}}}InternalInfo")
    for type_name, category in borrow.GENERATED_TYPES["ChartOfAccounts"]:
        generated = etree.SubElement(
            internal, f"{{{borrow.XR}}}GeneratedType", name=f"{type_name}.{CHART_NAME}", category=category
        )
        etree.SubElement(generated, f"{{{borrow.XR}}}TypeId").text = str(uuid.uuid4())
        etree.SubElement(generated, f"{{{borrow.XR}}}ValueId").text = str(uuid.uuid4())
    values = {"ObjectBelonging": belonging, "Name": CHART_NAME}
    if belonging == "Native":
        values.update(
            {
                "CodeLength": "8",
                "DescriptionLength": "120",
                "OrderLength": "8",
                "MaxExtDimensionCount": "3",
                "ExtDimensionTypes": f"ChartOfCharacteristicTypes.{TYPE_NAME}",
            }
        )
    if base_uuid:
        values["ExtendedConfigurationObject"] = base_uuid
    _properties(chart, values)
    children = etree.SubElement(chart, f"{{{MD}}}ChildObjects")
    if belonging == "Native":
        for kind, names in [("AccountingFlag", ACCOUNT_FLAGS), ("ExtDimensionAccountingFlag", DIMENSION_FLAGS)]:
            for name in names:
                item = etree.SubElement(children, f"{{{MD}}}{kind}", uuid=str(uuid.uuid4()))
                _properties(item, {"Name": name})
                typed = etree.SubElement(item.find(f"{{{MD}}}Properties"), f"{{{MD}}}Type")
                etree.SubElement(typed, f"{{{editor.V8}}}Type").text = "xs:boolean"
    path = root / "ChartsOfAccounts" / f"{CHART_NAME}.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(etree.tostring(node, xml_declaration=True, encoding="UTF-8"))
    return chart


def _characteristic_chart(root, belonging, object_uuid, *, base_uuid=None):
    node = etree.Element(
        f"{{{MD}}}MetaDataObject",
        nsmap={None: MD, "v8": editor.V8, "xr": borrow.XR, "xsi": predefined.XSI, "cfg": borrow.CFG},
        version="2.20",
    )
    chart = etree.SubElement(node, f"{{{MD}}}ChartOfCharacteristicTypes", uuid=object_uuid)
    internal = etree.SubElement(chart, f"{{{MD}}}InternalInfo")
    values = {"ObjectBelonging": belonging, "Name": TYPE_NAME}
    if belonging == "Native":
        values.update(
            {"CodeLength": "5", "CodeAllowedLength": "Fixed", "DescriptionLength": "50", "Hierarchical": "false"}
        )
    if base_uuid:
        values["ExtendedConfigurationObject"] = base_uuid
    props = _properties(chart, values)
    type_node = etree.SubElement(props, f"{{{MD}}}Type")
    if belonging == "Native":
        for logical in ("CatalogRef.Субконто", "CatalogRef.ВидыВзаиморасчетов", "DocumentRef.ДокументТест"):
            etree.SubElement(type_node, f"{{{editor.V8}}}Type").text = f"cfg:{logical}"
    else:
        type_node.set(f"{{{predefined.XSI}}}type", "xr:ExtendedProperty")
        state = etree.SubElement(internal, f"{{{borrow.XR}}}PropertyState")
        etree.SubElement(state, f"{{{borrow.XR}}}Property").text = "Type"
        etree.SubElement(state, f"{{{borrow.XR}}}State").text = "MultiState"
        extend = etree.SubElement(
            type_node, f"{{{borrow.XR}}}ExtendValue", attrib={f"{{{predefined.XSI}}}type": "v8:TypeDescription"}
        )
        etree.SubElement(extend, f"{{{editor.V8}}}Type").text = "cfg:CatalogRef.Демо_Заказы"
    etree.SubElement(chart, f"{{{MD}}}ChildObjects")
    path = root / "ChartsOfCharacteristicTypes" / f"{TYPE_NAME}.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(etree.tostring(node, xml_declaration=True, encoding="UTF-8"))
    return chart


def _configuration(root, object_uuid, *, extension, registrations):
    node = etree.Element(f"{{{MD}}}MetaDataObject", nsmap={None: MD}, version="2.20")
    config = etree.SubElement(node, f"{{{MD}}}Configuration", uuid=object_uuid)
    values = {"Name": "TestExtension" if extension else "TestBase"}
    if extension:
        values.update(
            {"ConfigurationExtensionPurpose": "Customization", "KeepMappingToExtendedConfigurationObjectsByIDs": "true"}
        )
    _properties(config, values)
    children = etree.SubElement(config, f"{{{MD}}}ChildObjects")
    for kind, name in registrations:
        etree.SubElement(children, f"{{{MD}}}{kind}").text = name
    (root / "Configuration.xml").write_bytes(etree.tostring(node, xml_declaration=True, encoding="UTF-8"))


def _predefined(folder, items, *, type_name="ChartOfAccountsPredefinedItems"):
    tree = etree.Element(
        f"{{{EXT}}}PredefinedData",
        nsmap={None: EXT, "v8": editor.V8, "xr": borrow.XR, "xs": editor.XS, "xsi": predefined.XSI},
        attrib={f"{{{predefined.XSI}}}type": type_name, "version": "2.20"},
    )
    for name, item_id, parent, state in items:
        item = etree.SubElement(parent if parent is not None else tree, f"{{{EXT}}}Item", id=item_id)
        etree.SubElement(item, f"{{{EXT}}}Name").text = name
        etree.SubElement(item, f"{{{EXT}}}Code").text = item_id[-4:]
        etree.SubElement(item, f"{{{EXT}}}Description").text = name
        if type_name == "ChartOfAccountsPredefinedItems":
            etree.SubElement(item, f"{{{EXT}}}AccountType").text = "Active"
            etree.SubElement(item, f"{{{EXT}}}OffBalance").text = "false"
            etree.SubElement(item, f"{{{EXT}}}Order")
            etree.SubElement(item, f"{{{EXT}}}AccountingFlags")
        else:
            etree.SubElement(item, f"{{{EXT}}}Type")
            etree.SubElement(item, f"{{{EXT}}}IsFolder").text = "false"
        if state:
            etree.SubElement(item, f"{{{EXT}}}ExtensionState").text = state
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Predefined.xml").write_bytes(etree.tostring(tree, xml_declaration=True, encoding="UTF-8"))
    return tree


def fixture(tmp_path, *, native_parent=False, base_parent=False):
    base, target = tmp_path / "base", tmp_path / "extension"
    base.mkdir()
    target.mkdir()
    _configuration(
        base,
        BASE_ID,
        extension=False,
        registrations=[("ChartOfAccounts", CHART_NAME), ("ChartOfCharacteristicTypes", TYPE_NAME)],
    )
    _configuration(
        target,
        EXT_ID,
        extension=True,
        registrations=[("ChartOfAccounts", CHART_NAME), ("ChartOfCharacteristicTypes", TYPE_NAME)],
    )
    _chart(base, "Native", CHART_ID)
    _chart(target, "Adopted", str(uuid.uuid4()), base_uuid=CHART_ID)
    _characteristic_chart(base, "Native", TYPE_ID)
    _characteristic_chart(target, "Adopted", str(uuid.uuid4()), base_uuid=TYPE_ID)
    _predefined(
        base / "ChartsOfCharacteristicTypes" / TYPE_NAME / "Ext",
        [("BaseSubkonto", "00000000-0000-0000-0000-000000000202", None, None)],
        type_name="PlanOfCharacteristicKindPredefinedItems",
    )
    _add_predef_type(base / "ChartsOfCharacteristicTypes" / TYPE_NAME / "Ext", "BaseSubkonto", "CatalogRef.Субконто")
    _predefined(
        target / "ChartsOfCharacteristicTypes" / TYPE_NAME / "Ext",
        [("Демо_Контрагенты", "00000000-0000-0000-0000-000000000201", None, "Native")],
        type_name="PlanOfCharacteristicKindPredefinedItems",
    )
    _add_predef_type(
        target / "ChartsOfCharacteristicTypes" / TYPE_NAME / "Ext", "Демо_Контрагенты", "CatalogRef.Демо_Заказы"
    )
    if base_parent:
        base_predefined = _predefined(
            base / "ChartsOfAccounts" / CHART_NAME / "Ext",
            [("BaseParent", "00000000-0000-0000-0000-000000000101", None, None)],
        )
        root_parent = base_predefined.find(f"{{{EXT}}}Item")
        children = etree.SubElement(root_parent, f"{{{EXT}}}ChildItems")
        child = etree.SubElement(children, f"{{{EXT}}}Item", id="00000000-0000-0000-0000-000000000111")
        for key, value in [
            ("Name", "BaseChild"),
            ("Code", "000.01"),
            ("Description", "Base child"),
            ("AccountType", "Active"),
            ("OffBalance", "false"),
        ]:
            etree.SubElement(child, f"{{{EXT}}}{key}").text = value
        etree.SubElement(child, f"{{{EXT}}}Order")
        etree.SubElement(child, f"{{{EXT}}}AccountingFlags")
        base_flags = {"Валютный": False, "Количественный": True, "УчетПоПодразделениям": True, "НалоговыйУчет": True}
        for item in (root_parent, child):
            flags = item.find(f"{{{EXT}}}AccountingFlags")
            for flag_name, value in base_flags.items():
                flag = etree.SubElement(
                    flags, f"{{{EXT}}}Flag", ref=f"ChartOfAccounts.{CHART_NAME}.AccountingFlag.{flag_name}"
                )
                flag.text = str(value).lower()
        dimensions = etree.SubElement(child, f"{{{EXT}}}ExtDimensionTypes")
        dimension = etree.SubElement(
            dimensions, f"{{{EXT}}}ExtDimensionType", name="00000000-0000-0000-0000-000000000202"
        )
        etree.SubElement(dimension, f"{{{EXT}}}Turnover").text = "false"
        dimension_flags = etree.SubElement(dimension, f"{{{EXT}}}AccountingFlags")
        for flag_name, value in DIMENSION_FLAGS.items():
            flag = etree.SubElement(
                dimension_flags,
                f"{{{EXT}}}Flag",
                ref=f"ChartOfAccounts.{CHART_NAME}.ExtDimensionAccountingFlag.{flag_name}",
            )
            flag.text = str(value).lower()
        (base / "ChartsOfAccounts" / CHART_NAME / "Ext" / "Predefined.xml").write_bytes(
            etree.tostring(base_predefined, xml_declaration=True, encoding="UTF-8")
        )
    if native_parent:
        _predefined(
            target / "ChartsOfAccounts" / CHART_NAME / "Ext",
            [("NativeParent", "00000000-0000-0000-0000-000000000102", None, "Native")],
        )
    return target, base


def _add_predef_type(folder, name, logical_type):
    tree = editor.xml_read((folder / "Predefined.xml").read_bytes(), f"{{{EXT}}}PredefinedData")
    item = next(item for item in tree.findall(f".//{{{EXT}}}Item") if item.findtext(f"{{{EXT}}}Name") == name)
    etree.SubElement(
        item.find(f"{{{EXT}}}Type"), f"{{{editor.V8}}}Type", nsmap={"cfg": borrow.CFG}
    ).text = f"cfg:{logical_type}"
    (folder / "Predefined.xml").write_bytes(etree.tostring(tree, xml_declaration=True, encoding="UTF-8"))


def request(base, *, parent=None, name="Демо_РИДВнеНМА"):
    return {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "predefined.create",
                "target": f"ChartOfAccounts.{CHART_NAME}",
                "parameters": {
                    "baseRoot": str(base),
                    "name": name,
                    "code": "016",
                    "description": "РИД вне НМА",
                    "accountType": "Active",
                    "offBalance": False,
                    "parent": parent,
                    "accountingFlags": ACCOUNT_FLAGS,
                    "extDimensions": [
                        {
                            "name": f"ChartOfCharacteristicTypes.{TYPE_NAME}.Демо_Контрагенты",
                            "turnover": False,
                            "accountingFlags": DIMENSION_FLAGS,
                        }
                    ],
                },
            }
        ],
    }


def characteristic_request(base):
    values = [
        ("Демо_Заказы", "ДМО60", "Заказы", "CatalogRef.Демо_Заказы"),
        ("Демо_ТипРасчетов", "ДМО61", "Тип расчетов", "CatalogRef.ВидыВзаиморасчетов"),
        ("Демо_Корректировки", "ДМОКР", "Корректировки", "CatalogRef.Субконто"),
    ]
    return {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "predefined.create",
                "target": f"{CHARACTERISTIC_CHART}.{TYPE_NAME}",
                "parameters": {
                    "baseRoot": str(base),
                    "name": name,
                    "code": code,
                    "description": description,
                    "type": item_type,
                    "isFolder": False,
                },
            }
            for name, code, description, item_type in values
        ],
    }


def test_plan_adds_cfe_native_account_and_copies_controlled_lengths_deterministically(tmp_path):
    target, base = fixture(tmp_path)
    payload = request(base)
    plan1 = editor.plan_make(editor.Snapshot(target), payload)
    plan2 = editor.plan_make(editor.Snapshot(target), payload)
    paths = {write["path"] for write in plan1["writes"]}
    assert paths == {
        f"ChartsOfAccounts/{CHART_NAME}.xml",
        f"ChartsOfAccounts/{CHART_NAME}/Ext/Predefined.xml",
    }
    assert plan1["writes"] == plan2["writes"]
    after = next(write["after"]["sha256"] for write in plan1["writes"] if write["path"].endswith("/Predefined.xml"))
    assert after
    descriptor_after = next(write for write in plan1["writes"] if write["path"] == f"ChartsOfAccounts/{CHART_NAME}.xml")
    chart = editor.xml_read(present(editor.state_bytes(descriptor_after["after"])), f"{{{MD}}}MetaDataObject").find(
        f"{{{MD}}}ChartOfAccounts"
    )
    assert not chart.findall(f"{{{MD}}}InternalInfo/{{{borrow.XR}}}PropertyState")
    assert {
        field.tag.rsplit("}", 1)[-1]: field.text
        for field in chart.findall(f"{{{MD}}}Properties/*")
        if field.tag.rsplit("}", 1)[-1].endswith("Length")
    } == {"CodeLength": "8", "DescriptionLength": "120", "OrderLength": "8"}
    assert chart.findtext(f"{{{MD}}}Properties/{{{MD}}}ExtDimensionTypes") == (
        f"ChartOfCharacteristicTypes.{TYPE_NAME}"
    )
    assert chart.findtext(f"{{{MD}}}Properties/{{{MD}}}MaxExtDimensionCount") == "3"
    for kind, expected in [("AccountingFlag", ACCOUNT_FLAGS), ("ExtDimensionAccountingFlag", DIMENSION_FLAGS)]:
        members = chart.findall(f"{{{MD}}}ChildObjects/{{{MD}}}{kind}")
        assert {member.findtext(f"{{{MD}}}Properties/{{{MD}}}Name") for member in members} == set(expected)
        for member in members:
            props = member.find(f"{{{MD}}}Properties")
            assert props.findtext(f"{{{MD}}}ObjectBelonging") == "Adopted"
            assert props.findtext(f"{{{MD}}}ExtendedConfigurationObject")
            assert props.findtext(f"{{{MD}}}Type/{{{editor.V8}}}Type") == "xs:boolean"


def test_create_inspect_verify_characteristic_native_values_and_resolve_target_uuid(tmp_path, capsys):
    target, base = fixture(tmp_path)
    payload = characteristic_request(base)
    plan = editor.plan_make(editor.Snapshot(target), payload)
    predef_write = next(
        write
        for write in plan["writes"]
        if write["path"].endswith("/Predefined.xml")
        and write["path"].startswith(f"ChartsOfCharacteristicTypes/{TYPE_NAME}/")
    )
    generated = editor.xml_read(present(editor.state_bytes(predef_write["after"])), f"{{{EXT}}}PredefinedData")
    assert [item.findtext(f"{{{EXT}}}Name") for item in generated.findall(f"{{{EXT}}}Item")][-3:] == [
        "Демо_Заказы",
        "Демо_ТипРасчетов",
        "Демо_Корректировки",
    ]
    assert all(
        item.findtext(f"{{{EXT}}}IsFolder") == "false" and item.findtext(f"{{{EXT}}}ExtensionState") == "Native"
        for item in generated.findall(f"{{{EXT}}}Item")[-3:]
    )
    descriptor_write = next(
        write for write in plan["writes"] if write["path"] == f"ChartsOfCharacteristicTypes/{TYPE_NAME}.xml"
    )
    descriptor = editor.xml_read(present(editor.state_bytes(descriptor_write["after"])), f"{{{MD}}}MetaDataObject")
    chart = descriptor.find(f"{{{MD}}}ChartOfCharacteristicTypes")
    properties = chart.find(f"{{{MD}}}Properties")
    states = {
        state.findtext(f"{{{borrow.XR}}}Property"): state.findtext(f"{{{borrow.XR}}}State")
        for state in chart.findall(f"{{{MD}}}InternalInfo/{{{borrow.XR}}}PropertyState")
    }
    assert states == {"Type": "MultiState", "Predefined": "Extended"}
    assert properties.findtext(f"{{{MD}}}CodeLength") == "5"
    assert properties.findtext(f"{{{MD}}}CodeAllowedLength") == "Fixed"
    assert properties.findtext(f"{{{MD}}}DescriptionLength") == "50"
    assert properties.findtext(f"{{{MD}}}Hierarchical") == "false"
    assert "CatalogRef.Демо_Заказы" in predefined._characteristic_types(chart)
    base_chart = editor.xml_read(
        (base / "ChartsOfCharacteristicTypes" / f"{TYPE_NAME}.xml").read_bytes(), f"{{{MD}}}MetaDataObject"
    ).find(f"{{{MD}}}ChartOfCharacteristicTypes")
    assert "CatalogRef.Субконто" in predefined._characteristic_types(base_chart)
    assert editor.apply(target, None, plan) == "applied"
    predefined.verify(editor.Snapshot(target), f"{CHARACTERISTIC_CHART}.{TYPE_NAME}", str(base))

    assert (
        editor.main(
            [
                "inspect",
                "--root",
                str(target),
                "--object",
                f"{CHARACTERISTIC_CHART}.{TYPE_NAME}",
                "--base-root",
                str(base),
                "--mode",
                "brief",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)["changes"]
    assert {"property": "Type", "state": "MultiState"} in report["propertyStates"]
    scalar = {item["name"]: item["value"] for item in report["scalarProperties"]}
    assert scalar["CodeLength"] == "5" and scalar["DescriptionLength"] == "50"
    assert scalar["CodeAllowedLength"] == "Fixed"
    assert scalar["Hierarchical"] == "false"
    type_summary = report["typeSummary"][0]
    assert type_summary["checkValue"] == []
    assert type_summary["extendValue"] == [["cfg:CatalogRef.Демо_Заказы"]]
    items = report["predefinedItems"]
    orders = next(item for item in items if item["name"] == "Демо_Заказы")
    assert orders["type"] == "CatalogRef.Демо_Заказы" and orders["isFolder"] is False

    account_payload = request(base)
    account_parameters = account_payload["operations"][0]["parameters"]
    account_parameters["extDimensions"] = [
        {
            "name": f"{CHARACTERISTIC_CHART}.{TYPE_NAME}.Демо_Заказы",
            "turnover": False,
            "accountingFlags": DIMENSION_FLAGS,
        }
    ]
    account_plan = editor.plan_make(editor.Snapshot(target), account_payload)
    assert editor.apply(target, None, account_plan) == "applied"
    account_path = target / "ChartsOfAccounts" / CHART_NAME / "Ext" / "Predefined.xml"
    account_root = editor.xml_read(account_path.read_bytes(), f"{{{EXT}}}PredefinedData")
    dimension = account_root.find(f".//{{{EXT}}}ExtDimensionType")
    dimension.set("name", orders["id"])
    account_path.write_bytes(etree.tostring(account_root, xml_declaration=True, encoding="UTF-8"))
    inspected = editor.inspect_object(editor.Snapshot(target), f"ChartOfAccounts.{CHART_NAME}", base_root=str(base))
    assert inspected["predefinedItems"][0]["extDimensionTypes"] == [f"{CHARACTERISTIC_CHART}.{TYPE_NAME}.Демо_Заказы"]
    predefined.verify(editor.Snapshot(target), f"ChartOfAccounts.{CHART_NAME}", str(base))


def test_repeated_characteristic_create_repairs_missing_hierarchical_without_rewriting_items(tmp_path):
    target, base = fixture(tmp_path)
    payload = characteristic_request(base)
    first_plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, first_plan) == "applied"

    descriptor_path = target / "ChartsOfCharacteristicTypes" / f"{TYPE_NAME}.xml"
    original = descriptor_path.read_bytes()
    root = editor.xml_read(original, f"{{{MD}}}MetaDataObject")
    chart = root.find(f"{{{MD}}}ChartOfCharacteristicTypes")
    hierarchical = chart.find(f"{{{MD}}}Properties/{{{MD}}}Hierarchical")
    assert hierarchical is not None and hierarchical.text == "false"
    chart.find(f"{{{MD}}}Properties").remove(hierarchical)
    descriptor_path.write_bytes(editor.serialize_like(root, original))

    repair_plan = editor.plan_make(editor.Snapshot(target), payload)
    assert {write["path"] for write in repair_plan["writes"]} == {f"ChartsOfCharacteristicTypes/{TYPE_NAME}.xml"}
    repaired = editor.xml_read(
        present(editor.state_bytes(repair_plan["writes"][0]["after"])), f"{{{MD}}}MetaDataObject"
    )
    assert repaired.findtext(f"{{{MD}}}ChartOfCharacteristicTypes/{{{MD}}}Properties/{{{MD}}}Hierarchical") == "false"
    assert editor.apply(target, None, repair_plan) == "applied"
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []


def test_inspect_keeps_characteristic_descriptor_diagnostics_when_predefined_item_is_unreadable(tmp_path, capsys):
    target, base = fixture(tmp_path)
    path = base / "ChartsOfCharacteristicTypes" / TYPE_NAME / "Ext" / "Predefined.xml"
    tree = editor.xml_read(path.read_bytes(), f"{{{EXT}}}PredefinedData")
    item = tree.find(f"{{{EXT}}}Item")
    item.remove(item.find(f"{{{EXT}}}IsFolder"))
    path.write_bytes(etree.tostring(tree, xml_declaration=True, encoding="UTF-8"))
    assert (
        editor.main(
            ["inspect", "--root", str(base), "--object", f"{CHARACTERISTIC_CHART}.{TYPE_NAME}", "--mode", "brief"]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    inspected = result["changes"]
    assert {"name": "Name", "value": TYPE_NAME} in inspected["scalarProperties"]
    assert inspected["predefinedItemsError"]["message"] == editor.PUBLIC_ERRORS[4]
    assert inspected["predefinedItemsTotal"] is None


def test_apply_is_idempotent_for_a_root_account_plan(tmp_path):
    target, base = fixture(tmp_path)
    plan = editor.plan_make(editor.Snapshot(target), request(base))
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    repeat = editor.plan_make(editor.Snapshot(target), request(base))
    assert repeat["writes"] == []


def test_update_native_account_preserves_identity_dimensions_and_children(tmp_path):
    target, base = fixture(tmp_path)
    created = request(base)
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), created))
    child = request(base, parent="Демо_РИДВнеНМА", name="Демо_Дочерний")
    child["operations"][0]["parameters"]["code"] = "016.1"
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), child))
    path = target / "ChartsOfAccounts" / CHART_NAME / "Ext" / "Predefined.xml"
    before = etree.fromstring(path.read_bytes())
    update = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "predefined.update",
                "target": f"ChartOfAccounts.{CHART_NAME}",
                "parameters": {
                    "baseRoot": str(base),
                    "name": "Демо_РИДВнеНМА",
                    "accountType": "ActivePassive",
                    "accountingFlags": {**ACCOUNT_FLAGS, "НалоговыйУчет": True},
                },
            }
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), update)
    assert [w["path"] for w in plan["writes"]] == [f"ChartsOfAccounts/{CHART_NAME}/Ext/Predefined.xml"]
    editor.apply(target, None, plan)
    after = etree.fromstring(path.read_bytes())
    expected = before.find(f"{{{EXT}}}Item")
    expected.find(f"{{{EXT}}}AccountType").text = "ActivePassive"
    expected.find(
        f'{{{EXT}}}AccountingFlags/{{{EXT}}}Flag[@ref="ChartOfAccounts.{CHART_NAME}.AccountingFlag.НалоговыйУчет"]'
    ).text = "true"
    assert etree.tostring(before) == etree.tostring(after)
    assert editor.plan_make(editor.Snapshot(target), update)["writes"] == []
    with pytest.raises(editor.Rejected, match="conflicts"):
        editor.plan_make(editor.Snapshot(target), created)
    for mutation in ("missing", "adopted", "foreign-id"):
        damaged = etree.fromstring(path.read_bytes())
        item = damaged.find(f"{{{EXT}}}Item")
        if mutation == "missing":
            damaged.remove(item)
        elif mutation == "adopted":
            item.find(f"{{{EXT}}}ExtensionState").text = "AdoptedCheck"
        else:
            item.set("id", str(uuid.uuid4()))
        path.write_bytes(etree.tostring(damaged))
        with pytest.raises(editor.Rejected):
            editor.plan_make(editor.Snapshot(target), update)
        path.write_bytes(etree.tostring(after))


def test_update_moves_native_account_under_base_parent_keeping_identity(tmp_path):
    target, base = fixture(tmp_path, base_parent=True)
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), request(base)))
    path = target / "ChartsOfAccounts" / CHART_NAME / "Ext" / "Predefined.xml"
    before = etree.fromstring(path.read_bytes()).find(f"{{{EXT}}}Item")
    account_id = before.get("id")
    update = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "predefined.update",
                "target": f"ChartOfAccounts.{CHART_NAME}",
                "parameters": {
                    "baseRoot": str(base),
                    "name": "Демо_РИДВнеНМА",
                    "accountType": "Active",
                    "accountingFlags": ACCOUNT_FLAGS,
                    "parent": "BaseChild",
                },
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), update))
    items = {
        name: (node, parent, state)
        for node, name, parent, state in predefined._items(etree.fromstring(path.read_bytes()))
    }
    assert items["Демо_РИДВнеНМА"][1] == "BaseChild"
    assert items["Демо_РИДВнеНМА"][0].get("id") == account_id
    assert items["BaseChild"][2] == "AdoptedCheck" and items["BaseParent"][2] == "AdoptedCheck"
    assert editor.plan_make(editor.Snapshot(target), update)["writes"] == []
    predefined.verify(editor.Snapshot(target), f"ChartOfAccounts.{CHART_NAME}", str(base))
    update["operations"][0]["parameters"]["parent"] = "Демо_РИДВнеНМА"
    with pytest.raises(editor.Rejected, match="descendant"):
        editor.plan_make(editor.Snapshot(target), update)
    update["operations"][0]["parameters"]["parent"] = None
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), update))
    root = etree.fromstring(path.read_bytes())
    items = {name: (node, parent) for node, name, parent, _ in predefined._items(root)}
    assert items["Демо_РИДВнеНМА"][1] is None
    assert items["BaseChild"][0].find(f"{{{EXT}}}ChildItems") is None


def test_update_sets_native_account_order_and_keeps_create_idempotent(tmp_path):
    target, base = fixture(tmp_path)
    create = request(base)
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), create))
    path = target / "ChartsOfAccounts" / CHART_NAME / "Ext" / "Predefined.xml"
    update = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "predefined.update",
                "target": f"ChartOfAccounts.{CHART_NAME}",
                "parameters": {
                    "baseRoot": str(base),
                    "name": "Демо_РИДВнеНМА",
                    "accountType": "Active",
                    "accountingFlags": ACCOUNT_FLAGS,
                    "order": "016",
                },
            }
        ],
    }
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), update))
    items = {name: node for node, name, _, _ in predefined._items(etree.fromstring(path.read_bytes()))}
    assert items["Демо_РИДВнеНМА"].findtext(f"{{{EXT}}}Order") == "016"
    assert editor.plan_make(editor.Snapshot(target), update)["writes"] == []
    assert editor.plan_make(editor.Snapshot(target), create)["writes"] == []
    predefined.verify(editor.Snapshot(target), f"ChartOfAccounts.{CHART_NAME}", str(base))
    update["operations"][0]["parameters"]["order"] = " "
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), update)


def test_identical_create_preserves_unrelated_internal_property_state(tmp_path):
    target, base = fixture(tmp_path)
    payload = request(base)
    create_plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, create_plan) == "applied"
    predef_path = target / "ChartsOfAccounts" / CHART_NAME / "Ext" / "Predefined.xml"
    predefined_before = predef_path.read_bytes()
    descriptor = target / "ChartsOfAccounts" / f"{CHART_NAME}.xml"
    descriptor_tree = editor.xml_read(descriptor.read_bytes(), f"{{{MD}}}MetaDataObject")
    chart = descriptor_tree.find(f"{{{MD}}}ChartOfAccounts")
    internal = chart.find(f"{{{MD}}}InternalInfo")
    state = etree.SubElement(internal, f"{{{borrow.XR}}}PropertyState")
    etree.SubElement(state, f"{{{borrow.XR}}}Property").text = "Predefined"
    etree.SubElement(state, f"{{{borrow.XR}}}State").text = "Extended"
    descriptor.write_bytes(etree.tostring(descriptor_tree, xml_declaration=True, encoding="UTF-8"))
    descriptor_before_replay = descriptor.read_bytes()

    repair_plan = editor.plan_make(editor.Snapshot(target), payload)
    assert repair_plan["writes"] == []
    assert descriptor.read_bytes() == descriptor_before_replay
    assert len(chart.findall(f"{{{MD}}}InternalInfo/{{{borrow.XR}}}PropertyState")) == 1
    assert predef_path.read_bytes() == predefined_before
    predefined.verify(editor.Snapshot(target), f"ChartOfAccounts.{CHART_NAME}")


@pytest.mark.parametrize("damage", ["missing-length", "missing-flag-member"])
def test_verify_rejects_native_accounts_without_borrowed_chart_dependencies(tmp_path, damage):
    target, base = fixture(tmp_path)
    plan = editor.plan_make(editor.Snapshot(target), request(base))
    assert editor.apply(target, None, plan) == "applied"
    descriptor = target / "ChartsOfAccounts" / f"{CHART_NAME}.xml"
    tree = editor.xml_read(descriptor.read_bytes(), f"{{{MD}}}MetaDataObject")
    chart = tree.find(f"{{{MD}}}ChartOfAccounts")
    if damage == "missing-length":
        chart.find(f"{{{MD}}}Properties/{{{MD}}}CodeLength").getparent().remove(
            chart.find(f"{{{MD}}}Properties/{{{MD}}}CodeLength")
        )
    else:
        flag = chart.find(f"{{{MD}}}ChildObjects/{{{MD}}}AccountingFlag")
        flag.getparent().remove(flag)
    descriptor.write_bytes(etree.tostring(tree, xml_declaration=True, encoding="UTF-8"))
    with pytest.raises(editor.Rejected, match="Native predefined account|Native predefined accounts require chart"):
        predefined.verify(editor.Snapshot(target), f"ChartOfAccounts.{CHART_NAME}")


def test_adopted_chart_length_property_mismatch_is_rejected(tmp_path):
    target, base = fixture(tmp_path)
    descriptor = target / "ChartsOfAccounts" / f"{CHART_NAME}.xml"
    tree = editor.xml_read(descriptor.read_bytes(), f"{{{MD}}}MetaDataObject")
    chart = tree.find(f"{{{MD}}}ChartOfAccounts")
    properties = chart.find(f"{{{MD}}}Properties")
    etree.SubElement(properties, f"{{{MD}}}CodeLength").text = "7"
    descriptor.write_bytes(etree.tostring(tree, xml_declaration=True, encoding="UTF-8"))
    with pytest.raises(editor.Rejected, match="Adopted chart CodeLength differs from base"):
        editor.plan_make(editor.Snapshot(target), request(base))


def test_add_under_existing_native_parent_and_inspect_pages_items(tmp_path):
    target, base = fixture(tmp_path, native_parent=True)
    plan = editor.plan_make(editor.Snapshot(target), request(base, parent="NativeParent"))
    raw = next(write for write in plan["writes"] if write["path"].endswith("/Predefined.xml"))
    root = editor.xml_read(present(editor.state_bytes(raw["after"])), f"{{{EXT}}}PredefinedData")
    parent = root.find(f'.//{{{EXT}}}Item[{{{EXT}}}Name="NativeParent"]')
    child = parent.find(f"{{{EXT}}}ChildItems/{{{EXT}}}Item")
    assert child.findtext(f"{{{EXT}}}Name") == "Демо_РИДВнеНМА"
    assert child.findtext(f"{{{EXT}}}ExtensionState") == "Native"
    inspected = editor.inspect_object(editor.Snapshot(target), f"ChartOfAccounts.{CHART_NAME}", limit=1)
    assert inspected["predefinedItemsTotal"] == 1
    assert inspected["predefinedItems"][0]["parent"] is None
    assert inspected["predefinedItemsNextOffset"] is None


def test_native_account_parent_remains_idempotent_after_receiving_child(tmp_path):
    target, base = fixture(tmp_path, native_parent=True)
    payload = request(base, parent="NativeParent")
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    repeat = editor.plan_make(editor.Snapshot(target), payload)
    assert repeat["writes"] == []


def test_reordered_subkonto_list_conflicts_with_existing_native_account(tmp_path):
    target, base = fixture(tmp_path)
    payload = request(base)
    payload["operations"][0]["parameters"]["extDimensions"] = [
        {
            "name": f"{CHARACTERISTIC_CHART}.{TYPE_NAME}.Демо_Контрагенты",
            "turnover": False,
            "accountingFlags": DIMENSION_FLAGS,
        },
        {
            "name": f"{CHARACTERISTIC_CHART}.{TYPE_NAME}.BaseSubkonto",
            "turnover": False,
            "accountingFlags": DIMENSION_FLAGS,
        },
    ]
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert editor.apply(target, None, plan) == "applied"
    path = target / "ChartsOfAccounts" / CHART_NAME / "Ext" / "Predefined.xml"
    root = editor.xml_read(path.read_bytes(), f"{{{EXT}}}PredefinedData")
    dimensions = root.find(f".//{{{EXT}}}ExtDimensionTypes")
    dimensions[:] = list(reversed(list(dimensions)))
    path.write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    with pytest.raises(editor.Rejected, match="Existing predefined account conflicts with request"):
        editor.plan_make(editor.Snapshot(target), payload)


def test_base_parent_chain_is_materialized_minimally_and_idempotently(tmp_path):
    target, base = fixture(tmp_path, base_parent=True)
    payload = request(base, parent="BaseChild")
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert plan == editor.plan_make(editor.Snapshot(target), payload)
    predef_write = next(
        write for write in plan["writes"] if write["path"] == f"ChartsOfAccounts/{CHART_NAME}/Ext/Predefined.xml"
    )
    root = editor.xml_read(present(editor.state_bytes(predef_write["after"])), f"{{{EXT}}}PredefinedData")
    adopted_root = root.find(f"{{{EXT}}}Item")
    assert adopted_root.findtext(f"{{{EXT}}}Name") == "BaseParent"
    assert adopted_root.findtext(f"{{{EXT}}}ExtensionState") == "AdoptedCheck"
    adopted_child = adopted_root.find(f"{{{EXT}}}ChildItems/{{{EXT}}}Item")
    assert adopted_child.findtext(f"{{{EXT}}}Name") == "BaseChild"
    assert adopted_child.findtext(f"{{{EXT}}}ExtensionState") == "AdoptedCheck"
    source_root = editor.xml_read(
        (base / "ChartsOfAccounts" / CHART_NAME / "Ext" / "Predefined.xml").read_bytes(), f"{{{EXT}}}PredefinedData"
    )
    source_child = source_root.find(f"{{{EXT}}}Item/{{{EXT}}}ChildItems/{{{EXT}}}Item")
    assert editor.signature(adopted_child.find(f"{{{EXT}}}AccountingFlags")) == editor.signature(
        source_child.find(f"{{{EXT}}}AccountingFlags")
    )
    assert editor.signature(adopted_child.find(f"{{{EXT}}}ExtDimensionTypes")) == editor.signature(
        source_child.find(f"{{{EXT}}}ExtDimensionTypes")
    )
    cht_write = next(
        write
        for write in plan["writes"]
        if write["path"] == f"ChartsOfCharacteristicTypes/{TYPE_NAME}/Ext/Predefined.xml"
    )
    cht_root = editor.xml_read(present(editor.state_bytes(cht_write["after"])), f"{{{EXT}}}PredefinedData")
    adopted_subkonto = next(
        item for item in cht_root.findall(f"{{{EXT}}}Item") if item.findtext(f"{{{EXT}}}Name") == "BaseSubkonto"
    )
    assert adopted_subkonto.findtext(f"{{{EXT}}}ExtensionState") == "AdoptedCheck"
    assert adopted_subkonto.findtext(f"{{{EXT}}}Code") == "0202"
    assert adopted_subkonto.findtext(f"{{{EXT}}}IsFolder") == "false"
    assert predefined._characteristic_item_type(adopted_subkonto) == "CatalogRef.Субконто"
    account = adopted_child.find(f"{{{EXT}}}ChildItems/{{{EXT}}}Item")
    assert account.findtext(f"{{{EXT}}}Name") == "Демо_РИДВнеНМА"
    assert account.findtext(f"{{{EXT}}}ExtensionState") == "Native"
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    assert editor.plan_make(editor.Snapshot(target), payload)["writes"] == []
    predefined.verify(editor.Snapshot(target), f"{CHARACTERISTIC_CHART}.{TYPE_NAME}", str(base))


def test_existing_generated_parent_analytics_are_repaired_and_saved_on_idempotent_account_request(tmp_path):
    target, base = fixture(tmp_path, base_parent=True)
    source_path = base / "ChartsOfAccounts" / CHART_NAME / "Ext" / "Predefined.xml"
    source = editor.xml_read(source_path.read_bytes(), f"{{{EXT}}}PredefinedData")
    extension_namespace = uuid.UUID(EXT_ID)
    target_root = etree.Element(
        f"{{{EXT}}}PredefinedData",
        nsmap={None: EXT, "xsi": predefined.XSI},
        attrib={f"{{{predefined.XSI}}}type": "ChartOfAccountsPredefinedItems", "version": "2.20"},
    )
    parent_node = None
    for source_node, item_name in [
        (source.find(f"{{{EXT}}}Item"), "BaseParent"),
        (source.find(f"{{{EXT}}}Item/{{{EXT}}}ChildItems/{{{EXT}}}Item"), "BaseChild"),
    ]:
        owner = f"ChartOfAccounts.{CHART_NAME}.Predefined.AdoptedCheck.{item_name}"
        adopted = etree.SubElement(
            parent_node if parent_node is not None else target_root,
            f"{{{EXT}}}Item",
            id=str(uuid.uuid5(extension_namespace, owner)),
        )
        for field in ("Name", "Code", "Description", "AccountType", "OffBalance", "Order"):
            value = source_node.find(f"{{{EXT}}}{field}")
            cloned = etree.SubElement(adopted, f"{{{EXT}}}{field}")
            cloned.text = value.text if value is not None else None
        etree.SubElement(adopted, f"{{{EXT}}}ExtensionState").text = "AdoptedCheck"
        etree.SubElement(adopted, f"{{{EXT}}}AccountingFlags")
        if parent_node is not None:
            children = etree.SubElement(parent_node, f"{{{EXT}}}ChildItems")
            children.append(adopted)
        parent_node = adopted
    native = etree.SubElement(
        etree.SubElement(parent_node, f"{{{EXT}}}ChildItems"),
        f"{{{EXT}}}Item",
        id=str(uuid.uuid5(extension_namespace, f"ChartOfAccounts.{CHART_NAME}.Predefined.Демо_РИДВнеНМА")),
    )
    for field, value in [
        ("Name", "Демо_РИДВнеНМА"),
        ("Code", "016"),
        ("Description", "РИД вне НМА"),
        ("AccountType", "Active"),
        ("OffBalance", "false"),
    ]:
        etree.SubElement(native, f"{{{EXT}}}{field}").text = value
    etree.SubElement(native, f"{{{EXT}}}Order")
    etree.SubElement(native, f"{{{EXT}}}ExtensionState").text = "Native"
    flags = etree.SubElement(native, f"{{{EXT}}}AccountingFlags")
    for flag, value in ACCOUNT_FLAGS.items():
        etree.SubElement(flags, f"{{{EXT}}}Flag", ref=f"ChartOfAccounts.{CHART_NAME}.AccountingFlag.{flag}").text = str(
            value
        ).lower()
    dimensions = etree.SubElement(native, f"{{{EXT}}}ExtDimensionTypes")
    dimension = etree.SubElement(
        dimensions, f"{{{EXT}}}ExtDimensionType", name=f"ChartOfCharacteristicTypes.{TYPE_NAME}.Демо_Контрагенты"
    )
    etree.SubElement(dimension, f"{{{EXT}}}Turnover").text = "false"
    dimension_flags = etree.SubElement(dimension, f"{{{EXT}}}AccountingFlags")
    for flag, value in DIMENSION_FLAGS.items():
        etree.SubElement(
            dimension_flags, f"{{{EXT}}}Flag", ref=f"ChartOfAccounts.{CHART_NAME}.ExtDimensionAccountingFlag.{flag}"
        ).text = str(value).lower()
    target_predefined = target / "ChartsOfAccounts" / CHART_NAME / "Ext" / "Predefined.xml"
    target_predefined.parent.mkdir(parents=True, exist_ok=True)
    target_predefined.write_bytes(etree.tostring(target_root, xml_declaration=True, encoding="UTF-8"))

    plan = editor.plan_make(editor.Snapshot(target), request(base, parent="BaseChild"))
    write = next(write for write in plan["writes"] if write["path"].endswith("/Predefined.xml"))
    assert write["before"]["sha256"] != write["after"]["sha256"]
    assert editor.apply(target, None, plan) == "applied"
    repaired = editor.xml_read(target_predefined.read_bytes(), f"{{{EXT}}}PredefinedData")
    repaired_child = repaired.find(f"{{{EXT}}}Item/{{{EXT}}}ChildItems/{{{EXT}}}Item")
    source_child = source.find(f"{{{EXT}}}Item/{{{EXT}}}ChildItems/{{{EXT}}}Item")
    assert predefined._flags(repaired_child, f"ChartOfAccounts.{CHART_NAME}.AccountingFlag.") == predefined._flags(
        source_child, f"ChartOfAccounts.{CHART_NAME}.AccountingFlag."
    )
    repaired_dimension = repaired_child.find(f"{{{EXT}}}ExtDimensionTypes/{{{EXT}}}ExtDimensionType")
    source_dimension = source_child.find(f"{{{EXT}}}ExtDimensionTypes/{{{EXT}}}ExtDimensionType")
    assert repaired_dimension.get("name") == source_dimension.get("name")
    assert predefined._bool(repaired_dimension.find(f"{{{EXT}}}Turnover")) is predefined._bool(
        source_dimension.find(f"{{{EXT}}}Turnover")
    )
    assert predefined._flags(
        repaired_dimension, f"ChartOfAccounts.{CHART_NAME}.ExtDimensionAccountingFlag."
    ) == predefined._flags(source_dimension, f"ChartOfAccounts.{CHART_NAME}.ExtDimensionAccountingFlag.")


def test_conflicting_existing_adoptedcheck_parent_is_rejected(tmp_path):
    target, base = fixture(tmp_path, base_parent=True)
    _predefined(
        target / "ChartsOfAccounts" / CHART_NAME / "Ext",
        [("BaseParent", "00000000-0000-0000-0000-000000000112", None, "AdoptedCheck")],
    )
    with pytest.raises(editor.Rejected, match="Existing base parent account conflicts with AdoptedCheck"):
        editor.plan_make(editor.Snapshot(target), request(base, parent="BaseParent"))


def test_duplicate_name_and_case_insensitive_code_are_rejected(tmp_path):
    target, base = fixture(tmp_path, native_parent=True)
    existing = _predefined(
        target / "ChartsOfAccounts" / CHART_NAME / "Ext",
        [("Демо_РИДВнеНМА", "00000000-0000-0000-0000-000000000301", None, "Native")],
    )
    with pytest.raises(editor.Rejected, match="Existing predefined account conflicts with request"):
        editor.plan_make(editor.Snapshot(target), request(base))
    payload = request(base, name="Демо_Другой")
    payload["operations"][0]["parameters"]["code"] = "016"
    existing.find(f"{{{EXT}}}Item/{{{EXT}}}Code").text = "016"
    (target / "ChartsOfAccounts" / CHART_NAME / "Ext" / "Predefined.xml").write_bytes(etree.tostring(existing))
    with pytest.raises(editor.Rejected, match="Predefined account code already exists"):
        editor.plan_make(editor.Snapshot(target), payload)


def test_inspect_cli_paginates_predefined_items(tmp_path, capsys):
    target, base = fixture(tmp_path, native_parent=True)
    assert (
        editor.main(
            [
                "inspect",
                "--root",
                str(target),
                "--object",
                f"ChartOfAccounts.{CHART_NAME}",
                "--mode",
                "brief",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)["changes"]
    assert len(report["predefinedItems"]) == 1
    assert report["predefinedItemsTotal"] == 1


def test_inspect_and_verify_resolve_dumped_dimension_uuid_using_exact_base_root(tmp_path, capsys):
    target, base = fixture(tmp_path)
    plan = editor.plan_make(editor.Snapshot(target), request(base))
    assert editor.apply(target, None, plan) == "applied"
    predef_path = target / "ChartsOfAccounts" / CHART_NAME / "Ext" / "Predefined.xml"
    tree = editor.xml_read(predef_path.read_bytes(), f"{{{EXT}}}PredefinedData")
    dimension = tree.find(f".//{{{EXT}}}ExtDimensionType")
    dimension.set("name", "00000000-0000-0000-0000-000000000202")
    predef_path.write_bytes(etree.tostring(tree, xml_declaration=True, encoding="UTF-8"))

    assert (
        editor.main(
            ["inspect", "--root", str(target), "--object", f"ChartOfAccounts.{CHART_NAME}", "--base-root", str(base)]
        )
        == 0
    )
    inspected = json.loads(capsys.readouterr().out)["changes"]["predefinedItems"][0]
    refs = inspected["extDimensionTypeRefs"]
    assert refs == [
        {
            "raw": "00000000-0000-0000-0000-000000000202",
            "resolved": f"ChartOfCharacteristicTypes.{TYPE_NAME}.BaseSubkonto",
        }
    ]
    assert inspected["extDimensionTypes"] == [refs[0]["resolved"]]
    assert inspected["order"] == ""
    assert inspected["extDimensions"] == [
        {
            "name": refs[0]["resolved"],
            "rawRef": refs[0]["raw"],
            "turnover": False,
            "accountingFlags": DIMENSION_FLAGS,
        }
    ]
    assert (
        editor.main(
            ["verify", "--root", str(target), "--object", f"ChartOfAccounts.{CHART_NAME}", "--base-root", str(base)]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["checks"]["local"]["code"] == 0


def test_verify_rejects_unknown_dumped_dimension_uuid(tmp_path):
    target, base = fixture(tmp_path)
    plan = editor.plan_make(editor.Snapshot(target), request(base))
    assert editor.apply(target, None, plan) == "applied"
    predef_path = target / "ChartsOfAccounts" / CHART_NAME / "Ext" / "Predefined.xml"
    tree = editor.xml_read(predef_path.read_bytes(), f"{{{EXT}}}PredefinedData")
    tree.find(f".//{{{EXT}}}ExtDimensionType").set("name", "00000000-0000-0000-0000-000000000999")
    predef_path.write_bytes(etree.tostring(tree, xml_declaration=True, encoding="UTF-8"))
    with pytest.raises(editor.Rejected, match="Unknown base subkonto UUID"):
        predefined.verify(editor.Snapshot(target), f"ChartOfAccounts.{CHART_NAME}", base)


def test_normalize_dumped_dimension_uuid_preserves_payload_is_idempotent_and_rejects_unknown(tmp_path):
    target, base = fixture(tmp_path)
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), request(base)))
    path = target / "ChartsOfAccounts" / CHART_NAME / "Ext" / "Predefined.xml"
    tree = editor.xml_read(path.read_bytes(), f"{{{EXT}}}PredefinedData")
    dimension = tree.find(f".//{{{EXT}}}ExtDimensionType")
    dimension.set("name", "00000000-0000-0000-0000-000000000202")
    path.write_bytes(etree.tostring(tree, xml_declaration=True, encoding="UTF-8"))

    expected = etree.fromstring(path.read_bytes())
    expected.find(f".//{{{EXT}}}ExtDimensionType").set("name", f"ChartOfCharacteristicTypes.{TYPE_NAME}.BaseSubkonto")
    operation = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "predefined.normalize-dimension-refs",
                "target": f"ChartOfAccounts.{CHART_NAME}",
                "parameters": {"baseRoot": str(base)},
            }
        ],
    }
    plan = editor.plan_make(editor.Snapshot(target), operation)
    assert [write["path"] for write in plan["writes"]] == [f"ChartsOfAccounts/{CHART_NAME}/Ext/Predefined.xml"]
    assert editor.apply(target, None, plan) == "applied"
    actual = etree.fromstring(path.read_bytes())
    assert etree.tostring(actual) == etree.tostring(expected)
    assert editor.plan_make(editor.Snapshot(target), operation)["writes"] == []

    actual.find(f".//{{{EXT}}}ExtDimensionType").set("name", "00000000-0000-0000-0000-000000000999")
    path.write_bytes(etree.tostring(actual, xml_declaration=True, encoding="UTF-8"))
    before_rejected_plan = path.read_bytes()
    snapshot = editor.Snapshot(target)
    with pytest.raises(editor.Rejected, match="Unknown base subkonto UUID"):
        editor.plan_make(snapshot, operation)
    assert snapshot.writes == {}
    assert path.read_bytes() == before_rejected_plan


@pytest.mark.parametrize(
    "flags",
    [
        [
            ("ChartOfAccounts.Хозрасчетный.AccountingFlag.Валютный", "false"),
            ("ChartOfAccounts.Хозрасчетный.AccountingFlag.Валютный", "true"),
        ],
        [("Catalog.Хозрасчетный.AccountingFlag.Валютный", "false")],
        [("ChartOfAccounts.Хозрасчетный.AccountingFlag.Валютный", "yes")],
    ],
)
def test_verify_rejects_duplicate_foreign_or_invalid_accounting_flags(tmp_path, flags):
    target, _ = fixture(tmp_path, native_parent=True)
    path = target / "ChartsOfAccounts" / CHART_NAME / "Ext" / "Predefined.xml"
    tree = editor.xml_read(path.read_bytes(), f"{{{EXT}}}PredefinedData")
    item = tree.find(f"{{{EXT}}}Item")
    container = item.find(f"{{{EXT}}}AccountingFlags")
    for reference, value in flags:
        etree.SubElement(container, f"{{{EXT}}}Flag", ref=reference).text = value
    path.write_bytes(etree.tostring(tree, xml_declaration=True, encoding="UTF-8"))
    with pytest.raises(editor.Rejected):
        predefined.verify(editor.Snapshot(target), f"ChartOfAccounts.{CHART_NAME}")


CATALOG_NAME = "Демо_ТипыДокументовСканов"


def _catalog_fixture(tmp_path, *, code_length="0"):
    target = tmp_path / "catalog-extension"
    target.mkdir()
    _configuration(target, EXT_ID, extension=True, registrations=[("Catalog", CATALOG_NAME)])
    node = etree.Element(f"{{{MD}}}MetaDataObject", nsmap={None: MD, "v8": editor.V8, "xr": borrow.XR}, version="2.17")
    catalog = etree.SubElement(node, f"{{{MD}}}Catalog", uuid="fe84f470-6746-57f3-bf2c-da283e43385d")
    etree.SubElement(catalog, f"{{{MD}}}InternalInfo")
    _properties(
        catalog,
        {
            "ObjectBelonging": "Native",
            "Name": CATALOG_NAME,
            "Hierarchical": "false",
            "CodeLength": code_length,
            "DescriptionLength": "100",
        },
    )
    etree.SubElement(catalog, f"{{{MD}}}ChildObjects")
    path = target / "Catalogs" / f"{CATALOG_NAME}.xml"
    path.parent.mkdir(parents=True)
    path.write_bytes(etree.tostring(node, xml_declaration=True, encoding="UTF-8"))
    return target


def catalog_request(items):
    return {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "predefined.create",
                "target": f"Catalog.{CATALOG_NAME}",
                "parameters": parameters,
            }
            for parameters in items
        ],
    }


def test_catalog_predefined_items_match_designer_sample_and_replan_keeps_uuid(tmp_path):
    # Matches Predefined.xml that Designer 8.3.27 saves for an own catalog of an extension.
    target = _catalog_fixture(tmp_path)
    payload = catalog_request(
        [
            {"name": "РеализацияТоваровУслуг", "description": "Реализация (акты, накладные, УПД)"},
            {"name": "Демо_ПеремещениеМЦ02", "description": "Перемещение МЦ-02"},
        ]
    )
    plan = editor.plan_make(editor.Snapshot(target), payload)
    assert [write["path"] for write in plan["writes"]] == [f"Catalogs/{CATALOG_NAME}/Ext/Predefined.xml"]
    text = present(editor.state_bytes(plan["writes"][0]["after"])).decode("utf-8")
    assert "\n\t<Item id=" in text and "\n\t\t<Name>Демо_ПеремещениеМЦ02</Name>" in text
    root = editor.xml_read(present(editor.state_bytes(plan["writes"][0]["after"])), f"{{{EXT}}}PredefinedData")
    assert root.get(f"{{{predefined.XSI}}}type") == "CatalogPredefinedItems"
    assert root.get("version") == "2.17"
    items = root.findall(f"{{{EXT}}}Item")
    assert [[child.tag.rsplit("}", 1)[-1] for child in item] for item in items] == [
        ["Name", "Code", "Description", "IsFolder"]
    ] * 2
    assert [
        (item.findtext(f"{{{EXT}}}Name"), item.find(f"{{{EXT}}}Code").text, item.findtext(f"{{{EXT}}}IsFolder"))
        for item in items
    ] == [("РеализацияТоваровУслуг", None, "false"), ("Демо_ПеремещениеМЦ02", None, "false")]
    ids = [item.get("id") for item in items]
    assert editor.apply(target, None, plan) == "applied"
    predefined.verify(editor.Snapshot(target), f"Catalog.{CATALOG_NAME}")

    repeat = editor.plan_make(editor.Snapshot(target), payload)
    assert repeat["writes"] == []
    added = editor.plan_make(
        editor.Snapshot(target),
        catalog_request(
            [
                {"name": "РеализацияТоваровУслуг", "description": "Реализация (акты, накладные, УПД)"},
                {"name": "Демо_ПеремещениеМЦ02", "description": "Перемещение МЦ-02"},
                {"name": "СчетФактураВыданный", "description": "Счет-фактура выданный"},
            ]
        ),
    )
    grown = editor.xml_read(present(editor.state_bytes(added["writes"][0]["after"])), f"{{{EXT}}}PredefinedData")
    assert [item.get("id") for item in grown.findall(f"{{{EXT}}}Item")][:2] == ids
    inspected = editor.inspect_object(editor.Snapshot(target), f"Catalog.{CATALOG_NAME}")
    assert [(item["name"], item["id"]) for item in inspected["predefinedItems"]] == [
        ("РеализацияТоваровУслуг", ids[0]),
        ("Демо_ПеремещениеМЦ02", ids[1]),
    ]


def test_catalog_predefined_name_and_code_conflicts_are_rejected(tmp_path):
    target = _catalog_fixture(tmp_path, code_length="5")
    first = catalog_request([{"name": "РеализацияТоваровУслуг", "code": "РТУ", "description": "Реализация"}])
    assert editor.apply(target, None, editor.plan_make(editor.Snapshot(target), first)) == "applied"
    with pytest.raises(editor.Rejected, match="Existing predefined catalog item conflicts with request"):
        editor.plan_make(
            editor.Snapshot(target),
            catalog_request([{"name": "реализацияТоваровУслуг", "code": "РТУ", "description": "Другое"}]),
        )
    with pytest.raises(editor.Rejected, match="Predefined catalog code already exists"):
        editor.plan_make(
            editor.Snapshot(target),
            catalog_request([{"name": "Демо_ПеремещениеМЦ02", "code": "ртУ", "description": "Перемещение МЦ-02"}]),
        )
    with pytest.raises(editor.Rejected, match="Catalog code exceeds CodeLength"):
        editor.plan_make(
            editor.Snapshot(target),
            catalog_request(
                [{"name": "Демо_ПеремещениеМЦ02", "code": "Демо_МЦ02", "description": "Перемещение МЦ-02"}]
            ),
        )
