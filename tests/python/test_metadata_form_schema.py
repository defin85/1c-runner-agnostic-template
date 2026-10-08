"""Request validation only: no claims about XML or BSL platform semantics."""

import tests.python.metadata_test_support  # noqa: F401, I001 — runs first: skips the module without pytest, lxml, jsonschema
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator

from scripts.python.metadata_form_schema import (
    FORM_PROPERTIES_COMPLETE,
    PARAMETER_SCHEMAS,
    normalize_parameters,
)


def check(op, definition):
    return normalize_parameters(op, {"definition": definition})["definition"]


def test_compile_keeps_rich_types_nested_controls_and_named_maps():
    definition = {
        "title": "Загрузка",
        "properties": {"autoTitle": False, "width": 80},
        "events": {"OnCreateAtServer": "ПриСозданииНаСервере"},
        "excludedCommands": ["Reread"],
        "elements": [
            {
                "group": "horizontal",
                "name": "Группа",
                "children": [
                    {
                        "input": "Ссылка",
                        "path": "Объект.Ссылка",
                        "listChoiceMode": True,
                        "choices": [{"type": "boolean", "value": False, "title": "Нет"}],
                        "on": ["OnChange"],
                        "handlers": {"OnChange": "СсылкаПриИзменении"},
                    },
                    {
                        "table": "Таблица",
                        "columns": [{"input": "Колонка"}],
                        "commandBarButtons": [{"button": "Кнопка", "picture": "StdPicture.Execute"}],
                    },
                    {"radio": "Выбор", "choices": [{"value": "a", "title": "А"}]},
                    {"progress": "Ход", "path": "Ход"},
                    {"spreadsheet": "Документ", "path": "Документ"},
                ],
            }
        ],
        "attributes": [
            {"name": "Ссылка", "type": "CatalogRef.Номенклатура | string(20)"},
            {"name": "Таблица", "type": "ValueTable", "columns": [{"name": "Сумма", "type": "decimal(15,2,nonneg)"}]},
        ],
        "parameters": [{"name": "Период", "type": "StandardPeriod", "key": True}],
        "commands": [{"name": "Команда", "action": "КомандаОбработка", "shortcut": "Ctrl+Enter"}],
    }
    before = deepcopy(definition)
    result = check("form.compile", definition)
    assert result == definition == before
    result["attributes"][0]["name"] = "Другое"
    assert definition == before


def test_edit_keeps_actions_call_types_and_event_objects():
    definition = {
        "into": "Группа",
        "after": "ПрежнееПоле",
        "elements": [
            {
                "input": "Поле",
                "on": [{"event": "OnChange", "handler": "ПослеИзменения", "callType": "After"}, "StartChoice"],
                "handlers": {"StartChoice": "НачалоВыбора"},
            }
        ],
        "attributes": [{"name": "Ссылка", "type": "DocumentRef.Заказ | CatalogRef.Заказы"}],
        "commands": [
            {"name": "Первая", "action": "Действие", "callType": "After"},
            {
                "name": "Вторая",
                "actions": [{"handler": "До", "callType": "Before"}, {"handler": "После", "callType": "After"}],
            },
        ],
        "formEvents": [{"name": "OnOpen", "handler": "ПриОткрытии", "callType": "After"}],
        "elementEvents": [{"element": "ПрежнееПоле", "name": "OnChange", "handler": "Изменение"}],
    }
    assert check("form.edit", definition) == definition


@pytest.mark.parametrize(
    ("op", "definition"),
    [
        ("form.edit", {"properties": {"autoTitle": False}}),
        ("form.edit", {"events": {"OnOpen": "ПриОткрытии"}}),
        ("form.edit", {"parameters": [{"name": "Параметр"}]}),
        # radio/spreadsheet joined form.edit with E6; progress stays compile-only.
        ("form.edit", {"elements": [{"progress": "Прогресс"}]}),
        ("form.edit", {"after": "А", "before": "Б", "elements": [{"label": "Надпись"}]}),
        ("form.edit", {"elements": [{"input": "Поле", "choices": []}]}),
        ("form.edit", {"elements": [{"table": "Таблица", "commandBarButtons": []}]}),
        ("form.compile", {"commands": [{"name": "Команда", "actions": [{"handler": "До"}]}]}),
        ("form.compile", {"commands": [{"name": "Команда", "callType": "After"}]}),
        ("form.compile", {"elements": [{"input": "Поле", "on": [{"event": "OnChange"}]}]}),
        ("form.compile", {"formEvents": []}),
        ("form.compile", {"into": "Группа"}),
    ],
)
def test_compile_and_edit_are_not_silently_interchangeable(op, definition):
    with pytest.raises(ValueError, match="^Invalid form parameters$"):
        check(op, definition)


@pytest.mark.parametrize(
    "definition",
    [
        {"unknown": "secret"},
        {"attributes": [{"name": "Поле", "unknown": "secret"}]},
        {"attributes": [{"name": "Таблица", "columns": [{"name": "Колонка", "columns": []}]}]},
        {"elements": [{"group": "vertical", "children": [{"input": "Поле", "unknown": "secret"}]}]},
        {"elements": [{"table": "Таблица", "columns": [{"input": "Поле", "children": []}]}]},
        {"elements": [{"group": "Группа", "on": ["OnChange"]}]},
        {"elements": [{"cmdBar": "Панель", "title": "Ignored"}]},
        {"elements": [{"input": "Поле", "handlers": {"OnChange": "НеИспользуется"}}]},
        {"elements": [{"button": "Кнопка", "command": "Первая", "stdCommand": "Close"}]},
        {"elements": [{"input": "Первое", "check": "Второе"}]},
        {"elements": [{"label": "Надпись", "width": float("nan")}]},
        {"events": {"OnOpen": {"handler": "НеСтрока"}}},
        {"events": {"OnOpen": "handler<secret>"}},
        {"parameters": [{"name": "Параметр", "type": {"name": "string"}}]},
        {"commands": [{"name": "Команда", "action": ["НеСтрока"]}]},
        {"title": "Один", "properties": {"title": "Другой"}},
    ],
)
def test_rejects_unknown_ignored_or_malformed_nested_values(definition):
    with pytest.raises(ValueError, match="^Invalid form parameters$"):
        check("form.compile", definition)


@pytest.mark.parametrize(
    "definition",
    [
        {"into": "Группа", "attributes": [{"name": "Поле"}]},
        {"commands": [{"name": "Команда", "actions": [{"handler": "До", "ignored": 1}]}]},
        {"commands": [{"name": "Команда", "action": "Один", "actions": [{"handler": "Два"}]}]},
        {"commands": [{"name": "Команда", "callType": "After"}]},
        {"elementEvents": [{"element": "Поле", "name": "OnChange", "handler": "Изменение", "extra": 1}]},
        {"formEvents": [{"name": "OnOpen", "handler": "Открытие", "callType": "Invalid"}]},
        {
            "elements": [
                {
                    "input": "Поле",
                    "on": [{"event": "OnChange", "handler": "Первый"}],
                    "handlers": {"OnChange": "Игнорируется"},
                }
            ]
        },
    ],
)
def test_edit_rejects_ignored_relationships_and_nested_keys(definition):
    with pytest.raises(ValueError, match="^Invalid form parameters$"):
        check("form.edit", definition)


def test_schemas_are_closed_and_can_be_embedded_in_request_schema():
    for op, schema in PARAMETER_SCHEMAS.items():
        Draft202012Validator.check_schema(schema)
        embedded = Draft202012Validator({"type": "object", "properties": {"parameters": schema}})
        valid = {"definition": {"elements": [{"group": "vertical", "children": [{"input": "Поле"}]}]}}
        assert embedded.is_valid({"parameters": valid})
        assert normalize_parameters(op, valid) == valid
        assert not embedded.is_valid({"parameters": {**valid, "ignored": "secret"}})


@pytest.mark.parametrize("op", ["form.compile", "form.edit"])
def test_control_specific_properties_are_not_mistaken_for_control_discriminators(op):
    definition = {
        "elements": [
            {"page": "Страница", "group": "horizontal"},
            {"popup": "Меню", "picture": "StdPicture.Open"},
            {"picture": "CommonPicture.Картинка", "name": "Картинка"},
        ]
    }
    assert check(op, definition) == definition


def test_scalar_property_inventory_is_complete_but_does_not_admit_arbitrary_xml():
    assert FORM_PROPERTIES_COMPLETE is True
    with pytest.raises(ValueError, match="^Invalid form parameters$"):
        check("form.compile", {"properties": {"UninventoriedProperty": "value"}})


def test_form_properties_beyond_legacy_map_and_both_name_spellings():
    properties = {
        "saveWindowSettings": True,
        "SettingsStorage": "SettingsStorage.Хранилище",
        "childrenAlign": "TitlesLeftDataAuto",
        "HorizontalSpacing": "OneAndHalf",
        "verticalSpacing": "Half",
        "HorizontalAlign": "Center",
        "verticalAlign": "Top",
        "childItemsWidth": "LeftWide",
        "Enabled": False,
        "readOnly": "false",
        "scale": "100.5",
        "ConversationsRepresentation": "DontShow",
        "showTitle": True,
        "ShowCloseButton": "1",
        "CollapseItemsByImportanceVariant": "Use",
        "groupList": "Список",
        "variantAppearance": "Настройки",
        "CustomSettingsFolder": "",
        "reportResultViewMode": "Compact",
        "ViewModeApplicationOnSetReportResult": "Apply",
        "autoTime": "CurrentOrFirst",
        "AutoShowState": "ShowOnComposition",
        "saveDataInSettings": "UseList",
        "AutoSaveDataInSettings": "Use",
        "verticalScroll": "useIfNecessary",
        "width": 123.5,
        "Height": "+50.0",
    }
    assert check("form.compile", {"properties": properties}) == {"properties": properties}
    for name, value in properties.items():
        other = name[0].upper() + name[1:] if name[0].islower() else name[0].lower() + name[1:]
        assert check("form.compile", {"properties": {other: value}}) == {"properties": {other: value}}


@pytest.mark.parametrize(
    "properties",
    [
        {"autoTitle": True, "AutoTitle": True},
        {"width": 100, "Width": 100},
        {"autoTime": True},
        {"AutoShowState": False},
        {"saveDataInSettings": True},
        {"AutoSaveDataInSettings": "Auto"},
        {"verticalScroll": "Auto"},
        {"group": "arbitrary"},
        {"showTitle": "yes"},
        {"Scale": "1e2"},
        {"width": float("inf")},
        {"Title": "Not a multilingual structure"},
        {"SettingsStorage": "</SettingsStorage><Enabled>false</Enabled>"},
        {"ReportResult": "value&entity;"},
        {"DetailsData": {"path": "Объект"}},
        {"BaseForm": "xml"},
        {"Attributes": []},
        {"MobileDeviceCommandBarContent": {}},
        {"CommandSet": "ignored"},
        {"Events": {}},
    ],
)
def test_property_types_collisions_and_structured_xml_escape_hatches_are_rejected(properties):
    with pytest.raises(ValueError, match="^Invalid form parameters$"):
        check("form.compile", {"properties": properties})


def test_decimal_properties_normalize_exponent_without_losing_value():
    definition = {"properties": {"Width": 1e-7, "scale": 1e20}}
    assert check("form.compile", definition) == {"properties": {"Width": "0.0000001", "scale": "100000000000000000000"}}
    assert definition == {"properties": {"Width": 1e-7, "scale": 1e20}}
