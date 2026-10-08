"""Strict input contracts for the two existing, intentionally different form DSLs.

These schemas describe requests, not platform qualification or BSL correctness.
The property inventory covers scalar Form properties; structured XML children
are not generic properties and keep their dedicated DSL sections.
"""

import math
from copy import deepcopy
from decimal import Decimal

from jsonschema import Draft202012Validator

FORM_PROPERTIES_COMPLETE = True
_TEXT = {"type": "string", "not": {"pattern": r"[\x00-\x08\x0b\x0c\x0e-\x1f]"}}
_NAME = {"type": "string", "pattern": r"^[^\W\d]\w*$", "not": {"pattern": r"[\r\n]"}}
_VALUE = {"type": "string", "minLength": 1, "not": {"pattern": r'[<>&"\x00-\x1f]'}}
_BOOL = {"type": "boolean"}
_SIZE = {"type": "number", "minimum": 0}
_CALL = {"enum": ["Before", "After", "Override"]}


def _object(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


def _array(items):
    return {"type": "array", "items": items}


def _map(values):
    return {"type": "object", "propertyNames": _NAME, "additionalProperties": values}


# Interface facts, not copied schema text. Form extends FormVisualEntity, whose
# base PredefinedChildItems adds no scalar properties. Property names/types and
# imported enumeration values agree between Designer XML 2.17 and 2.20:
# https://github.com/yellow-hammer/namespace-forest/tree/1faa66885d16a83f38768f19bb45d835e0c00fec/schemas/designer
# Files: v8.1c.ru-8.3-xcf-logform.xsd, v8.1c.ru-8.2-managed-application-logform.xsd,
# v8.1c.ru-8.1-data-enterprise.xsd, v8.1c.ru-8.3-xcf-readable.xsd.
_PROPERTY_ENUMS = {
    "WindowOpeningMode": ("Independent", "LockOwnerWindow", "LockWholeInterface"),
    "EnterKeyBehavior": ("ControlNavigation", "DefaultButton"),
    "AutoSaveDataInSettings": ("DontUse", "Use"),
    "SaveDataInSettings": ("DontUse", "UseList"),
    "Group": ("Horizontal", "Vertical", "HorizontalIfPossible", "AlwaysHorizontal"),
    "ChildrenAlign": (
        "Auto",
        "None",
        "ItemsLeftTitlesLeft",
        "ItemsRightTitlesLeft",
        "ItemsLeftTitlesRight",
        "ItemsRightTitlesRight",
        "TitlesLeftDataLeft",
        "TitlesLeftDataRight",
        "TitlesRightDataLeft",
        "TitlesRightDataRight",
        "TitlesLeftDataAuto",
    ),
    "HorizontalSpacing": ("Auto", "None", "Half", "Single", "OneAndHalf", "Double"),
    "VerticalSpacing": ("Auto", "None", "Half", "Single", "OneAndHalf", "Double"),
    "HorizontalAlign": ("Left", "Center", "Right", "Auto"),
    "VerticalAlign": ("Top", "Center", "Bottom", "Auto"),
    "ChildItemsWidth": ("Auto", "Equal", "LeftWide", "LeftWidest", "LeftNarrow", "LeftNarrowest"),
    "CommandBarLocation": ("None", "Auto", "Top", "Bottom"),
    "VerticalScroll": ("auto", "use", "useIfNecessary", "useWithoutStretch"),
    "ScalingMode": ("Auto", "Normal", "Compact"),
    "ConversationsRepresentation": ("Auto", "Show", "DontShow"),
    "CollapseItemsByImportanceVariant": ("Auto", "Use", "DontUse"),
    "UseForFoldersAndItems": ("Items", "Folders", "FoldersAndItems"),
    "AutoTime": ("DontUse", "Last", "First", "CurrentOrLast", "CurrentOrFirst"),
    "UsePostingMode": ("Regular", "RealTime", "Ask", "Auto"),
    "ReportFormType": ("Main", "Settings", "Variant"),
    "AutoShowState": ("Auto", "DontShow", "Show", "ShowOnComposition"),
    "ReportResultViewMode": ("Auto", "Default", "Compact"),
    "ViewModeApplicationOnSetReportResult": ("Auto", "Apply", "DontApply"),
}
_PROPERTY_BOOL = {"oneOf": [_BOOL, {"enum": ["true", "false", "0", "1"]}]}
_PROPERTY_DECIMAL = {
    "oneOf": [
        {"type": "number"},
        {"type": "string", "pattern": r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$", "not": {"pattern": r"[\r\n]"}},
    ]
}
_PROPERTY_REF = {"type": "string", "not": {"pattern": r'[<>&"\x00-\x1f]'}}
_XML_PROPERTIES = {
    **{name: {"enum": list(values)} for name, values in _PROPERTY_ENUMS.items()},
    **dict.fromkeys(
        (
            "SaveWindowSettings",
            "AutoTitle",
            "AutoURL",
            "AutoFillCheck",
            "Customizable",
            "Enabled",
            "ReadOnly",
            "ShowTitle",
            "ShowCloseButton",
            "RepostOnWrite",
        ),
        _PROPERTY_BOOL,
    ),
    **dict.fromkeys(("Width", "Height", "Scale"), _PROPERTY_DECIMAL),
    **dict.fromkeys(
        ("SettingsStorage", "GroupList", "ReportResult", "DetailsData", "VariantAppearance", "CustomSettingsFolder"),
        _PROPERTY_REF,
    ),
}
_FORM_PROPERTIES: dict = {
    alias: schema for name, schema in _XML_PROPERTIES.items() for alias in (name, name[0].lower() + name[1:])
}
# Only this exact legacy spelling invokes multilingual Title emission.
_FORM_PROPERTIES["title"] = _TEXT


def _schema(edit):
    reference = {"$ref": "#/$defs/element"}
    children = _array(reference)
    event = _object({"event": _NAME, "handler": _NAME, "callType": _CALL}, ("event",))
    events = {"on": _array({"oneOf": [_NAME, event]} if edit else _NAME), "handlers": _map(_NAME)}
    common = {"name": _NAME, **dict.fromkeys(("visible", "hidden", "enabled", "disabled", "readOnly"), _BOOL)}
    if not edit:
        common.update(dict.fromkeys(("horizontalStretch", "verticalStretch"), _BOOL))
    dimensions = {"width": _SIZE, "height": _SIZE}
    auto_dimensions = dict.fromkeys(("autoMaxWidth", "autoMaxHeight"), _BOOL)
    field = {"path": _VALUE, "title": _TEXT}
    choices = _array(
        {
            **_object(
                {
                    "title": _TEXT,
                    "value": {"type": ["string", "number", "boolean"]},
                    "type": {"enum": ["string", "number", "boolean"]},
                },
                ("title", "value"),
            ),
            "allOf": [
                {
                    "if": {"required": ["type"], "properties": {"type": {"const": kind}}},
                    "then": {"properties": {"value": {"type": kind}}},
                }
                for kind in ("string", "number", "boolean")
            ],
        }
    )
    variants = {
        "group": {"title": _TEXT, "representation": _VALUE, "showTitle": _BOOL, "united": _BOOL, "children": children},
        "input": {
            **field,
            **events,
            **dimensions,
            **auto_dimensions,
            **dict.fromkeys(
                (
                    "multiLine",
                    "passwordMode",
                    "choiceButton",
                    "clearButton",
                    "spinButton",
                    "dropListButton",
                    "markIncomplete",
                    "skipOnInput",
                    "horizontalStretch",
                    "verticalStretch",
                ),
                _BOOL,
            ),
            "titleLocation": _VALUE,
            "inputHint": _TEXT,
        },
        "check": {**field, **events, "titleLocation": _VALUE},
        "label": {"title": _TEXT, "hyperlink": _BOOL, **events, **dimensions, **auto_dimensions},
        "labelField": {**field, **events, "hyperlink": _BOOL},
        "table": {
            **field,
            **events,
            "representation": _VALUE,
            **dict.fromkeys(("changeRowSet", "changeRowOrder", "header", "footer"), _BOOL),
            "height": _SIZE,
            "commandBarLocation": _VALUE,
            "searchStringLocation": _VALUE,
            "columns": children,
        },
        "pages": {**events, "pagesRepresentation": _VALUE, "children": children},
        "page": {"title": _TEXT, "children": children, "group": _VALUE},
        "button": {
            **events,
            "title": _TEXT,
            "type": _VALUE,
            "command": _NAME,
            "stdCommand": _VALUE,
            "defaultButton": _BOOL,
            "picture": _VALUE,
            "representation": _VALUE,
            "locationInCommandBar": _VALUE,
        },
        "picture": {**events, **dimensions, "title": _TEXT, "src": _VALUE, "hyperlink": _BOOL},
        "picField": {**field, **events, **dimensions},
        "calendar": {**field, **events},
        "cmdBar": {"autofill": _BOOL, "children": children},
        "popup": {"title": _TEXT, "picture": _VALUE, "representation": _VALUE, "children": children},
        "radio": {"path": _VALUE, "titleLocation": _VALUE, "choices": choices, **events},
        "spreadsheet": {"path": _VALUE},
        # Kinds added for form.edit parity with BslEdit add_element (E6).
        "textDocument": {**field, **events},
        "formattedDocument": {**field, **events},
        "chart": {**field, **events},
        "columnGroup": {"title": _TEXT, "group": _VALUE, "showTitle": _BOOL, "children": children},
        "buttonGroup": {"title": _TEXT, "representation": _VALUE, "children": children},
    }
    if not edit:
        variants["input"].update({"listChoiceMode": _BOOL, "choices": choices})
        variants["label"]["textColor"] = _VALUE
        variants["table"]["commandBarButtons"] = children
        variants["progress"] = {"path": _VALUE, "titleLocation": _VALUE}
    element_schemas = []
    for kind, properties in variants.items():
        branch = _object({**common, kind: _VALUE, **properties}, (kind,))
        # picture is also a button/popup property; group is also page orientation.
        if kind == "picture":
            branch["not"] = {"anyOf": [{"required": [key]} for key in ("button", "popup")]}
        if kind == "group":
            branch["not"] = {"required": ["page"]}
        if kind == "button":
            branch["not"] = {"required": ["command", "stdCommand"]}
        element_schemas.append(branch)
    column = _object({"name": _NAME, "title": _TEXT, "type": _VALUE}, ("name", "type") if edit else ("name",))
    attribute = _object(
        {
            "name": _NAME,
            "title": _TEXT,
            "type": _VALUE,
            "main": _BOOL,
            "savedData": _BOOL,
            "fillChecking": _VALUE,
            "columns": _array(column),
        },
        ("name",),
    )
    command = _object(
        {
            "name": _NAME,
            "title": _TEXT,
            "action": _NAME,
            "shortcut": _VALUE,
            "picture": _VALUE,
            "representation": _VALUE,
        },
        ("name",),
    )
    definition = {"elements": children, "attributes": _array(attribute), "commands": _array(command)}
    if edit:
        command["properties"].update(
            {
                "callType": _CALL,
                "actions": {**_array(_object({"handler": _NAME, "callType": _CALL}, ("handler",))), "minItems": 1},
            }
        )
        command["not"] = {"required": ["action", "actions"]}
        command["dependentRequired"] = {"callType": ["action"]}
        form_event = _object({"name": _NAME, "handler": _NAME, "callType": _CALL}, ("name", "handler"))
        element_event = _object({**form_event["properties"], "element": _NAME}, ("element", "name", "handler"))
        definition.update(
            {
                "into": _NAME,
                "after": _NAME,
                "before": _NAME,
                "formEvents": _array(form_event),
                "elementEvents": _array(element_event),
            }
        )
    else:
        definition.update(
            {
                "title": _TEXT,
                "properties": _object(_FORM_PROPERTIES),
                "events": _map(_NAME),
                "excludedCommands": _array(_VALUE),
                "parameters": _array(_object({"name": _NAME, "type": _VALUE, "key": _BOOL}, ("name",))),
            }
        )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"urn:onec-template:metadata:form.{'edit' if edit else 'compile'}:parameters:1",
        **_object({"definition": _object(definition)}, ("definition",)),
        "$defs": {"element": {"oneOf": element_schemas}},
    }


PARAMETER_SCHEMAS = {"form.compile": _schema(False), "form.edit": _schema(True)}


def _check_values(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Invalid form parameters")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Invalid form parameters")
            _check_values(item)
    elif isinstance(value, list):
        for item in value:
            _check_values(item)


def _check_elements(elements):
    for element in elements:
        events = element.get("on", [])
        event_names = [event if isinstance(event, str) else event["event"] for event in events]
        handlers = element.get("handlers", {})
        if set(handlers) - set(event_names):
            raise ValueError("Invalid form parameters")
        for event in events:
            if isinstance(event, dict) and "handler" in event and event["event"] in handlers:
                raise ValueError("Invalid form parameters")
        for key in ("children", "columns", "commandBarButtons"):
            _check_elements(element.get(key, []))


def normalize_parameters(op, parameters):
    """Validate without changing rich types or conflating compile/edit syntax."""
    try:
        _check_values(parameters)
        validator = Draft202012Validator(PARAMETER_SCHEMAS[op])
        if not validator.is_valid(parameters):
            raise ValueError("Invalid form parameters")
        definition = parameters["definition"]
        if any(key in definition for key in ("into", "after", "before")) and not definition.get("elements"):
            raise ValueError("Invalid form parameters")
        if "after" in definition and "before" in definition:
            raise ValueError("Invalid form parameters")
        if "title" in definition and "title" in definition.get("properties", {}):
            raise ValueError("Invalid form parameters")
        properties = definition.get("properties", {})
        xml_names = [name[0].upper() + name[1:] for name in properties]
        if len(xml_names) != len(set(xml_names)):
            raise ValueError("Invalid form parameters")
        _check_elements(definition.get("elements", []))
        result = deepcopy(parameters)
        # xs:decimal has no exponent notation, unlike Python's str(float).
        for name, value in result["definition"].get("properties", {}).items():
            if name[0].upper() + name[1:] in ("Width", "Height", "Scale"):
                if isinstance(value, float) and "e" in str(value).lower():
                    result["definition"]["properties"][name] = format(Decimal(str(value)), "f")
        return result
    except (KeyError, TypeError, RecursionError):
        raise ValueError("Invalid form parameters") from None


# --- Element-level editing (form.set-properties and neighbours) -------------
# Property names, their order and value kinds are interface facts of the
# Designer logform schema 2.17/2.20 (same source as _PROPERTY_ENUMS above:
# v8.1c.ru-8.3-xcf-logform.xsd and v8.1c.ru-8.2-managed-application-logform.xsd;
# UseOutput from v8.1c.ru-8.1-data-ui.xsd). Kinds: b boolean, w true/false/auto,
# d decimal, s plain text, l multilingual text, f formatted multilingual text,
# c color, F font, p picture, t a type list (form.compile type spelling),
# x a structured value this operation does not build; any other value names an enumeration in ELEMENT_ENUMS.
ELEMENT_ENUMS = {
    "FormElementTitleLocation": ("None", "Auto", "Left", "Top", "Right", "Bottom"),
    "TooltipRepresentation": (
        "Auto",
        "None",
        "Balloon",
        "Button",
        "ShowAuto",
        "ShowTop",
        "ShowLeft",
        "ShowBottom",
        "ShowRight",
    ),
    "WarningOnEditRepresentation": ("Show", "DontShow", "Auto"),
    "ItemHorizontalAlignment": ("Left", "Center", "Right", "Auto"),
    "ItemVerticalAlignment": ("Top", "Center", "Bottom", "Auto"),
    "DisplayImportance": ("Auto", "VeryHigh", "High", "Usual", "Low", "VeryLow"),
    "TableFieldEditMode": ("Directly", "Enter", "EnterOnInput"),
    "FormFixedInTable": ("None", "Left", "Right"),
    "OnMainServerUnavalableBehavior": ("Auto", "MakeDisable", "DontChangeBehavior"),
    "ChoiceButtonRepresentation": ("Auto", "ShowInDropList", "ShowInDropListAndInInputField", "ShowInInputField"),
    "InputFieldMultipleValuePictureSize": ("Auto", "Small", "Medium", "Large"),
    "InputFieldMultipleValuePictureShape": ("Auto", "Rect", "Circle", "Square"),
    "FoldersAndItems": ("Items", "Folders", "FoldersAndItems", "Auto"),
    "IncompleteItemChoiceMode": ("OnEnterPressed", "OnActivate"),
    "EditTextUpdate": ("Auto", "DontUse", "OnValueChange", "Always"),
    "HeightControlVariant": ("Auto", "UseHeightInFormRows", "UseContentHeight"),
    "AutoShowClearButtonMode": ("Auto", "Always", "FilledOnly"),
    "AutoShowOpenButtonMode": ("Auto", "Always", "FilledOnly"),
    "AutoCorrectionOnTextInput": ("Auto", "Use", "DontUse"),
    "SpellCheckingOnTextInput": ("Auto", "Use", "DontUse"),
    "AutoCapitalizationOnTextInput": ("Auto", "None", "Words", "Sentences", "AllCharacters"),
    "SpecialTextInputMode": ("Auto", "None", "DigitsAndPunctuation", "URL", "Email", "PhoneNumber", "Digits"),
    "AutofillHint": (
        "DontUse",
        "FullName",
        "GivenName",
        "FamilyName",
        "MiddleName",
        "NamePrefix",
        "NameSuffix",
        "Street",
        "City",
        "Region",
        "Country",
        "PostalCode",
        "UserName",
        "Password",
        "NewPassword",
        "OneTimeCode",
        "Email",
        "PhoneNumber",
        "CreditCardNumber",
    ),
    "OnScreenKeyboardReturnKeyText": ("Auto", "Return", "Go", "Join", "Next", "Search", "Send", "Done", "Continue"),
    "ChoiceHistoryOnInput": ("Auto", "DontUse"),
    "CheckBoxType": ("Auto", "CheckBox", "Tumbler", "Switcher"),
    "FormChildrenGroup": ("Horizontal", "Vertical", "HorizontalIfPossible", "AlwaysHorizontal"),
    "FormChildrenAlign": _PROPERTY_ENUMS["ChildrenAlign"],
    "FormItemSpacing": ("Auto", "None", "Half", "Single", "OneAndHalf", "Double"),
    "UsualGroupBehavior": ("Usual", "Collapsible", "PopUp", "Auto"),
    "UsualGroupControlRepresentation": ("TitleHyperlink", "Picture"),
    "UsualGroupRepresentation": (
        "None",
        "StrongSeparation",
        "WeakSeparation",
        "NormalSeparation",
        "GroupBox",
        "Line",
        "Margin",
    ),
    "FormChildrenWidth": ("Auto", "Equal", "LeftWide", "LeftWidest", "LeftNarrow", "LeftNarrowest"),
    "UsualGroupThroughAlign": ("Use", "DontUse", "Auto"),
    "CurrentRowUse": ("Use", "DontUse", "Auto"),
    "FormPagesRepresentation": (
        "None",
        "TabsOnTop",
        "TabsOnBottom",
        "TabsOnLeftHorizontal",
        "TabsOnRightHorizontal",
        "Swipe",
        "Auto",
    ),
    "TableRepresentation": ("List", "HierarchicalList", "Tree"),
    "FormElementCommandBarLocation": ("None", "Auto", "Top", "Bottom"),
    "TableHeightControlVariant": ("Auto", "UseHeightInFormRows", "UseHeightInTableRows", "UseContentHeight"),
    "TableRowInputMode": ("EndOfList", "EndOfWindow", "AfterCurrentRow", "BeforeCurrentRow"),
    "TableSelectionMode": ("SingleRow", "MultiRow"),
    "TableRowSelectionMode": ("Cell", "Row"),
    "TableScrollBarUse": ("DontUse", "UseAlways", "AutoUse"),
    "SearchOnInput": ("Use", "DontUse", "Auto"),
    "TableInitialListView": ("Beginning", "End", "Auto"),
    "TableInitialTreeView": ("NoExpand", "ExpandTopLevel", "ExpandAllLevels"),
    "UseOutput": ("Auto", "Enable", "Disable"),
    "FileDragMode": ("AsFile", "AsFileRef"),
    "SearchStringLocation": ("Auto", "None", "CommandBar", "Top", "Bottom", "FormCaption", "PullFromTop"),
    "ViewStatusLocation": ("Auto", "None", "Top", "Bottom"),
    "SearchControlLocation": ("Auto", "None", "CommandBar"),
    "RefreshRequestMethod": ("None", "PullFromTop", "PullFromBottom", "PullFromTopOrBottom"),
    "TableCurrentRowUse": ("Auto", "Choice", "SelectionPresentation", "SelectionPresentationAndChoice"),
    "TableBehaviorOnHorizontalCompression": ("Auto", "HideItemsByImportance", "MoveItemsByImportance"),
    "ManagedFormButtonType": ("CommandBarButton", "UsualButton", "Hyperlink", "CommandBarHyperlink"),
    "ButtonRepresentation": ("Text", "Picture", "PictureAndText", "Auto"),
    "MenuElementPlacementArea": ("mainCmdsLeft", "autoCmds", "userCmds", "mainCmdsRight"),
    "RepresentationInContextMenu": ("None", "AdditionalInContextMenu", "OnlyInContextMenu", "Auto"),
    "ButtonShape": ("Auto", "Usual", "Oval"),
    "ButtonShapeRepresentation": ("Auto", "Always", "WhenActive", "None"),
    "FormButtonPictureLocation": ("Auto", "Left", "Right"),
    "ButtonLocationInCommandBar": ("Auto", "InAdditionalSubmenu", "InCommandBar", "InCommandBarAndInAdditionalSubmenu"),
    "ButtonGroupRepresentation": ("Auto", "Usual", "Compact"),
    "ColumnsGroup": ("Horizontal", "Vertical", "InCell"),
    "PictureSize": (
        "RealSize",
        "Stretch",
        "Proportionally",
        "Tile",
        "AutoSize",
        "RealSizeIgnoreScale",
        "AutoSizeIgnoreScale",
        "ByFontSize",
    ),
    "RadioButtonType": ("Auto", "RadioButtons", "Tumbler"),
    "FormDateSelectionMode": ("Single", "Multiple", "Interval"),
    "SelectionShowMode": (
        "WhenActive",
        "Always",
        "DontShow",
        "WhenMultipleCellsSelected",
        "WhenMultipleCellsSelectedWhenActive",
    ),
    "DrawingSelectionShowMode": ("Show", "DontShow", "Auto"),
    "ViewScalingMode": ("Auto", "Normal", "Large"),
}


def _props(text):
    """Parse 'Name:kind ...' in schema order."""
    return tuple(tuple(item.split(":", 1)) for item in text.split())


_FIELD = _props(
    "DataPath:s Visible:b UserVisible:x DefaultItem:b Enabled:b ReadOnly:b SkipOnInput:w Title:l "
    "TitleTextColor:c TitleBackColor:c TitleFont:F TitleLocation:FormElementTitleLocation TitleHeight:d "
    "ToolTip:l ToolTipRepresentation:TooltipRepresentation "
    "WarningOnEditRepresentation:WarningOnEditRepresentation WarningOnEdit:l Shortcut:s CommandSet:x "
    "HorizontalAlign:ItemHorizontalAlignment VerticalAlign:ItemVerticalAlignment "
    "GroupHorizontalAlign:ItemHorizontalAlignment GroupVerticalAlign:ItemVerticalAlignment "
    "DisplayImportance:DisplayImportance EditMode:TableFieldEditMode FixingInTable:FormFixedInTable "
    "CellHyperlink:b AutoCellHeight:b ShowInHeader:b HeaderPicture:p HeaderHorizontalAlign:ItemHorizontalAlignment "
    "ShowInFooter:b FooterDataPath:s FooterText:l FooterTextColor:c FooterBackColor:c FooterFont:F "
    "FooterPicture:p FooterHorizontalAlign:ItemHorizontalAlignment "
    "OnMainServerUnavalableBehavior:OnMainServerUnavalableBehavior"
)
_DECORATION = _props(
    "Visible:b UserVisible:x Enabled:b Width:d AutoMaxWidth:b MaxWidth:d MinWidth:d Height:d "
    "AutoMaxHeight:b MaxHeight:d HorizontalStretch:w VerticalStretch:w SkipOnInput:w TextColor:c Font:F "
    "Shortcut:s Title:f ToolTip:l ToolTipRepresentation:TooltipRepresentation "
    "GroupHorizontalAlign:ItemHorizontalAlignment GroupVerticalAlign:ItemVerticalAlignment "
    "OnMainServerUnavalableBehavior:OnMainServerUnavalableBehavior"
)
_GROUP = _props(
    "Visible:b UserVisible:x Enabled:b ReadOnly:b EnableContentChange:b Title:l TitleTextColor:c TitleFont:F "
    "ToolTip:l ToolTipRepresentation:TooltipRepresentation Shortcut:s Width:d Height:d HorizontalStretch:w "
    "VerticalStretch:w GroupHorizontalAlign:ItemHorizontalAlignment GroupVerticalAlign:ItemVerticalAlignment"
)
_SIZED = (
    "Width:d AutoMaxWidth:b MaxWidth:d MinWidth:d Height:d AutoMaxHeight:b MaxHeight:d "
    "HorizontalStretch:b VerticalStretch:b "
)
ELEMENT_PROPERTIES = {
    "InputField": _FIELD
    + _props(
        "Width:d AutoMaxWidth:b MaxWidth:d MinWidth:d Height:d AutoMaxHeight:b MaxHeight:d HorizontalStretch:w "
        "VerticalStretch:w Wrap:b PasswordMode:w MultiLine:w ExtendedEdit:w MarkNegatives:w DropListButton:w "
        "ChoiceButton:w ChoiceButtonRepresentation:ChoiceButtonRepresentation ChoiceButtonPicture:p "
        "ClearButton:w SpinButton:w OpenButton:w CreateButton:w Mask:s MultipleValuesFont:F "
        "MultipleValuesTextColor:c MultipleValuesBackColor:c MultipleValuesHyperlink:w MultipleValuesPicture:p "
        "MultipleValueDataPath:s MultipleValuePictureDataPath:s MultipleValuePresentDataPath:s "
        "AllowInputEmptyMultipleValues:b AllowMultipleValuesDuplicates:b ExtendedEditMultipleValues:b "
        "MultipleValuePictureSize:InputFieldMultipleValuePictureSize "
        "MultipleValuePictureShape:InputFieldMultipleValuePictureShape ShowCheckBoxesInDropList:w "
        "AutoChoiceIncomplete:w QuickChoice:w ChoiceFoldersAndItems:FoldersAndItems Format:l EditFormat:l "
        "AutoMarkIncomplete:w ChooseType:b IncompleteChoiceMode:IncompleteItemChoiceMode TypeDomainEnabled:b "
        "TextEdit:b EditTextUpdate:EditTextUpdate MinValue:x MaxValue:x ChoiceForm:s ChoiceParameterLinks:x "
        "ChoiceParameters:x AvailableTypes:t ListChoiceMode:b ChoiceList:x ChoiceListButton:w "
        "ChoiceListHeight:d DropListWidth:d TextColor:c BackColor:c BorderColor:c Font:F TypeLink:x "
        "HeightControlVariant:HeightControlVariant AutoShowClearButtonMode:AutoShowClearButtonMode "
        "AutoShowOpenButtonMode:AutoShowOpenButtonMode AutoCorrectionOnTextInput:AutoCorrectionOnTextInput "
        "SpellCheckingOnTextInput:SpellCheckingOnTextInput "
        "AutoCapitalizationOnTextInput:AutoCapitalizationOnTextInput SpecialTextInputMode:SpecialTextInputMode "
        "AutofillHint:AutofillHint OnScreenKeyboardReturnKeyText:OnScreenKeyboardReturnKeyText InputHint:l "
        "ChoiceHistoryOnInput:ChoiceHistoryOnInput"
    ),
    "CheckBoxField": _FIELD
    + _props(
        "CheckBoxType:CheckBoxType ThreeState:b BorderColor:c BackColor:c TextColor:c Font:F EditFormat:l "
        "ItemTitleHeight:d ItemWidth:d ItemHeight:d EqualItemsWidth:w"
    ),
    "LabelField": _FIELD
    + _props(
        "Width:d AutoMaxWidth:b MaxWidth:d MinWidth:d Height:d AutoMaxHeight:b MaxHeight:d HorizontalStretch:w "
        "VerticalStretch:w MarkNegatives:w Format:l Hiperlink:b PasswordMode:w Border:x BorderColor:c "
        "TextColor:c BackColor:c Font:F"
    ),
    "RadioButtonField": _FIELD
    + _props(
        "RadioButtonType:RadioButtonType ItemWidth:d ItemHeight:d ItemTitleHeight:d ColumnsCount:d "
        "EqualColumnsWidth:w ChoiceList:x Font:F TextColor:c BackColor:c BorderColor:c"
    ),
    "PictureField": _FIELD
    + _props(
        _SIZED + "PictureSize:PictureSize Zoomable:b ImageScale:d Hyperlink:b NonselectedPictureText:l "
        "EnableStartDrag:b EnableDrag:b ValuesPicture:p TextColor:c Border:x BorderColor:c Font:F "
        "FileDragMode:FileDragMode"
    ),
    "CalendarField": _FIELD
    + _props(
        _SIZED + "SelectionMode:FormDateSelectionMode ShowCurrentDate:b CalendarNavigation:b "
        "BeginOfRepresentationPeriod:x EndOfRepresentationPeriod:x EnableStartDrag:b EnableDrag:b Font:F "
        "BorderColor:c Border:x ShowMonthsPanel:b WidthInMonths:d HeightInMonths:d"
    ),
    "SpreadSheetDocumentField": _FIELD
    + _props(
        _SIZED + "ShowGrid:b ShowHeaders:b VerticalScrollBar:x HorizontalScrollBar:x BlackAndWhiteView:b "
        "Protection:b SelectionShowMode:SelectionShowMode Output:UseOutput Edit:b ShowGroups:b "
        "EnableStartDrag:b EnableDrag:b BorderColor:c ViewScalingMode:ViewScalingMode ShowCellNames:b "
        "ShowRowAndColumnNames:b PointerType:x DrawingSelectionShowMode:DrawingSelectionShowMode"
    ),
    "TextDocumentField": _FIELD + _props(_SIZED + "Output:UseOutput TextColor:c BackColor:c BorderColor:c Font:F"),
    "FormattedDocumentField": _FIELD + _props(_SIZED + "Output:UseOutput TextColor:c BackColor:c BorderColor:c Font:F"),
    "ChartField": _FIELD + _props(_SIZED),
    "LabelDecoration": _DECORATION
    + _props(
        "Hyperlink:b HorizontalAlign:ItemHorizontalAlignment VerticalAlign:ItemVerticalAlignment "
        "TitleHeight:d BackColor:c BorderColor:c Border:x"
    ),
    "PictureDecoration": _DECORATION
    + _props(
        "Picture:p PictureSize:PictureSize Hyperlink:b Zoomable:b ImageScale:d NonselectedPictureText:l "
        "EnableStartDrag:b EnableDrag:b Border:x BorderColor:c FileDragMode:FileDragMode"
    ),
    "UsualGroup": _GROUP
    + _props(
        "Group:FormChildrenGroup ChildrenAlign:FormChildrenAlign HorizontalSpacing:FormItemSpacing "
        "VerticalSpacing:FormItemSpacing HorizontalAlign:ItemHorizontalAlignment "
        "VerticalAlign:ItemVerticalAlignment Behavior:UsualGroupBehavior CollapsedRepresentationTitle:l "
        "Collapsed:b ControlRepresentation:UsualGroupControlRepresentation "
        "Representation:UsualGroupRepresentation ShowLeftMargin:b United:b ChildItemsWidth:FormChildrenWidth "
        "Format:l ShowTitle:b TitleDataPath:s BackColor:c HiddenStateTitleBackColor:c "
        "ThroughAlign:UsualGroupThroughAlign CurrentRowUse:CurrentRowUse AssociatedTableElementId:x"
    ),
    "Page": _GROUP
    + _props(
        "Picture:p Group:FormChildrenGroup ChildrenAlign:FormChildrenAlign HorizontalSpacing:FormItemSpacing "
        "VerticalSpacing:FormItemSpacing HorizontalAlign:ItemHorizontalAlignment "
        "VerticalAlign:ItemVerticalAlignment ChildItemsWidth:FormChildrenWidth Format:l ShowTitle:b "
        "TitleDataPath:s BackColor:c ScrollOnCompress:b"
    ),
    "Pages": _GROUP
    + _props("PagesRepresentation:FormPagesRepresentation CurrentRowUse:CurrentRowUse AssociatedTableElementId:x"),
    "ColumnGroup": _GROUP
    + _props(
        "Group:ColumnsGroup ShowTitle:b TitleBackColor:c ShowInHeader:b HeaderDataPath:s "
        "HeaderHorizontalAlign:ItemHorizontalAlignment HeaderFormat:l HeaderPicture:p FixingInTable:FormFixedInTable"
    ),
    "CommandBar": _GROUP + _props("HorizontalLocation:ItemHorizontalAlignment CommandSource:s"),
    "Popup": _GROUP
    + _props(
        "Picture:p CommandSource:s Representation:ButtonRepresentation PlacementArea:MenuElementPlacementArea "
        "Shape:ButtonShape ShapeRepresentation:ButtonShapeRepresentation BackColor:c BorderColor:c"
    ),
    "ButtonGroup": _GROUP
    + _props("CommandSource:s PlacementArea:MenuElementPlacementArea Representation:ButtonGroupRepresentation"),
    "Table": _props(
        "Representation:TableRepresentation Visible:b UserVisible:x CommandBarLocation:FormElementCommandBarLocation "
        "Autofill:b Enabled:b ReadOnly:b SkipOnInput:w DefaultItem:b ChangeRowSet:b ChangeRowOrder:b Width:d "
        "AutoMaxWidth:b MaxWidth:d MinWidth:d Height:d AutoMaxHeight:b MaxHeight:d HeightInTableRows:d "
        "HeightControlVariant:TableHeightControlVariant AutoMaxRowsCount:b MaxRowsCount:d ChoiceMode:b "
        "MultipleChoice:b RowInputMode:TableRowInputMode SelectionMode:TableSelectionMode "
        "RowSelectionMode:TableRowSelectionMode Header:b HeaderHeight:d Footer:b FooterHeight:d "
        "HorizontalScrollBar:TableScrollBarUse VerticalScrollBar:TableScrollBarUse HorizontalLines:b "
        "VerticalLines:b FixedLeft:d FixedRight:d UseAlternationRowColor:b AutoInsertNewRow:b "
        "AutoAddIncomplete:w AutoMarkIncomplete:w SearchOnInput:SearchOnInput "
        "InitialListView:TableInitialListView InitialTreeView:TableInitialTreeView Output:UseOutput "
        "HorizontalStretch:b VerticalStretch:b EnableStartDrag:b EnableDrag:b FileDragMode:FileDragMode "
        "DataPath:s RowPictureDataPath:s RowsPicture:p TextColor:c BackColor:c BorderColor:c Font:F Title:l "
        "TitleHeight:d TitleFont:F TitleTextColor:c TitleLocation:FormElementTitleLocation Shortcut:s "
        "CommandSet:x ToolTip:l ToolTipRepresentation:TooltipRepresentation "
        "SearchStringLocation:SearchStringLocation ViewStatusLocation:ViewStatusLocation "
        "SearchControlLocation:SearchControlLocation GroupHorizontalAlign:ItemHorizontalAlignment "
        "GroupVerticalAlign:ItemVerticalAlignment RefreshRequest:RefreshRequestMethod "
        "CurrentRowUse:TableCurrentRowUse BehaviorOnHorizontalCompression:TableBehaviorOnHorizontalCompression "
        "ViewMode:x SettingsNamedItemDetailedRepresentation:b AutoRefresh:b AutoRefreshPeriod:d Period:x "
        "ChoiceFoldersAndItems:x RestoreCurrentRow:b TopLevelParent:x ShowRoot:b AllowRootChoice:b "
        "AllowGettingCurrentRowURL:b RowFilter:x UpdateOnDataChange:x UserSettingsGroup:s TreeSpecialSearch:b "
        "OnMainServerUnavalableBehavior:OnMainServerUnavalableBehavior"
    ),
    "Button": _props(
        "Type:ManagedFormButtonType DataPath:s CommandName:s Parameter:x Visible:b UserVisible:x "
        "Representation:ButtonRepresentation DefaultButton:b SkipOnInput:w Enabled:b DefaultItem:b "
        "OnlyInAllActions:w Width:d AutoMaxWidth:b MaxWidth:d MinWidth:d Height:d AutoMaxHeight:b MaxHeight:d "
        "HorizontalStretch:b VerticalStretch:b GroupHorizontalAlign:ItemHorizontalAlignment "
        "GroupVerticalAlign:ItemVerticalAlignment PlacementArea:MenuElementPlacementArea Check:b TextColor:c "
        "BackColor:c BorderColor:c Font:F Shortcut:s Picture:p Title:l TitleHeight:d "
        "ToolTipRepresentation:TooltipRepresentation RepresentationInContextMenu:RepresentationInContextMenu "
        "Shape:ButtonShape ShapeRepresentation:ButtonShapeRepresentation PictureLocation:FormButtonPictureLocation "
        "LocationInCommandBar:ButtonLocationInCommandBar CommandUniqueness:b "
        "OnMainServerUnavalableBehavior:OnMainServerUnavalableBehavior"
    ),
}
# Form-level scalars reuse the form.compile inventory; Title is multilingual.
ELEMENT_ENUMS.update({"Form" + name: values for name, values in _PROPERTY_ENUMS.items()})
FORM_ELEMENT_PROPERTIES = (
    ("Title", "l"),
    *(
        (
            name,
            "b"
            if schema is _PROPERTY_BOOL
            else "d"
            if schema is _PROPERTY_DECIMAL
            else "s"
            if schema is _PROPERTY_REF
            else "Form" + name,
        )
        for name, schema in _XML_PROPERTIES.items()
    ),
)
# Children that are the element's composition, never properties.
STRUCTURE_NODES = frozenset(
    (
        "ContextMenu",
        "ExtendedTooltip",
        "AutoCommandBar",
        "SearchStringAddition",
        "ViewStatusAddition",
        "SearchControlAddition",
        "Events",
        "ChildItems",
    )
)
ATTRIBUTE_ORDER = (
    "Title",
    "Type",
    "MainAttribute",
    "View",
    "Edit",
    "SavedData",
    "FillCheck",
    "Save",
    "UseAlways",
    "FunctionalOptions",
    "Columns",
    "Settings",
)
COMMAND_ORDER = (
    "Title",
    "ToolTip",
    "Shortcut",
    "Picture",
    "Use",
    "Action",
    "FunctionalOptions",
    "Representation",
    "ModifiesSavedData",
    "CurrentRowUse",
)

_PROPERTY_NAME = {"type": "string", "pattern": r"^[A-Za-z][A-Za-z0-9]{0,127}$"}
_LOCAL_TEXT = {
    "oneOf": [
        _TEXT,
        {
            "type": "object",
            "minProperties": 1,
            "maxProperties": 16,
            "propertyNames": {"type": "string", "pattern": r"^[A-Za-z]{2,8}(_[A-Za-z]{2,8})?$"},
            "additionalProperties": {"oneOf": [_TEXT, {"type": "null"}]},
        },
    ]
}
_TYPE_SPELLING = {"type": "string", "minLength": 1, "maxLength": 1024, "not": {"pattern": r'[<>&"\x00-\x1f]'}}
_REMOVE = {"const": True}


def _operation_schema(name, properties, required, **extra):
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"urn:onec-template:metadata:{name}:parameters:1",
        **_object(properties, required),
        **extra,
    }


_REMOVE_ONLY = {"if": {"required": ["remove"]}, "then": {"maxProperties": 2}}
_COLUMN = {
    **_object({"name": _NAME, "type": _TYPE_SPELLING, "title": _LOCAL_TEXT, "remove": _REMOVE}, ("name",)),
    **_REMOVE_ONLY,
}
OPERATION_SCHEMAS = {
    "form.set-properties": _operation_schema(
        "form.set-properties",
        {
            "element": _NAME,
            "properties": {"type": "object", "minProperties": 1, "maxProperties": 64, "propertyNames": _PROPERTY_NAME},
        },
        ("properties",),
    ),
    "form.move-element": _operation_schema(
        "form.move-element",
        {"element": _NAME, "into": _NAME, "after": _NAME, "before": _NAME},
        ("element",),
        anyOf=[{"required": [key]} for key in ("into", "after", "before")],
        **{"not": {"required": ["after", "before"]}},
    ),
    "form.remove-element": _operation_schema("form.remove-element", {"element": _NAME}, ("element",)),
    "form.rename-element": _operation_schema(
        "form.rename-element",
        {"element": _NAME, "newName": _NAME, "id": {"type": "integer", "minimum": 1}},
        ("element", "newName"),
    ),
    "form.set-attribute": _operation_schema(
        "form.set-attribute",
        {
            "name": _NAME,
            "type": _TYPE_SPELLING,
            "title": _LOCAL_TEXT,
            "main": _BOOL,
            "savedData": _BOOL,
            "fillChecking": {"enum": ["ShowError", "DontCheck"]},
            "columns": {**_array(_COLUMN), "minItems": 1, "maxItems": 256},
            "remove": _REMOVE,
        },
        ("name",),
        **_REMOVE_ONLY,
    ),
    "form.remove-event": _operation_schema(
        "form.remove-event",
        {"name": _NAME, "element": _NAME, "callType": {"enum": ["Before", "After", "Override"]}},
        ("name",),
    ),
    "form.set-command": _operation_schema(
        "form.set-command",
        {
            "name": _NAME,
            "action": _NAME,
            "title": _LOCAL_TEXT,
            "toolTip": _LOCAL_TEXT,
            "shortcut": {"type": "string", "pattern": r"^((Ctrl|Alt|Shift)\+){0,3}[A-Za-z0-9]{1,16}$"},
            "representation": {"enum": ["Auto", "Text", "Picture", "TextPicture"]},
            "modifiesSavedData": _BOOL,
            "currentRowUse": {"enum": ["Auto", "Use", "DontUse"]},
            "id": {"type": "integer", "minimum": 1},
            "remove": _REMOVE,
        },
        ("name",),
        # `id` removes one copy of a duplicated command: allowed only together with remove.
        allOf=[
            {"if": {"required": ["remove"]}, "then": {"maxProperties": 3}},
            {"if": {"required": ["remove"], "not": {"required": ["id"]}}, "then": {"maxProperties": 2}},
            {"if": {"required": ["id"]}, "then": {"required": ["remove"]}},
        ],
    ),
}
