import tests.python.metadata_test_support  # noqa: F401, I001 — runs first: skips the module without pytest, lxml, jsonschema
import shutil
import uuid
import copy
from pathlib import Path

import lxml.etree as etree
import pytest

from scripts.python import metadata as editor
from scripts.python import metadata_borrow as borrow


FIXTURES = Path(__file__).parents[1] / "fixtures/managed-form-cli"
PREDEF = "http://v8.1c.ru/8.3/xcf/predef"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
CORE = editor.V8


def _object(kind, name, *, adopted=False, base_uuid=None):
    root = etree.Element(
        f"{{{editor.MD}}}MetaDataObject",
        nsmap={None: editor.MD, "xr": borrow.XR, "v8": editor.V8, "cfg": borrow.CFG, "d4p1": borrow.CFG, "xsi": XSI},
        version="2.17",
    )
    node = etree.SubElement(root, f"{{{editor.MD}}}{kind}", uuid=str(uuid.uuid4()))
    props = etree.SubElement(node, f"{{{editor.MD}}}Properties")
    if adopted:
        etree.SubElement(props, f"{{{editor.MD}}}ObjectBelonging").text = "Adopted"
    etree.SubElement(props, f"{{{editor.MD}}}Name").text = name
    if base_uuid:
        etree.SubElement(props, f"{{{editor.MD}}}ExtendedConfigurationObject").text = base_uuid
    children = etree.SubElement(node, f"{{{editor.MD}}}ChildObjects")
    if kind == "ChartOfAccounts":
        for child_kind, names in (
            ("AccountingFlag", ("Валютный", "Количественный", "УчетПоПодразделениям", "НалоговыйУчет")),
            ("ExtDimensionAccountingFlag", ("Суммовой", "Валютный", "Количественный")),
        ):
            for child_name in names:
                child = etree.SubElement(children, f"{{{editor.MD}}}{child_kind}", uuid=str(uuid.uuid4()))
                child_props = etree.SubElement(child, f"{{{editor.MD}}}Properties")
                etree.SubElement(child_props, f"{{{editor.MD}}}Name").text = child_name
    return root


def _predefined(kind, items):
    type_name = {
        "ChartOfAccounts": "ChartOfAccountsPredefinedItems",
        "ChartOfCharacteristicTypes": "PlanOfCharacteristicKindPredefinedItems",
    }[kind]
    root = etree.Element(
        f"{{{PREDEF}}}PredefinedData",
        nsmap={None: PREDEF, "v8": CORE, "xsi": XSI, "cfg": borrow.CFG},
        version="2.17",
        **{f"{{{XSI}}}type": type_name},
    )
    for item in items:
        root.append(item)
    return root


def _account_parent():
    item = etree.Element(f"{{{PREDEF}}}Item", id=str(uuid.uuid4()))
    for tag, value in (
        ("Name", "Родитель76"),
        ("Code", "76"),
        ("Description", "Родитель"),
        ("AccountType", "Active"),
        ("OffBalance", "false"),
        ("Order", "76"),
    ):
        etree.SubElement(item, f"{{{PREDEF}}}{tag}").text = value
    flags = etree.SubElement(item, f"{{{PREDEF}}}AccountingFlags")
    for name in ("Валютный", "Количественный", "УчетПоПодразделениям", "НалоговыйУчет"):
        etree.SubElement(
            flags, f"{{{PREDEF}}}Flag", ref=f"ChartOfAccounts.Хозрасчетный.AccountingFlag.{name}"
        ).text = "false"
    etree.SubElement(item, f"{{{PREDEF}}}ExtDimensionTypes")
    return item


def _characteristic_base():
    item = etree.Element(f"{{{PREDEF}}}Item", id=str(uuid.uuid4()))
    for tag, value in (("Name", "БазовыйВид"), ("Code", "1"), ("Description", "База")):
        etree.SubElement(item, f"{{{PREDEF}}}{tag}").text = value
    type_node = etree.SubElement(item, f"{{{PREDEF}}}Type")
    etree.SubElement(type_node, f"{{{CORE}}}Type", nsmap={"cfg": borrow.CFG}).text = "cfg:CatalogRef.Субконто"
    etree.SubElement(item, f"{{{PREDEF}}}IsFolder").text = "false"
    return item


def _write_object(root_path, directory, name, document):
    path = root_path / directory / f"{name}.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(etree.tostring(document, xml_declaration=True, encoding="UTF-8"))


def _roots(tmp_path):
    source, target = tmp_path / "base", tmp_path / "extension"
    shutil.copytree(FIXTURES / "cf", source)
    shutil.copytree(FIXTURES / "own-cfe", target)
    registrations = (
        ("ChartOfAccounts", "Хозрасчетный"),
        ("ChartOfCharacteristicTypes", "ВидыСубконтоХозрасчетные"),
        ("Catalog", "Демо_Заказы"),
        ("Catalog", "ДоговорыКонтрагентов"),
    )
    for root in (source, target):
        config_path = root / "Configuration.xml"
        original = config_path.read_bytes()
        config = editor.metadata(original, "Configuration")
        children = config.find("m:ChildObjects", editor.NS)
        for kind, name in registrations:
            etree.SubElement(children, f"{{{editor.MD}}}{kind}").text = name
        config_path.write_bytes(editor.serialize_like(config.getparent(), original))

    account_base = _object("ChartOfAccounts", "Хозрасчетный")
    etree.SubElement(
        account_base[0].find("m:Properties", editor.NS), f"{{{editor.MD}}}ExtDimensionTypes"
    ).text = "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные"
    account_base_uuid = editor.identity(editor.metadata(etree.tostring(account_base), "ChartOfAccounts"))
    account_target = _object("ChartOfAccounts", "Хозрасчетный", adopted=True, base_uuid=account_base_uuid)
    etree.SubElement(account_target[0], f"{{{editor.MD}}}InternalInfo")
    for base_child in account_base[0].find("m:ChildObjects", editor.NS):
        kind = etree.QName(base_child).localname
        if kind not in {"AccountingFlag", "ExtDimensionAccountingFlag"}:
            continue
        name = editor.prop(base_child, "Name")
        target_child = next(
            child
            for child in account_target[0].find("m:ChildObjects", editor.NS)
            if etree.QName(child).localname == kind and editor.prop(child, "Name") == name
        )
        target_properties = target_child.find("m:Properties", editor.NS)
        etree.SubElement(target_properties, f"{{{editor.MD}}}ObjectBelonging").text = "Adopted"
        etree.SubElement(target_properties, f"{{{editor.MD}}}ExtendedConfigurationObject").text = editor.identity(
            base_child
        )
    etree.SubElement(
        account_target[0].find("m:Properties", editor.NS), f"{{{editor.MD}}}ExtDimensionTypes"
    ).text = "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные"
    type_base = _object("ChartOfCharacteristicTypes", "ВидыСубконтоХозрасчетные")
    etree.SubElement(type_base[0], f"{{{editor.MD}}}InternalInfo")
    type_props = type_base[0].find("m:Properties", editor.NS)
    base_type = etree.SubElement(type_props, f"{{{editor.MD}}}Type")
    etree.SubElement(base_type, f"{{{editor.V8}}}Type").text = "d4p1:CatalogRef.Демо_Заказы"
    type_base_uuid = editor.identity(editor.metadata(etree.tostring(type_base), "ChartOfCharacteristicTypes"))
    type_target = _object(
        "ChartOfCharacteristicTypes", "ВидыСубконтоХозрасчетные", adopted=True, base_uuid=type_base_uuid
    )
    etree.SubElement(type_target[0], f"{{{editor.MD}}}InternalInfo")
    catalog = _object("Catalog", "Демо_Заказы")
    dependency_catalog_base = _object("Catalog", "ДоговорыКонтрагентов")
    dependency_catalog_target = _object("Catalog", "ДоговорыКонтрагентов")
    base_only_catalog = _object("Catalog", "Субконто")
    internal = etree.SubElement(base_only_catalog[0], f"{{{editor.MD}}}InternalInfo")
    generated = etree.SubElement(internal, f"{{{borrow.XR}}}GeneratedType", name="CatalogRef.Субконто", category="Ref")
    etree.SubElement(generated, f"{{{borrow.XR}}}TypeId").text = str(uuid.uuid4())
    properties = catalog[0].find("m:Properties", editor.NS)
    standard = etree.SubElement(properties, f"{{{editor.MD}}}StandardAttributes")
    description = etree.SubElement(standard, f"{{{borrow.XR}}}StandardAttribute", name="Description")
    etree.SubElement(description, f"{{{borrow.XR}}}FillChecking").text = "DontCheck"

    for root, objects in (
        (source, (account_base, type_base, dependency_catalog_base, base_only_catalog)),
        (target, (account_target, type_target, catalog, dependency_catalog_target)),
    ):
        for item in objects:
            node = item[0]
            kind = etree.QName(node).localname
            name = editor.prop(node, "Name")
            _write_object(root, borrow.DIRECTORIES[kind], name, item)

    account_predef = source / "ChartsOfAccounts/Хозрасчетный/Ext/Predefined.xml"
    account_predef.parent.mkdir(parents=True, exist_ok=True)
    account_predef.write_bytes(
        etree.tostring(_predefined("ChartOfAccounts", [_account_parent()]), xml_declaration=True, encoding="UTF-8")
    )
    type_predef = source / "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные/Ext/Predefined.xml"
    type_predef.parent.mkdir(parents=True, exist_ok=True)
    type_predef.write_bytes(
        etree.tostring(
            _predefined("ChartOfCharacteristicTypes", [_characteristic_base()]), xml_declaration=True, encoding="UTF-8"
        )
    )
    return source, target


def _request(operations):
    return {"schemaVersion": 1, "operations": operations}


def test_description_fill_checking_preserves_uuid(tmp_path):
    source, target = _roots(tmp_path)
    path = target / "Catalogs/Демо_Заказы.xml"
    before = editor.identity(editor.metadata(path.read_bytes(), "Catalog"))
    request = _request(
        [
            {
                "op": "catalog.set-description-fill-checking",
                "target": "Catalog.Демо_Заказы",
                "parameters": {"value": "ShowError"},
            }
        ]
    )
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert len(plan["writes"]) == 1
    assert editor.apply(target, None, plan) == "applied"
    assert editor.apply(target, None, plan) == "already-applied"
    root = editor.metadata(path.read_bytes(), "Catalog")
    assert editor.identity(root) == before
    checking = root.find(
        "m:Properties/m:StandardAttributes/xr:StandardAttribute/xr:FillChecking",
        namespaces=editor.NS | {"xr": borrow.XR},
    )
    assert checking is not None and checking.text == "ShowError"


def test_remove_native_leaf_account_and_refusals(tmp_path):
    source, target = _roots(tmp_path)
    definition = {
        "name": "Демо_Диагностика016",
        "code": "Д016",
        "description": "Диагностика",
        "accountType": "Active",
        "offBalance": True,
        "order": "Д016",
        "accountingFlags": {
            name: False for name in ("Валютный", "Количественный", "УчетПоПодразделениям", "НалоговыйУчет")
        },
    }
    borrow_step = {
        "op": "object.borrow",
        "target": "ChartOfAccounts.Хозрасчетный",
        "parameters": {"baseRoot": str(source)},
    }
    peer = dict(definition, name="Демо_Оставить", code="Д017", order="Д017")
    create = _request(
        [
            borrow_step,
            {
                "op": "chart.add-predefined",
                "target": "ChartOfAccounts.Хозрасчетный",
                "parameters": {"items": [definition, peer]},
            },
        ]
    )
    editor.apply(target, None, editor.plan_make(editor.Snapshot(target), create))
    relative = "ChartsOfAccounts/Хозрасчетный/Ext/Predefined.xml"
    path = target / relative
    original = path.read_bytes()
    item = etree.fromstring(original).find(f"{{{PREDEF}}}Item")
    item_id = item.get("id")
    peer_bytes = etree.tostring(etree.fromstring(original)[1])
    reviewed = [
        {
            "path": file.relative_to(target).as_posix(),
            "sha256": editor.digest(file.read_bytes()),
            "reason": "Fixture dependency review: no reference to diagnostic account",
        }
        for file in target.rglob("*")
        if file.is_file()
        and "/Ext/" in file.relative_to(target).as_posix()
        and file.relative_to(target).as_posix() != relative
    ]
    remove = {
        "op": "chart.remove-predefined",
        "target": "ChartOfAccounts.Хозрасчетный",
        "parameters": {"name": definition["name"], "expectedUuid": item_id, "reviewedDependencies": reviewed},
    }
    request = _request([borrow_step, remove])
    for missing in ("name", "expectedUuid"):
        invalid = copy.deepcopy(request)
        del invalid["operations"][1]["parameters"][missing]
        with pytest.raises(editor.Rejected, match="Invalid operation parameters"):
            editor.plan_make(editor.Snapshot(target), invalid)
    invalid = copy.deepcopy(request)
    invalid["operations"][1]["target"] = "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные"
    with pytest.raises(editor.Rejected, match="Only account removal"):
        editor.plan_make(editor.Snapshot(target), invalid)
    # Wrong identity, borrowed items and children are never removed.
    invalid = copy.deepcopy(request)
    invalid["operations"][1]["parameters"]["expectedUuid"] = str(uuid.uuid4())
    with pytest.raises(editor.Rejected, match="UUID conflict"):
        editor.plan_make(editor.Snapshot(target), invalid)
    for marker in ("Adopted", "AdoptedCheck", None):
        root = etree.fromstring(original)
        state = root.find(f"{{{PREDEF}}}Item/{{{PREDEF}}}ExtensionState")
        if marker is None:
            state.getparent().remove(state)
        else:
            state.text = marker
        path.write_bytes(editor.serialize_like(root, original))
        with pytest.raises(editor.Rejected, match="adopted predefined"):
            editor.plan_make(editor.Snapshot(target), request)
    root = etree.fromstring(original)
    etree.SubElement(root[0], f"{{{PREDEF}}}ChildItems")
    path.write_bytes(editor.serialize_like(root, original))
    with pytest.raises(editor.Rejected, match="with children"):
        editor.plan_make(editor.Snapshot(target), request)
    path.write_bytes(original)
    base_item = etree.parse(str(source / relative)).getroot()[0]
    invalid = copy.deepcopy(request)
    invalid["operations"][1]["parameters"].update(
        name=base_item.findtext(f"{{{PREDEF}}}Name"), expectedUuid=base_item.get("id")
    )
    with pytest.raises(editor.Rejected, match="base predefined"):
        editor.plan_make(editor.Snapshot(target), invalid)
    module = target / "ChartsOfAccounts/Хозрасчетный/Ext/ManagerModule.bsl"
    module.write_text("// fixture module", encoding="utf-8")
    with pytest.raises(editor.Rejected, match="Cannot prove dependencies in BSL"):
        editor.plan_make(editor.Snapshot(target), request)
    review = {
        "path": module.relative_to(target).as_posix(),
        "sha256": editor.digest(module.read_bytes()),
        "reason": "Fixture module has no references",
    }
    remove["parameters"]["reviewedDependencies"].append(review)
    module.write_text(definition["name"], encoding="utf-8")
    with pytest.raises(editor.Rejected, match="Stale reviewed dependency"):
        editor.plan_make(editor.Snapshot(target), request)
    review["sha256"] = editor.digest(module.read_bytes())
    with pytest.raises(editor.Rejected, match="referenced predefined item"):
        editor.plan_make(editor.Snapshot(target), request)
    module.write_text(item_id, encoding="utf-8")
    review["sha256"] = editor.digest(module.read_bytes())
    with pytest.raises(editor.Rejected, match="referenced predefined item"):
        editor.plan_make(editor.Snapshot(target), request)
    module.write_text("// fixture module", encoding="utf-8")
    review["sha256"] = editor.digest(module.read_bytes())
    before = {file: file.read_bytes() for file in target.rglob("*") if file.is_file()}
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert [write["path"] for write in plan["writes"]] == [relative]
    assert editor.apply(target, None, plan) == "applied"
    assert all(file.read_bytes() == data for file, data in before.items() if file != path)
    remaining = etree.parse(str(path)).getroot()
    assert len(remaining) == 1 and etree.tostring(remaining[0]) == peer_bytes
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []
    assert editor.apply(target, None, plan) == "already-applied"


def test_account_predefined_parent_and_repeat(tmp_path):
    source, target = _roots(tmp_path)
    definition = {
        "name": "Демо_Счет_7610",
        "code": "76.10",
        "description": "Счет",
        "accountType": "Active",
        "offBalance": False,
        "order": "7610",
        "accountingFlags": {
            name: False for name in ("Валютный", "Количественный", "УчетПоПодразделениям", "НалоговыйУчет")
        },
        "parent": "Родитель76",
    }
    request = _request(
        [
            {"op": "object.borrow", "target": "ChartOfAccounts.Хозрасчетный", "parameters": {"baseRoot": str(source)}},
            {
                "op": "chart.add-predefined",
                "target": "ChartOfAccounts.Хозрасчетный",
                "parameters": {"items": [definition]},
            },
        ]
    )
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert any(write["path"].endswith("/Ext/Predefined.xml") for write in plan["writes"])
    assert editor.apply(target, None, plan) == "applied"
    repeated = editor.plan_make(editor.Snapshot(target), request)
    assert repeated["writes"] == []


def test_account_predefined_repairs_adopted_chart_dependencies(tmp_path):
    source, target = _roots(tmp_path)
    descriptor_path = target / "ChartsOfAccounts/Хозрасчетный.xml"
    descriptor_original = descriptor_path.read_bytes()
    descriptor = editor.metadata(descriptor_original, "ChartOfAccounts")
    node = descriptor
    properties = node.find("m:Properties", editor.NS)
    for child in list(properties):
        if etree.QName(child).localname not in {"ObjectBelonging", "Name", "Comment", "ExtendedConfigurationObject"}:
            properties.remove(child)
    children = node.find("m:ChildObjects", editor.NS)
    for child in list(children):
        children.remove(child)
    descriptor_path.write_bytes(editor.serialize_like(node.getparent(), descriptor_original))
    source_before = (source / "ChartsOfAccounts/Хозрасчетный.xml").read_bytes()

    flags = {name: False for name in ("Валютный", "Количественный", "УчетПоПодразделениям", "НалоговыйУчет")}
    definition = {
        "name": "Демо_Счет_9999",
        "code": "9999",
        "description": "Счет",
        "accountType": "Active",
        "offBalance": False,
        "order": "9999",
        "accountingFlags": flags,
    }
    request = _request(
        [
            {"op": "object.borrow", "target": "ChartOfAccounts.Хозрасчетный", "parameters": {"baseRoot": str(source)}},
            {
                "op": "chart.add-predefined",
                "target": "ChartOfAccounts.Хозрасчетный",
                "parameters": {"items": [definition]},
            },
        ]
    )
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert {write["path"] for write in plan["writes"]} == {
        "ChartsOfAccounts/Хозрасчетный.xml",
        "ChartsOfAccounts/Хозрасчетный/Ext/Predefined.xml",
    }
    assert editor.apply(target, None, plan) == "applied"

    repaired = editor.metadata(descriptor_path.read_bytes(), "ChartOfAccounts")
    base = editor.metadata((source / "ChartsOfAccounts/Хозрасчетный.xml").read_bytes(), "ChartOfAccounts")
    for name in (
        "CodeLength",
        "DescriptionLength",
        "CodeMask",
        "MaxExtDimensionCount",
        "ExtDimensionTypes",
        "AutoOrderByCode",
        "OrderLength",
    ):
        assert editor.prop(repaired, name) == editor.prop(base, name)
    repaired_children = repaired.find("m:ChildObjects", editor.NS)
    base_children = base.find("m:ChildObjects", editor.NS)
    for kind in ("AccountingFlag", "ExtDimensionAccountingFlag"):
        for expected in base_children.findall(f"m:{kind}", editor.NS):
            name = editor.prop(expected, "Name")
            actual = [
                node for node in repaired_children.findall(f"m:{kind}", editor.NS) if editor.prop(node, "Name") == name
            ]
            assert len(actual) == 1
            assert editor.prop(actual[0], "ObjectBelonging") == "Adopted"
            assert editor.prop(actual[0], "ExtendedConfigurationObject") == editor.identity(expected)

    predefined_path = target / "ChartsOfAccounts/Хозрасчетный/Ext/Predefined.xml"
    item = etree.parse(str(predefined_path)).find("p:Item", namespaces={"p": PREDEF})
    item_id = item.get("id")
    assert source_before == (source / "ChartsOfAccounts/Хозрасчетный.xml").read_bytes()
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []
    assert etree.parse(str(predefined_path)).find("p:Item", namespaces={"p": PREDEF}).get("id") == item_id


@pytest.mark.parametrize("initial_state", [None, "Checked", "Extended"])
def test_account_predefined_borrows_referenced_characteristic_items(tmp_path, initial_state):
    source, target = _roots(tmp_path)
    for kind, name in (("ChartOfCharacteristicTypes", "ВидыСубконтоХозрасчетные"), ("ChartOfAccounts", "Хозрасчетный")):
        descriptor_path = target / borrow.DIRECTORIES[kind] / f"{name}.xml"
        descriptor_original = descriptor_path.read_bytes()
        descriptor = editor.metadata(descriptor_original, kind)
        if initial_state is not None:
            state = etree.SubElement(descriptor.find("m:InternalInfo", editor.NS), f"{{{borrow.XR}}}PropertyState")
            etree.SubElement(state, f"{{{borrow.XR}}}Property").text = "Predefined"
            etree.SubElement(state, f"{{{borrow.XR}}}State").text = initial_state
        descriptor_path.write_bytes(editor.serialize_like(descriptor.getparent(), descriptor_original))
    type_path = source / "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные.xml"
    type_original = type_path.read_bytes()
    type_base = editor.metadata(type_original, "ChartOfCharacteristicTypes")
    type_properties = type_base.find("m:Properties", editor.NS)
    for name, value in (
        ("Hierarchical", "false"),
        ("CodeLength", "5"),
        ("CodeAllowedLength", "Fixed"),
        ("DescriptionLength", "50"),
    ):
        etree.SubElement(type_properties, f"{{{editor.MD}}}{name}").text = value
    type_path.write_bytes(editor.serialize_like(type_base.getparent(), type_original))

    flags = {name: False for name in ("Валютный", "Количественный", "УчетПоПодразделениям", "НалоговыйУчет")}
    ext_flags = {name: False for name in ("Суммовой", "Валютный", "Количественный")}
    account_path = source / "ChartsOfAccounts/Хозрасчетный/Ext/Predefined.xml"
    account_original = account_path.read_bytes()
    account_root = editor.xml_read(account_original, f"{{{PREDEF}}}PredefinedData")
    parent = account_root.find(f"{{{PREDEF}}}Item")
    dimensions = parent.find(f"{{{PREDEF}}}ExtDimensionTypes")
    dimension = etree.SubElement(
        dimensions,
        f"{{{PREDEF}}}ExtDimensionType",
        name="ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные.БазовыйВид",
    )
    etree.SubElement(dimension, f"{{{PREDEF}}}Turnover").text = "false"
    dimension_flags = etree.SubElement(dimension, f"{{{PREDEF}}}AccountingFlags")
    for name in ("Суммовой", "Валютный", "Количественный"):
        etree.SubElement(
            dimension_flags, f"{{{PREDEF}}}Flag", ref=f"ChartOfAccounts.Хозрасчетный.ExtDimensionAccountingFlag.{name}"
        ).text = "false"
    account_path.write_bytes(editor.serialize_like(account_root, account_original))
    request = _request(
        [
            {
                "op": "object.borrow",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {"baseRoot": str(source)},
            },
            {
                "op": "chart.extend-characteristic-type",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {"types": ["CatalogRef.ДоговорыКонтрагентов"]},
            },
            {
                "op": "chart.add-predefined",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {
                    "items": [
                        {
                            "name": "Демо_СвойВид",
                            "code": "ДМО1",
                            "description": "Вид",
                            "type": "CatalogRef.Демо_Заказы",
                            "isFolder": False,
                        }
                    ]
                },
            },
            {"op": "object.borrow", "target": "ChartOfAccounts.Хозрасчетный", "parameters": {"baseRoot": str(source)}},
            {
                "op": "chart.add-predefined",
                "target": "ChartOfAccounts.Хозрасчетный",
                "parameters": {
                    "items": [
                        {
                            "name": "Демо_Счет_9997",
                            "code": "9997",
                            "description": "Счет",
                            "accountType": "Active",
                            "offBalance": False,
                            "order": "9997",
                            "parent": "Родитель76",
                            "accountingFlags": flags,
                            "extDimensionTypes": [
                                {
                                    "name": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные.БазовыйВид",
                                    "turnover": False,
                                    "accountingFlags": ext_flags,
                                }
                            ],
                        }
                    ]
                },
            },
        ]
    )
    plan = editor.plan_make(editor.Snapshot(target), request)
    expected_paths = {
        "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные.xml",
        "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные/Ext/Predefined.xml",
        "ChartsOfAccounts/Хозрасчетный.xml",
        "ChartsOfAccounts/Хозрасчетный/Ext/Predefined.xml",
    }
    if initial_state == "Extended":
        expected_paths.remove("ChartsOfAccounts/Хозрасчетный.xml")
    assert {write["path"] for write in plan["writes"]} == expected_paths
    assert editor.apply(target, None, plan) == "applied"

    base_type = editor.metadata(type_path.read_bytes(), "ChartOfCharacteristicTypes")
    repaired_type = editor.metadata(
        (target / "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные.xml").read_bytes(), "ChartOfCharacteristicTypes"
    )
    for name in ("Hierarchical", "CodeLength", "CodeAllowedLength", "DescriptionLength"):
        assert editor.prop(repaired_type, name) == editor.prop(base_type, name)
    base_item = editor.xml_read(
        (source / "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные/Ext/Predefined.xml").read_bytes(),
        f"{{{PREDEF}}}PredefinedData",
    ).find(f"{{{PREDEF}}}Item")
    repaired_root = editor.xml_read(
        (target / "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные/Ext/Predefined.xml").read_bytes(),
        f"{{{PREDEF}}}PredefinedData",
    )
    repaired_item = next(
        item
        for item in repaired_root.findall(f"{{{PREDEF}}}Item")
        if item.findtext(f"{{{PREDEF}}}Name") == "БазовыйВид"
    )
    repaired_type_root = editor.metadata(
        (target / "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные.xml").read_bytes(), "ChartOfCharacteristicTypes"
    )
    assert (
        repaired_type_root.find(
            'm:InternalInfo/xr:PropertyState[xr:Property="Predefined"][xr:State="Extended"]',
            namespaces=editor.NS | {"xr": borrow.XR},
        )
        is not None
    )
    states = repaired_type_root.findall("m:InternalInfo/xr:PropertyState", namespaces=editor.NS | {"xr": borrow.XR})
    assert sorted(state.findtext("xr:Property", namespaces=editor.NS | {"xr": borrow.XR}) for state in states) == [
        "Predefined",
        "Type",
    ]
    account_type_root = editor.metadata((target / "ChartsOfAccounts/Хозрасчетный.xml").read_bytes(), "ChartOfAccounts")
    assert (
        account_type_root.find(
            'm:InternalInfo/xr:PropertyState[xr:Property="Predefined"][xr:State="Extended"]',
            namespaces=editor.NS | {"xr": borrow.XR},
        )
        is not None
    )
    assert repaired_item.get("id") == base_item.get("id")
    assert repaired_item.find(f"{{{PREDEF}}}ExtensionState") is None
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []

    # Repair existing native items without changing their UUIDs or any data bytes.
    preserved = {path: path.read_bytes() for path in target.glob("*/**/Ext/Predefined.xml")}
    assert len(preserved) == 2
    descriptors = ("ChartsOfAccounts/Хозрасчетный.xml", "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные.xml")
    for relative in descriptors:
        path = target / relative
        original = path.read_bytes()
        root = etree.fromstring(original)
        state = root.find('.//xr:PropertyState[xr:Property="Predefined"]/xr:State', namespaces={"xr": borrow.XR})
        state.text = "Checked"
        path.write_bytes(editor.serialize_like(root, original))
    repair = editor.plan_make(editor.Snapshot(target), request)
    assert {write["path"] for write in repair["writes"]} == set(descriptors)
    assert editor.apply(target, None, repair) == "applied"
    assert all(path.read_bytes() == original for path, original in preserved.items())
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []

    marker = etree.SubElement(repaired_item, f"{{{PREDEF}}}ExtensionState")
    pvh_path = target / "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные/Ext/Predefined.xml"
    marker.text = "AdoptedCheck"
    pvh_path.write_bytes(editor.serialize_like(repaired_item.getroottree().getroot(), pvh_path.read_bytes()))
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []
    marker.text = "Native"
    pvh_path.write_bytes(editor.serialize_like(repaired_item.getroottree().getroot(), pvh_path.read_bytes()))
    with pytest.raises(editor.Rejected, match="Conflicting adopted characteristic predefined item"):
        editor.plan_make(editor.Snapshot(target), request)


@pytest.mark.parametrize("kind,family", [("Catalog", "CatalogRef"), ("Enum", "EnumRef"), ("Document", "DocumentRef")])
def test_predefined_base_type_ids_and_repair(tmp_path, kind, family):
    source, target = _roots(tmp_path)
    # The chart borrow declares the base root, but does not read this dependency.
    dependency_path = "Catalogs/ДоговорыКонтрагентов.xml"
    dependency = editor.metadata((source / dependency_path).read_bytes(), "Catalog")
    adopted = _object("Catalog", "ДоговорыКонтрагентов", adopted=True, base_uuid=editor.identity(dependency))
    _write_object(target, "Catalogs", "ДоговорыКонтрагентов", adopted)
    reference = family + ".БазовыйТип"
    descriptor = _object(kind, "БазовыйТип")
    internal = etree.SubElement(descriptor[0], f"{{{editor.MD}}}InternalInfo")
    generated = etree.SubElement(internal, f"{{{borrow.XR}}}GeneratedType", name=reference, category="Ref")
    type_id = str(uuid.uuid4())
    etree.SubElement(generated, f"{{{borrow.XR}}}TypeId").text = type_id
    _write_object(source, borrow.DIRECTORIES[kind], "БазовыйТип", descriptor)
    pvh_descriptor = source / "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные.xml"
    original = pvh_descriptor.read_bytes()
    pvh = editor.metadata(original, "ChartOfCharacteristicTypes")
    etree.SubElement(pvh.find("m:Properties/m:Type", editor.NS), f"{{{CORE}}}Type").text = "cfg:" + reference
    etree.SubElement(
        pvh.find("m:Properties/m:Type", editor.NS), f"{{{CORE}}}Type"
    ).text = "cfg:CatalogRef.ДоговорыКонтрагентов"
    pvh_descriptor.write_bytes(editor.serialize_like(pvh.getparent(), original))
    relative = "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные/Ext/Predefined.xml"
    base_root = etree.parse(str(source / relative)).getroot()
    base_root.find("p:Item/p:Type/v8:Type", NS := {"p": PREDEF, "v8": CORE}).text = "cfg:" + reference
    (source / relative).write_bytes(etree.tostring(base_root))
    flags = {name: False for name in ("Валютный", "Количественный", "УчетПоПодразделениям", "НалоговыйУчет")}
    request = _request(
        [
            {
                "op": "object.borrow",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {"baseRoot": str(source)},
            },
            {
                "op": "chart.add-predefined",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {
                    "items": [
                        {
                            "name": "Демо_БазовыйТип",
                            "code": "ДМО1",
                            "description": "Тип",
                            "type": [reference, "CatalogRef.ДоговорыКонтрагентов"],
                            "isFolder": False,
                        }
                    ]
                },
            },
            {"op": "object.borrow", "target": "ChartOfAccounts.Хозрасчетный", "parameters": {"baseRoot": str(source)}},
            {
                "op": "chart.add-predefined",
                "target": "ChartOfAccounts.Хозрасчетный",
                "parameters": {
                    "items": [
                        {
                            "name": "Демо_Счет_9997",
                            "code": "9997",
                            "description": "Счет",
                            "accountType": "Active",
                            "offBalance": False,
                            "order": "9997",
                            "accountingFlags": flags,
                            "extDimensionTypes": [
                                {
                                    "name": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные.БазовыйВид",
                                    "turnover": False,
                                    "accountingFlags": {
                                        name: False for name in ("Суммовой", "Валютный", "Количественный")
                                    },
                                }
                            ],
                        }
                    ]
                },
            },
        ]
    )
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert not any(write["path"] == f"{borrow.DIRECTORIES[kind]}/БазовыйТип.xml" for write in plan["writes"])
    assert editor.apply(target, None, plan) == "applied"
    path = target / relative
    correct = path.read_bytes()
    root = etree.fromstring(correct)
    assert root.xpath("p:Item/p:Type/v8:TypeId/text()", namespaces=NS) == [type_id, type_id]
    assert root.xpath("p:Item/p:Type/v8:Type/text()", namespaces=NS) == ["cfg:CatalogRef.ДоговорыКонтрагентов"]
    identities = root.xpath("p:Item/@id", namespaces=NS)
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []
    # Simulate the previous serializer in both the own and copied base item.
    for member in root.findall("p:Item/p:Type/v8:TypeId", NS):
        replacement = etree.Element(f"{{{CORE}}}Type", nsmap={"cfg": borrow.CFG})
        replacement.text = "cfg:" + reference
        replacement.tail = member.tail
        member.getparent().replace(member, replacement)
    path.write_bytes(editor.serialize_like(root, correct))
    repair = editor.plan_make(editor.Snapshot(target), request)
    assert [write["path"] for write in repair["writes"]] == [relative]
    assert editor.apply(target, None, repair) == "applied"
    repaired = etree.parse(str(path)).getroot()
    assert repaired.xpath("p:Item/@id", namespaces=NS) == identities
    assert repaired.xpath("p:Item/p:Type/v8:TypeId/text()", namespaces=NS) == [type_id, type_id]
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []
    repaired.find("p:Item/p:Type/v8:TypeId", NS).text = str(uuid.uuid4())
    path.write_bytes(editor.serialize_like(repaired, correct))
    before = path.read_bytes()
    with pytest.raises(editor.Rejected, match="Conflicting predefined item"):
        editor.plan_make(editor.Snapshot(target), request)
    assert path.read_bytes() == before
    path.write_bytes(correct)
    for invalid in ("missing", "ambiguous"):
        malformed = copy.deepcopy(descriptor)
        malformed_internal = malformed[0].find("m:InternalInfo", editor.NS)
        if invalid == "missing":
            malformed_internal.remove(malformed_internal[0])
        else:
            malformed_internal.append(copy.deepcopy(malformed_internal[0]))
        _write_object(source, borrow.DIRECTORIES[kind], "БазовыйТип", malformed)
        with pytest.raises(editor.Rejected, match="GeneratedType is missing or ambiguous"):
            editor.plan_make(editor.Snapshot(target), request)
        assert path.read_bytes() == correct


def test_account_predefined_rejects_unlinked_chart_dependencies(tmp_path):
    source, target = _roots(tmp_path)
    descriptor_path = target / "ChartsOfAccounts/Хозрасчетный.xml"
    flags = {name: False for name in ("Валютный", "Количественный", "УчетПоПодразделениям", "НалоговыйУчет")}
    request = _request(
        [
            {"op": "object.borrow", "target": "ChartOfAccounts.Хозрасчетный", "parameters": {"baseRoot": str(source)}},
            {
                "op": "chart.add-predefined",
                "target": "ChartOfAccounts.Хозрасчетный",
                "parameters": {
                    "items": [
                        {
                            "name": "Демо_Счет_9999",
                            "code": "9999",
                            "description": "Счет",
                            "accountType": "Active",
                            "offBalance": False,
                            "order": "9999",
                            "accountingFlags": flags,
                        }
                    ]
                },
            },
        ]
    )
    descriptor = editor.metadata(descriptor_path.read_bytes(), "ChartOfAccounts")
    flag = descriptor.find("m:ChildObjects/m:AccountingFlag", editor.NS)
    original_name = flag.find("m:Properties/m:Name", editor.NS).text
    flag.find("m:Properties/m:Name", editor.NS).text = original_name.lower()
    descriptor_path.write_bytes(editor.serialize_like(descriptor.getparent(), descriptor_path.read_bytes()))
    with pytest.raises(editor.Rejected, match="Conflicting adopted chart flag"):
        editor.plan_make(editor.Snapshot(target), request)
    flag.find("m:Properties/m:Name", editor.NS).text = original_name
    for name in ("ObjectBelonging", "ExtendedConfigurationObject"):
        value = flag.find(f"m:Properties/m:{name}", editor.NS)
        value.getparent().remove(value)
    descriptor_path.write_bytes(editor.serialize_like(descriptor.getparent(), descriptor_path.read_bytes()))
    with pytest.raises(editor.Rejected, match="Conflicting adopted chart flag"):
        editor.plan_make(editor.Snapshot(target), request)

    descriptor = editor.metadata(descriptor_path.read_bytes(), "ChartOfAccounts")
    flag = descriptor.find("m:ChildObjects/m:AccountingFlag", editor.NS)
    properties = flag.find("m:Properties", editor.NS)
    etree.SubElement(properties, f"{{{editor.MD}}}ObjectBelonging").text = "Adopted"
    etree.SubElement(properties, f"{{{editor.MD}}}ExtendedConfigurationObject").text = str(uuid.uuid4())
    descriptor_path.write_bytes(editor.serialize_like(descriptor.getparent(), descriptor_path.read_bytes()))
    with pytest.raises(editor.Rejected, match="Conflicting adopted chart flag"):
        editor.plan_make(editor.Snapshot(target), request)


def test_predefined_version_follows_owner_and_repairs_existing_file(tmp_path):
    source, target = _roots(tmp_path)
    definition = {
        "name": "Демо_Счет_7610",
        "code": "76.10",
        "description": "Счет",
        "accountType": "Active",
        "offBalance": False,
        "order": "7610",
        "accountingFlags": {
            name: False for name in ("Валютный", "Количественный", "УчетПоПодразделениям", "НалоговыйУчет")
        },
        "parent": "Родитель76",
    }
    request = _request(
        [
            {"op": "object.borrow", "target": "ChartOfAccounts.Хозрасчетный", "parameters": {"baseRoot": str(source)}},
            {
                "op": "chart.add-predefined",
                "target": "ChartOfAccounts.Хозрасчетный",
                "parameters": {"items": [definition]},
            },
        ]
    )
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert editor.apply(target, None, plan) == "applied"
    path = target / "ChartsOfAccounts/Хозрасчетный/Ext/Predefined.xml"
    initial = etree.parse(str(path))
    assert initial.getroot().get("version") == "2.17"
    item = initial.find("p:Item/p:ChildItems/p:Item", namespaces={"p": PREDEF})
    item_id = item.get("id")
    item_data = etree.tostring(item)

    initial.getroot().set("version", "2.20")
    path.write_bytes(etree.tostring(initial, xml_declaration=True, encoding="UTF-8"))
    repair = editor.plan_make(editor.Snapshot(target), request)
    assert [write["path"] for write in repair["writes"]] == ["ChartsOfAccounts/Хозрасчетный/Ext/Predefined.xml"]
    assert editor.apply(target, None, repair) == "applied"
    fixed = etree.parse(str(path))
    fixed_item = fixed.find("p:Item/p:ChildItems/p:Item", namespaces={"p": PREDEF})
    assert fixed.getroot().get("version") == "2.17"
    assert fixed_item.get("id") == item_id
    assert etree.tostring(fixed_item) == item_data
    assert editor.plan_make(editor.Snapshot(target), request)["writes"] == []


def test_account_predefined_repeat_keeps_existing_children(tmp_path):
    source, target = _roots(tmp_path)
    flags = {name: False for name in ("Валютный", "Количественный", "УчетПоПодразделениям", "НалоговыйУчет")}
    parent = {
        "name": "Демо_Счет_7650",
        "code": "7650",
        "description": "Родитель",
        "accountType": "Active",
        "offBalance": False,
        "order": "7650",
        "accountingFlags": flags,
    }
    child = {
        "name": "Демо_Счет_7650_1",
        "code": "7650.1",
        "description": "Потомок",
        "accountType": "Active",
        "offBalance": False,
        "order": "7650.1",
        "accountingFlags": flags,
        "parent": "Демо_Счет_7650",
    }
    request = _request(
        [
            {"op": "object.borrow", "target": "ChartOfAccounts.Хозрасчетный", "parameters": {"baseRoot": str(source)}},
            {
                "op": "chart.add-predefined",
                "target": "ChartOfAccounts.Хозрасчетный",
                "parameters": {"items": [parent, child]},
            },
        ]
    )
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert editor.apply(target, None, plan) == "applied"
    repeated = editor.plan_make(editor.Snapshot(target), request)
    assert repeated["writes"] == []
    changed = copy.deepcopy(request)
    changed["operations"][1]["parameters"]["items"][1]["parent"] = "Родитель76"
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), changed)


def test_account_predefined_rejects_base_code_collision(tmp_path):
    source, target = _roots(tmp_path)
    flags = {name: False for name in ("Валютный", "Количественный", "УчетПоПодразделениям", "НалоговыйУчет")}
    request = _request(
        [
            {"op": "object.borrow", "target": "ChartOfAccounts.Хозрасчетный", "parameters": {"baseRoot": str(source)}},
            {
                "op": "chart.add-predefined",
                "target": "ChartOfAccounts.Хозрасчетный",
                "parameters": {
                    "items": [
                        {
                            "name": "Демо_Дубль",
                            "code": "76",
                            "description": "Дубль",
                            "accountType": "Active",
                            "offBalance": False,
                            "order": "76",
                            "accountingFlags": flags,
                        }
                    ]
                },
            },
        ]
    )
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), request)


def test_account_predefined_rejects_base_name_collision(tmp_path):
    source, target = _roots(tmp_path)
    flags = {name: False for name in ("Валютный", "Количественный", "УчетПоПодразделениям", "НалоговыйУчет")}
    request = _request(
        [
            {"op": "object.borrow", "target": "ChartOfAccounts.Хозрасчетный", "parameters": {"baseRoot": str(source)}},
            {
                "op": "chart.add-predefined",
                "target": "ChartOfAccounts.Хозрасчетный",
                "parameters": {
                    "items": [
                        {
                            "name": "Родитель76",
                            "code": "999",
                            "description": "Дубль",
                            "accountType": "Active",
                            "offBalance": False,
                            "order": "999",
                            "accountingFlags": flags,
                        }
                    ]
                },
            },
        ]
    )
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), request)


def test_characteristic_predefined_rejects_missing_or_disallowed_type(tmp_path):
    source, target = _roots(tmp_path)
    missing = _request(
        [
            {
                "op": "object.borrow",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {"baseRoot": str(source)},
            },
            {
                "op": "chart.extend-characteristic-type",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {"types": ["CatalogRef.ДоговорыКонтрагентов"]},
            },
            {
                "op": "chart.add-predefined",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {
                    "items": [
                        {
                            "name": "Демо_ВидСубконто",
                            "code": "ДМО2",
                            "description": "Вид",
                            "type": "CatalogRef.НесуществующийСправочник",
                            "isFolder": False,
                        }
                    ]
                },
            },
        ]
    )
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), missing)
    disallowed = _request(
        [
            {
                "op": "object.borrow",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {"baseRoot": str(source)},
            },
            {
                "op": "chart.add-predefined",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {
                    "items": [
                        {
                            "name": "Демо_ВидСубконто",
                            "code": "ДМО2",
                            "description": "Вид",
                            "type": "CatalogRef.ДоговорыКонтрагентов",
                            "isFolder": False,
                        }
                    ]
                },
            },
        ]
    )
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), disallowed)


def test_chart_predefined_rejects_wrong_family(tmp_path):
    source, target = _roots(tmp_path)
    request = _request(
        [
            {"op": "object.borrow", "target": "ChartOfAccounts.Хозрасчетный", "parameters": {"baseRoot": str(source)}},
            {
                "op": "chart.add-predefined",
                "target": "ChartOfAccounts.Хозрасчетный",
                "parameters": {
                    "items": [
                        {
                            "name": "Демо_ВидСубконто",
                            "code": "ДМО3",
                            "description": "Вид",
                            "type": "CatalogRef.ДоговорыКонтрагентов",
                            "isFolder": False,
                        }
                    ]
                },
            },
        ]
    )
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), request)


def test_account_predefined_accepts_target_characteristic_item(tmp_path):
    source, target = _roots(tmp_path)
    flags = {name: False for name in ("Валютный", "Количественный", "УчетПоПодразделениям", "НалоговыйУчет")}
    ext_flags = {name: False for name in ("Суммовой", "Валютный", "Количественный")}
    request = _request(
        [
            {
                "op": "object.borrow",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {"baseRoot": str(source)},
            },
            {
                "op": "chart.extend-characteristic-type",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {"types": ["CatalogRef.ДоговорыКонтрагентов"]},
            },
            {
                "op": "chart.add-predefined",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {
                    "items": [
                        {
                            "name": "Демо_ВидСубконто",
                            "code": "ДМО4",
                            "description": "Вид",
                            "type": "CatalogRef.ДоговорыКонтрагентов",
                            "isFolder": False,
                        }
                    ]
                },
            },
            {"op": "object.borrow", "target": "ChartOfAccounts.Хозрасчетный", "parameters": {"baseRoot": str(source)}},
            {
                "op": "chart.add-predefined",
                "target": "ChartOfAccounts.Хозрасчетный",
                "parameters": {
                    "items": [
                        {
                            "name": "Демо_Счет_9999",
                            "code": "9999",
                            "description": "Счет",
                            "accountType": "Active",
                            "offBalance": False,
                            "order": "9999",
                            "accountingFlags": flags,
                            "extDimensionTypes": [
                                {
                                    "name": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные.Демо_ВидСубконто",
                                    "turnover": False,
                                    "accountingFlags": ext_flags,
                                }
                            ],
                        }
                    ]
                },
            },
        ]
    )
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert any("Predefined.xml" in write["path"] for write in plan["writes"])


def test_account_ext_dimension_rejects_wrong_target_base_link(tmp_path):
    source, target = _roots(tmp_path)
    descriptor_path = target / "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные.xml"
    original = descriptor_path.read_bytes()
    descriptor = editor.metadata(original, "ChartOfCharacteristicTypes")
    descriptor.find("m:Properties/m:ExtendedConfigurationObject", editor.NS).text = str(uuid.uuid4())
    descriptor_path.write_bytes(editor.serialize_like(descriptor.getparent(), original))
    flags = {name: False for name in ("Валютный", "Количественный", "УчетПоПодразделениям", "НалоговыйУчет")}
    ext_flags = {name: False for name in ("Суммовой", "Валютный", "Количественный")}
    request = _request(
        [
            {"op": "object.borrow", "target": "ChartOfAccounts.Хозрасчетный", "parameters": {"baseRoot": str(source)}},
            {
                "op": "chart.add-predefined",
                "target": "ChartOfAccounts.Хозрасчетный",
                "parameters": {
                    "items": [
                        {
                            "name": "Демо_Счет_9998",
                            "code": "9998",
                            "description": "Счет",
                            "accountType": "Active",
                            "offBalance": False,
                            "order": "9998",
                            "accountingFlags": flags,
                            "extDimensionTypes": [
                                {
                                    "name": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные.БазовыйВид",
                                    "turnover": False,
                                    "accountingFlags": ext_flags,
                                }
                            ],
                        }
                    ]
                },
            },
        ]
    )
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(target), request)
    assert not (target / "ChartsOfAccounts/Хозрасчетный/Ext/Predefined.xml").exists()


def test_characteristic_type_extension_uses_canonical_type(tmp_path):
    source, target = _roots(tmp_path)
    request = _request(
        [
            {
                "op": "object.borrow",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {"baseRoot": str(source)},
            },
            {
                "op": "chart.extend-characteristic-type",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {"types": ["CatalogRef.ДоговорыКонтрагентов"]},
            },
        ]
    )
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert any(
        "ChartsOfCharacteristicTypes" in write["path"] and write["path"].endswith(".xml") for write in plan["writes"]
    )
    assert editor.apply(target, None, plan) == "applied"
    root = editor.metadata(
        (target / "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные.xml").read_bytes(), "ChartOfCharacteristicTypes"
    )
    extended = root.find("m:Properties/m:Type/xr:ExtendValue", namespaces=editor.NS | {"xr": borrow.XR})
    assert (
        extended is not None and extended.findall("v8:Type", editor.NS)[0].text == "cfg:CatalogRef.ДоговорыКонтрагентов"
    )


def test_characteristic_predefined_uses_canonical_type(tmp_path):
    source, target = _roots(tmp_path)
    type_path = source / "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные.xml"
    type_original = type_path.read_bytes()
    type_base = editor.metadata(type_original, "ChartOfCharacteristicTypes")
    type_properties = type_base.find("m:Properties", editor.NS)
    for name, value in (
        ("Hierarchical", "false"),
        ("CodeLength", "5"),
        ("CodeAllowedLength", "Fixed"),
        ("DescriptionLength", "50"),
    ):
        etree.SubElement(type_properties, f"{{{editor.MD}}}{name}").text = value
    type_path.write_bytes(editor.serialize_like(type_base.getparent(), type_original))
    request = _request(
        [
            {
                "op": "object.borrow",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {"baseRoot": str(source)},
            },
            {
                "op": "chart.extend-characteristic-type",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {"types": ["CatalogRef.ДоговорыКонтрагентов"]},
            },
            {
                "op": "chart.add-predefined",
                "target": "ChartOfCharacteristicTypes.ВидыСубконтоХозрасчетные",
                "parameters": {
                    "items": [
                        {
                            "name": "Демо_ВидСубконто",
                            "code": "ДМО1",
                            "description": "Вид",
                            "type": "CatalogRef.ДоговорыКонтрагентов",
                            "isFolder": False,
                        }
                    ]
                },
            },
        ]
    )
    plan = editor.plan_make(editor.Snapshot(target), request)
    assert editor.apply(target, None, plan) == "applied"
    repaired = editor.metadata(
        (target / "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные.xml").read_bytes(), "ChartOfCharacteristicTypes"
    )
    for name in ("Hierarchical", "CodeLength", "CodeAllowedLength", "DescriptionLength"):
        assert editor.prop(repaired, name) == editor.prop(type_base, name)
    path = target / "ChartsOfCharacteristicTypes/ВидыСубконтоХозрасчетные/Ext/Predefined.xml"
    root = etree.parse(str(path)).getroot()
    assert root.get("version") == "2.17"
    assert (
        root.findtext("p:Item/p:Type/v8:Type", namespaces={"p": PREDEF, "v8": CORE})
        == "cfg:CatalogRef.ДоговорыКонтрагентов"
    )
