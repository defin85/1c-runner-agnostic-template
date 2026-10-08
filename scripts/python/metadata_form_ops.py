"""Form mutations in the shared snapshot; never invoke a writing CLI.

The scalar field layout follows cc-1c-skills form-edit (Nick Shirokov, MIT;
automation/vendor/cc-1c-skills/LICENSE). Existing editor guards are reused.
"""

import copy
import decimal
import math
import re

import lxml.etree as etree

from . import metadata_borrow as borrow

FORM_OBJECT_TYPES = {
    kind: kind + "Object"
    for kind in (
        "Document",
        "Catalog",
        "DataProcessor",
        "Report",
        "ExternalDataProcessor",
        "ExternalReport",
        "ChartOfAccounts",
        "ChartOfCharacteristicTypes",
        "ExchangePlan",
        "BusinessProcess",
        "Task",
    )
}
FORM_OBJECT_TYPES["InformationRegister"] = "InformationRegisterRecordManager"


def form_path(target):
    from . import metadata as editor

    parts = target.split(".")
    editor.require(all(editor.NAME.fullmatch(part) for part in parts), "Invalid form target")
    if len(parts) == 2 and parts[0] == "CommonForm":
        return f"CommonForms/{parts[1]}/Ext/Form.xml"
    editor.require(len(parts) == 4 and parts[2] == "Form", "Expected exact form target")
    if parts[0] in {"ExternalDataProcessor", "ExternalReport"}:
        return f"{parts[1]}/Forms/{parts[3]}/Ext/Form.xml"
    editor.require(parts[0] in editor.OWNER_TYPES.values(), "Unsupported form owner")
    return f"{borrow.DIRECTORIES[parts[0]]}/{parts[1]}/Forms/{parts[3]}/Ext/Form.xml"


def rewrite_rename_references(snapshot, form_targets, old_path, new_path, generated_names):
    """Rewrite only selected form references while the owner still has its old name."""
    from . import metadata as editor

    xsi = "http://www.w3.org/2001/XMLSchema-instance"
    seen = set()

    folded_generated = {}
    for name in generated_names:
        folded_generated.setdefault(name.casefold(), []).append(name)

    def rewrite_type(node):
        value = node.text or ""
        prefix, separator, local = value.partition(":")
        matches = folded_generated.get(local.casefold(), [])
        if not matches:
            return False
        editor.require(
            len(matches) == 1
            and separator
            and node.nsmap.get(prefix) == borrow.CFG
            and node.tag == f"{{{editor.V8}}}Type",
            "Unsupported or ambiguous form type reference",
            3,
        )
        editor.require(not node.attrib and not len(node), "Unsupported or ambiguous form type structure", 3)
        old_type = matches[0]
        editor.require(local == old_type, "Case-ambiguous form type reference", 3)
        family, separator, _ = old_type.partition(".")
        editor.require(
            separator and (family not in {"DefinedType", "Characteristic"}),
            "Unsupported form type set representation",
            3,
        )
        node.text = prefix + ":" + generated_names[old_type]
        return True

    def members(tree, section, member_tag):
        containers = tree.findall(f"f:{section}", editor.NS)
        editor.require(len(containers) <= 1, "Ambiguous form section: " + section, 3)
        if not containers:
            return []
        return containers[0].findall(f"f:{member_tag}", editor.NS)

    for form_target in form_targets:
        physical = form_path(form_target)
        folded = physical.casefold()
        editor.require(folded not in seen, "Repeated form target", 3)
        seen.add(folded)

        view = copy.copy(snapshot)
        view.load_form(physical)
        tree = view.tree
        changed = False
        attributes = members(tree, "Attributes", "Attribute")
        parameters = members(tree, "Parameters", "Parameter")
        fields = list(attributes) + list(parameters)
        for attribute in attributes:
            columns = attribute.findall("f:Columns", editor.NS)
            editor.require(len(columns) <= 1, "Ambiguous form columns section", 3)
            if columns:
                fields.extend(columns[0].findall("f:Column", editor.NS))
        for field in fields:
            types = field.findall("f:Type", editor.NS)
            editor.require(len(types) <= 1, "Ambiguous form type section", 3)
            if types:
                for typed in types[0].iter(f"{{{editor.V8}}}Type", f"{{{editor.V8}}}TypeSet"):
                    changed |= rewrite_type(typed)

        for attribute in attributes:
            settings_nodes = attribute.findall("f:Settings", editor.NS)
            matching_settings = [
                settings
                for settings in settings_nodes
                if any(
                    (node.text or "").casefold() == old_path.casefold()
                    for node in settings.findall("f:MainTable", editor.NS)
                )
            ]
            if not matching_settings:
                continue
            editor.require(
                len(settings_nodes) == 1 and len(matching_settings) == 1,
                "Unsupported or ambiguous DynamicList settings",
                3,
            )
            settings = matching_settings[0]
            main_tables = settings.findall("f:MainTable", editor.NS)
            matching = [node for node in main_tables if (node.text or "").casefold() == old_path.casefold()]
            type_nodes = attribute.findall("f:Type", editor.NS)
            dynamic_types = []
            for type_node in type_nodes:
                for node in type_node.findall(f"{{{editor.V8}}}Type"):
                    prefix, separator, local = (node.text or "").partition(":")
                    if separator and local == "DynamicList" and node.nsmap.get(prefix) == borrow.CFG:
                        dynamic_types.append(node)
            editor.require(
                len(main_tables) == 1
                and len(matching) == 1
                and settings.get(f"{{{xsi}}}type") == "DynamicList"
                and len(type_nodes) == 1
                and len(dynamic_types) == 1
                and not type_nodes[0].attrib
                and len(type_nodes[0]) == 1
                and not dynamic_types[0].attrib
                and not len(dynamic_types[0])
                and not matching[0].attrib
                and not len(matching[0]),
                "Unsupported or ambiguous DynamicList MainTable",
                3,
            )
            editor.require(matching[0].text == old_path, "Case-ambiguous form MainTable", 3)
            matching[0].text = new_path
            changed = True

        form_body = snapshot.read("target", physical)
        if changed:
            snapshot.stage(physical, editor.serialize_like(tree, form_body, preserve_mixed_eol=True))


def create_form(snapshot, operation):
    """Managed form, based on form-add's existing XML layout."""
    from . import metadata as editor
    from . import metadata_object_ops as objects

    target, parameters = operation["target"], operation["parameters"]
    parts = target.split(".")
    editor.require(
        len(parts) == 2 and parts[0] in FORM_OBJECT_TYPES and editor.NAME.fullmatch(parts[1]),
        "Form creation owner is not connected",
    )
    purpose = parameters["purpose"]
    processors = {"DataProcessor", "Report", "ExternalDataProcessor", "ExternalReport"}
    editor.require(
        purpose in {"Object", "List", "Choice", "Record"}
        and (purpose not in {"List", "Choice"} or parts[0] not in processors)
        and (purpose != "Choice" or parts[0] != "InformationRegister")
        and (purpose != "Record" or parts[0] == "InformationRegister"),
        "Invalid owner/purpose combination",
    )
    dynamic = purpose in {"List", "Choice"}
    main_name = "Список" if dynamic else "Запись" if purpose == "Record" else "Объект"
    main_type = "DynamicList" if dynamic else FORM_OBJECT_TYPES[parts[0]] + "." + parts[1]
    config, owner, owner_path, original = objects.read_object(snapshot, target)
    editor.require(
        editor.node_name(owner) == parts[1] and editor.prop(owner, "ObjectBelonging") in {"", "Native", "Adopted"},
        "Invalid form owner",
    )
    base = objects.exact_base_owner(snapshot, owner, owner_path)
    editor.require(owner.getparent().get("version") == "2.17", "Unsupported form owner version")
    name = parameters["name"]
    if base is not None:
        editor.require(
            not any(
                (editor.prop(child, "Name") or child.text or "").casefold() == name.casefold()
                for child in base.findall("m:ChildObjects/*", editor.NS)
            ),
            "New form conflicts with base child",
            3,
        )
    logical = target + ".Form." + name
    path = form_path(logical)
    descriptor_path, _, _, _ = editor.layout(path)
    module_path = path[:-4] + "/Module.bsl"
    registrations = owner.findall("m:ChildObjects", editor.NS)
    editor.require(len(registrations) == 1, "Missing or ambiguous owner ChildObjects")
    registrations = registrations[0]
    registered = borrow._linked(registrations, "Form", name)
    existing = snapshot.read("target", descriptor_path, optional=True)
    editor.require(registered == (existing is not None), "Form registration/file mismatch", 3)
    occupied = borrow._uuid_inventory(snapshot, external_name=parts[1] if owner is config else None)
    identity = editor.allocate_uuid(editor.identity(config), "Form", logical, "object", {} if existing else occupied)
    nsmap = dict(owner.getparent().nsmap)
    nsmap.update(
        {
            None: editor.MD,
            "v8": editor.V8,
            "app": "http://v8.1c.ru/8.2/managed-application/core",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        }
    )
    descriptor = etree.Element(f"{{{editor.MD}}}MetaDataObject", nsmap=nsmap, version="2.17")
    form = etree.SubElement(descriptor, f"{{{editor.MD}}}Form", uuid=identity)
    properties = etree.SubElement(form, f"{{{editor.MD}}}Properties")
    if editor.prop(config, "ConfigurationExtensionPurpose"):
        etree.SubElement(properties, f"{{{editor.MD}}}ObjectBelonging").text = "Native"
    etree.SubElement(properties, f"{{{editor.MD}}}Name").text = name
    synonym = etree.SubElement(properties, f"{{{editor.MD}}}Synonym")
    item = etree.SubElement(synonym, f"{{{editor.V8}}}item")
    etree.SubElement(item, f"{{{editor.V8}}}lang").text = "ru"
    etree.SubElement(item, f"{{{editor.V8}}}content").text = parameters["synonym"]
    etree.SubElement(properties, f"{{{editor.MD}}}Comment")
    etree.SubElement(properties, f"{{{editor.MD}}}FormType").text = "Managed"
    etree.SubElement(properties, f"{{{editor.MD}}}IncludeHelpInContents").text = "false"
    purposes = etree.SubElement(properties, f"{{{editor.MD}}}UsePurposes")
    for value in ("PlatformApplication", "MobilePlatformApplication"):
        etree.SubElement(
            purposes, f"{{{editor.V8}}}Value", {f"{{{nsmap['xsi']}}}type": "app:ApplicationUsePurpose"}
        ).text = value

    def serialize(tree):
        etree.indent(tree, space="\t")
        return b'<?xml version="1.0" encoding="UTF-8"?>\n' + etree.tostring(tree, encoding="UTF-8") + b"\n"

    if existing is not None:
        editor.require(
            editor.signature(editor.xml_read(existing, descriptor.tag)) == editor.signature(descriptor),
            "Existing form descriptor differs",
            3,
        )
        view = copy.copy(snapshot)
        view.load_form(path)
        mains = view.tree.findall('f:Attributes/f:Attribute[f:MainAttribute="true"]', editor.NS)
        editor.require(
            len(mains) == 1
            and mains[0].get("name") == main_name
            and mains[0].findtext("f:Type/v8:Type", namespaces=editor.NS) == "cfg:" + main_type,
            "Existing form main attribute differs",
            3,
        )
        types = mains[0].findall("f:Type/v8:Type", editor.NS)
        editor.require(
            len(types) == 1
            and types[0].nsmap.get("cfg") == borrow.CFG
            and not mains[0].findall("f:Type/v8:TypeSet", editor.NS),
            "Invalid existing main attribute type",
            3,
        )
        if dynamic:
            settings = mains[0].findall("f:Settings", editor.NS)
            editor.require(
                len(settings) == 1
                and settings[0].get(f"{{{nsmap['xsi']}}}type") == "DynamicList"
                and settings[0].nsmap.get(None) == editor.FORM,
                "Existing dynamic list settings differ",
                3,
            )
            tables = settings[0].findall("f:MainTable", editor.NS)
            queries = settings[0].findall("f:CustomQuery", editor.NS)
            editor.require(
                len(tables) == 1
                and tables[0].text == target
                and not tables[0].attrib
                and len(tables[0]) == 0
                and len(queries) <= 1
                and all(node.text == "false" and not node.attrib and len(node) == 0 for node in queries),
                "Existing dynamic list settings differ",
                3,
            )
    else:
        editor.require(
            not snapshot.list_directory("target", path.rsplit("/Ext/", 1)[0], optional=True),
            "Unregistered form artifacts already exist",
            3,
        )
        nsmap.update({None: editor.FORM, "cfg": borrow.CFG, "xs": editor.XS})
        body = etree.Element(f"{{{editor.FORM}}}Form", nsmap=nsmap, version="2.17")
        bar = etree.SubElement(body, f"{{{editor.FORM}}}AutoCommandBar", name="ФормаКоманднаяПанель", id="-1")
        etree.SubElement(bar, f"{{{editor.FORM}}}Autofill").text = "true"
        etree.SubElement(body, f"{{{editor.FORM}}}ChildItems")
        attributes = etree.SubElement(body, f"{{{editor.FORM}}}Attributes")
        attribute = etree.SubElement(
            attributes, f"{{{editor.FORM}}}Attribute", name=main_name, id=str(editor.allocate_form_ids(body, 1)[0])
        )
        typed = etree.SubElement(attribute, f"{{{editor.FORM}}}Type")
        etree.SubElement(typed, f"{{{editor.V8}}}Type").text = "cfg:" + main_type
        etree.SubElement(attribute, f"{{{editor.FORM}}}MainAttribute").text = "true"
        if dynamic:
            settings = etree.SubElement(
                attribute, f"{{{editor.FORM}}}Settings", {f"{{{nsmap['xsi']}}}type": "DynamicList"}
            )
            etree.SubElement(settings, f"{{{editor.FORM}}}MainTable").text = target
        else:
            etree.SubElement(attribute, f"{{{editor.FORM}}}SavedData").text = "true"
        registration = etree.Element(f"{{{editor.MD}}}Form")
        registration.text = name
        following = next(
            (node for node in registrations if node.tag in {f"{{{editor.MD}}}Template", f"{{{editor.MD}}}Command"}),
            None,
        )
        if following is not None:
            registrations.insert(registrations.index(following), registration)
        else:
            registrations.append(registration)
        snapshot.stage(descriptor_path, serialize(descriptor))
        snapshot.stage(path, serialize(body))
        # No invented handler or generated business logic. Existing modules are
        # never rewritten, and the new form has no event referencing this file.
        snapshot.stage(module_path, b"")
    default_key = (
        ("DefaultForm" if parts[0] in processors else "DefaultObjectForm")
        if purpose == "Object"
        else "Default" + purpose + "Form"
    )
    defaults = owner.findall(f"m:Properties/m:{default_key}", editor.NS)
    if not defaults and base is not None:
        inherited = base.findall(f"m:Properties/m:{default_key}", editor.NS)
        editor.require(len(inherited) <= 1, "Ambiguous base default form property", 4)
        if inherited and (parameters["setDefault"] or not inherited[0].text):
            property_node = copy.deepcopy(inherited[0])
            owner.find("m:Properties", editor.NS).append(property_node)
            defaults = [property_node]
    editor.require(
        len(defaults) <= 1 and (bool(defaults) or not parameters["setDefault"]),
        "Missing or ambiguous default form property",
    )
    if defaults and (parameters["setDefault"] or not defaults[0].text):
        defaults[0].text = logical
    snapshot.stage(owner_path, editor.serialize_like(owner.getparent(), original))


def remove_form(snapshot, operation):
    """Remove one registered form after checking the remaining snapshot."""
    from . import metadata as editor
    from . import metadata_object_ops as objects

    logical = operation["target"]
    body_path = form_path(logical)
    descriptor_path, owner_path, config_path, kind = editor.layout(body_path)
    descriptor_kind = "CommonForm" if kind == "CommonForm" else "Form"
    owner_kind = logical.split(".")[0] if kind == "external" else "Configuration" if kind == "CommonForm" else kind
    original = snapshot.read("target", owner_path)
    owner = editor.metadata(original, owner_kind)
    editor.identity(owner)
    if kind != "CommonForm":
        editor.require(editor.node_name(owner) == logical.split(".")[1], "Owner name mismatch", 3)
    if kind not in {"external", "CommonForm"}:
        config = editor.metadata(snapshot.read("target", config_path), "Configuration")
        editor.require_registration(config, kind, editor.node_name(owner))
    name = logical.split(".")[-1]
    registrations = owner.findall("m:ChildObjects", editor.NS)
    editor.require(len(registrations) == 1, "Missing or ambiguous owner registrations", 3)
    matches = [
        node
        for node in registrations[0]
        if node.tag == f"{{{editor.MD}}}{descriptor_kind}" and (node.text or "").casefold() == name.casefold()
    ]
    editor.require(
        len(matches) <= 1
        and all(
            node.text == name and not node.attrib and not len(node) and not (node.tail or "").strip()
            for node in matches
        ),
        "Ambiguous form registration",
        3,
    )
    descriptor_data = snapshot.read("target", descriptor_path, optional=True)
    directory = body_path.rsplit("/Ext/", 1)[0]
    files = {}

    def inventory(path):
        for child, entry_kind in (snapshot.list_directory("target", path, optional=True) or {}).items():
            candidate = path + "/" + child
            editor.require(child.casefold() != "templates", "Template removal is outside the contract", 3)
            if entry_kind == "directory":
                inventory(candidate)
            else:
                files[candidate] = snapshot.read("target", candidate)

    inventory(directory)
    editor.require(bool(matches) == (descriptor_data is not None), "Form registration/file mismatch", 3)
    editor.require(bool(matches) or not files, "Orphan form files", 3)
    removed_ids = set()
    if descriptor_data is not None:
        descriptor = editor.metadata(descriptor_data, descriptor_kind)
        editor.require(editor.node_name(descriptor) == name, "Form descriptor name mismatch", 3)
        editor.require(
            editor.prop(descriptor, "ObjectBelonging") in {"", "Native", "Adopted"}, "Unknown form belonging", 3
        )
        form_type = editor.prop(descriptor, "FormType")
        editor.require(form_type in {"Managed", "Ordinary"}, "Unknown form type", 3)
        expected_body = body_path if form_type == "Managed" else body_path[:-3] + "bin"
        editor.require(expected_body in files, "Registered form body is missing", 3)
        removed_ids.add(editor.identity(descriptor))
        files[descriptor_path] = descriptor_data
        registrations[0].remove(matches[0])
        defaults = owner.findall("m:Properties/*", editor.NS)
        for default in defaults:
            if etree.QName(default).localname.startswith("Default") and etree.QName(default).localname.endswith("Form"):
                if (default.text or "").casefold() == logical.casefold():
                    editor.require(
                        default.text == logical and not default.attrib and not len(default),
                        "Ambiguous default form reference",
                        3,
                    )
                    default.text = None
    # Only files in the removed form subtree are excluded from dependencies.
    reviewed = objects.reviewed_dependency_map(snapshot, operation["parameters"].get("reviewedDependencies", ()))
    documents, _ = objects.read_dependency_documents(
        snapshot, owner, owner_path, excluded_files=set(files), reviewed_dependencies=reviewed, owner_help=True
    )
    objects.check_or_rewrite_references(
        snapshot, documents, owner, owner_path, original, False, name, logical, None, {}, removed_ids=removed_ids
    )
    if descriptor_data is not None:
        snapshot.stage(owner_path, editor.serialize_like(owner.getparent(), original))
        for path in files:
            snapshot.stage(path, None)


def compile_form(snapshot, operation):
    return _merge_form(snapshot, operation)


def edit_form(snapshot, operation):
    return _merge_form(snapshot, operation, adding=True)


def _merge_form(snapshot, operation, *, adding=False):
    """Merge explicitly described form members without replacing unrelated XML."""
    from . import metadata as editor
    from . import metadata_form_compile, metadata_form_schema

    definition = metadata_form_schema.normalize_parameters(
        "form.edit" if adding else "form.compile", operation["parameters"]
    )["definition"]
    placement = {}
    if adding:
        placement = {key: definition.pop(key) for key in ("into", "after", "before") if key in definition}
    path = form_path(operation["target"])
    descriptor, _, _, kind = editor.layout(path)
    form_kind = "CommonForm" if kind == "CommonForm" else "Form"
    form_node = editor.metadata(snapshot.read("target", descriptor), form_kind)
    base_root = None
    if editor.prop(form_node, "ObjectBelonging") == "Adopted":
        bases = [
            alias
            for (alias, read_path), data in snapshot.blobs.items()
            if alias != "target"
            and read_path == descriptor
            and data is not None
            and editor.identity(editor.metadata(data, form_kind))
            == editor.prop(form_node, "ExtendedConfigurationObject").lower()
        ]
        if len(bases) != 1:
            raise editor.PublicRejected(
                "Exact base form context required, include form borrow with baseRoot", [operation["target"]], 3
            )
        base_root = snapshot.roots[bases[0]]
    view = copy.copy(snapshot)
    view.load_form(path, base_root)
    if kind == "external":
        editor.require(
            etree.QName(view.owner).localname == operation["target"].split(".")[0], "External object kind mismatch"
        )
    render = metadata_form_compile.render_edit_form if adding else metadata_form_compile.render_form
    generated = editor.xml_read(render(definition), f"{{{editor.FORM}}}Form")
    before_signature = editor.signature(view.tree)
    for tree in (view.tree, generated):
        for container in tree.iter():
            if etree.QName(container).localname in {
                "ChildItems",
                "Attributes",
                "Columns",
                "AdditionalColumns",
                "Parameters",
                "Commands",
            }:
                names = [
                    (
                        ("table:" + child.get("table", ""))
                        if child.tag == f"{{{editor.FORM}}}AdditionalColumns"
                        else child.get("name", "")
                    ).casefold()
                    for child in container
                ]
                editor.require(all(name != "table:" for name in names), "Unnamed additional columns", 3)
                editor.require(all(names) and len(names) == len(set(names)), "Duplicate/unnamed form members", 3)
    working_ids = [node.get("id") for node in editor.working_nodes(view.tree) if node.get("id") is not None]
    editor.require(len(working_ids) == len(set(working_ids)), "Duplicate working form IDs", 3)

    def main_identity():
        mains = [
            node
            for node in view.tree.findall("f:Attributes/f:Attribute", editor.NS)
            if node.findtext("f:MainAttribute", namespaces=editor.NS) == "true"
        ]
        editor.require(len(mains) <= 1, "Ambiguous main form attribute", 3)
        return [
            (
                tuple(sorted(node.attrib.items())),
                tuple(
                    editor.signature(child)
                    for child in node
                    if etree.QName(child).localname in {"Type", "MainAttribute"}
                ),
            )
            for node in mains
        ]

    before_main = main_identity()
    before_base = [editor.signature(node) for node in view.tree.findall("f:BaseForm", editor.NS)]
    existing_nodes = set(view.tree.iter())

    def one(parent, tag):
        nodes = parent.findall(f"{{{editor.FORM}}}{tag}")
        editor.require(len(nodes) <= 1, "Ambiguous form section/property: " + tag, 3)
        return nodes[0] if nodes else None

    def section(parent, tag):
        found = one(parent, tag)
        return found if found is not None else etree.SubElement(parent, f"{{{editor.FORM}}}{tag}")

    def clone(node):
        # Retain QName namespace bindings even when the destination lacks them.
        return etree.fromstring(etree.tostring(node))

    def set_property(dest, source, tag):
        old, new = one(dest, tag), one(source, tag)
        if old is not None and new is not None and editor.signature(old) == editor.signature(new):
            return
        if old is not None:
            editor.require(
                not any(node.get("id") is not None for node in old.iter()),
                "Cannot replace identity-bearing property: " + tag,
                3,
            )
        if tag in {"Title", "InputHint"} and old is not None:
            # Only the Russian presentation is supplied by this description.
            editor.require(
                all(child.tag == f"{{{editor.V8}}}item" for child in old), "Unknown multilingual structure", 3
            )
            russian = [child for child in old if child.findtext(f"{{{editor.V8}}}lang") == "ru"]
            editor.require(len(russian) <= 1, "Ambiguous Russian presentation", 3)
            if russian:
                item = russian[0]
                editor.require(
                    not item.attrib
                    and not (item.text or "").strip()
                    and not (item.tail or "").strip()
                    and [child.tag for child in item] == [f"{{{editor.V8}}}lang", f"{{{editor.V8}}}content"]
                    and all(not child.attrib and not len(child) and not (child.tail or "").strip() for child in item),
                    "Unknown multilingual item structure",
                    3,
                )
            if new is not None:
                replacement = new.find(f"{{{editor.V8}}}item")
                editor.require(replacement is not None, "Missing Russian presentation", 3)
                if russian:
                    old.replace(russian[0], clone(replacement))
                else:
                    old.append(clone(replacement))
            elif russian:
                old.remove(russian[0])
            return
        if old is not None and (len(old) or tag == "Type" or new is None and tag in {"ChoiceList", "CommandSet"}):
            if tag == "Type" or new is None and tag in {"ChoiceList", "CommandSet"}:
                example = (
                    {"attributes": [{"name": "Образец", "type": "string(20)|decimal(15,2)|dateTime|boolean"}]}
                    if tag == "Type"
                    else (
                        {"excludedCommands": ["Form.StandardCommand.Close"]}
                        if tag == "CommandSet"
                        else {
                            "elements": [
                                {
                                    "input": "Выбор",
                                    "choices": [
                                        {"title": "Строка", "value": "", "type": "string"},
                                        {"title": "Число", "value": 0, "type": "number"},
                                        {"title": "Флаг", "value": False, "type": "boolean"},
                                    ],
                                }
                            ]
                        }
                    )
                )
                sample = editor.xml_read(metadata_form_compile.render_form(example), f"{{{editor.FORM}}}Form").find(
                    ".//f:" + tag, editor.NS
                )

                def known_shape(node, reference):
                    return (
                        reference is not None
                        and node.tag == reference.tag
                        and node.attrib == reference.attrib
                        and all(any(known_shape(child, expected) for expected in reference) for child in node)
                    )

                editor.require(known_shape(old, sample), "Unknown structure in property: " + tag, 3)
            else:
                editor.require(new is not None and old.tag == new.tag, "Cannot clear structured property: " + tag, 3)
                assert new is not None
                allowed = {node.tag for node in new.iter()}
                editor.require(
                    all(node.tag in allowed for node in old.iter()), "Unknown structure in property: " + tag, 3
                )
        if new is None:
            if old is not None:
                dest.remove(old)
        elif old is not None:
            dest.replace(old, clone(new))
        else:
            added = clone(new)
            if tag == "Title" and dest.tag == f"{{{editor.FORM}}}LabelDecoration":
                added.set("formatted", str(dest.findtext("f:Hyperlink", namespaces=editor.NS) == "true").lower())
            dest.append(added)

    aliases = {
        "path": "DataPath",
        "hidden": "Visible",
        "disabled": "Enabled",
        "markIncomplete": "AutoMarkIncomplete",
        "main": "MainAttribute",
        "key": "KeyParameter",
        "src": "Picture",
        "command": "CommandName",
        "stdCommand": "CommandName",
        "choices": "ChoiceList",
    }

    def merge_slots(target, incoming, tag):
        def key(node):
            editor.require(
                node.tag == f"{{{editor.FORM}}}{tag}"
                and not len(node)
                and set(node.attrib) <= ({"name", "callType"} if tag == "Event" else {"callType"})
                and node.get("callType") in {None, "Before", "After", "Override"},
                "Unsupported handler slot structure",
                3,
            )
            editor.require(tag != "Event" or node.get("name"), "Unnamed event slot", 3)
            return ((node.get("name") or "").casefold(), node.get("callType"))

        old = {key(node): node for node in target if node.tag == f"{{{editor.FORM}}}{tag}"}
        editor.require(
            len(old) == len([node for node in target if node.tag == f"{{{editor.FORM}}}{tag}"]),
            "Ambiguous existing handler slot",
            3,
        )
        requested = set()
        for node in incoming:
            slot = key(node)
            editor.require(slot not in requested, "Duplicate requested handler slot", 3)
            requested.add(slot)
            if slot in old:
                editor.require(
                    old[slot].attrib == node.attrib and old[slot].text == node.text, "Conflicting handler slot", 3
                )
            else:
                target.append(clone(node))

    def merge_events(dest, source):
        incoming = one(source, "Events")
        if incoming is None:
            return
        target = one(dest, "Events")
        if target is None and dest.tag == f"{{{editor.FORM}}}Form":
            # Designer keeps form events right after AutoCommandBar, before the
            # element tree, tail sections and BaseForm (Номенклатура.ФормаЭлемента).
            later = [
                child
                for child in dest
                if isinstance(child.tag, str)
                and etree.QName(child).localname in {"ChildItems", "BaseForm"} | FORM_TAIL_SECTIONS
            ]
            target = etree.Element(f"{{{editor.FORM}}}Events")
            if later:
                later[0].addprevious(target)
            else:
                dest.append(target)
        elif target is None:
            target = section(dest, "Events")
        editor.require(all(child.tag == f"{{{editor.FORM}}}Event" for child in target), "Unknown Events structure", 3)
        if adding:
            merge_slots(target, incoming, "Event")
            return
        for event in incoming:
            matches = [
                child
                for child in target
                if (child.get("name") or "").casefold() == (event.get("name") or "").casefold()
            ]
            editor.require(len(matches) <= 1, "Ambiguous form event", 3)
            if matches:
                editor.require(
                    matches[0].get("name") == event.get("name")
                    and not len(matches[0])
                    and set(matches[0].attrib) == {"name"},
                    "Unsupported event structure",
                    3,
                )
                target.replace(matches[0], clone(event))
            else:
                target.append(clone(event))

    def merge_members(dest, source, entries, container_tag):
        if not entries:
            return
        incoming = one(source, container_tag)
        editor.require(
            incoming is not None and len(incoming) == len(entries), "Generated members do not match description", 3
        )
        assert incoming is not None
        target = section(dest, container_tag)
        ordered = []
        for spec, node in zip(entries, incoming, strict=False):
            name = node.get("name")
            editor.require(name is not None, "Unnamed generated member", 3)
            matches = [child for child in target if (child.get("name") or "").casefold() == name.casefold()]
            if container_tag == "ChildItems":
                # A description names the destination explicitly. Reuse the
                # original node rather than cloning its presentation and IDs.
                existing = editor.named(view.tree).get(name.casefold())
                if existing is not None:
                    editor.require(
                        existing.getparent() is not None and existing.getparent().tag == f"{{{editor.FORM}}}ChildItems",
                        "Cannot relocate a companion as a form element",
                        3,
                    )
                    editor.require(
                        existing is not dest and existing not in dest.iterancestors(),
                        "Cyclic form element placement",
                        3,
                    )
                    matches = [existing]
            editor.require(len(matches) <= 1, "Ambiguous existing form member: " + name, 3)
            if matches:
                current = matches[0]
                editor.require(
                    current.tag == node.tag and current.get("name") == name,
                    "Form member kind/name conflict: " + name,
                    3,
                )
                if current.getparent() is not target:
                    editor.require(not adding, "Existing element belongs to another container", 3)
                    target.append(current)
                previous = copy.deepcopy(current)
                merge_member(current, node, spec)
                reduced = copy.deepcopy(current)
                if adding:
                    # Permit new handler slots on the member and its existing descendants.
                    previous_nodes = {
                        (part.tag, part.get("id"), part.get("name")): part
                        for part in previous.iter()
                        if part.get("id") is not None
                    }
                    for part in list(reduced.iter()):
                        old_part = previous_nodes.get((part.tag, part.get("id"), part.get("name")))
                        if old_part is None:
                            continue
                        for old_parent, new_parent, tag in (
                            (old_part, part, "Action"),
                            (one(old_part, "Events"), one(part, "Events"), "Event"),
                        ):
                            if new_parent is None:
                                continue
                            old_slots = (
                                {
                                    (child.get("name"), child.get("callType"))
                                    for child in old_parent
                                    if child.tag == f"{{{editor.FORM}}}{tag}"
                                }
                                if old_parent is not None
                                else set()
                            )
                            for child in list(new_parent):
                                if (
                                    child.tag == f"{{{editor.FORM}}}{tag}"
                                    and (child.get("name"), child.get("callType")) not in old_slots
                                ):
                                    new_parent.remove(child)
                            if old_parent is None and tag == "Event":
                                part.remove(new_parent)
                editor.require(
                    not adding or editor.signature(reduced) == editor.signature(previous),
                    "Existing form member conflicts with addition: " + name,
                    3,
                )
            else:
                current = clone(node)
                if container_tag == "ChildItems":
                    # Build just the new container and its companions first;
                    # descendants may be existing elements to move into it.
                    for children in list(current.iter(f"{{{editor.FORM}}}ChildItems")):
                        children.getparent().remove(children)
                    editor.check_new_element_names(
                        view.tree,
                        [
                            part.get("name")
                            for part in current.iter()
                            if part.get("id") is not None and part.get("name")
                        ],
                    )
                # Reserve only this new subtree; attached predecessors and BaseForm
                # are already accounted for by the shared allocator.
                new_nodes = [part for part in current.iter() if part.get("id") is not None]
                if new_nodes:
                    for part, identifier in zip(
                        new_nodes, editor.allocate_form_ids(view.tree, len(new_nodes)), strict=False
                    ):
                        part.set("id", str(identifier))
                target.append(current)
                if container_tag == "ChildItems":
                    merge_member(current, node, spec)
            ordered.append(current)
        if container_tag == "ChildItems" and not (adding and anchor is not None and dest is element_parent):
            # Reorder only explicitly named slots; leave other siblings in place.
            selected = set(ordered)
            replacements = iter(ordered)
            reordered = [next(replacements) if child in selected else child for child in target]
            editor.require(not adding or list(target) == reordered, "Existing element order conflicts with addition", 3)
            target[:] = reordered

    def merge_member(dest, source, spec):
        editor.require(set(dest.attrib) <= {"id", "name"}, "Unknown member identity attributes", 3)
        local = etree.QName(source).localname
        element_kind = (
            metadata_form_compile.element_kind(spec)
            if local not in {"Attribute", "Column", "Parameter", "Command"}
            else None
        )
        for key in spec:
            if (
                key in {"name", "children", "columns", "commandBarButtons", "on", "handlers"}
                or adding
                and key in {"action", "actions", "callType"}
            ):
                continue
            if key == element_kind and key != "group":
                continue
            tag = aliases.get(key, key[0].upper() + key[1:])
            if key == "height" and local == "Table":
                tag = "HeightInTableRows"
            if key == "group" and local == "UsualGroup":
                old_behavior, new_behavior = one(dest, "Behavior"), one(source, "Behavior")
                # A normal orientation already means Usual; keep its explicit
                # spelling rather than deleting an unchanged source property.
                if not (new_behavior is None and old_behavior is not None and old_behavior.text == "Usual"):
                    set_property(dest, source, "Behavior")
            set_property(dest, source, tag)
        if local == "LabelDecoration" and "hyperlink" in spec:
            title = one(dest, "Title")
            if title is not None:
                title.set("formatted", str(spec["hyperlink"]).lower())
        if "on" in spec:
            merge_events(dest, source)
        if adding and local == "Command" and ("action" in spec or "actions" in spec):
            merge_slots(dest, source.findall("f:Action", editor.NS), "Action")
        if "handlers" in spec:
            editor.require(
                "on" in spec
                and set(spec["handlers"])
                <= {event if isinstance(event, str) else event["event"] for event in spec["on"]},
                "Handlers require explicitly listed events",
                3,
            )
        if "children" in spec:
            merge_members(dest, source, spec["children"], "ChildItems")
        if "columns" in spec:
            merge_members(dest, source, spec["columns"], "Columns" if local == "Attribute" else "ChildItems")
        if spec.get("commandBarButtons"):
            source_bar = one(source, "AutoCommandBar")
            target_bar = one(dest, "AutoCommandBar")
            editor.require(source_bar is not None and target_bar is not None, "Missing table command bar", 3)
            merge_members(target_bar, source_bar, spec["commandBarButtons"], "ChildItems")

    # Generator defaults (notably AutoCommandBar) are deliberately not merged.
    editor.named(view.tree)
    editor.named(generated)
    if adding:
        for events in generated.iter(f"{{{editor.FORM}}}Events"):
            merge_slots(events, [], "Event")
        for command in generated.findall("f:Commands/f:Command", editor.NS):
            merge_slots(command, [], "Action")
    element_parent = view.tree
    anchor = None
    if adding and placement:
        nodes = editor.named(view.tree)
        if "into" in placement:
            element_parent = nodes.get(placement["into"].casefold())
            editor.require(
                element_parent is not None and element_parent.get("name") == placement["into"],
                "Exact target container not found",
                3,
            )
            assert element_parent is not None
            editor.require(
                etree.QName(element_parent).localname
                in {"UsualGroup", "Page", "Pages", "Table", "CommandBar", "AutoCommandBar", "Popup"},
                "Element cannot contain ChildItems",
                3,
            )
        for side in ("after", "before"):
            if side not in placement:
                continue
            anchor = nodes.get(placement[side].casefold())
            editor.require(
                anchor is not None
                and anchor.get("name") == placement[side]
                and anchor.getparent().tag == f"{{{editor.FORM}}}ChildItems",
                "Exact sibling anchor not found",
                3,
            )
            assert anchor is not None
            if "into" not in placement:
                element_parent = anchor.getparent().getparent()
            editor.require(anchor.getparent().getparent() is element_parent, "Anchor is not in the target container", 3)
    existing_elements = set(editor.working_nodes(view.tree))
    if "title" in definition or "title" in definition.get("properties", {}):
        set_property(view.tree, generated, "Title")
    for key in definition.get("properties", {}):
        if key != "title":
            set_property(view.tree, generated, key[0].upper() + key[1:])
    if "excludedCommands" in definition:
        set_property(view.tree, generated, "CommandSet")
    if "events" in definition or "formEvents" in definition:
        merge_events(view.tree, generated)
    for key, tag in (
        ("elements", "ChildItems"),
        ("attributes", "Attributes"),
        ("parameters", "Parameters"),
        ("commands", "Commands"),
    ):
        merge_members(element_parent if key == "elements" else view.tree, generated, definition.get(key, []), tag)
    if adding:
        nodes = editor.named(view.tree)
        requested_events = set()
        for event in definition.get("elementEvents", []):
            destination = nodes.get(event["element"].casefold())
            editor.require(
                destination is not None and destination.get("name") == event["element"],
                "Exact event element not found",
                3,
            )
            slot = (event["element"], event["name"].casefold(), event.get("callType"))
            editor.require(slot not in requested_events, "Duplicate requested element event slot", 3)
            requested_events.add(slot)
            event_source = editor.xml_read(
                metadata_form_compile.render_edit_form(
                    {"formEvents": [{key: value for key, value in event.items() if key != "element"}]}
                ),
                f"{{{editor.FORM}}}Form",
            )
            merge_events(destination, event_source)
    if adding and anchor is not None and definition.get("elements"):
        container = anchor.getparent()
        nodes = editor.named(view.tree)
        # With before, walk the list backwards so it keeps its order ahead of the anchor.
        before = "before" in placement
        step = -1 if before else 1
        for description in definition["elements"][::step]:
            name = description.get("name") or description[metadata_form_compile.element_kind(description)]
            member = nodes[name.casefold()]
            editor.require(member is not anchor, "Element cannot be placed next to itself", 3)
            if member in existing_elements:
                editor.require(
                    container.index(member) == container.index(anchor) + step,
                    "Existing element placement conflicts with addition",
                    3,
                )
            else:
                container.remove(member)
                container.insert(container.index(anchor) + (0 if before else 1), member)
            anchor = member
    if adding:
        _check_new_placement(view.tree, existing_nodes)
        _indent_new_nodes(view.tree, existing_nodes)
    after_main = main_identity()
    if not before_main and after_main and base_root is not None and form_kind == "Form":
        # Designer native projection (form.borrow nativeProjection) stores no main
        # attribute; the extension adds it, as in Catalog.Номенклатура.ФормаЭлемента.
        base = view.tree.find("f:BaseForm", editor.NS)
        owner_kind, owner_name = operation["target"].split(".")[:2]
        main = [
            node
            for node in view.tree.findall("f:Attributes/f:Attribute", editor.NS)
            if node.findtext("f:MainAttribute", namespaces=editor.NS) == "true"
        ][0]
        editor.require(
            base is not None
            and not _base_main_attributes(base)
            and [value.text for value in main.iter(f"{{{editor.V8}}}Type")] == [f"cfg:{owner_kind}Object.{owner_name}"],
            "Main form attribute identity/type must be preserved",
            3,
        )
    else:
        editor.require(before_main == after_main, "Main form attribute identity/type must be preserved", 3)
    editor.require(
        before_base == [editor.signature(node) for node in view.tree.findall("f:BaseForm", editor.NS)],
        "BaseForm changed",
        4,
    )
    if editor.signature(view.tree) != before_signature:
        snapshot.stage(path, editor.serialize_like(view.tree, snapshot.read("target", path)))


def _check_new_placement(tree, existing_nodes):
    """New items obey BslEdit canContain for the container they land in."""
    from . import metadata as editor

    for items in tree.iter(f"{{{editor.FORM}}}ChildItems"):
        owner = items.getparent()
        if owner.tag == f"{{{editor.FORM}}}BaseForm":
            continue
        container_kind = "Form" if owner is tree else etree.QName(owner).localname
        for child in items:
            if child in existing_nodes or not isinstance(child.tag, str):
                continue
            kind = etree.QName(child).localname
            if not can_contain(container_kind, kind):
                raise editor.PublicRejected("Container cannot hold this kind", [container_kind, kind], 2)


def _indent_new_nodes(tree, existing_nodes):
    """Lay out nodes added by form.edit like their siblings; old lines keep their bytes."""
    tops = [
        node
        for node in tree.iter()
        if isinstance(node.tag, str) and node not in existing_nodes and node.getparent() in existing_nodes
    ]
    compact = set()
    for parent in dict.fromkeys(node.getparent() for node in tops):
        _check_layout(parent)
        old = [child for child in parent if child in existing_nodes]
        if old and not parent.text and not any(child.tail for child in old):
            # A compact (unindented) container stays compact.
            compact.add(parent)
            continue
        outer = _ws_before(parent) if parent.getparent() is not None else "\n"
        inner = outer + "\t"
        parent.text = inner
        for child in parent:
            child.tail = inner if child.getnext() is not None else outer
    for node in tops:
        if node.getparent() not in compact:
            _indent_new(node, _ws_before(node))


def add_input(snapshot, operation):
    from . import metadata as editor

    path = form_path(operation["target"])
    descriptor, _, _, kind = editor.layout(path)
    form_kind = "CommonForm" if kind == "CommonForm" else "Form"
    form_node = editor.metadata(snapshot.read("target", descriptor), form_kind)
    base_root = None
    if editor.prop(form_node, "ObjectBelonging") == "Adopted":
        bases = [
            alias
            for (alias, read_path), data in snapshot.blobs.items()
            if alias != "target"
            and read_path == descriptor
            and data is not None
            and editor.identity(editor.metadata(data, form_kind))
            == editor.prop(form_node, "ExtendedConfigurationObject").lower()
        ]
        if len(bases) != 1:
            raise editor.PublicRejected(
                "Exact base form context required, include form borrow with baseRoot", [operation["target"]], 3
            )
        base_root = snapshot.roots[bases[0]]
    view = copy.copy(snapshot)
    view.load_form(path, base_root)
    if kind == "external":
        editor.require(
            etree.QName(view.owner).localname == operation["target"].split(".")[0], "External object kind mismatch"
        )
    parameters = operation["parameters"]
    attribute_path = parameters["attribute"]
    if "." in attribute_path:
        main_name, name = attribute_path.split(".")
        mains = [
            node
            for node in view.tree.findall("f:Attributes/f:Attribute", editor.NS)
            if node.findtext("f:MainAttribute", namespaces=editor.NS) == "true"
        ]
        editor.require(
            len(mains) == 1 and mains[0].get("name") == main_name, "Object main attribute missing or ambiguous"
        )
        main_types = mains[0].findall("f:Type/v8:Type", editor.NS)
        editor.require(
            len(main_types) == 1 and not mains[0].findall("f:Type/v8:TypeSet", editor.NS), "Invalid main attribute type"
        )
        prefix, _, value = (main_types[0].text or "").partition(":")
        owner_kind = etree.QName(view.owner).localname
        editor.require(
            main_types[0].nsmap.get(prefix) == borrow.CFG
            and value == owner_kind + "Object." + editor.node_name(view.owner),
            "Main attribute owner type mismatch",
        )
        attribute = borrow._member(
            view.owner, "Attribute", name, optional=owner_kind == "Catalog" and name in {"Code", "Description"}
        )
        if attribute is None and owner_kind == "Catalog" and name in {"Code", "Description"}:
            length = editor.prop(view.owner, name + "Length")
            editor.require(
                length.isdecimal() and 0 < int(length) <= 2147483647, "Standard field is disabled or malformed"
            )
            code_type = editor.prop(view.owner, "CodeType")
            editor.require(name == "Description" or code_type in {"String", "Number"}, "Unsupported Code type")
            scalar = "decimal" if name == "Code" and code_type == "Number" else "string"
        elif attribute is None:
            raise editor.Rejected("Object attribute missing", 4)
        else:
            typed = attribute.find("m:Properties/m:Type", editor.NS)
            values = typed.findall(f"{{{editor.V8}}}Type") if typed is not None else []
            editor.require(
                len(values) == 1 and typed is not None and not typed.findall(f"{{{editor.V8}}}TypeSet"),
                "Object attribute must have one scalar type",
            )
            prefix, _, scalar = (values[0].text or "").partition(":")
            editor.require(
                values[0].nsmap.get(prefix) == editor.XS and scalar in {"string", "decimal", "boolean", "dateTime"},
                "Object attribute must have one scalar type",
            )
        view.attributes[attribute_path] = scalar
    nodes = editor.named(view.tree)
    existing = nodes.get(parameters["name"].casefold())
    if existing is not None:
        editor.require(existing.get("name") == parameters["name"], "Case-ambiguous field name", 3)
        base = view.tree.find("f:BaseForm", editor.NS)
        editor.require(
            base is None or parameters["name"].casefold() not in editor.named(base), "Base field name is reserved", 3
        )
        editor.element_check(view, parameters, check_position="after" in parameters)
        return
    scalar, container = editor.placement(view, parameters)
    names = [parameters["name"], *(parameters["name"] + suffix for suffix in editor.COMPANIONS.values())]
    editor.check_new_element_names(view.tree, names)
    identifiers = editor.allocate_form_ids(view.tree, 3)
    before = copy.deepcopy(view.tree)
    if container is None:
        parent = view.tree if parameters["parent"] == "$root" else nodes[parameters["parent"].casefold()]
        container = etree.SubElement(parent, f"{{{editor.FORM}}}ChildItems")
    field = etree.Element(
        f"{{{editor.FORM}}}" + ("CheckBoxField" if scalar == "boolean" else "InputField"),
        name=parameters["name"],
        id=str(identifiers[0]),
    )
    etree.SubElement(field, f"{{{editor.FORM}}}DataPath").text = attribute_path
    title = etree.SubElement(field, f"{{{editor.FORM}}}Title")
    item = etree.SubElement(title, f"{{{editor.V8}}}item")
    etree.SubElement(item, f"{{{editor.V8}}}lang").text = "ru"
    etree.SubElement(item, f"{{{editor.V8}}}content").text = parameters["title"]
    for index, (tag, suffix) in enumerate(editor.COMPANIONS.items(), 1):
        etree.SubElement(field, f"{{{editor.FORM}}}{tag}", name=parameters["name"] + suffix, id=str(identifiers[index]))
    position = (
        list(container).index(nodes[parameters["after"].casefold()]) + 1 if "after" in parameters else len(container)
    )
    container.insert(position, field)
    editor.element_check(view, parameters)
    reduced = copy.deepcopy(view.tree)
    added = editor.named(reduced)[parameters["name"].casefold()]
    reduced_container = added.getparent()
    reduced_container.remove(added)
    old_parent = before if parameters["parent"] == "$root" else editor.named(before)[parameters["parent"].casefold()]
    if old_parent.find("f:ChildItems", editor.NS) is None:
        reduced_container.getparent().remove(reduced_container)
    editor.require(editor.signature(reduced) == editor.signature(before), "Existing form content changed", 4)
    snapshot.stage(path, editor.serialize_like(view.tree, snapshot.read("target", path)))


# --- Element-level editing ----------------------------------------------------
# Rules follow BslEdit form-edit.js at 53ee395 (MIT): canContain, companion
# sets, reference checks and node order. They are ported, not invoked. Only the
# touched nodes change; whitespace of untouched lines is kept byte for byte.
ELEMENT_OPERATIONS = (
    "form.set-properties",
    "form.move-element",
    "form.remove-element",
    "form.rename-element",
    "form.set-attribute",
    "form.set-command",
    "form.remove-event",
)
XR = "http://v8.1c.ru/8.3/xcf/readable"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
COLOR_PREFIXES = {
    "style": "http://v8.1c.ru/8.1/data/ui/style",
    "web": "http://v8.1c.ru/8.1/data/ui/colors/web",
    "win": "http://v8.1c.ru/8.1/data/ui/colors/windows",
}
BAR_ITEMS = frozenset(("Button", "Popup", "ButtonGroup"))
BAR_CONTAINERS = frozenset(("AutoCommandBar", "CommandBar", "Popup", "ButtonGroup", "ContextMenu"))
# Sections a form keeps after its ChildItems (BslEdit moveElement).
FORM_TAIL_SECTIONS = frozenset(
    ("Attributes", "Commands", "Parameters", "CommandInterface", "CommandSet", "ConditionalAppearance")
)
FORM_STRUCTURE = frozenset(("AutoCommandBar", "Events", "ChildItems", "BaseForm")) | FORM_TAIL_SECTIONS


def can_contain(container_kind, item_kind):
    """BslEdit canContain: which item kinds a container accepts in ChildItems."""
    if item_kind == "Page":
        return container_kind == "Pages"
    if container_kind == "Pages":
        return False
    if container_kind in BAR_CONTAINERS:
        return item_kind in BAR_ITEMS
    if item_kind in {"ButtonGroup", "Popup"}:
        return False
    if container_kind in {"Table", "ColumnGroup"}:
        return item_kind not in {"Pages", "Table", "UsualGroup", "CommandBar"}
    if item_kind == "ColumnGroup":
        return False
    return container_kind in {"Form", "UsualGroup", "Page"}


def list_elements(tree):
    """BslEdit listElements: the ChildItems tree with kind, parent and data path."""
    from . import metadata as editor

    result = []

    def walk(node, parent, depth):
        for items in node.findall("f:ChildItems", editor.NS):
            for child in items:
                if not isinstance(child.tag, str):
                    continue
                entry = {
                    "name": child.get("name"),
                    "kind": etree.QName(child).localname,
                    "depth": depth,
                    "parent": parent,
                }
                data_path = child.findtext("f:DataPath", namespaces=editor.NS)
                if data_path and data_path.strip():
                    entry["dataPath"] = data_path.strip()
                result.append(entry)
                walk(child, child.get("name"), depth + 1)

    walk(tree, "Form", 0)
    return result


def _open(snapshot, target, repair_names=False):
    from . import metadata as editor

    path = form_path(target)
    descriptor, _, _, kind = editor.layout(path)
    form_kind = "CommonForm" if kind == "CommonForm" else "Form"
    form_node = editor.metadata(snapshot.read("target", descriptor), form_kind)
    base_root = None
    if editor.prop(form_node, "ObjectBelonging") == "Adopted":
        bases = [
            alias
            for (alias, read_path), data in snapshot.blobs.items()
            if alias != "target"
            and read_path == descriptor
            and data is not None
            and editor.identity(editor.metadata(data, form_kind))
            == editor.prop(form_node, "ExtendedConfigurationObject").lower()
        ]
        if len(bases) != 1:
            raise editor.PublicRejected(
                "Exact base form context required, include form borrow with baseRoot", [target], 3
            )
        base_root = snapshot.roots[bases[0]]
    view = copy.copy(snapshot)
    view.load_form(path, base_root)
    if kind == "external":
        editor.require(etree.QName(view.owner).localname == target.split(".")[0], "External object kind mismatch")
    # Existing duplicates are a broken form, not something to edit around.
    # form.rename-element is the one repair; _finish still demands unique names.
    if not repair_names:
        editor.named(view.tree)
    return view, path


def _base_names(view, section):
    """Names the borrowed BaseForm owns; D4 keeps them read-only here."""
    from . import metadata as editor

    base = view.tree.find("f:BaseForm", editor.NS)
    if base is None:
        return set()
    if section == "elements":
        return {node.get("name").casefold() for node in editor.working_nodes(base) if node.get("name")}
    tag = {"attributes": "Attributes/f:Attribute", "commands": "Commands/f:Command"}[section]
    return {node.get("name", "").casefold() for node in base.findall("f:" + tag, editor.NS)}


def _finish(snapshot, view, path, base_signature, remaining_duplicates=None):
    from . import metadata as editor

    editor.require(
        base_signature == [editor.signature(node) for node in view.tree.findall("f:BaseForm", editor.NS)],
        "BaseForm changed",
        4,
    )
    if remaining_duplicates is None:
        editor.named(view.tree)
    else:
        # form.rename-element only: other pre-existing duplicates may wait for their own rename.
        editor.require(editor.duplicate_names(view.tree) <= remaining_duplicates, "Duplicate existing element name", 4)
    ids = [node.get("id") for node in editor.working_nodes(view.tree) if node.get("id") is not None]
    editor.require(len(ids) == len(set(ids)), "Duplicate working form IDs", 4)
    original = snapshot.read("target", path)
    if editor.signature(view.tree) != editor.signature(editor.xml_read(original, view.tree.tag)):
        snapshot.stage(path, editor.serialize_like(view.tree, original))


def _local(node):
    return etree.QName(node).localname if isinstance(node.tag, str) else None


def _ws_before(node):
    previous = node.getprevious()
    parent = node.getparent()
    if previous is not None:
        return previous.tail or ""
    return (parent.text or "") if parent is not None else "\n"


def _check_layout(parent):
    """Only whitespace separates element children; mixed content is not edited."""
    from . import metadata as editor

    editor.require(
        not (parent.text or "").strip() and all(not (child.tail or "").strip() for child in parent),
        "Unsupported mixed content",
        3,
    )


def _insert(parent, index, child):
    """Insert child keeping sibling indentation; returns the child's leading whitespace."""
    _check_layout(parent)
    if len(parent):
        inner = parent.text or ""
        if index >= len(parent):
            closing = parent[-1].tail
            parent[-1].tail = inner
            child.tail = closing
            parent.append(child)
        else:
            child.tail = _ws_before(parent[index])
            parent.insert(index, child)
        return _ws_before(child)
    outer = _ws_before(parent) if parent.getparent() is not None else "\n"
    parent.text = outer + "\t"
    child.tail = outer
    parent.append(child)
    return parent.text


def _detach(node):
    parent = node.getparent()
    _check_layout(parent)
    previous = node.getprevious()
    if node.getnext() is None:
        if previous is not None:
            previous.tail = node.tail
        else:
            parent.text = None
    parent.remove(node)


def _shift(node, old, new):
    """Re-indent a subtree whose leading whitespace changes from old to new."""
    if old == new:
        return
    for part in node.iter():
        if len(part) and part.text is not None and not part.text.strip() and part.text.startswith(old):
            part.text = new + part.text[len(old) :]
        if part is not node and part.tail is not None and not part.tail.strip() and part.tail.startswith(old):
            part.tail = new + part.tail[len(old) :]


def _indent_new(node, leading):
    """Pretty-print a freshly built subtree at the depth given by its leading whitespace."""
    tail = node.tail
    etree.indent(node, space="\t", level=0)
    _shift(node, "\n", leading)
    node.tail = tail


def _new(parent, tag, text=None, **attributes):
    """Create a child in the destination tree so it reuses existing namespace prefixes."""
    child = etree.SubElement(parent, tag, **attributes)
    parent.remove(child)
    child.text = text
    return child


def _place(parent, child, order, structure):
    """Insert a new property node before the first sibling that follows it."""
    name = etree.QName(child).localname
    rank = order.index(name) if name in order else len(order)
    index = len(parent)
    for position, sibling in enumerate(parent):
        local = _local(sibling)
        if local is None:
            continue
        if (
            local in structure
            or (local in order and order.index(local) > rank)
            or (etree.QName(sibling).namespace != etree.QName(parent).namespace)
        ):
            index = position
            break
    leading = _insert(parent, index, child)
    _indent_new(child, leading)


def _one(parent, tag):
    from . import metadata as editor

    nodes = parent.findall(f"{{{editor.FORM}}}{tag}")
    editor.require(len(nodes) <= 1, "Ambiguous form property", 3)
    return nodes[0] if nodes else None


def _owner_name(node):
    for ancestor in node.iterancestors():
        if ancestor.get("name") is not None and ancestor.get("id") is not None:
            return ancestor.get("name")
    return "Form"


def _path_root(text):
    return re.sub(r"\[[0-9]+\]", "", (text or "").strip()).split(".")


def _text_value(value, prop):
    from . import metadata as editor

    if not isinstance(value, str) or len(value) > 4096 or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value):
        raise editor.PublicRejected("Invalid property value", [prop], 2)
    return value


def _local_text(node, value, prop, formatted=False):
    """Multilingual value: a string sets ru, a mapping sets languages; null drops one."""
    from . import metadata as editor

    patch = {"ru": value} if isinstance(value, str) else value
    if (
        not isinstance(patch, dict)
        or not patch
        or not all(
            isinstance(lang, str)
            and re.fullmatch(r"[A-Za-z]{2,8}(_[A-Za-z]{2,8})?", lang)
            and (text is None or isinstance(text, str))
            for lang, text in patch.items()
        )
    ):
        raise editor.PublicRejected("Invalid multilingual value", [prop], 2)
    for text in patch.values():
        if text is not None:
            _text_value(text, prop)
    items = {}
    if node is not None:
        for item in node:
            editor.require(
                item.tag == f"{{{editor.V8}}}item"
                and not item.attrib
                and [child.tag for child in item] == [f"{{{editor.V8}}}lang", f"{{{editor.V8}}}content"]
                and all(not child.attrib and not len(child) for child in item),
                "Unknown multilingual structure",
                3,
            )
            lang = item.findtext(f"{{{editor.V8}}}lang")
            editor.require(lang not in items, "Ambiguous multilingual item", 3)
            items[lang] = item
        editor.require(not (node.text or "").strip() or not len(node), "Unknown multilingual structure", 3)
    return patch, items


def _write_local(parent, prop, value, order, structure, formatted=False):
    """Set a multilingual node; returns without change when content is equal."""
    from . import metadata as editor

    node = _one(parent, prop)
    patch, items = _local_text(node, value, prop, formatted)
    created = node is None
    if created:
        node = _new(parent, f"{{{editor.FORM}}}{prop}", **({"formatted": "false"} if formatted else {}))
        langs = sorted(
            (lang for lang, text in patch.items() if text is not None),
            key=lambda lang: (0 if lang == "ru" else 1 if lang == "en" else 2, lang),
        )
        if not langs:
            return
        for lang in langs:
            item = etree.SubElement(node, f"{{{editor.V8}}}item")
            etree.SubElement(item, f"{{{editor.V8}}}lang").text = lang
            etree.SubElement(item, f"{{{editor.V8}}}content").text = patch[lang]
        _place(parent, node, order, structure)
        return
    for lang, text in patch.items():
        if lang in items and text is None:
            _detach(items.pop(lang))
        elif lang in items:
            items[lang].find(f"{{{editor.V8}}}content").text = text
        elif text is not None:
            item = _new(node, f"{{{editor.V8}}}item")
            etree.SubElement(item, f"{{{editor.V8}}}lang").text = lang
            etree.SubElement(item, f"{{{editor.V8}}}content").text = text
            leading = _insert(node, len(node), item)
            _indent_new(item, leading)
            items[lang] = item
    if not len(node):
        _detach(node)


def _prefix(node, prefix, uri, prop):
    from . import metadata as editor

    if node.nsmap.get(prefix) != uri:
        raise editor.PublicRejected("Missing namespace prefix binding", [prop, prefix], 3)


def _scalar(value, kind, prop):
    from . import metadata as editor
    from . import metadata_form_schema as schema

    if kind == "b":
        if value in (True, False, "true", "false"):
            return str(value).lower()
    elif kind == "w":
        if value in (True, False, "true", "false", "auto"):
            return str(value).lower()
    elif kind == "d":
        if type(value) is int:
            return str(value)
        if type(value) is float and math.isfinite(value):
            return format(decimal.Decimal(str(value)), "f")
        if isinstance(value, str) and re.fullmatch(r"-?[0-9]{1,15}(\.[0-9]{1,15})?", value):
            return value
    elif kind == "s":
        return _text_value(value, prop)
    elif kind in schema.ELEMENT_ENUMS:
        if isinstance(value, str) and value in schema.ELEMENT_ENUMS[kind]:
            return value
        raise editor.PublicRejected("Value outside enumeration", [prop], 2)
    raise editor.PublicRejected("Invalid property value", [prop], 2)


def _complex(parent, prop, kind, value):
    """Build a color, font or picture node the way Designer writes it."""
    from . import metadata as editor

    tag = f"{{{editor.FORM}}}{prop}"
    if kind == "c":
        if not isinstance(value, str) or not re.fullmatch(r"(style|web|win):[^\W\d]\w{0,127}|#[0-9A-Fa-f]{6}", value):
            raise editor.PublicRejected("Invalid color value", [prop], 2)
        if ":" in value:
            prefix = value.split(":", 1)[0]
            _prefix(parent, prefix, COLOR_PREFIXES[prefix], prop)
        return _new(parent, tag, value)
    if kind == "F":
        keys = {"ref", "face", "height", "bold", "italic", "underline", "strikeout", "scale"}
        if not isinstance(value, dict) or not value or set(value) - keys or ("ref" in value) == ("face" in value):
            raise editor.PublicRejected("Invalid font value", [prop], 2)
        attributes = []
        if "ref" in value:
            if not isinstance(value["ref"], str) or not re.fullmatch(r"style:[^\W\d]\w{0,127}", value["ref"]):
                raise editor.PublicRejected("Invalid font value", [prop], 2)
            _prefix(parent, "style", COLOR_PREFIXES["style"], prop)
            attributes.append(("ref", value["ref"]))
        else:
            _text_value(value["face"], prop)
            attributes.append(("faceName", value["face"]))
        for key in ("height", "scale"):
            if key in value and not (type(value[key]) in (int, float) and math.isfinite(value[key]) and value[key] > 0):
                raise editor.PublicRejected("Invalid font value", [prop], 2)
        if "height" in value:
            attributes.append(("height", _scalar(value["height"], "d", prop)))
        for flag in ("bold", "italic", "underline", "strikeout"):
            if flag in value:
                if type(value[flag]) is not bool:
                    raise editor.PublicRejected("Invalid font value", [prop], 2)
                attributes.append((flag, str(value[flag]).lower()))
        attributes.append(("kind", "StyleItem" if "ref" in value else "Absolute"))
        if "ref" not in value:
            attributes.append(("scale", _scalar(value.get("scale", 100), "d", prop)))
        node = _new(parent, tag)
        for key, item in attributes:
            node.set(key, item)
        return node
    reference = {"ref": value} if isinstance(value, str) else value
    if (
        not isinstance(reference, dict)
        or set(reference) - {"ref", "loadTransparent"}
        or not isinstance(reference.get("ref"), str)
        or not re.fullmatch(r"(CommonPicture|StdPicture)\.[^\W\d]\w{0,127}", reference["ref"])
        or type(reference.get("loadTransparent", False)) is not bool
    ):
        raise editor.PublicRejected("Invalid picture value", [prop], 2)
    _prefix(parent, "xr", XR, prop)
    node = _new(parent, tag)
    etree.SubElement(node, f"{{{XR}}}Ref").text = reference["ref"]
    etree.SubElement(node, f"{{{XR}}}LoadTransparent").text = str(reference.get("loadTransparent", False)).lower()
    return node


def _available_types(view, parent, prop, value):
    """AvailableTypes (ДоступныеТипы) of an input field: v8:Type children as Designer writes them.

    This is the list of types offered when the field edits a TypeDescription value (with TypeDomainEnabled,
    РазрешитьСоставнойТип). It is not ОграничениеТипа (TypeRestriction): the platform keeps that runtime
    property outside the element XML, and AvailableTypes does not narrow the value types of a composite
    reference attribute (checked live in a BP 3.0 test infobase: the type choice dialog still offers every type).

    The value uses the form.compile type spelling (CatalogRef.Имя, СправочникСсылка.Имя, string(10), ...);
    a list or a '|'-separated string gives several types. A leading 'cfg:' is accepted for references.
    """
    from . import metadata as editor

    parts = value if isinstance(value, list) else [value]
    if not parts or not all(isinstance(part, str) and part.strip() for part in parts):
        raise editor.PublicRejected("Invalid type spelling", [prop], 2)
    spellings = []
    for part in parts:
        for item in re.split(r"[|+]", part):
            item = item.strip()
            item = item[4:] if item.startswith("cfg:") else item
            if not item or re.search(r'[<>&"\x00-\x1f]', item):
                raise editor.PublicRejected("Invalid type spelling", [prop], 2)
            spellings.append(item)
    typed = _type_children(view, " | ".join(spellings), prop)
    built = _new(parent, f"{{{editor.FORM}}}{prop}")
    _copy_into(built, typed)
    return built


def _check_reference(view, prop, text):
    """Keep new data paths and command names resolvable inside this form."""
    from . import metadata as editor

    if prop.endswith("DataPath") and text:
        segments = _path_root(text.lstrip("~"))
        tables = {
            node.get("name"): node for node in editor.working_nodes(view.tree) if node.tag == f"{{{editor.FORM}}}Table"
        }
        hops = 0
        # Items.<Таблица>.CurrentData.<поле> goes through a table to its attribute (form-validate).
        while segments[0] == "Items":
            hops += 1
            table = tables.get(segments[1]) if len(segments) > 2 and segments[2] == "CurrentData" else None
            if table is None or hops > 10:
                raise editor.PublicRejected("Data path table not found", [prop], 3)
            path = (table.findtext("f:DataPath", default="", namespaces=editor.NS) or "").strip()
            if not path:
                return
            segments = _path_root(path.lstrip("~"))
        names = {node.get("name") for node in view.tree.findall("f:Attributes/f:Attribute", editor.NS)}
        if segments[0] not in names:
            raise editor.PublicRejected("Data path attribute not found", [prop], 3)
    if prop == "CommandName" and text.startswith("Form.Command."):
        names = {node.get("name") for node in view.tree.findall("f:Commands/f:Command", editor.NS)}
        if text[len("Form.Command.") :] not in names:
            raise editor.PublicRejected("Command not found", [prop], 3)


def set_properties(snapshot, operation):
    """form.set-properties: scalar and simple structured properties of one element."""
    from . import metadata as editor
    from . import metadata_form_schema as schema

    view, path = _open(snapshot, operation["target"])
    base_signature = [editor.signature(node) for node in view.tree.findall("f:BaseForm", editor.NS)]
    parameters = operation["parameters"]
    name = parameters.get("element", "Form")
    if name == "Form":
        node, kind, catalog = view.tree, "Form", schema.FORM_ELEMENT_PROPERTIES
        structure = FORM_STRUCTURE
        editor.require(view.kind != "borrowed-cfe", "Borrowed form properties belong to BaseForm", 3)
    else:
        node = editor.named(view.tree).get(name.casefold())
        if not (
            node is not None and node.get("name") == name and node.getparent().tag == f"{{{editor.FORM}}}ChildItems"
        ):
            raise editor.Rejected("Exact form element not found", 3)
        kind = etree.QName(node).localname
        catalog = schema.ELEMENT_PROPERTIES.get(kind)
        if catalog is None:
            raise editor.PublicRejected("Unsupported element kind", [kind], 2)
        if name.casefold() in _base_names(view, "elements"):
            raise editor.PublicRejected("Base form element is read-only", [name], 3)
        structure = schema.STRUCTURE_NODES
    kinds = {prop: value_kind for prop, value_kind in catalog}
    order = [prop for prop, _ in catalog]
    attributes = {key.casefold() for key in node.attrib} | {"name", "id", "version", "formatted", "calltype"}
    for prop, value in parameters["properties"].items():
        if prop in schema.STRUCTURE_NODES or prop in FORM_STRUCTURE:
            raise editor.PublicRejected("Composition node is not a property", [prop], 2)
        if prop.casefold() in attributes:
            raise editor.PublicRejected("Start-tag attribute is not a property", [prop], 2)
        value_kind = kinds.get(prop)
        if value_kind is None:
            raise editor.PublicRejected("Unknown property", [kind, prop], 2)
        if value_kind == "x":
            raise editor.PublicRejected("Structured property is not supported", [prop], 2)
        existing = _one(node, prop)
        if value is None:
            if existing is not None:
                _detach(existing)
            continue
        if value_kind == "t":
            built = _available_types(view, node, prop, value)
            if existing is not None:
                if editor.signature(existing) == editor.signature(built):
                    continue
                leading = _ws_before(existing)
                built.tail = existing.tail
                node.replace(existing, built)
                _indent_new(built, leading)
            else:
                _place(node, built, order, structure)
            continue
        if value_kind in {"l", "f"}:
            _write_local(node, prop, value, order, structure, formatted=value_kind == "f")
            continue
        if value_kind in {"c", "F", "p"}:
            built = _complex(node, prop, value_kind, value)
            if existing is not None:
                if editor.signature(existing) == editor.signature(built):
                    continue
                expected = {f"{{{XR}}}Ref", f"{{{XR}}}LoadTransparent"} if value_kind == "p" else set()
                editor.require(
                    {child.tag for child in existing} <= expected
                    and (value_kind == "F" or set(existing.attrib) <= set()),
                    "Unknown property structure",
                    3,
                )
                leading = _ws_before(existing)
                built.tail = existing.tail
                node.replace(existing, built)
                _indent_new(built, leading)
            else:
                _place(node, built, order, structure)
            continue
        text = _scalar(value, value_kind, prop)
        _check_reference(view, prop, text)
        if existing is not None:
            editor.require(not len(existing) and not existing.attrib, "Unknown property structure", 3)
            existing.text = text
        else:
            _place(node, _new(node, f"{{{editor.FORM}}}{prop}", text), order, structure)
    _finish(snapshot, view, path, base_signature)


def _item(view, name, role):
    from . import metadata as editor

    node = editor.named(view.tree).get(name.casefold())
    if not (node is not None and node.get("name") == name):
        raise editor.Rejected("Exact form element not found", 3)
    if node.getparent().tag != f"{{{editor.FORM}}}ChildItems":
        raise editor.PublicRejected("Not a form item", [name], 2)
    return node


def move_element(snapshot, operation):
    """form.move-element: move an item with its companions and descendants, IDs kept."""
    from . import metadata as editor

    view, path = _open(snapshot, operation["target"])
    base_signature = [editor.signature(node) for node in view.tree.findall("f:BaseForm", editor.NS)]
    parameters = operation["parameters"]
    node = _item(view, parameters["element"], "element")
    kind = etree.QName(node).localname
    if parameters["element"].casefold() in _base_names(view, "elements"):
        raise editor.PublicRejected("Base form element is read-only", [parameters["element"]], 3)
    anchor_name = parameters.get("after") or parameters.get("before")
    anchor = _item(view, anchor_name, "anchor") if anchor_name else None
    if anchor is node:
        raise editor.PublicRejected("Element cannot be placed relative to itself", [anchor_name], 2)
    into = parameters.get("into")
    if into == "Form":
        container = view.tree
    elif into is not None:
        container = editor.named(view.tree).get(into.casefold())
        if not (container is not None and container.get("name") == into):
            raise editor.Rejected("Exact target container not found", 3)
    else:
        # The operation schema requires into, after or before; without them no container exists.
        if anchor is None:
            raise editor.Rejected("Exact target container not found", 3)
        container = anchor.getparent().getparent()
    if anchor is not None and anchor.getparent().getparent() is not container:
        raise editor.PublicRejected("Anchor is not in the target container", [anchor_name], 3)
    if container is node or node in container.iterancestors():
        raise editor.PublicRejected("Element cannot be moved into itself", [parameters["element"]], 2)
    container_kind = "Form" if container is view.tree else etree.QName(container).localname
    if not can_contain(container_kind, kind):
        raise editor.PublicRejected("Container cannot hold this kind", [container_kind, kind], 2)
    source = node.getparent()
    items = [child for child in container.findall("f:ChildItems", editor.NS)]
    editor.require(len(items) <= 1, "Ambiguous ChildItems", 3)
    target = items[0] if items else None
    if target is source:
        order = [child for child in source if child is not node]
        index = len(order) if anchor is None else order.index(anchor) + (1 if "after" in parameters else 0)
        if list(source).index(node) == index:
            return _finish(snapshot, view, path, base_signature)
    old_leading = _ws_before(node)
    _detach(node)
    if not len(source):
        _detach(source)
    if target is None:
        target = _new(container, f"{{{editor.FORM}}}ChildItems")
        if container is view.tree:
            position = next(
                (index for index, child in enumerate(container) if _local(child) in FORM_TAIL_SECTIONS), len(container)
            )
        else:
            position = len(container)
        _insert(container, position, target)
        target.text = None
    index = len(target) if anchor is None else list(target).index(anchor) + (1 if "after" in parameters else 0)
    new_leading = _insert(target, index, node)
    _shift(node, old_leading, new_leading)
    _finish(snapshot, view, path, base_signature)


def _references_to_items(view, subtree):
    """BslEdit referencesTo plus Designer links by element name.

    CommandName Form.Item.<name>, CommandSource Item.<name>, AdditionSource/Item <name>
    of detached additions, DataPath Items.<name>.… and conditional-appearance fields.
    """
    from . import metadata as editor

    names = {part.get("name") for part in subtree.iter() if part.get("name") is not None and part.get("id") is not None}
    owners = []
    for part in view.tree.iter():
        if not isinstance(part.tag, str) or part is subtree or subtree in part.iterancestors():
            continue
        if part.tag == f"{{{editor.FORM}}}BaseForm" or any(
            ancestor.tag == f"{{{editor.FORM}}}BaseForm" for ancestor in part.iterancestors()
        ):
            continue
        text = (part.text or "").strip()
        local = etree.QName(part).localname
        if local == "CommandName":
            match = re.match(r"Form\.Item\.([^.]+)\.", text)
        elif local == "CommandSource":
            match = re.fullmatch(r"Item\.([^.]+)", text)
        elif local.endswith("DataPath"):
            match = re.match(r"Items\.([^.\[]+)(?:\[[0-9]+\])?\.", text)
        elif local == "Item" and etree.QName(part.getparent()).localname == "AdditionSource":
            match = re.fullmatch(r"([^.]+)", text)
        else:
            match = None
        if match and match.group(1) in names:
            owners.append(_owner_name(part))
        elif (
            local == "field"
            and text in names
            and any(etree.QName(ancestor).localname == "ConditionalAppearance" for ancestor in part.iterancestors())
        ):
            owners.append("ConditionalAppearance")
    return list(dict.fromkeys(owners))


def remove_element(snapshot, operation):
    """form.remove-element: remove an unreferenced item with companions and descendants."""
    from . import metadata as editor

    view, path = _open(snapshot, operation["target"])
    base_signature = [editor.signature(node) for node in view.tree.findall("f:BaseForm", editor.NS)]
    name = operation["parameters"]["element"]
    node = _item(view, name, "element")
    base_names = _base_names(view, "elements")
    removed = [part.get("name") for part in node.iter() if part.get("name") and part.get("id") is not None]
    if any(item.casefold() in base_names for item in removed):
        raise editor.PublicRejected("Base form element is read-only", [name], 3)
    references = _references_to_items(view, node)
    if references:
        raise editor.PublicRejected("Element is referenced by", references, 3)
    handlers = {(event.text or "").strip() for event in node.iter(f"{{{editor.FORM}}}Event")} - {""}
    source = node.getparent()
    _detach(node)
    if not len(source):
        _detach(source)
    still_used = {
        (part.text or "").strip() for part in view.tree.iter(f"{{{editor.FORM}}}Event", f"{{{editor.FORM}}}Action")
    }
    orphans = sorted(handlers - still_used)
    if orphans and snapshot.read("target", view.module, optional=True) is not None:
        # Procedures stay in the module; the plan names them for review.
        item = snapshot.pending_dependencies.setdefault(view.module, {"reason": "bsl-review", "targets": set()})
        item["targets"].update(orphans)
    _finish(snapshot, view, path, base_signature)


def rename_element(snapshot, operation):
    """form.rename-element: rename one unreferenced item and its own companions.

    The only operation that opens a form with duplicate element names: `id`
    selects the exact node. Each rename removes one occurrence of a duplicate;
    the remaining pre-existing duplicates wait for their own rename, and the new
    name must be unique, so no new duplicate can appear.
    """
    from . import metadata as editor

    view, path = _open(snapshot, operation["target"], repair_names=True)
    duplicates_before = editor.duplicate_names(view.tree)
    base_signature = [editor.signature(node) for node in view.tree.findall("f:BaseForm", editor.NS)]
    parameters = operation["parameters"]
    name, new_name = parameters["element"], parameters["newName"]
    items = [
        node
        for node in editor.working_nodes(view.tree)
        if isinstance(node.tag, str)
        and node.get("name") == name
        and node.get("id") is not None
        and node.getparent().tag == f"{{{editor.FORM}}}ChildItems"
    ]
    if "id" in parameters:
        items = [node for node in items if node.get("id") == str(parameters["id"])]
    editor.require(len(items) == 1, "Exact form element not found", 3)
    node = items[0]
    base_names = _base_names(view, "elements")
    editor.require(
        name.casefold() not in base_names and new_name.casefold() not in base_names, "Base form element is read-only", 3
    )
    if _references_to_items(view, node):
        raise editor.PublicRejected("Element is referenced by", _references_to_items(view, node), 3)
    companions = [
        child
        for child in node
        if isinstance(child.tag, str) and child.get("id") is not None and (child.get("name") or "").startswith(name)
    ]
    renamed = [node, *companions]
    taken = {
        (part.get("name") or "").casefold()
        for part in editor.working_nodes(view.tree)
        if isinstance(part.tag, str) and part not in renamed
    }
    for part in renamed:
        part.set("name", new_name + part.get("name")[len(name) :])
        editor.require(part.get("name").casefold() not in taken, "Element name already exists", 3)
    if snapshot.read("target", view.module, optional=True) is not None:
        item = snapshot.pending_dependencies.setdefault(view.module, {"reason": "bsl-review", "targets": set()})
        item["targets"].add(name)
    _finish(snapshot, view, path, base_signature, remaining_duplicates=duplicates_before)


def _type_children(view, spelling, prop="Type"):
    """Type node content through the shared form.compile type spelling."""
    from . import metadata as editor
    from . import metadata_form_compile

    try:
        sample = editor.xml_read(
            metadata_form_compile.render_form({"attributes": [{"name": "Образец", "type": spelling}]}),
            f"{{{editor.FORM}}}Form",
        )
    except ValueError:
        raise editor.PublicRejected("Invalid type spelling", [prop], 2) from None
    typed = sample.find("f:Attributes/f:Attribute/f:Type", editor.NS)
    if not (typed is not None and len(typed)):
        raise editor.Rejected("Invalid type spelling")
    for part in typed.iter():
        if part is typed or not part.text or len(part):
            continue
        prefix, separator, _ = part.text.partition(":")
        if separator and prefix in part.nsmap:
            if view.tree.nsmap.get(prefix) != part.nsmap[prefix]:
                raise editor.PublicRejected("Missing namespace prefix binding", [prop, prefix], 3)
    return typed


def _copy_into(parent, source):
    """Recreate source children under parent in the destination namespaces."""
    for child in source:
        copy_node = etree.SubElement(parent, child.tag, dict(child.attrib))
        copy_node.text = child.text
        _copy_into(copy_node, child)


def _member_ids(view, section):
    from . import metadata as editor

    roots = [view.tree, *view.tree.findall("f:BaseForm", editor.NS)]
    used = [
        int(node.get("id"))
        for root in roots
        for node in root.findall(f"f:{section}//*[@id]", editor.NS)
        if re.fullmatch(r"-?[0-9]{1,10}", node.get("id", ""))
    ]
    start = max(used, default=0) + 1
    return max(start, 1000000 if view.tree.find("f:BaseForm", editor.NS) is not None else 1)


def _set_member_type(view, member, spelling, order):
    from . import metadata as editor

    typed = _type_children(view, spelling)
    existing = _one(member, "Type")
    replacement = _new(member, f"{{{editor.FORM}}}Type")
    _copy_into(replacement, typed)
    if existing is not None:
        if editor.signature(existing) == editor.signature(replacement):
            return
        leading = _ws_before(existing)
        replacement.tail = existing.tail
        member.replace(existing, replacement)
        _indent_new(replacement, leading)
    else:
        _place(member, replacement, order, set())


def _set_flag(member, tag, text, order):
    """Write a scalar member node; None removes it (the platform default)."""
    from . import metadata as editor

    existing = _one(member, tag)
    if text is None:
        if existing is not None:
            _detach(existing)
        return
    if existing is not None:
        editor.require(not len(existing) and not existing.attrib, "Unknown property structure", 3)
        existing.text = text
    else:
        _place(member, _new(member, f"{{{editor.FORM}}}{tag}", text), order, set())


def _new_member(section_node, tag, name, identifier):
    from . import metadata as editor

    member = _new(section_node, f"{{{editor.FORM}}}{tag}", name=name, id=str(identifier))
    leading = _insert(section_node, len(section_node), member)
    return member, leading


def _section(view, tag):
    from . import metadata as editor

    section = _one(view.tree, tag)
    if section is None:
        section = _new(view.tree, f"{{{editor.FORM}}}{tag}")
        tail_order = ["Attributes", "Commands", "Parameters", "CommandInterface"]
        rank = tail_order.index(tag)
        position = next(
            (
                index
                for index, child in enumerate(view.tree)
                if _local(child) in tail_order[rank + 1 :] or _local(child) in {"BaseForm"}
            ),
            len(view.tree),
        )
        _insert(view.tree, position, section)
    return section


def _through_tables(view, segments):
    """Resolve Items.<Таблица>.CurrentData.<поле> to the table data path; None when unresolved."""
    from . import metadata as editor

    tables = None
    hops = 0
    while segments and segments[0] == "Items":
        if tables is None:
            tables = {
                node.get("name"): node
                for node in editor.working_nodes(view.tree)
                if node.tag == f"{{{editor.FORM}}}Table"
            }
        hops += 1
        table = tables.get(segments[1]) if len(segments) > 2 and segments[2] == "CurrentData" else None
        path = (
            (table.findtext("f:DataPath", default="", namespaces=editor.NS) or "").strip() if table is not None else ""
        )
        if not path or hops > 10:
            return None
        segments = _path_root(path.lstrip("~")) + segments[3:]
    return segments


def _attribute_references(view, attribute, column=None):
    """Data paths and conditional-appearance fields that use an attribute or column."""
    from . import metadata as editor

    owners = []
    base = view.tree.find("f:BaseForm", editor.NS)
    for part in view.tree.iter():
        if not isinstance(part.tag, str) or (base is not None and (part is base or base in part.iterancestors())):
            continue
        local = etree.QName(part).localname
        in_appearance = any(
            etree.QName(ancestor).localname == "ConditionalAppearance" for ancestor in part.iterancestors()
        )
        if not (local.endswith("DataPath") or in_appearance and (part.get(f"{{{XSI}}}type") or "").endswith(":Field")):
            continue
        segments = _through_tables(view, _path_root((part.text or "").lstrip("~")))
        if segments and segments[0] == attribute and (column is None or len(segments) > 1 and segments[1] == column):
            owners.append("ConditionalAppearance" if in_appearance else _owner_name(part))
    return list(dict.fromkeys(owners))


def set_attribute(snapshot, operation):
    """form.set-attribute: create, change or remove one form attribute and its columns."""
    from . import metadata as editor
    from . import metadata_form_schema as schema

    view, path = _open(snapshot, operation["target"])
    base_signature = [editor.signature(node) for node in view.tree.findall("f:BaseForm", editor.NS)]
    parameters = operation["parameters"]
    name = parameters["name"]
    order = schema.ATTRIBUTE_ORDER
    section = _one(view.tree, "Attributes")
    attributes = section.findall("f:Attribute", editor.NS) if section is not None else []
    matches = [node for node in attributes if node.get("name", "").casefold() == name.casefold()]
    editor.require(
        len(matches) <= 1 and all(node.get("name") == name for node in matches), "Ambiguous form attribute", 3
    )
    member = matches[0] if matches else None
    if name.casefold() in _base_names(view, "attributes"):
        raise editor.PublicRejected("Base form attribute is read-only", [name], 3)
    if parameters.get("remove"):
        if member is None:
            return _finish(snapshot, view, path, base_signature)
        references = _attribute_references(view, name)
        if references:
            raise editor.PublicRejected("Attribute is referenced by", references, 3)
        _detach(member)
        if section is not None and not len(section):
            _detach(section)
        return _finish(snapshot, view, path, base_signature)
    if parameters.get("main"):
        others = [
            node.get("name")
            for node in attributes
            if node is not member and node.findtext("f:MainAttribute", namespaces=editor.NS) == "true"
        ]
        if others:
            raise editor.PublicRejected("Second main attribute", others, 3)
    if member is None:
        editor.require("type" in parameters, "New attribute requires a type")
        section = _section(view, "Attributes")
        member, leading = _new_member(section, "Attribute", name, _member_ids(view, "Attributes"))
        member.text = None
    if "title" in parameters:
        _write_local(member, "Title", parameters["title"], order, set())
    if "type" in parameters:
        _set_member_type(view, member, parameters["type"], order)
    if "main" in parameters:
        _set_flag(member, "MainAttribute", "true" if parameters["main"] else None, order)
    if "savedData" in parameters:
        _set_flag(member, "SavedData", "true" if parameters["savedData"] else None, order)
    if "fillChecking" in parameters:
        _set_flag(member, "FillCheck", "ShowError" if parameters["fillChecking"] == "ShowError" else None, order)
    for column in parameters.get("columns", []):
        box = _one(member, "Columns")
        found = [
            node
            for node in (box if box is not None else [])
            if node.get("name", "").casefold() == column["name"].casefold()
        ]
        editor.require(
            len(found) <= 1 and all(node.get("name") == column["name"] for node in found),
            "Ambiguous form attribute column",
            3,
        )
        if column.get("remove"):
            if found:
                references = _attribute_references(view, name, column["name"])
                if references:
                    raise editor.PublicRejected("Column is referenced by", references, 3)
                _detach(found[0])
                if box is not None and not len(box):
                    _detach(box)
            continue
        if found:
            target = found[0]
        else:
            editor.require("type" in column, "New column requires a type")
            if box is None:
                box = _new(member, f"{{{editor.FORM}}}Columns")
                _place(member, box, order, set())
                box.text = None
            target, _ = _new_member(box, "Column", column["name"], _member_ids(view, "Attributes"))
        if "title" in column:
            _write_local(target, "Title", column["title"], order, set())
        if "type" in column:
            _set_member_type(view, target, column["type"], order)
    editor.require(member.find("f:Type", editor.NS) is not None, "Attribute type is missing", 3)
    _finish(snapshot, view, path, base_signature)


def set_command(snapshot, operation):
    """form.set-command: create, change or remove one form command; BSL is untouched."""
    from . import metadata as editor
    from . import metadata_form_schema as schema

    view, path = _open(snapshot, operation["target"])
    base_signature = [editor.signature(node) for node in view.tree.findall("f:BaseForm", editor.NS)]
    parameters = operation["parameters"]
    name = parameters["name"]
    order = schema.COMMAND_ORDER
    section = _one(view.tree, "Commands")
    commands = section.findall("f:Command", editor.NS) if section is not None else []
    matches = [node for node in commands if node.get("name", "").casefold() == name.casefold()]
    if "id" in parameters:
        return _remove_duplicate_command(snapshot, view, path, base_signature, parameters, matches)
    editor.require(len(matches) <= 1 and all(node.get("name") == name for node in matches), "Ambiguous form command", 3)
    member = matches[0] if matches else None
    if name.casefold() in _base_names(view, "commands"):
        raise editor.PublicRejected("Base form command is read-only", [name], 3)
    if parameters.get("remove"):
        if member is None:
            return _finish(snapshot, view, path, base_signature)
        base = view.tree.find("f:BaseForm", editor.NS)
        owners = [
            (
                "CommandInterface"
                if any(_local(a) == "CommandInterface" for a in part.iterancestors())
                else _owner_name(part)
            )
            for part in view.tree.iter()
            if isinstance(part.tag, str)
            and (part.text or "").strip() == "Form.Command." + name
            and (base is None or base not in part.iterancestors())
        ]
        if owners:
            raise editor.PublicRejected("Command is referenced by", list(dict.fromkeys(owners)), 3)
        _detach(member)
        if section is not None and not len(section):
            _detach(section)
        return _finish(snapshot, view, path, base_signature)
    if member is None:
        editor.require("action" in parameters, "New command requires an action")
        section = _section(view, "Commands")
        member, _ = _new_member(section, "Command", name, _member_ids(view, "Commands"))
        member.text = None
    for key, tag in (("title", "Title"), ("toolTip", "ToolTip")):
        if key in parameters:
            _write_local(member, tag, parameters[key], order, set())
    if "shortcut" in parameters:
        _set_flag(member, "Shortcut", parameters["shortcut"], order)
    if "action" in parameters:
        actions = member.findall("f:Action", editor.NS)
        editor.require(
            len(actions) <= 1 and all(not node.attrib and not len(node) for node in actions),
            "Unsupported command action structure",
            3,
        )
        _set_flag(member, "Action", parameters["action"], order)
    if "representation" in parameters:
        _set_flag(member, "Representation", parameters["representation"], order)
    if "modifiesSavedData" in parameters:
        _set_flag(member, "ModifiesSavedData", "true" if parameters["modifiesSavedData"] else None, order)
    if "currentRowUse" in parameters:
        _set_flag(member, "CurrentRowUse", parameters["currentRowUse"], order)
    _finish(snapshot, view, path, base_signature)


def _remove_duplicate_command(snapshot, view, path, base_signature, parameters, matches):
    """form.set-command remove with `id`: drop one copy of a duplicated command.

    Converted forms may declare the same command twice. Buttons refer to a
    command by name, so removing one identical copy keeps every reference valid.
    Copies that differ in anything but `id` are a real conflict: rename instead.
    """
    from . import metadata as editor

    name = parameters["name"]
    if not parameters.get("remove") or set(parameters) - {"name", "id", "remove"}:
        raise editor.PublicRejected("Command id selects a duplicate copy to remove", [name], 3)
    if name.casefold() in _base_names(view, "commands"):
        raise editor.PublicRejected("Base form command is read-only", [name], 3)
    editor.require(all(node.get("name") == name for node in matches), "Ambiguous form command", 3)
    selected = [node for node in matches if node.get("id") == str(parameters["id"])]
    if not selected and len(matches) <= 1:
        # Repeating the request after apply changes nothing: the duplicate is gone.
        return _finish(snapshot, view, path, base_signature)
    editor.require(len(selected) == 1, "Exact form command not found", 3)
    if len(matches) < 2:
        raise editor.PublicRejected("Command is not duplicated, remove it without id", [name], 3)

    def content(node):
        node = copy.deepcopy(node)
        node.attrib.pop("id", None)
        node.tail = None
        return editor.signature(node)

    if any(content(node) != content(selected[0]) for node in matches if node is not selected[0]):
        raise editor.PublicRejected("Duplicate commands differ, rename one of them", [name], 3)
    _detach(selected[0])
    _finish(snapshot, view, path, base_signature)


def remove_event(snapshot, operation):
    """form.remove-event: unbind one form or element event; the module procedure stays for review."""
    from . import metadata as editor

    view, path = _open(snapshot, operation["target"])
    base_signature = [editor.signature(node) for node in view.tree.findall("f:BaseForm", editor.NS)]
    parameters = operation["parameters"]
    owner = view.tree
    if "element" in parameters:
        owner = _item(view, parameters["element"], "element")
        if parameters["element"].casefold() in _base_names(view, "elements"):
            raise editor.PublicRejected("Base form element is read-only", [parameters["element"]], 3)
    section = _one(owner, "Events")
    events = list(section) if section is not None else []
    editor.require(
        all(
            node.tag == f"{{{editor.FORM}}}Event" and not len(node) and set(node.attrib) <= {"name", "callType"}
            for node in events
        ),
        "Unknown Events structure",
        3,
    )
    name = parameters["name"]
    matches = [
        node
        for node in events
        if (node.get("name") or "").casefold() == name.casefold()
        and ("callType" not in parameters or node.get("callType") == parameters["callType"])
    ]
    editor.require(all(node.get("name") == name for node in matches), "Ambiguous form event", 3)
    if len(matches) > 1:
        raise editor.PublicRejected("Event has several handler slots; specify callType", [name], 3)
    if not matches:
        # Repeating the request after apply changes nothing, as form.set-command remove.
        return _finish(snapshot, view, path, base_signature)
    handler = (matches[0].text or "").strip()
    _detach(matches[0])
    if section is not None and not len(section):
        _detach(section)
    still_used = {
        (part.text or "").strip() for part in view.tree.iter(f"{{{editor.FORM}}}Event", f"{{{editor.FORM}}}Action")
    }
    if handler and handler not in still_used and snapshot.read("target", view.module, optional=True) is not None:
        # The procedure stays in the module; the plan names it for review.
        item = snapshot.pending_dependencies.setdefault(view.module, {"reason": "bsl-review", "targets": set()})
        item["targets"].add(handler)
    _finish(snapshot, view, path, base_signature)


def _base_main_attributes(base):
    from . import metadata as editor

    return [
        node
        for node in base.findall("f:Attributes/f:Attribute", editor.NS)
        if node.findtext("f:MainAttribute", namespaces=editor.NS) == "true"
    ]
