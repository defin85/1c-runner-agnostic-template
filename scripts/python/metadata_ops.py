"""Fixed operation catalog for the unified metadata editor (design D0–D2).

The catalog deliberately separates requested coverage from connected handlers.
Legacy entrypoints are not invoked here. Template/MXL tools remain independent.
"""

from copy import deepcopy

from jsonschema import Draft202012Validator, ValidationError

from . import (
    metadata_create,
    metadata_form_ops,
    metadata_form_schema,
    metadata_object_ops,
    metadata_object_schema,
    metadata_predefined,
    metadata_predefined_ops,
    metadata_template_ops,
)
from .metadata_borrow import (
    borrow_form,
    borrow_object,
    borrow_tabular_section,
    extend_characteristic_types,
    extend_member_type,
    register_borrowed_object,
)

OBJECT_TYPES = (
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
    "CommonModule",
    "ScheduledJob",
    "EventSubscription",
    "HTTPService",
    "WebService",
    "DefinedType",
    "CommonCommand",
    "Subsystem",
)
EDIT_OPERATIONS = (
    *(
        f"{action}-{child}"
        for action in ("add", "remove")
        for child in (
            "attribute",
            "ts",
            "dimension",
            "resource",
            "enumValue",
            "column",
            "form",
            "command",
            "owner",
            "registerRecord",
            "basedOn",
            "inputByString",
        )
    ),
    "add-ts-attribute",
    "remove-ts-attribute",
    "modify-ts-attribute",
    "modify-ts",
    "modify-attribute",
    "modify-dimension",
    "modify-resource",
    "modify-enumValue",
    "modify-column",
    "modify-property",
    "set-owners",
    "set-registerRecords",
    "set-basedOn",
    "set-inputByString",
)
PRESERVED_COMMANDS = (
    "template-add",
    "template-remove",
    "mxl-info",
    "mxl-compile",
    "mxl-decompile",
    "mxl-validate",
)
EXCLUSIONS = {
    "templates": "Template content edits only for registered SpreadsheetDocument templates (template.*); no template registration, removal or MXL/other template kinds; owner removal affecting templates is excluded; HTTPService.URLTemplate is retained.",
    "CommonTemplate": "Not part of object.borrow.",
    "Force": "References block removal, including keepFiles; no bypass.",
    "BaseForm": "Borrowed forms: form element, attribute and command operations reject nodes present in BaseForm; only extension-owned nodes change.",
}

# Requestable operations. Availability comes from HANDLERS; the mapping from
# former commands and the evidence of each operation belong to traceability and
# tests, not to the working catalog. Retired skills are kept out by import sync.
OPERATIONS = (
    "object.rename",
    "object.create",
    "object.edit",
    "object.remove",
    "object.borrow",
    "object.register-borrowed",
    "object.copy-description",
    "form.create",
    "form.compile",
    "form.edit",
    "form.remove",
    "predefined.create",
    "predefined.update",
    "predefined.normalize-dimension-refs",
    "form.borrow",
    "form.add-input",
    "tabular-section.borrow",
    "member.extend-type",
    "object.extend-type",
    "form.set-properties",
    "form.move-element",
    "form.remove-element",
    "form.rename-element",
    "form.set-attribute",
    "form.set-command",
    "form.remove-event",
    *metadata_template_ops.PARAMETER_SCHEMAS,
    "catalog.set-description-fill-checking",
    "chart.add-predefined",
    "chart.remove-predefined",
    "chart.extend-characteristic-type",
    "exchange-plan.edit-content",
)

# Filled only with transferred, in-memory subject functions. This is not a
# public plugin registry; legacy CLI entrypoints never appear here.
HANDLERS: dict = {
    "object.borrow": borrow_object,
    "object.register-borrowed": register_borrowed_object,
    "tabular-section.borrow": borrow_tabular_section,
    "member.extend-type": extend_member_type,
    "object.extend-type": extend_characteristic_types,
    "object.rename": metadata_object_ops.rename_object,
    "form.borrow": borrow_form,
    "object.edit": metadata_object_ops.edit_object,
    "form.add-input": metadata_form_ops.add_input,
    "object.copy-description": metadata_object_ops.copy_description,
    "catalog.set-description-fill-checking": metadata_predefined_ops.set_description_fill_checking,
    "chart.add-predefined": metadata_predefined_ops.add_predefined,
    "chart.remove-predefined": metadata_predefined_ops.remove_predefined,
    "chart.extend-characteristic-type": metadata_predefined_ops.extend_characteristic_type,
    "exchange-plan.edit-content": metadata_object_ops.edit_exchange_plan_content,
    "form.create": metadata_form_ops.create_form,
    "form.compile": metadata_form_ops.compile_form,
    "form.edit": metadata_form_ops.edit_form,
    "form.remove": metadata_form_ops.remove_form,
    "form.set-properties": metadata_form_ops.set_properties,
    "form.move-element": metadata_form_ops.move_element,
    "form.remove-element": metadata_form_ops.remove_element,
    "form.rename-element": metadata_form_ops.rename_element,
    "form.set-attribute": metadata_form_ops.set_attribute,
    "form.set-command": metadata_form_ops.set_command,
    "form.remove-event": metadata_form_ops.remove_event,
    "object.remove": metadata_object_ops.remove_object,
    "object.create": metadata_create.create_object,
}
HANDLERS["predefined.create"] = metadata_predefined.create
HANDLERS["predefined.update"] = metadata_predefined.update
HANDLERS["predefined.normalize-dimension-refs"] = metadata_predefined.normalize_dimension_refs
HANDLERS.update({name: metadata_template_ops.edit for name in metadata_template_ops.OPERATIONS})
HANDLERS["template.import-xlsx"] = metadata_template_ops.import_xlsx


def operation_context(snapshot, operation):
    return (
        metadata_object_ops.property_context(snapshot, operation["target"])
        if operation["op"] == "object.edit"
        else None
    )


def _closed(properties: dict, required: tuple | None = None) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
        "required": list(properties) if required is None else list(required),
    }


# Parameters require the operation-specific validator and snapshot; validating
# this envelope alone never authorizes planning or source writes.
REQUEST_ENVELOPE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    **_closed(
        {
            "schemaVersion": {"type": "integer", "const": 1},
            "operations": {
                "type": "array",
                "minItems": 1,
                "items": _closed(
                    {
                        "op": {"type": "string", "enum": list(OPERATIONS)},
                        "target": {"type": "string", "minLength": 1},
                        "parameters": {"type": "object"},
                    }
                ),
            },
        }
    ),
}
RESULT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    **_closed(
        {
            "schemaVersion": {"type": "integer", "const": 1},
            "status": {
                "enum": [
                    "capabilities",
                    "inspected",
                    "planned",
                    "applied",
                    "already-applied",
                    "verified",
                    "rejected",
                    "failed",
                ]
            },
            "checks": _closed(
                {
                    "platform": {"const": "not-run"},
                    "runtime": {"const": "not-run"},
                    "local": _closed(
                        {
                            "code": {"enum": [0, 2, 3, 4, 5]},
                            "objects": {"type": "array", "minItems": 1, "items": {"type": "object"}},
                        }
                    ),
                },
                ("platform", "runtime"),
            ),
            "changes": {"type": ["object", "array", "null"]},
            "error": {
                "oneOf": [
                    {"type": "null"},
                    _closed(
                        {
                            "code": {"type": "integer", "enum": [2, 3, 4, 5]},
                            "message": {"type": "string", "minLength": 1, "maxLength": 8192},
                        }
                    ),
                ]
            },
        }
    ),
    "allOf": [
        {
            "if": {"properties": {"status": {"enum": ["rejected", "failed"]}}},
            "then": {"properties": {"error": {"type": "object"}, "changes": {"type": "null"}}},
            "else": {"properties": {"error": {"type": "null"}}},
        },
        {
            "if": {"properties": {"status": {"const": "failed"}}},
            "then": {"properties": {"error": {"properties": {"code": {"const": 5}}}}},
        },
        {
            "if": {"properties": {"status": {"const": "rejected"}}},
            "then": {"properties": {"error": {"properties": {"code": {"enum": [2, 3, 4]}}}}},
        },
    ],
}


_NAME = {
    "type": "string",
    "pattern": r"^[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]{0,127}$",
    "not": {"pattern": r"[\x00-\x1f]"},
}
_ROOT = {"type": "string", "minLength": 1, "not": {"pattern": r"[\x00-\x1f]"}}
_LOGICAL_PATH = {
    "type": "string",
    "pattern": r"^[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*(\.[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)+$",
    "not": {"pattern": r"[\x00-\x1f]"},
}
_REVIEWED_DEPENDENCY = metadata_object_schema.REVIEWED_DEPENDENCY
PARAMETER_SCHEMAS = {
    "object.rename": _closed(
        {
            "name": _NAME,
            "forms": {"type": "array", "items": _LOGICAL_PATH, "uniqueItems": True},
            "reviewedDependencies": {"type": "array", "items": _REVIEWED_DEPENDENCY, "uniqueItems": True},
        },
        ("name",),
    ),
    **metadata_form_schema.PARAMETER_SCHEMAS,
    **metadata_form_schema.OPERATION_SCHEMAS,
    **metadata_object_schema.PARAMETER_SCHEMAS,
    "object.borrow": _closed({"baseRoot": _ROOT, "restoreRegistration": {"type": "boolean"}}, ("baseRoot",)),
    "object.register-borrowed": _closed({"baseRoot": _ROOT}),
    "tabular-section.borrow": _closed({"baseRoot": _ROOT}),
    "member.extend-type": _closed(
        {
            "baseRoot": _ROOT,
            "type": {
                "type": "string",
                "pattern": r"^(?:String\((?:0|10|15|60)\)|(?:EnumRef|CatalogRef)\.[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]{0,127})$",
            },
        },
        ("baseRoot", "type"),
    ),
    "object.extend-type": _closed(
        {
            "baseRoot": _ROOT,
            "types": {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1, "uniqueItems": True},
            "checkBaseType": {"type": "boolean"},
        },
        ("baseRoot", "types"),
    ),
    "form.borrow": _closed(
        {
            "baseRoot": _ROOT,
            "borrowMainAttribute": {"enum": ["Form", "All"]},
            "moduleOnly": {"type": "boolean"},
            "nativeProjection": {"type": "boolean"},
            "repairNativeCommandProjection": {"type": "boolean"},
            "repairNativeMainAttributeProjection": {"type": "boolean"},
            "commands": {"type": "array", "items": _NAME, "minItems": 1, "uniqueItems": True},
            "inheritEvents": {"type": "array", "items": _NAME, "minItems": 1, "uniqueItems": True},
        },
        ("baseRoot",),
    ),
    "object.remove": _closed(
        {
            "keepFiles": {"type": "boolean"},
            "reviewedDependencies": {"type": "array", "items": _REVIEWED_DEPENDENCY, "uniqueItems": True},
        },
        (),
    ),
    "predefined.update": _closed(
        {
            "baseRoot": _ROOT,
            "name": _NAME,
            "accountType": {"enum": ["Active", "Passive", "ActivePassive"]},
            "accountingFlags": {"type": "object", "propertyNames": _NAME, "additionalProperties": {"type": "boolean"}},
            "parent": {"anyOf": [_NAME, {"type": "null"}]},
            "order": {"type": "string", "minLength": 1, "maxLength": 64, "pattern": r"\S"},
        },
        ("baseRoot", "name", "accountType", "accountingFlags"),
    ),
    "predefined.normalize-dimension-refs": _closed({"baseRoot": _ROOT}),
    "predefined.create": {
        "oneOf": [
            _closed(
                {
                    "baseRoot": _ROOT,
                    "name": _NAME,
                    "code": {"type": "string", "minLength": 1, "maxLength": 128, "not": {"pattern": r"[\x00-\x1f]"}},
                    "description": {"type": "string", "maxLength": 1024, "not": {"pattern": r"[\x00-\x1f]"}},
                    "accountType": {"enum": ["Active", "Passive", "ActivePassive"]},
                    "offBalance": {"type": "boolean"},
                    "parent": {"anyOf": [_NAME, {"type": "null"}]},
                    "accountingFlags": {
                        "type": "object",
                        "propertyNames": _NAME,
                        "additionalProperties": {"type": "boolean"},
                    },
                    "extDimensions": {
                        "type": "array",
                        "items": _closed(
                            {
                                "name": {
                                    "type": "string",
                                    "minLength": 1,
                                    "maxLength": 512,
                                    "not": {"pattern": r"[\x00-\x1f]"},
                                },
                                "turnover": {"type": "boolean"},
                                "accountingFlags": {
                                    "type": "object",
                                    "propertyNames": _NAME,
                                    "additionalProperties": {"type": "boolean"},
                                },
                            },
                            ("name", "turnover", "accountingFlags"),
                        ),
                    },
                },
                (
                    "baseRoot",
                    "name",
                    "code",
                    "description",
                    "accountType",
                    "offBalance",
                    "accountingFlags",
                    "extDimensions",
                ),
            ),
            _closed(
                {
                    "baseRoot": _ROOT,
                    "name": _NAME,
                    "code": {"type": "string", "minLength": 1, "maxLength": 128, "not": {"pattern": r"[\x00-\x1f]"}},
                    "description": {"type": "string", "maxLength": 1024, "not": {"pattern": r"[\x00-\x1f]"}},
                    "type": {
                        "type": "string",
                        "pattern": r"^CatalogRef\.[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]{0,127}$",
                    },
                    "isFolder": {"const": False},
                },
                ("baseRoot", "name", "code", "description", "type", "isFolder"),
            ),
            # Own catalog (CatalogPredefinedItems): no baseRoot, code optional.
            _closed(
                {
                    "name": _NAME,
                    "code": {"type": "string", "maxLength": 128, "not": {"pattern": r"[\x00-\x1f]"}},
                    "description": {"type": "string", "maxLength": 1024, "not": {"pattern": r"[\x00-\x1f]"}},
                    "isFolder": {"const": False},
                },
                ("name", "description"),
            ),
        ]
    },
    "form.remove": _closed(
        {
            "reviewedDependencies": {"type": "array", "items": _REVIEWED_DEPENDENCY, "uniqueItems": True},
        },
        (),
    ),
    # Each child must subsequently be accounted for against the source snapshot.
    "object.copy-description": _closed(
        {
            "sourceRoot": _ROOT,
            "source": _LOGICAL_PATH,
            "prefix": {"type": "string", "pattern": r"^[A-Za-zА-Яа-яЁё0-9_]*$", "not": {"pattern": r"[\x00-\x1f]"}},
            "include": {"type": "array", "items": _LOGICAL_PATH, "uniqueItems": True},
            "exclude": {"type": "array", "items": _LOGICAL_PATH, "uniqueItems": True},
            "mapping": {"type": "object", "propertyNames": _LOGICAL_PATH, "additionalProperties": _LOGICAL_PATH},
        },
        ("sourceRoot", "source", "prefix", "include", "exclude"),
    ),
    # target is the owner; name is the exact new form name (legacy FormName).
    "form.create": _closed(
        {
            "name": _NAME,
            "synonym": {"type": "string"},
            "purpose": {"enum": ["Object", "List", "Choice", "Record"]},
            "setDefault": {"type": "boolean"},
        },
        ("name",),
    ),
    # Type/qualifiers are read from the snapshot, not supplied or guessed here.
    "form.add-input": _closed(
        {
            "name": _NAME,
            "attribute": {
                "type": "string",
                "pattern": r"^(Объект\.)?[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]{0,127}$",
                "not": {"pattern": r"[\x00-\x1f]"},
            },
            "title": {
                "type": "string",
                "minLength": 1,
                "maxLength": 1024,
                "pattern": r"\S",
                "not": {"pattern": r"[\x00-\x08\x0b\x0c\x0e-\x1f]"},
            },
            "parent": {"anyOf": [_NAME, {"const": "$root"}]},
            "after": _NAME,
        },
        ("name", "attribute", "title", "parent"),
    ),
    **metadata_template_ops.PARAMETER_SCHEMAS,
    "catalog.set-description-fill-checking": _closed(
        {
            "value": {"enum": ["DontCheck", "ShowError", "ShowWarning"]},
        }
    ),
    "chart.add-predefined": _closed(
        {
            "items": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "anyOf": [
                        _closed(
                            {
                                "name": _NAME,
                                "code": {"type": "string", "minLength": 1},
                                "description": {"type": "string"},
                                "parent": _NAME,
                                "accountType": {"enum": ["Active", "Passive", "ActivePassive"]},
                                "offBalance": {"type": "boolean"},
                                "order": {"type": "string", "minLength": 1},
                                "accountingFlags": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        name: {"type": "boolean"}
                                        for name in (
                                            "Валютный",
                                            "Количественный",
                                            "УчетПоПодразделениям",
                                            "НалоговыйУчет",
                                        )
                                    },
                                    "required": ["Валютный", "Количественный", "УчетПоПодразделениям", "НалоговыйУчет"],
                                },
                                "extDimensionTypes": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "properties": {
                                            "name": {"type": "string", "minLength": 1},
                                            "turnover": {"type": "boolean"},
                                            "accountingFlags": {
                                                "type": "object",
                                                "additionalProperties": False,
                                                "properties": {
                                                    name: {"type": "boolean"}
                                                    for name in ("Суммовой", "Валютный", "Количественный")
                                                },
                                                "required": ["Суммовой", "Валютный", "Количественный"],
                                            },
                                        },
                                        "required": ["name", "turnover", "accountingFlags"],
                                    },
                                },
                            },
                            ("name", "code", "description", "accountType", "offBalance", "order", "accountingFlags"),
                        ),
                        _closed(
                            {
                                "name": _NAME,
                                "code": {"type": "string", "minLength": 1},
                                "description": {"type": "string"},
                                "parent": _NAME,
                                "type": {
                                    "anyOf": [
                                        {"type": "string", "minLength": 1},
                                        {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
                                    ]
                                },
                                "isFolder": {"type": "boolean"},
                            },
                            ("name", "code", "description", "type", "isFolder"),
                        ),
                    ]
                },
            },
        }
    ),
    "chart.extend-characteristic-type": _closed(
        {
            "types": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}, "uniqueItems": True},
        }
    ),
    "chart.remove-predefined": _closed(
        {
            "name": _NAME,
            "expectedUuid": {
                "type": "string",
                "pattern": r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
            },
            "reviewedDependencies": {"type": "array", "items": _REVIEWED_DEPENDENCY},
        },
        ("name", "expectedUuid"),
    ),
    "exchange-plan.edit-content": _closed(
        {
            "remove": {"type": "array", "minItems": 1, "items": _LOGICAL_PATH, "uniqueItems": True},
            "deduplicate": {"const": True},
        }
    ),
}


def normalize_operation(operation: dict, *, properties: dict | None = None) -> list[dict]:
    """Normalize one step against properties from its current ordered snapshot.

    No source is read here. The planner calls this after preceding steps, not
    with a property inventory captured before borrow/create operations.
    Array creation targets $root and expands to exact, ordered object targets.
    """
    try:
        Draft202012Validator(REQUEST_ENVELOPE_SCHEMA["properties"]["operations"]["items"]).validate(operation)
    except ValidationError:
        raise ValueError("Invalid request structure") from None
    operation = deepcopy(operation)
    op, parameters = operation["op"], operation["parameters"]
    if op in metadata_form_schema.PARAMETER_SCHEMAS:
        operation["parameters"] = metadata_form_schema.normalize_parameters(op, parameters)
    elif op in metadata_object_schema.PARAMETER_SCHEMAS:
        operation["parameters"] = metadata_object_schema.normalize_parameters(
            op, parameters, properties=properties, object_name=operation["target"]
        )
        if op == "object.create":
            definition = operation["parameters"]["definition"]
            if isinstance(definition, list):
                if operation["target"] != "$root" or not definition:
                    raise ValueError("Array creation requires a root target and nonempty definitions")
                return [
                    {**operation, "target": f"{item['type']}.{item['name']}", "parameters": {"definition": item}}
                    for item in definition
                ]
            if operation["target"] != f"{definition['type']}.{definition['name']}":
                raise ValueError("Creation target does not match definition")
    else:
        try:
            Draft202012Validator(PARAMETER_SCHEMAS[op]).validate(parameters)
        except ValidationError:
            # ValidationError text includes caller data, possibly local secrets.
            raise ValueError("Invalid operation parameters") from None
        if op == "object.remove":
            parameters.setdefault("keepFiles", False)
        elif op == "form.create":
            parameters.setdefault("purpose", "Object")
            parameters.setdefault("setDefault", False)
            parameters.setdefault("synonym", parameters["name"])
        elif op == "object.copy-description":
            parameters.setdefault("mapping", {})
            if set(parameters["include"]) & set(parameters["exclude"]):
                raise ValueError("A child cannot be both included and excluded")
        elif op == "predefined.create":
            if "accountType" in parameters:
                parameters.setdefault("parent", None)
        elif op == "template.import-xlsx":
            parameters.setdefault("replace", False)
    return [operation]


def normalize_request(request: dict) -> dict:
    """Normalize context-independent requests without I/O or write authority.

    Snapshot-dependent edits require normalize_operation in the planner instead.
    """
    try:
        Draft202012Validator(REQUEST_ENVELOPE_SCHEMA).validate(request)
    except ValidationError:
        raise ValueError("Invalid request structure") from None
    result = {"schemaVersion": 1, "operations": []}
    for operation in request["operations"]:
        result["operations"].extend(normalize_operation(operation))
    return result


def capabilities() -> dict:
    """Return declared scope; no handler is qualified merely by being listed."""
    return {
        "layouts": ["CF", "CFE", "EPF", "ERF"],
        "xml": {
            "layout": "Designer-hierarchical",
            "existingVersions": ["2.17", "2.20"],
            "generatedMetadataVersion": "2.17",
            "descriptionConversion": {"Catalog": ["2.20", "2.17"]},
            "unsupported": ["Plain", "EDT", "ordinary-form-binary"],
        },
        "objectTypes": list(OBJECT_TYPES),
        "editOperations": list(EDIT_OPERATIONS),
        "connectedEditOperations": list(metadata_object_ops.CONNECTED_EDIT_OPERATIONS),
        "connectedEditObjectTypes": list(metadata_object_ops.CONNECTED_EDIT_OBJECT_TYPES),
        "connectedCreateObjectTypes": list(metadata_create.KINDS),
        "connectedRemoveObjectTypes": list(metadata_object_ops.REMOVE_DIRECTORIES),
        "connectedRenameObjectTypes": list(metadata_object_ops.RENAME_OBJECT_TYPES),
        "renameDependencyPolicy": "structural-only; selected form references and ExchangePlan Content.xml references are rewritten; BSL and other Ext artifacts remain pendingDependencies; ambiguous references reject planning",
        "operations": {
            name: {"available": name in HANDLERS, "parameterSchema": deepcopy(PARAMETER_SCHEMAS.get(name))}
            for name in OPERATIONS
        },
        "preservedCommands": list(PRESERVED_COMMANDS),
        "exclusions": dict(EXCLUSIONS),
        "requestEnvelopeSchema": deepcopy(REQUEST_ENVELOPE_SCHEMA),
        "resultSchema": deepcopy(RESULT_SCHEMA),
        "checks": {"platform": "not-run", "runtime": "not-run"},
    }
