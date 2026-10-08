"""Small, strict metadata operations for adopted catalogs and charts."""

from __future__ import annotations

import copy
import re
import uuid

import lxml.etree as etree

from . import metadata_borrow as borrow
from . import metadata_object_ops

PREDEF = "http://v8.1c.ru/8.3/xcf/predef"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
CFG = "http://v8.1c.ru/8.1/data/enterprise/current-config"
CORE = "http://v8.1c.ru/8.1/data/core"
NS = {"p": PREDEF, "v8": CORE, "m": borrow.MD, "xr": borrow.XR}
PREDEFINED_TYPES = {
    "ChartOfAccounts": "ChartOfAccountsPredefinedItems",
    "ChartOfCharacteristicTypes": "PlanOfCharacteristicKindPredefinedItems",
}
ACCOUNT_FLAGS = ("Валютный", "Количественный", "УчетПоПодразделениям", "НалоговыйУчет")
EXT_FLAGS = ("Суммовой", "Валютный", "Количественный")


def _canonical_type(member):
    from . import metadata as editor

    value = member.text or ""
    prefix, separator, local = value.partition(":")
    namespace = member.nsmap.get(prefix) if separator else None
    namespace = namespace or {"cfg": borrow.CFG, "v8": CORE, "xs": editor.XS}.get(prefix)
    names = {borrow.CFG: "cfg", CORE: "v8", editor.XS: "xs"}
    if not separator or not local or namespace not in names:
        raise editor.Rejected("Invalid characteristic Type QName", 4)
    return names[namespace] + ":" + local


def _type_spec(member):
    return (etree.QName(member).localname, _canonical_type(member), tuple(sorted(member.attrib.items())))


def _item_name(item):
    value = item.findtext(f"{{{PREDEF}}}Name") or ""
    return value


def _items(root):
    for item in root.findall(f"{{{PREDEF}}}Item"):
        yield item, None
        children = item.find(f"{{{PREDEF}}}ChildItems")
        if children is not None:
            yield from _children(children, item)


def _children(container, parent):
    for item in container.findall(f"{{{PREDEF}}}Item"):
        yield item, parent
        nested = item.find(f"{{{PREDEF}}}ChildItems")
        if nested is not None:
            yield from _children(nested, item)


def _require_uuid(value, message):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError(message) from None


def _predefined_path(kind, name):
    directory = borrow.DIRECTORIES[kind]
    return f"{directory}/{name}/Ext/Predefined.xml"


def _descriptor(snapshot, target, kind):
    from . import metadata as editor

    config, node, path, original = metadata_object_ops.read_object(snapshot, target)
    editor.require(
        kind == target.split(".")[0] and editor.prop(node, "ObjectBelonging") == "Adopted",
        "Predefined items require an adopted chart",
        3,
    )
    metadata_object_ops.exact_base_owner(snapshot, node, path)
    return config, node, path, original


def _base_predefined(snapshot, kind, name, descriptor_path, expected_uuid):
    """Read the exact base predefined file already declared by object.borrow."""
    from . import metadata as editor

    for alias, root in snapshot.roots.items():
        if alias == "target":
            continue
        base_bytes = snapshot.read(alias, descriptor_path, optional=True)
        if base_bytes is None:
            continue
        base = editor.metadata(base_bytes, kind)
        if editor.identity(base) != expected_uuid:
            continue
        path = _predefined_path(kind, name)
        data = snapshot.read(alias, path, optional=True)
        if data is None:
            return None
        root = editor.xml_read(data, f"{{{PREDEF}}}PredefinedData")
        return root
    return None


def _named_predefined_exists(snapshot, kind, name, item_name):
    """Require one unambiguous item from target or its exact base context."""
    from . import metadata as editor

    candidates = []
    candidate_shapes = []
    descriptor_path = f"{borrow.DIRECTORIES[kind]}/{name}.xml"
    for alias in snapshot.roots:
        data = snapshot.read(alias, descriptor_path, optional=True)
        if data is None:
            continue
        descriptor = editor.metadata(data, kind)
        if editor.prop(descriptor, "Name") != name:
            continue
        if alias == "target" and editor.prop(descriptor, "ObjectBelonging") == "Adopted":
            for base_alias in snapshot.roots:
                if base_alias != "target":
                    snapshot.read(base_alias, descriptor_path, optional=True)
            metadata_object_ops.exact_base_owner(snapshot, descriptor, descriptor_path)
        predefined = snapshot.read(alias, _predefined_path(kind, name), optional=True)
        if predefined is None:
            continue
        root = editor.xml_read(predefined, f"{{{PREDEF}}}PredefinedData")
        for item, _ in _items(root):
            if _item_name(item).casefold() != item_name.casefold():
                continue
            candidates.append(item)
            normalized = copy.deepcopy(item)
            if (
                alias == "target"
                and editor.prop(descriptor, "ObjectBelonging") == "Adopted"
                and normalized.findtext(f"{{{PREDEF}}}ExtensionState") in {"Adopted", "AdoptedCheck"}
            ):
                marker = normalized.find(f"{{{PREDEF}}}ExtensionState")
                normalized.remove(marker)
            candidate_shapes.append(_without_id(normalized, snapshot))
    editor.require(
        candidates and len({item.get("id") for item in candidates}) == 1 and len(set(candidate_shapes)) == 1,
        "Referenced predefined item is missing or ambiguous",
        3,
    )


def _predefined_type_member(snapshot, member):
    """Use base TypeId only when a concrete reference is absent from the extension."""
    from . import metadata as editor

    result = copy.deepcopy(member)
    if member.tag == f"{{{CORE}}}TypeId":
        result.text = _require_uuid(member.text, "Invalid predefined TypeId")
        return result
    value = _canonical_type(member)
    prefix, separator, local = value.partition(":")
    if not separator or prefix != "cfg":
        return result
    family, dot, name = local.partition(".")
    owners = {prefix: kind for kind, generated in borrow.GENERATED_TYPES.items() for prefix, _ in generated}
    editor.require(
        dot and family in owners and editor.NAME.fullmatch(name), "Invalid predefined characteristic Type reference", 3
    )
    kind = owners[family]
    descriptor_path = f"{borrow.DIRECTORIES[kind]}/{name}.xml"
    target_data = snapshot.read("target", descriptor_path, optional=True)
    if target_data is not None:
        target = editor.metadata(target_data, kind)
        editor.require(editor.prop(target, "Name") == name, "Type descriptor name mismatch", 3)
        if editor.prop(target, "ObjectBelonging") == "Adopted":
            for alias in snapshot.roots:
                if alias != "target":
                    snapshot.read(alias, descriptor_path, optional=True)
            metadata_object_ops.exact_base_owner(snapshot, target, descriptor_path)
        return result
    candidates = []
    for alias in snapshot.roots:
        if alias == "target":
            continue
        data = snapshot.read(alias, descriptor_path, optional=True)
        if data is None:
            continue
        descriptor = editor.metadata(data, kind)
        editor.require(editor.prop(descriptor, "Name") == name, "Type descriptor name mismatch", 3)
        generated = descriptor.findall(f'm:InternalInfo/xr:GeneratedType[@name="{local}"]/xr:TypeId', NS)
        editor.require(len(generated) == 1, "Base reference GeneratedType is missing or ambiguous", 3)
        candidates.append(
            (editor.identity(descriptor), _require_uuid(generated[0].text, "Invalid base reference TypeId"))
        )
    editor.require(
        candidates and len(set(candidates)) == 1, "Predefined characteristic Type reference is missing or ambiguous", 3
    )
    result.tag = f"{{{CORE}}}TypeId"
    result.text = candidates[0][1]
    return result


def _normalize_predefined_type(snapshot, item):
    normalized = copy.deepcopy(item)
    for type_node in normalized.findall(f"{{{PREDEF}}}Type"):
        for member in list(type_node):
            if member.tag in {f"{{{CORE}}}Type", f"{{{CORE}}}TypeId"}:
                type_node.replace(member, _predefined_type_member(snapshot, member))
    return normalized


def _read_predefined(snapshot, kind, name, owner):
    from . import metadata as editor

    owner_root = owner.getparent()
    version = owner_root.get("version") if owner_root is not None else None
    editor.require(version in {"2.17", "2.20"}, "Unsupported chart owner format version", 4)
    path = _predefined_path(kind, name)
    original = snapshot.read("target", path, optional=True)
    if original is None:
        root = etree.Element(
            f"{{{PREDEF}}}PredefinedData",
            nsmap={None: PREDEF, "v8": editor.V8, "xr": borrow.XR, "xs": editor.XS, "xsi": XSI},
            **{f"{{{XSI}}}type": PREDEFINED_TYPES[kind], "version": version},
        )
        return path, root, original
    root = editor.xml_read(original, f"{{{PREDEF}}}PredefinedData")
    editor.require(
        root.get("version") in {"2.17", "2.20"} and root.get(f"{{{XSI}}}type") == PREDEFINED_TYPES[kind],
        "Invalid predefined data file",
        4,
    )
    root.set("version", version)
    return path, root, original


def _serialize(root, original):
    from . import metadata as editor

    if original is not None:
        return editor.serialize_like(root, original)
    etree.indent(root, space="\t")
    data = b'<?xml version="1.0" encoding="UTF-8"?>\n' + etree.tostring(root, encoding="utf-8") + b"\n"
    editor.xml_read(data, f"{{{PREDEF}}}PredefinedData")
    return data


def _new_item(root, definition, kind, item_id, snapshot=None, allowed_types=None):
    from . import metadata as editor

    item = etree.Element(f"{{{PREDEF}}}Item", id=item_id)
    for key in ("name", "code", "description"):
        etree.SubElement(item, f"{{{PREDEF}}}{key.title()}").text = definition[key]
    if kind == "ChartOfAccounts":
        etree.SubElement(item, f"{{{PREDEF}}}AccountType").text = definition["accountType"]
        etree.SubElement(item, f"{{{PREDEF}}}OffBalance").text = str(definition["offBalance"]).lower()
        etree.SubElement(item, f"{{{PREDEF}}}Order").text = definition["order"]
        flags = etree.SubElement(item, f"{{{PREDEF}}}AccountingFlags")
        for name in ACCOUNT_FLAGS:
            flag = etree.SubElement(
                flags, f"{{{PREDEF}}}Flag", ref=f"ChartOfAccounts.{root.get('chartName')}.AccountingFlag.{name}"
            )
            flag.text = str(definition["accountingFlags"][name]).lower()
        dimensions = etree.SubElement(item, f"{{{PREDEF}}}ExtDimensionTypes")
        for dimension in definition.get("extDimensionTypes", []):
            ext = etree.SubElement(dimensions, f"{{{PREDEF}}}ExtDimensionType", name=dimension["name"])
            etree.SubElement(ext, f"{{{PREDEF}}}Turnover").text = str(dimension["turnover"]).lower()
            ext_flags = etree.SubElement(ext, f"{{{PREDEF}}}AccountingFlags")
            for name in EXT_FLAGS:
                flag = etree.SubElement(
                    ext_flags,
                    f"{{{PREDEF}}}Flag",
                    ref=f"ChartOfAccounts.{root.get('chartName')}.ExtDimensionAccountingFlag.{name}",
                )
                flag.text = str(dimension["accountingFlags"][name]).lower()
    else:
        from . import metadata_create

        type_node = etree.SubElement(item, f"{{{PREDEF}}}Type")
        values = definition["type"] if isinstance(definition["type"], list) else [definition["type"]]
        for value in values:
            typed = metadata_create.type_node(value)
            members = typed.findall("v8:Type", {"v8": CORE})
            editor.require(
                len(members) == 1 and not typed.findall("v8:TypeSet", {"v8": CORE}),
                "Predefined characteristic Type must be one concrete reference type",
                2,
            )
            editor.require(
                (members[0].text or "").startswith("cfg:"),
                "Predefined characteristic Type must be a metadata reference",
                2,
            )
            if allowed_types is not None:
                editor.require(
                    _type_spec(members[0]) in allowed_types,
                    "Predefined characteristic Type is not allowed by the chart Type",
                    3,
                )
            member = _predefined_type_member(snapshot, members[0]) if snapshot is not None else members[0]
            etree.SubElement(type_node, member.tag, nsmap={"cfg": CFG}).text = member.text
        etree.SubElement(item, f"{{{PREDEF}}}IsFolder").text = str(definition["isFolder"]).lower()
    etree.SubElement(item, f"{{{PREDEF}}}ExtensionState").text = "Native"
    return item


def _without_id(item, snapshot=None):
    if snapshot is not None:
        item = _normalize_predefined_type(snapshot, item)

    def semantic(node):
        text = node.text.strip() if node.text and node.text.strip() else None
        if snapshot is not None and node.tag == f"{{{CORE}}}Type":
            text = _canonical_type(node)
        attributes = tuple(sorted((key, value) for key, value in node.attrib.items() if key != "id"))
        children = tuple(semantic(child) for child in node if etree.QName(child).localname != "ChildItems")
        if node.tag == f"{{{PREDEF}}}Type":
            children = tuple(sorted(children))
        return node.tag, attributes, text, children

    return semantic(item)


def _ensure_chart_dependencies(
    snapshot,
    config,
    node,
    base_descriptor,
    descriptor_path,
    original,
    *,
    property_names=None,
    include_account_flags=True,
):
    """Project only the base chart members needed to read account predefined data.

    An object.borrow shell intentionally has no chart properties or child objects.
    The predefined XML still refers to the chart's code/description rules and
    accounting flags, so the platform needs those exact adopted dependencies in
    the extension descriptor.  Existing target members are never rewritten.
    """
    from . import metadata as editor

    if property_names is None:
        property_names = (
            "CodeLength",
            "DescriptionLength",
            "CodeMask",
            "MaxExtDimensionCount",
            "ExtDimensionTypes",
            "AutoOrderByCode",
            "OrderLength",
        )
    target_properties = node.find(f"{{{editor.MD}}}Properties")
    base_properties = base_descriptor.find(f"{{{editor.MD}}}Properties")
    if target_properties is None or base_properties is None:
        raise editor.Rejected("Chart properties are missing or ambiguous", 4)
    changed = False
    for name in property_names:
        expected_matches = base_properties.findall(f"{{{editor.MD}}}{name}")
        editor.require(len(expected_matches) <= 1, f"Duplicate base chart property: {name}", 4)
        expected = expected_matches[0] if expected_matches else None
        if expected is None:
            continue
        current_matches = target_properties.findall(f"{{{editor.MD}}}{name}")
        editor.require(len(current_matches) <= 1, f"Duplicate adopted chart property: {name}", 4)
        current = current_matches[0] if current_matches else None
        if current is None:
            target_properties.append(copy.deepcopy(expected))
            changed = True
            continue
        editor.require(
            not len(current)
            and not len(expected)
            and current.text == expected.text
            and tuple(sorted(current.attrib.items())) == tuple(sorted(expected.attrib.items())),
            f"Conflicting adopted chart property: {name}",
            3,
        )

    if not include_account_flags:
        if changed:
            snapshot.stage(descriptor_path, editor.serialize_like(node.getparent(), original))
        return

    base_children = base_descriptor.findall(f"{{{editor.MD}}}ChildObjects")
    target_children = node.findall(f"{{{editor.MD}}}ChildObjects")
    editor.require(
        len(base_children) == 1 and len(target_children) <= 1, "Chart ChildObjects are missing or ambiguous", 4
    )
    target_container = target_children[0] if target_children else etree.SubElement(node, f"{{{editor.MD}}}ChildObjects")
    if not target_children:
        changed = True
    target_by_name = {}
    for child in target_container:
        if child.tag not in {f"{{{editor.MD}}}AccountingFlag", f"{{{editor.MD}}}ExtDimensionAccountingFlag"}:
            continue
        child_name = editor.prop(child, "Name")
        key = etree.QName(child).localname, child_name.casefold()
        editor.require(key not in target_by_name, "Duplicate chart accounting flag", 4)
        target_by_name[key] = child

    occupied = borrow._uuid_inventory(snapshot)
    root_uuid = editor.identity(config)
    for base_child in base_children[0]:
        kind = etree.QName(base_child).localname
        if kind not in {"AccountingFlag", "ExtDimensionAccountingFlag"}:
            continue
        child_name = editor.prop(base_child, "Name")
        key = kind, child_name.casefold()
        current = target_by_name.get(key)
        if current is not None:
            belonging = editor.prop(current, "ObjectBelonging")
            link = editor.prop(current, "ExtendedConfigurationObject")
            editor.require(
                editor.prop(current, "Name") == child_name
                and belonging == "Adopted"
                and link
                and link.lower() == editor.identity(base_child),
                f"Conflicting adopted chart flag: {child_name}",
                3,
            )
            continue
        source_uuid = editor.identity(base_child)
        child_uuid = editor.allocate_uuid(root_uuid, kind, f"{descriptor_path}.{kind}.{child_name}", "object", occupied)
        adopted = etree.Element(f"{{{editor.MD}}}{kind}", uuid=child_uuid)
        etree.SubElement(adopted, f"{{{editor.MD}}}InternalInfo")
        properties = etree.SubElement(adopted, f"{{{editor.MD}}}Properties")
        for prop_name, value in (
            ("ObjectBelonging", "Adopted"),
            ("Name", child_name),
            ("Comment", None),
            ("ExtendedConfigurationObject", source_uuid),
        ):
            etree.SubElement(properties, f"{{{editor.MD}}}{prop_name}").text = value
        target_container.append(adopted)
        target_by_name[key] = adopted
        changed = True

    if changed:
        snapshot.stage(descriptor_path, editor.serialize_like(node.getparent(), original))


def _same_adopted_predefined_item(current, base, snapshot=None):
    """Compare a copied base item, accepting only platform's adopted marker."""
    if current.get("id") != base.get("id"):
        return False
    if _without_id(current, snapshot) == _without_id(base, snapshot):
        return True
    state = current.findtext(f"{{{PREDEF}}}ExtensionState")
    if state not in {"Adopted", "AdoptedCheck"}:
        return False
    normalized = copy.deepcopy(current)
    marker = normalized.find(f"{{{PREDEF}}}ExtensionState")
    if marker is not None:
        normalized.remove(marker)
    return _without_id(normalized, snapshot) == _without_id(base, snapshot)


def _ensure_predefined_property_state(node):
    from . import metadata as editor

    internal = node.find(f"{{{editor.MD}}}InternalInfo")
    editor.require(internal is not None, "Chart InternalInfo is missing", 4)
    states = internal.findall(f"{{{borrow.XR}}}PropertyState")
    predefined = [state for state in states if state.findtext(f"{{{borrow.XR}}}Property") == "Predefined"]
    editor.require(len(predefined) <= 1, "Duplicate Predefined property state", 4)
    if predefined:
        state = predefined[0]
        current = state.findtext(f"{{{borrow.XR}}}State")
        editor.require(current in {"Checked", "Extended"}, "Conflicting Predefined property state", 3)
        if current == "Checked":
            state.find(f"{{{borrow.XR}}}State").text = "Extended"
            return True
        return False
    state = etree.SubElement(internal, f"{{{borrow.XR}}}PropertyState")
    etree.SubElement(state, f"{{{borrow.XR}}}Property").text = "Predefined"
    etree.SubElement(state, f"{{{borrow.XR}}}State").text = "Extended"
    return True


def _ensure_base_characteristic_items(snapshot, account_base, references):
    """Add only the referenced root items inherited from the exact PVH base."""
    from . import metadata as editor

    grouped = {}
    for reference in references:
        parts = reference.split(".")
        editor.require(
            len(parts) == 3
            and parts[0] == "ChartOfCharacteristicTypes"
            and editor.NAME.fullmatch(parts[1])
            and editor.NAME.fullmatch(parts[2]),
            "Predefined account uses an invalid extDimensionType",
            3,
        )
        owner = editor.prop(account_base, "ExtDimensionTypes")
        editor.require(owner == ".".join(parts[:2]), "Predefined account uses an unknown extDimensionType", 3)
        grouped.setdefault(parts[1], set()).add(parts[2])

    for name, requested_names in grouped.items():
        target = f"ChartOfCharacteristicTypes.{name}"
        config, node, descriptor_path, original = _descriptor(snapshot, target, "ChartOfCharacteristicTypes")
        base_descriptor = metadata_object_ops.exact_base_owner(snapshot, node, descriptor_path)
        if base_descriptor is None:
            raise editor.Rejected("Exact base context required", 3)
        _ensure_chart_dependencies(
            snapshot,
            config,
            node,
            base_descriptor,
            descriptor_path,
            original,
            property_names=("Hierarchical", "CodeLength", "CodeAllowedLength", "DescriptionLength"),
            include_account_flags=False,
        )

        path, root, root_original = _read_predefined(snapshot, "ChartOfCharacteristicTypes", name, node)
        if any(item.findtext(f"{{{PREDEF}}}ExtensionState") == "Native" for item, _ in _items(root)):
            if _ensure_predefined_property_state(node):
                snapshot.stage(
                    descriptor_path, editor.serialize_like(node.getparent(), snapshot.read("target", descriptor_path))
                )
        base_root = _base_predefined(
            snapshot,
            "ChartOfCharacteristicTypes",
            name,
            descriptor_path,
            editor.prop(node, "ExtendedConfigurationObject"),
        )
        editor.require(base_root is not None, "Exact base characteristic predefined data is missing", 3)
        base_items = list(_items(base_root))
        base_names = [_item_name(item).casefold() for item, _ in base_items]
        base_codes = [(item.findtext(f"{{{PREDEF}}}Code") or "").casefold() for item, _ in base_items]
        base_ids = [item.get("id") for item, _ in base_items]
        editor.require(
            all(base_names)
            and len(base_names) == len(set(base_names))
            and all(base_codes)
            and len(base_codes) == len(set(base_codes))
            and all(base_ids)
            and len(base_ids) == len(set(base_ids)),
            "Duplicate base characteristic predefined item",
            4,
        )
        base_by_name = {_item_name(item).casefold(): (item, parent) for item, parent in base_items}
        existing = list(_items(root))
        existing_names = [_item_name(item).casefold() for item, _ in existing]
        existing_codes = [(item.findtext(f"{{{PREDEF}}}Code") or "").casefold() for item, _ in existing]
        existing_ids = [item.get("id") for item, _ in existing]
        editor.require(
            all(existing_names)
            and len(existing_names) == len(set(existing_names))
            and all(existing_codes)
            and len(existing_codes) == len(set(existing_codes))
            and all(existing_ids)
            and len(existing_ids) == len(set(existing_ids)),
            "Duplicate characteristic predefined item in target",
            4,
        )
        by_name = {_item_name(item).casefold(): (item, parent) for item, parent in existing}
        by_code = set(existing_codes)
        existing_ids = set(existing_ids)
        changed = False
        for item_name in sorted(requested_names, key=str.casefold):
            base_entry = base_by_name.get(item_name.casefold())
            if base_entry is None:
                continue
            base_item, base_parent = base_entry
            editor.require(
                base_parent is None and base_item.find(f"{{{PREDEF}}}ChildItems") is None,
                "Nested base characteristic predefined item is unsupported",
                3,
            )
            current_entry = by_name.get(item_name.casefold())
            if current_entry is not None:
                current, current_parent = current_entry
                editor.require(
                    current_parent is None and _same_adopted_predefined_item(current, base_item, snapshot),
                    "Conflicting adopted characteristic predefined item",
                    3,
                )
                normalized = _normalize_predefined_type(snapshot, current)
                if _without_id(current) != _without_id(normalized):
                    current.replace(current.find(f"{{{PREDEF}}}Type"), normalized.find(f"{{{PREDEF}}}Type"))
                    changed = True
                continue
            _named_predefined_exists(snapshot, "ChartOfCharacteristicTypes", name, item_name)
            code = (base_item.findtext(f"{{{PREDEF}}}Code") or "").casefold()
            base_id = _require_uuid(base_item.get("id"), "Base characteristic predefined UUID is invalid")
            editor.require(
                code and code not in by_code and base_id not in existing_ids,
                "Conflicting adopted characteristic predefined code",
                3,
            )
            adopted = _normalize_predefined_type(snapshot, base_item)
            root.append(adopted)
            by_name[item_name.casefold()] = (adopted, None)
            by_code.add(code)
            existing_ids.add(base_id)
            changed = True
        candidate = _serialize(root, root_original)
        if changed or candidate != root_original:
            snapshot.stage(path, candidate)


def add_predefined(snapshot, operation):
    from . import metadata as editor

    target = operation["target"]
    kind, name = target.split(".", 1)
    config, node, descriptor_path, _ = _descriptor(snapshot, target, kind)
    base_descriptor = metadata_object_ops.exact_base_owner(snapshot, node, descriptor_path)
    if base_descriptor is None:
        raise editor.Rejected("Exact base context required", 3)
    if kind == "ChartOfCharacteristicTypes":
        _ensure_chart_dependencies(
            snapshot,
            config,
            node,
            base_descriptor,
            descriptor_path,
            snapshot.read("target", descriptor_path),
            property_names=("Hierarchical", "CodeLength", "CodeAllowedLength", "DescriptionLength"),
            include_account_flags=False,
        )
    elif kind == "ChartOfAccounts":
        _ensure_chart_dependencies(
            snapshot, config, node, base_descriptor, descriptor_path, snapshot.read("target", descriptor_path)
        )
    if operation["parameters"]["items"] and _ensure_predefined_property_state(node):
        snapshot.stage(
            descriptor_path, editor.serialize_like(node.getparent(), snapshot.read("target", descriptor_path))
        )
    for definition in operation["parameters"]["items"]:
        account_shape = {"accountType", "offBalance", "order", "accountingFlags"} <= set(definition)
        characteristic_shape = {"type", "isFolder"} <= set(definition)
        editor.require(
            (kind == "ChartOfAccounts" and account_shape and not characteristic_shape)
            or (kind == "ChartOfCharacteristicTypes" and characteristic_shape and not account_shape),
            "Predefined item kind does not match the target chart",
            2,
        )
    allowed_types = None
    if kind == "ChartOfCharacteristicTypes":
        allowed_types = set()
        base_type = base_descriptor.find("m:Properties/m:Type", editor.NS)
        if base_type is not None:
            allowed_types.update(
                _type_spec(member) for member in base_type if member.tag in {f"{{{CORE}}}Type", f"{{{CORE}}}TypeSet"}
            )
        target_type = node.find("m:Properties/m:Type", editor.NS)
        if target_type is not None:
            extended = target_type.find("xr:ExtendValue", NS)
            type_source = extended if extended is not None else target_type
            allowed_types.update(
                _type_spec(member) for member in type_source if member.tag in {f"{{{CORE}}}Type", f"{{{CORE}}}TypeSet"}
            )
        editor.require(allowed_types, "Chart characteristic Type is missing", 3)
    path, root, original = _read_predefined(snapshot, kind, name, node)
    root.set("chartName", name)
    base_root = _base_predefined(
        snapshot, kind, name, descriptor_path, editor.prop(node, "ExtendedConfigurationObject")
    )
    base_items = [] if base_root is None else list(_items(base_root))
    base_names = [_item_name(item).casefold() for item, _ in base_items]
    base_codes = [(item.findtext(f"{{{PREDEF}}}Code") or "").casefold() for item, _ in base_items]
    editor.require(
        len(base_names) == len(set(base_names)) and len(base_codes) == len(set(base_codes)),
        "Duplicate predefined name or code in base",
        4,
    )
    base_by_name = {_item_name(item).casefold(): item for item, _ in base_items}
    allowed_account_flags = set()
    allowed_ext_flags = set()
    if kind == "ChartOfAccounts":
        allowed_account_flags = {
            editor.prop(child, "Name")
            for child in base_descriptor.findall("m:ChildObjects/m:AccountingFlag", editor.NS)
        }
        allowed_ext_flags = {
            editor.prop(child, "Name")
            for child in base_descriptor.findall("m:ChildObjects/m:ExtDimensionAccountingFlag", editor.NS)
        }
    existing = list(_items(root))
    names = [_item_name(item).casefold() for item, _ in existing]
    codes = [(item.findtext(f"{{{PREDEF}}}Code") or "").casefold() for item, _ in existing]
    editor.require(
        all(names) and len(names) == len(set(names)) and len(codes) == len(set(codes)),
        "Duplicate predefined item in source",
        4,
    )
    by_name = {_item_name(item).casefold(): (item, parent) for item, parent in existing}
    by_code = set(codes)
    ids = [item.get("id") for item, _ in existing if item.get("id")]
    editor.require(len(ids) == len(set(ids)), "Duplicate predefined UUID in source", 4)
    occupied = set(ids)
    requested_names = {item["name"].casefold() for item in operation["parameters"]["items"]}
    if kind == "ChartOfAccounts":
        references = []
        for item, _ in existing:
            references.extend(
                ext.get("name")
                for ext in item.findall(f"{{{PREDEF}}}ExtDimensionTypes/{{{PREDEF}}}ExtDimensionType")
                if ext.get("name")
            )
        for definition in operation["parameters"]["items"]:
            references.extend(dimension["name"] for dimension in definition.get("extDimensionTypes", []))
            parent_name = definition.get("parent")
            seen_parents = set()
            while parent_name is not None:
                parent_key = parent_name.casefold()
                editor.require(parent_key not in seen_parents, "Cyclic base predefined parent", 4)
                seen_parents.add(parent_key)
                parent_item = base_by_name.get(parent_key)
                if parent_item is None:
                    break
                parent_parent = next((parent for item, parent in base_items if item is parent_item), None)
                references.extend(
                    ext.get("name")
                    for ext in parent_item.findall(f"{{{PREDEF}}}ExtDimensionTypes/{{{PREDEF}}}ExtDimensionType")
                    if ext.get("name")
                )
                parent_name = _item_name(parent_parent) if parent_parent is not None else None
        _ensure_base_characteristic_items(snapshot, base_descriptor, references)
    for definition in operation["parameters"]["items"]:
        item_name = definition["name"]
        if kind == "ChartOfAccounts":
            editor.require(
                set(definition["accountingFlags"]) <= allowed_account_flags,
                "Predefined account uses an unknown accounting flag",
                3,
            )
            for dimension in definition.get("extDimensionTypes", []):
                reference = dimension["name"]
                parts = reference.split(".")
                ext_owner = editor.prop(base_descriptor, "ExtDimensionTypes")
                editor.require(
                    len(parts) == 3 and ext_owner == ".".join(parts[:2]),
                    "Predefined account uses an unknown extDimensionType",
                    3,
                )
                _named_predefined_exists(snapshot, "ChartOfCharacteristicTypes", parts[1], parts[2])
                editor.require(
                    set(dimension["accountingFlags"]) <= allowed_ext_flags,
                    "Predefined account uses an unknown extDimension accounting flag",
                    3,
                )
        current = by_name.get(item_name.casefold())
        if current:
            requested_parent = definition.get("parent")
            current_parent = current[1]
            editor.require(
                (requested_parent is None and current_parent is None)
                or (
                    requested_parent is not None
                    and current_parent is not None
                    and _item_name(current_parent) == requested_parent
                ),
                "Conflicting predefined parent",
                3,
            )
            if item_name.casefold() in base_by_name:
                editor.require(
                    current[0].get("id") == base_by_name[item_name.casefold()].get("id")
                    and _without_id(current[0]) == _without_id(base_by_name[item_name.casefold()]),
                    "Conflicting predefined item with base",
                    3,
                )
            expected = _new_item(root, definition, kind, current[0].get("id"), snapshot, allowed_types)
            editor.require(
                _without_id(current[0], snapshot) == _without_id(expected, snapshot), "Conflicting predefined item", 3
            )
            if kind == "ChartOfCharacteristicTypes":
                normalized = _normalize_predefined_type(snapshot, current[0])
                if _without_id(current[0]) != _without_id(normalized):
                    current[0].replace(current[0].find(f"{{{PREDEF}}}Type"), normalized.find(f"{{{PREDEF}}}Type"))
            continue
        code = definition["code"].casefold()
        editor.require(item_name.casefold() not in base_by_name, "Conflicting predefined name", 3)
        editor.require(code not in by_code and code not in set(base_codes), "Conflicting predefined code", 3)
        parent_name = definition.get("parent")
        parent = None
        if parent_name:
            matches = [item for item, _ in _items(root) if _item_name(item) == parent_name]
            base_parent = base_by_name.get(parent_name.casefold())
            if base_parent is not None:
                editor.require(len(matches) <= 1, "Ambiguous predefined parent", 3)
                if matches:
                    editor.require(
                        matches[0].get("id") == base_parent.get("id")
                        and _without_id(matches[0]) == _without_id(base_parent),
                        "Conflicting predefined parent",
                        3,
                    )
                    parent = matches[0]
                else:
                    base_matches = [base_parent]
                    editor.require(len(base_matches) == 1, "Predefined parent is not present in the base or request", 3)
                    parent = copy.deepcopy(base_matches[0])
                    parent_children = parent.find(f"{{{PREDEF}}}ChildItems")
                    if parent_children is not None:
                        parent.remove(parent_children)
                    parent_id = _require_uuid(parent.get("id"), "Base predefined parent UUID is invalid")
                    editor.require(parent_id not in occupied, "Base predefined parent UUID conflicts in target", 3)
                    root.append(parent)
                    occupied.add(parent_id)
                    parent_name_key = _item_name(parent).casefold()
                    parent_code_key = (parent.findtext(f"{{{PREDEF}}}Code") or "").casefold()
                    editor.require(
                        parent_name_key not in by_name and parent_code_key not in by_code,
                        "Conflicting predefined parent",
                        3,
                    )
                    by_name[parent_name_key] = (parent, None)
                    by_code.add(parent_code_key)
            else:
                editor.require(
                    parent_name.casefold() in requested_names and len(matches) == 1,
                    "Predefined parent is not present in the base or request",
                    3,
                )
                parent = matches[0]
        item_id = editor.allocate_uuid(
            editor.identity(config),
            kind,
            f"{target}.Predefined.{item_name}",
            "item",
            {("predefined", path, value): value for value in occupied},
        )
        editor.require(item_id not in occupied, "Predefined UUID collision", 3)
        item = _new_item(root, definition, kind, item_id, snapshot, allowed_types)
        if parent is None:
            root.append(item)
        else:
            children = parent.find(f"{{{PREDEF}}}ChildItems")
            if children is None:
                children = etree.SubElement(parent, f"{{{PREDEF}}}ChildItems")
            children.append(item)
        by_name[item_name.casefold()] = (item, parent)
        by_code.add(code)
        occupied.add(item_id)
    root.attrib.pop("chartName", None)
    candidate = _serialize(root, original)
    if candidate != original:
        snapshot.stage(path, candidate)


def remove_predefined(snapshot, operation):
    """Remove one explicitly identified native leaf account, refusing dependencies."""
    from . import metadata as editor

    target = operation["target"]
    parts = target.split(".")
    editor.require(
        len(parts) == 2 and parts[0] == "ChartOfAccounts" and editor.NAME.fullmatch(parts[1]),
        "Only account removal is supported",
        2,
    )
    _, owner, descriptor_path, descriptor_original = _descriptor(snapshot, target, parts[0])
    name = operation["parameters"]["name"]
    expected = _require_uuid(operation["parameters"]["expectedUuid"], "Invalid expected UUID")
    path, root, original = _read_predefined(snapshot, parts[0], parts[1], owner)
    base = _base_predefined(
        snapshot, parts[0], parts[1], descriptor_path, editor.prop(owner, "ExtendedConfigurationObject")
    )
    editor.require(base is not None, "Exact base predefined data is missing", 3)
    editor.require(
        not any(
            _item_name(item).casefold() == name.casefold() or (item.get("id") or "").lower() == expected
            for item, _ in _items(base)
        ),
        "Cannot remove a base predefined item",
        3,
    )
    matches = [item for item, _ in _items(root) if _item_name(item).casefold() == name.casefold()]
    editor.require(len(matches) <= 1, "Ambiguous predefined name", 3)
    ids = [item for item, _ in _items(root) if (item.get("id") or "").lower() == expected]
    if not matches:
        editor.require(not ids, "Expected UUID belongs to another predefined item", 3)
        return
    item = matches[0]
    editor.require(_item_name(item) == name and ids == [item], "Predefined name or UUID conflict", 3)
    editor.require(
        item.findtext(f"{{{PREDEF}}}ExtensionState") == "Native", "Cannot remove an adopted predefined item", 3
    )
    editor.require(item.find(f"{{{PREDEF}}}ChildItems") is None, "Cannot remove a predefined item with children", 3)
    if original is None or editor.serialize_like(root, original) != original:
        raise editor.Rejected("Removal requires lossless predefined serialization", 3)
    reviewed = metadata_object_ops._reviewed_dependencies(
        snapshot, operation["parameters"].get("reviewedDependencies", ())
    )
    documents, files = metadata_object_ops.read_dependency_documents(
        snapshot, owner, descriptor_path, excluded_files={path, descriptor_path}, reviewed_dependencies=reviewed
    )
    # The chart was validated above; the generic rename shape excludes accounting flags.
    documents[descriptor_path] = (owner.getparent(), descriptor_original)
    parent = item.getparent()
    if parent is None:
        raise editor.Rejected("Predefined parent is missing", 4)
    parent.remove(item)
    candidate = editor.serialize_like(root, original)
    # Reviews handle opaque/dynamic dependencies; explicit references still block removal.
    token = re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", re.IGNORECASE)
    for source, data in {**files, path: candidate}.items():
        text = data.decode("utf-8-sig", errors="replace")
        editor.require(
            not token.search(text) and expected not in text.lower(),
            "Cannot remove referenced predefined item: " + source,
            3,
        )
    metadata_object_ops.check_or_rewrite_references(
        snapshot,
        documents,
        owner,
        descriptor_path,
        descriptor_original,
        False,
        name,
        target + "." + name,
        None,
        {},
        removed_ids={expected},
    )
    snapshot.stage(path, candidate)


def set_description_fill_checking(snapshot, operation):
    from . import metadata as editor

    target = operation["target"]
    editor.require(
        target.startswith("Catalog.") and editor.NAME.fullmatch(target.split(".", 1)[1]),
        "Description.FillChecking requires a Catalog",
        2,
    )
    _, node, path, original = metadata_object_ops.read_object(snapshot, target)
    standard = node.find('m:Properties/m:StandardAttributes/xr:StandardAttribute[@name="Description"]', NS)
    if standard is None:
        raise editor.Rejected("Catalog Description standard attribute is missing", 4)
    checking = standard.find(f"{{{borrow.XR}}}FillChecking")
    if checking is None or checking.text not in {"DontCheck", "ShowError", "ShowWarning"}:
        raise editor.Rejected("Catalog Description FillChecking is invalid", 4)
    value = operation["parameters"]["value"]
    if checking.text != value:
        checking.text = value
        snapshot.stage(path, editor.serialize_like(node.getparent(), original))


def extend_characteristic_type(snapshot, operation):
    from . import metadata as editor

    target = operation["target"]
    editor.require(
        target.startswith("ChartOfCharacteristicTypes.") and editor.NAME.fullmatch(target.split(".", 1)[1]),
        "Type extension requires a chart of characteristic types",
        2,
    )
    config, node, path, original = _descriptor(snapshot, target, "ChartOfCharacteristicTypes")
    base = metadata_object_ops.exact_base_owner(snapshot, node, path)
    if base is None:
        raise editor.Rejected("Exact base context required", 3)
    base_type = base.find("m:Properties/m:Type", editor.NS)
    if base_type is None or not any(child.tag in {f"{{{CORE}}}Type", f"{{{CORE}}}TypeSet"} for child in base_type):
        raise editor.Rejected("Base chart characteristic Type is missing", 4)
    additions = operation["parameters"]["types"]

    def specification(member):
        return _type_spec(member)

    base_members = [child for child in base_type if child.tag in {f"{{{CORE}}}Type", f"{{{CORE}}}TypeSet"}]
    base_specs = [specification(member) for member in base_members]
    editor.require(len(set(base_specs)) == len(base_specs), "Type extension duplicates a base type", 3)
    from . import metadata_create

    addition_members = []
    addition_specs = []
    for value in additions:
        typed = metadata_create.type_node(value)
        members = typed.findall("v8:Type", editor.NS)
        editor.require(
            len(members) == 1 and not typed.findall("v8:TypeSet", editor.NS),
            "Characteristic Type addition must be one concrete reference type",
            2,
        )
        member = members[0]
        member_spec = specification(member)
        addition_members.append((copy.deepcopy(member), member_spec[1]))
        addition_specs.append(member_spec)
    editor.require(
        len(set(addition_specs)) == len(addition_specs) and not set(addition_specs) & set(base_specs),
        "Type extension duplicates a base type",
        3,
    )
    # An extended Type stores only the added members. Base members remain
    # inherited from the adopted object and are validated above for conflicts.
    expected_specs = addition_specs
    properties = node.find("m:Properties", editor.NS)
    if properties is None:
        raise editor.Rejected("Chart Properties are missing", 4)
    current = properties.find("m:Type", editor.NS)
    if current is not None:
        editor.require(
            current.get(f"{{{XSI}}}type") == "xr:ExtendedProperty" and len(current) == 1,
            "Conflicting existing extended Type",
            3,
        )
        extended = current.find("xr:ExtendValue", NS)
        if extended is None or extended.get(f"{{{XSI}}}type") != "v8:TypeDescription":
            raise editor.Rejected("Extended Type value is missing", 4)
        current_members = [child for child in extended if child.tag in {f"{{{CORE}}}Type", f"{{{CORE}}}TypeSet"}]
        editor.require(
            len(current_members) == len(extended)
            and [specification(item) for item in current_members] == expected_specs,
            "Existing extended Type differs",
            3,
        )
        states = node.findall("m:InternalInfo/xr:PropertyState", NS)
        type_states = [state for state in states if state.findtext("xr:Property", namespaces=NS) == "Type"]
        editor.require(
            len(type_states) == 1 and type_states[0].findtext("xr:State", namespaces=NS) == "MultiState",
            "Extended Type state is missing",
            4,
        )
        return
    type_node = etree.Element(
        f"{{{editor.MD}}}Type",
        nsmap={**node.nsmap, "xr": borrow.XR, "v8": editor.V8, "cfg": borrow.CFG, "xsi": XSI},
        **{f"{{{XSI}}}type": "xr:ExtendedProperty"},
    )
    extended = etree.SubElement(type_node, f"{{{borrow.XR}}}ExtendValue", **{f"{{{XSI}}}type": "v8:TypeDescription"})
    for member, value in addition_members:
        rendered = member
        rendered.text = value
        rendered.tail = None
        extended.append(rendered)
    properties.append(type_node)
    internal = node.find("m:InternalInfo", editor.NS)
    editor.require(internal is not None, "Chart InternalInfo is missing", 4)
    state = etree.SubElement(internal, f"{{{borrow.XR}}}PropertyState")
    etree.SubElement(state, f"{{{borrow.XR}}}Property").text = "Type"
    etree.SubElement(state, f"{{{borrow.XR}}}State").text = "MultiState"
    snapshot.stage(path, editor.serialize_like(node.getparent(), original))
