"""Pure metadata generation adapted from cc-1c-skills meta-compile v1.5.

Copyright 2025-2026 Nick Shirokov, MIT; see
automation/vendor/cc-1c-skills/LICENSE. No CLI, file I/O or random identities.
"""

import re
from copy import deepcopy

import lxml.etree as etree

from . import metadata_borrow as borrow
from . import metadata_object_ops as objects
from . import metadata_object_schema as schema

REGISTERS = ("InformationRegister", "AccumulationRegister", "AccountingRegister", "CalculationRegister")
CHARTS = ("ChartOfAccounts", "ChartOfCharacteristicTypes", "ChartOfCalculationTypes")
KINDS = (
    "Catalog",
    "Document",
    "Enum",
    "Constant",
    "DefinedType",
    *REGISTERS,
    *CHARTS,
    "BusinessProcess",
    "Task",
    "ExchangePlan",
    "Report",
    "DataProcessor",
    "DocumentJournal",
    "CommonModule",
    "ScheduledJob",
    "EventSubscription",
    "HTTPService",
    "WebService",
    "CommonCommand",
    "Subsystem",
)
SPECIAL_FILES = {
    "BusinessProcess": ("Flowchart", "http://v8.1c.ru/8.3/MDClasses"),
    "ExchangePlan": ("ExchangePlanContent", "http://v8.1c.ru/8.3/xcf/extrnprops"),
}
RUSSIAN_REGISTER_STANDARD_ATTRIBUTES = {
    "InformationRegister": ("Активность", "НомерСтроки", "Регистратор", "Период"),
    "AccumulationRegister": ("Активность", "НомерСтроки", "Регистратор", "Период"),
    "AccountingRegister": ("Активность", "Период", "Регистратор", "НомерСтроки", "Счет"),
    "CalculationRegister": (
        "Активность",
        "Регистратор",
        "НомерСтроки",
        "ПериодРегистрации",
        "ВидРасчета",
        "СторноЗапись",
    ),
}


def preserve_added_children(current, expected, allowed):
    """Allow later additions, never changes to explicitly requested children."""
    from . import metadata as editor

    requested = expected.find(f"{{{editor.MD}}}ChildObjects")
    if requested is None:
        return
    containers = current.findall(f"{{{editor.MD}}}ChildObjects")
    editor.require(len(containers) == 1, "Existing child container differs", 3)
    actual = containers[0]

    def key(child):
        child_kind = etree.QName(child).localname
        editor.require(
            child.tag == f"{{{editor.MD}}}{child_kind}" and child_kind in allowed, "Unsupported existing child", 3
        )
        name = editor.prop(child, "Name") if len(child) else child.text or ""
        editor.require(editor.NAME.fullmatch(name), "Invalid existing child name", 3)
        return name.casefold()

    wanted = {key(child): child for child in requested}
    keys = [key(child) for child in actual]
    editor.require(
        len(keys) == len(set(keys)) and [name for name in keys if name in wanted] == list(wanted),
        "Requested children missing, reordered or ambiguous",
        3,
    )
    for name, child in zip(keys, actual, strict=False):
        if name in wanted and child.tag == wanted[name].tag == f"{{{editor.MD}}}TabularSection":
            preserve_added_children(child, wanted[name], {"Attribute"})
    requested[:] = [
        wanted[name] if name in wanted else deepcopy(child) for name, child in zip(keys, actual, strict=False)
    ]


def create_object(snapshot, operation):
    """Stage native descriptors, registration and new empty modules atomically."""
    from . import metadata as editor

    definition = operation["parameters"]["definition"]
    kind, name = definition["type"], definition["name"]
    editor.require(kind in KINDS and operation["target"] == kind + "." + name, "Object creation kind is not connected")
    config, config_bytes = borrow._checked(snapshot, "target", "Configuration.xml", "Configuration")
    extension = editor.prop(config, "ConfigurationExtensionPurpose")
    editor.require(
        config.getparent().get("version") in {"2.17", "2.20"}
        and extension in {None, "", "Patch", "Customization", "AddOn"},
        "Unsupported creation root",
    )
    registrations = borrow._registrations(config)
    directory = borrow.DIRECTORIES[kind] + "/" + name
    path = directory + ".xml"
    existing = snapshot.read("target", path, optional=True)
    editor.require(
        borrow._linked(registrations, kind, name) == (existing is not None), "Object registration/file mismatch", 3
    )
    if kind == "Subsystem":
        # The platform resolves Content and Picture only inside the extension:
        # base objects must be borrowed (object.borrow) earlier in the request.
        for item in [*definition.get("content", []), *([definition["picture"]] if definition.get("picture") else [])]:
            ref_kind, _, ref_name = item.partition(".")
            editor.require(
                ref_kind in borrow.DIRECTORIES and borrow._linked(registrations, ref_kind, ref_name),
                "Subsystem reference is not registered: " + item,
                3,
            )
    occupied = borrow._uuid_inventory(snapshot)
    candidate = render_object(
        definition, editor.identity(config), {} if existing else occupied, extension=bool(extension)
    )
    special = SPECIAL_FILES.get(kind)
    special_path = directory + "/Ext/" + ("Content.xml" if kind == "ExchangePlan" else "Flowchart.xml")
    if existing is not None:
        current = editor.metadata(existing, kind)
        expected = editor.metadata(candidate, kind)
        allowed = {objects.ADD_KINDS[collection] for collection, owners in objects.ADD_OWNERS.items() if kind in owners}
        allowed.update(
            {
                "ChartOfAccounts": ("AccountingFlag", "ExtDimensionAccountingFlag"),
                "Task": ("AddressingAttribute",),
                "CalculationRegister": ("Recalculation",),
                "HTTPService": ("URLTemplate",),
                "WebService": ("Operation",),
            }.get(kind, ())
        )
        if any(kind in owners for owners in objects.ADD_OWNERS.values()):
            allowed.update(("Form", "Template", "Command"))
        preserve_added_children(current, expected, allowed)
        editor.require(
            editor.signature(current.getparent()) == editor.signature(expected.getparent()),
            "Existing object differs; refusing replacement",
            3,
        )
        if special:
            editor.xml_read(snapshot.read("target", special_path), f"{{{special[1]}}}{special[0]}")
        return
    editor.require(
        not snapshot.list_directory("target", directory, optional=True),
        "Unregistered object artifacts already exist",
        3,
    )
    borrow._register(registrations, kind, name)
    snapshot.stage(path, candidate)
    modules = {
        "Catalog": ("ObjectModule",),
        "Document": ("ObjectModule",),
        "Enum": ("ManagerModule",),
        "Constant": ("ManagerModule", "ValueManagerModule"),
    }
    modules.update({kind: ("RecordSetModule",) for kind in REGISTERS})
    modules.update({kind: ("ObjectModule",) for kind in (*CHARTS, "BusinessProcess", "Task", "ExchangePlan")})
    modules.update({kind: ("ObjectModule", "ManagerModule") for kind in ("Report", "DataProcessor")})
    modules.update({kind: ("Module",) for kind in ("CommonModule", "HTTPService", "WebService")})
    modules["CommonCommand"] = ("CommandModule",)
    for module in modules.get(kind, ()):
        snapshot.stage(directory + "/Ext/" + module + ".bsl", b"")
    if special:
        document = etree.Element(
            f"{{{special[1]}}}{special[0]}", nsmap={None: special[1], "xr": borrow.XR}, version="2.17"
        )
        snapshot.stage(
            special_path,
            b'<?xml version="1.0" encoding="UTF-8"?>\n' + etree.tostring(document, encoding="UTF-8") + b"\n",
        )
    snapshot.stage("Configuration.xml", editor.serialize_like(config.getparent(), config_bytes))


def type_node(value):
    """The existing rich type syntax, with strict names and scalar qualifiers."""
    from . import metadata as editor

    node = etree.Element(f"{{{editor.MD}}}Type", nsmap={"v8": editor.V8, "xs": editor.XS, "cfg": borrow.CFG})
    seen = set()
    for part in schema.normalize_type(value).split(" + "):
        match = re.fullmatch(
            r"(CatalogRef|DocumentRef|EnumRef|ChartOfAccountsRef|ChartOfCharacteristicTypesRef|ChartOfCalculationTypesRef|ExchangePlanRef|BusinessProcessRef|TaskRef|DefinedType|Characteristic)\.([A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)",
            part,
        )
        if part in schema.BARE_TYPE_NAMES:
            key = part
            addition = etree.Element(f"{{{editor.V8}}}Type")
            addition.text = "cfg:" + part
            additions = [addition]
        elif match:
            key = part
            tag = "TypeSet" if match[1] in {"DefinedType", "Characteristic"} else "Type"
            addition = etree.Element(f"{{{editor.V8}}}{tag}")
            addition.text = "cfg:" + part
            additions = [addition]
        elif part == "UUID":
            key = "UUID"
            addition = etree.Element(f"{{{editor.V8}}}Type")
            addition.text = "v8:UUID"
            additions = [addition]
        elif part == "ValueStorage":
            key = "ValueStorage"
            addition = etree.Element(f"{{{editor.V8}}}Type")
            addition.text = "v8:ValueStorage"
            additions = [addition]
        elif part == "BinaryData":
            key = "base64Binary"
            addition = etree.Element(f"{{{editor.V8}}}Type")
            addition.text = "xs:base64Binary"
            additions = [addition]
        else:
            scalar, key = objects.scalar_type(part)
            additions = list(scalar)
        editor.require(key not in seen, "Duplicate type member or conflicting qualifiers")
        seen.add(key)
        node.extend(additions)
    return node


def register_member(definition, identity, register, kind):
    """Reuse common typed properties; retain the legacy register-specific order."""
    from . import metadata as editor

    editor.require(register in REGISTERS and kind in {"Resource", "Dimension"}, "Invalid register child")
    flags = set(definition.get("flags", []))
    allowed = {"req"}
    if kind == "Dimension" or register == "InformationRegister":
        allowed |= {"index", "indexadditional"}
    if kind == "Dimension":
        if register == "InformationRegister":
            allowed |= {"master", "mainfilter", "denyincomplete"}
        elif register == "AccumulationRegister":
            allowed |= {"denyincomplete", "nouseintotals"}
    editor.require(flags <= allowed, "Unsupported register member flags")
    editor.require(
        "indexing" not in definition or kind == "Dimension" or register == "InformationRegister",
        "Indexing is not supported for this resource",
    )
    common = {**definition, "flags": list(flags & {"req", "index", "indexadditional"})}
    node = objects.attribute_node(
        common, identity, typed=type_node(definition.get("type", "Number(15,2)" if kind == "Resource" else "String"))
    )
    node.tag = f"{{{editor.MD}}}{kind}"
    properties = node.find(f"{{{editor.MD}}}Properties")

    def find(name):
        return properties.find(f"{{{editor.MD}}}{name}")

    def remove(name):
        child = find(name)
        if child is not None:
            properties.remove(child)

    def add(name, value, before=None):
        child = etree.Element(f"{{{editor.MD}}}{name}")
        child.text = value
        if before:
            properties.insert(properties.index(find(before)), child)
        else:
            properties.append(child)

    if register == "InformationRegister":
        find("FillFromFillingValue").text = "true" if "master" in flags else "false"
        fill = find("FillValue")
        fill.clear()
        fill.set(f"{{{objects.XSI}}}nil", "true")
    else:
        remove("FillFromFillingValue")
        remove("FillValue")
        remove("DataHistory")
    if kind == "Dimension":
        if register == "InformationRegister":
            add("Master", "true" if "master" in flags else "false", "Indexing")
            add("MainFilter", "true" if "mainfilter" in flags else "false", "Indexing")
        if register in {"InformationRegister", "AccumulationRegister"}:
            add("DenyIncompleteValues", "true" if "denyincomplete" in flags else "false", "Indexing")
        if register == "AccumulationRegister":
            add("UseInTotals", "false" if "nouseintotals" in flags else "true")
    elif register != "InformationRegister":
        remove("Indexing")
        if register != "AccumulationRegister":
            remove("FullTextSearch")
    return node


def render_object(definition, root_uuid, occupied, *, extension=False):
    """Render connected creation kinds; identity keys do not depend on order."""
    from . import metadata as editor

    defn = definition
    obj_type, obj_name = defn["type"], defn["name"]
    editor.require(obj_type in KINDS and editor.NAME.fullmatch(obj_name), "Unconnected object kind or invalid name")
    lines = []
    X = lines.append
    object_type_synonyms = schema._OBJECT_ALIASES
    standard_attributes_by_type = {
        "Catalog": [
            "PredefinedDataName",
            "Predefined",
            "Ref",
            "DeletionMark",
            "IsFolder",
            "Owner",
            "Parent",
            "Description",
            "Code",
        ],
        "Document": ["Posted", "Ref", "DeletionMark", "Date", "Number"],
        "Enum": ["Order", "Ref"],
        "InformationRegister": ["Active", "LineNumber", "Recorder", "Period"],
        "AccumulationRegister": ["Active", "LineNumber", "Recorder", "Period"],
        "AccountingRegister": ["Active", "Period", "Recorder", "LineNumber", "Account"],
        "CalculationRegister": [
            "Active",
            "Recorder",
            "LineNumber",
            "RegistrationPeriod",
            "CalculationType",
            "ReversingEntry",
        ],
        "ChartOfAccounts": [
            "PredefinedDataName",
            "Predefined",
            "Ref",
            "DeletionMark",
            "Description",
            "Code",
            "Parent",
            "Order",
            "Type",
            "OffBalance",
        ],
        "ChartOfCharacteristicTypes": [
            "PredefinedDataName",
            "Predefined",
            "Ref",
            "DeletionMark",
            "Description",
            "Code",
            "Parent",
            "ValueType",
        ],
        "ChartOfCalculationTypes": [
            "PredefinedDataName",
            "Predefined",
            "Ref",
            "DeletionMark",
            "Description",
            "Code",
            "ActionPeriodIsBasic",
        ],
        "BusinessProcess": ["Ref", "DeletionMark", "Date", "Number", "Started", "Completed", "HeadTask"],
        "Task": ["Ref", "DeletionMark", "Date", "Number", "Executed", "Description", "RoutePoint", "BusinessProcess"],
        "ExchangePlan": ["Ref", "DeletionMark", "Code", "Description", "ThisNode", "SentNo", "ReceivedNo"],
        "DocumentJournal": ["Type", "Ref", "Date", "Posted", "DeletionMark", "Number"],
    }

    def get_enum_prop(prop_name, field_name, default):
        value = schema._enum(prop_name, defn.get(field_name, default))
        editor.require(isinstance(value, str) and editor.NAME.fullmatch(value), "Invalid enum property")
        return value

    def emit_value_type(indent, value):
        # Namespace-aware XML nodes avoid interpolating a requested QName into XML.
        X(etree.tostring(type_node(value), encoding="unicode"))

    def build_type_str(value):
        result = value.get("valueType", "String")
        if any(key in value for key in ("length", "precision", "nonneg", "nonnegative")):
            result = schema._attribute(
                {
                    "name": "Value",
                    "type": result,
                    **{key: value[key] for key in ("length", "precision", "nonneg", "nonnegative") if key in value},
                },
                create=True,
            )["type"]
        return result

    def esc_xml(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def split_camel_case(name):
        if not name:
            return name
        result = re.sub(r"([а-яё])([А-ЯЁ])", r"\1 \2", name)
        result = re.sub(r"([a-z])([A-Z])", r"\1 \2", result)
        if len(result) > 1:
            result = result[0] + result[1:].lower()
        return result

    def emit_mltext(indent, tag, text):
        if not text:
            X(f"{indent}<{tag}/>")
            return
        X(f"{indent}<{tag}>")
        X(f"{indent}\t<v8:item>")
        X(f"{indent}\t\t<v8:lang>ru</v8:lang>")
        X(f"{indent}\t\t<v8:content>{esc_xml(text)}</v8:content>")
        X(f"{indent}\t</v8:item>")
        X(f"{indent}</{tag}>")

    def emit_standard_attribute(indent, attr_name):
        X(f'{indent}<xr:StandardAttribute name="{attr_name}">')
        X(f"{indent}\t<xr:LinkByType/>")
        fill_checking = (
            get_enum_prop("FillChecking", "descriptionFillChecking", "DontCheck")
            if obj_type == "Catalog" and attr_name == "Description"
            else "DontCheck"
        )
        X(f"{indent}\t<xr:FillChecking>{fill_checking}</xr:FillChecking>")
        X(f"{indent}\t<xr:MultiLine>false</xr:MultiLine>")
        X(f"{indent}\t<xr:FillFromFillingValue>false</xr:FillFromFillingValue>")
        X(f"{indent}\t<xr:CreateOnInput>Auto</xr:CreateOnInput>")
        X(f'{indent}\t<xr:MaxValue xsi:nil="true"/>')
        X(f"{indent}\t<xr:ToolTip/>")
        X(f"{indent}\t<xr:ExtendedEdit>false</xr:ExtendedEdit>")
        X(f"{indent}\t<xr:Format/>")
        X(f"{indent}\t<xr:ChoiceForm/>")
        X(f"{indent}\t<xr:QuickChoice>Auto</xr:QuickChoice>")
        X(f"{indent}\t<xr:ChoiceHistoryOnInput>Auto</xr:ChoiceHistoryOnInput>")
        X(f"{indent}\t<xr:EditFormat/>")
        X(f"{indent}\t<xr:PasswordMode>false</xr:PasswordMode>")
        X(f"{indent}\t<xr:DataHistory>Use</xr:DataHistory>")
        X(f"{indent}\t<xr:MarkNegatives>false</xr:MarkNegatives>")
        X(f'{indent}\t<xr:MinValue xsi:nil="true"/>')
        X(f"{indent}\t<xr:Synonym/>")
        X(f"{indent}\t<xr:Comment/>")
        X(f"{indent}\t<xr:FullTextSearch>Use</xr:FullTextSearch>")
        X(f"{indent}\t<xr:ChoiceParameterLinks/>")
        X(f'{indent}\t<xr:FillValue xsi:nil="true"/>')
        X(f"{indent}\t<xr:Mask/>")
        X(f"{indent}\t<xr:ChoiceParameters/>")
        X(f"{indent}</xr:StandardAttribute>")

    def emit_standard_attributes(indent, object_type):
        attrs = standard_attributes_by_type.get(object_type)
        if not attrs:
            return
        X(f"{indent}<StandardAttributes>")
        for a in attrs:
            emit_standard_attribute(f"{indent}\t", a)
        X(f"{indent}</StandardAttributes>")

    def emit_input_by_string(indent, object_type, fields):
        enabled = [name for name, length in fields if str(length).isdecimal() and int(str(length)) > 0]
        if not enabled:
            X(f"{indent}<InputByString/>")
            return
        X(f"{indent}<InputByString>")
        for name in enabled:
            X(f"{indent}\t<xr:Field>{object_type}.{obj_name}.StandardAttribute.{name}</xr:Field>")
        X(f"{indent}</InputByString>")

    def emit_catalog_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        hierarchical = "true" if defn.get("hierarchical") is True else "false"
        hierarchy_type = get_enum_prop("HierarchyType", "hierarchyType", "HierarchyFoldersAndItems")
        X(f"{i}<Hierarchical>{hierarchical}</Hierarchical>")
        X(f"{i}<HierarchyType>{hierarchy_type}</HierarchyType>")
        X(f"{i}<LimitLevelCount>false</LimitLevelCount>")
        X(f"{i}<LevelCount>2</LevelCount>")
        X(f"{i}<FoldersOnTop>true</FoldersOnTop>")
        X(f"{i}<UseStandardCommands>true</UseStandardCommands>")
        X(f"{i}<Owners/>")
        X(f"{i}<SubordinationUse>ToItems</SubordinationUse>")
        code_length = str(defn["codeLength"]) if defn.get("codeLength") is not None else "9"
        description_length = str(defn["descriptionLength"]) if defn.get("descriptionLength") is not None else "25"
        code_type = get_enum_prop("CodeType", "codeType", "String")
        code_allowed_length = get_enum_prop("CodeAllowedLength", "codeAllowedLength", "Variable")
        autonumbering = "false" if defn.get("autonumbering") is False else "true"
        check_unique = "true" if defn.get("checkUnique") is True else "false"
        X(f"{i}<CodeLength>{code_length}</CodeLength>")
        X(f"{i}<DescriptionLength>{description_length}</DescriptionLength>")
        X(f"{i}<CodeType>{code_type}</CodeType>")
        X(f"{i}<CodeAllowedLength>{code_allowed_length}</CodeAllowedLength>")
        X(f"{i}<CodeSeries>WholeCatalog</CodeSeries>")
        X(f"{i}<CheckUnique>{check_unique}</CheckUnique>")
        X(f"{i}<Autonumbering>{autonumbering}</Autonumbering>")
        default_presentation = get_enum_prop("DefaultPresentation", "defaultPresentation", "AsDescription")
        X(f"{i}<DefaultPresentation>{default_presentation}</DefaultPresentation>")
        emit_standard_attributes(i, "Catalog")
        X(f"{i}<Characteristics/>")
        X(f"{i}<PredefinedDataUpdate>Auto</PredefinedDataUpdate>")
        X(f"{i}<EditType>InDialog</EditType>")
        X(f"{i}<QuickChoice>true</QuickChoice>")
        X(f"{i}<ChoiceMode>BothWays</ChoiceMode>")
        emit_input_by_string(i, "Catalog", [("Description", description_length), ("Code", code_length)])
        X(f"{i}<SearchStringModeOnInputByString>Begin</SearchStringModeOnInputByString>")
        X(f"{i}<FullTextSearchOnInputByString>DontUse</FullTextSearchOnInputByString>")
        X(f"{i}<ChoiceDataGetModeOnInputByString>Directly</ChoiceDataGetModeOnInputByString>")
        X(f"{i}<DefaultObjectForm/>")
        X(f"{i}<DefaultFolderForm/>")
        X(f"{i}<DefaultListForm/>")
        X(f"{i}<DefaultChoiceForm/>")
        X(f"{i}<DefaultFolderChoiceForm/>")
        X(f"{i}<AuxiliaryObjectForm/>")
        X(f"{i}<AuxiliaryFolderForm/>")
        X(f"{i}<AuxiliaryListForm/>")
        X(f"{i}<AuxiliaryChoiceForm/>")
        X(f"{i}<AuxiliaryFolderChoiceForm/>")
        X(f"{i}<IncludeHelpInContents>false</IncludeHelpInContents>")
        X(f"{i}<BasedOn/>")
        X(f"{i}<DataLockFields/>")
        data_lock_control_mode = get_enum_prop("DataLockControlMode", "dataLockControlMode", "Automatic")
        X(f"{i}<DataLockControlMode>{data_lock_control_mode}</DataLockControlMode>")
        full_text_search = get_enum_prop("FullTextSearch", "fullTextSearch", "Use")
        X(f"{i}<FullTextSearch>{full_text_search}</FullTextSearch>")
        X(f"{i}<ObjectPresentation/>")
        X(f"{i}<ExtendedObjectPresentation/>")
        X(f"{i}<ListPresentation/>")
        X(f"{i}<ExtendedListPresentation/>")
        X(f"{i}<Explanation/>")
        X(f"{i}<CreateOnInput>DontUse</CreateOnInput>")
        X(f"{i}<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>")
        X(f"{i}<DataHistory>DontUse</DataHistory>")
        X(f"{i}<UpdateDataHistoryImmediatelyAfterWrite>false</UpdateDataHistoryImmediatelyAfterWrite>")
        X(f"{i}<ExecuteAfterWriteDataHistoryVersionProcessing>false</ExecuteAfterWriteDataHistoryVersionProcessing>")

    def emit_document_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        X(f"{i}<UseStandardCommands>true</UseStandardCommands>")
        X(f"{i}<Numerator/>")
        number_type = get_enum_prop("NumberType", "numberType", "String")
        number_length = str(defn["numberLength"]) if defn.get("numberLength") is not None else "11"
        number_allowed_length = get_enum_prop("NumberAllowedLength", "numberAllowedLength", "Variable")
        number_periodicity = get_enum_prop("InformationRegisterPeriodicity", "numberPeriodicity", "Year")
        check_unique = "false" if defn.get("checkUnique") is False else "true"
        autonumbering = "false" if defn.get("autonumbering") is False else "true"
        X(f"{i}<NumberType>{number_type}</NumberType>")
        X(f"{i}<NumberLength>{number_length}</NumberLength>")
        X(f"{i}<NumberAllowedLength>{number_allowed_length}</NumberAllowedLength>")
        X(f"{i}<NumberPeriodicity>{number_periodicity}</NumberPeriodicity>")
        X(f"{i}<CheckUnique>{check_unique}</CheckUnique>")
        X(f"{i}<Autonumbering>{autonumbering}</Autonumbering>")
        emit_standard_attributes(i, "Document")
        X(f"{i}<Characteristics/>")
        X(f"{i}<BasedOn/>")
        X(f"{i}<InputByString>")
        X(f"{i}\t<xr:Field>Document.{obj_name}.StandardAttribute.Number</xr:Field>")
        X(f"{i}</InputByString>")
        X(f"{i}<CreateOnInput>DontUse</CreateOnInput>")
        X(f"{i}<SearchStringModeOnInputByString>Begin</SearchStringModeOnInputByString>")
        X(f"{i}<FullTextSearchOnInputByString>DontUse</FullTextSearchOnInputByString>")
        X(f"{i}<ChoiceDataGetModeOnInputByString>Directly</ChoiceDataGetModeOnInputByString>")
        X(f"{i}<DefaultObjectForm/>")
        X(f"{i}<DefaultListForm/>")
        X(f"{i}<DefaultChoiceForm/>")
        X(f"{i}<AuxiliaryObjectForm/>")
        X(f"{i}<AuxiliaryListForm/>")
        X(f"{i}<AuxiliaryChoiceForm/>")
        posting = get_enum_prop("Posting", "posting", "Allow")
        real_time_posting = get_enum_prop("RealTimePosting", "realTimePosting", "Deny")
        reg_records_deletion = get_enum_prop("RegisterRecordsDeletion", "registerRecordsDeletion", "AutoDelete")
        reg_records_writing = get_enum_prop(
            "RegisterRecordsWritingOnPost", "registerRecordsWritingOnPost", "WriteModified"
        )
        sequence_filling = str(defn["sequenceFilling"]) if defn.get("sequenceFilling") else "AutoFill"
        post_in_priv = "false" if defn.get("postInPrivilegedMode") is False else "true"
        unpost_in_priv = "false" if defn.get("unpostInPrivilegedMode") is False else "true"
        X(f"{i}<Posting>{posting}</Posting>")
        X(f"{i}<RealTimePosting>{real_time_posting}</RealTimePosting>")
        X(f"{i}<RegisterRecordsDeletion>{reg_records_deletion}</RegisterRecordsDeletion>")
        X(f"{i}<RegisterRecordsWritingOnPost>{reg_records_writing}</RegisterRecordsWritingOnPost>")
        X(f"{i}<SequenceFilling>{sequence_filling}</SequenceFilling>")
        # RegisterRecords
        reg_records = []
        if defn.get("registerRecords"):
            for rr in defn["registerRecords"]:
                rr_str = str(rr)
                if "." in rr_str:
                    dot_idx = rr_str.index(".")
                    rr_prefix = rr_str[:dot_idx]
                    rr_suffix = rr_str[dot_idx + 1 :]
                    if rr_prefix in object_type_synonyms:
                        rr_prefix = object_type_synonyms[rr_prefix]
                    reg_records.append(f"{rr_prefix}.{rr_suffix}")
                else:
                    reg_records.append(rr_str)
        if reg_records:
            X(f"{i}<RegisterRecords>")
            for rr in reg_records:
                X(f'{i}\t<xr:Item xsi:type="xr:MDObjectRef">{rr}</xr:Item>')
            X(f"{i}</RegisterRecords>")
        else:
            X(f"{i}<RegisterRecords/>")
        X(f"{i}<PostInPrivilegedMode>{post_in_priv}</PostInPrivilegedMode>")
        X(f"{i}<UnpostInPrivilegedMode>{unpost_in_priv}</UnpostInPrivilegedMode>")
        X(f"{i}<IncludeHelpInContents>false</IncludeHelpInContents>")
        X(f"{i}<DataLockFields/>")
        data_lock_control_mode = get_enum_prop("DataLockControlMode", "dataLockControlMode", "Automatic")
        X(f"{i}<DataLockControlMode>{data_lock_control_mode}</DataLockControlMode>")
        full_text_search = get_enum_prop("FullTextSearch", "fullTextSearch", "Use")
        X(f"{i}<FullTextSearch>{full_text_search}</FullTextSearch>")
        X(f"{i}<ObjectPresentation/>")
        X(f"{i}<ExtendedObjectPresentation/>")
        X(f"{i}<ListPresentation/>")
        X(f"{i}<ExtendedListPresentation/>")
        X(f"{i}<Explanation/>")
        X(f"{i}<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>")
        X(f"{i}<DataHistory>DontUse</DataHistory>")
        X(f"{i}<UpdateDataHistoryImmediatelyAfterWrite>false</UpdateDataHistoryImmediatelyAfterWrite>")
        X(f"{i}<ExecuteAfterWriteDataHistoryVersionProcessing>false</ExecuteAfterWriteDataHistoryVersionProcessing>")

    def emit_enum_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        X(f"{i}<UseStandardCommands>false</UseStandardCommands>")
        emit_standard_attributes(i, "Enum")
        X(f"{i}<Characteristics/>")
        X(f"{i}<QuickChoice>true</QuickChoice>")
        X(f"{i}<ChoiceMode>BothWays</ChoiceMode>")
        X(f"{i}<DefaultListForm/>")
        X(f"{i}<DefaultChoiceForm/>")
        X(f"{i}<AuxiliaryListForm/>")
        X(f"{i}<AuxiliaryChoiceForm/>")
        X(f"{i}<ListPresentation/>")
        X(f"{i}<ExtendedListPresentation/>")
        X(f"{i}<Explanation/>")
        X(f"{i}<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>")

    def emit_constant_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        # Type
        value_type = build_type_str(defn) or "String"
        emit_value_type(i, value_type)
        X(f"{i}<UseStandardCommands>true</UseStandardCommands>")
        X(f"{i}<DefaultForm/>")
        X(f"{i}<ExtendedPresentation/>")
        X(f"{i}<Explanation/>")
        X(f"{i}<PasswordMode>false</PasswordMode>")
        X(f"{i}<Format/>")
        X(f"{i}<EditFormat/>")
        X(f"{i}<ToolTip/>")
        X(f"{i}<MarkNegatives>false</MarkNegatives>")
        X(f"{i}<Mask/>")
        X(f"{i}<MultiLine>false</MultiLine>")
        X(f"{i}<ExtendedEdit>false</ExtendedEdit>")
        X(f'{i}<MinValue xsi:nil="true"/>')
        X(f'{i}<MaxValue xsi:nil="true"/>')
        X(f"{i}<FillChecking>DontCheck</FillChecking>")
        X(f"{i}<ChoiceFoldersAndItems>Items</ChoiceFoldersAndItems>")
        X(f"{i}<ChoiceParameterLinks/>")
        X(f"{i}<ChoiceParameters/>")
        X(f"{i}<QuickChoice>Auto</QuickChoice>")
        X(f"{i}<ChoiceForm/>")
        X(f"{i}<LinkByType/>")
        X(f"{i}<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>")
        data_lock_control_mode = get_enum_prop("DataLockControlMode", "dataLockControlMode", "Automatic")
        X(f"{i}<DataLockControlMode>{data_lock_control_mode}</DataLockControlMode>")
        X(f"{i}<DataHistory>DontUse</DataHistory>")
        X(f"{i}<UpdateDataHistoryImmediatelyAfterWrite>false</UpdateDataHistoryImmediatelyAfterWrite>")
        X(f"{i}<ExecuteAfterWriteDataHistoryVersionProcessing>false</ExecuteAfterWriteDataHistoryVersionProcessing>")

    def emit_information_register_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        X(f"{i}<UseStandardCommands>true</UseStandardCommands>")
        X(f"{i}<EditType>InDialog</EditType>")
        X(f"{i}<DefaultRecordForm/>")
        X(f"{i}<DefaultListForm/>")
        X(f"{i}<AuxiliaryRecordForm/>")
        X(f"{i}<AuxiliaryListForm/>")
        emit_standard_attributes(i, "InformationRegister")
        periodicity = get_enum_prop("InformationRegisterPeriodicity", "periodicity", "Nonperiodical")
        write_mode = get_enum_prop("WriteMode", "writeMode", "Independent")
        main_filter_on_period = "false"
        if defn.get("mainFilterOnPeriod") is not None:
            main_filter_on_period = "true" if defn["mainFilterOnPeriod"] is True else "false"
        elif periodicity != "Nonperiodical":
            main_filter_on_period = "true"
        X(f"{i}<InformationRegisterPeriodicity>{periodicity}</InformationRegisterPeriodicity>")
        X(f"{i}<WriteMode>{write_mode}</WriteMode>")
        X(f"{i}<MainFilterOnPeriod>{main_filter_on_period}</MainFilterOnPeriod>")
        X(f"{i}<IncludeHelpInContents>false</IncludeHelpInContents>")
        data_lock_control_mode = get_enum_prop("DataLockControlMode", "dataLockControlMode", "Automatic")
        X(f"{i}<DataLockControlMode>{data_lock_control_mode}</DataLockControlMode>")
        full_text_search = get_enum_prop("FullTextSearch", "fullTextSearch", "Use")
        X(f"{i}<FullTextSearch>{full_text_search}</FullTextSearch>")
        X(f"{i}<EnableTotalsSliceFirst>false</EnableTotalsSliceFirst>")
        X(f"{i}<EnableTotalsSliceLast>false</EnableTotalsSliceLast>")
        X(f"{i}<RecordPresentation/>")
        X(f"{i}<ExtendedRecordPresentation/>")
        X(f"{i}<ListPresentation/>")
        X(f"{i}<ExtendedListPresentation/>")
        X(f"{i}<Explanation/>")
        X(f"{i}<DataHistory>DontUse</DataHistory>")
        X(f"{i}<UpdateDataHistoryImmediatelyAfterWrite>false</UpdateDataHistoryImmediatelyAfterWrite>")
        X(f"{i}<ExecuteAfterWriteDataHistoryVersionProcessing>false</ExecuteAfterWriteDataHistoryVersionProcessing>")

    def emit_accumulation_register_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        X(f"{i}<UseStandardCommands>true</UseStandardCommands>")
        X(f"{i}<DefaultListForm/>")
        X(f"{i}<AuxiliaryListForm/>")
        register_type = get_enum_prop("RegisterType", "registerType", "Balance")
        X(f"{i}<RegisterType>{register_type}</RegisterType>")
        X(f"{i}<IncludeHelpInContents>false</IncludeHelpInContents>")
        emit_standard_attributes(i, "AccumulationRegister")
        data_lock_control_mode = get_enum_prop("DataLockControlMode", "dataLockControlMode", "Automatic")
        X(f"{i}<DataLockControlMode>{data_lock_control_mode}</DataLockControlMode>")
        full_text_search = get_enum_prop("FullTextSearch", "fullTextSearch", "Use")
        X(f"{i}<FullTextSearch>{full_text_search}</FullTextSearch>")
        enable_totals_splitting = "false" if defn.get("enableTotalsSplitting") is False else "true"
        X(f"{i}<EnableTotalsSplitting>{enable_totals_splitting}</EnableTotalsSplitting>")
        X(f"{i}<ListPresentation/>")
        X(f"{i}<ExtendedListPresentation/>")
        X(f"{i}<Explanation/>")

    def emit_accounting_register_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        X(f"{i}<UseStandardCommands>true</UseStandardCommands>")
        X(f"{i}<DefaultListForm/>")
        X(f"{i}<AuxiliaryListForm/>")
        chart_of_accounts = str(defn["chartOfAccounts"]) if defn.get("chartOfAccounts") else ""
        if chart_of_accounts:
            X(f"{i}<ChartOfAccounts>{chart_of_accounts}</ChartOfAccounts>")
        else:
            X(f"{i}<ChartOfAccounts/>")
        correspondence = "true" if defn.get("correspondence") is True else "false"
        X(f"{i}<Correspondence>{correspondence}</Correspondence>")
        period_adj_len = str(defn["periodAdjustmentLength"]) if defn.get("periodAdjustmentLength") is not None else "0"
        X(f"{i}<PeriodAdjustmentLength>{period_adj_len}</PeriodAdjustmentLength>")
        X(f"{i}<IncludeHelpInContents>false</IncludeHelpInContents>")
        emit_standard_attributes(i, "AccountingRegister")
        data_lock_control_mode = get_enum_prop("DataLockControlMode", "dataLockControlMode", "Automatic")
        X(f"{i}<DataLockControlMode>{data_lock_control_mode}</DataLockControlMode>")
        full_text_search = get_enum_prop("FullTextSearch", "fullTextSearch", "Use")
        X(f"{i}<FullTextSearch>{full_text_search}</FullTextSearch>")
        X(f"{i}<ListPresentation/>")
        X(f"{i}<ExtendedListPresentation/>")
        X(f"{i}<Explanation/>")

    def emit_calculation_register_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        X(f"{i}<UseStandardCommands>true</UseStandardCommands>")
        X(f"{i}<DefaultListForm/>")
        X(f"{i}<AuxiliaryListForm/>")
        chart_of_calc_types = str(defn["chartOfCalculationTypes"]) if defn.get("chartOfCalculationTypes") else ""
        if chart_of_calc_types:
            X(f"{i}<ChartOfCalculationTypes>{chart_of_calc_types}</ChartOfCalculationTypes>")
        else:
            X(f"{i}<ChartOfCalculationTypes/>")
        periodicity = get_enum_prop("InformationRegisterPeriodicity", "periodicity", "Month")
        X(f"{i}<Periodicity>{periodicity}</Periodicity>")
        action_period = "true" if defn.get("actionPeriod") is True else "false"
        X(f"{i}<ActionPeriod>{action_period}</ActionPeriod>")
        base_period = "true" if defn.get("basePeriod") is True else "false"
        X(f"{i}<BasePeriod>{base_period}</BasePeriod>")
        schedule = str(defn["schedule"]) if defn.get("schedule") else ""
        if schedule:
            X(f"{i}<Schedule>{schedule}</Schedule>")
        else:
            X(f"{i}<Schedule/>")
        schedule_value = str(defn["scheduleValue"]) if defn.get("scheduleValue") else ""
        if schedule_value:
            X(f"{i}<ScheduleValue>{schedule_value}</ScheduleValue>")
        else:
            X(f"{i}<ScheduleValue/>")
        schedule_date = str(defn["scheduleDate"]) if defn.get("scheduleDate") else ""
        if schedule_date:
            X(f"{i}<ScheduleDate>{schedule_date}</ScheduleDate>")
        else:
            X(f"{i}<ScheduleDate/>")
        X(f"{i}<IncludeHelpInContents>false</IncludeHelpInContents>")
        emit_standard_attributes(i, "CalculationRegister")
        data_lock_control_mode = get_enum_prop("DataLockControlMode", "dataLockControlMode", "Automatic")
        X(f"{i}<DataLockControlMode>{data_lock_control_mode}</DataLockControlMode>")
        full_text_search = get_enum_prop("FullTextSearch", "fullTextSearch", "Use")
        X(f"{i}<FullTextSearch>{full_text_search}</FullTextSearch>")
        X(f"{i}<ListPresentation/>")
        X(f"{i}<ExtendedListPresentation/>")
        X(f"{i}<Explanation/>")

    def emit_chart_of_accounts_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        X(f"{i}<UseStandardCommands>true</UseStandardCommands>")
        ext_dim_types = str(defn["extDimensionTypes"]) if defn.get("extDimensionTypes") else ""
        if ext_dim_types:
            X(f"{i}<ExtDimensionTypes>{ext_dim_types}</ExtDimensionTypes>")
        else:
            X(f"{i}<ExtDimensionTypes/>")
        max_ext_dim = str(defn["maxExtDimensionCount"]) if defn.get("maxExtDimensionCount") is not None else "3"
        X(f"{i}<MaxExtDimensionCount>{max_ext_dim}</MaxExtDimensionCount>")
        code_mask = str(defn["codeMask"]) if defn.get("codeMask") else ""
        if code_mask:
            X(f"{i}<CodeMask>{esc_xml(code_mask)}</CodeMask>")
        else:
            X(f"{i}<CodeMask/>")
        code_length = str(defn["codeLength"]) if defn.get("codeLength") is not None else "8"
        description_length = str(defn["descriptionLength"]) if defn.get("descriptionLength") is not None else "120"
        code_series = str(defn["codeSeries"]) if defn.get("codeSeries") else "WholeChartOfAccounts"
        auto_order = "false" if defn.get("autoOrderByCode") is False else "true"
        order_length = str(defn["orderLength"]) if defn.get("orderLength") is not None else "5"
        X(f"{i}<CodeLength>{code_length}</CodeLength>")
        X(f"{i}<DescriptionLength>{description_length}</DescriptionLength>")
        X(f"{i}<CodeSeries>{code_series}</CodeSeries>")
        X(f"{i}<CheckUnique>false</CheckUnique>")
        X(f"{i}<DefaultPresentation>AsDescription</DefaultPresentation>")
        X(f"{i}<AutoOrderByCode>{auto_order}</AutoOrderByCode>")
        X(f"{i}<OrderLength>{order_length}</OrderLength>")
        X(f"{i}<EditType>InDialog</EditType>")
        emit_standard_attributes(i, "ChartOfAccounts")
        X(f"{i}<StandardTabularSections>")
        X(f'{i}\t<xr:StandardTabularSection name="ExtDimensionTypes">')
        X(f"{i}\t\t<xr:StandardAttributes>")
        for st_attr in ["TurnoversOnly", "Predefined", "ExtDimensionType", "LineNumber"]:
            emit_standard_attribute(f"{i}\t\t\t", st_attr)
        X(f"{i}\t\t</xr:StandardAttributes>")
        X(f"{i}\t</xr:StandardTabularSection>")
        X(f"{i}</StandardTabularSections>")
        X(f"{i}<Characteristics/>")
        X(f"{i}<PredefinedDataUpdate>Auto</PredefinedDataUpdate>")
        X(f"{i}<QuickChoice>true</QuickChoice>")
        X(f"{i}<ChoiceMode>BothWays</ChoiceMode>")
        emit_input_by_string(i, "ChartOfAccounts", [("Description", description_length), ("Code", code_length)])
        X(f"{i}<SearchStringModeOnInputByString>Begin</SearchStringModeOnInputByString>")
        X(f"{i}<FullTextSearchOnInputByString>DontUse</FullTextSearchOnInputByString>")
        X(f"{i}<ChoiceDataGetModeOnInputByString>Directly</ChoiceDataGetModeOnInputByString>")
        X(f"{i}<DefaultObjectForm/>")
        X(f"{i}<DefaultListForm/>")
        X(f"{i}<DefaultChoiceForm/>")
        X(f"{i}<AuxiliaryObjectForm/>")
        X(f"{i}<AuxiliaryListForm/>")
        X(f"{i}<AuxiliaryChoiceForm/>")
        X(f"{i}<IncludeHelpInContents>false</IncludeHelpInContents>")
        X(f"{i}<BasedOn/>")
        X(f"{i}<DataLockFields/>")
        data_lock_control_mode = get_enum_prop("DataLockControlMode", "dataLockControlMode", "Automatic")
        X(f"{i}<DataLockControlMode>{data_lock_control_mode}</DataLockControlMode>")
        full_text_search = get_enum_prop("FullTextSearch", "fullTextSearch", "Use")
        X(f"{i}<FullTextSearch>{full_text_search}</FullTextSearch>")
        X(f"{i}<ObjectPresentation/>")
        X(f"{i}<ExtendedObjectPresentation/>")
        X(f"{i}<ListPresentation/>")
        X(f"{i}<ExtendedListPresentation/>")
        X(f"{i}<Explanation/>")
        X(f"{i}<CreateOnInput>DontUse</CreateOnInput>")
        X(f"{i}<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>")
        X(f"{i}<DataHistory>DontUse</DataHistory>")
        X(f"{i}<UpdateDataHistoryImmediatelyAfterWrite>false</UpdateDataHistoryImmediatelyAfterWrite>")
        X(f"{i}<ExecuteAfterWriteDataHistoryVersionProcessing>false</ExecuteAfterWriteDataHistoryVersionProcessing>")

    def emit_chart_of_characteristic_types_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        X(f"{i}<UseStandardCommands>true</UseStandardCommands>")
        code_length = str(defn["codeLength"]) if defn.get("codeLength") is not None else "9"
        description_length = str(defn["descriptionLength"]) if defn.get("descriptionLength") is not None else "25"
        code_allowed_length = get_enum_prop("CodeAllowedLength", "codeAllowedLength", "Variable")
        autonumbering = "false" if defn.get("autonumbering") is False else "true"
        check_unique = "true" if defn.get("checkUnique") is True else "false"
        X(f"{i}<CodeLength>{code_length}</CodeLength>")
        X(f"{i}<CodeAllowedLength>{code_allowed_length}</CodeAllowedLength>")
        X(f"{i}<DescriptionLength>{description_length}</DescriptionLength>")
        X(f"{i}<CheckUnique>{check_unique}</CheckUnique>")
        X(f"{i}<Autonumbering>{autonumbering}</Autonumbering>")
        X(f"{i}<DefaultPresentation>AsDescription</DefaultPresentation>")
        char_ext_values = str(defn["characteristicExtValues"]) if defn.get("characteristicExtValues") else ""
        if char_ext_values:
            X(f"{i}<CharacteristicExtValues>{char_ext_values}</CharacteristicExtValues>")
        else:
            X(f"{i}<CharacteristicExtValues/>")
        emit_value_type(i, " + ".join(defn.get("valueTypes") or ["Boolean", "String(100)", "Number(15,2)", "DateTime"]))
        hierarchical = "true" if defn.get("hierarchical") is True else "false"
        X(f"{i}<Hierarchical>{hierarchical}</Hierarchical>")
        X(f"{i}<FoldersOnTop>true</FoldersOnTop>")
        emit_standard_attributes(i, "ChartOfCharacteristicTypes")
        X(f"{i}<Characteristics/>")
        X(f"{i}<PredefinedDataUpdate>Auto</PredefinedDataUpdate>")
        X(f"{i}<EditType>InDialog</EditType>")
        X(f"{i}<QuickChoice>true</QuickChoice>")
        X(f"{i}<ChoiceMode>BothWays</ChoiceMode>")
        emit_input_by_string(
            i, "ChartOfCharacteristicTypes", [("Description", description_length), ("Code", code_length)]
        )
        X(f"{i}<SearchStringModeOnInputByString>Begin</SearchStringModeOnInputByString>")
        X(f"{i}<FullTextSearchOnInputByString>DontUse</FullTextSearchOnInputByString>")
        X(f"{i}<ChoiceDataGetModeOnInputByString>Directly</ChoiceDataGetModeOnInputByString>")
        X(f"{i}<DefaultObjectForm/>")
        X(f"{i}<DefaultFolderForm/>")
        X(f"{i}<DefaultListForm/>")
        X(f"{i}<DefaultChoiceForm/>")
        X(f"{i}<DefaultFolderChoiceForm/>")
        X(f"{i}<AuxiliaryObjectForm/>")
        X(f"{i}<AuxiliaryFolderForm/>")
        X(f"{i}<AuxiliaryListForm/>")
        X(f"{i}<AuxiliaryChoiceForm/>")
        X(f"{i}<AuxiliaryFolderChoiceForm/>")
        X(f"{i}<IncludeHelpInContents>false</IncludeHelpInContents>")
        X(f"{i}<BasedOn/>")
        X(f"{i}<DataLockFields/>")
        data_lock_control_mode = get_enum_prop("DataLockControlMode", "dataLockControlMode", "Automatic")
        X(f"{i}<DataLockControlMode>{data_lock_control_mode}</DataLockControlMode>")
        full_text_search = get_enum_prop("FullTextSearch", "fullTextSearch", "Use")
        X(f"{i}<FullTextSearch>{full_text_search}</FullTextSearch>")
        X(f"{i}<ObjectPresentation/>")
        X(f"{i}<ExtendedObjectPresentation/>")
        X(f"{i}<ListPresentation/>")
        X(f"{i}<ExtendedListPresentation/>")
        X(f"{i}<Explanation/>")
        X(f"{i}<CreateOnInput>DontUse</CreateOnInput>")
        X(f"{i}<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>")
        X(f"{i}<DataHistory>DontUse</DataHistory>")
        X(f"{i}<UpdateDataHistoryImmediatelyAfterWrite>false</UpdateDataHistoryImmediatelyAfterWrite>")
        X(f"{i}<ExecuteAfterWriteDataHistoryVersionProcessing>false</ExecuteAfterWriteDataHistoryVersionProcessing>")

    def emit_chart_of_calculation_types_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        X(f"{i}<UseStandardCommands>true</UseStandardCommands>")
        code_length = str(defn["codeLength"]) if defn.get("codeLength") is not None else "9"
        description_length = str(defn["descriptionLength"]) if defn.get("descriptionLength") is not None else "25"
        code_type = get_enum_prop("CodeType", "codeType", "String")
        code_allowed_length = get_enum_prop("CodeAllowedLength", "codeAllowedLength", "Variable")
        X(f"{i}<CodeLength>{code_length}</CodeLength>")
        X(f"{i}<CodeType>{code_type}</CodeType>")
        X(f"{i}<CodeAllowedLength>{code_allowed_length}</CodeAllowedLength>")
        X(f"{i}<DescriptionLength>{description_length}</DescriptionLength>")
        X(f"{i}<DefaultPresentation>AsDescription</DefaultPresentation>")
        dependence = get_enum_prop("DependenceOnCalculationTypes", "dependenceOnCalculationTypes", "DontUse")
        X(f"{i}<DependenceOnCalculationTypes>{dependence}</DependenceOnCalculationTypes>")
        base_types = list(defn.get("baseCalculationTypes", []))
        if base_types:
            X(f"{i}<BaseCalculationTypes>")
            for bt in base_types:
                X(f'{i}\t<xr:Item xsi:type="xr:MDObjectRef">{bt}</xr:Item>')
            X(f"{i}</BaseCalculationTypes>")
        else:
            X(f"{i}<BaseCalculationTypes/>")
        action_period_use = "true" if defn.get("actionPeriodUse") is True else "false"
        X(f"{i}<ActionPeriodUse>{action_period_use}</ActionPeriodUse>")
        emit_standard_attributes(i, "ChartOfCalculationTypes")
        X(f"{i}<Characteristics/>")
        X(f"{i}<PredefinedDataUpdate>Auto</PredefinedDataUpdate>")
        X(f"{i}<EditType>InDialog</EditType>")
        X(f"{i}<QuickChoice>true</QuickChoice>")
        X(f"{i}<ChoiceMode>BothWays</ChoiceMode>")
        emit_input_by_string(i, "ChartOfCalculationTypes", [("Description", description_length), ("Code", code_length)])
        X(f"{i}<SearchStringModeOnInputByString>Begin</SearchStringModeOnInputByString>")
        X(f"{i}<FullTextSearchOnInputByString>DontUse</FullTextSearchOnInputByString>")
        X(f"{i}<ChoiceDataGetModeOnInputByString>Directly</ChoiceDataGetModeOnInputByString>")
        X(f"{i}<DefaultObjectForm/>")
        X(f"{i}<DefaultListForm/>")
        X(f"{i}<DefaultChoiceForm/>")
        X(f"{i}<AuxiliaryObjectForm/>")
        X(f"{i}<AuxiliaryListForm/>")
        X(f"{i}<AuxiliaryChoiceForm/>")
        X(f"{i}<IncludeHelpInContents>false</IncludeHelpInContents>")
        X(f"{i}<BasedOn/>")
        X(f"{i}<DataLockFields/>")
        data_lock_control_mode = get_enum_prop("DataLockControlMode", "dataLockControlMode", "Automatic")
        X(f"{i}<DataLockControlMode>{data_lock_control_mode}</DataLockControlMode>")
        full_text_search = get_enum_prop("FullTextSearch", "fullTextSearch", "Use")
        X(f"{i}<FullTextSearch>{full_text_search}</FullTextSearch>")
        X(f"{i}<ObjectPresentation/>")
        X(f"{i}<ExtendedObjectPresentation/>")
        X(f"{i}<ListPresentation/>")
        X(f"{i}<ExtendedListPresentation/>")
        X(f"{i}<Explanation/>")
        X(f"{i}<CreateOnInput>DontUse</CreateOnInput>")
        X(f"{i}<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>")

    def emit_business_process_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        X(f"{i}<UseStandardCommands>true</UseStandardCommands>")
        edit_type = get_enum_prop("EditType", "editType", "InDialog")
        X(f"{i}<EditType>{edit_type}</EditType>")
        number_type = get_enum_prop("NumberType", "numberType", "String")
        number_length = str(defn["numberLength"]) if defn.get("numberLength") is not None else "11"
        number_allowed_length = get_enum_prop("NumberAllowedLength", "numberAllowedLength", "Variable")
        check_unique = "false" if defn.get("checkUnique") is False else "true"
        autonumbering = "false" if defn.get("autonumbering") is False else "true"
        X(f"{i}<NumberType>{number_type}</NumberType>")
        X(f"{i}<NumberLength>{number_length}</NumberLength>")
        X(f"{i}<NumberAllowedLength>{number_allowed_length}</NumberAllowedLength>")
        X(f"{i}<CheckUnique>{check_unique}</CheckUnique>")
        X(f"{i}<Autonumbering>{autonumbering}</Autonumbering>")
        emit_standard_attributes(i, "BusinessProcess")
        X(f"{i}<Characteristics/>")
        task_ref = str(defn["task"]) if defn.get("task") else ""
        if task_ref:
            X(f"{i}<Task>{task_ref}</Task>")
        else:
            X(f"{i}<Task/>")
        X(f"{i}<BasedOn/>")
        X(f"{i}<InputByString>")
        X(f"{i}\t<xr:Field>BusinessProcess.{obj_name}.StandardAttribute.Number</xr:Field>")
        X(f"{i}</InputByString>")
        X(f"{i}<CreateOnInput>DontUse</CreateOnInput>")
        X(f"{i}<SearchStringModeOnInputByString>Begin</SearchStringModeOnInputByString>")
        X(f"{i}<FullTextSearchOnInputByString>DontUse</FullTextSearchOnInputByString>")
        X(f"{i}<ChoiceDataGetModeOnInputByString>Directly</ChoiceDataGetModeOnInputByString>")
        X(f"{i}<DefaultObjectForm/>")
        X(f"{i}<DefaultListForm/>")
        X(f"{i}<DefaultChoiceForm/>")
        X(f"{i}<AuxiliaryObjectForm/>")
        X(f"{i}<AuxiliaryListForm/>")
        X(f"{i}<AuxiliaryChoiceForm/>")
        X(f"{i}<IncludeHelpInContents>false</IncludeHelpInContents>")
        X(f"{i}<DataLockFields/>")
        data_lock_control_mode = get_enum_prop("DataLockControlMode", "dataLockControlMode", "Automatic")
        X(f"{i}<DataLockControlMode>{data_lock_control_mode}</DataLockControlMode>")
        full_text_search = get_enum_prop("FullTextSearch", "fullTextSearch", "Use")
        X(f"{i}<FullTextSearch>{full_text_search}</FullTextSearch>")
        X(f"{i}<ObjectPresentation/>")
        X(f"{i}<ExtendedObjectPresentation/>")
        X(f"{i}<ListPresentation/>")
        X(f"{i}<ExtendedListPresentation/>")
        X(f"{i}<Explanation/>")
        X(f"{i}<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>")
        X(f"{i}<DataHistory>DontUse</DataHistory>")
        X(f"{i}<UpdateDataHistoryImmediatelyAfterWrite>false</UpdateDataHistoryImmediatelyAfterWrite>")
        X(f"{i}<ExecuteAfterWriteDataHistoryVersionProcessing>false</ExecuteAfterWriteDataHistoryVersionProcessing>")

    def emit_task_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        X(f"{i}<UseStandardCommands>true</UseStandardCommands>")
        number_type = get_enum_prop("NumberType", "numberType", "String")
        number_length = str(defn["numberLength"]) if defn.get("numberLength") is not None else "14"
        number_allowed_length = get_enum_prop("NumberAllowedLength", "numberAllowedLength", "Variable")
        check_unique = "false" if defn.get("checkUnique") is False else "true"
        autonumbering = "false" if defn.get("autonumbering") is False else "true"
        task_number_auto_prefix = (
            str(defn["taskNumberAutoPrefix"]) if defn.get("taskNumberAutoPrefix") else "BusinessProcessNumber"
        )
        description_length = str(defn["descriptionLength"]) if defn.get("descriptionLength") is not None else "150"
        X(f"{i}<NumberType>{number_type}</NumberType>")
        X(f"{i}<NumberLength>{number_length}</NumberLength>")
        X(f"{i}<NumberAllowedLength>{number_allowed_length}</NumberAllowedLength>")
        X(f"{i}<CheckUnique>{check_unique}</CheckUnique>")
        X(f"{i}<Autonumbering>{autonumbering}</Autonumbering>")
        X(f"{i}<TaskNumberAutoPrefix>{task_number_auto_prefix}</TaskNumberAutoPrefix>")
        X(f"{i}<DescriptionLength>{description_length}</DescriptionLength>")
        addressing = str(defn["addressing"]) if defn.get("addressing") else ""
        if addressing:
            X(f"{i}<Addressing>{addressing}</Addressing>")
        else:
            X(f"{i}<Addressing/>")
        main_addressing = str(defn["mainAddressingAttribute"]) if defn.get("mainAddressingAttribute") else ""
        if main_addressing:
            X(f"{i}<MainAddressingAttribute>{main_addressing}</MainAddressingAttribute>")
        else:
            X(f"{i}<MainAddressingAttribute/>")
        current_performer = str(defn["currentPerformer"]) if defn.get("currentPerformer") else ""
        if current_performer:
            X(f"{i}<CurrentPerformer>{current_performer}</CurrentPerformer>")
        else:
            X(f"{i}<CurrentPerformer/>")
        emit_standard_attributes(i, "Task")
        X(f"{i}<Characteristics/>")
        X(f"{i}<BasedOn/>")
        X(f"{i}<InputByString>")
        X(f"{i}\t<xr:Field>Task.{obj_name}.StandardAttribute.Number</xr:Field>")
        X(f"{i}</InputByString>")
        X(f"{i}<CreateOnInput>DontUse</CreateOnInput>")
        X(f"{i}<SearchStringModeOnInputByString>Begin</SearchStringModeOnInputByString>")
        X(f"{i}<FullTextSearchOnInputByString>DontUse</FullTextSearchOnInputByString>")
        X(f"{i}<ChoiceDataGetModeOnInputByString>Directly</ChoiceDataGetModeOnInputByString>")
        X(f"{i}<DefaultObjectForm/>")
        X(f"{i}<DefaultListForm/>")
        X(f"{i}<DefaultChoiceForm/>")
        X(f"{i}<AuxiliaryObjectForm/>")
        X(f"{i}<AuxiliaryListForm/>")
        X(f"{i}<AuxiliaryChoiceForm/>")
        X(f"{i}<IncludeHelpInContents>false</IncludeHelpInContents>")
        X(f"{i}<DataLockFields/>")
        data_lock_control_mode = get_enum_prop("DataLockControlMode", "dataLockControlMode", "Automatic")
        X(f"{i}<DataLockControlMode>{data_lock_control_mode}</DataLockControlMode>")
        full_text_search = get_enum_prop("FullTextSearch", "fullTextSearch", "Use")
        X(f"{i}<FullTextSearch>{full_text_search}</FullTextSearch>")
        X(f"{i}<ObjectPresentation/>")
        X(f"{i}<ExtendedObjectPresentation/>")
        X(f"{i}<ListPresentation/>")
        X(f"{i}<ExtendedListPresentation/>")
        X(f"{i}<Explanation/>")
        X(f"{i}<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>")
        X(f"{i}<DataHistory>DontUse</DataHistory>")
        X(f"{i}<UpdateDataHistoryImmediatelyAfterWrite>false</UpdateDataHistoryImmediatelyAfterWrite>")
        X(f"{i}<ExecuteAfterWriteDataHistoryVersionProcessing>false</ExecuteAfterWriteDataHistoryVersionProcessing>")

    def emit_exchange_plan_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        X(f"{i}<UseStandardCommands>true</UseStandardCommands>")
        code_length = str(defn["codeLength"]) if defn.get("codeLength") is not None else "9"
        description_length = str(defn["descriptionLength"]) if defn.get("descriptionLength") is not None else "100"
        code_allowed_length = get_enum_prop("CodeAllowedLength", "codeAllowedLength", "Variable")
        X(f"{i}<CodeLength>{code_length}</CodeLength>")
        X(f"{i}<CodeAllowedLength>{code_allowed_length}</CodeAllowedLength>")
        X(f"{i}<DescriptionLength>{description_length}</DescriptionLength>")
        X(f"{i}<DefaultPresentation>AsDescription</DefaultPresentation>")
        X(f"{i}<EditType>InDialog</EditType>")
        emit_standard_attributes(i, "ExchangePlan")
        distributed = "true" if defn.get("distributedInfoBase") is True else "false"
        include_ext = "true" if defn.get("includeConfigurationExtensions") is True else "false"
        X(f"{i}<DistributedInfoBase>{distributed}</DistributedInfoBase>")
        X(f"{i}<IncludeConfigurationExtensions>{include_ext}</IncludeConfigurationExtensions>")
        X(f"{i}<BasedOn/>")
        X(f"{i}<QuickChoice>true</QuickChoice>")
        X(f"{i}<ChoiceMode>BothWays</ChoiceMode>")
        emit_input_by_string(i, "ExchangePlan", [("Description", description_length), ("Code", code_length)])
        X(f"{i}<SearchStringModeOnInputByString>Begin</SearchStringModeOnInputByString>")
        X(f"{i}<FullTextSearchOnInputByString>DontUse</FullTextSearchOnInputByString>")
        X(f"{i}<ChoiceDataGetModeOnInputByString>Directly</ChoiceDataGetModeOnInputByString>")
        X(f"{i}<DefaultObjectForm/>")
        X(f"{i}<DefaultListForm/>")
        X(f"{i}<DefaultChoiceForm/>")
        X(f"{i}<AuxiliaryObjectForm/>")
        X(f"{i}<AuxiliaryListForm/>")
        X(f"{i}<AuxiliaryChoiceForm/>")
        X(f"{i}<IncludeHelpInContents>false</IncludeHelpInContents>")
        X(f"{i}<DataLockFields/>")
        data_lock_control_mode = get_enum_prop("DataLockControlMode", "dataLockControlMode", "Automatic")
        X(f"{i}<DataLockControlMode>{data_lock_control_mode}</DataLockControlMode>")
        full_text_search = get_enum_prop("FullTextSearch", "fullTextSearch", "Use")
        X(f"{i}<FullTextSearch>{full_text_search}</FullTextSearch>")
        X(f"{i}<ObjectPresentation/>")
        X(f"{i}<ExtendedObjectPresentation/>")
        X(f"{i}<ListPresentation/>")
        X(f"{i}<ExtendedListPresentation/>")
        X(f"{i}<Explanation/>")
        X(f"{i}<CreateOnInput>DontUse</CreateOnInput>")
        X(f"{i}<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>")
        X(f"{i}<DataHistory>DontUse</DataHistory>")
        X(f"{i}<UpdateDataHistoryImmediatelyAfterWrite>false</UpdateDataHistoryImmediatelyAfterWrite>")
        X(f"{i}<ExecuteAfterWriteDataHistoryVersionProcessing>false</ExecuteAfterWriteDataHistoryVersionProcessing>")

    def emit_report_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        X(f"{i}<UseStandardCommands>true</UseStandardCommands>")
        default_form = str(defn["defaultForm"]) if defn.get("defaultForm") else ""
        if default_form:
            X(f"{i}<DefaultForm>{default_form}</DefaultForm>")
        else:
            X(f"{i}<DefaultForm/>")
        aux_form = str(defn["auxiliaryForm"]) if defn.get("auxiliaryForm") else ""
        if aux_form:
            X(f"{i}<AuxiliaryForm>{aux_form}</AuxiliaryForm>")
        else:
            X(f"{i}<AuxiliaryForm/>")
        main_dcs = str(defn["mainDataCompositionSchema"]) if defn.get("mainDataCompositionSchema") else ""
        if main_dcs:
            X(f"{i}<MainDataCompositionSchema>{main_dcs}</MainDataCompositionSchema>")
        else:
            X(f"{i}<MainDataCompositionSchema/>")
        def_settings = str(defn["defaultSettingsForm"]) if defn.get("defaultSettingsForm") else ""
        if def_settings:
            X(f"{i}<DefaultSettingsForm>{def_settings}</DefaultSettingsForm>")
        else:
            X(f"{i}<DefaultSettingsForm/>")
        aux_settings = str(defn["auxiliarySettingsForm"]) if defn.get("auxiliarySettingsForm") else ""
        if aux_settings:
            X(f"{i}<AuxiliarySettingsForm>{aux_settings}</AuxiliarySettingsForm>")
        else:
            X(f"{i}<AuxiliarySettingsForm/>")
        def_variant = str(defn["defaultVariantForm"]) if defn.get("defaultVariantForm") else ""
        if def_variant:
            X(f"{i}<DefaultVariantForm>{def_variant}</DefaultVariantForm>")
        else:
            X(f"{i}<DefaultVariantForm/>")
        X(f"{i}<VariantsStorage/>")
        X(f"{i}<SettingsStorage/>")
        X(f"{i}<IncludeHelpInContents>false</IncludeHelpInContents>")
        X(f"{i}<ExtendedPresentation/>")
        X(f"{i}<Explanation/>")

    def emit_data_processor_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        X(f"{i}<UseStandardCommands>false</UseStandardCommands>")
        default_form = str(defn["defaultForm"]) if defn.get("defaultForm") else ""
        if default_form:
            X(f"{i}<DefaultForm>{default_form}</DefaultForm>")
        else:
            X(f"{i}<DefaultForm/>")
        aux_form = str(defn["auxiliaryForm"]) if defn.get("auxiliaryForm") else ""
        if aux_form:
            X(f"{i}<AuxiliaryForm>{aux_form}</AuxiliaryForm>")
        else:
            X(f"{i}<AuxiliaryForm/>")
        X(f"{i}<IncludeHelpInContents>false</IncludeHelpInContents>")
        X(f"{i}<ExtendedPresentation/>")
        X(f"{i}<Explanation/>")

    def emit_document_journal_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        default_form = str(defn["defaultForm"]) if defn.get("defaultForm") else ""
        if default_form:
            X(f"{i}<DefaultForm>{default_form}</DefaultForm>")
        else:
            X(f"{i}<DefaultForm/>")
        aux_form = str(defn["auxiliaryForm"]) if defn.get("auxiliaryForm") else ""
        if aux_form:
            X(f"{i}<AuxiliaryForm>{aux_form}</AuxiliaryForm>")
        else:
            X(f"{i}<AuxiliaryForm/>")
        X(f"{i}<UseStandardCommands>true</UseStandardCommands>")
        reg_docs = list(defn.get("registeredDocuments", []))
        if reg_docs:
            X(f"{i}<RegisteredDocuments>")
            for rd in reg_docs:
                rd_str = str(rd)
                if "." in rd_str:
                    dot_idx = rd_str.index(".")
                    rd_prefix = rd_str[:dot_idx]
                    rd_suffix = rd_str[dot_idx + 1 :]
                    if rd_prefix in object_type_synonyms:
                        rd_prefix = object_type_synonyms[rd_prefix]
                    rd_str = f"{rd_prefix}.{rd_suffix}"
                X(f'{i}\t<xr:Item xsi:type="xr:MDObjectRef">{rd_str}</xr:Item>')
            X(f"{i}</RegisteredDocuments>")
        else:
            X(f"{i}<RegisteredDocuments/>")
        emit_standard_attributes(i, "DocumentJournal")
        X(f"{i}<ListPresentation/>")
        X(f"{i}<ExtendedListPresentation/>")
        X(f"{i}<Explanation/>")

    def emit_common_module_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        context = str(defn["context"]) if defn.get("context") else ""
        global_val = "true" if defn.get("global") is True else "false"
        server = "false"
        server_call = "false"
        client_managed = "false"
        client_ordinary = "false"
        external_connection = "false"
        privileged = "false"
        if context == "server" or context == "serverCall":
            server = "true"
            server_call = "true"
        elif context == "client":
            client_managed = "true"
        elif context == "serverClient":
            server = "true"
            client_managed = "true"
        else:
            if defn.get("server") is True:
                server = "true"
            if defn.get("serverCall") is True:
                server_call = "true"
            if defn.get("clientManagedApplication") is True:
                client_managed = "true"
            if defn.get("clientOrdinaryApplication") is True:
                client_ordinary = "true"
            if defn.get("externalConnection") is True:
                external_connection = "true"
            if defn.get("privileged") is True:
                privileged = "true"
        X(f"{i}<Global>{global_val}</Global>")
        X(f"{i}<ClientManagedApplication>{client_managed}</ClientManagedApplication>")
        X(f"{i}<Server>{server}</Server>")
        X(f"{i}<ExternalConnection>{external_connection}</ExternalConnection>")
        X(f"{i}<ClientOrdinaryApplication>{client_ordinary}</ClientOrdinaryApplication>")
        X(f"{i}<ServerCall>{server_call}</ServerCall>")
        X(f"{i}<Privileged>{privileged}</Privileged>")
        return_values_reuse = get_enum_prop("ReturnValuesReuse", "returnValuesReuse", "DontUse")
        X(f"{i}<ReturnValuesReuse>{return_values_reuse}</ReturnValuesReuse>")

    def emit_common_command_properties(indent):
        # Property order of an own extension command saved by Designer 8.3.27
        # (Демо_ДиагностикаСеанса); the parameter type is filled after parsing.
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        X(f"{i}<Group>{esc_xml(defn.get('group', 'ActionsPanelTools'))}</Group>")
        X(f"{i}<Representation>{defn.get('representation', 'Auto')}</Representation>")
        emit_mltext(i, "ToolTip", defn.get("toolTip", ""))
        X(f"{i}<Picture/>")
        X(f"{i}<Shortcut/>")
        X(f"{i}<IncludeHelpInContents>false</IncludeHelpInContents>")
        X(f"{i}<CommandParameterType/>")
        X(f"{i}<ParameterUseMode>{defn.get('parameterUseMode', 'Single')}</ParameterUseMode>")
        X(f"{i}<ModifiesData>{'true' if defn.get('modifiesData') is True else 'false'}</ModifiesData>")
        X(f"{i}<OnMainServerUnavalableBehavior>Auto</OnMainServerUnavalableBehavior>")

    def emit_subsystem_properties(indent):
        # Property order of an own extension subsystem saved by Designer 8.3.27
        # (Демо_Диагностика); Content refers to objects registered in the same root.
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        X(f"{i}<IncludeHelpInContents>false</IncludeHelpInContents>")
        X(
            f"{i}<IncludeInCommandInterface>{'false' if defn.get('includeInCommandInterface') is False else 'true'}</IncludeInCommandInterface>"
        )
        X(f"{i}<UseOneCommand>{'true' if defn.get('useOneCommand') is True else 'false'}</UseOneCommand>")
        emit_mltext(i, "Explanation", defn.get("explanation", ""))
        if defn.get("picture"):
            X(f"{i}<Picture>")
            X(f"{i}\t<xr:Ref>{esc_xml(defn['picture'])}</xr:Ref>")
            X(f"{i}\t<xr:LoadTransparent>false</xr:LoadTransparent>")
            X(f"{i}</Picture>")
        else:
            X(f"{i}<Picture/>")
        if defn.get("content"):
            X(f"{i}<Content>")
            for item in defn["content"]:
                X(f'{i}\t<xr:Item xsi:type="xr:MDObjectRef">{esc_xml(item)}</xr:Item>')
            X(f"{i}</Content>")
        else:
            X(f"{i}<Content/>")

    def emit_scheduled_job_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        method_name = str(defn["methodName"]) if defn.get("methodName") else ""
        # Ensure CommonModule. prefix
        if method_name and not method_name.startswith("CommonModule."):
            method_name = f"CommonModule.{method_name}"
        X(f"{i}<MethodName>{esc_xml(method_name)}</MethodName>")
        description = str(defn["description"]) if defn.get("description") else synonym
        X(f"{i}<Description>{esc_xml(description)}</Description>")
        key = str(defn["key"]) if defn.get("key") else ""
        X(f"{i}<Key>{esc_xml(key)}</Key>")
        use = "true" if defn.get("use") is True else "false"
        X(f"{i}<Use>{use}</Use>")
        predefined = "true" if defn.get("predefined") is True else "false"
        X(f"{i}<Predefined>{predefined}</Predefined>")
        restart_count = str(defn["restartCountOnFailure"]) if defn.get("restartCountOnFailure") is not None else "3"
        restart_interval = (
            str(defn["restartIntervalOnFailure"]) if defn.get("restartIntervalOnFailure") is not None else "10"
        )
        X(f"{i}<RestartCountOnFailure>{restart_count}</RestartCountOnFailure>")
        X(f"{i}<RestartIntervalOnFailure>{restart_interval}</RestartIntervalOnFailure>")

    def emit_event_subscription_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        sources = list(defn.get("source", []))
        if sources:
            X(f"{i}<Source>")
            for src in sources:
                resolved = schema.normalize_type(str(src))
                X(f"{i}\t<v8:Type>cfg:{resolved}</v8:Type>")
            X(f"{i}</Source>")
        else:
            X(f"{i}<Source/>")
        event = str(defn["event"]) if defn.get("event") else "BeforeWrite"
        X(f"{i}<Event>{event}</Event>")
        handler = str(defn["handler"]) if defn.get("handler") else ""
        # Ensure CommonModule. prefix
        if handler and not handler.startswith("CommonModule."):
            handler = f"CommonModule.{handler}"
        X(f"{i}<Handler>{esc_xml(handler)}</Handler>")

    def emit_http_service_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        root_url = str(defn["rootURL"]) if defn.get("rootURL") else obj_name.lower()
        X(f"{i}<RootURL>{esc_xml(root_url)}</RootURL>")
        reuse_sessions = get_enum_prop("ReuseSessions", "reuseSessions", "DontUse")
        X(f"{i}<ReuseSessions>{reuse_sessions}</ReuseSessions>")
        session_max_age = str(defn["sessionMaxAge"]) if defn.get("sessionMaxAge") is not None else "20"
        X(f"{i}<SessionMaxAge>{session_max_age}</SessionMaxAge>")

    def emit_web_service_properties(indent):
        i = indent
        X(f"{i}<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext(i, "Synonym", synonym)
        X(f"{i}<Comment/>")
        namespace = str(defn["namespace"]) if defn.get("namespace") else ""
        X(f"{i}<Namespace>{esc_xml(namespace)}</Namespace>")
        xdto_packages = str(defn["xdtoPackages"]) if defn.get("xdtoPackages") else ""
        if xdto_packages:
            X(f"{i}<XDTOPackages>{xdto_packages}</XDTOPackages>")
        else:
            X(f"{i}<XDTOPackages/>")
        reuse_sessions = get_enum_prop("ReuseSessions", "reuseSessions", "DontUse")
        X(f"{i}<ReuseSessions>{reuse_sessions}</ReuseSessions>")
        session_max_age = str(defn["sessionMaxAge"]) if defn.get("sessionMaxAge") is not None else "20"
        X(f"{i}<SessionMaxAge>{session_max_age}</SessionMaxAge>")

    def emit_url_template(indent, tmpl_name, tmpl_def):
        uid = editor.allocate_uuid(root_uuid, "URLTemplate", logical + ".URLTemplate." + tmpl_name, "object", occupied)
        tmpl_synonym = split_camel_case(tmpl_name)
        template = ""
        methods = {}
        if isinstance(tmpl_def, str):
            template = tmpl_def
        else:
            template = str(tmpl_def["template"]) if tmpl_def.get("template") else f"/{tmpl_name.lower()}"
            if tmpl_def.get("methods"):
                for k, v in tmpl_def["methods"].items():
                    methods[k] = str(v)
        X(f'{indent}<URLTemplate uuid="{uid}">')
        X(f"{indent}\t<Properties>")
        X(f"{indent}\t\t<Name>{esc_xml(tmpl_name)}</Name>")
        emit_mltext(f"{indent}\t\t", "Synonym", tmpl_synonym)
        X(f"{indent}\t\t<Template>{esc_xml(template)}</Template>")
        X(f"{indent}\t</Properties>")
        if methods:
            X(f"{indent}\t<ChildObjects>")
            for method_name, http_method in sorted(methods.items()):
                method_uuid = editor.allocate_uuid(
                    root_uuid,
                    "Method",
                    logical + ".URLTemplate." + tmpl_name + ".Method." + method_name,
                    "object",
                    occupied,
                )
                method_synonym = split_camel_case(method_name)
                handler = f"{tmpl_name}{method_name}"
                X(f'{indent}\t\t<Method uuid="{method_uuid}">')
                X(f"{indent}\t\t\t<Properties>")
                X(f"{indent}\t\t\t\t<Name>{esc_xml(method_name)}</Name>")
                emit_mltext(f"{indent}\t\t\t\t", "Synonym", method_synonym)
                X(f"{indent}\t\t\t\t<HTTPMethod>{http_method}</HTTPMethod>")
                X(f"{indent}\t\t\t\t<Handler>{esc_xml(handler)}</Handler>")
                X(f"{indent}\t\t\t</Properties>")
                X(f"{indent}\t\t</Method>")
            X(f"{indent}\t</ChildObjects>")
        else:
            X(f"{indent}\t<ChildObjects/>")
        X(f"{indent}</URLTemplate>")

    def emit_operation(indent, op_name, op_def):
        uid = editor.allocate_uuid(root_uuid, "Operation", logical + ".Operation." + op_name, "object", occupied)
        op_synonym = split_camel_case(op_name)
        return_type = "xs:string"
        nillable = "false"
        transactioned = "false"
        handler = op_name
        params = {}
        if isinstance(op_def, str):
            return_type = op_def
        else:
            if op_def.get("returnType"):
                return_type = str(op_def["returnType"])
            if op_def.get("nillable") is True:
                nillable = "true"
            if op_def.get("transactioned") is True:
                transactioned = "true"
            if op_def.get("handler"):
                handler = str(op_def["handler"])
            if op_def.get("parameters"):
                for k, v in op_def["parameters"].items():
                    params[k] = v
        X(f'{indent}<Operation uuid="{uid}">')
        X(f"{indent}\t<Properties>")
        X(f"{indent}\t\t<Name>{esc_xml(op_name)}</Name>")
        emit_mltext(f"{indent}\t\t", "Synonym", op_synonym)
        X(f"{indent}\t\t<Comment/>")
        X(f"{indent}\t\t<XDTOReturningValueType>{return_type}</XDTOReturningValueType>")
        X(f"{indent}\t\t<Nillable>{nillable}</Nillable>")
        X(f"{indent}\t\t<Transactioned>{transactioned}</Transactioned>")
        X(f"{indent}\t\t<ProcedureName>{esc_xml(handler)}</ProcedureName>")
        X(f"{indent}\t</Properties>")
        if params:
            X(f"{indent}\t<ChildObjects>")
            for param_name, param_def in sorted(params.items()):
                param_uuid = editor.allocate_uuid(
                    root_uuid,
                    "Parameter",
                    logical + ".Operation." + op_name + ".Parameter." + param_name,
                    "object",
                    occupied,
                )
                param_synonym = split_camel_case(param_name)
                param_type = "xs:string"
                param_nillable = "true"
                param_dir = "In"
                if isinstance(param_def, str):
                    param_type = param_def
                else:
                    if param_def.get("type"):
                        param_type = str(param_def["type"])
                    if param_def.get("nillable") is False:
                        param_nillable = "false"
                    if param_def.get("direction"):
                        param_dir = str(param_def["direction"])
                X(f'{indent}\t\t<Parameter uuid="{param_uuid}">')
                X(f"{indent}\t\t\t<Properties>")
                X(f"{indent}\t\t\t\t<Name>{esc_xml(param_name)}</Name>")
                emit_mltext(f"{indent}\t\t\t\t", "Synonym", param_synonym)
                X(f"{indent}\t\t\t\t<XDTOValueType>{param_type}</XDTOValueType>")
                X(f"{indent}\t\t\t\t<Nillable>{param_nillable}</Nillable>")
                X(f"{indent}\t\t\t\t<TransferDirection>{param_dir}</TransferDirection>")
                X(f"{indent}\t\t\t</Properties>")
                X(f"{indent}\t\t</Parameter>")
            X(f"{indent}\t</ChildObjects>")
        else:
            X(f"{indent}\t<ChildObjects/>")
        X(f"{indent}</Operation>")

    synonym = defn.get("synonym", split_camel_case(obj_name))

    def checked_names(values):
        editor.require(
            all(editor.NAME.fullmatch(name) for name in values)
            and len({name.casefold() for name in values}) == len(values),
            "Invalid or duplicate service child name",
        )

    checked_names(defn.get("urlTemplates", {}))
    for template in defn.get("urlTemplates", {}).values():
        methods = template.get("methods", {})
        checked_names(methods)
        editor.require(
            all(
                value in {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "CONNECT", "TRACE", "MERGE"}
                for value in methods.values()
            ),
            "Unsupported HTTP method",
        )
    checked_names(defn.get("operations", {}))
    for name, operation in defn.get("operations", {}).items():
        editor.require(editor.NAME.fullmatch(operation.get("handler") or name), "Invalid service handler name")
        parameters = operation.get("parameters", {})
        checked_names(parameters)
        values = [operation.get("returnType") or "xs:string"]
        for parameter in parameters.values():
            editor.require(
                (parameter.get("direction") or "In") in {"In", "Out", "InOut"}, "Invalid parameter direction"
            )
            values.append(parameter.get("type") or "xs:string")
        editor.require(
            all(re.fullmatch(r"xs:[A-Za-z_][A-Za-z0-9_.-]*", value) for value in values),
            "XDTO type must use the declared xs namespace",
        )
    if defn.get("xdtoPackages"):
        fragment = editor.xml_read(
            (
                f'<XDTOPackages xmlns:xr="{borrow.XR}" xmlns:xsi="{objects.XSI}">'
                + defn["xdtoPackages"]
                + "</XDTOPackages>"
            ).encode(),
            "XDTOPackages",
        )
        editor.require(not (fragment.text or "").strip(), "Invalid XDTO package list")
        for item in fragment:
            editor.require(
                item.tag == f"{{{borrow.XR}}}Item"
                and not item.attrib
                and not (item.text or "").strip()
                and not (item.tail or "").strip()
                and [child.tag for child in item]
                == [f"{{{borrow.XR}}}{name}" for name in ("Presentation", "CheckState", "Value")],
                "Invalid XDTO package item",
            )
            presentation, state, value = item
            editor.require(
                all(not len(child) and not (child.tail or "").strip() for child in item)
                and not presentation.attrib
                and not state.attrib
                and state.text in {"0", "1", "2"}
                and dict(value.attrib) == {f"{{{objects.XSI}}}type": "xr:MDObjectRef"}
                and value.nsmap.get("xr") == borrow.XR,
                "Invalid XDTO package properties",
            )
            parts = (value.text or "").split(".")
            editor.require(
                len(parts) == 2 and parts[0] == "XDTOPackage" and editor.NAME.fullmatch(parts[1]),
                "Invalid XDTO package reference",
            )
    if obj_type == "Subsystem":
        content = defn.get("content", [])
        editor.require(len({item.casefold() for item in content}) == len(content), "Duplicate subsystem content")
        for item in [*content, *([defn["picture"]] if defn.get("picture") else [])]:
            parts = item.split(".")
            editor.require(
                len(parts) == 2 and parts[0] in borrow.DIRECTORIES and editor.NAME.fullmatch(parts[1]),
                "Invalid subsystem reference",
            )
        editor.require(
            not defn.get("picture") or defn["picture"].startswith("CommonPicture."),
            "Subsystem picture must be a common picture",
        )
        editor.require(
            not (defn.get("useOneCommand") is True and len(content) != 1),
            "UseOneCommand requires exactly one content item",
        )
    if obj_type == "CommonCommand":
        group = defn.get("group", "ActionsPanelTools").split(".")
        editor.require(
            len(group) == 1
            and editor.NAME.fullmatch(group[0])
            and group[0].isascii()
            or len(group) == 2
            and group[0] == "CommandGroup"
            and editor.NAME.fullmatch(group[1]),
            "Invalid command group",
        )
    if obj_type == "CommonModule":
        context = defn.get("context", "")
        editor.require(context in {"", "server", "serverCall", "client", "serverClient"}, "Unsupported module context")
        editor.require(
            not context
            or not set(defn)
            & {
                "server",
                "serverCall",
                "clientManagedApplication",
                "clientOrdinaryApplication",
                "externalConnection",
                "privileged",
            },
            "Module context cannot be combined with explicit execution flags",
        )
    for key in ("methodName", "handler"):
        if defn.get(key):
            parts = defn[key].split(".")
            editor.require(
                (len(parts) == 2 or len(parts) == 3 and parts[0] == "CommonModule")
                and all(editor.NAME.fullmatch(part) for part in parts),
                "Invalid module method reference",
            )
    if defn.get("event"):
        editor.require(editor.NAME.fullmatch(defn["event"]), "Invalid subscription event")
    source_types = {prefix for types in borrow.GENERATED_TYPES.values() for prefix, _ in types}
    for source in defn.get("source", []):
        parts = schema.normalize_type(source).split(".")
        editor.require(
            len(parts) in {1, 2} and parts[0] in source_types and all(editor.NAME.fullmatch(part) for part in parts),
            "Invalid subscription source type",
        )
    for key in ("defaultForm", "auxiliaryForm", "defaultSettingsForm", "auxiliarySettingsForm", "defaultVariantForm"):
        if defn.get(key):
            parts = defn[key].split(".")
            editor.require(
                (
                    len(parts) == 2
                    and parts[0] == "CommonForm"
                    or len(parts) == 4
                    and parts[:3] == [obj_type, obj_name, "Form"]
                )
                and all(editor.NAME.fullmatch(part) for part in parts),
                "Invalid form reference",
            )
    if defn.get("mainDataCompositionSchema"):
        parts = defn["mainDataCompositionSchema"].split(".")
        editor.require(
            len(parts) == 4 and parts[:3] == ["Report", obj_name, "Template"] and editor.NAME.fullmatch(parts[3]),
            "Invalid data composition schema reference",
        )
    for value in defn.get("registeredDocuments", []):
        parts = value.split(".")
        editor.require(
            len(parts) == 2
            and object_type_synonyms.get(parts[0], parts[0]) == "Document"
            and editor.NAME.fullmatch(parts[1]),
            "Invalid registered document reference",
        )
    # Validate raw reference tokens consumed by the original property emitter.
    for reference in defn.get("registerRecords", []):
        pieces = reference.split(".")
        editor.require(
            len(pieces) == 2
            and object_type_synonyms.get(pieces[0], pieces[0])
            in {"InformationRegister", "AccumulationRegister", "AccountingRegister", "CalculationRegister"}
            and editor.NAME.fullmatch(pieces[1]),
            "Invalid register reference",
        )
    if "sequenceFilling" in defn:
        editor.require(editor.NAME.fullmatch(defn["sequenceFilling"]), "Invalid sequence filling value")
    for key, prefix in (
        ("chartOfAccounts", "ChartOfAccounts"),
        ("chartOfCalculationTypes", "ChartOfCalculationTypes"),
        ("schedule", "InformationRegister"),
        ("extDimensionTypes", "ChartOfCharacteristicTypes"),
        ("characteristicExtValues", "Catalog"),
        ("task", "Task"),
        ("addressing", "InformationRegister"),
        ("currentPerformer", "SessionParameter"),
    ):
        if defn.get(key):
            parts = defn[key].split(".")
            editor.require(
                len(parts) == 2 and parts[0] == prefix and editor.NAME.fullmatch(parts[1]),
                "Invalid register reference property",
            )
    for value in defn.get("baseCalculationTypes", []):
        parts = value.split(".")
        editor.require(
            len(parts) == 2 and parts[0] == "ChartOfCalculationTypes" and editor.NAME.fullmatch(parts[1]),
            "Invalid base calculation reference",
        )
    if "codeSeries" in defn:
        editor.require(editor.NAME.fullmatch(defn["codeSeries"]), "Invalid code series")
    if "taskNumberAutoPrefix" in defn:
        editor.require(editor.NAME.fullmatch(defn["taskNumberAutoPrefix"]), "Invalid task number prefix")
    if defn.get("mainAddressingAttribute"):
        parts = defn["mainAddressingAttribute"].split(".")
        editor.require(
            len(parts) == 4
            and parts[:3] == ["Task", obj_name, "AddressingAttribute"]
            and parts[3] in {value["name"] for value in defn.get("addressingAttributes", [])},
            "Main addressing attribute must identify a declared task member",
        )
    for key in ("scheduleValue", "scheduleDate"):
        if defn.get(key):
            parts = defn[key].split(".")
            editor.require(
                len(parts) == 4
                and parts[0] == "InformationRegister"
                and parts[2] in {"Dimension", "Resource", "Attribute", "StandardAttribute"}
                and all(editor.NAME.fullmatch(part) for part in parts),
                "Invalid schedule field reference",
            )
    emitters = {
        "Catalog": emit_catalog_properties,
        "Document": emit_document_properties,
        "Enum": emit_enum_properties,
        "Constant": emit_constant_properties,
        "InformationRegister": emit_information_register_properties,
        "AccumulationRegister": emit_accumulation_register_properties,
        "AccountingRegister": emit_accounting_register_properties,
        "CalculationRegister": emit_calculation_register_properties,
        "ChartOfAccounts": emit_chart_of_accounts_properties,
        "ChartOfCharacteristicTypes": emit_chart_of_characteristic_types_properties,
        "ChartOfCalculationTypes": emit_chart_of_calculation_types_properties,
        "BusinessProcess": emit_business_process_properties,
        "Task": emit_task_properties,
        "ExchangePlan": emit_exchange_plan_properties,
        "Report": emit_report_properties,
        "DataProcessor": emit_data_processor_properties,
        "DocumentJournal": emit_document_journal_properties,
        "CommonModule": emit_common_module_properties,
        "ScheduledJob": emit_scheduled_job_properties,
        "EventSubscription": emit_event_subscription_properties,
        "HTTPService": emit_http_service_properties,
        "WebService": emit_web_service_properties,
        "CommonCommand": emit_common_command_properties,
        "Subsystem": emit_subsystem_properties,
    }
    nsmap = {None: editor.MD, "v8": editor.V8, "xs": editor.XS, "xr": borrow.XR, "xsi": objects.XSI, "cfg": borrow.CFG}
    root = etree.Element(f"{{{editor.MD}}}MetaDataObject", nsmap=nsmap, version="2.17")
    logical = obj_type + "." + obj_name

    def allocate(role):
        return editor.allocate_uuid(root_uuid, obj_type, logical, role, occupied)

    node = etree.SubElement(root, f"{{{editor.MD}}}{obj_type}", uuid=allocate("object"))
    internal = etree.SubElement(node, f"{{{editor.MD}}}InternalInfo")
    if obj_type not in borrow.GENERATED_TYPES:
        node.remove(internal)
    if obj_type == "ExchangePlan":
        etree.SubElement(internal, f"{{{borrow.XR}}}ThisNode").text = allocate("ThisNode")
    for prefix, category in borrow.GENERATED_TYPES.get(obj_type, []):
        generated = etree.SubElement(
            internal, f"{{{borrow.XR}}}GeneratedType", name=prefix + "." + obj_name, category=category
        )
        for role in ("TypeId", "ValueId"):
            etree.SubElement(generated, f"{{{borrow.XR}}}{role}").text = allocate(prefix + ":" + role)
    properties = etree.SubElement(node, f"{{{editor.MD}}}Properties")
    if extension:
        etree.SubElement(properties, f"{{{editor.MD}}}ObjectBelonging").text = "Native"
    if obj_type == "DefinedType":
        X(f"<Name>{esc_xml(obj_name)}</Name>")
        emit_mltext("", "Synonym", synonym)
        X("<Comment/>")
    else:
        emitters[obj_type]("")
    wrapper = etree.Element(f"{{{editor.MD}}}Properties", nsmap=nsmap)
    opening = etree.tostring(wrapper, encoding="unicode").replace("/>", ">")
    parsed = editor.xml_read((opening + "".join(lines) + "</Properties>").encode(), properties.tag)
    properties.extend(parsed)
    properties.find(f"{{{editor.MD}}}Comment").text = defn.get("comment")
    if obj_type == "Subsystem":
        etree.SubElement(node, f"{{{editor.MD}}}ChildObjects")
    if obj_type == "CommonCommand":
        values = defn.get("parameterTypes", [])
        if values:
            typed = type_node(" + ".join(values))
            typed.tag = f"{{{editor.MD}}}CommandParameterType"
            properties.replace(properties.find(f"{{{editor.MD}}}CommandParameterType"), typed)
    if obj_type == "DefinedType":
        values = defn.get("valueTypes", [])
        properties.append(type_node(" + ".join(values)) if values else etree.Element(f"{{{editor.MD}}}Type"))
    if obj_type in {
        "Catalog",
        "Document",
        "Enum",
        *REGISTERS,
        *CHARTS,
        "BusinessProcess",
        "Task",
        "ExchangePlan",
        "Report",
        "DataProcessor",
        "DocumentJournal",
    }:
        children = etree.SubElement(node, f"{{{editor.MD}}}ChildObjects")
        names = {name.casefold() for name in standard_attributes_by_type.get(obj_type, [])}
        names.update(
            name.casefold()
            for name in {
                "Catalog": (
                    "ИмяПредопределенныхДанных",
                    "Предопределенный",
                    "Ссылка",
                    "ПометкаУдаления",
                    "ЭтоГруппа",
                    "Владелец",
                    "Родитель",
                    "Наименование",
                    "Код",
                ),
                "Document": ("Проведен", "Ссылка", "ПометкаУдаления", "Дата", "Номер"),
                "Enum": (),
                "BusinessProcess": (
                    "Ссылка",
                    "ПометкаУдаления",
                    "Дата",
                    "Номер",
                    "Стартован",
                    "Завершен",
                    "ВедущаяЗадача",
                ),
                "Task": (
                    "Ссылка",
                    "ПометкаУдаления",
                    "Дата",
                    "Номер",
                    "Выполнена",
                    "Наименование",
                    "ТочкаМаршрута",
                    "БизнесПроцесс",
                ),
                "ExchangePlan": (
                    "Ссылка",
                    "ПометкаУдаления",
                    "Код",
                    "Наименование",
                    "ЭтотУзел",
                    "НомерОтправленного",
                    "НомерПринятого",
                ),
                "DocumentJournal": ("Тип", "Ссылка", "Дата", "Проведен", "ПометкаУдаления", "Номер"),
            }.get(obj_type, ())
        )
        if obj_type in REGISTERS:
            names.update(name.casefold() for name in RUSSIAN_REGISTER_STANDARD_ATTRIBUTES[obj_type])
        if obj_type in CHARTS:
            names.update(
                name.casefold()
                for name in (
                    "ИмяПредопределенныхДанных",
                    "Предопределенный",
                    "Ссылка",
                    "ПометкаУдаления",
                    "Наименование",
                    "Код",
                    "Родитель",
                    "Порядок",
                    "Вид",
                    "Забалансовый",
                    "ТипЗначения",
                    "ПериодДействияБазовый",
                )
            )
        if obj_type == "ChartOfAccounts":
            names.update({"extdimensiontypes", "видысубконто"})

        def checked_name(value, scope):
            name = value["name"]
            editor.require(
                editor.NAME.fullmatch(name) and name.casefold() not in scope, "Invalid or duplicate child name"
            )
            scope.add(name.casefold())
            return name

        def attribute(value, path, context):
            return objects.attribute_node(
                value,
                editor.allocate_uuid(root_uuid, "Attribute", path, "object", occupied),
                typed=type_node(value.get("type", "String")),
                context=context,
            )

        for collection, kind in (("resources", "Resource"), ("dimensions", "Dimension")):
            for value in defn.get(collection, []):
                name = checked_name(value, names)
                identity = editor.allocate_uuid(root_uuid, kind, logical + "." + kind + "." + name, "object", occupied)
                children.append(register_member(value, identity, obj_type, kind))
        for value in defn.get("attributes", []):
            name = checked_name(value, names)
            context = "processor" if obj_type in {"Report", "DataProcessor"} else obj_type.lower()
            children.append(attribute(value, logical + ".Attribute." + name, context))
        for section in defn.get("tabularSections", []):
            name = checked_name(section, names)
            path = logical + ".TabularSection." + name
            table = etree.SubElement(
                children,
                f"{{{editor.MD}}}TabularSection",
                uuid=editor.allocate_uuid(root_uuid, "TabularSection", path, "object", occupied),
            )
            info = etree.SubElement(table, f"{{{editor.MD}}}InternalInfo")
            for category in ("TabularSection", "TabularSectionRow"):
                prefix = obj_type + category
                generated = etree.SubElement(
                    info, f"{{{borrow.XR}}}GeneratedType", name=prefix + "." + obj_name + "." + name, category=category
                )
                for role in ("TypeId", "ValueId"):
                    etree.SubElement(generated, f"{{{borrow.XR}}}{role}").text = editor.allocate_uuid(
                        root_uuid, "TabularSection", path, prefix + "." + obj_name + "." + name + ":" + role, occupied
                    )
            lines.clear()
            X(f"<Name>{esc_xml(name)}</Name>")
            emit_mltext("", "Synonym", section.get("synonym", split_camel_case(name)))
            X("<Comment/><ToolTip/><FillChecking>DontCheck</FillChecking><StandardAttributes>")
            emit_standard_attribute("", "LineNumber")
            X("</StandardAttributes>")
            if obj_type == "Catalog":
                X("<Use>ForItem</Use>")
            table.append(editor.xml_read((opening + "".join(lines) + "</Properties>").encode(), properties.tag))
            columns = etree.SubElement(table, f"{{{editor.MD}}}ChildObjects")
            column_names = {"linenumber", "номерстроки"}
            for value in section.get("attributes", []):
                column = checked_name(value, column_names)
                context = "processor-tabular" if obj_type in {"Report", "DataProcessor"} else "tabular"
                columns.append(attribute(value, path + ".Attribute." + column, context))
        for value in defn.get("columns", []):
            name = checked_name(value, names)
            column = etree.SubElement(
                children,
                f"{{{editor.MD}}}Column",
                uuid=editor.allocate_uuid(root_uuid, "Column", logical + ".Column." + name, "object", occupied),
            )
            lines.clear()
            X(f"<Name>{esc_xml(name)}</Name>")
            emit_mltext("", "Synonym", value.get("synonym", split_camel_case(name)))
            X("<Comment/>")
            indexing = schema._enum("Indexing", value.get("indexing", "DontIndex"))
            X(f"<Indexing>{indexing}</Indexing><References/>")
            props = editor.xml_read((opening + "".join(lines) + "</Properties>").encode(), properties.tag)
            props.find(f"{{{editor.MD}}}Comment").text = value.get("comment")
            references = props.find(f"{{{editor.MD}}}References")
            for reference in value.get("references", []):
                parts = reference.split(".")
                editor.require(
                    len(parts) == 4
                    and parts[0] == "Document"
                    and parts[2] in {"Attribute", "StandardAttribute"}
                    and all(editor.NAME.fullmatch(part) for part in parts),
                    "Invalid journal column reference",
                )
                etree.SubElement(
                    references, f"{{{borrow.XR}}}Item", {f"{{{objects.XSI}}}type": "xr:MDObjectRef"}
                ).text = reference
            column.append(props)
        for collection, kind in (
            ("accountingFlags", "AccountingFlag"),
            ("extDimensionAccountingFlags", "ExtDimensionAccountingFlag"),
        ):
            for value in defn.get(collection, []):
                name = checked_name({"name": value}, names)
                flag = objects.attribute_node(
                    {"name": name, "type": "Boolean"},
                    editor.allocate_uuid(root_uuid, kind, logical + "." + kind + "." + name, "object", occupied),
                    context="tabular",
                )
                flag.tag = f"{{{editor.MD}}}{kind}"
                props = flag.find(f"{{{editor.MD}}}Properties")
                for property_name in (
                    "ChoiceFoldersAndItems",
                    "CreateOnInput",
                    "Indexing",
                    "FullTextSearch",
                    "DataHistory",
                ):
                    props.remove(props.find(f"{{{editor.MD}}}{property_name}"))
                children.append(flag)
        for value in defn.get("addressingAttributes", []):
            name = checked_name(value, names)
            editor.require(
                set(value.get("flags", [])) <= {"index", "indexadditional"} and "fillChecking" not in value,
                "Unsupported addressing attribute flags/properties",
            )
            dimension = value.get("addressingDimension", "")
            if dimension:
                parts = dimension.split(".")
                editor.require(
                    len(parts) == 4
                    and parts[0] == "InformationRegister"
                    and parts[2] == "Dimension"
                    and all(editor.NAME.fullmatch(part) for part in parts),
                    "Invalid addressing dimension reference",
                )
            member = objects.attribute_node(
                {
                    "indexing": "IndexWithAdditionalOrder" if "indexadditional" in value.get("flags", []) else "Index",
                    **value,
                },
                editor.allocate_uuid(
                    root_uuid, "AddressingAttribute", logical + ".AddressingAttribute." + name, "object", occupied
                ),
                typed=type_node(value.get("type", "String")),
            )
            member.tag = f"{{{editor.MD}}}AddressingAttribute"
            props = member.find(f"{{{editor.MD}}}Properties")
            for child in list(props):
                if etree.QName(child).localname not in {
                    "Name",
                    "Synonym",
                    "Comment",
                    "Type",
                    "Indexing",
                    "FullTextSearch",
                    "DataHistory",
                }:
                    props.remove(child)
            reference = etree.Element(f"{{{editor.MD}}}AddressingDimension")
            reference.text = dimension or None
            props.insert(4, reference)
            children.append(member)
        for value in defn.get("values", []):
            name = value["name"]
            editor.require(
                obj_type == "Enum" and editor.NAME.fullmatch(name) and name.casefold() not in names,
                "Invalid or duplicate enum value",
            )
            names.add(name.casefold())
            child = etree.SubElement(
                children,
                f"{{{editor.MD}}}EnumValue",
                uuid=editor.allocate_uuid(root_uuid, "EnumValue", logical + ".EnumValue." + name, "object", occupied),
            )
            props = etree.SubElement(child, f"{{{editor.MD}}}Properties")
            etree.SubElement(props, f"{{{editor.MD}}}Name").text = name
            title = etree.SubElement(props, f"{{{editor.MD}}}Synonym")
            text = value.get("synonym", split_camel_case(name))
            if text:
                item = etree.SubElement(title, f"{{{editor.V8}}}item")
                etree.SubElement(item, f"{{{editor.V8}}}lang").text = "ru"
                etree.SubElement(item, f"{{{editor.V8}}}content").text = text
            etree.SubElement(props, f"{{{editor.MD}}}Comment").text = value.get("comment")
    if obj_type in {"HTTPService", "WebService"}:
        children = etree.SubElement(node, f"{{{editor.MD}}}ChildObjects")
        definitions = defn.get("urlTemplates" if obj_type == "HTTPService" else "operations", {})
        emit = emit_url_template if obj_type == "HTTPService" else emit_operation
        for name in sorted(definitions):
            lines.clear()
            emit("", name, definitions[name])
            container = editor.xml_read((opening + "".join(lines) + "</Properties>").encode(), properties.tag)
            children.extend(container)
    etree.indent(root, space="\t")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + etree.tostring(root, encoding="UTF-8") + b"\n"
