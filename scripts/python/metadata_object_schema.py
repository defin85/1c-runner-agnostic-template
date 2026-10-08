"""Pure input normalization for metadata objects; no filesystem or XML writes.

The DSL and shorthand algorithms are adapted from Nikolay-Shirokov/cc-1c-skills
meta-compile.py and meta-edit.py v1.5, vendored in automation/vendor/cc-1c-skills.
Copyright (c) 2025-2026 Nick Shirokov; MIT terms are retained in that directory's LICENSE.
Unlike those entrypoints, unknown keys and malformed shorthand are errors.
Property names for edits come from the planner's XML snapshot, not a guessed list.
"""

import re
from copy import deepcopy
from typing import Any, NoReturn

from jsonschema import Draft202012Validator, ValidationError

TEXT = {"type": "string"}
NAME = {"type": "string", "pattern": r"^[^\W\d]\w*$", "maxLength": 128, "not": {"pattern": r"[\x00-\x20]"}}
BOOL = {"type": "boolean"}
INTEGER = {"type": "integer", "minimum": 0}


def obj(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


def array(items):
    return {"type": "array", "items": items}


REVIEWED_DEPENDENCY = obj(
    {
        "path": {"type": "string", "minLength": 1, "not": {"pattern": r"[\x00-\x1f]"}},
        "sha256": {"type": "string", "pattern": r"^[0-9a-f]{64}$"},
        "reason": {"type": "string", "minLength": 1, "not": {"pattern": r"[\x00-\x1f]"}},
    },
    ("path", "sha256", "reason"),
)


def named_map(value):
    return {"type": "object", "propertyNames": NAME, "additionalProperties": value}


REVIEWED_DEPENDENCY = obj(
    {
        "path": {"type": "string", "minLength": 1, "not": {"pattern": r"[\x00-\x1f]"}},
        "sha256": {"type": "string", "pattern": r"^[0-9a-f]{64}$"},
        "reason": {"type": "string", "minLength": 1, "not": {"pattern": r"[\x00-\x1f]"}},
    },
    ("path", "sha256", "reason"),
)


TYPE = {"anyOf": [dict(TEXT, minLength=1), array(dict(TEXT, minLength=1))]}
FLAGS = array({"enum": ["req", "index", "indexadditional", "master", "mainfilter", "denyincomplete", "nouseintotals"]})
ATTRIBUTE = obj(
    {
        "name": NAME,
        "type": TYPE,
        "synonym": TEXT,
        "comment": TEXT,
        "flags": FLAGS,
        "fillChecking": TEXT,
        "indexing": TEXT,
        "after": NAME,
        "before": NAME,
    },
    ("name",),
)
ADDRESSING_ATTRIBUTE = obj({**ATTRIBUTE["properties"], "addressingDimension": TEXT}, ("name",))
ENUM_VALUE = obj(
    {
        key: value
        for key, value in ATTRIBUTE["properties"].items()
        if key in ("name", "synonym", "comment", "after", "before")
    },
    ("name",),
)
COLUMN = obj({"name": NAME, "synonym": TEXT, "indexing": TEXT, "references": array(TEXT)}, ("name",))
TABULAR_SECTION = obj({"name": NAME, "synonym": TEXT, "attributes": array(ATTRIBUTE)}, ("name",))
URL_TEMPLATE = obj({"template": TEXT, "methods": named_map(TEXT)})
WS_PARAMETER = obj({"type": TEXT, "nillable": BOOL, "direction": TEXT})
WS_OPERATION = obj(
    {
        "returnType": TEXT,
        "nillable": BOOL,
        "transactioned": BOOL,
        "handler": TEXT,
        "parameters": named_map(WS_PARAMETER),
    }
)

# The per-type fields below are the inputs actually consumed by the vendored
# emit_*_properties functions. A field belonging to another type is not ignored.
_FIELDS = {
    "Catalog": "hierarchical hierarchyType codeLength descriptionLength descriptionFillChecking codeType codeAllowedLength autonumbering checkUnique defaultPresentation dataLockControlMode fullTextSearch",
    "Document": "numberType numberLength numberAllowedLength numberPeriodicity checkUnique autonumbering posting realTimePosting registerRecordsDeletion registerRecordsWritingOnPost sequenceFilling postInPrivilegedMode unpostInPrivilegedMode registerRecords dataLockControlMode fullTextSearch",
    "Enum": "values",
    "Constant": "valueType length precision nonneg nonnegative dataLockControlMode",
    "InformationRegister": "periodicity writeMode mainFilterOnPeriod dataLockControlMode fullTextSearch",
    "AccumulationRegister": "registerType enableTotalsSplitting dataLockControlMode fullTextSearch",
    "AccountingRegister": "chartOfAccounts correspondence periodAdjustmentLength dataLockControlMode fullTextSearch",
    "CalculationRegister": "chartOfCalculationTypes periodicity actionPeriod basePeriod schedule scheduleValue scheduleDate dataLockControlMode fullTextSearch",
    "ChartOfAccounts": "extDimensionTypes maxExtDimensionCount codeMask codeLength descriptionLength codeSeries autoOrderByCode orderLength dataLockControlMode fullTextSearch accountingFlags extDimensionAccountingFlags",
    "ChartOfCharacteristicTypes": "codeLength descriptionLength codeAllowedLength autonumbering checkUnique characteristicExtValues valueTypes hierarchical dataLockControlMode fullTextSearch",
    "ChartOfCalculationTypes": "codeLength descriptionLength codeType codeAllowedLength dependenceOnCalculationTypes baseCalculationTypes actionPeriodUse dataLockControlMode fullTextSearch",
    "BusinessProcess": "editType numberType numberLength numberAllowedLength checkUnique autonumbering task dataLockControlMode fullTextSearch",
    "Task": "numberType numberLength numberAllowedLength checkUnique autonumbering taskNumberAutoPrefix descriptionLength addressing mainAddressingAttribute currentPerformer dataLockControlMode fullTextSearch addressingAttributes",
    "ExchangePlan": "codeLength descriptionLength codeAllowedLength distributedInfoBase includeConfigurationExtensions dataLockControlMode fullTextSearch",
    "DocumentJournal": "defaultForm auxiliaryForm registeredDocuments columns",
    "Report": "defaultForm auxiliaryForm mainDataCompositionSchema defaultSettingsForm auxiliarySettingsForm defaultVariantForm",
    "DataProcessor": "defaultForm auxiliaryForm",
    "CommonModule": "context global server serverCall clientManagedApplication clientOrdinaryApplication externalConnection privileged returnValuesReuse",
    "ScheduledJob": "methodName description key use predefined restartCountOnFailure restartIntervalOnFailure",
    "EventSubscription": "source event handler",
    "HTTPService": "rootURL reuseSessions sessionMaxAge urlTemplates",
    "WebService": "namespace xdtoPackages reuseSessions sessionMaxAge operations",
    "DefinedType": "valueTypes",
    "CommonCommand": "group representation toolTip parameterTypes parameterUseMode modifiesData",
    "Subsystem": "includeInCommandInterface useOneCommand explanation picture content",
}
OBJECT_TYPES = tuple(_FIELDS)
_ATTR_TS = {
    "Catalog",
    "Document",
    "Report",
    "DataProcessor",
    "ExchangePlan",
    "ChartOfCharacteristicTypes",
    "ChartOfAccounts",
    "ChartOfCalculationTypes",
    "BusinessProcess",
    "Task",
}
_REGISTERS = {"InformationRegister", "AccumulationRegister", "AccountingRegister", "CalculationRegister"}
_BOOLEAN_FIELDS = set(
    "hierarchical autonumbering checkUnique postInPrivilegedMode unpostInPrivilegedMode mainFilterOnPeriod enableTotalsSplitting correspondence actionPeriod basePeriod autoOrderByCode actionPeriodUse distributedInfoBase includeConfigurationExtensions modifiesData includeInCommandInterface useOneCommand global server serverCall clientManagedApplication clientOrdinaryApplication externalConnection privileged use predefined nonneg nonnegative".split()
)
_INTEGER_FIELDS = set(
    "codeLength descriptionLength numberLength periodAdjustmentLength maxExtDimensionCount orderLength length precision restartCountOnFailure restartIntervalOnFailure sessionMaxAge".split()
)
_LIST_FIELDS = set(
    "content parameterTypes registerRecords valueTypes baseCalculationTypes registeredDocuments source accountingFlags extDimensionAccountingFlags".split()
)
_SPECIAL_FIELDS = {
    "values": array(ENUM_VALUE),
    "representation": {"enum": ["Auto", "Text", "Picture", "PictureAndText"]},
    "parameterUseMode": {"enum": ["Single", "Multiple"]},
    "columns": array(COLUMN),
    "descriptionFillChecking": {"enum": ["DontCheck", "ShowError", "ShowWarning"]},
    "addressingAttributes": array(ADDRESSING_ATTRIBUTE),
    "urlTemplates": named_map(URL_TEMPLATE),
    "operations": named_map(WS_OPERATION),
    "valueType": TYPE,
}


def _create_schema(kind):
    properties = {"type": {"const": kind}, "name": NAME, "synonym": TEXT, "comment": TEXT}
    for key in _FIELDS[kind].split():
        properties[key] = _SPECIAL_FIELDS.get(key) or (
            BOOL
            if key in _BOOLEAN_FIELDS
            else INTEGER
            if key in _INTEGER_FIELDS
            else array(TEXT)
            if key in _LIST_FIELDS
            else TEXT
        )
    if kind in _ATTR_TS | _REGISTERS:
        properties["attributes"] = array(ATTRIBUTE)
    if kind in _ATTR_TS:
        properties["tabularSections"] = array(TABULAR_SECTION)
    if kind in _REGISTERS:
        properties.update(dimensions=array(ATTRIBUTE), resources=array(ATTRIBUTE))
    return obj(properties, ("type", "name"))


CREATE_DEFINITION = {"oneOf": [_create_schema(kind) for kind in OBJECT_TYPES]}
_CHILDREN = {
    "attribute": "attributes",
    "ts": "tabularSections",
    "dimension": "dimensions",
    "resource": "resources",
    "enumValue": "enumValues",
    "column": "columns",
    "form": "forms",
    "command": "commands",
}
_COMPLEX = {
    "owner": "Owners",
    "owners": "Owners",
    "registerRecord": "RegisterRecords",
    "registerRecords": "RegisterRecords",
    "basedOn": "BasedOn",
    "inputByString": "InputByString",
}
EDIT_OPERATIONS = tuple(
    [
        f"{action}-{child}"
        for action in ("add", "remove")
        for child in (*_CHILDREN, "owner", "registerRecord", "basedOn", "inputByString")
    ]
    + [
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
    ]
)
_CHILD_SCHEMA = {
    "attributes": ATTRIBUTE,
    "dimensions": ATTRIBUTE,
    "resources": ATTRIBUTE,
    "tabularSections": TABULAR_SECTION,
    "enumValues": ENUM_VALUE,
    "columns": COLUMN,
    "forms": obj({"name": NAME}, ("name",)),
    "commands": obj({"name": NAME}, ("name",)),
}
SCALAR = {"type": ["string", "boolean", "number"]}
PROPERTY_MAP = {"type": "object", "additionalProperties": {"anyOf": [SCALAR, array(TEXT)]}}
LOGICAL_NAME = {"type": "string", "pattern": r"^[^\W\d]\w{0,127}\.[^\W\d]\w{0,127}$", "maxLength": 257}
CONTENT_RENAMES = {
    "type": "object",
    "minProperties": 1,
    "propertyNames": LOGICAL_NAME,
    "additionalProperties": LOGICAL_NAME,
}
_CHANGES = {
    "type": "object",
    "properties": {"name": NAME, "type": TYPE, "synonym": TEXT, "addTypes": array(TEXT)},
    "additionalProperties": SCALAR,
}
_TS_CHANGES = {
    "type": "object",
    "properties": {"add": array(ATTRIBUTE), "remove": array(NAME), "modify": named_map(_CHANGES)},
    "additionalProperties": SCALAR,
}
EXCHANGE_PLAN_CONTENT_CHANGE = obj(
    {
        "replaceMetadata": obj({"from": TEXT, "to": TEXT}, ("from", "to")),
    },
    ("replaceMetadata",),
)
EDIT_DEFINITION = obj(
    {
        "contentRenames": CONTENT_RENAMES,
        "contentDeduplicate": {"const": True},
        "add": obj({key: array(value) for key, value in _CHILD_SCHEMA.items()}),
        "remove": obj({key: array(NAME) for key in _CHILD_SCHEMA}),
        "modify": obj(
            {
                "properties": PROPERTY_MAP,
                **{key: named_map(_TS_CHANGES if key == "tabularSections" else _CHANGES) for key in _CHILD_SCHEMA},
            }
        ),
        "_complex": array(
            obj(
                {
                    "action": {"enum": ["add", "remove", "set"]},
                    "property": {"enum": list(dict.fromkeys(_COMPLEX.values()))},
                    "values": array(TEXT),
                },
                ("action", "property", "values"),
            )
        ),
        "exchangePlanContent": EXCHANGE_PLAN_CONTENT_CHANGE,
    }
)
PARAMETER_SCHEMAS = {
    "object.create": obj({"definition": {"anyOf": [CREATE_DEFINITION, array(CREATE_DEFINITION)]}}, ("definition",)),
    "object.edit": obj(
        {"definition": EDIT_DEFINITION, "reviewedDependencies": array(REVIEWED_DEPENDENCY)}, ("definition",)
    ),
}

_OBJECT_ALIASES = dict(
    zip(
        "Справочник Документ Перечисление Константа РегистрСведений РегистрНакопления РегистрБухгалтерии РегистрРасчета ПланСчетов ПланВидовХарактеристик ПланВидовРасчета БизнесПроцесс Задача ПланОбмена ЖурналДокументов Отчет Обработка ОбщийМодуль РегламентноеЗадание ПодпискаНаСобытие HTTPСервис ВебСервис ОпределяемыйТип ОбщаяКоманда Подсистема".split(),
        OBJECT_TYPES,
        strict=False,
    )
)
_OBJECT_ALIASES.update(
    {
        "Каталог": "Catalog",
        "РегистрРасчёта": "CalculationRegister",
        "ПланВидовРасчёта": "ChartOfCalculationTypes",
        "Отчёт": "Report",
    }
)
_TYPE_ALIASES: dict[str, str] = {
    "число": "Number",
    "строка": "String",
    "булево": "Boolean",
    "дата": "Date",
    "датавремя": "DateTime",
    "bool": "Boolean",
    "хранилищезначения": "ValueStorage",
    "уникальныйидентификатор": "UUID",
    "определяемыйтип": "DefinedType",
    "характеристика": "Characteristic",
}
for _kind, _ru in [
    ("Catalog", "справочник"),
    ("Document", "документ"),
    ("Enum", "перечисление"),
    ("ChartOfAccounts", "плансчетов"),
    ("ChartOfCharacteristicTypes", "планвидовхарактеристик"),
    ("ChartOfCalculationTypes", "планвидоврасчета"),
    ("ExchangePlan", "планобмена"),
    ("BusinessProcess", "бизнеспроцесс"),
    ("Task", "задача"),
]:
    _TYPE_ALIASES[_ru + "ссылка"] = _kind + "Ref"
_TYPE_ALIASES["планвидоврасчётассылка"] = "ChartOfCalculationTypesRef"
BARE_TYPE_NAMES = frozenset(
    {
        "AnyRef",
        "CatalogRef",
        "DocumentRef",
        "ChartOfAccountsRef",
        "ChartOfCharacteristicTypesRef",
        "ChartOfCalculationTypesRef",
        "BusinessProcessRef",
        "TaskRef",
        "ExchangePlanRef",
    }
)
for _type in [*_TYPE_ALIASES.values(), *BARE_TYPE_NAMES, "String", "Number", "Boolean", "Date", "DateTime"]:
    _TYPE_ALIASES[_type.lower()] = _type
_ACTION_ALIASES = {"добавить": "add", "удалить": "remove", "изменить": "modify"}
_CHILD_ALIASES: dict[str, str] = dict(
    zip(
        "реквизиты табличныечасти измерения ресурсы значения графы формы команды свойства".split(),
        [*_CHILDREN.values(), "properties"],
        strict=False,
    )
)
_CHILD_ALIASES.update(
    {
        "attrs": "attributes",
        "тч": "tabularSections",
        "ts": "tabularSections",
        "dims": "dimensions",
        "res": "resources",
        "values": "enumValues",
        "колонки": "columns",
    }
)
_CHILD_ALIASES.update({value.lower(): value for value in (*_CHILDREN.values(), "properties")})
_ENUM_ALIASES = {
    "Balances": "Balance",
    "Остатки": "Balance",
    "Обороты": "Turnovers",
    "RecordSubordinate": "RecorderSubordinate",
    "Subordinate": "RecorderSubordinate",
    "ПодчинениеРегистратору": "RecorderSubordinate",
    "Независимый": "Independent",
    "NotDependOnCalculationTypes": "DontUse",
    "NoDependence": "DontUse",
    "Depend": "RequireCalculationTypes",
    "RequireCalculation": "RequireCalculationTypes",
    "None": "Nonperiodical",
    "Daily": "Day",
    "Monthly": "Month",
    "Quarterly": "Quarter",
    "Yearly": "Year",
    "Непериодический": "Nonperiodical",
    "Секунда": "Second",
    "День": "Day",
    "Месяц": "Month",
    "Квартал": "Quarter",
    "Год": "Year",
    "ПозицияРегистратора": "RecorderPosition",
    "Автоматический": "Automatic",
    "Управляемый": "Managed",
    "Использовать": "Use",
    "НеИспользовать": "DontUse",
    "Разрешить": "Allow",
    "Запретить": "Deny",
    "ВДиалоге": "InDialog",
    "ВСписке": "InList",
    "ОбаСпособа": "BothWays",
    "ВВидеНаименования": "AsDescription",
    "ВВидеКода": "AsCode",
    "НеПроверять": "DontCheck",
    "Ошибка": "ShowError",
    "Предупреждение": "ShowWarning",
    "НеИндексировать": "DontIndex",
    "Индексировать": "Index",
    "ИндексироватьСДопУпорядочиванием": "IndexWithAdditionalOrder",
}
_ENUM_VALUES = {
    "RegisterType": "Balance Turnovers",
    "WriteMode": "Independent RecorderSubordinate",
    "InformationRegisterPeriodicity": "Nonperiodical Second Day Month Quarter Year RecorderPosition",
    "DependenceOnCalculationTypes": "DontUse RequireCalculationTypes",
    "DataLockControlMode": "Automatic Managed",
    "FullTextSearch": "Use DontUse",
    "DataHistory": "Use DontUse",
    "DefaultPresentation": "AsDescription AsCode",
    "Posting": "Allow Deny",
    "RealTimePosting": "Allow Deny",
    "EditType": "InDialog InList BothWays",
    "HierarchyType": "HierarchyFoldersAndItems HierarchyOfItems",
    "CodeType": "String Number",
    "CodeAllowedLength": "Variable Fixed",
    "NumberType": "String Number",
    "NumberAllowedLength": "Variable Fixed",
    "RegisterRecordsDeletion": "AutoDelete AutoDeleteOnUnpost AutoDeleteOff",
    "RegisterRecordsWritingOnPost": "WriteModified WriteSelected WriteAll",
    "ReturnValuesReuse": "DontUse DuringRequest DuringSession",
    "ReuseSessions": "DontUse AutoUse",
    "FillChecking": "DontCheck ShowError ShowWarning",
    "Indexing": "DontIndex Index IndexWithAdditionalOrder",
}


def _enum(key, value):
    options = _ENUM_VALUES.get(key)
    if not options:
        return value
    if not isinstance(value, str):
        _error("enum property: expected string")
    value = _ENUM_ALIASES.get(value, value)
    for candidate in options.split():
        if candidate.lower() == value.lower():
            return candidate
    _error("enum property: unsupported value")


def _error(message) -> NoReturn:
    raise ValidationError(message)


def _mapping(value, label) -> dict[str, Any]:
    if not isinstance(value, dict):
        _error(f"{label}: expected object")
    return value


def _keys(value, allowed, label):
    _mapping(value, label)
    if set(value) - set(allowed):
        _error(f"{label}: unknown keys")


def _aliases(value, aliases, label):
    result = {}
    for key, item in _mapping(value, label).items():
        normal = aliases.get(key.strip().lower(), key)
        if normal in result:
            _error(f"{label}: duplicate alias")
        result[normal] = item
    return result


def normalize_type(value):
    if isinstance(value, list):
        if not value:
            _error("type: empty union")
        return " + ".join(normalize_type(item) for item in value)
    if not isinstance(value, str) or not value.strip():
        _error("type: expected nonempty string")
    parts = []
    for part in value.split(" + "):
        match = re.fullmatch(r"([^.(]+)(.*)", part.strip())
        if not match:
            _error("type: malformed type")
        base, suffix = match.groups()
        parts.append(_TYPE_ALIASES.get(base.lower(), base) + suffix)
    return " + ".join(parts)


def _attribute(value, *, create=False, addressing=False):
    if isinstance(value, str):
        position = re.search(r"\s*(>>\s*after|<<\s*before)\s+(\S+)\s*$", value)
        placement = {}
        if position:
            if create:
                _error("attribute: creation does not support placement")
            placement["after" if position.group(1).startswith(">>") else "before"] = position.group(2)
            value = value[: position.start()].strip()
        main, separator, flags = value.partition("|")
        name, colon, value_type = main.partition(":")
        result = {"name": name.strip(), **placement}
        if colon:
            result["type"] = value_type.strip()
        if separator:
            result["flags"] = [flag.strip().lower() for flag in flags.split(",") if flag.strip()]
    else:
        result = dict(_mapping(value, "attribute"))
        allowed = set(ATTRIBUTE["properties"])
        if create:
            allowed = (allowed - {"after", "before"}) | {"valueType", "length", "precision", "nonneg", "nonnegative"}
        if addressing:
            allowed.add("addressingDimension")
        _keys(result, allowed, "attribute")
        if "valueType" in result:
            if "type" in result:
                _error("attribute: duplicate type")
            result["type"] = result.pop("valueType")
        if any(key in result for key in ("length", "precision", "nonneg", "nonnegative")):
            qualifiers = {
                key: result.pop(key) for key in ("length", "precision", "nonneg", "nonnegative") if key in result
            }
            Draft202012Validator(
                obj({"length": INTEGER, "precision": INTEGER, "nonneg": BOOL, "nonnegative": BOOL})
            ).validate(qualifiers)
            if (
                "nonneg" in qualifiers
                and "nonnegative" in qualifiers
                and qualifiers["nonneg"] != qualifiers["nonnegative"]
            ):
                _error("attribute: conflicting nonnegative aliases")
            base = normalize_type(result.get("type", ""))
            if base not in ("String", "Number") or "length" not in qualifiers:
                _error("attribute: qualifiers require String/Number and length")
            if base == "String":
                if set(qualifiers) != {"length"}:
                    _error("attribute: unexpected String qualifiers")
                result["type"] = f"String({qualifiers['length']})"
            else:
                nonneg = qualifiers.get("nonneg", qualifiers.get("nonnegative", False))
                result["type"] = (
                    f"Number({qualifiers['length']},{qualifiers.get('precision', 0)}{',nonneg' if nonneg else ''})"
                )
    if "type" in result:
        result["type"] = normalize_type(result["type"])
    for key in ("fillChecking", "indexing"):
        if key in result:
            result[key] = _enum(key[0].upper() + key[1:], result[key])
    if "after" in result and "before" in result:
        _error("attribute: after and before are mutually exclusive")
    return result


def _list(value, label):
    if not isinstance(value, list):
        _error(f"{label}: expected array")
    return value


def _attributes(value, create=False, addressing=False):
    if create and isinstance(value, dict):
        value = [{"name": key, "type": item} for key, item in value.items()]
    return [_attribute(item, create=create, addressing=addressing) for item in _list(value, "attributes")]


def _named(value) -> dict[str, Any]:
    return {"name": value} if isinstance(value, str) else dict(_mapping(value, "named item"))


def _sections(value, create):
    if create and isinstance(value, dict):
        value = [{"name": key, "attributes": item} for key, item in value.items()]
    sections = []
    for item in _list(value, "tabularSections"):
        item = _named(item)
        for alias in ("attrs", "реквизиты"):
            if alias in item:
                if "attributes" in item:
                    _error("tabularSections: duplicate attribute alias")
                item["attributes"] = item.pop(alias)
        if "attributes" in item:
            item["attributes"] = _attributes(item["attributes"], create)
        sections.append(item)
    return sections


def _create(value):
    value = dict(_mapping(value, "definition"))
    if "objectType" in value:
        if "type" in value:
            _error("definition: duplicate object type")
        value["type"] = value.pop("objectType")
    if not isinstance(value.get("type"), str):
        _error("definition: object type required")
    value["type"] = _OBJECT_ALIASES.get(value["type"], value["type"])
    for key in ("attributes", "dimensions", "resources", "addressingAttributes"):
        if key in value:
            value[key] = _attributes(value[key], create=True, addressing=key == "addressingAttributes")
    if "tabularSections" in value:
        value["tabularSections"] = _sections(value["tabularSections"], True)
    for key in ("values", "columns"):
        if key in value:
            value[key] = [_named(item) for item in _list(value[key], key)]
            if any("after" in item or "before" in item for item in value[key]):
                _error("creation children do not support placement")
    if value.get("type") == "DefinedType" and "valueType" in value:
        if "valueTypes" in value:
            _error("definition: duplicate value types")
        item = value.pop("valueType")
        value["valueTypes"] = item if isinstance(item, list) else [item]
    if "valueTypes" in value:
        value["valueTypes"] = [normalize_type(item) for item in _list(value["valueTypes"], "valueTypes")]
    if "valueType" in value:
        value["valueType"] = normalize_type(value["valueType"])
    if "urlTemplates" in value:
        value["urlTemplates"] = {
            key: {"template": item} if isinstance(item, str) else item
            for key, item in _mapping(value["urlTemplates"], "urlTemplates").items()
        }
    if "operations" in value:
        operations = {}
        for key, item in _mapping(value["operations"], "operations").items():
            operation_definition: dict[str, Any] = (
                {"returnType": item} if isinstance(item, str) else dict(_mapping(item, "WebService operation"))
            )
            if "parameters" in operation_definition:
                operation_definition["parameters"] = {
                    name: {"type": parameter} if isinstance(parameter, str) else parameter
                    for name, parameter in _mapping(operation_definition["parameters"], "parameters").items()
                }
            operations[key] = operation_definition
        value["operations"] = operations
    for key in value:
        property_name = (
            "InformationRegisterPeriodicity"
            if key in ("periodicity", "numberPeriodicity")
            else key[0].upper() + key[1:]
        )
        value[key] = _enum(property_name, value[key])
    return value


def _split(value, delimiter=","):
    parts, start, depth = [], 0, 0
    for index, character in enumerate(value):
        depth += (character == "(") - (character == ")")
        if depth < 0:
            _error("inline: unbalanced parentheses")
        if character == delimiter and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    if depth:
        _error("inline: unbalanced parentheses")
    parts.append(value[start:].strip())
    return parts


def _pairs(parts):
    result = {}
    for part in parts:
        key, separator, value = part.partition("=")
        key = key.strip()
        if not separator or not key or key in result:
            _error("inline: malformed or duplicate assignment")
        result[key] = value.strip()
    return result


def _modifications(items):
    result = {}
    for item in items:
        name, colon, changes = item.partition(":")
        name = name.strip()
        if not colon or not name or name in result:
            _error("inline: malformed or duplicate modification")
        result[name] = _pairs(_split(changes))
    return result


def _inline(operation, value, object_name):
    if operation not in EDIT_OPERATIONS or not isinstance(value, str):
        _error("inline: unsupported operation or value")
    action, target = operation.split("-", 1)
    items = [part.strip() for part in value.split(";;") if part.strip()]
    if target in _COMPLEX:
        if target == "inputByString":
            if not object_name:
                _error("inputByString: object_name context required")
            items = [item if item.split(".")[0] in OBJECT_TYPES else f"{object_name}.{item}" for item in items]
        return {"_complex": [{"action": action, "property": _COMPLEX[target], "values": items}]}
    if target == "ts-attribute":
        sections = {}
        for item in items:
            name, dot, rest = item.partition(".")
            if not dot or not name or not rest:
                _error("inline: expected Section.Attribute")
            sections.setdefault(name, []).append(rest)
        return {
            "modify": {
                "tabularSections": {
                    name: {action: _modifications(values) if action == "modify" else values}
                    for name, values in sections.items()
                }
            }
        }
    if target == "property":
        return {"modify": {"properties": _pairs(items)}}
    child = _CHILDREN[target]
    if action == "modify":
        return {"modify": {child: _modifications(items)}}
    if action == "add" and target == "ts":
        sections = []
        for item in items:
            name, colon, rest = item.partition(":")
            attributes = []
            if colon:
                for part in _split(rest):
                    if attributes and not re.match(r"^[^\W\d]\w*\s*:", part):
                        attributes[-1] += ", " + part
                    else:
                        attributes.append(part)
            sections.append({"name": name.strip(), "attributes": attributes})
        items = sections
    return {action: {child: items}}


def _changes(value, *, properties, path):
    value = dict(_mapping(value, "changes"))
    allowed = properties.get(path) if properties is not None else None
    for key, item in value.items():
        if key == "type":
            value[key] = normalize_type(item)
        elif key == "addTypes":
            value[key] = [normalize_type(part) for part in _list(item, key)]
        elif key not in ("name", "synonym"):
            if allowed is None:
                _error("modify: properties context required")
            if key not in allowed:
                _error("modify: unknown property in snapshot")
            value[key] = _enum(key, item)
    return value


def _edit(value, *, properties):
    value = _aliases(value, _ACTION_ALIASES, "definition")
    for action in ("add", "remove", "modify"):
        if action not in value:
            continue
        children = _aliases(value[action], _CHILD_ALIASES, action)
        for child, items in children.items():
            if action == "add":
                if child in ("attributes", "dimensions", "resources"):
                    children[child] = _attributes(items)
                elif child == "tabularSections":
                    children[child] = _sections(items, False)
                elif child in _CHILD_SCHEMA:
                    children[child] = [_named(item) for item in _list(items, child)]
            elif action == "modify":
                if child == "properties":
                    _keys(items, properties.get("", ()) if properties is not None else (), "modify properties")
                    for key, item in items.items():
                        if isinstance(item, list) and key not in _COMPLEX.values():
                            _error("modify properties: array only supported for complex properties")
                    children[child] = {key: _enum(key, item) for key, item in items.items()}
                elif child in _CHILD_SCHEMA:
                    updates = {}
                    for name, changes in _mapping(items, "modify children").items():
                        path = f"{child}.{name}"
                        if child == "tabularSections":
                            changes = dict(_mapping(changes, "section changes"))
                            nested = {}
                            for nested_action in ("add", "remove", "modify"):
                                if nested_action in changes:
                                    nested[nested_action] = changes.pop(nested_action)
                            changes = _changes(changes, properties=properties, path=path)
                            if "add" in nested:
                                item = nested["add"]
                                nested["add"] = _attributes(item if isinstance(item, list) else [item])
                            if "remove" in nested and not isinstance(nested["remove"], list):
                                nested["remove"] = [nested["remove"]]
                            if "modify" in nested:
                                nested["modify"] = {
                                    attr: _changes(update, properties=properties, path=f"{path}.attributes.{attr}")
                                    for attr, update in _mapping(nested["modify"], "section modifications").items()
                                }
                            changes.update(nested)
                        else:
                            changes = _changes(changes, properties=properties, path=path)
                        updates[name] = changes
                    children[child] = updates
        value[action] = children
    return value


def _normalize_parameters(operation, parameters, *, properties=None, object_name=None):
    """Return canonical DSL. ``properties`` maps logical child paths to XML keys.

    Use '' for root properties, 'attributes.Name' for a child and
    'tabularSections.Rows.attributes.Name' for an attribute in a tabular section.
    The caller derives this context from its current, ordered XML snapshot.
    This function never reads paths and never claims platform validity.
    """
    parameters = deepcopy(parameters)
    _keys(
        parameters,
        ("definition", "operation", "value", "reviewedDependencies") if operation == "object.edit" else ("definition",),
        "parameters",
    )
    reviewed_dependencies = parameters.get("reviewedDependencies")
    if operation == "object.create":
        definition = parameters.get("definition")
        parameters["definition"] = (
            [_create(item) for item in definition] if isinstance(definition, list) else _create(definition)
        )
    elif operation == "object.edit":
        reviewed_dependencies = parameters.get("reviewedDependencies")
        if "operation" in parameters:
            if "definition" in parameters:
                _error("parameters: definition and operation are mutually exclusive")
            definition = _inline(parameters["operation"], parameters.get("value", ""), object_name)
        else:
            if "value" in parameters:
                _error("parameters: value requires operation")
            definition = parameters.get("definition")
        parameters = {"definition": _edit(definition, properties=properties)}
        if reviewed_dependencies is not None:
            parameters["reviewedDependencies"] = reviewed_dependencies
    else:
        _error("unsupported object operation")
    Draft202012Validator(PARAMETER_SCHEMAS[operation]).validate(parameters)
    return parameters


def normalize_parameters(operation, parameters, *, properties=None, object_name=None):
    """Normalize without leaking request data in validator errors.

    ``properties`` has the logical-path format documented on _normalize_parameters.
    Its presence does not prove the child exists: the planner must resolve each
    target against the snapshot, including special name/type/synonym setters.
    """
    try:
        return _normalize_parameters(operation, parameters, properties=properties, object_name=object_name)
    except ValidationError:
        raise ValueError("Invalid object operation parameters") from None
