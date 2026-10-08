"""Object adoption using the editor's read/stage snapshot, never direct I/O.

Shell layout, ordering and generated types follow cfe-borrow v1.2 from
Nikolay-Shirokov/cc-1c-skills (Copyright 2025-2026 Nick Shirokov, MIT; license
retained in automation/vendor/cc-1c-skills/LICENSE). Identity allocation and
conflict checks belong to the unified editor, not the legacy CLI.
"""

import copy
import uuid
from pathlib import Path

import lxml.etree as etree

MD = "http://v8.1c.ru/8.3/MDClasses"
XR = "http://v8.1c.ru/8.3/xcf/readable"
CHARACTERISTIC_REFERENCE_FAMILIES = {
    "CatalogRef",
    "DocumentRef",
    "EnumRef",
    "ChartOfAccountsRef",
    "ChartOfCharacteristicTypesRef",
    "ChartOfCalculationTypesRef",
    "ExchangePlanRef",
    "BusinessProcessRef",
    "TaskRef",
}
DIRECTORIES = {
    "Catalog": "Catalogs",
    "Document": "Documents",
    "Enum": "Enums",
    "CommonModule": "CommonModules",
    "CommonPicture": "CommonPictures",
    "CommonCommand": "CommonCommands",
    "CommonTemplate": "CommonTemplates",
    "ExchangePlan": "ExchangePlans",
    "Report": "Reports",
    "DataProcessor": "DataProcessors",
    "InformationRegister": "InformationRegisters",
    "AccumulationRegister": "AccumulationRegisters",
    "ChartOfCharacteristicTypes": "ChartsOfCharacteristicTypes",
    "ChartOfAccounts": "ChartsOfAccounts",
    "AccountingRegister": "AccountingRegisters",
    "ChartOfCalculationTypes": "ChartsOfCalculationTypes",
    "CalculationRegister": "CalculationRegisters",
    "BusinessProcess": "BusinessProcesses",
    "Task": "Tasks",
    "Subsystem": "Subsystems",
    "Role": "Roles",
    "Constant": "Constants",
    "FunctionalOption": "FunctionalOptions",
    "DefinedType": "DefinedTypes",
    "FunctionalOptionsParameter": "FunctionalOptionsParameters",
    "CommonForm": "CommonForms",
    "DocumentJournal": "DocumentJournals",
    "SessionParameter": "SessionParameters",
    "StyleItem": "StyleItems",
    "EventSubscription": "EventSubscriptions",
    "ScheduledJob": "ScheduledJobs",
    "SettingsStorage": "SettingsStorages",
    "FilterCriterion": "FilterCriteria",
    "CommandGroup": "CommandGroups",
    "DocumentNumerator": "DocumentNumerators",
    "Sequence": "Sequences",
    "IntegrationService": "IntegrationServices",
    "XDTOPackage": "XDTOPackages",
    "WebService": "WebServices",
    "HTTPService": "HTTPServices",
    "WSReference": "WSReferences",
    "CommonAttribute": "CommonAttributes",
    "Style": "Styles",
}
TYPE_ORDER = (
    "Language Subsystem StyleItem Style CommonPicture SessionParameter Role CommonTemplate "
    "FilterCriterion CommonModule CommonAttribute ExchangePlan XDTOPackage WebService HTTPService "
    "WSReference EventSubscription ScheduledJob SettingsStorage FunctionalOption FunctionalOptionsParameter "
    "DefinedType CommonCommand CommandGroup Constant CommonForm Catalog Document DocumentNumerator "
    "Sequence DocumentJournal Enum Report DataProcessor InformationRegister AccumulationRegister "
    "ChartOfCharacteristicTypes ChartOfAccounts AccountingRegister ChartOfCalculationTypes "
    "CalculationRegister BusinessProcess Task IntegrationService"
).split()
_OBJECT_KINDS = (
    "Catalog",
    "Document",
    "ChartOfAccounts",
    "ChartOfCharacteristicTypes",
    "ChartOfCalculationTypes",
    "BusinessProcess",
    "Task",
    "ExchangePlan",
)
GENERATED_TYPES = {
    kind: [(kind + category, category) for category in ("Object", "Ref", "Selection", "List", "Manager")]
    for kind in _OBJECT_KINDS
}
for _kind in ("InformationRegister", "AccumulationRegister", "AccountingRegister", "CalculationRegister"):
    GENERATED_TYPES[_kind] = [
        (_kind + category, category)
        for category in ("Record", "Manager", "Selection", "List", "RecordSet", "RecordKey")
    ]
GENERATED_TYPES["InformationRegister"].append(("InformationRegisterRecordManager", "RecordManager"))
GENERATED_TYPES["AccountingRegister"] = [
    ("AccountingRegister" + name, name)
    for name in ("Record", "ExtDimensions", "RecordSet", "RecordKey", "Selection", "List", "Manager")
]
GENERATED_TYPES["CalculationRegister"].append(("RecalculationsManager", "Recalcs"))
GENERATED_TYPES["BusinessProcess"].append(("BusinessProcessRoutePointRef", "RoutePointRef"))
GENERATED_TYPES["ChartOfCharacteristicTypes"].insert(4, ("Characteristic", "Characteristic"))
GENERATED_TYPES["ChartOfAccounts"] += [
    ("ChartOfAccounts" + name, name) for name in ("ExtDimensionTypes", "ExtDimensionTypesRow")
]
GENERATED_TYPES["ChartOfCalculationTypes"] += [
    (name + suffix, name + suffix)
    for name in ("DisplacingCalculationTypes", "BaseCalculationTypes", "LeadingCalculationTypes")
    for suffix in ("", "Row")
]
GENERATED_TYPES.update(
    {
        "Enum": [("Enum" + name, name) for name in ("Ref", "Manager", "List")],
        "Constant": [("Constant" + name, name) for name in ("Manager", "ValueManager", "ValueKey")],
        "DocumentJournal": [("DocumentJournal" + name, name) for name in ("Selection", "List", "Manager")],
        "Report": [("ReportObject", "Object"), ("ReportManager", "Manager")],
        "DataProcessor": [("DataProcessorObject", "Object"), ("DataProcessorManager", "Manager")],
        "DefinedType": [("DefinedType", "DefinedType")],
    }
)
WITH_CHILDREN = {
    *_OBJECT_KINDS,
    "Enum",
    "InformationRegister",
    "AccumulationRegister",
    "AccountingRegister",
    "CalculationRegister",
    "Report",
}
COMMON_MODULE_PROPERTIES = (
    "Global",
    "ClientManagedApplication",
    "Server",
    "ExternalConnection",
    "ClientOrdinaryApplication",
    "ServerCall",
)
CFG = "http://v8.1c.ru/8.1/data/enterprise/current-config"
STYLE = "http://v8.1c.ru/8.1/data/ui/style"


def _checked(snapshot, alias, path, kind):
    from . import metadata as editor

    data = snapshot.read(alias, path)
    node = editor.metadata(data, kind)
    root = node.getparent()
    editor.require(root.get("version") in {"2.17", "2.20"}, "Unsupported metadata version")
    properties = node.findall(f"{{{MD}}}Properties")
    editor.require(len(properties) == 1, "Ambiguous metadata properties", 4)
    names = [child.tag for child in properties[0] if isinstance(child.tag, str)]
    editor.require(len(names) == len(set(names)), "Duplicate metadata property", 4)
    editor.node_name(node)
    return node, data


def _registrations(config):
    from . import metadata as editor

    children = config.findall(f"{{{MD}}}ChildObjects")
    editor.require(len(children) == 1, "Configuration ChildObjects missing or ambiguous", 4)
    seen = set()
    for child in children[0]:
        if not isinstance(child.tag, str):
            continue
        kind = etree.QName(child).localname
        editor.require(
            child.tag == f"{{{MD}}}{kind}" and kind in TYPE_ORDER, "Unsupported configuration registration", 4
        )
        name = child.text or ""
        editor.require(editor.NAME.fullmatch(name) and not len(child), "Invalid object registration", 4)
        key = kind, name.casefold()
        editor.require(key not in seen, "Duplicate object registration", 3)
        seen.add(key)
    return children[0]


def _linked(children, kind, name):
    from . import metadata as editor

    matches = [
        child
        for child in children
        if child.tag == f"{{{MD}}}{kind}" and (child.text or "").casefold() == name.casefold()
    ]
    editor.require(not matches or matches[0].text == name, "Case-ambiguous object registration", 3)
    return bool(matches)


def _uuid_inventory(snapshot, *, external_name=None):
    """Enumerate descriptor trees, excluding Ext (modules, form bodies, data).

    Directory reads and every descriptor participate in plan preconditions. UUID
    definitions are uuid attributes and generated type IDs, not reference values.
    Orphan descriptors are included so they cannot conceal an identity collision.
    """
    from . import metadata as editor

    occupied = {}
    used = set()

    def collect(path):
        root = editor.xml_read(snapshot.read("target", path), f"{{{MD}}}MetaDataObject")
        for index, node in enumerate(root.iter()):
            values = []
            if node.get("uuid") is not None:
                values.append(("uuid", node.get("uuid")))
            if node.tag in {f"{{{XR}}}TypeId", f"{{{XR}}}ValueId", f"{{{XR}}}ThisNode", f"{{{XR}}}ObjectId"}:
                values.append(("text", node.text))
            for role, value in values:
                try:
                    normalized = str(uuid.UUID(value))
                except (ValueError, TypeError, AttributeError):
                    raise editor.Rejected("Invalid target UUID inventory", 4) from None
                editor.require(normalized not in used, "Existing UUID collision", 4)
                used.add(normalized)
                occupied["existing", path, f"{index}:{role}"] = normalized

    def walk(directory):
        entries = snapshot.list_directory("target", directory, optional=True)
        for name, kind in (entries or {}).items():
            path = directory + "/" + name
            if kind == "directory" and name != "Ext":
                walk(path)
            elif kind == "file" and name.endswith(".xml"):
                collect(path)

    editor.require(external_name is None or editor.NAME.fullmatch(external_name), "Invalid external owner name")
    collect(external_name + ".xml" if external_name else "Configuration.xml")
    for directory in (external_name,) if external_name else (*DIRECTORIES.values(), "Languages"):
        walk(directory)
    return occupied


def _shell(kind, name, source, root_uuid, occupied, logical_path=None, *, xml_format="2.17"):
    from . import metadata as editor

    target = logical_path or kind + "." + name

    def allocate(role):
        return editor.allocate_uuid(root_uuid, kind, target, role, occupied)

    root = etree.Element(f"{{{MD}}}MetaDataObject", nsmap={None: MD, "xr": XR}, version=xml_format)
    node = etree.SubElement(root, f"{{{MD}}}{kind}", uuid=allocate("object"))
    internal = etree.SubElement(node, f"{{{MD}}}InternalInfo")
    if kind == "ExchangePlan":
        etree.SubElement(internal, f"{{{XR}}}ThisNode").text = allocate("ThisNode")
    for prefix, category in GENERATED_TYPES.get(kind, []):
        generated = etree.SubElement(internal, f"{{{XR}}}GeneratedType", name=prefix + "." + name, category=category)
        for role in ("TypeId", "ValueId"):
            etree.SubElement(generated, f"{{{XR}}}{role}").text = allocate(prefix + ":" + role)
    properties = etree.SubElement(node, f"{{{MD}}}Properties")
    for key, value in [
        ("ObjectBelonging", "Adopted"),
        ("Name", name),
        ("Comment", None),
        ("ExtendedConfigurationObject", editor.identity(source)),
    ]:
        etree.SubElement(properties, f"{{{MD}}}{key}").text = value
    if kind == "CommonModule":
        for key in COMMON_MODULE_PROPERTIES:
            value = editor.prop(source, key)
            editor.require(value in {"true", "false"}, "Missing/invalid CommonModule execution property", 4)
            etree.SubElement(properties, f"{{{MD}}}{key}").text = value
    if kind in WITH_CHILDREN:
        etree.SubElement(node, f"{{{MD}}}ChildObjects")
    etree.indent(root, space="\t")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + etree.tostring(root, encoding="UTF-8") + b"\n"


def _register(children, kind, name):
    """The original cfe-borrow order, preserving existing nodes and their text."""
    node = etree.Element(f"{{{MD}}}{kind}")
    node.text = name
    rank = TYPE_ORDER.index(kind)
    reference = None
    for child in children:
        if not isinstance(child.tag, str):
            continue
        child_kind = etree.QName(child).localname
        if TYPE_ORDER.index(child_kind) > rank or (child_kind == kind and child.text > name):
            reference = child
            break
    indent = "\n\t\t\t"
    if children.text and not children.text.strip() and "\n" in children.text:
        indent = children.text
    if reference is not None:
        node.tail = reference.getprevious().tail if reference.getprevious() is not None else children.text
        children.insert(children.index(reference), node)
    elif len(children):
        node.tail = children[-1].tail
        children[-1].tail = indent
        children.append(node)
    else:
        children.text = indent
        node.tail = "\n\t\t"
        children.append(node)


def borrow_object(snapshot, operation):
    """Adopt an exact top-level object; form and tabular section bodies are separate operations."""
    from . import metadata as editor

    target = operation.get("target", "")
    parts = target.split(".") if isinstance(target, str) else []
    editor.require(
        operation.get("op") == "object.borrow" and len(parts) == 2, "Expected object.borrow with Kind.Name target"
    )
    kind, name = parts
    editor.require(
        kind in DIRECTORIES and kind not in {"CommonTemplate", "CommonForm"},
        "Unsupported object.borrow kind; templates and forms require separate handling",
    )
    editor.require(editor.NAME.fullmatch(name), "Invalid object name")
    parameters = operation.get("parameters", {})
    editor.require(
        isinstance(parameters, dict)
        and "baseRoot" in parameters
        and set(parameters) <= {"baseRoot", "restoreRegistration"}
        and isinstance(parameters["baseRoot"], str)
        and isinstance(parameters.get("restoreRegistration", False), bool),
        "Invalid borrow parameters",
    )
    restore_registration = parameters.get("restoreRegistration", False)
    alias = snapshot.source_root(Path(parameters["baseRoot"]))
    editor.require(alias != "target", "Base root must differ from extension root")
    config, config_bytes = _checked(snapshot, "target", "Configuration.xml", "Configuration")
    base_config, _ = _checked(snapshot, alias, "Configuration.xml", "Configuration")
    editor.require(
        editor.prop(config, "ConfigurationExtensionPurpose") in {"Patch", "Customization", "AddOn"},
        "Target root must be an extension",
    )
    editor.require(
        editor.prop(config, "KeepMappingToExtendedConfigurationObjectsByIDs") == "true",
        "Extension must support mapping by internal IDs",
    )
    editor.require(
        not editor.prop(base_config, "ConfigurationExtensionPurpose"), "Base root must be a main configuration"
    )
    children, base_children = _registrations(config), _registrations(base_config)
    editor.require(_linked(base_children, kind, name), "Base object registration missing", 4)
    path = f"{DIRECTORIES[kind]}/{name}.xml"
    source, _ = _checked(snapshot, alias, path, kind)
    editor.require(editor.node_name(source) == name, "Base object name mismatch", 4)
    editor.require(
        editor.prop(source, "ObjectBelonging") in {"", "Native"}
        and not editor.prop(source, "ExtendedConfigurationObject"),
        "Base object must not be adopted",
        4,
    )
    existing = snapshot.read("target", path, optional=True)
    registered = _linked(children, kind, name)
    editor.require(
        not restore_registration or existing is not None,
        "Registration recovery requires an existing adopted descriptor",
        3,
    )
    editor.require(
        (existing is not None) == registered or (restore_registration and not registered),
        "Object registration/file mismatch",
        3,
    )
    if existing is not None:
        current, _ = _checked(snapshot, "target", path, kind)
        editor.require(
            editor.node_name(current) == name
            and editor.prop(current, "ObjectBelonging") == "Adopted"
            and (editor.prop(current, "ExtendedConfigurationObject") or "").lower() == editor.identity(source),
            "Existing object has a conflicting base link",
            3,
        )
        if kind == "Report" and current.find("m:ChildObjects", editor.NS) is None:
            etree.SubElement(current, f"{{{MD}}}ChildObjects")
            snapshot.stage(path, editor.serialize_like(current.getparent(), existing))
        if not registered:
            _uuid_inventory(snapshot)
            _register(children, kind, name)
            snapshot.stage("Configuration.xml", editor.serialize_like(config.getparent(), config_bytes))
        return
    editor.require(
        not snapshot.list_directory("target", f"{DIRECTORIES[kind]}/{name}", optional=True),
        "Unregistered object artifacts already exist",
        3,
    )
    occupied = _uuid_inventory(snapshot)
    shell = _shell(kind, name, source, editor.identity(config), occupied, xml_format=config.getparent().get("version"))
    _register(children, kind, name)
    config_after = editor.serialize_like(config.getparent(), config_bytes)
    snapshot.stage(path, shell)
    snapshot.stage("Configuration.xml", config_after)


def register_borrowed_object(snapshot, operation):
    """Register one existing adopted descriptor after verifying its exact base identity."""
    from . import metadata as editor

    target = operation.get("target", "")
    parts = target.split(".") if isinstance(target, str) else []
    editor.require(
        operation.get("op") == "object.register-borrowed" and len(parts) == 2,
        "Expected object.register-borrowed with Kind.Name target",
    )
    kind, name = parts
    editor.require(
        kind in DIRECTORIES and kind not in {"CommonTemplate", "CommonForm"}, "Unsupported registered object kind"
    )
    editor.require(editor.NAME.fullmatch(name), "Invalid object name")
    parameters = operation.get("parameters", {})
    editor.require(
        isinstance(parameters, dict) and set(parameters) == {"baseRoot"} and isinstance(parameters["baseRoot"], str),
        "Invalid registration parameters",
    )
    alias = snapshot.source_root(Path(parameters["baseRoot"]))
    editor.require(alias != "target", "Base root must differ from extension root")
    config, config_bytes = _checked(snapshot, "target", "Configuration.xml", "Configuration")
    base_config, _ = _checked(snapshot, alias, "Configuration.xml", "Configuration")
    editor.require(
        editor.prop(config, "ConfigurationExtensionPurpose") in {"Patch", "Customization", "AddOn"},
        "Target root must be an extension",
    )
    editor.require(
        editor.prop(config, "KeepMappingToExtendedConfigurationObjectsByIDs") == "true",
        "Extension must support mapping by internal IDs",
    )
    editor.require(
        not editor.prop(base_config, "ConfigurationExtensionPurpose"), "Base root must be a main configuration"
    )
    children, base_children = _registrations(config), _registrations(base_config)
    editor.require(_linked(base_children, kind, name), "Base object registration missing", 4)
    path = f"{DIRECTORIES[kind]}/{name}.xml"
    source, _ = _checked(snapshot, alias, path, kind)
    editor.require(editor.node_name(source) == name, "Base object name mismatch", 4)
    editor.require(
        editor.prop(source, "ObjectBelonging") in {"", "Native"}
        and not editor.prop(source, "ExtendedConfigurationObject"),
        "Base object must not be adopted",
        4,
    )
    adopted_data = snapshot.read("target", path, optional=True)
    editor.require(adopted_data is not None, "Missing adopted object descriptor", 3)
    adopted, _ = _checked(snapshot, "target", path, kind)
    source_uuid = editor.identity(source)
    adopted_uuid = editor.identity(adopted)
    editor.require(
        editor.node_name(adopted) == name
        and editor.prop(adopted, "ObjectBelonging") == "Adopted"
        and (editor.prop(adopted, "ExtendedConfigurationObject") or "").lower() == source_uuid
        and adopted_uuid != source_uuid,
        "Existing object has a conflicting base link",
        3,
    )
    if _linked(children, kind, name):
        return
    _register(children, kind, name)
    snapshot.stage("Configuration.xml", editor.serialize_like(config.getparent(), config_bytes))


def borrow_tabular_section(snapshot, operation):
    """Adopt the empty section shell directly under its owning object."""
    from . import metadata as editor

    parts = operation["target"].split(".")
    editor.require(
        len(parts) == 4 and parts[2] == "TabularSection" and all(editor.NAME.fullmatch(part) for part in parts),
        "Expected Kind.Name.TabularSection.Name",
    )
    kind, owner_name, _, name = parts
    editor.require(kind in DIRECTORIES, "Unsupported section owner")
    alias = snapshot.source_root(Path(operation["parameters"]["baseRoot"]))
    path = f"{DIRECTORIES[kind]}/{owner_name}.xml"
    source_owner, _ = _checked(snapshot, alias, path, kind)
    sources = source_owner.findall(f"{{{MD}}}ChildObjects/{{{MD}}}TabularSection")
    sources = [node for node in sources if editor.prop(node, "Name").casefold() == name.casefold()]
    editor.require(
        len(sources) == 1 and editor.node_name(sources[0]) == name, "Missing or ambiguous base tabular section", 4
    )
    source = sources[0]
    source_uuid = editor.identity(source)
    editor.require(
        editor.prop(source, "ObjectBelonging") in {"", "Native"}
        and not editor.prop(source, "ExtendedConfigurationObject"),
        "Base section must not be adopted",
        4,
    )
    borrow_object(
        snapshot, {"op": "object.borrow", "target": kind + "." + owner_name, "parameters": operation["parameters"]}
    )
    owner, original = _checked(snapshot, "target", path, kind)
    children = owner.findall(f"{{{MD}}}ChildObjects")
    editor.require(len(children) <= 1, "Ambiguous owner ChildObjects", 4)
    children = children[0] if children else etree.SubElement(owner, f"{{{MD}}}ChildObjects")
    existing = [
        node
        for node in children
        if node.tag == f"{{{MD}}}TabularSection" and editor.prop(node, "Name").casefold() == name.casefold()
    ]
    editor.require(len(existing) <= 1, "Ambiguous target tabular section", 3)
    if existing:
        node = existing[0]
        editor.require(
            editor.node_name(node) == name
            and editor.prop(node, "ObjectBelonging") == "Adopted"
            and (editor.prop(node, "ExtendedConfigurationObject") or "").lower() == source_uuid,
            "Existing section has a conflicting base link",
            3,
        )
        editor.identity(node)
        return
    config, _ = _checked(snapshot, "target", "Configuration.xml", "Configuration")
    occupied = _uuid_inventory(snapshot)

    def allocate(role):
        return editor.allocate_uuid(editor.identity(config), "TabularSection", operation["target"], role, occupied)

    node = etree.Element(f"{{{MD}}}TabularSection", uuid=allocate("object"))
    internal = etree.SubElement(node, f"{{{MD}}}InternalInfo")
    seen = set()
    for item in source.findall(f"{{{MD}}}InternalInfo/{{{XR}}}GeneratedType"):
        generated_name, category = item.get("name"), item.get("category")
        editor.require(generated_name and category and generated_name not in seen, "Invalid generated section type", 4)
        seen.add(generated_name)
        generated = etree.SubElement(internal, f"{{{XR}}}GeneratedType", name=generated_name, category=category)
        for role in ("TypeId", "ValueId"):
            etree.SubElement(generated, f"{{{XR}}}{role}").text = allocate(generated_name + ":" + role)
    properties = etree.SubElement(node, f"{{{MD}}}Properties")
    for key, value in [
        ("ObjectBelonging", "Adopted"),
        ("Name", name),
        ("Comment", None),
        ("ExtendedConfigurationObject", source_uuid),
    ]:
        etree.SubElement(properties, f"{{{MD}}}{key}").text = value
    etree.SubElement(node, f"{{{MD}}}ChildObjects")
    etree.indent(node, space="\t", level=3)
    if len(children):
        node.tail = children[-1].tail
        children[-1].tail = "\n\t\t\t"
    else:
        children.text = "\n\t\t\t"
        node.tail = "\n\t\t"
    children.append(node)
    snapshot.stage(path, editor.serialize_like(owner.getparent(), original))


def _member(parent, kind, name, *, optional=False):
    from . import metadata as editor

    children = parent.findall(f"{{{MD}}}ChildObjects")
    editor.require(len(children) <= 1, "Ambiguous ChildObjects", 4)
    matches = (
        []
        if not children
        else [
            node
            for node in children[0]
            if node.tag == f"{{{MD}}}{kind}" and editor.prop(node, "Name").casefold() == name.casefold()
        ]
    )
    editor.require(len(matches) <= 1 and (matches or optional), "Missing or ambiguous " + kind + "." + name, 4)
    if matches:
        editor.require(editor.node_name(matches[0]) == name, "Case-ambiguous member", 3)
        return matches[0]
    return None


def _borrow_member(snapshot, base_root, owner_name, members):
    """Reuse the old adopted attribute/value layout without rewriting siblings."""
    from . import metadata as editor

    kind, name = owner_name.split(".")
    path = f"{DIRECTORIES[kind]}/{name}.xml"
    parameters = {"baseRoot": str(base_root)}
    borrow_object(snapshot, {"op": "object.borrow", "target": owner_name, "parameters": parameters})
    if len(members) == 2:
        editor.require(members[0][0] == "TabularSection" and members[1][0] == "Attribute", "Unsupported nested member")
        borrow_tabular_section(
            snapshot,
            {
                "op": "tabular-section.borrow",
                "parameters": parameters,
                "target": owner_name + ".TabularSection." + members[0][1],
            },
        )
    editor.require(
        len(members) in {1, 2}
        and members[-1][0]
        in {
            "Attribute",
            "EnumValue",
            "Dimension",
            "Resource",
            "AccountingFlag",
            "ExtDimensionAccountingFlag",
            "Command",
        },
        "Unsupported adopted member",
    )
    editor.require(members[-1][0] != "Command" or len(members) == 1, "Unsupported nested command")
    alias = snapshot.source_root(Path(base_root))
    source, _ = _checked(snapshot, alias, path, kind)
    target, original = _checked(snapshot, "target", path, kind)
    parent = target
    for member_kind, member_name in members:
        source = _member(source, member_kind, member_name)
    for member_kind, member_name in members[:-1]:
        parent = _member(parent, member_kind, member_name)
    if source is None or parent is None:
        raise editor.Rejected("Missing member or owner", 4)
    member_kind, member_name = members[-1]
    existing = _member(parent, member_kind, member_name, optional=True)
    editor.require(
        editor.prop(source, "ObjectBelonging") in {"", "Native"}
        and not editor.prop(source, "ExtendedConfigurationObject"),
        "Base member must be native",
        4,
    )
    source_id = editor.identity(source)
    if existing is not None:
        editor.require(
            editor.prop(existing, "ObjectBelonging") == "Adopted"
            and (editor.prop(existing, "ExtendedConfigurationObject") or "").lower() == source_id,
            "Existing member has a conflicting base link",
            3,
        )
        editor.identity(existing)
        return source
    config, _ = _checked(snapshot, "target", "Configuration.xml", "Configuration")
    logical_path = owner_name + "".join("." + k + "." + n for k, n in members)
    new_id = editor.allocate_uuid(
        editor.identity(config), member_kind, logical_path, "object", _uuid_inventory(snapshot)
    )
    node = etree.Element(f"{{{MD}}}{member_kind}", uuid=new_id)
    etree.SubElement(node, f"{{{MD}}}InternalInfo")
    properties = etree.SubElement(node, f"{{{MD}}}Properties")
    for key, value in [
        ("ObjectBelonging", "Adopted"),
        ("Name", member_name),
        ("Comment", None),
        ("ExtendedConfigurationObject", source_id),
    ]:
        etree.SubElement(properties, f"{{{MD}}}{key}").text = value
    if member_kind == "Command":
        # Platform dumps of adopted object commands keep only Group besides the
        # identity properties (src/cfe/ФормированиеТестовыхДанных/Catalogs/Организации.xml).
        groups = source.findall(f"{{{MD}}}Properties/{{{MD}}}Group")
        editor.require(
            len(groups) == 1 and groups[0].text and not len(groups[0]), "Missing or ambiguous command Group", 4
        )
        etree.SubElement(properties, f"{{{MD}}}Group").text = groups[0].text
    elif member_kind != "EnumValue":
        types = source.findall(f"{{{MD}}}Properties/{{{MD}}}Type")
        editor.require(len(types) == 1, "Missing or ambiguous member Type", 4)
        # Retain namespaces used only in QName text, not merely element tags.
        source_type = types[0]
        cloned = etree.SubElement(properties, source_type.tag, nsmap=source_type.nsmap, attrib=dict(source_type.attrib))
        cloned.text = source_type.text
        for child in source_type:
            cloned.append(copy.deepcopy(child))
    children = parent.find(f"{{{MD}}}ChildObjects")
    if children is None:
        children = etree.SubElement(parent, f"{{{MD}}}ChildObjects")
    level = 3 + 2 * (len(members) - 1)
    etree.indent(node, space="\t", level=level)
    if len(children):
        node.tail = children[-1].tail
        children[-1].tail = "\n" + "\t" * level
    else:
        children.text = "\n" + "\t" * level
        node.tail = "\n" + "\t" * (level - 1)
    children.append(node)
    snapshot.stage(path, editor.serialize_like(target.getparent(), original))
    return source


def _type_property_state(owner):
    """Return the Type property's state, rejecting ambiguous internal metadata."""
    from . import metadata as editor

    internal_infos = owner.findall(f"{{{MD}}}InternalInfo")
    editor.require(len(internal_infos) == 1, "Missing or ambiguous InternalInfo", 4)
    type_states = []
    for state in internal_infos[0].findall(f"{{{XR}}}PropertyState"):
        editor.require(
            not state.attrib
            and not (state.text or "").strip()
            and [child.tag for child in state] == [f"{{{XR}}}Property", f"{{{XR}}}State"]
            and all(not child.attrib and not len(child) for child in state),
            "Malformed property state",
            4,
        )
        property_name = state[0].text or ""
        if property_name == "Type":
            editor.require(state[1].text == "MultiState", "Conflicting Type property state", 3)
            type_states.append(state)
    editor.require(len(type_states) <= 1, "Duplicate Type property state", 4)
    return internal_infos[0], type_states[0] if type_states else None


def _mark_type_multistate(owner):
    internal_info, state = _type_property_state(owner)
    if state is None:
        state = etree.SubElement(internal_info, f"{{{XR}}}PropertyState")
        etree.SubElement(state, f"{{{XR}}}Property").text = "Type"
        etree.SubElement(state, f"{{{XR}}}State").text = "MultiState"
    return state


def _type_nodes_shape(container):
    def shape(node):
        return (
            node.tag,
            node.text,
            tuple(sorted(node.attrib.items())),
            tuple(shape(child) for child in node if isinstance(child.tag, str)),
        )

    return [shape(child) for child in container if isinstance(child.tag, str)]


def _validate_check_value(typed, source_type, editor):
    check = typed.find(f"{{{XR}}}CheckValue")
    if check is not None and len(check):
        editor.require(
            _type_nodes_shape(check) == _type_nodes_shape(source_type),
            "Adopted Type CheckValue differs from base Type",
            3,
        )


def _extended_type_description(owner, typed, editor):
    """Match Designer extension XML; repair only known legacy CLI shapes."""
    xsi_type = "{http://www.w3.org/2001/XMLSchema-instance}type"
    prefix, separator, local = (typed.get(xsi_type) or "").partition(":")
    editor.require(
        typed.tag == f"{{{MD}}}Type"
        and set(typed.attrib) == {xsi_type}
        and not (typed.text or "").strip()
        and separator
        and local == "ExtendedProperty"
        and typed.nsmap.get(prefix) == XR,
        "Unsupported Type extension",
        4,
    )
    children = list(typed)
    _, state = _type_property_state(owner)
    tags = [child.tag for child in children]
    editor.require(
        tags in ([f"{{{XR}}}ExtendValue"], [f"{{{XR}}}CheckValue", f"{{{XR}}}ExtendValue"]),
        "Unsupported Type extension state",
        4,
    )
    # Preserve explicit base CheckValue; remove only the known empty legacy shape.
    repaired = state is None
    if len(children) == 2:
        check_value = children[0]
        prefix, separator, local = (check_value.get(xsi_type) or "").partition(":")
        editor.require(
            set(check_value.attrib) == {xsi_type}
            and not (check_value.text or "").strip()
            and separator
            and local == "TypeDescription"
            and check_value.nsmap.get(prefix) == editor.V8,
            "Unsupported Type check value",
            4,
        )
        for child in check_value:
            value = (child.text or "").strip()
            value_prefix, value_separator, value_local = value.partition(":")
            editor.require(
                child.tag == f"{{{editor.V8}}}Type"
                and not child.attrib
                and not len(child)
                and value_separator
                and value_prefix in child.nsmap
                and value_local,
                "Unsupported Type check value",
                4,
            )
        if not len(check_value):
            typed.remove(check_value)
            repaired = True
    extend_value = children[-1]
    _mark_type_multistate(owner)
    prefix, separator, local = (extend_value.get(xsi_type) or "").partition(":")
    editor.require(
        set(extend_value.attrib) == {xsi_type}
        and not (extend_value.text or "").strip()
        and separator
        and local == "TypeDescription"
        and extend_value.nsmap.get(prefix) == editor.V8,
        "Unsupported Type description",
        4,
    )
    return extend_value, repaired


def extend_member_type(snapshot, operation):
    """Adopt a contracted member change while retaining its native base identity."""
    from . import metadata as editor
    from . import metadata_create as create

    target = operation.get("target", "")
    parts = target.split(".") if isinstance(target, str) else []
    editor.require(all(editor.NAME.fullmatch(part) for part in parts), "Invalid member type-extension target")
    if len(parts) == 4:
        owner_kind, owner_name, member_kind, member_name = parts
        members = [(member_kind, member_name)]
        editor.require(
            (owner_kind in {"Catalog", "Document"} and member_kind == "Attribute")
            or (owner_kind == "InformationRegister" and member_kind == "Resource"),
            "Only Catalog/Document attributes and InformationRegister resources are supported",
        )
    elif len(parts) == 6:
        owner_kind, owner_name, section_kind, section_name, member_kind, member_name = parts
        editor.require(
            owner_kind in {"Catalog", "Document"} and section_kind == "TabularSection" and member_kind == "Attribute",
            "Only Catalog/Document tabular-section attributes are supported",
        )
        members = [("TabularSection", section_name), ("Attribute", member_name)]
    else:
        raise editor.Rejected("Expected owner member or TabularSection.Attribute target")
    parameters = operation.get("parameters", {})
    editor.require(
        isinstance(parameters, dict)
        and set(parameters) == {"baseRoot", "type"}
        and isinstance(parameters["baseRoot"], str)
        and isinstance(parameters["type"], str),
        "Invalid type-extension parameters",
    )

    base_root, requested_type = parameters["baseRoot"], parameters["type"]
    # Keep this operation intentionally narrower than the general type grammar:
    # it covers endpoint storage additions and three reviewed string routes only.
    editor.require(
        requested_type in {"String(0)", "String(10)", "String(15)", "String(60)"}
        or requested_type.startswith(("EnumRef.", "CatalogRef.")),
        "Unsupported member extension type",
    )
    requested_node = create.type_node(requested_type)
    requested_children = list(requested_node)
    editor.require(
        len(requested_children) in ({2} if requested_type.startswith("String(") else {1}),
        "A member extension must add exactly one type",
    )
    alias = snapshot.source_root(Path(base_root))
    path = f"{DIRECTORIES[owner_kind]}/{owner_name}.xml"
    source_owner, _ = _checked(snapshot, alias, path, owner_kind)
    source_parent = source_owner
    for member_kind, member_name in members[:-1]:
        source_parent = _member(source_parent, member_kind, member_name)
    source_member = _member(source_parent, *members[-1])
    assert source_member is not None

    xsi_type = "{http://www.w3.org/2001/XMLSchema-instance}type"

    def string_length(typed):
        editor.require(
            typed is not None
            and len(typed) == 2
            and typed[0].tag == f"{{{editor.V8}}}Type"
            and typed[1].tag == f"{{{editor.V8}}}StringQualifiers"
            and set(typed.attrib) <= {xsi_type},
            "Unsupported string type description",
        )
        assert typed is not None
        prefix, separator, primitive = (typed[0].text or "").partition(":")
        editor.require(
            separator and primitive == "string" and typed[0].nsmap.get(prefix) == editor.XS,
            "Member type is not xs:string",
        )
        qualifiers = typed[1]
        editor.require(
            not qualifiers.attrib
            and [node.tag for node in qualifiers] == [f"{{{editor.V8}}}Length", f"{{{editor.V8}}}AllowedLength"]
            and all(not node.attrib and not len(node) for node in qualifiers),
            "Unsupported string qualifiers",
        )
        length = qualifiers[0].text
        editor.require(
            length is not None and length.isdecimal() and qualifiers[1].text == "Variable",
            "Only variable-length strings can be widened",
        )
        assert length is not None
        return int(length)

    source_type = source_member.find(f"{{{MD}}}Properties/{{{MD}}}Type")
    editor.require(
        source_type is not None and source_type.get(xsi_type) is None,
        "Base member must have a native, non-extended Type",
    )
    assert source_type is not None

    _borrow_member(snapshot, base_root, owner_kind + "." + owner_name, members)
    target_owner, original = _checked(snapshot, "target", path, owner_kind)
    target_parent = target_owner
    for member_kind, member_name in members[:-1]:
        target_parent = _member(target_parent, member_kind, member_name)
    adopted_member = _member(target_parent, *members[-1])
    assert adopted_member is not None
    editor.require(
        editor.prop(adopted_member, "ObjectBelonging") == "Adopted"
        and (editor.prop(adopted_member, "ExtendedConfigurationObject") or "").lower()
        == editor.identity(source_member),
        "Adopted member has a conflicting base link",
        3,
    )
    current_type = adopted_member.find(f"{{{MD}}}Properties/{{{MD}}}Type")
    editor.require(current_type is not None, "Missing adopted member Type", 4)
    current_extended = current_type.get(xsi_type)

    def shape(node):
        return (
            node.tag,
            node.text,
            tuple(sorted(node.attrib.items())),
            tuple(shape(child) for child in node if isinstance(child.tag, str)),
        )

    def install_extension(children):
        replacement = etree.Element(
            f"{{{MD}}}Type",
            nsmap={
                "xr": XR,
                "xsi": "http://www.w3.org/2001/XMLSchema-instance",
                "v8": editor.V8,
                "xs": editor.XS,
                "cfg": CFG,
            },
            attrib={xsi_type: "xr:ExtendedProperty"},
        )
        replacement.tail = current_type.tail
        extension = etree.SubElement(replacement, f"{{{XR}}}ExtendValue", attrib={xsi_type: "v8:TypeDescription"})
        for child in children:
            extension.append(copy.deepcopy(child))
        properties = adopted_member.find(f"{{{MD}}}Properties")
        properties.replace(current_type, replacement)
        _mark_type_multistate(adopted_member)

    def is_string(typed):
        if typed is None or not len(typed):
            return False
        first = typed[0]
        prefix, separator, primitive = (first.text or "").partition(":")
        return (
            first.tag == f"{{{editor.V8}}}Type"
            and separator
            and primitive == "string"
            and first.nsmap.get(prefix) == editor.XS
        )

    if requested_type.startswith("String(") and is_string(source_type):
        target_length = int(requested_type[7:-1])
        source_length = string_length(source_type)
        editor.require(
            (source_length, target_length) in {(50, 60), (200, 0), (50, 0)},
            "Only String(50)->String(60), String(200)->String(0), and String(50)->String(0) routes are supported",
        )
        if current_extended is not None:
            extension, legacy = _extended_type_description(adopted_member, current_type, editor)
            _validate_check_value(current_type, source_type, editor)
            editor.require(
                [shape(child) for child in extension] == [shape(child) for child in requested_children],
                "Existing adopted string extension differs from request",
                3,
            )
            if legacy:
                snapshot.stage(path, editor.serialize_like(target_owner.getparent(), original))
            return
        editor.require(
            string_length(current_type) == source_length,
            "Adopted member Type differs from base; refusing replacement",
            3,
        )
        install_extension(requested_children)
    else:
        # Reference alternatives and the reviewed String(15) route are additive.
        is_reference_addition = requested_type.startswith(("EnumRef.", "CatalogRef."))
        is_additive_string = requested_type in {"String(10)", "String(15)"}
        editor.require(is_reference_addition or is_additive_string, "Unsupported additive member type")
        editor.require(
            not (is_additive_string and is_string(source_type)),
            "String qualifier routes cannot add a second primitive string type",
        )
        if is_reference_addition:
            expected_ref = "cfg:" + requested_type
            editor.require(
                not any(
                    (child.text or "").strip() == expected_ref for child in source_type.findall(f"{{{editor.V8}}}Type")
                ),
                "Requested reference is already present in the base type",
            )
        if current_extended is not None:
            extension, legacy = _extended_type_description(adopted_member, current_type, editor)
            _validate_check_value(current_type, source_type, editor)
            existing_shapes = [shape(child) for child in extension]
            requested_shapes = [shape(child) for child in requested_children]
            if any(
                existing_shapes[index : index + len(requested_shapes)] == requested_shapes
                for index in range(len(existing_shapes) - len(requested_shapes) + 1)
            ):
                if legacy:
                    snapshot.stage(path, editor.serialize_like(target_owner.getparent(), original))
                return
            for child in requested_children:
                extension.append(copy.deepcopy(child))
            snapshot.stage(path, editor.serialize_like(target_owner.getparent(), original))
            return
        editor.require(
            editor.signature(current_type) == editor.signature(source_type),
            "Adopted member Type differs from base; refusing replacement",
            3,
        )
        install_extension(requested_children)
    snapshot.stage(path, editor.serialize_like(target_owner.getparent(), original))


def extend_characteristic_types(snapshot, operation):
    """Append explicit reference alternatives to an adopted characteristic chart Type."""
    from . import metadata as editor
    from . import metadata_create as create

    parts = operation.get("target", "").split(".") if isinstance(operation.get("target"), str) else []
    editor.require(
        len(parts) == 2 and parts[0] == "ChartOfCharacteristicTypes" and editor.NAME.fullmatch(parts[1]),
        "Expected ChartOfCharacteristicTypes.Name target",
    )
    parameters = operation.get("parameters", {})
    editor.require(
        isinstance(parameters, dict)
        and set(parameters) in ({"baseRoot", "types"}, {"baseRoot", "types", "checkBaseType"})
        and isinstance(parameters["baseRoot"], str)
        and isinstance(parameters["types"], list)
        and parameters["types"]
        and ("checkBaseType" not in parameters or isinstance(parameters["checkBaseType"], bool)),
        "Invalid characteristic type extension parameters",
    )
    remove_base_check = parameters.get("checkBaseType") is False
    requested = parameters["types"]
    editor.require(
        all(isinstance(value, str) and value for value in requested)
        and len({value.casefold() for value in requested}) == len(requested),
        "Empty or duplicate characteristic type",
    )

    def reference_values(typed, *, extension=False, owner=None):
        if extension:
            editor.require(owner is not None, "Missing characteristic Type owner", 4)
            description, legacy = _extended_type_description(owner, typed, editor)
        else:
            editor.require(
                typed.tag == f"{{{MD}}}Type" and not typed.attrib and not (typed.text or "").strip(),
                "Unsupported base characteristic Type",
            )
            description = typed
            legacy = False
        values = []
        for child in description:
            editor.require(
                child.tag == f"{{{editor.V8}}}Type"
                and not child.attrib
                and not len(child)
                and not (child.tail or "").strip(),
                "Unsupported characteristic reference type",
            )
            prefix, separator, local = (child.text or "").partition(":")
            family, dot, name = local.partition(".")
            editor.require(
                separator
                and dot
                and child.nsmap.get(prefix) == CFG
                and family in CHARACTERISTIC_REFERENCE_FAMILIES
                and editor.NAME.fullmatch(name),
                "Characteristic type must be a concrete metadata reference",
            )
            values.append(family + "." + name)
        editor.require(
            values and len({value.casefold() for value in values}) == len(values),
            "Empty or duplicate characteristic reference type",
        )
        return values, description, legacy

    target, base_root = operation["target"], parameters["baseRoot"]
    alias = snapshot.source_root(Path(base_root))
    path = f"{DIRECTORIES[parts[0]]}/{parts[1]}.xml"
    source, _ = _checked(snapshot, alias, path, parts[0])
    editor.require(
        editor.node_name(source) == parts[1]
        and editor.prop(source, "ObjectBelonging") in {"", "Native"}
        and not editor.prop(source, "ExtendedConfigurationObject"),
        "Base characteristic chart must be native",
        4,
    )
    source_properties = source.findall(f"{{{MD}}}Properties")
    editor.require(len(source_properties) == 1, "Missing or ambiguous base properties", 4)
    source_types = source_properties[0].findall(f"{{{MD}}}Type")
    editor.require(len(source_types) == 1, "Missing or ambiguous base characteristic Type", 4)
    base_values, _, _ = reference_values(source_types[0])
    base_set = {value.casefold() for value in base_values}
    additions = []
    for value in requested:
        rendered = create.type_node(value)
        editor.require(
            len(rendered) == 1 and rendered[0].tag == f"{{{editor.V8}}}Type",
            "Characteristic type must be a concrete metadata reference",
        )
        prefix, separator, local = (rendered[0].text or "").partition(":")
        family, dot, name = local.partition(".")
        editor.require(
            separator
            and dot
            and rendered[0].nsmap.get(prefix) == CFG
            and family in CHARACTERISTIC_REFERENCE_FAMILIES
            and editor.NAME.fullmatch(name),
            "Characteristic type must be a concrete metadata reference",
        )
        normalized = family + "." + name
        editor.require(normalized.casefold() not in base_set, "Characteristic type already exists in base")
        additions.append((normalized, rendered[0]))

    borrow_object(snapshot, {"op": "object.borrow", "target": target, "parameters": {"baseRoot": base_root}})
    adopted, original = _checked(snapshot, "target", path, parts[0])
    editor.require(
        editor.node_name(adopted) == parts[1]
        and editor.prop(adopted, "ObjectBelonging") == "Adopted"
        and (editor.prop(adopted, "ExtendedConfigurationObject") or "").lower() == editor.identity(source),
        "Adopted chart has a conflicting base link",
        3,
    )
    properties = adopted.findall(f"{{{MD}}}Properties")
    editor.require(len(properties) == 1, "Missing or ambiguous adopted properties", 4)
    type_nodes = properties[0].findall(f"{{{MD}}}Type")
    editor.require(len(type_nodes) <= 1, "Ambiguous adopted characteristic Type", 4)
    if type_nodes:
        raw_check = type_nodes[0].find(f"{{{XR}}}CheckValue")
        if remove_base_check and raw_check is not None:
            editor.require(len(raw_check) > 0, "Cannot remove an empty characteristic Type CheckValue", 3)
            _validate_check_value(type_nodes[0], source_types[0], editor)
        existing_values, description, legacy = reference_values(type_nodes[0], extension=True, owner=adopted)
        _validate_check_value(type_nodes[0], source_types[0], editor)
        existing_set = {value.casefold() for value in existing_values}
        editor.require(not existing_set & base_set, "Adopted Type duplicates a base characteristic type", 3)
        additions = [(value, child) for value, child in additions if value.casefold() not in existing_set]
        if not additions:
            changed = legacy
            if remove_base_check and raw_check is not None:
                type_nodes[0].remove(raw_check)
                changed = True
            if changed:
                snapshot.stage(path, editor.serialize_like(adopted.getparent(), original))
            return
        for _, child in additions:
            description.append(copy.deepcopy(child))
        if remove_base_check and raw_check is not None:
            type_nodes[0].remove(raw_check)
    else:
        additions_node = etree.Element(
            f"{{{editor.MD}}}Type",
            nsmap={"xr": XR, "xsi": "http://www.w3.org/2001/XMLSchema-instance", "v8": editor.V8, "cfg": CFG},
            attrib={"{http://www.w3.org/2001/XMLSchema-instance}type": "xr:ExtendedProperty"},
        )
        description = etree.SubElement(
            additions_node,
            f"{{{XR}}}ExtendValue",
            attrib={"{http://www.w3.org/2001/XMLSchema-instance}type": "v8:TypeDescription"},
        )
        for _, child in additions:
            description.append(copy.deepcopy(child))
        properties[0].append(additions_node)
        _mark_type_multistate(adopted)
    snapshot.stage(path, editor.serialize_like(adopted.getparent(), original))


def borrow_form_dependencies(snapshot, base_root, owner_name, form, mode="Form"):
    """Resolve the old Form/All dependency traversal without stripping form XML.

    The caller owns form projection; this function only stages exact metadata
    adoptions. No BSL inference is used to claim a complete runtime dependency set.
    """
    from . import metadata as editor

    editor.require(mode in {"Form", "All"}, "Unsupported main attribute mode")
    editor.require(
        form.tag == f"{{{editor.FORM}}}Form" and form.get("version") in {"2.17", "2.20"}, "Unsupported source form"
    )
    alias = snapshot.source_root(Path(base_root))
    parameters = {"baseRoot": str(base_root)}
    resolved, adopted_members, adopted_sections, type_stack = {}, {}, set(), set()
    type_owners = {prefix: kind for kind, generated in GENERATED_TYPES.items() for prefix, _ in generated}
    builtin_type_namespaces = {
        editor.XS,
        editor.V8,
        "http://v8.1c.ru/8.1/data/ui",
        "http://v8.1c.ru/8.2/managed-application/core",
        "http://v8.1c.ru/8.2/managed-application/logform",
    }
    type_link_nodes = list(form.iter(f"{{{editor.FORM}}}TypeLink"))

    def adopt(target):
        parts = target.split(".")
        editor.require(
            len(parts) == 2 and parts[0] in DIRECTORIES and all(editor.NAME.fullmatch(part) for part in parts),
            "Unsupported dependency: " + target,
        )
        if target not in resolved:
            borrow_object(snapshot, {"op": "object.borrow", "target": target, "parameters": parameters})
            resolved[target] = _checked(snapshot, alias, f"{DIRECTORIES[parts[0]]}/{parts[1]}.xml", parts[0])[0]
        return resolved[target]

    def types(node):
        if node is None:
            raise editor.Rejected("Missing dependency Type", 4)
        references = []
        for value in node.iter(f"{{{editor.V8}}}Type", f"{{{editor.V8}}}TypeSet"):
            text = value.text or ""
            prefix, separator, local = text.partition(":")
            namespace = value.nsmap.get(prefix if separator else None)
            editor.require(namespace, "Unknown type namespace: " + text)
            if namespace != CFG:
                editor.require(namespace in builtin_type_namespaces, "Unsupported type namespace: " + text)
                continue
            # The platform uses this exact TypeSet as a wildcard for any document
            # reference. It has no concrete metadata dependency to adopt.
            if local == "DocumentRef" and value.tag == f"{{{editor.V8}}}TypeSet":
                editor.require(not len(value), "Unsupported metadata type set: " + text)
                continue
            family, dot, name = local.partition(".")
            editor.require(
                dot and family in type_owners and editor.NAME.fullmatch(name), "Unsupported metadata type: " + text
            )
            editor.require(
                value.tag != f"{{{editor.V8}}}TypeSet" or family in {"DefinedType", "Characteristic"},
                "Unsupported type set: " + text,
            )
            target = type_owners[family] + "." + name
            source_type = adopt(target)
            if family in {"DefinedType", "Characteristic"}:
                editor.require(target not in type_stack, "Cyclic type set: " + target, 4)
                type_stack.add(target)
                try:
                    references.extend(types(source_type.find(f"{{{MD}}}Properties/{{{MD}}}Type")))
                finally:
                    type_stack.remove(target)
            else:
                references.append(target)
        return sorted(set(references))

    def adopt_attribute(owner, members):
        key = owner, tuple(members)
        if key in adopted_members:
            return adopted_members[key]
        node = _borrow_member(snapshot, base_root, owner, members)
        types(node.find(f"{{{MD}}}Properties/{{{MD}}}Type"))
        adopted_members[key] = node
        return node

    def section(owner, source, name):
        if (owner, name) in adopted_sections:
            return
        borrow_tabular_section(
            snapshot,
            {"op": "tabular-section.borrow", "parameters": parameters, "target": owner + ".TabularSection." + name},
        )
        for child in source.findall(f"{{{MD}}}ChildObjects/{{{MD}}}Attribute"):
            adopt_attribute(owner, [("TabularSection", name), ("Attribute", editor.node_name(child))])
        adopted_sections.add((owner, name))

    def walk(owner, parent, segments, members=()):
        if not segments:
            return
        name = segments[0]
        standards = {
            node.get("name")
            for node in parent.findall(f"{{{MD}}}Properties/{{{MD}}}StandardAttributes/{{{XR}}}StandardAttribute")
        }
        kind = etree.QName(parent).localname
        implicit = (
            {"RegisterRecords"}
            if kind == "Document"
            else ({"LineNumber", "RowsCount"} if kind == "TabularSection" else set())
        )
        # Column totals of a tabular section are addressed as Total<Attribute>;
        # section() already adopts every attribute of the borrowed section.
        column_total = (
            kind == "TabularSection"
            and name.startswith("Total")
            and _member(parent, "Attribute", name[len("Total") :], optional=True) is not None
        )
        if name in standards or name in implicit or column_total:
            editor.require(len(segments) == 1, "Unsupported standard field traversal: " + ".".join(segments))
            return
        matches = [
            (kind, _member(parent, kind, name, optional=True))
            for kind in ("Attribute", "Dimension", "Resource", "TabularSection")
        ]
        matches = [(kind, node) for kind, node in matches if node is not None]
        editor.require(len(matches) == 1, "Unresolved data path: " + owner + "." + ".".join(segments), 4)
        kind, node = matches[0]
        if kind == "TabularSection":
            editor.require(not members, "Unsupported nested tabular section")
            section(owner, node, name)
            walk(owner, node, segments[1:], (("TabularSection", name),))
        else:
            adopted = adopt_attribute(owner, [*members, (kind, name)])
            if len(segments) > 1:
                references = types(adopted.find(f"{{{MD}}}Properties/{{{MD}}}Type"))
                editor.require(len(references) == 1, "Ambiguous reference path: " + ".".join(segments), 4)
                walk(references[0], adopt(references[0]), segments[1:])

    source_owner = adopt(owner_name) if owner_name else None
    # Form attributes, parameters and additional columns can themselves refer to
    # configuration types even when no control has an object-bound DataPath.
    types(form)
    attributes = form.findall(f"{{{editor.FORM}}}Attributes/{{{editor.FORM}}}Attribute")
    attribute_names = [node.get("name", "") for node in attributes]
    editor.require(
        all(editor.NAME.fullmatch(name) for name in attribute_names)
        and len({name.casefold() for name in attribute_names}) == len(attribute_names),
        "Invalid or duplicate form attribute",
        4,
    )
    type_link_paths = []
    for node in type_link_nodes:
        children = [child for child in node if isinstance(child.tag, str)]
        editor.require(
            not node.attrib
            and [child.tag for child in children] == [f"{{{XR}}}DataPath", f"{{{XR}}}LinkItem"]
            and all(
                not child.attrib and not any(isinstance(grandchild.tag, str) for grandchild in child)
                for child in children
            ),
            "Unsupported TypeLink structure",
            4,
        )
        path = (children[0].text or "").strip()
        index_text = (children[1].text or "").strip()
        item_path = path.split(".")
        if item_path[0] == "Items":
            # Link to a field of the current row of a form table: the platform
            # resolves Items.<Table>.CurrentData.<Field> through the table DataPath.
            editor.require(
                len(item_path) == 4
                and item_path[2] == "CurrentData"
                and all(editor.NAME.fullmatch(part) for part in item_path[1::2])
                and index_text == "0",
                "Invalid TypeLink reference",
                4,
            )
            tables = [item for item in form.iter(f"{{{editor.FORM}}}Table") if item.get("name") == item_path[1]]
            named = [
                item
                for item in form.iter()
                if isinstance(item.tag, str) and item.get("name") == item_path[1] and item.get("id") is not None
            ]
            editor.require(len(tables) == 1 and len(named) == 1, "Unresolved TypeLink form item: " + path, 4)
            table_path = (tables[0].findtext(f"{{{editor.FORM}}}DataPath") or "").strip()
            editor.require(table_path, "Unresolved TypeLink form item: " + path, 4)
            type_link_paths.append(table_path + "." + item_path[3])
            continue
        editor.require(
            editor.NAME.fullmatch(path) is not None
            and index_text.isascii()
            and index_text.isdigit()
            and int(index_text) > 0,
            "Invalid TypeLink reference",
            4,
        )
        matches = [attribute for attribute in attributes if attribute.get("name") == path]
        editor.require(len(matches) == 1, "Unresolved TypeLink data path: " + path, 4)
        type_description = matches[0].find(f"{{{editor.FORM}}}Type")
        value_types = (
            [] if type_description is None else [child for child in type_description if isinstance(child.tag, str)]
        )
        editor.require(
            type_description is not None
            and not type_description.attrib
            and len(value_types) == 1
            and value_types[0].tag == f"{{{editor.V8}}}Type"
            and not value_types[0].attrib
            and not any(isinstance(child.tag, str) for child in value_types[0]),
            "Unsupported TypeLink data type: " + path,
            4,
        )
        raw_type = (value_types[0].text or "").strip()
        prefix, separator, local_type = raw_type.partition(":")
        family, dot, linked_chart_name = local_type.partition(".")
        editor.require(
            separator
            and value_types[0].nsmap.get(prefix) == CFG
            and family == "ChartOfAccountsRef"
            and dot
            and editor.NAME.fullmatch(linked_chart_name),
            "Unsupported TypeLink data type: " + path,
            4,
        )
        references = types(type_description)
        linked_chart_ref = "ChartOfAccounts." + linked_chart_name
        editor.require(references == [linked_chart_ref], "Unsupported TypeLink data type: " + path, 4)
        adopt(linked_chart_ref)
        base_chart, _ = _checked(
            snapshot, alias, f"{DIRECTORIES['ChartOfAccounts']}/{linked_chart_name}.xml", "ChartOfAccounts"
        )
        maximum = editor.prop(base_chart, "MaxExtDimensionCount")
        editor.require(
            maximum.isascii() and maximum.isdigit() and int(maximum) > 0 and int(index_text) <= int(maximum),
            "TypeLink item exceeds chart extra-dimension count",
            4,
        )
        type_link_paths.append(path)
    data_paths = {
        node.text
        for node in form.iter()
        if node.text
        and (
            node.tag
            in {f"{{{editor.FORM}}}DataPath", f"{{{editor.FORM}}}TitleDataPath", f"{{{editor.FORM}}}RowPictureDataPath"}
            or node.tag == f"{{{editor.FORM}}}Field"
            and node.getparent().tag == f"{{{editor.FORM}}}UseAlways"
        )
    }
    data_paths.update(type_link_paths)
    mains = [node for node in attributes if node.findtext(f"{{{editor.FORM}}}MainAttribute") == "true"]
    editor.require(len(mains) <= 1, "Ambiguous main form attribute", 4)
    main_name = mains[0].get("name") if mains else None
    if main_name and source_owner is not None:
        main_types = types(mains[0].find(f"{{{editor.FORM}}}Type"))
        editor.require(main_types == [owner_name], "Main attribute does not match owner", 4)
        if mode == "All":
            for child in source_owner.findall(f"{{{MD}}}ChildObjects/*"):
                kind, name = etree.QName(child).localname, editor.prop(child, "Name")
                if kind in {"Attribute", "Dimension", "Resource", "TabularSection"}:
                    walk(owner_name, source_owner, [name])
        virtual_columns, paths, tables = {}, set(), set()
        for additional in mains[0].findall(f"{{{editor.FORM}}}Columns/{{{editor.FORM}}}AdditionalColumns"):
            table = additional.get("table", "")
            editor.require(
                table.startswith(main_name + ".") and table not in tables,
                "Invalid or duplicate AdditionalColumns table",
                4,
            )
            tables.add(table)
            paths.add(table)
            for column in additional.findall(f"{{{editor.FORM}}}Column"):
                name = column.get("name", "")
                key = table + "." + name
                editor.require(
                    editor.NAME.fullmatch(name)
                    and key.casefold() not in {existing.casefold() for existing in virtual_columns},
                    "Duplicate or invalid additional column",
                    4,
                )
                virtual_columns[key] = table
        paths.update(value for value in data_paths if value.startswith(main_name + "."))
        for path in sorted(paths):
            # AdditionalColumns are form-owned values, not metadata attributes.
            value = virtual_columns.get(path, path)
            parts = value.split(".")
            editor.require(all(editor.NAME.fullmatch(part) for part in parts), "Unsupported DataPath: " + path)
            walk(owner_name, source_owner, parts[1:])

    for path in sorted(data_paths):
        parts = path.split(".")
        if main_name and source_owner is not None and parts[0] == main_name:
            continue
        editor.require(all(editor.NAME.fullmatch(part) for part in parts), "Unsupported DataPath: " + path)
        matches = [node for node in attributes if node.get("name") == parts[0]]
        editor.require(len(matches) == 1, "Unresolved form attribute path: " + path, 4)
        node, remaining = matches[0], parts[1:]
        while remaining:
            columns = [
                column
                for column in node.findall(f"{{{editor.FORM}}}Columns/{{{editor.FORM}}}Column")
                if column.get("name") == remaining[0]
            ]
            editor.require(len(columns) <= 1, "Ambiguous form column: " + path, 4)
            if columns:
                node, remaining = columns[0], remaining[1:]
                continue
            references = types(node.find(f"{{{editor.FORM}}}Type"))
            editor.require(len(references) == 1, "Unsupported form attribute traversal: " + path, 4)
            walk(references[0], adopt(references[0]), remaining)
            break

    builtin_styles = {
        "AccentColor",
        "FormBackColor",
        "LargeTextFont",
        "NormalTextFont",
        "TableHeaderBackColor",
        "ToolTipBackColor",
    }
    for node in form.iter():
        if not isinstance(node.tag, str):
            continue
        value = node.text or ""
        if (
            node.tag in {f"{{{editor.FORM}}}CommandName", f"{{{editor.FORM}}}Command", f"{{{editor.FORM}}}CommandGroup"}
            and value
        ):
            parts = value.split(".")
            if parts[0] in {"CommonCommand", "CommandGroup"}:
                adopt(value)
            elif len(parts) >= 2 and parts[0] in DIRECTORIES:
                if (
                    len(parts) == 4
                    and parts[2] == "Command"
                    and all(editor.NAME.fullmatch(part) for part in (parts[1], parts[3]))
                ):
                    command_owner = ".".join(parts[:2])
                    adopt(command_owner)
                    source_command = _borrow_member(snapshot, base_root, command_owner, [("Command", parts[3])])
                    group = editor.prop(source_command, "Group")
                    if group.startswith("CommandGroup."):
                        adopt(group)
                    continue
                editor.require(
                    len(parts) == 4 and parts[0] == "Document" and parts[2:] == ["StandardCommand", "CreateBasedOn"],
                    "Unsupported metadata command: " + value,
                    4,
                )
                command_owner = ".".join(parts[:2])
                source = adopt(command_owner)
                based_on = source.findall(f"{{{MD}}}Properties/{{{MD}}}BasedOn")
                editor.require(
                    editor.prop(source, "UseStandardCommands") == "true"
                    and len(based_on) == 1
                    and len(based_on[0]) > 0,
                    "CreateBasedOn command is unavailable in source: " + value,
                    4,
                )
                for item in based_on[0]:
                    editor.require(item.tag == f"{{{XR}}}Item" and item.text, "Unsupported BasedOn dependency", 4)
                    adopt(item.text)
                path = f"{DIRECTORIES[parts[0]]}/{parts[1]}.xml"
                target, original = _checked(snapshot, "target", path, parts[0])
                properties = target.find(f"{{{MD}}}Properties")
                changed = False
                for key in ("UseStandardCommands", "BasedOn"):
                    expected = source.find(f"{{{MD}}}Properties/{{{MD}}}{key}")
                    context = etree.Element(properties.tag, nsmap=properties.nsmap)
                    context.append(copy.deepcopy(expected))
                    expected = context[-1]
                    current = properties.find(f"{{{MD}}}{key}")
                    if current is None:
                        properties.append(copy.deepcopy(expected))
                        changed = True
                    else:
                        editor.require(
                            editor.signature(current) == editor.signature(expected),
                            "Conflicting command property: " + command_owner + "." + key,
                            3,
                        )
                if changed:
                    snapshot.stage(path, editor.serialize_like(target.getparent(), original))
        if node.tag == f"{{{XR}}}Ref" and value:
            parts = value.split(".")
            if len(parts) == 2 and parts[0] == "StdPicture":
                editor.require(editor.NAME.fullmatch(parts[1]), "Invalid standard picture")
            elif len(parts) == 2 and parts[0] == "CommonPicture":
                adopt(value)
            else:
                raise editor.Rejected("Unsupported form reference: " + value)
        xsi_type = node.get("{http://www.w3.org/2001/XMLSchema-instance}type", "")
        if ":" in xsi_type:
            prefix, local = xsi_type.split(":", 1)
            if node.nsmap.get(prefix) == XR and local == "DesignTimeRef" and value:
                parts = value.split(".")
                empty_enum = len(parts) == 3 and parts[2] == "EmptyRef"
                enum_value = len(parts) == 4 and parts[2] == "EnumValue"
                editor.require(
                    (empty_enum or enum_value)
                    and parts[0] == "Enum"
                    and all(editor.NAME.fullmatch(part) for part in parts),
                    "Unsupported design-time reference: " + value,
                )
                adopt(".".join(parts[:2]))
                if enum_value:
                    _borrow_member(snapshot, base_root, ".".join(parts[:2]), [("EnumValue", parts[3])])
        for style in (value, node.get("ref", "")):
            prefix, separator, name = style.partition(":")
            if separator and node.nsmap.get(prefix) == STYLE:
                editor.require(editor.NAME.fullmatch(name), "Invalid style reference")
                # Стиль, которого нет в основной конфигурации, - платформенный (BorderColor, FormTextColor и т.п.).
                if (
                    name not in builtin_styles
                    and snapshot.read(alias, f"StyleItems/{name}.xml", optional=True) is not None
                ):
                    adopt("StyleItem." + name)
    return sorted(resolved)


def _native_command_projection(form):
    """Normalize inherited standard-command bindings as Designer serializes them."""
    from . import metadata as editor

    references = {}
    for command in form.iter(f"{{{editor.FORM}}}CommandName"):
        value = (command.text or "").strip()
        if not value.startswith("Form.StandardCommand."):
            continue
        parent = command.getparent()
        identity = (parent.tag, parent.get("name"), parent.get("id"))
        editor.require(
            identity[1] and identity[2], "Standard command projection requires named, identified controls", 3
        )
        editor.require(identity not in references, "Ambiguous standard command control identity", 3)
        references[identity] = value
        command.text = "0"
    return references


def _repair_native_command_projection(form, references):
    """Change only known inherited command bindings, preserving all other edits."""
    from . import metadata as editor

    controls = {}
    for command in form.iter(f"{{{editor.FORM}}}CommandName"):
        ancestor = command.getparent()
        while ancestor is not None and ancestor is not form:
            if etree.QName(ancestor).localname == "BaseForm":
                break
            ancestor = ancestor.getparent()
        if ancestor is not form:
            continue
        parent = command.getparent()
        identity = (parent.tag, parent.get("name"), parent.get("id"))
        if identity in controls:
            editor.require(False, "Ambiguous command control identity during projection repair", 3)
        controls[identity] = command
    for identity, old_value in references.items():
        command = controls.get(identity)
        editor.require(command is not None, "Inherited standard command control changed; projection repair refused", 3)
        assert command is not None
        value = (command.text or "").strip()
        editor.require(
            value in {old_value, "0"}, "Inherited standard command binding changed; projection repair refused", 3
        )
        command.text = "0"


_NATIVE_MAIN_ATTRIBUTE_ID = "1000001"


# Data path properties Designer drops in a native projection (R018, R234 samples).
_NATIVE_DROPPED_PATHS = ("DataPath", "TitleDataPath", "FooterDataPath")


def _native_form_projection(form, source_owner):
    """Project a base form as Designer 8.3.27 stores it after "Add to extension".

    Verified on Catalog.ДоговорыКонтрагентов.ФормаЭлемента (R018) and
    Document.СчетНаОплатуПокупателю.ФормаДокумента (R234), 2026-09-27:
    element tree only, without data paths (including title and footer paths), form attributes, commands, parameters
    and command interface; every button command is 0 and BaseForm is identical.
    Choice parameter links keep a reference by form attribute id or by
    `<main id>/0:<object attribute uuid>` (R028 samples). Anything else is rejected.
    """
    from . import metadata as editor

    attributes = form.findall("f:Attributes/f:Attribute", editor.NS)
    ids = {node.get("name"): node.get("id") for node in attributes}
    mains = [node.get("id") for node in _native_main_attributes(form)]
    object_attributes = {}
    if source_owner is not None:
        for node in source_owner.findall(f"{{{MD}}}ChildObjects/{{{MD}}}Attribute"):
            object_attributes[editor.node_name(node)] = node.get("uuid")
    for node in form.iter(f"{{{XR}}}DataPath"):
        parts = (node.text or "").split(".")
        if len(parts) == 1 and parts[0] in ids:
            node.text = ids[parts[0]]
            continue
        editor.require(
            len(parts) == 2 and len(mains) == 1 and ids.get(parts[0]) == mains[0] and parts[1] in object_attributes,
            "Unsupported native projection path: " + (node.text or ""),
            4,
        )
        node.text = f"{mains[0]}/0:{object_attributes[parts[1]]}"
    dropped = {f"{{{editor.FORM}}}{name}" for name in _NATIVE_DROPPED_PATHS}
    for node in form.iter():
        if not isinstance(node.tag, str) or node.tag in dropped:
            continue
        local = etree.QName(node).localname
        editor.require(
            not local.endswith("DataPath") or node.tag == f"{{{XR}}}DataPath",
            "Unsupported native projection path property: " + local,
            4,
        )
        editor.require(
            local != "ConditionalAppearance", "Unsupported native projection section: ConditionalAppearance", 4
        )
    for section in ("Attributes", "Commands", "Parameters", "CommandInterface"):
        for node in form.findall(f"f:{section}", editor.NS):
            form.remove(node)
    for node in [node for node in form.iter() if node.tag in dropped]:
        node.getparent().remove(node)
    for node in form.iter(f"{{{editor.FORM}}}CommandName"):
        node.text = "0"
    for table in form.iter(f"{{{editor.FORM}}}Table"):
        for node in table.findall("f:CommandSet", editor.NS):
            table.remove(node)
    for decoration in form.iter(f"{{{editor.FORM}}}PictureDecoration"):
        for node in decoration.findall("f:Picture", editor.NS):
            decoration.remove(node)
    etree.SubElement(form, f"{{{editor.FORM}}}Attributes")


def _native_main_attributes(form):
    from . import metadata as editor

    return [
        node
        for node in form.findall("f:Attributes/f:Attribute", editor.NS)
        if node.findtext("f:MainAttribute", namespaces=editor.NS) == "true"
    ]


def _signature_without_id(node):
    from . import metadata as editor

    signature = editor.signature(node)
    return (signature[0], tuple(item for item in signature[1] if item[0] != "id"), *signature[2:])


def _repair_native_main_attribute_projection(form, source_main_signature=None):
    """Project only the adopted main-attribute ID observed in native Designer."""
    from . import metadata as editor

    mains = _native_main_attributes(form)
    editor.require(len(mains) == 1, "Native main attribute projection requires one main attribute", 3)
    main = mains[0]
    editor.require(
        main.get("name") == "Объект", "Native main attribute projection supports only the observed Объект attribute", 3
    )
    editor.require(
        main.get("id") in {"1", _NATIVE_MAIN_ATTRIBUTE_ID},
        "Main attribute ID changed; native projection repair refused",
        3,
    )
    if source_main_signature is not None:
        editor.require(
            _signature_without_id(main) == source_main_signature,
            "Main attribute properties changed; native projection repair refused",
            3,
        )
    for node in form.iter():
        if node is main or (
            isinstance(node.tag, str)
            and etree.QName(node).localname == "Attribute"
            and node.findtext("f:MainAttribute", namespaces=editor.NS) == "true"
        ):
            continue
        editor.require(
            node.get("id") != _NATIVE_MAIN_ATTRIBUTE_ID,
            "Native main attribute ID collides with another form element",
            3,
        )
    main.set("id", _NATIVE_MAIN_ATTRIBUTE_ID)


def _form_commands(form, editor):
    containers = form.findall(f"{{{editor.FORM}}}Commands")
    editor.require(len(containers) <= 1, "Ambiguous form command category", 3)
    return containers[0] if containers else None


def _selected_form_commands(form, names, editor):
    commands = _form_commands(form, editor)
    source = list(commands.findall(f"{{{editor.FORM}}}Command")) if commands is not None else []
    by_name, by_id = {}, {}
    for command in source:
        name, command_id = command.get("name"), command.get("id")
        editor.require(name and editor.NAME.fullmatch(name), "Invalid base form command name", 4)
        key = name.casefold()
        editor.require(key not in by_name, "Ambiguous base form command name", 4)
        by_name[key] = command
        if command_id:
            editor.require(command_id not in by_id, "Ambiguous base form command ID", 4)
            by_id[command_id] = command

    selected = []
    seen = set()
    for name in names:
        editor.require(isinstance(name, str) and editor.NAME.fullmatch(name), "Invalid selected form command", 3)
        key = name.casefold()
        editor.require(key not in seen, "Duplicate selected form command", 3)
        seen.add(key)
        editor.require(key in by_name, "Selected base form command is missing", 4)
        command = copy.deepcopy(by_name[key])
        for action in command.findall(f"{{{editor.FORM}}}Action"):
            command.remove(action)
        selected.append(command)
    return selected


def _command_signature(command, editor):
    normalized = copy.deepcopy(command)
    for node in normalized.iter():
        if node.text is not None and not node.text.strip():
            node.text = None
        if node.tail is not None and not node.tail.strip():
            node.tail = None
    return editor.signature(normalized)


def _selected_form_events(form, names, editor):
    containers = form.findall(f"{{{editor.FORM}}}Events")
    editor.require(len(containers) <= 1, "Ambiguous form event category", 3)
    events = list(containers[0].findall(f"{{{editor.FORM}}}Event")) if containers else []
    by_name = {}
    for event in events:
        name = event.get("name")
        editor.require(name and editor.NAME.fullmatch(name), "Invalid base form event name", 4)
        key = name.casefold()
        editor.require(key not in by_name, "Ambiguous base form event name", 4)
        by_name[key] = event

    selected = {}
    for name in names:
        editor.require(isinstance(name, str) and editor.NAME.fullmatch(name), "Invalid selected form event", 3)
        key = name.casefold()
        editor.require(key not in selected, "Duplicate selected form event", 3)
        event = by_name.get(key)
        if event is None:
            raise editor.Rejected("Selected base form event is missing or extended", 4)
        event_name, handler = event.get("name"), event.text
        if event_name is None or handler is None:
            raise editor.Rejected("Selected base form event is missing or extended", 4)
        editor.require(
            set(event.attrib) == {"name"} and not len(event) and handler.strip(),
            "Selected base form event is missing or extended",
            4,
        )
        selected[key] = (event_name, handler.strip())
    return selected


def _remove_selected_form_events(form, selected, editor):
    containers = form.findall(f"{{{editor.FORM}}}Events")
    editor.require(len(containers) <= 1, "Ambiguous form event category", 3)
    if not containers:
        return False
    changed = False
    for event in list(containers[0].findall(f"{{{editor.FORM}}}Event")):
        key = (event.get("name") or "").casefold()
        if key not in selected:
            continue
        expected_name, expected_handler = selected[key]
        editor.require(
            event.get("name") == expected_name
            and set(event.attrib) == {"name"}
            and not len(event)
            and (event.text or "").strip() == expected_handler,
            "Conflicting existing inherited form event",
            3,
        )
        containers[0].remove(event)
        changed = True
    return changed


def _merge_selected_form_commands(form, selected, editor):
    commands = _form_commands(form, editor)
    if commands is None:
        commands = etree.Element(f"{{{editor.FORM}}}Commands")
        base = form.find(f"{{{editor.FORM}}}BaseForm")
        if base is None:
            form.append(commands)
        else:
            form.insert(form.index(base), commands)
    existing = list(commands.findall(f"{{{editor.FORM}}}Command"))
    by_name, by_id = {}, {}
    for command in existing:
        name, command_id = command.get("name"), command.get("id")
        editor.require(name and editor.NAME.fullmatch(name), "Invalid existing form command name", 3)
        key = name.casefold()
        editor.require(key not in by_name, "Ambiguous existing form command name", 3)
        by_name[key] = command
        if command_id:
            editor.require(command_id not in by_id, "Ambiguous existing form command ID", 3)
            by_id[command_id] = command

    changed = False
    for command in selected:
        name, command_id = command.get("name"), command.get("id")
        key = name.casefold()
        current = by_name.get(key)
        if current is not None:
            editor.require(
                current.get("id") == command_id
                and _command_signature(current, editor) == _command_signature(command, editor),
                "Conflicting existing form command",
                3,
            )
            continue
        if command_id and command_id in by_id:
            raise editor.Rejected("Conflicting existing form command ID", 3)
        commands.append(copy.deepcopy(command))
        by_name[key] = commands[-1]
        if command_id:
            by_id[command_id] = commands[-1]
        changed = True
    return changed


def borrow_form(snapshot, operation):
    """Stage an adopted form with inherited, not reconnected, base handlers.

    The new extension module is empty: base handlers remain inherited. Existing
    extension modules are never replaced, and the source module is read-only.
    Platform qualification of the projection is separate from this XML check.
    """
    from . import metadata as editor

    target, parameters = operation["target"], operation["parameters"]
    module_only = parameters.get("moduleOnly", False)
    selected_names = parameters.get("commands")
    selected_event_names = parameters.get("inheritEvents")
    if selected_names is not None or selected_event_names is not None:
        for names, message in (
            (selected_names, "Invalid selected form commands"),
            (selected_event_names, "Invalid selected form events"),
        ):
            if names is None:
                continue
            editor.require(
                isinstance(names, list)
                and names
                and all(isinstance(name, str) and editor.NAME.fullmatch(name) for name in names)
                and len({name.casefold() for name in names}) == len(names),
                message,
                3,
            )
        editor.require(not module_only, "Selected form commands cannot use moduleOnly", 3)
        editor.require(
            not any(
                parameters.get(option, False)
                for option in (
                    "nativeProjection",
                    "repairNativeCommandProjection",
                    "repairNativeMainAttributeProjection",
                )
            ),
            "Selected form commands cannot be combined with native projection options",
            3,
        )
        editor.require(
            "borrowMainAttribute" not in parameters, "Selected form commands cannot include main attribute adoption", 3
        )
    editor.require(
        not module_only or "borrowMainAttribute" not in parameters,
        "Module-only borrowing cannot include main attribute adoption",
    )
    repair_main_projection = parameters.get("repairNativeMainAttributeProjection", False)
    editor.require(
        not module_only or not repair_main_projection,
        "Module-only borrowing cannot include native main attribute projection",
    )
    parts = target.split(".")
    common = len(parts) == 2 and parts[0] == "CommonForm"
    editor.require(
        common or len(parts) == 4 and parts[2] == "Form" and parts[0] in editor.OWNER_TYPES.values(),
        "Expected CommonForm.Name or Kind.Name.Form.Name",
    )
    editor.require(all(editor.NAME.fullmatch(part) for part in parts), "Invalid form target")
    name, kind = parts[-1], "CommonForm" if common else "Form"
    base_root = parameters["baseRoot"]
    alias = snapshot.source_root(Path(base_root))
    editor.require(alias != "target", "Base root must differ from extension root")
    config, config_bytes = _checked(snapshot, "target", "Configuration.xml", "Configuration")
    base_config, _ = _checked(snapshot, alias, "Configuration.xml", "Configuration")
    editor.require(
        editor.prop(config, "ConfigurationExtensionPurpose") in {"Patch", "Customization", "AddOn"}
        and editor.prop(config, "KeepMappingToExtendedConfigurationObjectsByIDs") == "true",
        "Target must be an extension with internal ID mapping",
    )
    editor.require(not editor.prop(base_config, "ConfigurationExtensionPurpose"), "Base must be a main configuration")
    owner_name = None if common else ".".join(parts[:2])
    owner_path = "Configuration.xml" if common else f"{DIRECTORIES[parts[0]]}/{parts[1]}.xml"
    stem = f"CommonForms/{name}" if common else f"{DIRECTORIES[parts[0]]}/{parts[1]}/Forms/{name}"
    descriptor_path, form_path, module_path = stem + ".xml", stem + "/Ext/Form.xml", stem + "/Ext/Form/Module.bsl"
    base_owner = base_config if common else _checked(snapshot, alias, owner_path, parts[0])[0]
    base_containers = base_owner.findall(f"{{{MD}}}ChildObjects")
    editor.require(len(base_containers) == 1, "Base form owner ChildObjects missing or ambiguous", 4)
    base_children = _registrations(base_config) if common else base_containers[0]
    base_registrations = [
        node
        for node in base_children
        if node.tag == f"{{{MD}}}{kind}" and (node.text or "").casefold() == name.casefold()
    ]
    editor.require(
        len(base_registrations) == 1 and base_registrations[0].text == name,
        "Base form registration missing or ambiguous",
        4,
    )
    source, _ = _checked(snapshot, alias, descriptor_path, kind)
    editor.require(
        editor.node_name(source) == name
        and editor.prop(source, "FormType") == "Managed"
        and editor.prop(source, "ObjectBelonging") in {"", "Native"}
        and not editor.prop(source, "ExtendedConfigurationObject"),
        "Unsupported base form",
        4,
    )
    form_bytes = snapshot.read(alias, form_path)
    form = editor.xml_read(form_bytes, f"{{{editor.FORM}}}Form")
    editor.require(
        form.get("version") in {"2.17", "2.20"} and not form.findall(f"{{{editor.FORM}}}BaseForm"),
        "Unsupported base form body",
        4,
    )
    editor.require(
        module_only or form.get("version") == config.getparent().get("version"),
        "Base form format differs from target configuration format",
        4,
    )
    snapshot.read(alias, module_path, optional=True)
    if module_only:
        # Build a delta in the target format, never relabel the source layout.
        # Base handlers remain inherited, as in the full-form route below.
        form = etree.Element(
            f"{{{editor.FORM}}}Form", nsmap={None: editor.FORM}, version=config.getparent().get("version")
        )
    # Designer inherits base handlers. Copying their bindings into the extension
    # connects them a second time (including element events and command actions).
    # Project only the source: existing extension handlers below remain untouched.
    selected_events = (
        _selected_form_events(form, selected_event_names, editor) if selected_event_names is not None else None
    )
    for binding in [*form.iter(f"{{{editor.FORM}}}Events"), *form.findall("f:Commands/f:Command/f:Action", editor.NS)]:
        binding.getparent().remove(binding)
    if parameters.get("nativeProjection", False):
        editor.require(
            not module_only
            and "borrowMainAttribute" not in parameters
            and not repair_main_projection
            and not parameters.get("repairNativeCommandProjection", False),
            "Native projection cannot be combined with other form projection options",
        )
        _native_form_projection(form, None if common else base_owner)
    legacy_base = copy.deepcopy(form)
    legacy_base.tag = f"{{{editor.FORM}}}BaseForm"
    command_projection = _native_command_projection(form)
    command_projected_base = copy.deepcopy(form)
    command_projected_base.tag = f"{{{editor.FORM}}}BaseForm"
    source_mains = _native_main_attributes(form)
    source_main_signature = _signature_without_id(source_mains[0]) if len(source_mains) == 1 else None
    if repair_main_projection:
        _repair_native_main_attribute_projection(form)
    expected_base = copy.deepcopy(form)
    expected_base.tag = f"{{{editor.FORM}}}BaseForm"
    selected = _selected_form_commands(form, selected_names, editor) if selected_names is not None else None
    selective = selected is not None or selected_events is not None
    if owner_name:
        borrow_object(snapshot, {"op": "object.borrow", "target": owner_name, "parameters": {"baseRoot": base_root}})
    owner, owner_bytes = (config, config_bytes) if common else _checked(snapshot, "target", owner_path, parts[0])
    editor.require(len(owner.findall(f"{{{MD}}}ChildObjects")) <= 1, "Ambiguous target ChildObjects", 4)
    children = _registrations(owner) if common else owner.find(f"{{{MD}}}ChildObjects")
    if children is None:
        children = etree.SubElement(owner, f"{{{MD}}}ChildObjects")
    registrations = [
        node for node in children if node.tag == f"{{{MD}}}{kind}" and (node.text or "").casefold() == name.casefold()
    ]
    editor.require(
        len(registrations) <= 1 and (not registrations or registrations[0].text == name),
        "Ambiguous form registration",
        3,
    )
    existing = snapshot.read("target", descriptor_path, optional=True)
    editor.require(bool(registrations) == (existing is not None), "Form registration/file mismatch", 3)
    if selective:
        editor.require(existing is not None, "Selected form commands require an existing borrowed form", 3)
    if existing is not None:
        current, _ = _checked(snapshot, "target", descriptor_path, kind)
        editor.require(
            editor.node_name(current) == name
            and editor.prop(current, "ObjectBelonging") == "Adopted"
            and (editor.prop(current, "ExtendedConfigurationObject") or "").lower() == editor.identity(source),
            "Existing form has a conflicting base link",
            3,
        )
        working = editor.xml_read(snapshot.read("target", form_path), f"{{{editor.FORM}}}Form")
        if not selective:
            editor.require(working.get("version") == form.get("version"), "Existing form version differs from base", 3)
        else:
            editor.require(working.get("version") in {"2.17", "2.20"}, "Unsupported existing form version", 3)
        bases = working.findall(f"{{{editor.FORM}}}BaseForm")
        editor.require(len(bases) == 1, "Existing form BaseForm is missing or ambiguous", 3)
        repair_commands = parameters.get("repairNativeCommandProjection", False)
        if selective:
            working_bytes = snapshot.read("target", form_path)
            changed = _merge_selected_form_commands(working, selected, editor) if selected is not None else False
            changed = (
                _merge_selected_form_commands(bases[0], selected, editor) if selected is not None else False
            ) or changed
            changed = (
                _remove_selected_form_events(working, selected_events, editor) if selected_events is not None else False
            ) or changed
            changed = (
                _remove_selected_form_events(bases[0], selected_events, editor)
                if selected_events is not None
                else False
            ) or changed
            if changed:
                snapshot.stage(form_path, editor.serialize_like(working, working_bytes))
            return
        if repair_commands or repair_main_projection:
            base = bases[0]
            base_signature = editor.signature(base)
            allowed_bases = [command_projected_base]
            if repair_commands:
                allowed_bases.append(legacy_base)
            if repair_main_projection:
                projected_bases = []
                for candidate in allowed_bases:
                    candidate = copy.deepcopy(candidate)
                    _repair_native_main_attribute_projection(candidate, source_main_signature)
                    projected_bases.append(candidate)
                allowed_bases.extend(projected_bases)
            editor.require(
                base_signature in {editor.signature(candidate) for candidate in allowed_bases},
                "BaseForm is not the exact known pre-repair projection",
                3,
            )
            if repair_commands:
                _repair_native_command_projection(base, command_projection)
                _repair_native_command_projection(working, command_projection)
            if repair_main_projection:
                _repair_native_main_attribute_projection(base, source_main_signature)
                _repair_native_main_attribute_projection(working, source_main_signature)
            editor.require(
                editor.signature(base) == editor.signature(expected_base),
                "Repaired BaseForm does not match the requested native projection",
                3,
            )
            if editor.signature(working) != editor.signature(
                editor.xml_read(snapshot.read("target", form_path), f"{{{editor.FORM}}}Form")
            ):
                snapshot.stage(form_path, editor.serialize_like(working, snapshot.read("target", form_path)))
        else:
            editor.require(
                editor.signature(bases[0]) == editor.signature(expected_base),
                "BaseForm differs; explicit base update required",
                3,
            )
        snapshot.read("target", module_path, optional=True)
        borrow_form_dependencies(snapshot, base_root, owner_name, form, parameters.get("borrowMainAttribute", "Form"))
        return
    if parameters.get("moduleOnly", False):
        for directory, allowed in ((stem, "Ext"), (stem + "/Ext", "Form"), (stem + "/Ext/Form", "Module.bsl")):
            editor.require(
                set(snapshot.list_directory("target", directory, optional=True) or {}) <= {allowed},
                "Unregistered form artifacts already exist",
                3,
            )
    else:
        editor.require(
            not snapshot.list_directory("target", stem, optional=True), "Unregistered form artifacts already exist", 3
        )
    borrow_form_dependencies(snapshot, base_root, owner_name, form, parameters.get("borrowMainAttribute", "Form"))
    # Dependencies can update the same owner/configuration; register in that
    # resulting view, never in the earlier descriptor captured above.
    owner, owner_bytes = _checked(snapshot, "target", owner_path, "Configuration" if common else parts[0])
    children = _registrations(owner) if common else owner.find(f"{{{MD}}}ChildObjects")
    if children is None:
        children = etree.SubElement(owner, f"{{{MD}}}ChildObjects")
    shell = _shell(
        kind,
        name,
        source,
        editor.identity(config),
        _uuid_inventory(snapshot),
        target,
        xml_format=config.getparent().get("version"),
    )
    descriptor = editor.xml_read(shell, f"{{{MD}}}MetaDataObject")
    etree.SubElement(descriptor.find(f"{{{MD}}}{kind}/{{{MD}}}Properties"), f"{{{MD}}}FormType").text = "Managed"
    etree.indent(descriptor, space="\t")
    if common:
        _register(children, kind, name)
    else:
        registration = etree.Element(f"{{{MD}}}Form")
        registration.text = name
        registration.tail = "\n\t\t"
        # Platform order keeps templates and commands after forms.
        later = [
            child
            for child in children
            if isinstance(child.tag, str) and etree.QName(child).localname in {"Template", "Command"}
        ]
        if later:
            registration.tail = later[0].getprevious().tail if later[0].getprevious() is not None else children.text
            children.insert(children.index(later[0]), registration)
        elif len(children):
            registration.tail = children[-1].tail
            children[-1].tail = "\n\t\t\t"
            children.append(registration)
        else:
            children.text = "\n\t\t\t"
            children.append(registration)
    form.append(expected_base)
    snapshot.stage(owner_path, editor.serialize_like(owner.getparent(), owner_bytes))
    snapshot.stage(descriptor_path, editor.serialize_like(descriptor, shell))
    snapshot.stage(form_path, editor.serialize_like(form, b"\n"))
    if snapshot.read("target", module_path, optional=True) is None:
        snapshot.stage(module_path, b"")
