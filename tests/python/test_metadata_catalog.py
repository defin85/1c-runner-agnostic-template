"""The migration inventory is a contract, not a claim of runtime qualification."""

import tests.python.metadata_test_support  # noqa: F401, I001 — runs first: skips the module without pytest, lxml, jsonschema
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from scripts.python import imported_skills
from scripts.python import metadata_ops as catalog

VENDOR = Path(__file__).parents[2] / "automation/vendor/cc-1c-skills/skills"


# Recorded by reading meta-compile.valid_types, meta-edit.valid_operations and
# meta-remove.TYPE_PLURAL_MAP before retirement; independent of the new catalog.
RECORDED_CREATE_TYPES = {
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
}
# New in this CLI: the legacy generator never created these kinds.
CONNECTED_CREATE_TYPES = RECORDED_CREATE_TYPES | {"CommonCommand", "Subsystem"}
RECORDED_EDIT_OPERATIONS = {
    "add-attribute",
    "add-ts",
    "add-dimension",
    "add-resource",
    "add-enumValue",
    "add-column",
    "add-form",
    "add-template",
    "add-command",
    "add-owner",
    "add-registerRecord",
    "add-basedOn",
    "add-inputByString",
    "remove-attribute",
    "remove-ts",
    "remove-dimension",
    "remove-resource",
    "remove-enumValue",
    "remove-column",
    "remove-form",
    "remove-template",
    "remove-command",
    "remove-owner",
    "remove-registerRecord",
    "remove-basedOn",
    "remove-inputByString",
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
}
# Former command -> new route, recorded from the retired catalog (see traceability).
RECORDED_LEGACY_ROUTES = {
    "meta-info": ("inspect",),
    "meta-compile": ("object.create",),
    "meta-edit": ("object.edit",),
    "meta-remove": ("object.remove",),
    "meta-validate": ("verify",),
    "form-info": ("inspect",),
    "form-add": ("form.create",),
    "form-compile": ("form.compile",),
    "form-edit": ("form.edit",),
    "form-remove": ("form.remove",),
    "form-validate": ("verify",),
    "cfe-borrow": ("object.borrow", "form.borrow", "tabular-section.borrow"),
    "managed-form": ("inspect", "form.add-input", "apply"),
}
RECORDED_REMOVE_TYPES = RECORDED_CREATE_TYPES | {
    "Role",
    "Subsystem",
    "CommonForm",
    "CommonTemplate",
    "CommonPicture",
    "CommonAttribute",
    "SessionParameter",
    "FunctionalOption",
    "FunctionalOptionsParameter",
    "Sequence",
    "FilterCriterion",
    "SettingsStorage",
    "XDTOPackage",
    "WSReference",
    "StyleItem",
    "Language",
}


def test_catalog_matches_recorded_inventory():
    assert set(catalog.OBJECT_TYPES) == CONNECTED_CREATE_TYPES
    assert len(catalog.OBJECT_TYPES) == 25
    assert set(catalog.EDIT_OPERATIONS) == (RECORDED_EDIT_OPERATIONS - {"add-template", "remove-template"})
    assert len(catalog.EDIT_OPERATIONS) == 38
    assert set(catalog.metadata_object_ops.REMOVE_DIRECTORIES) == (RECORDED_REMOVE_TYPES | {"CommonCommand"}) - {
        "CommonTemplate"
    }
    assert set(catalog.OBJECT_TYPES) == set(catalog.metadata_object_schema.OBJECT_TYPES)
    assert set(catalog.EDIT_OPERATIONS) == set(catalog.metadata_object_schema.EDIT_OPERATIONS)


def test_complete_routes_and_explicit_exclusions():
    assert len(catalog.OPERATIONS) == len(set(catalog.OPERATIONS))
    # Every former command maps onto a connected operation of the new catalog.
    for route in RECORDED_LEGACY_ROUTES.values():
        assert set(route) <= set(catalog.OPERATIONS) | {"inspect", "verify", "apply"}
    assert (
        set(catalog.OPERATIONS)
        == {
            "object.create",
            "object.edit",
            "object.remove",
            "object.borrow",
            "object.rename",
            "object.copy-description",
            "object.extend-type",
            "object.register-borrowed",
            "member.extend-type",
            "form.create",
            "form.compile",
            "form.edit",
            "form.remove",
            "form.borrow",
            "form.add-input",
            "tabular-section.borrow",
            "predefined.create",
            "predefined.update",
            "predefined.normalize-dimension-refs",
            "form.set-properties",
            "form.move-element",
            "form.remove-element",
            "form.rename-element",
            "form.set-attribute",
            "form.set-command",
            "form.remove-event",
        }
        | TEMPLATE_OPERATIONS
        | ACCOUNTING_EXTENSION_OPERATIONS
    )
    assert set(catalog.EXCLUSIONS) == {"templates", "CommonTemplate", "Force", "BaseForm"}
    assert all(name not in RECORDED_LEGACY_ROUTES for name in catalog.PRESERVED_COMMANDS)
    assert "HTTPService" in catalog.OBJECT_TYPES
    # Import sync owns the no-return policy for every former skill (managed-form was a runner command).
    assert imported_skills.RETIRED_METADATA_SKILLS == set(RECORDED_LEGACY_ROUTES) - {"managed-form"}
    project = VENDOR.parents[3]
    imported = json.loads((VENDOR.parent / "imported-skills.json").read_text(encoding="utf-8-sig"))
    helpers = {entry["name"]: entry["helper_path"] for entry in imported["skills"]}
    assert not set(RECORDED_LEGACY_ROUTES) & helpers.keys()
    for command in ("template-add", "template-remove", "mxl-info", "mxl-compile", "mxl-decompile", "mxl-validate"):
        assert (VENDOR.parent / helpers[command]).is_file()
    # Skill directories are produced by import sync only in the template source repo. In a generated
    # project they follow the applied overlay release; their removal on template-update is covered by
    # tests/smoke/copier-update-ready.sh, which starts from a release that still ships a retired skill.
    source_repo = (project / "automation/context/template-source-project-map.md").is_file()
    for name in RECORDED_LEGACY_ROUTES:
        assert not (VENDOR / name).exists()
        if source_repo:
            assert not (project / ".agents/skills" / name).exists()
            assert not (project / ".claude/skills" / name).exists()


# Operations for catalogs, charts of accounts and exchange plans added after the initial catalog.
ACCOUNTING_EXTENSION_OPERATIONS = {
    "catalog.set-description-fill-checking",
    "chart.add-predefined",
    "chart.remove-predefined",
    "chart.extend-characteristic-type",
    "exchange-plan.edit-content",
}

TEMPLATE_OPERATIONS = {
    "template.set-area",
    "template.set-parameter",
    "template.set-format",
    "template.insert-rows",
    "template.delete-rows",
    "template.insert-columns",
    "template.delete-columns",
    "template.merge-cells",
    "template.set-size",
    "template.set-print-settings",
    "template.set-header-footer",
    "template.import-xlsx",
}


def test_catalog_does_not_claim_unimplemented_operations_ready():
    report = catalog.capabilities()
    assert report["layouts"] == ["CF", "CFE", "EPF", "ERF"]
    assert report["xml"]["descriptionConversion"] == {"Catalog": ["2.20", "2.17"]}
    assert report["checks"] == {"platform": "not-run", "runtime": "not-run"}
    assert set(report["operations"]) == set(catalog.OPERATIONS)
    assert {name for name, item in report["operations"].items() if item["available"]} == {
        "object.borrow",
        "tabular-section.borrow",
        "form.borrow",
        "object.edit",
        "form.add-input",
        "object.copy-description",
        "object.extend-type",
        "object.register-borrowed",
        "member.extend-type",
        "form.create",
        "form.compile",
        "form.edit",
        "form.remove",
        "object.create",
        "object.remove",
        "object.rename",
        "predefined.create",
        "predefined.update",
        "predefined.normalize-dimension-refs",
        "form.set-properties",
        "form.move-element",
        "form.remove-element",
        "form.rename-element",
        "form.set-attribute",
        "form.set-command",
        "form.remove-event",
    } | TEMPLATE_OPERATIONS | ACCOUNTING_EXTENSION_OPERATIONS
    assert report["connectedRenameObjectTypes"] == [
        "Catalog",
        "CommonModule",
        "Enum",
        "DataProcessor",
        "EventSubscription",
        "ExchangePlan",
        "InformationRegister",
        "ScheduledJob",
        "ExternalDataProcessor",
        "ExternalReport",
    ]
    assert report["connectedCreateObjectTypes"] == [
        "Catalog",
        "Document",
        "Enum",
        "Constant",
        "DefinedType",
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
    ]
    assert report["connectedEditOperations"] == [
        "add-attribute",
        "add-dimension",
        "add-resource",
        "add-enumValue",
        "add-column",
        "add-ts",
        "add-ts-attribute",
        "modify-property",
        "modify-attribute",
        "modify-dimension",
        "modify-resource",
        "modify-enumValue",
        "modify-column",
        "modify-ts",
        "modify-ts-attribute",
        "add-owner",
        "remove-owner",
        "set-owners",
        "add-registerRecord",
        "remove-registerRecord",
        "set-registerRecords",
        "add-basedOn",
        "remove-basedOn",
        "set-basedOn",
        "add-inputByString",
        "remove-inputByString",
        "set-inputByString",
        "remove-attribute",
        "remove-ts",
        "remove-dimension",
        "remove-resource",
        "remove-enumValue",
        "remove-column",
        "remove-ts-attribute",
        "add-form",
        "remove-form",
        "add-command",
        "remove-command",
    ]
    assert report["connectedEditObjectTypes"] == [
        "Catalog",
        "Document",
        "ChartOfAccounts",
        "ChartOfCharacteristicTypes",
        "ChartOfCalculationTypes",
        "BusinessProcess",
        "Task",
        "ExchangePlan",
        "Report",
        "DataProcessor",
        "ExternalReport",
        "ExternalDataProcessor",
        "InformationRegister",
        "AccumulationRegister",
        "AccountingRegister",
        "CalculationRegister",
        "Enum",
        "DocumentJournal",
        "Constant",
        "CommonModule",
        "ScheduledJob",
        "EventSubscription",
        "HTTPService",
        "WebService",
        "DefinedType",
        "CommonCommand",
        "Subsystem",
    ]
    # Discovery exposes schemas and availability, not change history.
    assert all(set(item) == {"available", "parameterSchema"} for item in report["operations"].values())
    assert all(item["parameterSchema"] for item in report["operations"].values())
    assert not {"legacyRoutes", "importMigration"} & report.keys()
    serialized = json.dumps(report, ensure_ascii=False)
    for history in ("implementationTask", "tests/", "test_", "openspec", "excludeAfterMigration"):
        assert history not in serialized
    assert report["preservedCommands"] == list(catalog.PRESERVED_COMMANDS)
    assert report["exclusions"] == catalog.EXCLUSIONS
    report["layouts"].clear()
    assert catalog.capabilities()["layouts"] == ["CF", "CFE", "EPF", "ERF"]


def test_request_envelope_is_strict_but_not_a_parameter_validator():
    Draft202012Validator.check_schema(catalog.REQUEST_ENVELOPE_SCHEMA)
    validator = Draft202012Validator(catalog.REQUEST_ENVELOPE_SCHEMA)
    operation = {"op": "object.borrow", "target": "Document.Заказ", "parameters": {}}
    request = {"schemaVersion": 1, "operations": [operation]}
    validator.validate(request)
    for invalid in (
        {**request, "schemaVersion": True},
        {**request, "schemaVersion": 2},
        {**request, "extra": True},
        {**request, "operations": []},
        {**request, "operations": [{**operation, "extra": True}]},
        {**request, "operations": [{**operation, "op": "template.add"}]},
        {**request, "operations": [{**operation, "target": ""}]},
        {**request, "operations": [{**operation, "parameters": []}]},
    ):
        with pytest.raises(ValidationError):
            validator.validate(invalid)


def test_result_schema_rejects_false_platform_claims_and_inconsistent_errors():
    Draft202012Validator.check_schema(catalog.RESULT_SCHEMA)
    validator = Draft202012Validator(catalog.RESULT_SCHEMA)
    result = {
        "schemaVersion": 1,
        "status": "capabilities",
        "checks": {"platform": "not-run", "runtime": "not-run"},
        "changes": None,
        "error": None,
    }
    validator.validate(result)
    for code in (2, 3, 4, 5):
        validator.validate(
            {**result, "status": "failed" if code == 5 else "rejected", "error": {"code": code, "message": "Rejected"}}
        )
    for invalid in (
        {**result, "extra": True},
        {**result, "checks": {"platform": "passed", "runtime": "not-run"}},
        {**result, "status": "rejected"},
        {**result, "error": {"code": 2, "message": "Rejected"}},
        {**result, "status": "failed", "error": {"code": 3, "message": "Conflict"}},
        {**result, "status": "rejected", "error": {"code": True, "message": "Conflict"}},
    ):
        with pytest.raises(ValidationError):
            validator.validate(invalid)


@pytest.mark.parametrize(
    "op,parameters",
    [
        ("object.borrow", {"baseRoot": "C:/base"}),
        ("form.borrow", {"baseRoot": "C:/base", "borrowMainAttribute": "Form"}),
        ("form.borrow", {"baseRoot": "C:/base", "borrowMainAttribute": "All"}),
        ("tabular-section.borrow", {"baseRoot": "C:/base"}),
        ("object.remove", {"keepFiles": True}),
        ("object.remove", {}),
        (
            "object.remove",
            {
                "reviewedDependencies": [
                    {"path": "CommonModules/Модуль/Ext/Module.bsl", "sha256": "0" * 64, "reason": "reviewed"}
                ]
            },
        ),
        ("form.remove", {}),
        ("form.create", {"name": "Форма", "purpose": "Record", "setDefault": True}),
        (
            "form.add-input",
            {
                "name": "Поле",
                "attribute": "Объект.Реквизит",
                "title": "Реквизит",
                "parent": "$root",
                "after": "СтароеПоле",
            },
        ),
        ("form.add-input", {"name": "Поле", "attribute": "Реквизит", "title": "Реквизит", "parent": "Группа"}),
    ],
)
def test_parameter_normalization_preserves_explicit_values(op, parameters):
    request = {"schemaVersion": 1, "operations": [{"op": op, "target": "Document.Заказ", "parameters": parameters}]}
    original = json.loads(json.dumps(request))
    normalized = catalog.normalize_request(request)
    assert request == original
    for key, value in parameters.items():
        assert normalized["operations"][0]["parameters"][key] == value
    assert catalog.normalize_request(normalized) == normalized
    invalid = {**request, "operations": [{**request["operations"][0], "parameters": {**parameters, "unknown": True}}]}
    with pytest.raises(ValueError, match="Invalid operation parameters"):
        catalog.normalize_request(invalid)


@pytest.mark.parametrize(
    "op,parameters",
    [
        ("object.remove", {"Force": True}),
        ("object.remove", {"force": True, "keepFiles": True}),
        ("object.remove", {"keepFiles": 1}),
        ("object.borrow", {}),
        ("object.borrow", {"baseRoot": "base", "borrowMainAttribute": "All"}),
        ("form.borrow", {"baseRoot": "base", "borrowMainAttribute": "Everything"}),
        ("form.borrow", {"baseRoot": "base\x00"}),
        ("form.create", {"name": "bad\n"}),
        ("form.create", {"name": "Форма", "purpose": "Bogus"}),
        ("form.add-input", {"name": "Поле", "attribute": "Объект.ТЧ.Поле", "title": "x", "parent": "$root"}),
        ("form.add-input", {"name": "Поле", "attribute": "Поле", "title": " ", "parent": "$root"}),
        ("form.add-input", {"name": "Поле", "attribute": "Поле", "title": "x\x01", "parent": "$root"}),
    ],
)
def test_invalid_parameters_are_rejected_without_echoing_values(op, parameters):
    with pytest.raises(ValueError, match="^Invalid operation parameters$"):
        catalog.normalize_request(
            {"schemaVersion": 1, "operations": [{"op": op, "target": "Document.Заказ", "parameters": parameters}]}
        )


def test_missing_required_definition_fails_closed():
    assert set(catalog.PARAMETER_SCHEMAS) == set(catalog.OPERATIONS)
    with pytest.raises(ValueError, match="Invalid object operation parameters"):
        catalog.normalize_request(
            {"schemaVersion": 1, "operations": [{"op": "object.edit", "target": "Document.Заказ", "parameters": {}}]}
        )


def test_rich_requests_normalize_through_common_contract_without_mutation():
    request = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.create",
                "target": "$root",
                "parameters": {
                    "definition": [
                        {"objectType": "Справочник", "name": "Первый", "attributes": ["Флаг: Булево"]},
                        {"type": "Document", "name": "Второй"},
                    ]
                },
            },
            {
                "op": "object.edit",
                "target": "Document.Второй",
                "parameters": {"operation": "add-attribute", "value": "Сумма: Number(15,2)"},
            },
            {
                "op": "form.compile",
                "target": "Document.Второй.Form.Форма",
                "parameters": {
                    "definition": {"properties": {"Width": 1e-7}, "elements": [{"page": "Первая", "group": "Vertical"}]}
                },
            },
            {
                "op": "form.edit",
                "target": "Document.Второй.Form.Форма",
                "parameters": {"definition": {"commands": [{"name": "Команда", "action": "Обработчик"}]}},
            },
        ],
    }
    original = json.loads(json.dumps(request))
    result = catalog.normalize_request(request)
    assert request == original
    assert [step["target"] for step in result["operations"][:3]] == [
        "Catalog.Первый",
        "Document.Второй",
        "Document.Второй",
    ]
    assert result["operations"][0]["parameters"]["definition"]["attributes"] == [{"name": "Флаг", "type": "Boolean"}]
    assert result["operations"][2]["parameters"]["definition"]["add"]["attributes"] == [
        {"name": "Сумма", "type": "Number(15,2)"}
    ]
    assert result["operations"][3]["parameters"]["definition"]["properties"]["Width"] == "0.0000001"
    assert catalog.normalize_request(result) == result


def test_property_context_is_required_and_specific_to_the_current_step():
    step = {
        "op": "object.edit",
        "target": "Catalog.Первый",
        "parameters": {"definition": {"modify": {"attributes": {"Флаг": {"Indexing": "Индексировать"}}}}},
    }
    with pytest.raises(ValueError):
        catalog.normalize_operation(step)
    with pytest.raises(ValueError):
        catalog.normalize_operation(step, properties={"attributes.Другой": {"Indexing"}})
    normalized = catalog.normalize_operation(step, properties={"attributes.Флаг": {"Indexing"}})
    assert normalized[0]["parameters"]["definition"]["modify"]["attributes"]["Флаг"] == {"Indexing": "Index"}
    # No context is retained for a later call or another request.
    with pytest.raises(ValueError):
        catalog.normalize_operation(step)


@pytest.mark.parametrize(
    "target,definition",
    [
        ("Catalog.Другой", {"type": "Catalog", "name": "Первый"}),
        ("Catalog.Первый", [{"type": "Catalog", "name": "Первый"}]),
        ("$root", []),
    ],
)
def test_creation_never_discards_a_conflicting_target(target, definition):
    with pytest.raises(ValueError):
        catalog.normalize_operation({"op": "object.create", "target": target, "parameters": {"definition": definition}})


@pytest.mark.parametrize(
    "op,definition",
    [
        ("object.create", {"type": "Catalog", "name": "X", "attributes": [{"name": "A", "secret": "local-secret"}]}),
        ("object.edit", {"add": {"attributes": [{"name": "A", "secret": "local-secret"}]}}),
        ("form.compile", {"elements": [{"group": "G", "children": [{"input": "A", "secret": "local-secret"}]}]}),
        ("form.edit", {"commands": [{"name": "A", "secret": "local-secret"}]}),
    ],
)
def test_rich_nested_unknown_fields_are_rejected_without_echo(op, definition):
    with pytest.raises(ValueError) as error:
        catalog.normalize_operation({"op": op, "target": "Catalog.X", "parameters": {"definition": definition}})
    assert "local-secret" not in str(error.value)


def test_normalization_uses_legacy_defaults_and_does_not_accept_a_guessed_field_type():
    request = {
        "schemaVersion": 1,
        "operations": [
            {"op": "form.create", "target": "Document.Заказ", "parameters": {"name": "Форма"}},
            {"op": "object.remove", "target": "Catalog.Старый", "parameters": {}},
        ],
    }
    result = catalog.normalize_request(request)
    assert result["operations"][0]["parameters"] == {
        "name": "Форма",
        "synonym": "Форма",
        "purpose": "Object",
        "setDefault": False,
    }
    assert result["operations"][1]["parameters"] == {"keepFiles": False}
    for scalar in ("String", "Number", "Boolean", "Date"):
        with pytest.raises(ValueError, match="Invalid operation parameters"):
            catalog.normalize_request(
                {
                    "schemaVersion": 1,
                    "operations": [
                        {
                            "op": "form.add-input",
                            "target": "CommonForms/Форма/Ext/Form.xml",
                            "parameters": {
                                "name": "Поле",
                                "attribute": "Реквизит",
                                "title": "Поле",
                                "parent": "$root",
                                "type": scalar,
                            },
                        }
                    ],
                }
            )


def test_copy_description_preserves_explicit_composition_and_reference_mapping():
    parameters = {
        "sourceRoot": "C:/источник",
        "source": "Catalog.ДлинноеИмяСправочника",
        "prefix": "Демо_",
        "include": ["Attribute.НаименованиеПолное"],
        "exclude": ["Form.ФормаЭлемента", "Template.Макет"],
        "mapping": {"Catalog.ДлинноеИмяСправочника": "Catalog.Демо_ДлинноеИмяСправочника"},
    }
    operation = {
        "op": "object.copy-description",
        "target": "Catalog.Демо_ДлинноеИмяСправочника",
        "parameters": parameters,
    }
    request = {"schemaVersion": 1, "operations": [operation]}
    assert catalog.normalize_request(request) == request
    for invalid in (
        {**parameters, "mapping": {"Catalog.X": {"to": "Catalog.Y", "unknown": True}}},
        {**parameters, "mapping": {"../X": "Catalog.Y"}},
        {**parameters, "include": ["Attribute.X", "Attribute.X"]},
        {**parameters, "include": ["Form.ФормаЭлемента"]},
        {**parameters, "exclude": ["Form..Имя"]},
        {**parameters, "autoRename": True},
    ):
        with pytest.raises(ValueError):
            catalog.normalize_request({"schemaVersion": 1, "operations": [{**operation, "parameters": invalid}]})
