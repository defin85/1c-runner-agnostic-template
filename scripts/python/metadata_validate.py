"""Pure structural metadata validation, extracted from meta-validate v1.2.

Source: https://github.com/Nikolay-Shirokov/cc-1c-skills
Copyright (c) Nick Shirokov. MIT license; see automation/vendor/cc-1c-skills/LICENSE.
"""

import re

import lxml.etree as etree


def object_report(
    root,
    *,
    detailed=False,
    max_errors=30,
    registrar_references=None,
    common_modules=None,
) -> dict:
    """Validate an already safely parsed descriptor without reading files.

    Optional sets provide exact RegisterRecords references and existing common
    module descriptor names. None means that cross-object check is unavailable.
    The ok field counts successful structural checks, not platform verification.
    """
    errors = 0
    warnings = 0
    ok_count = 0
    stopped = False
    output_lines = []

    def out_line(msg):
        output_lines.append(msg)

    def report_ok(msg):
        nonlocal ok_count
        ok_count += 1
        if detailed:
            out_line(f"[OK]    {msg}")

    def report_error(msg):
        nonlocal errors, stopped
        errors += 1
        out_line(f"[ERROR] {msg}")
        if errors >= max_errors:
            stopped = True

    def report_warn(msg):
        nonlocal warnings
        warnings += 1
        out_line(f"[WARN]  {msg}")

    def finalize():
        checks = ok_count + errors + warnings
        if errors == 0 and warnings == 0 and not detailed:
            lines = [f"=== Validation OK: {md_type}.{obj_name} ({checks} checks) ==="]
        else:
            out_line("")
            out_line(f"=== Result: {errors} errors, {warnings} warnings ({checks} checks) ===")
            lines = output_lines
        return {"lines": lines, "errors": errors, "warnings": warnings, "ok": ok_count, "stopped": stopped}

    # ── Reference tables ─────────────────────────────────────────

    guid_pattern = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
    ident_pattern = re.compile(
        r"^[A-Za-z\u0410-\u042F\u0401\u0430-\u044F\u0451_][A-Za-z0-9\u0410-\u042F\u0401\u0430-\u044F\u0451_]*$"
    )

    valid_types = (
        "Catalog",
        "Document",
        "Enum",
        "Constant",
        "InformationRegister",
        "AccumulationRegister",
        "AccountingRegister",
        "CalculationRegister",
        "ChartOfAccounts",
        "ChartOfCharacteristicTypes",
        "ChartOfCalculationTypes",
        "BusinessProcess",
        "Task",
        "ExchangePlan",
        "DocumentJournal",
        "Report",
        "DataProcessor",
        "ExternalReport",
        "ExternalDataProcessor",
        "CommonModule",
        "ScheduledJob",
        "EventSubscription",
        "HTTPService",
        "WebService",
        "DefinedType",
        "CommonCommand",
        "Subsystem",
    )

    arbitrary_type_owners = ("Report", "DataProcessor", "ExternalReport", "ExternalDataProcessor")

    # GeneratedType categories by type
    generated_type_categories = {
        "Catalog": ["Object", "Ref", "Selection", "List", "Manager"],
        "Document": ["Object", "Ref", "Selection", "List", "Manager"],
        "Enum": ["Ref", "Manager", "List"],
        "Constant": ["Manager", "ValueManager", "ValueKey"],
        "InformationRegister": ["Record", "Manager", "Selection", "List", "RecordSet", "RecordKey", "RecordManager"],
        "AccumulationRegister": ["Record", "Manager", "Selection", "List", "RecordSet", "RecordKey"],
        "AccountingRegister": ["Record", "Manager", "Selection", "List", "RecordSet", "RecordKey", "ExtDimensions"],
        "CalculationRegister": ["Record", "Manager", "Selection", "List", "RecordSet", "RecordKey", "Recalcs"],
        "ChartOfAccounts": [
            "Object",
            "Ref",
            "Selection",
            "List",
            "Manager",
            "ExtDimensionTypes",
            "ExtDimensionTypesRow",
        ],
        "ChartOfCharacteristicTypes": ["Object", "Ref", "Selection", "List", "Manager", "Characteristic"],
        "ChartOfCalculationTypes": [
            "Object",
            "Ref",
            "Selection",
            "List",
            "Manager",
            "DisplacingCalculationTypes",
            "DisplacingCalculationTypesRow",
            "BaseCalculationTypes",
            "BaseCalculationTypesRow",
            "LeadingCalculationTypes",
            "LeadingCalculationTypesRow",
        ],
        "BusinessProcess": ["Object", "Ref", "Selection", "List", "Manager", "RoutePointRef"],
        "Task": ["Object", "Ref", "Selection", "List", "Manager"],
        "ExchangePlan": ["Object", "Ref", "Selection", "List", "Manager"],
        "DocumentJournal": ["Selection", "List", "Manager"],
        "Report": ["Object", "Manager"],
        "DataProcessor": ["Object", "Manager"],
        "ExternalReport": ["Object"],
        "ExternalDataProcessor": ["Object"],
        "DefinedType": ["DefinedType"],
    }

    # Types that have NO InternalInfo / GeneratedType
    types_without_internal_info = ("CommonModule", "ScheduledJob", "EventSubscription", "CommonCommand", "Subsystem")

    # StandardAttributes by type
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
        "AccumulationRegister": ["Active", "LineNumber", "Recorder", "Period", "RecordType"],
        "AccountingRegister": ["Active", "Period", "Recorder", "LineNumber", "Account"],
        "CalculationRegister": [
            "Active",
            "Recorder",
            "LineNumber",
            "RegistrationPeriod",
            "CalculationType",
            "ReversingEntry",
            "ActionPeriod",
            "BegOfActionPeriod",
            "EndOfActionPeriod",
            "BegOfBasePeriod",
            "EndOfBasePeriod",
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
            "IsFolder",
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

    # Types that have StandardAttributes block
    types_with_std_attrs = (
        "Catalog",
        "Document",
        "Enum",
        "InformationRegister",
        "AccumulationRegister",
        "AccountingRegister",
        "CalculationRegister",
        "ChartOfAccounts",
        "ChartOfCharacteristicTypes",
        "ChartOfCalculationTypes",
        "BusinessProcess",
        "Task",
        "ExchangePlan",
        "DocumentJournal",
    )

    # ChildObjects rules
    child_object_rules = {
        "Catalog": ["Attribute", "TabularSection", "Form", "Template", "Command"],
        "Document": ["Attribute", "TabularSection", "Form", "Template", "Command"],
        "ExchangePlan": ["Attribute", "TabularSection", "Form", "Template", "Command"],
        "ChartOfAccounts": [
            "Attribute",
            "TabularSection",
            "Form",
            "Template",
            "Command",
            "AccountingFlag",
            "ExtDimensionAccountingFlag",
        ],
        "ChartOfCharacteristicTypes": ["Attribute", "TabularSection", "Form", "Template", "Command"],
        "ChartOfCalculationTypes": ["Attribute", "TabularSection", "Form", "Template", "Command"],
        "BusinessProcess": ["Attribute", "TabularSection", "Form", "Template", "Command"],
        "Task": ["Attribute", "TabularSection", "Form", "Template", "Command", "AddressingAttribute"],
        "Report": ["Attribute", "TabularSection", "Form", "Template", "Command"],
        "DataProcessor": ["Attribute", "TabularSection", "Form", "Template", "Command"],
        "ExternalReport": ["Attribute", "TabularSection", "Form", "Template"],
        "ExternalDataProcessor": ["Attribute", "TabularSection", "Form", "Template"],
        "Enum": ["EnumValue", "Form", "Template", "Command"],
        "InformationRegister": ["Dimension", "Resource", "Attribute", "Form", "Template", "Command"],
        "AccumulationRegister": ["Dimension", "Resource", "Attribute", "Form", "Template", "Command"],
        "AccountingRegister": ["Dimension", "Resource", "Attribute", "Form", "Template", "Command"],
        "CalculationRegister": ["Dimension", "Resource", "Attribute", "Form", "Template", "Command", "Recalculation"],
        "DocumentJournal": ["Column", "Form", "Template", "Command"],
        "HTTPService": ["URLTemplate"],
        "WebService": ["Operation"],
        "Constant": ["Form"],
        "DefinedType": [],
        "CommonModule": [],
        "ScheduledJob": [],
        "EventSubscription": [],
        "CommonCommand": [],
        "Subsystem": ["Subsystem"],
    }

    # Valid enum property values
    valid_property_values = {
        "CodeType": ["String", "Number"],
        "CodeAllowedLength": ["Variable", "Fixed"],
        "NumberType": ["String", "Number"],
        "NumberAllowedLength": ["Variable", "Fixed"],
        "Posting": ["Allow", "Deny"],
        "RealTimePosting": ["Allow", "Deny"],
        "RegisterRecordsDeletion": ["AutoDelete", "AutoDeleteOnUnpost", "AutoDeleteOff"],
        "RegisterRecordsWritingOnPost": ["WriteModified", "WriteSelected", "WriteAll"],
        "DataLockControlMode": ["Automatic", "Managed"],
        "FullTextSearch": ["Use", "DontUse"],
        "DefaultPresentation": ["AsDescription", "AsCode"],
        "HierarchyType": ["HierarchyFoldersAndItems", "HierarchyOfItems"],
        "EditType": ["InDialog", "InList", "BothWays"],
        "WriteMode": ["Independent", "RecorderSubordinate"],
        "InformationRegisterPeriodicity": [
            "Nonperiodical",
            "Second",
            "Day",
            "Month",
            "Quarter",
            "Year",
            "RecorderPosition",
        ],
        "RegisterType": ["Balance", "Turnovers"],
        "ReturnValuesReuse": ["DontUse", "DuringRequest", "DuringSession"],
        "ReuseSessions": ["DontUse", "AutoUse"],
        "FillChecking": ["DontCheck", "ShowError", "ShowWarning"],
        "Indexing": ["DontIndex", "Index", "IndexWithAdditionalOrder"],
        "DataHistory": ["Use", "DontUse"],
        "DependenceOnCalculationTypes": ["DontUse", "RequireCalculationTypes"],
        "ParameterUseMode": ["Single", "Multiple"],
    }

    # Properties forbidden per type (would cause LoadConfigFromFiles error)
    forbidden_properties = {
        "ChartOfCharacteristicTypes": ["CodeType"],
        "ChartOfAccounts": ["Autonumbering", "Hierarchical"],
        "ChartOfCalculationTypes": ["CheckUnique", "Autonumbering"],
        "ExchangePlan": ["CodeType", "CheckUnique", "Autonumbering"],
    }

    # ── Namespaces ───────────────────────────────────────────────

    NS = {
        "md": "http://v8.1c.ru/8.3/MDClasses",
        "v8": "http://v8.1c.ru/8.1/data/core",
        "xr": "http://v8.1c.ru/8.3/xcf/readable",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xs": "http://www.w3.org/2001/XMLSchema",
        "cfg": "http://v8.1c.ru/8.1/data/enterprise/current-config",
    }

    def local_name(node):
        return etree.QName(node.tag).localname

    def find(parent, xpath):
        if parent is None:
            return None
        r = parent.xpath(xpath, namespaces=NS)
        return r[0] if r else None

    def find_all(parent, xpath):
        if parent is None:
            return []
        return parent.xpath(xpath, namespaces=NS)

    def inner_text(node):
        if node is None:
            return ""
        return node.text or ""

    def text_of(node):
        if node is None:
            return ""
        return (node.text or "").strip()

    md_type = ""
    obj_name = "(unknown)"
    out_line("")

    # ── Check 1: Root structure ──────────────────────────────────

    check1_ok = True

    if local_name(root) != "MetaDataObject":
        report_error(f"1. Root element is '{local_name(root)}', expected 'MetaDataObject'")
        return finalize()

    expected_ns = "http://v8.1c.ru/8.3/MDClasses"
    root_ns = etree.QName(root.tag).namespace or ""
    if root_ns != expected_ns:
        report_error(f"1. Root namespace is '{root_ns}', expected '{expected_ns}'")
        check1_ok = False

    # Version attribute
    version = root.get("version", "")
    if not version:
        report_warn("1. Missing version attribute on MetaDataObject")
    elif version not in ("2.17", "2.20"):
        report_warn(f"1. Unusual version '{version}' (expected 2.17 or 2.20)")

    # Detect type element -- exactly one child element in md namespace
    type_node = None
    md_type = ""
    child_elements = []
    for child in root:
        if isinstance(child.tag, str) and etree.QName(child.tag).namespace == expected_ns:
            child_elements.append(child)

    if len(child_elements) == 0:
        report_error("1. No metadata type element found inside MetaDataObject")
        return finalize()
    elif len(child_elements) > 1:
        names = [local_name(c) for c in child_elements]
        report_error(f"1. Multiple type elements found: {names}")
        check1_ok = False

    type_node = child_elements[0]
    md_type = local_name(type_node)

    if md_type not in valid_types:
        report_error(f"1. Unrecognized metadata type: {md_type}")
        return finalize()

    # UUID on type element
    type_uuid = type_node.get("uuid", "")
    if not type_uuid:
        report_error(f"1. Missing uuid on <{md_type}> element")
        check1_ok = False
    elif not guid_pattern.match(type_uuid):
        report_error(f"1. Invalid uuid '{type_uuid}' on <{md_type}>")
        check1_ok = False

    # Get object name early for header
    props_node = find(type_node, "md:Properties")
    name_node = find(props_node, "md:Name") if props_node is not None else None
    obj_name = inner_text(name_node) if name_node is not None and inner_text(name_node) else "(unknown)"

    # Now emit header — insert at beginning
    output_lines.insert(0, f"=== Validation: {md_type}.{obj_name} ===")

    if check1_ok:
        report_ok(f"1. Root structure: MetaDataObject/{md_type}, version {version}")

    if stopped:
        return finalize()

    # ── Check 2: InternalInfo ────────────────────────────────────

    internal_info = find(type_node, "md:InternalInfo")

    if md_type in types_without_internal_info:
        if internal_info is not None:
            gen_types = find_all(internal_info, "xr:GeneratedType")
            if len(gen_types) > 0:
                report_warn(f"2. InternalInfo: {md_type} should not have GeneratedType entries, found {len(gen_types)}")
            else:
                report_ok(f"2. InternalInfo: absent or empty (correct for {md_type})")
        else:
            report_ok(f"2. InternalInfo: absent (correct for {md_type})")
    elif md_type in generated_type_categories:
        expected_categories = generated_type_categories[md_type]
        if internal_info is None:
            report_error(f"2. InternalInfo: missing (expected {len(expected_categories)} GeneratedType)")
        else:
            gen_types = find_all(internal_info, "xr:GeneratedType")
            check2_ok = True
            found_categories = []

            for gt in gen_types:
                gt_name = gt.get("name", "")
                gt_category = gt.get("category", "")
                found_categories.append(gt_category)

                # Validate name format
                if gt_name and obj_name != "(unknown)":
                    if not gt_name.endswith(f".{obj_name}"):
                        report_error(f"2. GeneratedType name '{gt_name}' does not end with '.{obj_name}'")
                        check2_ok = False

                # Validate category
                if gt_category not in expected_categories:
                    report_warn(f"2. Unexpected GeneratedType category '{gt_category}' for {md_type}")

                # Validate TypeId and ValueId UUIDs
                type_id = find(gt, "xr:TypeId")
                value_id = find(gt, "xr:ValueId")
                if type_id is not None and not guid_pattern.match(inner_text(type_id)):
                    report_error(f"2. Invalid TypeId UUID in GeneratedType '{gt_category}'")
                    check2_ok = False
                if value_id is not None and not guid_pattern.match(inner_text(value_id)):
                    report_error(f"2. Invalid ValueId UUID in GeneratedType '{gt_category}'")
                    check2_ok = False

            # ExchangePlan: check for ThisNode
            if md_type == "ExchangePlan":
                this_node = find(internal_info, "xr:ThisNode")
                if this_node is None:
                    report_warn("2. ExchangePlan missing xr:ThisNode in InternalInfo")
                elif not guid_pattern.match(inner_text(this_node)):
                    report_error("2. ExchangePlan xr:ThisNode has invalid UUID")
                    check2_ok = False

            # Check count mismatch
            missing_cats = [c for c in expected_categories if c not in found_categories]
            if missing_cats:
                report_warn(f"2. Missing GeneratedType categories: {', '.join(missing_cats)}")

            if check2_ok:
                cat_list = ", ".join(sorted(found_categories))
                report_ok(f"2. InternalInfo: {len(gen_types)} GeneratedType ({cat_list})")

    if stopped:
        return finalize()

    # ── Check 3: Properties -- Name, Synonym ─────────────────────

    if props_node is None:
        report_error("3. Properties block missing")
    else:
        check3_ok = True

        # Name
        if name_node is None or not inner_text(name_node):
            report_error("3. Properties: Name is missing or empty")
            check3_ok = False
        else:
            name_val = inner_text(name_node)
            if not ident_pattern.match(name_val):
                report_error(f"3. Properties: Name '{name_val}' is not a valid 1C identifier")
                check3_ok = False
            if len(name_val) > 80:
                report_warn(f"3. Properties: Name '{name_val}' is longer than 80 characters ({len(name_val)})")

        # Synonym
        syn_node = find(props_node, "md:Synonym")
        syn_present = False
        if syn_node is not None:
            syn_item = find(syn_node, "v8:item")
            if syn_item is not None:
                syn_content = find(syn_item, "v8:content")
                if syn_content is not None and inner_text(syn_content):
                    syn_present = True

        if check3_ok:
            syn_info = "Synonym present" if syn_present else "no Synonym"
            report_ok(f'3. Properties: Name="{obj_name}", {syn_info}')

    if stopped:
        return finalize()

    # ── Check 4: Property values -- enum properties ──────────────

    if props_node is not None:
        enum_checked = 0
        check4_ok = True

        for prop_name, allowed in valid_property_values.items():
            prop_node = find(props_node, f"md:{prop_name}")
            if prop_node is not None and inner_text(prop_node):
                val = inner_text(prop_node)
                if val not in allowed:
                    report_error(f"4. Property '{prop_name}' has invalid value '{val}' (allowed: {', '.join(allowed)})")
                    check4_ok = False
                enum_checked += 1

        if check4_ok:
            report_ok(f"4. Property values: {enum_checked} enum properties checked")
    else:
        report_warn("4. No Properties block to check")

    if stopped:
        return finalize()

    # ── Check 5: StandardAttributes ──────────────────────────────

    if md_type in types_with_std_attrs:
        std_attr_node = find(props_node, "md:StandardAttributes")
        if std_attr_node is None:
            report_ok(f"5. StandardAttributes: absent (optional for {md_type})")
        else:
            std_attrs = find_all(std_attr_node, "xr:StandardAttribute")
            expected_std_attrs = standard_attributes_by_type.get(md_type, [])
            check5_ok = True

            found_names = []
            for sa in std_attrs:
                sa_name = sa.get("name", "")
                if sa_name:
                    found_names.append(sa_name)
                    if sa_name not in expected_std_attrs:
                        # AccountingRegister has dynamic attrs
                        is_dynamic = md_type == "AccountingRegister" and (
                            re.match(r"^ExtDimension\d+$", sa_name)
                            or re.match(r"^ExtDimensionType\d+$", sa_name)
                            or sa_name == "PeriodAdjustment"
                        )
                        # CalculationRegister has conditional period attrs
                        is_calc_dynamic = md_type == "CalculationRegister" and sa_name in (
                            "ActionPeriod",
                            "BegOfActionPeriod",
                            "EndOfActionPeriod",
                            "BegOfBasePeriod",
                            "EndOfBasePeriod",
                        )
                        if not is_dynamic and not is_calc_dynamic:
                            report_warn(f"5. Unexpected StandardAttribute '{sa_name}' for {md_type}")
                else:
                    report_error("5. StandardAttribute without 'name' attribute")
                    check5_ok = False

            if expected_std_attrs:
                missing_attrs = [a for a in expected_std_attrs if a not in found_names]
                if missing_attrs:
                    report_warn(f"5. Missing StandardAttributes: {', '.join(missing_attrs)}")

            if check5_ok:
                report_ok(f"5. StandardAttributes: {len(std_attrs)} entries")

    if stopped:
        return finalize()

    # ── Check 6: ChildObjects -- allowed element types ───────────

    child_obj_node = find(type_node, "md:ChildObjects")
    allowed_children = child_object_rules.get(md_type, [])

    if child_obj_node is not None:
        check6_ok = True
        child_counts = {}

        for child in child_obj_node:
            if not isinstance(child.tag, str):
                continue
            child_tag = local_name(child)

            if child_tag not in allowed_children:
                report_error(f"6. ChildObjects: disallowed element '{child_tag}' for {md_type}")
                check6_ok = False

            child_counts[child_tag] = child_counts.get(child_tag, 0) + 1

        if check6_ok:
            summary = ", ".join(f"{k}({v})" for k, v in sorted(child_counts.items()))
            if summary:
                report_ok(f"6. ChildObjects types: {summary}")
            else:
                report_ok(f"6. ChildObjects: empty (valid for {md_type})")
    elif len(allowed_children) == 0:
        report_ok(f"6. ChildObjects: absent (correct for {md_type})")
    else:
        report_ok("6. ChildObjects: absent")

    if stopped:
        return finalize()

    # ── Check 7: Child elements -- UUID, Name, Type ──────────────

    def check_child_element(node, kind, require_type):
        uuid = node.get("uuid", "")
        if not uuid:
            report_error(f"7. {kind} missing uuid")
            return False
        if not guid_pattern.match(uuid):
            report_error(f"7. {kind} has invalid uuid '{uuid}'")
            return False

        el_props = find(node, "md:Properties")
        if el_props is None:
            report_error(f"7. {kind} (uuid={uuid}) missing Properties")
            return False

        el_name = find(el_props, "md:Name")
        if el_name is None or not inner_text(el_name):
            report_error(f"7. {kind} (uuid={uuid}) missing or empty Name")
            return False

        name_val = inner_text(el_name)
        if not ident_pattern.match(name_val):
            report_error(f"7. {kind} '{name_val}' has invalid identifier")
            return False

        if require_type:
            type_el = find(el_props, "md:Type")
            if type_el is None:
                report_error(f"7. {kind} '{name_val}' missing Type block")
                return False
            xsi_type = type_el.get(f"{{{NS['xsi']}}}type")
            if xsi_type is not None:
                # EDT represents a multi-state extension with an ExtendedProperty
                # wrapper, a typed empty CheckValue, and the extended TypeDescription.
                # Reject the superficially similar but XDTO-invalid abbreviated form.
                internal_info = find(node, "md:InternalInfo")
                states = find_all(internal_info, "xr:PropertyState[xr:Property='Type']")
                state_ok = False
                if len(states) == 1:
                    state = states[0]
                    state_ok = (
                        not state.attrib
                        and not (state.text or "").strip()
                        and [child.tag for child in state] == [f"{{{NS['xr']}}}Property", f"{{{NS['xr']}}}State"]
                        and all(
                            not child.attrib and not len(child) and not (child.tail or "").strip() for child in state
                        )
                        and text_of(state[0]) == "Type"
                        and text_of(state[1]) == "MultiState"
                    )

                children = list(type_el)
                check_value = children[0] if len(children) > 0 else None
                extend_value = children[1] if len(children) > 1 else None
                xsi_attr = f"{{{NS['xsi']}}}type"

                def type_description(part, *, empty):
                    if (
                        part is None
                        or part.get(xsi_attr) != "v8:TypeDescription"
                        or part.nsmap.get("v8") != NS["v8"]
                        or set(part.attrib) != {xsi_attr}
                        or (part.text or "").strip()
                    ):
                        return False
                    if empty:
                        return len(part) == 0
                    type_items = [child for child in part if child.tag == f"{{{NS['v8']}}}Type"]
                    if not type_items or any(
                        child.attrib
                        or len(child)
                        or not text_of(child)
                        or ":" not in text_of(child)
                        or not child.nsmap.get(text_of(child).split(":", 1)[0])
                        for child in type_items
                    ):
                        return False
                    return all(etree.QName(child).namespace == NS["v8"] for child in part)

                valid_extension = (
                    xsi_type == "xr:ExtendedProperty"
                    and type_el.nsmap.get("xr") == NS["xr"]
                    and set(type_el.attrib) == {xsi_attr}
                    and not (type_el.text or "").strip()
                    and [child.tag for child in children] == [f"{{{NS['xr']}}}CheckValue", f"{{{NS['xr']}}}ExtendValue"]
                    and all(not (child.tail or "").strip() for child in children)
                    and state_ok
                    and type_description(check_value, empty=True)
                    and type_description(extend_value, empty=False)
                )
                if not valid_extension:
                    report_error(f"7. {kind} '{name_val}' has malformed xr:ExtendedProperty Type")
                    return False
                return True
            if (
                kind == "Attribute"
                and md_type in arbitrary_type_owners
                and not type_el.attrib
                and len(type_el) == 0
                and not (type_el.text or "").strip()
            ):
                # Designer serializes the arbitrary attribute type of processors and reports as <Type/>.
                return True
            v8_types = find_all(type_el, "v8:Type")
            v8_type_sets = find_all(type_el, "v8:TypeSet")
            v8_type_ids = find_all(type_el, "v8:TypeId")
            if len(v8_types) == 0 and len(v8_type_sets) == 0 and len(v8_type_ids) == 0:
                report_error(f"7. {kind} '{name_val}' Type block has no v8:Type, v8:TypeSet, or v8:TypeId")
                return False
            for type_id in v8_type_ids:
                if not guid_pattern.fullmatch(text_of(type_id)):
                    report_error(f"7. {kind} '{name_val}' has malformed v8:TypeId: TypeId has invalid UUID")
                    return False
                if type_id.attrib or len(type_id) or (type_id.tail or "").strip():
                    report_error(f"7. {kind} '{name_val}' has malformed v8:TypeId")
                    return False

        return True

    if child_obj_node is not None:
        check7_ok = True
        check7_count = 0
        element_kinds = ("Attribute", "Dimension", "Resource", "EnumValue", "Column")

        for kind in element_kinds:
            elements = find_all(child_obj_node, f"md:{kind}")
            require_type = kind not in ("EnumValue", "Column")
            for el in elements:
                if stopped:
                    break
                ok = check_child_element(el, kind, require_type)
                if not ok:
                    check7_ok = False
                check7_count += 1

        if check7_ok and check7_count > 0:
            report_ok(f"7. Child elements: {check7_count} items checked (UUID, Name, Type)")
        elif check7_count == 0:
            report_ok("7. Child elements: none to check")

    if stopped:
        return finalize()

    # ── Check 7b: Reserved attribute names ───────────────────────

    RESERVED_ATTR_NAMES = {
        "Ref",
        "DeletionMark",
        "Code",
        "Description",
        "Date",
        "Number",
        "Posted",
        "Parent",
        "Owner",
        "IsFolder",
        "Predefined",
        "PredefinedDataName",
        "Recorder",
        "Period",
        "LineNumber",
        "Active",
        "Order",
        "Type",
        "OffBalance",
        "Started",
        "Completed",
        "HeadTask",
        "Executed",
        "RoutePoint",
        "BusinessProcess",
        "ThisNode",
        "SentNo",
        "ReceivedNo",
        "CalculationType",
        "RegistrationPeriod",
        "ReversingEntry",
        "Account",
        "ValueType",
        "ActionPeriodIsBasic",
    }

    if child_obj_node is not None:
        check7b_ok = True
        for attr_node in find_all(child_obj_node, "md:Attribute"):
            attr_props = find(attr_node, "md:Properties")
            if attr_props is not None:
                attr_name_node = find(attr_props, "md:Name")
                if attr_name_node is not None and inner_text(attr_name_node):
                    an = inner_text(attr_name_node)
                    if an in RESERVED_ATTR_NAMES:
                        report_warn(f"7b. Attribute '{an}' conflicts with a standard attribute name")
                        check7b_ok = False
        if check7b_ok:
            report_ok("7b. Reserved attribute names: no conflicts")

    if stopped:
        return finalize()

    # ── Check 8: Name uniqueness ─────────────────────────────────

    def check_uniqueness(nodes, kind):
        names = {}
        has_dupes = False
        for node in nodes:
            el_props = find(node, "md:Properties")
            if el_props is None:
                continue
            el_name = find(el_props, "md:Name")
            if el_name is None or not inner_text(el_name):
                continue
            name_val = inner_text(el_name)
            if name_val in names:
                report_error(f"8. Duplicate {kind} name: '{name_val}'")
                has_dupes = True
            else:
                names[name_val] = True
        return not has_dupes

    if child_obj_node is not None:
        check8_ok = True

        # Attributes
        attrs = find_all(child_obj_node, "md:Attribute")
        if len(attrs) > 0:
            if not check_uniqueness(attrs, "Attribute"):
                check8_ok = False

        # TabularSections
        tss = find_all(child_obj_node, "md:TabularSection")
        if len(tss) > 0:
            if not check_uniqueness(tss, "TabularSection"):
                check8_ok = False

        # Dimensions
        dims = find_all(child_obj_node, "md:Dimension")
        if len(dims) > 0:
            if not check_uniqueness(dims, "Dimension"):
                check8_ok = False

        # Resources
        ress = find_all(child_obj_node, "md:Resource")
        if len(ress) > 0:
            if not check_uniqueness(ress, "Resource"):
                check8_ok = False

        # EnumValues
        evs = find_all(child_obj_node, "md:EnumValue")
        if len(evs) > 0:
            if not check_uniqueness(evs, "EnumValue"):
                check8_ok = False

        # Columns (DocumentJournal)
        cols = find_all(child_obj_node, "md:Column")
        if len(cols) > 0:
            if not check_uniqueness(cols, "Column"):
                check8_ok = False

        # URLTemplates (HTTPService)
        url_ts = find_all(child_obj_node, "md:URLTemplate")
        if len(url_ts) > 0:
            if not check_uniqueness(url_ts, "URLTemplate"):
                check8_ok = False

        # Operations (WebService)
        ops = find_all(child_obj_node, "md:Operation")
        if len(ops) > 0:
            if not check_uniqueness(ops, "Operation"):
                check8_ok = False

        if check8_ok:
            report_ok("8. Name uniqueness: all names unique")

    if stopped:
        return finalize()

    # ── Check 9: TabularSections -- internal structure ───────────

    if child_obj_node is not None:
        ts_sections = find_all(child_obj_node, "md:TabularSection")
        if len(ts_sections) > 0:
            check9_ok = True
            ts_count = 0

            for ts in ts_sections:
                if stopped:
                    break
                ts_count += 1

                # UUID
                ts_uuid = ts.get("uuid", "")
                if not ts_uuid or not guid_pattern.match(ts_uuid):
                    report_error(f"9. TabularSection #{ts_count}: invalid or missing uuid")
                    check9_ok = False

                # Name
                ts_props = find(ts, "md:Properties")
                ts_name_node = find(ts_props, "md:Name") if ts_props is not None else None
                ts_name = inner_text(ts_name_node) if ts_name_node is not None else "(unnamed)"

                if ts_name_node is None or not inner_text(ts_name_node):
                    report_error(f"9. TabularSection #{ts_count}: missing or empty Name")
                    check9_ok = False

                # InternalInfo with 2 GeneratedType
                ts_int_info = find(ts, "md:InternalInfo")
                if ts_int_info is not None:
                    ts_gens = find_all(ts_int_info, "xr:GeneratedType")
                    if len(ts_gens) < 2:
                        report_warn(f"9. TabularSection '{ts_name}': expected 2 GeneratedType, found {len(ts_gens)}")

                # Attributes inside TS
                ts_child_obj = find(ts, "md:ChildObjects")
                if ts_child_obj is not None:
                    ts_attrs = find_all(ts_child_obj, "md:Attribute")
                    ts_attr_names = {}
                    for ta in ts_attrs:
                        ta_ok = check_child_element(ta, f"TabularSection '{ts_name}'.Attribute", True)
                        if not ta_ok:
                            check9_ok = False

                        # Check name uniqueness within TS
                        ta_props = find(ta, "md:Properties")
                        ta_name = find(ta_props, "md:Name") if ta_props is not None else None
                        if ta_name is not None and inner_text(ta_name):
                            if inner_text(ta_name) in ts_attr_names:
                                report_error(
                                    f"9. Duplicate attribute '{inner_text(ta_name)}' in TabularSection '{ts_name}'"
                                )
                                check9_ok = False
                            else:
                                ts_attr_names[inner_text(ta_name)] = True

                    # StandardAttributes of TS: expect LineNumber
                    if ts_props is not None:
                        ts_std_attr = find(ts_props, "md:StandardAttributes")
                        if ts_std_attr is not None:
                            ts_std_attrs = find_all(ts_std_attr, "xr:StandardAttribute")
                            has_line_number = False
                            for tsa in ts_std_attrs:
                                if tsa.get("name") == "LineNumber":
                                    has_line_number = True
                            if not has_line_number:
                                report_warn(f"9. TabularSection '{ts_name}': missing LineNumber StandardAttribute")

            if check9_ok:
                report_ok(f"9. TabularSections: {ts_count} sections, structure valid")
        else:
            report_ok("9. TabularSections: none present")

    if stopped:
        return finalize()

    # ── Check 10: Cross-property consistency ─────────────────────

    check10_ok = True
    check10_issues = 0

    if props_node is not None:
        # Designer retains HierarchyType when hierarchy is disabled.
        # Its enum is still validated by check 4.

        # CommonModule: no context enabled
        if md_type == "CommonModule":
            contexts = (
                "Server",
                "ClientManagedApplication",
                "ClientOrdinaryApplication",
                "ExternalConnection",
                "ServerCall",
                "Global",
            )
            any_enabled = False
            for ctx in contexts:
                ctx_node = find(props_node, f"md:{ctx}")
                if ctx_node is not None and inner_text(ctx_node) == "true":
                    any_enabled = True
                    break
            if not any_enabled:
                report_warn("10. CommonModule: no execution context enabled")
                check10_issues += 1

        # EventSubscription: empty Handler
        if md_type == "EventSubscription":
            handler = find(props_node, "md:Handler")
            if handler is None or not text_of(handler):
                report_error("10. EventSubscription: empty Handler")
                check10_ok = False
                check10_issues += 1

            # Empty Source
            source = find(props_node, "md:Source")
            has_source = False
            if source is not None:
                source_types = find_all(source, "v8:Type")
                if len(source_types) > 0:
                    has_source = True
            if not has_source:
                report_warn("10. EventSubscription: no Source types specified")
                check10_issues += 1

        # ScheduledJob: empty MethodName
        if md_type == "ScheduledJob":
            method = find(props_node, "md:MethodName")
            if method is None or not text_of(method):
                report_error("10. ScheduledJob: empty MethodName")
                check10_ok = False
                check10_issues += 1

        # AccountingRegister: ChartOfAccounts must not be empty
        if md_type == "AccountingRegister":
            coa = find(props_node, "md:ChartOfAccounts")
            if coa is None or not text_of(coa):
                report_error("10. AccountingRegister: empty ChartOfAccounts")
                check10_ok = False
                check10_issues += 1
                out_line('[HINT] metadata object.edit: modify-property "ChartOfAccounts=ChartOfAccounts.XXX"')

        # CalculationRegister: ChartOfCalculationTypes must not be empty
        if md_type == "CalculationRegister":
            coct = find(props_node, "md:ChartOfCalculationTypes")
            if coct is None or not text_of(coct):
                report_error("10. CalculationRegister: empty ChartOfCalculationTypes")
                check10_ok = False
                check10_issues += 1
                out_line(
                    '[HINT] metadata object.edit: modify-property "ChartOfCalculationTypes=ChartOfCalculationTypes.XXX"'
                )

        # BusinessProcess: Task should not be empty
        if md_type == "BusinessProcess":
            task_prop = find(props_node, "md:Task")
            if task_prop is None or not text_of(task_prop):
                report_warn("10. BusinessProcess: empty Task reference")
                check10_issues += 1
                out_line('[HINT] metadata object.edit: modify-property "Task=Task.XXX"')

        # DocumentJournal: RegisteredDocuments should not be empty. An adopted
        # journal inherits the list from the base configuration and omits it.
        if md_type == "DocumentJournal" and text_of(find(props_node, "md:ObjectBelonging")) != "Adopted":
            reg_docs = find(props_node, "md:RegisteredDocuments")
            has_reg_docs = False
            if reg_docs is not None:
                items = find_all(reg_docs, "v8:Type")
                if len(items) > 0:
                    has_reg_docs = True
            if not has_reg_docs:
                report_warn("10. DocumentJournal: no RegisteredDocuments specified")
                check10_issues += 1

        # ChartOfAccounts: ExtDimensionTypes should be set if MaxExtDimensionCount > 0
        if md_type == "ChartOfAccounts":
            max_ext_dim = find(props_node, "md:MaxExtDimensionCount")
            if max_ext_dim is not None:
                try:
                    med_val = int(inner_text(max_ext_dim) or "0")
                except ValueError:
                    med_val = 0
                if med_val > 0:
                    edt = find(props_node, "md:ExtDimensionTypes")
                    if edt is None or not text_of(edt):
                        report_warn("10. ChartOfAccounts: MaxExtDimensionCount>0 but ExtDimensionTypes is empty")
                        check10_issues += 1
                        out_line(
                            '[HINT] metadata object.edit: modify-property "ExtDimensionTypes=ChartOfCharacteristicTypes.XXX"'
                        )

        # Register: must have at least one registrar document
        register_types = ("AccumulationRegister", "AccountingRegister", "CalculationRegister", "InformationRegister")
        if md_type in register_types and obj_name != "(unknown)":
            needs_registrar = True
            # InformationRegister with WriteMode=Independent does not need a registrar
            if md_type == "InformationRegister":
                write_mode = find(props_node, "md:WriteMode")
                if write_mode is None or inner_text(write_mode) != "RecorderSubordinate":
                    needs_registrar = False
            if needs_registrar:
                reg_ref = f"{md_type}.{obj_name}"
                if registrar_references is None:
                    report_warn(f"10. {md_type}: registrar check not-run (RegisterRecords context unavailable)")
                    check10_issues += 1
                elif reg_ref not in registrar_references:
                    report_warn(
                        f"10. {md_type}: no registrar document found (none references '{reg_ref}' in RegisterRecords)"
                    )
                    check10_issues += 1

    if check10_ok and check10_issues == 0:
        report_ok("10. Cross-property consistency")

    if stopped:
        return finalize()

    # ── Check 11: HTTPService/WebService nested structure ────────

    if md_type == "HTTPService" and child_obj_node is not None:
        url_templates = find_all(child_obj_node, "md:URLTemplate")
        check11_ok = True
        method_count = 0

        valid_http_methods = ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "MERGE", "CONNECT")

        for ut in url_templates:
            if stopped:
                break

            ut_props = find(ut, "md:Properties")
            ut_name_node = find(ut_props, "md:Name") if ut_props is not None else None
            ut_name = inner_text(ut_name_node) if ut_name_node is not None else "(unnamed)"

            # Template property
            tpl = find(ut_props, "md:Template") if ut_props is not None else None
            if tpl is None or not text_of(tpl):
                report_error(f"11. HTTPService URLTemplate '{ut_name}': empty Template")
                check11_ok = False

            # Methods inside URLTemplate
            ut_child_obj = find(ut, "md:ChildObjects")
            if ut_child_obj is not None:
                methods = find_all(ut_child_obj, "md:Method")
                for m in methods:
                    method_count += 1
                    m_props = find(m, "md:Properties")
                    if m_props is not None:
                        http_method = find(m_props, "md:HTTPMethod")
                        if http_method is not None and inner_text(http_method):
                            if inner_text(http_method) not in valid_http_methods:
                                report_error(
                                    f"11. HTTPService URLTemplate '{ut_name}': invalid HTTPMethod '{inner_text(http_method)}'"
                                )
                                check11_ok = False
                        else:
                            report_error(f"11. HTTPService URLTemplate '{ut_name}': Method missing HTTPMethod")
                            check11_ok = False

        if check11_ok:
            report_ok(f"11. HTTPService: {len(url_templates)} URLTemplate(s), {method_count} method(s)")

    elif md_type == "WebService" and child_obj_node is not None:
        operations = find_all(child_obj_node, "md:Operation")
        check11_ok = True
        param_count = 0

        valid_directions = ("In", "Out", "InOut")

        for op in operations:
            if stopped:
                break

            op_props = find(op, "md:Properties")
            op_name_node = find(op_props, "md:Name") if op_props is not None else None
            op_name = inner_text(op_name_node) if op_name_node is not None else "(unnamed)"

            # ReturnType
            ret_type = find(op_props, "md:XDTOReturningValueType") if op_props is not None else None
            if ret_type is None or not text_of(ret_type):
                report_warn(f"11. WebService Operation '{op_name}': no XDTOReturningValueType")

            # Parameters inside Operation
            op_child_obj = find(op, "md:ChildObjects")
            if op_child_obj is not None:
                params = find_all(op_child_obj, "md:Parameter")
                for p in params:
                    param_count += 1
                    p_props = find(p, "md:Properties")
                    if p_props is not None:
                        direction = find(p_props, "md:TransferDirection")
                        if (
                            direction is not None
                            and inner_text(direction)
                            and inner_text(direction) not in valid_directions
                        ):
                            report_error(
                                f"11. WebService Operation '{op_name}': Parameter has invalid TransferDirection '{inner_text(direction)}'"
                            )
                            check11_ok = False

        if check11_ok:
            report_ok(f"11. WebService: {len(operations)} operation(s), {param_count} parameter(s)")

    if stopped:
        return finalize()

    # ── Check 12: Forbidden properties per type ──────────────────

    if props_node is not None and md_type in forbidden_properties:
        forbidden = forbidden_properties[md_type]
        check12_ok = True
        for fp in forbidden:
            fp_node = find(props_node, f"md:{fp}")
            if fp_node is not None:
                report_error(f"12. Forbidden property '{fp}' present in {md_type} (will fail on LoadConfigFromFiles)")
                check12_ok = False
        if check12_ok:
            report_ok("12. Forbidden properties: none found")

    if stopped:
        return finalize()

    # ── Check 13: Method reference validation ─────────────────────

    if props_node is not None and md_type in ("EventSubscription", "ScheduledJob"):
        check13_ok = True
        method_ref = None
        prop_label = None

        if md_type == "EventSubscription":
            h_node = find(props_node, "md:Handler")
            if h_node is not None:
                method_ref = text_of(h_node)
            prop_label = "Handler"
        elif md_type == "ScheduledJob":
            m_node = find(props_node, "md:MethodName")
            if m_node is not None:
                method_ref = text_of(m_node)
            prop_label = "MethodName"

        if method_ref:
            parts = method_ref.split(".")
            # Format: CommonModule.ModuleName.ProcedureName (3 parts) or ModuleName.ProcedureName (2 parts, legacy)
            if (
                len(parts) == 3
                and parts[0] == "CommonModule"
                and all(ident_pattern.fullmatch(part) for part in parts[1:])
            ):
                cm_name = parts[1]
                proc_name = parts[2]
            elif len(parts) == 2 and all(ident_pattern.fullmatch(part) for part in parts):
                cm_name = parts[0]
                proc_name = parts[1]
            else:
                report_error(
                    f"13. {md_type}.{prop_label} = '{method_ref}': expected format 'CommonModule.ModuleName.ProcedureName'"
                )
                check13_ok = False
                cm_name = None
                proc_name = None
            if cm_name:
                if common_modules is None:
                    report_warn(
                        f"13. {md_type}.{prop_label}: CommonModule check not-run (descriptor context unavailable)"
                    )
                    check13_ok = False
                elif cm_name not in common_modules:
                    report_error(f"13. {md_type}.{prop_label}: CommonModule '{cm_name}' not found")
                    check13_ok = False
                else:
                    report_warn(
                        f"13. {md_type}.{prop_label}: BSL method '{proc_name}' check not-run (requires BSL Analyzer or target platform)"
                    )
                    check13_ok = False

        if check13_ok:
            report_ok(f"13. Method reference: {prop_label} = '{method_ref}'")

    if stopped:
        return finalize()

    # ── Check 14: DocumentJournal Column content ──────────────────

    if md_type == "DocumentJournal" and child_obj_node is not None:
        columns = find_all(child_obj_node, "md:Column")
        check14_ok = True
        col_count = 0
        empty_ref_count = 0

        for col in columns:
            col_count += 1
            col_props = find(col, "md:Properties")
            col_name_node = find(col_props, "md:Name") if col_props is not None else None
            col_name = inner_text(col_name_node) if col_name_node is not None else "(unnamed)"

            refs = find(col_props, "md:References") if col_props is not None else None
            has_items = False
            if refs is not None:
                items = find_all(refs, "xr:Item")
                if len(items) > 0:
                    has_items = True
            if not has_items:
                report_error(
                    f"14. DocumentJournal Column '{col_name}': empty References (will fail on LoadConfigFromFiles)"
                )
                check14_ok = False
                empty_ref_count += 1

        if check14_ok and col_count > 0:
            report_ok(f"14. DocumentJournal Columns: {col_count} column(s), all have References")
        elif col_count == 0:
            report_ok("14. DocumentJournal Columns: none")

    return finalize()


# Pure formatter/checks from form-validate v1.1, same upstream MIT attribution.
def form_report(root, form_name, *, detailed=False, max_errors=30) -> dict:
    """Check parsed form structure; this is not platform or BSL validation."""
    F_NS = "http://v8.1c.ru/8.3/xcf/logform"
    V8_NS = "http://v8.1c.ru/8.1/data/core"

    def localname(el):
        return etree.QName(el.tag).localname

    errors = 0
    warnings = 0
    ok_count = 0
    stopped = False
    output_lines = []

    def report_ok(msg):
        nonlocal ok_count
        ok_count += 1
        if detailed:
            output_lines.append(f"[OK]    {msg}")

    def report_error(msg):
        nonlocal errors, stopped
        errors += 1
        output_lines.append(f"[ERROR] {msg}")
        if errors >= max_errors:
            stopped = True

    def report_warn(msg):
        nonlocal warnings
        warnings += 1
        output_lines.append(f"[WARN]  {msg}")

    output_lines.append(f"=== Validation: Form.{form_name} ===")
    output_lines.append("")

    # Early BaseForm detection
    has_base_form = root.find(f"{{{F_NS}}}BaseForm") is not None

    # --- Check 1: Root element and version ---
    if localname(root) != "Form":
        report_error(f"Root element is '{localname(root)}', expected 'Form'")
    else:
        version = root.get("version", "")
        if version in ("2.17", "2.20"):
            report_ok(f"Root element: Form version={version}")
        elif version:
            report_warn(f"Form version='{version}' (expected 2.17 or 2.20)")
        else:
            report_warn("Form version attribute missing")

    # --- Check 2: AutoCommandBar ---
    if not stopped:
        acb = root.find(f"{{{F_NS}}}AutoCommandBar")
        if acb is not None:
            acb_name = acb.get("name", "")
            acb_id = acb.get("id", "")
            if acb_id == "-1":
                report_ok(f"AutoCommandBar: name='{acb_name}', id={acb_id}")
            else:
                report_error(f"AutoCommandBar id='{acb_id}', expected '-1'")
        elif has_base_form:
            report_ok("AutoCommandBar inherited from base form")
        else:
            report_error("AutoCommandBar element missing")

    # --- Collect all elements with IDs ---
    element_ids = {}  # id -> name
    all_elements = []  # list of dicts {Name, Tag, Id, ParentName, Node}

    def collect_elements(node, parent_name):
        nonlocal stopped
        for child in node:
            if not isinstance(child.tag, str):
                continue

            name = child.get("name", "")
            eid = child.get("id", "")

            if name and eid:
                tag = localname(child)

                all_elements.append(
                    {
                        "Name": name,
                        "Tag": tag,
                        "Id": eid,
                        "ParentName": parent_name,
                        "Node": child,
                    }
                )

                if eid != "-1":
                    if eid in element_ids:
                        report_error(f"Duplicate element id={eid}: '{name}' and '{element_ids[eid]}'")
                    else:
                        element_ids[eid] = name

                child_items = child.find(f"{{{F_NS}}}ChildItems")
                if child_items is not None:
                    collect_elements(child_items, name)
                for container_name in ("AutoCommandBar", "ContextMenu"):
                    container = child.find(f"{{{F_NS}}}{container_name}")
                    if container is not None:
                        items = container.find(f"{{{F_NS}}}ChildItems")
                        if items is not None:
                            collect_elements(items, container.get("name") or name)

    child_items_root = root.find(f"{{{F_NS}}}ChildItems")
    if child_items_root is not None:
        collect_elements(child_items_root, "(root)")

    acb = root.find(f"{{{F_NS}}}AutoCommandBar")
    if acb is not None:
        acb_children = acb.find(f"{{{F_NS}}}ChildItems")
        if acb_children is not None:
            collect_elements(
                acb_children,
                "\u0424\u043e\u0440\u043c\u0430\u041a\u043e\u043c\u0430\u043d\u0434\u043d\u0430\u044f\u041f\u0430\u043d\u0435\u043b\u044c",
            )

    # --- Check 3: Unique element IDs ---
    if not stopped:
        # Duplicates already reported during collection
        dup_count = 0
        id_counts = {}
        for el in all_elements:
            eid = el["Id"]
            if eid == "-1":
                continue
            id_counts[eid] = id_counts.get(eid, 0) + 1
        dup_count = sum(1 for v in id_counts.values() if v > 1)
        if dup_count == 0:
            report_ok(f"Unique element IDs: {len(element_ids)} elements")

    # --- Collect attributes (separate ID pool) ---
    attr_map = {}  # name -> node
    attr_ids = {}  # id -> name

    attr_nodes_parent = root.find(f"{{{F_NS}}}Attributes")
    attr_nodes = []
    if attr_nodes_parent is not None:
        attr_nodes = attr_nodes_parent.findall(f"{{{F_NS}}}Attribute")

    for attr in attr_nodes:
        attr_name = attr.get("name", "")
        attr_id = attr.get("id", "")
        if attr_name:
            attr_map[attr_name] = attr
        if attr_id:
            if attr_id in attr_ids:
                report_error(f"Duplicate attribute id={attr_id}: '{attr_name}' and '{attr_ids[attr_id]}'")
            else:
                attr_ids[attr_id] = attr_name

        # Column IDs uniqueness within parent
        col_ids = {}
        columns = attr.find(f"{{{F_NS}}}Columns")
        if columns is not None:
            for col in columns.findall(f"{{{F_NS}}}Column"):
                col_id = col.get("id", "")
                col_name = col.get("name", "")
                if col_id:
                    if col_id in col_ids:
                        report_error(
                            f"Duplicate column id={col_id} in '{attr_name}': '{col_name}' and '{col_ids[col_id]}'"
                        )
                    else:
                        col_ids[col_id] = col_name

    if not stopped:
        if attr_ids:
            report_ok(f"Unique attribute IDs: {len(attr_ids)} entries")

    # --- Collect commands (separate ID pool) ---
    cmd_map = {}  # name -> node
    cmd_ids = {}  # id -> name

    cmd_nodes_parent = root.find(f"{{{F_NS}}}Commands")
    cmd_nodes = []
    if cmd_nodes_parent is not None:
        cmd_nodes = cmd_nodes_parent.findall(f"{{{F_NS}}}Command")

    for cmd in cmd_nodes:
        cmd_name = cmd.get("name", "")
        cmd_id = cmd.get("id", "")
        if cmd_name:
            cmd_map[cmd_name] = cmd
        if cmd_id:
            if cmd_id in cmd_ids:
                report_error(f"Duplicate command id={cmd_id}: '{cmd_name}' and '{cmd_ids[cmd_id]}'")
            else:
                cmd_ids[cmd_id] = cmd_name

    if not stopped:
        if cmd_ids:
            report_ok(f"Unique command IDs: {len(cmd_ids)} entries")

    # --- Check 4: Companion elements ---
    companion_rules = {
        "InputField": ["ContextMenu", "ExtendedTooltip"],
        "CheckBoxField": ["ContextMenu", "ExtendedTooltip"],
        "LabelDecoration": ["ContextMenu", "ExtendedTooltip"],
        "LabelField": ["ContextMenu", "ExtendedTooltip"],
        "PictureDecoration": ["ContextMenu", "ExtendedTooltip"],
        "PictureField": ["ContextMenu", "ExtendedTooltip"],
        "CalendarField": ["ContextMenu", "ExtendedTooltip"],
        "UsualGroup": ["ExtendedTooltip"],
        "Pages": ["ExtendedTooltip"],
        "Page": ["ExtendedTooltip"],
        "Button": ["ExtendedTooltip"],
        "Table": [
            "ContextMenu",
            "AutoCommandBar",
            "SearchStringAddition",
            "ViewStatusAddition",
            "SearchControlAddition",
        ],
    }

    if not stopped:
        companion_errors = 0
        companion_checked = 0

        for el in all_elements:
            if stopped:
                break
            tag = el["Tag"]
            el_name = el["Name"]
            node = el["Node"]

            if tag not in companion_rules:
                continue

            required = companion_rules[tag]
            companion_checked += 1

            for comp_tag in required:
                comp_node = node.find(f"{{{F_NS}}}{comp_tag}")
                if comp_node is None:
                    report_error(f"[{tag}] '{el_name}': missing companion <{comp_tag}>")
                    companion_errors += 1

        if companion_errors == 0 and companion_checked > 0:
            report_ok(f"Companion elements: {companion_checked} elements checked")

    # --- Check 5: DataPath -> Attribute references ---
    if not stopped:
        path_errors = 0
        path_checked = 0
        path_base_skipped = 0

        skip_tags = {
            "ContextMenu",
            "ExtendedTooltip",
            "AutoCommandBar",
            "SearchStringAddition",
            "ViewStatusAddition",
            "SearchControlAddition",
        }
        tables = {el["Name"]: el["Node"] for el in all_elements if el["Tag"] == "Table"}

        for el in all_elements:
            if stopped:
                break
            tag = el["Tag"]
            el_name = el["Name"]
            node = el["Node"]

            if tag in skip_tags:
                continue

            if has_base_form and el["Id"]:
                try:
                    if int(el["Id"]) < 1000000:
                        path_base_skipped += 1
                        continue
                except (ValueError, TypeError):
                    pass

            dp_node = node.find(f"{{{F_NS}}}DataPath")
            if dp_node is None:
                continue

            data_path = (dp_node.text or "").strip()
            if not data_path:
                continue

            path_checked += 1

            clean_path = re.sub(r"\[\d+\]", "", data_path).lstrip("~")
            segments = clean_path.split(".")
            root_attr = segments[0]
            # Items.<Table>.CurrentData.<field> resolves through the table's own DataPath (form-validate).
            hops = 0
            table_error = ""
            while root_attr == "Items" and not table_error:
                hops += 1
                if hops > 10:
                    break
                if len(segments) < 3 or segments[2] != "CurrentData":
                    table_error = "unknown Items.* form, expected Items.<Table>.CurrentData.*"
                    break
                table = tables.get(segments[1])
                if table is None:
                    table_error = f"table '{segments[1]}' not found"
                    break
                table_path = (table.findtext(f"{{{F_NS}}}DataPath") or "").strip()
                if not table_path:
                    root_attr = None
                    break
                segments = re.sub(r"\[\d+\]", "", table_path).lstrip("~").split(".")
                root_attr = segments[0]
            if table_error:
                report_error(f"[{tag}] '{el_name}': DataPath='{data_path}' \u2014 {table_error}")
                path_errors += 1
                continue
            if root_attr is None or root_attr == "Items":
                continue

            if root_attr not in attr_map:
                report_error(f"[{tag}] '{el_name}': DataPath='{data_path}' \u2014 attribute '{root_attr}' not found")
                path_errors += 1

        path_msg = ""
        if path_checked > 0:
            path_msg = f"{path_checked} paths checked"
        if path_base_skipped > 0:
            skip_note = f"{path_base_skipped} base skipped"
            path_msg = f"{path_msg}, {skip_note}" if path_msg else skip_note
        if path_errors == 0 and path_msg:
            report_ok(f"DataPath references: {path_msg}")

    # --- Check 6: Button command references ---
    if not stopped:
        cmd_errors = 0
        cmd_checked = 0

        for el in all_elements:
            if stopped:
                break
            tag = el["Tag"]
            el_name = el["Name"]
            node = el["Node"]

            if tag != "Button":
                continue

            cmd_node = node.find(f"{{{F_NS}}}CommandName")
            if cmd_node is None:
                continue

            cmd_ref = (cmd_node.text or "").strip()
            if not cmd_ref:
                continue

            m = re.match(r"^Form\.Command\.(.+)$", cmd_ref)
            if m:
                cmd_name_ref = m.group(1)
                cmd_checked += 1
                if cmd_name_ref not in cmd_map:
                    report_error(
                        f"[Button] '{el_name}': CommandName='{cmd_ref}' \u2014 command '{cmd_name_ref}' not found in Commands"
                    )
                    cmd_errors += 1

        if cmd_errors == 0 and cmd_checked > 0:
            report_ok(f"Command references: {cmd_checked} buttons checked")

    # --- Check 7: Events have handler names ---
    if not stopped:
        event_errors = 0
        event_checked = 0

        # Form-level events
        form_events = root.find(f"{{{F_NS}}}Events")
        if form_events is not None:
            for evt in form_events.findall(f"{{{F_NS}}}Event"):
                evt_name = evt.get("name", "")
                handler = (evt.text or "").strip()
                event_checked += 1
                if not handler:
                    report_error(f"Form event '{evt_name}': empty handler name")
                    event_errors += 1

        # Element-level events
        for el in all_elements:
            if stopped:
                break
            tag = el["Tag"]
            el_name = el["Name"]
            node = el["Node"]

            events_node = node.find(f"{{{F_NS}}}Events")
            if events_node is None:
                continue

            for evt in events_node.findall(f"{{{F_NS}}}Event"):
                evt_name = evt.get("name", "")
                handler = (evt.text or "").strip()
                event_checked += 1
                if not handler:
                    report_error(f"[{tag}] '{el_name}' event '{evt_name}': empty handler name")
                    event_errors += 1

        if event_errors == 0 and event_checked > 0:
            report_ok(f"Event handlers: {event_checked} events checked")

    # --- Check 8: Command actions ---
    if not stopped:
        action_errors = 0
        action_checked = 0
        inherited_commands = {
            (cmd.get("name"), cmd.get("id"))
            for cmd in root.findall(f"{{{F_NS}}}BaseForm/{{{F_NS}}}Commands/{{{F_NS}}}Command")
        }

        for cmd in cmd_nodes:
            if stopped:
                break
            cmd_name = cmd.get("name", "")
            action_node = cmd.find(f"{{{F_NS}}}Action")
            action_checked += 1
            if action_node is None and (cmd_name, cmd.get("id")) in inherited_commands:
                continue
            if action_node is None or not (action_node.text or "").strip():
                report_error(f"Command '{cmd_name}': missing or empty Action")
                action_errors += 1

        if action_errors == 0 and action_checked > 0:
            report_ok(f"Command actions: {action_checked} commands checked")

    # --- Check 9: MainAttribute count ---
    if not stopped:
        main_count = 0
        for attr in attr_nodes:
            main_node = attr.find(f"{{{F_NS}}}MainAttribute")
            if main_node is not None and (main_node.text or "") == "true":
                main_count += 1

        if main_count <= 1:
            main_info = "1 main attribute" if main_count == 1 else "no main attribute"
            report_ok(f"MainAttribute: {main_info}")
        else:
            report_error(f"Multiple MainAttribute=true ({main_count} found, expected 0 or 1)")

    # --- Check 10: Title must be multilingual XML ---
    if not stopped:
        title_node = root.find(f"{{{F_NS}}}Title")
        if title_node is not None:
            v8_items = title_node.findall(f"{{{V8_NS}}}item")
            if len(v8_items) == 0 and (title_node.text or "").strip():
                report_error(
                    f"Form Title is plain text ('{(title_node.text or '').strip()}') \u2014 must be multilingual XML (<v8:item>). Use top-level 'title' key in form.compile DSL."
                )
            else:
                report_ok("Title: multilingual XML")

    # --- Check 11: Extension-specific validations ---
    base_form_node = root.find(f"{{{F_NS}}}BaseForm")
    is_extension = base_form_node is not None

    if not stopped and is_extension:
        # 11a. BaseForm version
        bf_version = base_form_node.get("version", "")
        if bf_version:
            report_ok(f"BaseForm: version={bf_version}")
        else:
            report_warn("BaseForm: version attribute missing")

        # 11b. callType values validation
        valid_call_types = {"Before", "After", "Override"}
        ct_errors = 0
        ct_checked = 0

        form_events_node = root.find(f"{{{F_NS}}}Events")
        if form_events_node is not None:
            for evt in form_events_node.findall(f"{{{F_NS}}}Event"):
                ct = evt.get("callType", "")
                if ct:
                    ct_checked += 1
                    if ct not in valid_call_types:
                        report_error(
                            f"Form event '{evt.get('name', '')}': invalid callType='{ct}' (expected: Before, After, Override)"
                        )
                        ct_errors += 1

        for el in all_elements:
            if stopped:
                break
            events_node = el["Node"].find(f"{{{F_NS}}}Events")
            if events_node is None:
                continue
            for evt in events_node.findall(f"{{{F_NS}}}Event"):
                ct = evt.get("callType", "")
                if ct:
                    ct_checked += 1
                    if ct not in valid_call_types:
                        report_error(
                            f"[{el['Tag']}] '{el['Name']}' event '{evt.get('name', '')}': invalid callType='{ct}'"
                        )
                        ct_errors += 1

        for cmd in cmd_nodes:
            if stopped:
                break
            cmd_name = cmd.get("name", "")
            for action in cmd.findall(f"{{{F_NS}}}Action"):
                ct = action.get("callType", "")
                if ct:
                    ct_checked += 1
                    if ct not in valid_call_types:
                        report_error(f"Command '{cmd_name}' Action: invalid callType='{ct}'")
                        ct_errors += 1

        if not stopped and ct_errors == 0 and ct_checked > 0:
            report_ok(f"callType values: {ct_checked} checked")

        # 11c. Extension ID ranges
        base_attr_names = set()
        base_cmd_names = set()

        bf_attrs = base_form_node.find(f"{{{F_NS}}}Attributes")
        if bf_attrs is not None:
            for b_attr in bf_attrs.findall(f"{{{F_NS}}}Attribute"):
                ba_name = b_attr.get("name", "")
                if ba_name:
                    base_attr_names.add(ba_name)

        bf_cmds = base_form_node.find(f"{{{F_NS}}}Commands")
        if bf_cmds is not None:
            for b_cmd in bf_cmds.findall(f"{{{F_NS}}}Command"):
                bc_name = b_cmd.get("name", "")
                if bc_name:
                    base_cmd_names.add(bc_name)

        id_warn_count = 0
        for attr in attr_nodes:
            a_name = attr.get("name", "")
            a_id = attr.get("id", "")
            if a_name and a_name not in base_attr_names and a_id:
                try:
                    int_id = int(a_id)
                    if int_id < 1000000:
                        report_warn(f"Attribute '{a_name}' (id={a_id}): extension-added attribute has id < 1000000")
                        id_warn_count += 1
                except (ValueError, TypeError):
                    pass

        for cmd in cmd_nodes:
            c_name = cmd.get("name", "")
            c_id = cmd.get("id", "")
            if c_name and c_name not in base_cmd_names and c_id:
                try:
                    int_id = int(c_id)
                    if int_id < 1000000:
                        report_warn(f"Command '{c_name}' (id={c_id}): extension-added command has id < 1000000")
                        id_warn_count += 1
                except (ValueError, TypeError):
                    pass

        if not stopped and id_warn_count == 0:
            ext_attr_count = sum(1 for a in attr_nodes if a.get("name", "") not in base_attr_names)
            ext_cmd_count = sum(1 for c in cmd_nodes if c.get("name", "") not in base_cmd_names)
            if (ext_attr_count + ext_cmd_count) > 0:
                report_ok(
                    f"Extension ID ranges: {ext_attr_count} attr(s), {ext_cmd_count} cmd(s) \u2014 all >= 1000000"
                )

    # Check callType without BaseForm
    if not stopped and not is_extension:
        call_type_without_base = False
        fe_node = root.find(f"{{{F_NS}}}Events")
        if fe_node is not None:
            for evt in fe_node.findall(f"{{{F_NS}}}Event"):
                if evt.get("callType"):
                    call_type_without_base = True
                    break
        if not call_type_without_base:
            for cmd in cmd_nodes:
                for action in cmd.findall(f"{{{F_NS}}}Action"):
                    if action.get("callType"):
                        call_type_without_base = True
                        break
                if call_type_without_base:
                    break
        if call_type_without_base:
            report_warn("callType attributes found but no BaseForm \u2014 possible incorrect structure")

    # --- Finalize ---
    checks = ok_count + errors + warnings
    if errors == 0 and warnings == 0 and not detailed:
        lines = [f"=== Validation OK: Form.{form_name} ({checks} checks) ==="]
    else:
        output_lines.append("")
        output_lines.append(f"=== Result: {errors} errors, {warnings} warnings ({checks} checks) ===")
        lines = output_lines

    return {"lines": lines, "errors": errors, "warnings": warnings, "ok": ok_count, "stopped": stopped}
