"""Read and add predefined accounts using the shared metadata Snapshot."""

from __future__ import annotations

import copy
import re
import uuid

import lxml.etree as etree

PREDEF = "http://v8.1c.ru/8.3/xcf/predef"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
CHART = "ChartOfAccounts"
CHARACTERISTIC_CHART = "ChartOfCharacteristicTypes"
CATALOG = "Catalog"
CATALOG_FIELDS = ("Name", "Code", "Description", "IsFolder")
ACCOUNT_TYPES = {"Active", "Passive", "ActivePassive"}
CHART_FLAGS = "AccountingFlag ExtDimensionAccountingFlag"
DIMENSION_REF = re.compile(
    r"^ChartOfCharacteristicTypes\.([A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)\.([A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)$"
)


def path_for(kind: str, object_name: str) -> str:
    return f"{kind}s/{object_name}/Ext/Predefined.xml"


def _xml(snapshot, alias: str, path: str, *, required=False):
    from . import metadata as editor

    data = snapshot.read(alias, path, optional=not required)
    if data is None:
        return None, None
    root = editor.xml_read(data, f"{{{PREDEF}}}PredefinedData")
    expected = (
        "ChartOfAccountsPredefinedItems"
        if path.startswith("ChartsOfAccounts/")
        else "PlanOfCharacteristicKindPredefinedItems"
        if path.startswith("ChartsOfCharacteristicTypes/")
        else "CatalogPredefinedItems"
        if path.startswith("Catalogs/")
        else None
    )
    if expected:
        editor.require(
            root.get(f"{{{XSI}}}type") == expected and root.get("version") in {"2.17", "2.20"},
            "Unsupported predefined data format",
            4,
        )
    return root, data


def _dimension_lookup(snapshot, alias: str, base_chart) -> tuple[str, dict[str, str]]:
    """Map base characteristic-type predefined UUIDs to logical item references."""
    from . import metadata as editor

    chart_ref = editor.prop(base_chart, "ExtDimensionTypes")
    match = re.fullmatch(r"ChartOfCharacteristicTypes\.([A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)", chart_ref)
    if match is None:
        raise editor.Rejected("Invalid base chart ExtDimensionTypes", 4)
    type_name = match.group(1)
    root, _ = _xml(snapshot, alias, path_for("ChartsOfCharacteristicType", type_name), required=True)
    references = {}
    roots = [root]
    target_root, _ = _xml(snapshot, "target", path_for("ChartsOfCharacteristicType", type_name))
    if target_root is not None:
        roots.append(target_root)
    for item_root in roots:
        for node, item_name, _, _ in _items(item_root):
            item_id = str(uuid.UUID(node.get("id")))
            logical_name = f"ChartOfCharacteristicTypes.{type_name}.{item_name}"
            editor.require(
                item_id not in references or references[item_id] == logical_name,
                "Ambiguous base/extension subkonto UUID",
                4,
            )
            references[item_id] = logical_name
    return chart_ref, references


def _checked_characteristic_chart(snapshot, target: str, base_root: str):
    from pathlib import Path

    from . import metadata as editor
    from . import metadata_borrow as borrow

    kind, name = target.split(".", 1)
    editor.require(
        kind == CHARACTERISTIC_CHART and editor.NAME.fullmatch(name), "Expected ChartOfCharacteristicTypes target"
    )
    path = f"{borrow.DIRECTORIES[CHARACTERISTIC_CHART]}/{name}.xml"
    target_config, _ = borrow._checked(snapshot, "target", "Configuration.xml", "Configuration")
    editor.require(
        bool(editor.prop(target_config, "ConfigurationExtensionPurpose")),
        "Predefined characteristic creation requires a configuration extension",
    )
    target_chart, _ = borrow._checked(snapshot, "target", path, CHARACTERISTIC_CHART)
    editor.require(
        editor.node_name(target_chart) == name and editor.prop(target_chart, "ObjectBelonging") == "Adopted",
        "Predefined characteristic creation requires an adopted chart",
    )
    alias = snapshot.source_root(Path(base_root))
    base_config, _ = borrow._checked(snapshot, alias, "Configuration.xml", "Configuration")
    editor.require(
        not editor.prop(base_config, "ConfigurationExtensionPurpose"), "Base root must be a main configuration"
    )
    editor.require(
        borrow._linked(borrow._registrations(target_config), kind, name)
        and borrow._linked(borrow._registrations(base_config), kind, name),
        "Characteristic chart registration missing",
        4,
    )
    base_chart, _ = borrow._checked(snapshot, alias, path, kind)
    editor.require(
        editor.node_name(base_chart) == name
        and editor.prop(base_chart, "ObjectBelonging") in {"", "Native"}
        and (editor.prop(target_chart, "ExtendedConfigurationObject") or "").lower() == editor.identity(base_chart),
        "Adopted characteristic chart base link mismatch",
        3,
    )
    return alias, path, target_chart, base_chart


def _characteristic_types(chart) -> set[str]:
    from . import metadata as editor
    from . import metadata_borrow as borrow

    result = set()
    for node in chart.findall(f"{{{editor.MD}}}Properties/{{{editor.MD}}}Type//{{{editor.V8}}}Type"):
        value = (node.text or "").strip()
        prefix, colon, logical = value.partition(":")
        if colon:
            editor.require(node.nsmap.get(prefix) == borrow.CFG, "Invalid characteristic predefined type namespace", 4)
            family, dot, object_name = logical.partition(".")
            editor.require(
                dot and family in borrow.CHARACTERISTIC_REFERENCE_FAMILIES and editor.NAME.fullmatch(object_name),
                "Unsupported characteristic predefined type",
                4,
            )
            result.add(logical)
    return result


def _ensure_characteristic_dependencies(snapshot, object_path: str, base_chart) -> None:
    """Copy controlled CHT settings while preserving its extended Type union."""
    from . import metadata as editor
    from . import metadata_borrow as borrow

    target_data = snapshot.read("target", object_path)
    root = editor.xml_read(target_data, f"{{{editor.MD}}}MetaDataObject")
    chart = root.find(f"{{{editor.MD}}}{CHARACTERISTIC_CHART}")
    properties = chart.find(f"{{{editor.MD}}}Properties")
    editor.require(properties is not None, "Missing adopted characteristic chart Properties", 4)
    changed = False
    for name in ("CodeLength", "CodeAllowedLength", "DescriptionLength", "Hierarchical"):
        source = base_chart.findall(f"{{{editor.MD}}}Properties/{{{editor.MD}}}{name}")
        target = properties.findall(f"{{{editor.MD}}}{name}")
        editor.require(len(source) == 1 and len(target) <= 1, f"Missing or ambiguous characteristic chart {name}", 4)
        value = source[0].text or ""
        if name == "Hierarchical":
            editor.require(value in {"true", "false"}, "Unsupported base characteristic chart Hierarchical", 4)
        elif name == "CodeAllowedLength":
            editor.require(value in {"Fixed", "Variable"}, "Unsupported base characteristic chart CodeAllowedLength", 4)
        else:
            editor.require(value.isdigit() and int(value) > 0, f"Unsupported base characteristic chart {name}", 4)
        if target:
            editor.require((target[0].text or "") == value, f"Adopted characteristic chart {name} differs from base", 3)
        else:
            etree.SubElement(properties, f"{{{editor.MD}}}{name}").text = value
            changed = True

    chart_name = properties.findtext(f"{{{editor.MD}}}Name") or ""
    editor.require(editor.NAME.fullmatch(chart_name), "Invalid characteristic chart Name", 4)
    predefined_path = f"{borrow.DIRECTORIES[CHARACTERISTIC_CHART]}/{chart_name}/Ext/Predefined.xml"
    predefined_data = snapshot.read("target", predefined_path, optional=True)
    native_items = []
    if predefined_data is not None:
        predefined = editor.xml_read(predefined_data, f"{{{PREDEF}}}PredefinedData")
        native_items = [
            item
            for item in predefined.findall(f"{{{PREDEF}}}Item")
            if item.findtext(f"{{{PREDEF}}}ExtensionState") == "Native"
        ]
    if native_items:
        internal = chart.find(f"{{{editor.MD}}}InternalInfo")
        editor.require(internal is not None, "Missing characteristic chart InternalInfo", 4)
        states = internal.findall(f"{{{borrow.XR}}}PropertyState")
        matching_states = [state for state in states if state.findtext(f"{{{borrow.XR}}}Property") == "Predefined"]
        editor.require(len(matching_states) <= 1, "Duplicate characteristic Predefined property state", 4)
        if matching_states:
            editor.require(
                matching_states[0].findtext(f"{{{borrow.XR}}}State") == "Extended",
                "Characteristic Predefined property state is not Extended",
                3,
            )
        else:
            state = etree.SubElement(internal, f"{{{borrow.XR}}}PropertyState")
            etree.SubElement(state, f"{{{borrow.XR}}}Property").text = "Predefined"
            etree.SubElement(state, f"{{{borrow.XR}}}State").text = "Extended"
            changed = True
    if changed:
        snapshot.stage(object_path, editor.serialize_like(root, target_data))


def _characteristic_item_type(node) -> str:
    from . import metadata as editor
    from . import metadata_borrow as borrow

    containers = node.findall(f"{{{PREDEF}}}Type")
    editor.require(len(containers) == 1, "Missing or ambiguous characteristic predefined Type", 4)
    types = containers[0].findall(f"{{{editor.V8}}}Type")
    editor.require(len(types) <= 1, "Multiple characteristic predefined Types", 4)
    if not types:
        return ""
    value = (types[0].text or "").strip()
    prefix, colon, logical = value.partition(":")
    family, dot, object_name = logical.partition(".")
    editor.require(
        colon
        and types[0].nsmap.get(prefix) == borrow.CFG
        and dot
        and family in borrow.CHARACTERISTIC_REFERENCE_FAMILIES
        and editor.NAME.fullmatch(object_name),
        "Invalid characteristic predefined Type",
        4,
    )
    return logical


def _resolve_dimension_ref(raw: str, references: dict[str, str], expected_chart: str) -> str:
    from . import metadata as editor

    if DIMENSION_REF.fullmatch(raw):
        resolved = raw
    else:
        try:
            key = str(uuid.UUID(raw))
        except (ValueError, TypeError, AttributeError):
            raise editor.Rejected("Invalid subkonto reference", 4) from None
        resolved = references.get(key)
        if resolved is None:
            raise editor.Rejected("Unknown base subkonto UUID; verify with exact base-root", 4)
    editor.require(
        resolved.rsplit(".", 1)[0] == expected_chart,
        "Subkonto reference does not belong to chart extra-dimension type",
        4,
    )
    return resolved


def _bool(node):
    from . import metadata as editor

    editor.require(node is not None, "Missing predefined boolean", 4)
    text = (node.text or "").strip()
    editor.require(text in {"true", "false"}, "Invalid predefined boolean", 4)
    return text == "true"


def _flags(node, expected_prefix: str) -> dict[str, bool]:
    """Read a metadata accounting-flag set with reference and value checks."""
    from . import metadata as editor

    containers = node.findall(f"{{{PREDEF}}}AccountingFlags")
    editor.require(len(containers) == 1, "Missing or ambiguous predefined accounting flags", 4)
    values = {}
    for flag in containers[0]:
        editor.require(flag.tag == f"{{{PREDEF}}}Flag", "Unexpected predefined accounting flag node", 4)
        reference = flag.get("ref", "")
        editor.require(reference.startswith(expected_prefix), "Invalid predefined accounting flag reference", 4)
        name = reference[len(expected_prefix) :]
        editor.require(
            editor.NAME.fullmatch(name) is not None and name not in values,
            "Invalid or duplicate predefined accounting flag reference",
            4,
        )
        values[name] = _bool(flag)
    return values


def _items(root):
    """Flatten hierarchy while rejecting ambiguous or malformed item identity."""
    from . import metadata as editor

    result = []
    names, ids = set(), set()

    def walk(container, parent=None):
        for child in container:
            if not isinstance(child.tag, str):
                continue
            editor.require(child.tag == f"{{{PREDEF}}}Item", "Unexpected predefined data node", 4)
            name = child.findtext(f"{{{PREDEF}}}Name") or ""
            try:
                item_id = str(uuid.UUID(child.get("id", "")))
            except (ValueError, AttributeError):
                raise editor.Rejected("Invalid predefined item UUID", 4) from None
            editor.require(editor.NAME.fullmatch(name), "Invalid predefined item name", 4)
            folded = name.casefold()
            editor.require(folded not in names and item_id not in ids, "Duplicate predefined identity", 4)
            names.add(folded)
            ids.add(item_id)
            states = child.findall(f"{{{PREDEF}}}ExtensionState")
            editor.require(
                len(states) <= 1 and (not states or (states[0].text or "") in {"Native", "AdoptedCheck"}),
                "Invalid predefined extension state",
                4,
            )
            children = child.findall(f"{{{PREDEF}}}ChildItems")
            editor.require(len(children) <= 1, "Ambiguous predefined children", 4)
            result.append((child, name, parent, states[0].text if states else None))
            if children:
                walk(children[0], name)

    walk(root)
    return result


def inspect(snapshot, target: str, limit=150, offset=0, base_root=None) -> dict:
    from . import metadata as editor

    kind, name = target.split(".", 1)
    if kind == CHARACTERISTIC_CHART:
        root, _ = _xml(snapshot, "target", path_for("ChartsOfCharacteristicType", name))
        if root is None:
            return {"items": [], "total": 0, "nextOffset": None}
        rows = []
        for node, item_name, parent, state in _items(root):
            rows.append(
                {
                    "name": item_name,
                    "parent": parent,
                    "id": str(uuid.UUID(node.get("id"))),
                    "code": node.findtext(f"{{{PREDEF}}}Code") or "",
                    "description": node.findtext(f"{{{PREDEF}}}Description") or "",
                    "type": _characteristic_item_type(node),
                    "isFolder": _bool(node.find(f"{{{PREDEF}}}IsFolder")),
                    "extensionState": state,
                }
            )
        editor.require(len(rows) <= 10000, "Too many predefined characteristic values", 4)
        page = rows[offset : offset + limit] if limit else rows[offset:]
        next_offset = offset + len(page) if offset + len(page) < len(rows) else None
        return {"items": page, "total": len(rows), "nextOffset": next_offset}
    if kind == CATALOG:
        root, _ = _xml(snapshot, "target", path_for(CATALOG, name))
        if root is None:
            return {"items": [], "total": 0, "nextOffset": None}
        rows = [
            {
                "name": item_name,
                "parent": parent,
                "id": str(uuid.UUID(node.get("id"))),
                "code": node.findtext(f"{{{PREDEF}}}Code") or "",
                "description": node.findtext(f"{{{PREDEF}}}Description") or "",
                "isFolder": _bool(node.find(f"{{{PREDEF}}}IsFolder")),
                "extensionState": state,
            }
            for node, item_name, parent, state in _items(root)
        ]
        editor.require(len(rows) <= 10000, "Too many predefined catalog items", 4)
        page = rows[offset : offset + limit] if limit else rows[offset:]
        next_offset = offset + len(page) if offset + len(page) < len(rows) else None
        return {"items": page, "total": len(rows), "nextOffset": next_offset}
    if kind != CHART:
        return {"items": [], "total": 0, "nextOffset": None}
    root, _ = _xml(snapshot, "target", path_for("ChartsOfAccount", name))
    if root is None:
        return {"items": [], "total": 0, "nextOffset": None}
    dimension_chart, dimension_references = "", {}
    if base_root is not None:
        alias, _, _, base_chart, _ = _checked_chart(snapshot, target, str(base_root))
        dimension_chart, dimension_references = _dimension_lookup(snapshot, alias, base_chart)
    rows = []
    for node, item_name, parent, state in _items(root):
        dimensions = node.findall(f"{{{PREDEF}}}ExtDimensionTypes/{{{PREDEF}}}ExtDimensionType")
        dimension_refs = []
        ext_dimensions = []
        for dim in dimensions:
            turnover = _bool(dim.find(f"{{{PREDEF}}}Turnover"))
            accounting_flags = _flags(dim, f"{CHART}.{name}.ExtDimensionAccountingFlag.")
            raw_ref = dim.get("name", "")
            resolved = None
            if DIMENSION_REF.fullmatch(raw_ref):
                resolved = raw_ref
            else:
                try:
                    resolved = dimension_references.get(str(uuid.UUID(raw_ref)))
                except (ValueError, TypeError, AttributeError):
                    resolved = None
            if resolved is not None and dimension_chart:
                resolved = _resolve_dimension_ref(raw_ref, dimension_references, dimension_chart)
            dimension_refs.append({"raw": raw_ref, "resolved": resolved})
            ext_dimensions.append(
                {
                    "name": resolved or raw_ref,
                    "rawRef": raw_ref,
                    "turnover": turnover,
                    "accountingFlags": accounting_flags,
                }
            )
        rows.append(
            {
                "name": item_name,
                "parent": parent,
                "id": str(uuid.UUID(node.get("id"))),
                "code": node.findtext(f"{{{PREDEF}}}Code") or "",
                "description": node.findtext(f"{{{PREDEF}}}Description") or "",
                "order": node.findtext(f"{{{PREDEF}}}Order") or "",
                "accountType": node.findtext(f"{{{PREDEF}}}AccountType") or "",
                "offBalance": _bool(node.find(f"{{{PREDEF}}}OffBalance")),
                "extensionState": state,
                "accountingFlags": _flags(node, f"{CHART}.{name}.AccountingFlag."),
                "extDimensionTypes": [ref["resolved"] or ref["raw"] for ref in dimension_refs],
                "extDimensionTypeRefs": dimension_refs,
                "extDimensions": ext_dimensions,
            }
        )
    editor.require(len(rows) <= 10000, "Too many predefined accounts", 4)
    page = rows[offset : offset + limit] if limit else rows[offset:]
    next_offset = offset + len(page) if offset + len(page) < len(rows) else None
    return {"items": page, "total": len(rows), "nextOffset": next_offset}


def _checked_chart(snapshot, target: str, base_root: str):
    from pathlib import Path

    from . import metadata as editor
    from . import metadata_borrow as borrow

    kind, name = target.split(".", 1)
    editor.require(kind == CHART and editor.NAME.fullmatch(name), "Expected ChartOfAccounts target")
    path = f"{borrow.DIRECTORIES[CHART]}/{name}.xml"
    target_config, _ = borrow._checked(snapshot, "target", "Configuration.xml", "Configuration")
    editor.require(
        bool(editor.prop(target_config, "ConfigurationExtensionPurpose")),
        "Predefined account creation requires a configuration extension",
    )
    target_chart, target_data = borrow._checked(snapshot, "target", path, CHART)
    editor.require(
        editor.node_name(target_chart) == name and editor.prop(target_chart, "ObjectBelonging") == "Adopted",
        "Predefined account creation requires an adopted chart",
    )
    alias = snapshot.source_root(Path(base_root))
    base_config, _ = borrow._checked(snapshot, alias, "Configuration.xml", "Configuration")
    editor.require(
        not editor.prop(base_config, "ConfigurationExtensionPurpose"), "Base root must be a main configuration"
    )
    editor.require(
        borrow._linked(borrow._registrations(target_config), CHART, name)
        and borrow._linked(borrow._registrations(base_config), CHART, name),
        "Chart registration missing",
        4,
    )
    base_chart, _ = borrow._checked(snapshot, alias, path, CHART)
    editor.require(
        editor.node_name(base_chart) == name
        and editor.prop(base_chart, "ObjectBelonging") in {"", "Native"}
        and (editor.prop(target_chart, "ExtendedConfigurationObject") or "").lower() == editor.identity(base_chart),
        "Adopted chart base link mismatch",
        3,
    )
    return alias, path, target_chart, base_chart, target_data


def _names(node, kind: str) -> set[str]:
    from . import metadata as editor

    return {editor.node_name(child) for child in node.findall(f"{{{editor.MD}}}ChildObjects/{{{editor.MD}}}{kind}")}


def _base_item_fields(node) -> tuple[str, str, str, str, bool, str]:
    """Read only the identity and account fields needed for an AdoptedCheck parent."""
    from . import metadata as editor

    values = {}
    for key in ("Name", "Code", "Description", "AccountType", "OffBalance", "Order"):
        fields = node.findall(f"{{{PREDEF}}}{key}")
        editor.require(len(fields) == 1, f"Missing or ambiguous base account {key}", 4)
        values[key] = fields[0].text or ""
    editor.require(
        editor.NAME.fullmatch(values["Name"]) is not None
        and bool(values["Code"])
        and values["AccountType"] in ACCOUNT_TYPES,
        "Invalid base parent account identity",
        4,
    )
    off_balance = values["OffBalance"]
    editor.require(off_balance in {"true", "false"}, "Invalid base parent OffBalance", 4)
    return (
        values["Name"],
        values["Code"],
        values["Description"],
        values["AccountType"],
        off_balance == "true",
        values["Order"],
    )


def _content_signature(node):
    """Compare XML payload while ignoring namespace declarations inherited from the file root."""
    if node is None:
        return None
    text = (node.text or "").strip() or None
    return (
        node.tag,
        tuple(sorted(node.attrib.items())),
        text,
        tuple(_content_signature(child) for child in node if isinstance(child.tag, str)),
    )


def _adopted_check_matches(node, source, expected_parent: str | None, actual_parent: str | None) -> bool:
    source_fields = _base_item_fields(source)
    current_fields = _base_item_fields(node)
    sections_match = True
    for field in ("AccountingFlags", "ExtDimensionTypes"):
        expected = source.findall(f"{{{PREDEF}}}{field}")
        actual = node.findall(f"{{{PREDEF}}}{field}")
        sections_match = (
            sections_match
            and len(expected) == len(actual)
            and all(
                _content_signature(source_node) == _content_signature(target_node)
                for source_node, target_node in zip(expected, actual, strict=False)
            )
        )
    return (
        node.findtext(f"{{{PREDEF}}}ExtensionState") == "AdoptedCheck"
        and current_fields == source_fields
        and actual_parent == expected_parent
        and sections_match
    )


def _repair_adopted_check_analytics(node, source) -> None:
    """Repair only the empty analytics emitted by the previous CLI version."""
    from . import metadata as editor

    for field in ("AccountingFlags", "ExtDimensionTypes"):
        source_nodes = source.findall(f"{{{PREDEF}}}{field}")
        target_nodes = node.findall(f"{{{PREDEF}}}{field}")
        editor.require(len(source_nodes) <= 1 and len(target_nodes) <= 1, f"Ambiguous AdoptedCheck {field}", 4)
        if len(source_nodes) == len(target_nodes) and all(
            _content_signature(source_node) == _content_signature(target_node)
            for source_node, target_node in zip(source_nodes, target_nodes, strict=False)
        ):
            continue
        target_is_empty = (
            len(target_nodes) == 1 and len(target_nodes[0]) == 0 and not (target_nodes[0].text or "").strip()
        )
        if field == "AccountingFlags":
            editor.require(target_is_empty, "Existing AdoptedCheck accounting flags conflict with base", 3)
        else:
            editor.require(
                not target_nodes or target_is_empty, "Existing AdoptedCheck extra dimensions conflict with base", 3
            )
        for target_node in target_nodes:
            node.remove(target_node)
        if source_nodes:
            cloned = copy.deepcopy(source_nodes[0])
            order = [
                "Name",
                "Code",
                "Description",
                "AccountType",
                "OffBalance",
                "Order",
                "ExtensionState",
                "AccountingFlags",
                "ExtDimensionTypes",
            ]
            positions = {key: index for index, key in enumerate(order)}
            rank = positions[field]
            following = next(
                (
                    child
                    for child in node
                    if isinstance(child.tag, str) and positions.get(child.tag.rsplit("}", 1)[-1], 100) > rank
                ),
                None,
            )
            node.insert(node.index(following) if following is not None else len(node), cloned)


def _ensure_parent_characteristic_dependencies(
    snapshot, base_root: str, base_account_chart, account_item, extension_namespace: uuid.UUID
) -> None:
    """Adopt only CHT predefined values referenced by this requested base account parent."""
    from . import metadata as editor
    from . import metadata_borrow as borrow

    dimensions = account_item.findall(f"{{{PREDEF}}}ExtDimensionTypes/{{{PREDEF}}}ExtDimensionType")
    if not dimensions:
        return
    raw_chart_ref = editor.prop(base_account_chart, "ExtDimensionTypes")
    match = re.fullmatch(r"ChartOfCharacteristicTypes\.([A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)", raw_chart_ref)
    if match is None:
        raise editor.Rejected("Invalid base account extra-dimension chart", 4)
    chart_target = f"{CHARACTERISTIC_CHART}.{match.group(1)}"
    alias, descriptor_path, target_chart, base_chart = _checked_characteristic_chart(snapshot, chart_target, base_root)
    base_predef_path = path_for("ChartsOfCharacteristicType", match.group(1))
    source_root, _ = _xml(snapshot, alias, base_predef_path, required=True)
    target_root, target_data = _xml(snapshot, "target", base_predef_path)
    source_items = _items(source_root)
    source_by_name = {item_name.casefold(): (node, item_name) for node, item_name, _, _ in source_items}
    source_by_id = {str(uuid.UUID(node.get("id"))): (node, item_name) for node, item_name, _, _ in source_items}
    target_items = _items(target_root) if target_root is not None else []
    target_by_name = {item_name.casefold(): (node, item_name, state) for node, item_name, _, state in target_items}
    target_codes = {
        (node.findtext(f"{{{PREDEF}}}Code") or "").casefold(): item_name for node, item_name, _, _ in target_items
    }
    base_types = _characteristic_types(base_chart)
    target_types = _characteristic_types(target_chart)
    for dimension in dimensions:
        raw_ref = dimension.get("name", "")
        source_item = None
        if DIMENSION_REF.fullmatch(raw_ref):
            ref_kind, ref_chart, item_name = raw_ref.split(".")
            if ref_kind != CHARACTERISTIC_CHART or ref_chart != match.group(1):
                raise editor.Rejected("Base account subkonto points to another chart", 4)
            source_item = source_by_name.get(item_name.casefold())
            if source_item is None or source_item[1] != item_name:
                raise editor.Rejected("Base account subkonto is absent from base chart", 4)
        else:
            try:
                source_item = source_by_id.get(str(uuid.UUID(raw_ref)))
            except (ValueError, TypeError, AttributeError):
                source_item = None
            if source_item is None:
                raise editor.Rejected("Base account subkonto UUID is absent from base chart", 4)
        source, name = source_item
        state = source.findtext(f"{{{PREDEF}}}ExtensionState")
        editor.require(state is None, "Base account subkonto is not a native predefined value", 4)
        fields = {}
        for field in ("Code", "Description", "Type", "IsFolder"):
            matches = source.findall(f"{{{PREDEF}}}{field}")
            editor.require(len(matches) == 1, f"Missing or ambiguous base subkonto {field}", 4)
            fields[field] = matches[0]
        editor.require(not _bool(fields["IsFolder"]), "Base account subkonto must be a leaf value", 4)
        item_type = _characteristic_item_type(source)
        editor.require(
            item_type in base_types | target_types,
            "Base account subkonto Type is not allowed by base or extension chart",
            4,
        )
        code = fields["Code"].text or ""
        editor.require(
            code and len(code) <= int(editor.prop(base_chart, "CodeLength")),
            "Base subkonto code exceeds characteristic chart length",
            4,
        )
        description_length = editor.prop(base_chart, "DescriptionLength")
        description = fields["Description"].text or ""
        editor.require(
            not description_length.isdigit() or len(description) <= int(description_length),
            "Base subkonto description exceeds characteristic chart length",
            4,
        )
        owner_name = chart_target + ".Predefined.AdoptedCheck." + name
        item_id = str(uuid.uuid5(extension_namespace, owner_name))
        existing = target_by_name.get(name.casefold())
        if existing is not None:
            target_item, target_name, target_state = existing
            editor.require(
                target_name == name
                and target_state == "AdoptedCheck"
                and target_item.get("id") == item_id
                and target_item.findtext(f"{{{PREDEF}}}Code") == code
                and target_item.findtext(f"{{{PREDEF}}}Description") == description
                and _characteristic_item_type(target_item) == item_type
                and not _bool(target_item.find(f"{{{PREDEF}}}IsFolder")),
                "Existing CHT AdoptedCheck dependency conflicts with base",
                3,
            )
            continue
        editor.require(
            code.casefold() not in target_codes, "Base subkonto code collides with extension predefined value", 3
        )
        occupied_ids = {node.get("id") for node, _, _, _ in [*source_items, *target_items]}
        editor.require(item_id not in occupied_ids, "Generated CHT AdoptedCheck UUID collision", 3)
        target_item = etree.Element(f"{{{PREDEF}}}Item", id=item_id)
        etree.SubElement(target_item, f"{{{PREDEF}}}Name").text = name
        for field in ("Code", "Description", "Type", "IsFolder"):
            target_item.append(copy.deepcopy(fields[field]))
        etree.SubElement(target_item, f"{{{PREDEF}}}ExtensionState").text = "AdoptedCheck"
        if target_root is None:
            version = target_chart.getparent().get("version")
            editor.require(version in {"2.17", "2.20"}, "Unsupported metadata version", 4)
            target_root = etree.Element(
                f"{{{PREDEF}}}PredefinedData",
                nsmap={
                    None: PREDEF,
                    "v8": editor.V8,
                    "xr": borrow.XR,
                    "xs": editor.XS,
                    "xsi": XSI,
                },
                attrib={f"{{{XSI}}}type": "PlanOfCharacteristicKindPredefinedItems", "version": version},
            )
        target_root.append(target_item)
        target_by_name[name.casefold()] = (target_item, name, "AdoptedCheck")
        target_codes[code.casefold()] = name
        target_items.append((target_item, name, None, "AdoptedCheck"))
        _stage_predefined(snapshot, base_predef_path, target_root, target_data)
        _ensure_characteristic_dependencies(snapshot, descriptor_path, base_chart)


def _ensure_base_parent_chain(
    snapshot,
    target: str,
    chart_name: str,
    base_items,
    target_root,
    target_items,
    parent_name: str,
    base_root: str,
    base_chart,
    extension_namespace: uuid.UUID,
):
    """Materialize only a requested base account's missing ancestor chain."""
    from . import metadata as editor

    base_by_name = {name.casefold(): (node, name, parent, state) for node, name, parent, state in base_items}
    selected = base_by_name.get(parent_name.casefold())
    if selected is None:
        raise editor.Rejected("Parent account is absent from base and extension", 3)
    if selected[1] != parent_name:
        raise editor.Rejected("Case-ambiguous base parent account", 3)
    chain = []
    current = selected
    seen = set()
    while current is not None:
        node, name, parent, state = current
        key = name.casefold()
        editor.require(key not in seen, "Cyclic base account hierarchy", 4)
        seen.add(key)
        editor.require(state is None, "Base parent is not a native predefined account", 4)
        _base_item_fields(node)
        chain.append(current)
        if parent is None:
            break
        current = base_by_name.get(parent.casefold())
        editor.require(
            current is not None and current[1] == parent, "Base parent hierarchy is incomplete or case-ambiguous", 4
        )
    chain.reverse()

    target_by_name = {name.casefold(): (node, name, parent, state) for node, name, parent, state in target_items}
    target_codes = {(node.findtext(f"{{{PREDEF}}}Code") or "").casefold(): name for node, name, _, _ in target_items}
    target_parent_node = None
    changed = False
    for source, name, source_parent, _ in chain:
        _ensure_parent_characteristic_dependencies(snapshot, base_root, base_chart, source, extension_namespace)
        owner_name = target + ".Predefined.AdoptedCheck." + name
        item_id = str(uuid.uuid5(extension_namespace, owner_name))
        existing = target_by_name.get(name.casefold())
        if existing is not None:
            node, current_name, actual_parent, state = existing
            editor.require(
                state == "AdoptedCheck"
                and current_name == name
                and _base_item_fields(node) == _base_item_fields(source)
                and actual_parent == source_parent,
                "Existing base parent account conflicts with AdoptedCheck",
                3,
            )
            if not _adopted_check_matches(node, source, source_parent, actual_parent):
                editor.require(node.get("id") == item_id, "Existing AdoptedCheck identity cannot be repaired", 3)
                _repair_adopted_check_analytics(node, source)
                changed = True
            target_parent_node = node
            continue

        code, description, account_type, off_balance, order = _base_item_fields(source)[1:]
        occupied_ids = {node.get("id") for node, _, _, _ in [*target_items, *base_items]}
        editor.require(item_id not in occupied_ids, "Generated AdoptedCheck UUID collision", 3)
        if code.casefold() in target_codes and target_codes[code.casefold()] != name:
            editor.require(False, "Base parent account code collides with extension account", 3)

        item = etree.Element(f"{{{PREDEF}}}Item", id=item_id)
        for key, value in [
            ("Name", name),
            ("Code", code),
            ("Description", description),
            ("AccountType", account_type),
            ("OffBalance", str(off_balance).lower()),
        ]:
            etree.SubElement(item, f"{{{PREDEF}}}{key}").text = value
        etree.SubElement(item, f"{{{PREDEF}}}Order").text = order or None
        etree.SubElement(item, f"{{{PREDEF}}}ExtensionState").text = "AdoptedCheck"
        for field in ("AccountingFlags", "ExtDimensionTypes"):
            source_nodes = source.findall(f"{{{PREDEF}}}{field}")
            editor.require(len(source_nodes) <= 1, f"Ambiguous base parent {field}", 4)
            for source_node in source_nodes:
                item.append(copy.deepcopy(source_node))
        if target_parent_node is None:
            target_root.append(item)
        else:
            children = target_parent_node.findall(f"{{{PREDEF}}}ChildItems")
            editor.require(len(children) <= 1, "Ambiguous base parent children", 4)
            container = children[0] if children else etree.SubElement(target_parent_node, f"{{{PREDEF}}}ChildItems")
            container.append(item)
        target_parent_node = item
        target_by_name[name.casefold()] = (item, name, source_parent, "AdoptedCheck")
        target_codes[code.casefold()] = name
    return target_parent_node, changed


def _stage_predefined(snapshot, path: str, root, original) -> None:
    from . import metadata as editor

    if original is None:
        etree.indent(root, space="\t")
        data = b'<?xml version="1.0" encoding="UTF-8"?>\n' + etree.tostring(root, encoding="UTF-8") + b"\n"
    else:
        data = editor.serialize_like(root, original)
    snapshot.stage(path, data)


def _same_requested_item(
    node, parent_name: str | None, item_id: str, parameters: dict, chart_name: str, account_flags: set[str]
) -> bool:
    """Match a generated Native item byte-semantically by its metadata contract."""
    expected_fields = {
        "Name",
        "Code",
        "Description",
        "AccountType",
        "OffBalance",
        "Order",
        "ExtensionState",
        "AccountingFlags",
        "ExtDimensionTypes",
    }
    fields = [child.tag.rsplit("}", 1)[-1] for child in node]
    required_fields = [field for field in fields if field != "ChildItems"]
    if (
        "ChildItems" in fields
        and fields.count("ChildItems") != 1
        or set(required_fields) != expected_fields
        or len(required_fields) != len(expected_fields)
    ):
        return False
    if (
        node.get("id") != item_id
        or node.findtext(f"{{{PREDEF}}}Name") != parameters["name"]
        or node.findtext(f"{{{PREDEF}}}Code") != parameters["code"]
        or node.findtext(f"{{{PREDEF}}}Description") != parameters["description"]
        or node.findtext(f"{{{PREDEF}}}AccountType") != parameters["accountType"]
        or _bool(node.find(f"{{{PREDEF}}}OffBalance")) is not parameters["offBalance"]
        or node.findtext(f"{{{PREDEF}}}ExtensionState") != "Native"
    ):
        return False
    actual_flags = _flags(node, f"{CHART}.{chart_name}.AccountingFlag.")
    if set(actual_flags) != account_flags or actual_flags != parameters["accountingFlags"]:
        return False
    expected_dimensions = {dim["name"]: dim for dim in parameters["extDimensions"]}
    actual_dimensions = {}
    actual_dimension_order = []
    for dimension in node.findall(f"{{{PREDEF}}}ExtDimensionTypes/{{{PREDEF}}}ExtDimensionType"):
        name = dimension.get("name", "")
        if not name or name in actual_dimensions:
            return False
        actual_dimension_order.append(name)
        turnovers = dimension.findall(f"{{{PREDEF}}}Turnover")
        if len(turnovers) != 1:
            return False
        flags = _flags(dimension, f"{CHART}.{chart_name}.ExtDimensionAccountingFlag.")
        actual_dimensions[name] = {"turnover": _bool(turnovers[0]), "accountingFlags": flags}
    if actual_dimension_order != list(expected_dimensions):
        return False
    if any(
        actual_dimensions[name]
        != {
            "turnover": expected_dimensions[name]["turnover"],
            "accountingFlags": expected_dimensions[name]["accountingFlags"],
        }
        for name in expected_dimensions
    ):
        return False
    return parent_name == parameters.get("parent")


def _ensure_chart_predefined_dependencies(
    snapshot, object_path: str, base_chart, base_root: str, chart_name: str
) -> None:
    """Preserve the base chart settings and flag members needed by predefined items."""
    from . import metadata as editor
    from . import metadata_borrow as borrow

    target_data = snapshot.read("target", object_path)
    root = editor.xml_read(target_data, f"{{{editor.MD}}}MetaDataObject")
    chart = root.find(f"{{{editor.MD}}}{CHART}")
    properties = chart.find(f"{{{editor.MD}}}Properties")
    editor.require(properties is not None, "Missing adopted chart Properties", 4)
    changed = False
    for name in ("CodeLength", "DescriptionLength", "OrderLength", "ExtDimensionTypes", "MaxExtDimensionCount"):
        base_values = base_chart.findall(f"{{{editor.MD}}}Properties/{{{editor.MD}}}{name}")
        target_values = properties.findall(f"{{{editor.MD}}}{name}")
        editor.require(len(base_values) == 1 and len(target_values) <= 1, f"Missing or ambiguous chart {name}", 4)
        base_value = base_values[0].text or ""
        if name in {"CodeLength", "DescriptionLength", "OrderLength", "MaxExtDimensionCount"}:
            editor.require(base_value.isdigit() and int(base_value) > 0, f"Unsupported base chart {name}", 4)
        else:
            editor.require(
                re.fullmatch(r"ChartOfCharacteristicTypes\.[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*", base_value)
                is not None,
                f"Unsupported base chart {name}",
                4,
            )
        if target_values:
            editor.require((target_values[0].text or "") == base_value, f"Adopted chart {name} differs from base", 3)
        else:
            etree.SubElement(properties, f"{{{editor.MD}}}{name}").text = base_value
            changed = True
    if changed:
        snapshot.stage(object_path, editor.serialize_like(root, target_data))

    # These child metadata objects define the references written into account
    # predefined data. Reuse the normal borrowing helper for identity allocation
    # and exact base-link checks instead of fabricating child descriptors here.
    for kind in ("AccountingFlag", "ExtDimensionAccountingFlag"):
        names = _names(base_chart, kind)
        editor.require(names, f"Base chart has no {kind} members", 4)
        for member_name in sorted(names):
            borrow._borrow_member(snapshot, base_root, CHART + "." + chart_name, [(kind, member_name)])


def update(snapshot, operation: dict) -> None:
    """Change accounting properties of a CLI-created native account, keeping identity."""
    from . import metadata as editor
    from . import metadata_borrow as borrow

    target = operation["target"]
    editor.require(target.split(".")[0] == CHART, "Only native account properties can be updated")
    parameters = operation["parameters"]
    alias, _, _, base_chart, _ = _checked_chart(snapshot, target, parameters["baseRoot"])
    chart_name = target.split(".")[1]
    path = path_for("ChartsOfAccount", chart_name)
    root, original = _xml(snapshot, "target", path)
    editor.require(root is not None, "Missing predefined accounts", 3)
    matches = [item for item in _items(root) if item[1] == parameters["name"]]
    editor.require(len(matches) == 1, "Missing or ambiguous predefined account", 3)
    item, _, current_parent, state = matches[0]
    config, _ = borrow._checked(snapshot, "target", "Configuration.xml", "Configuration")
    expected_id = str(uuid.uuid5(uuid.UUID(editor.identity(config)), target + ".Predefined." + parameters["name"]))
    editor.require(
        state == "Native" and item.get("id") == expected_id, "Only CLI-created native accounts can be updated", 3
    )
    flags = _flags(item, target + ".AccountingFlag.")
    editor.require(
        set(flags) == set(parameters["accountingFlags"]) == _names(base_chart, "AccountingFlag"),
        "Accounting flags must exactly match the base chart",
        3,
    )
    kinds = item.findall(f"{{{PREDEF}}}AccountType")
    editor.require(len(kinds) == 1, "Missing or ambiguous account type", 4)
    kinds[0].text = parameters["accountType"]
    for flag in item.findall(f"{{{PREDEF}}}AccountingFlags/{{{PREDEF}}}Flag"):
        name = flag.get("ref", "").rsplit(".", 1)[-1]
        flag.text = str(parameters["accountingFlags"][name]).lower()
    if "order" in parameters:
        # The platform does not fill Order of extension-native predefined
        # accounts; the caller passes the chart's ПолучитьПорядокКода() value.
        orders = item.findall(f"{{{PREDEF}}}Order")
        editor.require(len(orders) == 1, "Missing or ambiguous account order", 4)
        order_length = editor.prop(base_chart, "OrderLength")
        editor.require(
            not order_length.isdigit() or len(parameters["order"]) <= int(order_length),
            "Account order exceeds chart OrderLength",
            3,
        )
        orders[0].text = parameters["order"]
    if "parent" in parameters and parameters["parent"] != current_parent:
        _move_native_account(
            snapshot,
            target,
            chart_name,
            root,
            item,
            parameters["parent"],
            alias,
            parameters["baseRoot"],
            base_chart,
            uuid.UUID(editor.identity(config)),
        )
    _stage_predefined(snapshot, path, root, original)


def _move_native_account(
    snapshot,
    target: str,
    chart_name: str,
    root,
    item,
    parent_name,
    alias: str,
    base_root_path: str,
    base_chart,
    namespace: uuid.UUID,
) -> None:
    """Re-parent a CLI-created native account without changing its name or UUID."""
    from . import metadata as editor

    old_container = item.getparent()
    existing = _items(root)
    if parent_name is None:
        new_container = root
    else:
        descendants = (
            {name.casefold() for _, name, _, _ in _items(item.find(f"{{{PREDEF}}}ChildItems"))}
            if item.find(f"{{{PREDEF}}}ChildItems") is not None
            else set()
        )
        own_name = item.findtext(f"{{{PREDEF}}}Name") or ""
        editor.require(
            parent_name.casefold() != own_name.casefold() and parent_name.casefold() not in descendants,
            "Account cannot become its own descendant",
            3,
        )
        native_by_name = {n.casefold(): node for node, n, _, state in existing if state == "Native"}
        if parent_name.casefold() in native_by_name:
            parent_node = native_by_name[parent_name.casefold()]
        else:
            base_predefined, _ = _xml(snapshot, alias, path_for("ChartsOfAccount", chart_name))
            base_items = _items(base_predefined) if base_predefined is not None else []
            parent_node, _ = _ensure_base_parent_chain(
                snapshot,
                target,
                chart_name,
                base_items,
                root,
                existing,
                parent_name,
                base_root_path,
                base_chart,
                namespace,
            )
            editor.require(parent_node is not None, "Missing materialized parent account", 4)
        assert parent_node is not None
        containers = parent_node.findall(f"{{{PREDEF}}}ChildItems")
        editor.require(len(containers) <= 1, "Ambiguous parent children", 4)
        new_container = containers[0] if containers else etree.SubElement(parent_node, f"{{{PREDEF}}}ChildItems")
    old_container.remove(item)
    new_container.append(item)
    if (
        old_container is not root
        and old_container.tag == f"{{{PREDEF}}}ChildItems"
        and not any(isinstance(child.tag, str) for child in old_container)
    ):
        old_container.getparent().remove(old_container)


def normalize_dimension_refs(snapshot, operation: dict) -> None:
    """Replace dumped subkonto UUID references with exact-base logical references."""
    from . import metadata as editor

    target = operation["target"]
    parameters = operation["parameters"]
    alias, _, _, base_chart, _ = _checked_chart(snapshot, target, parameters["baseRoot"])
    expected_chart, references = _dimension_lookup(snapshot, alias, base_chart)
    chart_name = target.split(".", 1)[1]
    path = path_for("ChartsOfAccount", chart_name)
    root, original = _xml(snapshot, "target", path, required=True)
    changed = False
    for item, _, _, _ in _items(root):
        containers = item.findall(f"{{{PREDEF}}}ExtDimensionTypes")
        editor.require(len(containers) <= 1, "Ambiguous predefined ExtDimensionTypes", 4)
        if not containers:
            continue
        for dimension in containers[0]:
            editor.require(dimension.tag == f"{{{PREDEF}}}ExtDimensionType", "Unexpected predefined subkonto node", 4)
            raw = dimension.get("name", "")
            resolved = _resolve_dimension_ref(raw, references, expected_chart)
            if raw != resolved:
                dimension.set("name", resolved)
                changed = True
    if changed:
        _stage_predefined(snapshot, path, root, original)


def _create_account(snapshot, operation: dict) -> None:
    from . import metadata as editor
    from . import metadata_borrow as borrow

    parameters = operation["parameters"]
    alias, object_path, target_chart, base_chart, target_data = _checked_chart(
        snapshot, operation["target"], parameters["baseRoot"]
    )
    target = operation["target"]
    chart_name = target.split(".", 1)[1]
    predef_path = path_for("ChartsOfAccount", chart_name)
    target_root, original = _xml(snapshot, "target", predef_path)
    base_root, _ = _xml(snapshot, alias, predef_path)
    existing = _items(target_root)[::] if target_root is not None else []
    base_items = _items(base_root) if base_root is not None else []
    name = parameters["name"]
    editor.require(
        name.casefold() not in {item[1].casefold() for item in base_items},
        "Predefined account name already exists in base configuration",
        3,
    )
    same_name = [item for item in existing if item[1].casefold() == name.casefold()]
    editor.require(len(same_name) <= 1, "Duplicate predefined identity", 4)
    code = parameters["code"]
    base_codes = {(item[0].findtext(f"{{{PREDEF}}}Code") or "").casefold() for item in base_items}
    editor.require(code.casefold() not in base_codes, "Predefined account code already exists in base configuration", 3)
    code_matches = [
        item for item in existing if (item[0].findtext(f"{{{PREDEF}}}Code") or "").casefold() == code.casefold()
    ]
    editor.require(not any(item not in same_name for item in code_matches), "Predefined account code already exists", 3)
    code_length = editor.prop(base_chart, "CodeLength")
    description_length = editor.prop(base_chart, "DescriptionLength")
    editor.require(not code_length.isdigit() or len(code) <= int(code_length), "Account code exceeds chart length")
    editor.require(
        not description_length.isdigit() or len(parameters["description"]) <= int(description_length),
        "Account description exceeds chart length",
    )

    account_flags = _names(base_chart, "AccountingFlag")
    editor.require(
        set(parameters["accountingFlags"]) == account_flags, "Accounting flags must exactly match the base chart", 2
    )
    dimension_flags = _names(base_chart, "ExtDimensionAccountingFlag")
    ext_dimension_chart = editor.prop(base_chart, "ExtDimensionTypes")
    maximum = editor.prop(base_chart, "MaxExtDimensionCount")
    dimensions = parameters["extDimensions"]
    editor.require(
        len(dimensions) <= (int(maximum) if maximum.isdigit() else len(dimensions)), "Too many extra dimensions"
    )
    seen_dimensions = set()
    for dim in dimensions:
        match = DIMENSION_REF.fullmatch(dim["name"])
        editor.require(
            match and dim["name"].rsplit(".", 1)[0] == ext_dimension_chart,
            "Subkonto must belong to the chart extra-dimension type",
        )
        editor.require(dim["name"].casefold() not in seen_dimensions, "Duplicate subkonto")
        seen_dimensions.add(dim["name"].casefold())
        editor.require(
            set(dim["accountingFlags"]) == dimension_flags, "Extra-dimension flags must exactly match the base chart", 2
        )
        type_kind, type_object, value_name = dim["name"].split(".")
        type_path = f"{borrow.DIRECTORIES[type_kind]}/{type_object}.xml"
        target_config, _ = borrow._checked(snapshot, "target", "Configuration.xml", "Configuration")
        if borrow._linked(borrow._registrations(target_config), type_kind, type_object):
            type_node, _ = borrow._checked(snapshot, "target", type_path, type_kind)
            type_alias = "target"
        else:
            type_node, _ = borrow._checked(snapshot, alias, type_path, type_kind)
            type_alias = alias
        extension_type_state = editor.prop(type_node, "ObjectBelonging")
        if extension_type_state == "Adopted":
            base_type, _ = borrow._checked(snapshot, alias, type_path, type_kind)
            editor.require(
                (editor.prop(type_node, "ExtendedConfigurationObject") or "").lower() == editor.identity(base_type),
                "Adopted subkonto chart base link mismatch",
                3,
            )
            type_alias = alias
        type_predef_path = path_for("ChartsOfCharacteristicType", type_object)
        item_exists = False
        for candidate_alias in dict.fromkeys((type_alias, "target", alias)):
            type_items, _ = _xml(snapshot, candidate_alias, type_predef_path)
            if type_items is not None and any(item[1] == value_name for item in _items(type_items)):
                item_exists = True
                break
        editor.require(item_exists, "Subkonto predefined item does not exist", 3)

    extension_config, _ = borrow._checked(snapshot, "target", "Configuration.xml", "Configuration")
    namespace = uuid.UUID(editor.identity(extension_config))
    parent_name = parameters.get("parent")
    if target_root is None and parent_name is not None:
        version = target_chart.getparent().get("version")
        editor.require(version in {"2.17", "2.20"}, "Unsupported metadata version", 4)
        target_root = etree.Element(
            f"{{{PREDEF}}}PredefinedData",
            nsmap={
                None: PREDEF,
                "v8": editor.V8,
                "xr": borrow.XR,
                "xs": editor.XS,
                "xsi": XSI,
            },
            attrib={f"{{{XSI}}}type": "ChartOfAccountsPredefinedItems", "version": version},
        )
    native_by_name = {n.casefold(): node for node, n, _, state in existing if state == "Native"}
    parent_chain_changed = False
    if parent_name is None:
        parent_container = target_root
    elif parent_name.casefold() in native_by_name:
        parent = native_by_name[parent_name.casefold()]
        containers = parent.findall(f"{{{PREDEF}}}ChildItems")
        editor.require(len(containers) <= 1, "Ambiguous parent children", 4)
        parent_container = containers[0] if containers else etree.SubElement(parent, f"{{{PREDEF}}}ChildItems")
    else:
        editor.require(
            parent_name.casefold() not in {n.casefold() for _, n, _, state in existing if state != "AdoptedCheck"},
            "Parent conflicts with an existing extension account",
            3,
        )
        parent_node, parent_chain_changed = _ensure_base_parent_chain(
            snapshot,
            target,
            chart_name,
            base_items,
            target_root,
            existing,
            parent_name,
            parameters["baseRoot"],
            base_chart,
            namespace,
        )
        if parent_node is None:
            raise editor.Rejected("Missing materialized parent account", 4)
        containers = parent_node.findall(f"{{{PREDEF}}}ChildItems")
        editor.require(len(containers) <= 1, "Ambiguous parent children", 4)
        parent_container = containers[0] if containers else etree.SubElement(parent_node, f"{{{PREDEF}}}ChildItems")

    item_id = str(uuid.uuid5(namespace, target + ".Predefined." + name))
    if same_name:
        node, _, existing_parent, existing_state = same_name[0]
        editor.require(
            existing_state == "Native"
            and _same_requested_item(node, existing_parent, item_id, parameters, chart_name, account_flags),
            "Existing predefined account conflicts with request",
            3,
        )
        _ensure_chart_predefined_dependencies(snapshot, object_path, base_chart, parameters["baseRoot"], chart_name)
        if parent_chain_changed:
            _stage_predefined(snapshot, predef_path, target_root, original)
        return

    if target_root is None:
        version = target_chart.getparent().get("version")
        editor.require(version in {"2.17", "2.20"}, "Unsupported metadata version", 4)
        target_root = etree.Element(
            f"{{{PREDEF}}}PredefinedData",
            nsmap={
                None: PREDEF,
                "v8": editor.V8,
                "xr": borrow.XR,
                "xs": editor.XS,
                "xsi": XSI,
            },
            attrib={f"{{{XSI}}}type": "ChartOfAccountsPredefinedItems", "version": version},
        )
        parent_container = target_root
    if parent_container is None:
        raise editor.Rejected("Missing parent container", 4)

    occupied_ids = {item[0].get("id") for item in [*_items(target_root), *base_items]}
    editor.require(item_id not in occupied_ids, "Generated predefined UUID collision", 3)
    item = etree.Element(f"{{{PREDEF}}}Item", id=item_id)
    for key, value in [
        ("Name", name),
        ("Code", code),
        ("Description", parameters["description"]),
        ("AccountType", parameters["accountType"]),
        ("OffBalance", str(parameters["offBalance"]).lower()),
    ]:
        etree.SubElement(item, f"{{{PREDEF}}}{key}").text = value
    etree.SubElement(item, f"{{{PREDEF}}}Order")
    etree.SubElement(item, f"{{{PREDEF}}}ExtensionState").text = "Native"
    flags_node = etree.SubElement(item, f"{{{PREDEF}}}AccountingFlags")
    for flag in sorted(account_flags):
        node = etree.SubElement(flags_node, f"{{{PREDEF}}}Flag", ref=f"{CHART}.{chart_name}.AccountingFlag.{flag}")
        node.text = str(parameters["accountingFlags"][flag]).lower()
    dimensions_node = etree.SubElement(item, f"{{{PREDEF}}}ExtDimensionTypes")
    for dim in dimensions:
        dimension = etree.SubElement(dimensions_node, f"{{{PREDEF}}}ExtDimensionType", name=dim["name"])
        etree.SubElement(dimension, f"{{{PREDEF}}}Turnover").text = str(dim["turnover"]).lower()
        dim_flags = etree.SubElement(dimension, f"{{{PREDEF}}}AccountingFlags")
        for flag in sorted(dimension_flags):
            node = etree.SubElement(
                dim_flags, f"{{{PREDEF}}}Flag", ref=f"{CHART}.{chart_name}.ExtDimensionAccountingFlag.{flag}"
            )
            node.text = str(dim["accountingFlags"][flag]).lower()
    parent_container.append(item)
    _stage_predefined(snapshot, predef_path, target_root, original)
    _ensure_chart_predefined_dependencies(snapshot, object_path, base_chart, parameters["baseRoot"], chart_name)


def _create_characteristic(snapshot, operation: dict) -> None:
    from . import metadata as editor
    from . import metadata_borrow as borrow

    target = operation["target"]
    parameters = operation["parameters"]
    alias, descriptor_path, target_chart, base_chart = _checked_characteristic_chart(
        snapshot, target, parameters["baseRoot"]
    )
    chart_name = target.split(".", 1)[1]
    base_types = _characteristic_types(base_chart)
    target_types = _characteristic_types(target_chart)
    editor.require(
        parameters["type"] in base_types | target_types,
        "Characteristic value type is not allowed by base or extension chart",
        3,
    )
    code_length = editor.prop(base_chart, "CodeLength")
    editor.require(code_length.isdigit() and int(code_length) > 0, "Invalid base characteristic chart CodeLength", 4)
    editor.require(len(parameters["code"]) <= int(code_length), "Characteristic code exceeds base chart length", 3)
    description_length = editor.prop(base_chart, "DescriptionLength")
    editor.require(
        not description_length.isdigit() or len(parameters["description"]) <= int(description_length),
        "Characteristic description exceeds base chart length",
        3,
    )

    predef_path = path_for("ChartsOfCharacteristicType", chart_name)
    target_root, original = _xml(snapshot, "target", predef_path)
    base_root, _ = _xml(snapshot, alias, predef_path)
    existing = _items(target_root) if target_root is not None else []
    base_items = _items(base_root) if base_root is not None else []
    name = parameters["name"]
    editor.require(
        name.casefold() not in {item[1].casefold() for item in base_items},
        "Predefined characteristic name already exists in base configuration",
        3,
    )
    editor.require(
        parameters["code"].casefold()
        not in {(item[0].findtext(f"{{{PREDEF}}}Code") or "").casefold() for item in base_items},
        "Predefined characteristic code already exists in base configuration",
        3,
    )
    same_name = [item for item in existing if item[1].casefold() == name.casefold()]
    editor.require(len(same_name) <= 1, "Duplicate predefined identity", 4)
    code = parameters["code"]
    editor.require(
        not any(
            (item[0].findtext(f"{{{PREDEF}}}Code") or "").casefold() == code.casefold() and item not in same_name
            for item in existing
        ),
        "Predefined characteristic code already exists",
        3,
    )

    config, _ = borrow._checked(snapshot, "target", "Configuration.xml", "Configuration")
    namespace = uuid.UUID(editor.identity(config))
    item_id = str(uuid.uuid5(namespace, target + ".Predefined." + name))
    if same_name:
        node, _, _, state = same_name[0]
        fields = [child.tag.rsplit("}", 1)[-1] for child in node]
        expected_fields = {"Name", "Code", "Description", "Type", "IsFolder", "ExtensionState"}
        if "ChildItems" in fields:
            fields.remove("ChildItems")
        editor.require(
            len(fields) == len(expected_fields)
            and set(fields) == expected_fields
            and node.get("id") == item_id
            and state == "Native"
            and node.findtext(f"{{{PREDEF}}}Name") == name
            and node.findtext(f"{{{PREDEF}}}Code") == code
            and node.findtext(f"{{{PREDEF}}}Description") == parameters["description"]
            and _characteristic_item_type(node) == parameters["type"]
            and _bool(node.find(f"{{{PREDEF}}}IsFolder")) is False,
            "Existing predefined characteristic conflicts with request",
            3,
        )
        _ensure_characteristic_dependencies(snapshot, descriptor_path, base_chart)
        return

    existing_ids = {node.get("id") for node, _, _, _ in [*existing, *base_items]}
    editor.require(item_id not in existing_ids, "Generated characteristic predefined UUID collision", 3)
    if target_root is None:
        version = target_chart.getparent().get("version")
        editor.require(version in {"2.17", "2.20"}, "Unsupported metadata version", 4)
        target_root = etree.Element(
            f"{{{PREDEF}}}PredefinedData",
            nsmap={
                None: PREDEF,
                "v8": editor.V8,
                "xr": borrow.XR,
                "xs": editor.XS,
                "xsi": XSI,
            },
            attrib={f"{{{XSI}}}type": "PlanOfCharacteristicKindPredefinedItems", "version": version},
        )
    item = etree.Element(f"{{{PREDEF}}}Item", id=item_id)
    for key, value in [("Name", name), ("Code", code), ("Description", parameters["description"])]:
        etree.SubElement(item, f"{{{PREDEF}}}{key}").text = value
    type_node = etree.SubElement(item, f"{{{PREDEF}}}Type")
    type_child = etree.SubElement(type_node, f"{{{editor.V8}}}Type", nsmap={"cfg": borrow.CFG})
    type_child.text = f"cfg:{parameters['type']}"
    etree.SubElement(item, f"{{{PREDEF}}}IsFolder").text = "false"
    etree.SubElement(item, f"{{{PREDEF}}}ExtensionState").text = "Native"
    target_root.append(item)
    _stage_predefined(snapshot, predef_path, target_root, original)
    _ensure_characteristic_dependencies(snapshot, descriptor_path, base_chart)


def _checked_catalog(snapshot, target: str):
    """Own (non-adopted) catalog: Designer stores its predefined items without ExtensionState."""
    from . import metadata as editor
    from . import metadata_borrow as borrow

    kind, name = target.split(".", 1)
    editor.require(kind == CATALOG and editor.NAME.fullmatch(name), "Expected Catalog target")
    config, _ = borrow._checked(snapshot, "target", "Configuration.xml", "Configuration")
    editor.require(borrow._linked(borrow._registrations(config), kind, name), "Catalog registration missing", 4)
    catalog, _ = borrow._checked(snapshot, "target", f"{borrow.DIRECTORIES[CATALOG]}/{name}.xml", kind)
    editor.require(editor.node_name(catalog) == name, "Catalog name mismatch", 4)
    editor.require(
        editor.prop(catalog, "ObjectBelonging") in {"", "Native"},
        "Predefined items of an adopted catalog are not supported",
        2,
    )
    lengths = {}
    for field in ("CodeLength", "DescriptionLength"):
        value = editor.prop(catalog, field)
        editor.require(value.isdigit(), f"Invalid catalog {field}", 4)
        lengths[field] = int(value)
    return config, catalog, lengths


def _catalog_item_fields(node) -> list[str]:
    return [child.tag.rsplit("}", 1)[-1] for child in node if isinstance(child.tag, str)]


def _create_catalog(snapshot, operation: dict) -> None:
    from . import metadata as editor

    target = operation["target"]
    parameters = operation["parameters"]
    config, catalog, lengths = _checked_catalog(snapshot, target)
    catalog_name = target.split(".", 1)[1]
    name = parameters["name"]
    code = parameters.get("code", "")
    description = parameters["description"]
    editor.require(len(code) <= lengths["CodeLength"], "Catalog code exceeds CodeLength", 3)
    editor.require(len(description) <= lengths["DescriptionLength"], "Catalog description exceeds DescriptionLength", 3)

    predef_path = path_for(CATALOG, catalog_name)
    target_root, original = _xml(snapshot, "target", predef_path)
    existing = _items(target_root) if target_root is not None else []
    same_name = [item for item in existing if item[1].casefold() == name.casefold()]
    if same_name:
        node, _, parent, state = same_name[0]
        editor.require(
            parent is None
            and state is None
            and _catalog_item_fields(node) == list(CATALOG_FIELDS)
            and node.findtext(f"{{{PREDEF}}}Name") == name
            and (node.findtext(f"{{{PREDEF}}}Code") or "") == code
            and (node.findtext(f"{{{PREDEF}}}Description") or "") == description
            and _bool(node.find(f"{{{PREDEF}}}IsFolder")) is False,
            "Existing predefined catalog item conflicts with request",
            3,
        )
        return
    editor.require(
        not code
        or not any((item[0].findtext(f"{{{PREDEF}}}Code") or "").casefold() == code.casefold() for item in existing),
        "Predefined catalog code already exists",
        3,
    )

    namespace = uuid.UUID(editor.identity(config))
    item_id = str(uuid.uuid5(namespace, target + ".Predefined." + name))
    editor.require(
        item_id not in {node.get("id") for node, _, _, _ in existing}, "Generated catalog predefined UUID collision", 3
    )
    if target_root is None:
        version = catalog.getparent().get("version")
        editor.require(version in {"2.17", "2.20"}, "Unsupported metadata version", 4)
        target_root = etree.Element(
            f"{{{PREDEF}}}PredefinedData",
            nsmap={
                None: PREDEF,
                "v8": editor.V8,
                "xr": "http://v8.1c.ru/8.3/xcf/readable",
                "xs": editor.XS,
                "xsi": XSI,
            },
            attrib={f"{{{XSI}}}type": "CatalogPredefinedItems", "version": version},
        )
    item = etree.Element(f"{{{PREDEF}}}Item", id=item_id)
    for key, value in [("Name", name), ("Code", code or None), ("Description", description), ("IsFolder", "false")]:
        etree.SubElement(item, f"{{{PREDEF}}}{key}").text = value
    target_root.append(item)
    # Designer layout (tab indentation) for every item, including ones added earlier in the same plan.
    etree.indent(target_root, space="\t")
    _stage_predefined(snapshot, predef_path, target_root, original)


def _verify_catalog(snapshot, target: str) -> None:
    from . import metadata as editor

    root, _ = _xml(snapshot, "target", path_for(CATALOG, target.split(".", 1)[1]))
    if root is None:
        return
    _, catalog, lengths = _checked_catalog(snapshot, target)
    hierarchical = editor.prop(catalog, "Hierarchical") == "true"
    codes = set()
    for node, _, parent, state in _items(root):
        editor.require(state is None, "Own catalog predefined item must not have ExtensionState", 4)
        fields = [field for field in _catalog_item_fields(node) if field != "ChildItems"]
        editor.require(fields == list(CATALOG_FIELDS), "Incomplete predefined catalog item", 4)
        is_folder = _bool(node.find(f"{{{PREDEF}}}IsFolder"))
        editor.require(hierarchical or (not is_folder and parent is None), "Folders require a hierarchical catalog", 4)
        code = node.findtext(f"{{{PREDEF}}}Code") or ""
        editor.require(len(code) <= lengths["CodeLength"], "Catalog code exceeds CodeLength", 4)
        editor.require(not code or code.casefold() not in codes, "Duplicate predefined catalog code", 4)
        codes.add(code.casefold())
        editor.require(
            len(node.findtext(f"{{{PREDEF}}}Description") or "") <= lengths["DescriptionLength"],
            "Catalog description exceeds DescriptionLength",
            4,
        )


def create(snapshot, operation: dict) -> None:
    from . import metadata as editor

    kind = operation["target"].split(".", 1)[0]
    if kind == CHARACTERISTIC_CHART:
        editor.require("type" in operation["parameters"], "Characteristic predefined parameters do not match target", 2)
        _create_characteristic(snapshot, operation)
    elif kind == CHART:
        editor.require("accountType" in operation["parameters"], "Account predefined parameters do not match target", 2)
        _create_account(snapshot, operation)
    elif kind == CATALOG:
        editor.require(
            set(operation["parameters"]) <= {"name", "code", "description", "isFolder"},
            "Catalog predefined parameters do not match target",
            2,
        )
        _create_catalog(snapshot, operation)
    else:
        editor.require(False, "Unsupported predefined target kind", 2)


def _verify_account(snapshot, target: str, base_root=None) -> None:
    from . import metadata as editor

    kind, name = target.split(".", 1)
    if kind != CHART:
        return
    root, _ = _xml(snapshot, "target", path_for("ChartsOfAccount", name))
    if root is not None:
        from . import metadata_borrow as borrow

        chart_path = f"{borrow.DIRECTORIES[CHART]}/{name}.xml"
        config, _ = borrow._checked(snapshot, "target", "Configuration.xml", "Configuration")
        chart, _ = borrow._checked(snapshot, "target", chart_path, CHART)
        extension_config = bool(editor.prop(config, "ConfigurationExtensionPurpose"))
        dimension_chart = editor.prop(chart, "ExtDimensionTypes")
        dimension_references = {}
        if base_root is not None:
            alias, _, _, base_chart, _ = _checked_chart(snapshot, target, str(base_root))
            dimension_chart, dimension_references = _dimension_lookup(snapshot, alias, base_chart)
        native_items = [node for node, _, _, state in _items(root) if state == "Native"]
        if extension_config and native_items:
            properties = chart.find(f"{{{editor.MD}}}Properties")
            if properties is None:
                raise editor.Rejected("Missing account chart Properties", 4)
            assert properties is not None
            for field in (
                "CodeLength",
                "DescriptionLength",
                "OrderLength",
                "ExtDimensionTypes",
                "MaxExtDimensionCount",
            ):
                values = properties.findall(f"{{{editor.MD}}}{field}")
                editor.require(
                    len(values) == 1 and (values[0].text or "").strip(),
                    f"Native predefined accounts require chart {field}",
                    4,
                )
            for field in ("CodeLength", "DescriptionLength", "OrderLength", "MaxExtDimensionCount"):
                editor.require(
                    (properties.findtext(f"{{{editor.MD}}}{field}") or "").isdigit(), f"Invalid chart {field}", 4
                )
            for kind in ("AccountingFlag", "ExtDimensionAccountingFlag"):
                names = _names(chart, kind)
                editor.require(names, f"Native predefined accounts require chart {kind} members", 4)
        codes = set()
        for node, _, _, state in _items(root):
            editor.require(
                not editor.prop(config, "ConfigurationExtensionPurpose") or state in {"Native", "AdoptedCheck"},
                "CFE predefined item needs ExtensionState",
                4,
            )
            editor.require(
                node.findtext(f"{{{PREDEF}}}AccountType") in ACCOUNT_TYPES, "Invalid predefined account type", 4
            )
            code = node.findtext(f"{{{PREDEF}}}Code") or ""
            editor.require(
                bool(code) and code.casefold() not in codes, "Missing or duplicate predefined account code", 4
            )
            codes.add(code.casefold())
            _bool(node.find(f"{{{PREDEF}}}OffBalance"))
            editor.require(
                node.find(f"{{{PREDEF}}}Name") is not None
                and node.find(f"{{{PREDEF}}}Code") is not None
                and node.find(f"{{{PREDEF}}}Description") is not None
                and node.find(f"{{{PREDEF}}}AccountType") is not None
                and node.find(f"{{{PREDEF}}}OffBalance") is not None,
                "Incomplete predefined account",
                4,
            )
            account_flags = _flags(node, f"{CHART}.{name}.AccountingFlag.")
            if extension_config and state == "Native":
                editor.require(
                    set(account_flags) == _names(chart, "AccountingFlag"),
                    "Native predefined account flags do not match chart members",
                    4,
                )
            dims = node.findall(f"{{{PREDEF}}}ExtDimensionTypes/{{{PREDEF}}}ExtDimensionType")
            refs = [dim.get("name", "") for dim in dims]
            resolved_refs = [_resolve_dimension_ref(ref, dimension_references, dimension_chart) for ref in refs]
            editor.require(
                all(resolved.rsplit(".", 1)[0] == dimension_chart for resolved in resolved_refs)
                and len({ref.casefold() for ref in resolved_refs}) == len(resolved_refs),
                "Invalid or duplicate subkonto",
                4,
            )
            for dim in dims:
                _bool(dim.find(f"{{{PREDEF}}}Turnover"))
                dimension_flags = _flags(dim, f"{CHART}.{name}.ExtDimensionAccountingFlag.")
                if extension_config and state == "Native":
                    editor.require(
                        set(dimension_flags) == _names(chart, "ExtDimensionAccountingFlag"),
                        "Native predefined subkonto flags do not match chart members",
                        4,
                    )


def _verify_characteristic(snapshot, target: str, base_root=None) -> None:
    from pathlib import Path

    from . import metadata as editor
    from . import metadata_borrow as borrow

    kind, name = target.split(".", 1)
    root, _ = _xml(snapshot, "target", path_for("ChartsOfCharacteristicType", name))
    if root is None:
        return
    config, _ = borrow._checked(snapshot, "target", "Configuration.xml", "Configuration")
    extension = bool(editor.prop(config, "ConfigurationExtensionPurpose"))
    chart_path = f"{borrow.DIRECTORIES[kind]}/{name}.xml"
    chart, _ = borrow._checked(snapshot, "target", chart_path, kind)
    allowed_types = set()
    code_length = ""
    description_length = ""
    base_items = {}
    if base_root is not None:
        _, _, _, base_chart = _checked_characteristic_chart(snapshot, target, str(base_root))
        allowed_types = _characteristic_types(base_chart) | _characteristic_types(chart)
        code_length = editor.prop(base_chart, "CodeLength")
        description_length = editor.prop(base_chart, "DescriptionLength")
        base_alias = snapshot.source_root(Path(base_root))
        base_predefined, _ = _xml(snapshot, base_alias, path_for("ChartsOfCharacteristicType", name))
        base_items = (
            {item_name.casefold(): node for node, item_name, _, _ in _items(base_predefined)}
            if base_predefined is not None
            else {}
        )
        editor.require(
            code_length.isdigit() and int(code_length) > 0, "Invalid base characteristic chart CodeLength", 4
        )
    codes = set()
    for node, _, _, state in _items(root):
        editor.require(
            not extension or state in {"Native", "AdoptedCheck"},
            "CFE characteristic predefined item needs extension state",
            4,
        )
        fields = [child.tag.rsplit("}", 1)[-1] for child in node]
        editor.require(
            {"Name", "Code", "Description", "Type", "IsFolder"} <= set(fields),
            "Incomplete predefined characteristic",
            4,
        )
        code = node.findtext(f"{{{PREDEF}}}Code") or ""
        editor.require(
            bool(code) and code.casefold() not in codes, "Missing or duplicate characteristic predefined code", 4
        )
        codes.add(code.casefold())
        is_folder = _bool(node.find(f"{{{PREDEF}}}IsFolder"))
        item_type = _characteristic_item_type(node)
        if extension and state == "Native":
            editor.require(not is_folder and item_type, "Native CFE characteristic items must be typed leaves", 4)
        if extension and state == "AdoptedCheck":
            source = base_items.get((node.findtext(f"{{{PREDEF}}}Name") or "").casefold())
            editor.require(
                source is not None
                and node.findtext(f"{{{PREDEF}}}Code") == source.findtext(f"{{{PREDEF}}}Code")
                and node.findtext(f"{{{PREDEF}}}Description") == source.findtext(f"{{{PREDEF}}}Description")
                and item_type == _characteristic_item_type(source)
                and is_folder == _bool(source.find(f"{{{PREDEF}}}IsFolder")),
                "AdoptedCheck characteristic item differs from base",
                4,
            )
        if item_type and base_root is not None:
            editor.require(
                item_type in allowed_types,
                "Characteristic predefined Type is not allowed by base or extension chart",
                4,
            )
        if extension and state == "Native" and code_length:
            editor.require(len(code) <= int(code_length), "Characteristic code exceeds base chart length", 4)
        description = node.findtext(f"{{{PREDEF}}}Description") or ""
        if description_length.isdigit():
            editor.require(
                len(description) <= int(description_length), "Characteristic description exceeds base chart length", 4
            )


def verify(snapshot, target: str, base_root=None) -> None:
    kind, _ = target.split(".", 1)
    if kind == CHARACTERISTIC_CHART:
        _verify_characteristic(snapshot, target, base_root)
    elif kind == CHART:
        _verify_account(snapshot, target, base_root)
    elif kind == CATALOG:
        _verify_catalog(snapshot, target)
