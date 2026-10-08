"""Object DSL contracts; these are not platform/BSL qualification tests."""

import tests.python.metadata_test_support  # noqa: F401, I001 — runs first: skips the module without pytest, lxml, jsonschema
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator

from scripts.python import metadata_object_schema as schema


@pytest.mark.parametrize("kind", schema.OBJECT_TYPES)
def test_create_all_existing_object_types(kind):
    data = {"definition": {"type": kind, "name": "Тест"}}
    assert schema.normalize_parameters("object.create", data) == data


def test_create_nested_shorthands_are_copied_and_normalized():
    data = {
        "definition": {
            "objectType": "Справочник",
            "name": "Тест",
            "attributes": {"Ссылка": "СправочникСсылка.Контрагенты + Строка(20)"},
            "tabularSections": {
                "Строки": [{"name": "Сумма", "valueType": "Число", "length": 15, "precision": 2, "nonnegative": True}]
            },
        }
    }
    original = deepcopy(data)
    result = schema.normalize_parameters("object.create", data)["definition"]
    assert data == original
    assert result["type"] == "Catalog"
    assert result["attributes"][0]["type"] == "CatalogRef.Контрагенты + String(20)"
    assert result["tabularSections"][0]["attributes"][0]["type"] == "Number(15,2,nonneg)"


def test_http_templates_are_not_excluded_metadata_templates():
    result = schema.normalize_parameters(
        "object.create",
        {
            "definition": {
                "type": "HTTPService",
                "name": "HTTP",
                "urlTemplates": {
                    "Простой": "/path",
                    "Полный": {"template": "/path/{id}", "methods": {"Получить": "GET"}},
                },
            }
        },
    )
    assert result["definition"]["urlTemplates"]["Простой"] == {"template": "/path"}
    with pytest.raises(ValueError):
        schema.normalize_parameters(
            "object.create",
            {"definition": {"type": "HTTPService", "name": "HTTP", "urlTemplates": {"Путь": {"templates": []}}}},
        )


def test_webservice_nested_parameter_schema():
    data = {
        "definition": {
            "type": "WebService",
            "name": "API",
            "operations": {
                "Простой": "xs:string",
                "Полный": {
                    "returnType": "xs:integer",
                    "transactioned": True,
                    "parameters": {"Код": "xs:string", "Флаг": {"type": "xs:boolean", "nillable": False}},
                },
            },
        }
    }
    result = schema.normalize_parameters("object.create", data)
    assert result["definition"]["operations"]["Полный"]["parameters"]["Код"] == {"type": "xs:string"}
    data["definition"]["operations"]["Полный"]["parameters"]["Флаг"]["typo"] = True
    with pytest.raises(ValueError):
        schema.normalize_parameters("object.create", data)


@pytest.mark.parametrize(
    "definition",
    [
        {"type": "Catalog", "name": "Тест", "unknown": 1},
        {"type": "Catalog", "name": "Тест", "urlTemplates": {}},
        {"type": "Catalog", "name": "Тест", "attributes": [{"name": "Поле", "typo": 1}]},
        {"type": "Catalog", "name": "Тест", "tabularSections": [{"name": "ТЧ", "typo": 1}]},
        {"type": "Catalog", "name": "Тест", "templates": []},
    ],
)
def test_create_rejects_unknown_nested_keys(definition):
    with pytest.raises(ValueError):
        schema.normalize_parameters("object.create", {"definition": definition})


def test_edit_properties_follow_snapshot_not_static_whitelist():
    definition = {
        "modify": {"properties": {"NewPlatformProperty": True}, "attributes": {"Поле": {"PlatformQualifier": "Value"}}}
    }
    context = {"": {"NewPlatformProperty"}, "attributes.Поле": {"PlatformQualifier"}}
    data = {"definition": definition}
    assert schema.normalize_parameters("object.edit", data, properties=context) == data
    with pytest.raises(ValueError):
        schema.normalize_parameters("object.edit", data)
    with pytest.raises(ValueError):
        schema.normalize_parameters("object.edit", data, properties={"": {"OldProperty"}})


@pytest.mark.parametrize("operation", schema.EDIT_OPERATIONS)
def test_all_38_inline_operations_have_normalization(operation):
    action, child = operation.split("-", 1)
    if child in ("owner", "owners", "registerRecord", "registerRecords", "basedOn", "inputByString"):
        value = "Catalog.Тест"
    elif child == "property":
        value = "CodeLength=10"
    elif child == "ts-attribute":
        value = "Строки.Поле: type=String(20)" if action == "modify" else "Строки.Поле"
    elif action == "modify":
        value = "Поле: synonym=Новое имя"
    else:
        value = "Поле"
    result = schema.normalize_parameters(
        "object.edit",
        {"operation": operation, "value": value},
        properties={"": {"CodeLength"}},
        object_name="Catalog.Тест",
    )
    assert set(result) == {"definition"}
    assert result["definition"]


def test_inline_ts_attributes_preserve_number_commas_flags_and_placement():
    result = schema.normalize_parameters(
        "object.edit", {"operation": "add-ts", "value": "Строки: Сумма: Число(15,2) | req,index, Флаг: Булево"}
    )
    attrs = result["definition"]["add"]["tabularSections"][0]["attributes"]
    assert attrs == [
        {"name": "Сумма", "type": "Number(15,2)", "flags": ["req", "index"]},
        {"name": "Флаг", "type": "Boolean"},
    ]
    result = schema.normalize_parameters(
        "object.edit", {"operation": "add-attribute", "value": "Флаг: Булево >> after Код"}
    )
    assert result["definition"]["add"]["attributes"][0]["after"] == "Код"


def test_edit_aliases_and_nested_section_properties():
    result = schema.normalize_parameters(
        "object.edit",
        {"definition": {"изменить": {"тч": {"Строки": {"modify": {"Поле": {"CustomProperty": False}}}}}}},
        properties={"tabularSections.Строки.attributes.Поле": {"CustomProperty"}},
    )
    assert result["definition"]["modify"]["tabularSections"]["Строки"]["modify"]["Поле"] == {"CustomProperty": False}


@pytest.mark.parametrize(
    "data",
    [
        {"operation": "add-template", "value": "Макет"},
        {"definition": {"add": {"макеты": ["Макет"]}}},
        {"definition": {"add": {"attributes": [{"name": "Поле", "Force": True}]}}},
        {"operation": "modify-attribute", "value": "Поле: typo"},
        {"operation": "modify-ts-attribute", "value": "ПолеБезТЧ"},
        {"definition": {"add": {}, "добавить": {}}},
        {"definition": {}, "operation": "add-attribute", "value": "Поле"},
    ],
)
def test_edit_rejects_ignored_inputs(data):
    with pytest.raises(ValueError):
        schema.normalize_parameters("object.edit", data)


def test_exported_canonical_schemas_are_valid():
    for item in schema.PARAMETER_SCHEMAS.values():
        Draft202012Validator.check_schema(item)


def test_enum_aliases_normalize_and_invalid_value_is_rejected():
    result = schema.normalize_parameters(
        "object.create",
        {
            "definition": {
                "type": "РегистрСведений",
                "name": "Регистр",
                "periodicity": "Месяц",
                "writeMode": "RecordSubordinate",
            }
        },
    )
    assert result["definition"]["periodicity"] == "Month"
    assert result["definition"]["writeMode"] == "RecorderSubordinate"
    result = schema.normalize_parameters(
        "object.edit",
        {"definition": {"modify": {"attributes": {"Поле": {"Indexing": "Индексировать"}}}}},
        properties={"attributes.Поле": {"Indexing"}},
    )
    assert result["definition"]["modify"]["attributes"]["Поле"]["Indexing"] == "Index"
    with pytest.raises(ValueError):
        schema.normalize_parameters(
            "object.create", {"definition": {"type": "Catalog", "name": "Имя", "codeType": "Wrong"}}
        )


def test_invalid_input_error_does_not_echo_data():
    with pytest.raises(ValueError) as caught:
        schema.normalize_parameters(
            "object.create",
            {"definition": {"type": "Catalog", "name": "Private customer value", "secret": "not-for-errors"}},
        )
    assert str(caught.value) == "Invalid object operation parameters"
    assert caught.value.__suppress_context__
