"""Pure managed-form generator adapted from cc-1c-skills form-compile v1.0.

Copyright 2025-2026 Nick Shirokov, MIT; see
 automation/vendor/cc-1c-skills/LICENSE. No CLI, file writes or BSL generation.
"""

import math
import re
from decimal import Decimal

from . import metadata_form_schema


def decimal_text(number) -> str:
    """xs:decimal lexical form: no exponent, no trailing zeros (1e-07 -> 0.0000001)."""
    if isinstance(number, float) and not math.isfinite(number):
        raise ValueError("Non-finite number")
    # No normalize(): it rounds to the context precision (28 digits).
    text = format(Decimal(repr(number) if isinstance(number, float) else number), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def element_kind(description):
    # page/group and popup/picture are the intentional overlaps in the schema.
    return next(
        (
            key
            for key in (
                "page",
                "popup",
                "button",
                "columnGroup",
                "buttonGroup",
                "group",
                "input",
                "check",
                "radio",
                "progress",
                "label",
                "labelField",
                "spreadsheet",
                "textDocument",
                "formattedDocument",
                "chart",
                "table",
                "pages",
                "picture",
                "picField",
                "calendar",
                "cmdBar",
            )
            if key in description
        ),
        None,
    )


def render_form(definition, allocate_id=None) -> bytes:
    return _render_form(definition, allocate_id, "form.compile")


def render_edit_form(definition, allocate_id=None) -> bytes:
    return _render_form(definition, allocate_id, "form.edit")


def _render_form(definition, allocate_id, operation) -> bytes:
    """Render the existing description with an invocation-local ID allocator."""
    defn = metadata_form_schema.normalize_parameters(operation, {"definition": definition})["definition"]
    next_id = 0

    def new_id():
        nonlocal next_id
        if allocate_id is not None:
            return allocate_id()
        next_id += 1
        return next_id

    def esc_xml(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def emit_mltext(lines, indent, tag, text):
        if not text:
            lines.append(f"{indent}<{tag}/>")
            return
        lines.append(f"{indent}<{tag}>")
        lines.append(f"{indent}\t<v8:item>")
        lines.append(f"{indent}\t\t<v8:lang>ru</v8:lang>")
        lines.append(f"{indent}\t\t<v8:content>{esc_xml(text)}</v8:content>")
        lines.append(f"{indent}\t</v8:item>")
        lines.append(f"{indent}</{tag}>")

    # --- Event handler name generator ---

    EVENT_SUFFIX_MAP = {
        "OnChange": "\u041f\u0440\u0438\u0418\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u0438",
        "StartChoice": "\u041d\u0430\u0447\u0430\u043b\u043e\u0412\u044b\u0431\u043e\u0440\u0430",
        "ChoiceProcessing": "\u041e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0430\u0412\u044b\u0431\u043e\u0440\u0430",
        "AutoComplete": "\u0410\u0432\u0442\u043e\u041f\u043e\u0434\u0431\u043e\u0440",
        "Clearing": "\u041e\u0447\u0438\u0441\u0442\u043a\u0430",
        "Opening": "\u041e\u0442\u043a\u0440\u044b\u0442\u0438\u0435",
        "Click": "\u041d\u0430\u0436\u0430\u0442\u0438\u0435",
        "OnActivateRow": "\u041f\u0440\u0438\u0410\u043a\u0442\u0438\u0432\u0438\u0437\u0430\u0446\u0438\u0438\u0421\u0442\u0440\u043e\u043a\u0438",
        "BeforeAddRow": "\u041f\u0435\u0440\u0435\u0434\u041d\u0430\u0447\u0430\u043b\u043e\u043c\u0414\u043e\u0431\u0430\u0432\u043b\u0435\u043d\u0438\u044f",
        "BeforeDeleteRow": "\u041f\u0435\u0440\u0435\u0434\u0423\u0434\u0430\u043b\u0435\u043d\u0438\u0435\u043c",
        "BeforeRowChange": "\u041f\u0435\u0440\u0435\u0434\u041d\u0430\u0447\u0430\u043b\u043e\u043c\u0418\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u044f",
        "OnStartEdit": "\u041f\u0440\u0438\u041d\u0430\u0447\u0430\u043b\u0435\u0420\u0435\u0434\u0430\u043a\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u044f",
        "OnEndEdit": "\u041f\u0440\u0438\u041e\u043a\u043e\u043d\u0447\u0430\u043d\u0438\u0438\u0420\u0435\u0434\u0430\u043a\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u044f",
        "Selection": "\u0412\u044b\u0431\u043e\u0440\u0421\u0442\u0440\u043e\u043a\u0438",
        "OnCurrentPageChange": "\u041f\u0440\u0438\u0421\u043c\u0435\u043d\u0435\u0421\u0442\u0440\u0430\u043d\u0438\u0446\u044b",
        "TextEditEnd": "\u041e\u043a\u043e\u043d\u0447\u0430\u043d\u0438\u0435\u0412\u0432\u043e\u0434\u0430\u0422\u0435\u043a\u0441\u0442\u0430",
        "URLProcessing": "\u041e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0430\u041d\u0430\u0432\u0438\u0433\u0430\u0446\u0438\u043e\u043d\u043d\u043e\u0439\u0421\u0441\u044b\u043b\u043a\u0438",
        "DragStart": "\u041d\u0430\u0447\u0430\u043b\u043e\u041f\u0435\u0440\u0435\u0442\u0430\u0441\u043a\u0438\u0432\u0430\u043d\u0438\u044f",
        "Drag": "\u041f\u0435\u0440\u0435\u0442\u0430\u0441\u043a\u0438\u0432\u0430\u043d\u0438\u0435",
        "DragCheck": "\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430\u041f\u0435\u0440\u0435\u0442\u0430\u0441\u043a\u0438\u0432\u0430\u043d\u0438\u044f",
        "Drop": "\u041f\u043e\u043c\u0435\u0449\u0435\u043d\u0438\u0435",
        "AfterDeleteRow": "\u041f\u043e\u0441\u043b\u0435\u0423\u0434\u0430\u043b\u0435\u043d\u0438\u044f",
    }

    def get_handler_name(element_name, event_name):
        suffix = EVENT_SUFFIX_MAP.get(event_name)
        if suffix:
            return f"{element_name}{suffix}"
        return f"{element_name}{event_name}"

    def get_element_name(el, type_key):
        if el.get("name"):
            return str(el["name"])
        return str(el.get(type_key, ""))

    def emit_events(lines, el, element_name, indent):
        if not el.get("on"):
            return

        lines.append(f"{indent}<Events>")
        for evt in el["on"]:
            evt_name = evt if isinstance(evt, str) else evt["event"]
            handlers = el.get("handlers")
            if isinstance(evt, dict) and evt.get("handler"):
                handler = evt["handler"]
            elif handlers and handlers.get(evt_name):
                handler = str(handlers[evt_name])
            else:
                handler = get_handler_name(element_name, evt_name)
            call = f' callType="{evt["callType"]}"' if isinstance(evt, dict) and evt.get("callType") else ""
            lines.append(f'{indent}\t<Event name="{evt_name}"{call}>{handler}</Event>')
        lines.append(f"{indent}</Events>")

    def emit_companion(lines, tag, name, indent):
        cid = new_id()
        lines.append(f'{indent}<{tag} name="{name}" id="{cid}"/>')

    def emit_common_flags(lines, el, indent):
        if el.get("visible") is False or el.get("hidden") is True:
            lines.append(f"{indent}<Visible>false</Visible>")
        if el.get("enabled") is False or el.get("disabled") is True:
            lines.append(f"{indent}<Enabled>false</Enabled>")
        if el.get("readOnly") is True:
            lines.append(f"{indent}<ReadOnly>true</ReadOnly>")
        if el.get("horizontalStretch") is False:
            lines.append(f"{indent}<HorizontalStretch>false</HorizontalStretch>")
        if el.get("verticalStretch") is False:
            lines.append(f"{indent}<VerticalStretch>false</VerticalStretch>")

    def emit_title(lines, el, name, indent):
        if el.get("title"):
            emit_mltext(lines, indent, "Title", str(el["title"]))

    # --- Type emitter ---

    V8_TYPES = {
        "StandardPeriod": "v8:StandardPeriod",
        "ValueTable": "v8:ValueTable",
        "ValueTree": "v8:ValueTree",
        "ValueList": "v8:ValueListType",
        "TypeDescription": "v8:TypeDescription",
        "FixedArray": "v8:FixedArray",
        "FixedStructure": "v8:FixedStructure",
    }

    UI_TYPES = {
        "FormattedString": "v8ui:FormattedString",
        "Picture": "v8ui:Picture",
        "Color": "v8ui:Color",
        "Font": "v8ui:Font",
    }

    DCS_MAP = {
        "DataCompositionSettings": "dcsset:DataCompositionSettings",
        "DataCompositionSchema": "dcssch:DataCompositionSchema",
        "DataCompositionComparisonType": "dcscor:DataCompositionComparisonType",
    }

    CFG_REF_PATTERN = re.compile(
        r"^(CatalogRef|CatalogObject|DocumentRef|DocumentObject|EnumRef|"
        r"ChartOfAccountsRef|ChartOfCharacteristicTypesRef|ChartOfCalculationTypesRef|"
        r"ExchangePlanRef|BusinessProcessRef|TaskRef|"
        r"InformationRegisterRecordSet|AccumulationRegisterRecordSet|DataProcessorObject)\."
    )

    _FORM_TYPE_SYNONYMS = {
        "строка": "string",
        "число": "decimal",
        "булево": "boolean",
        "дата": "date",
        "датавремя": "dateTime",
        "number": "decimal",
        "bool": "boolean",
        "справочникссылка": "CatalogRef",
        "справочникобъект": "CatalogObject",
        "документссылка": "DocumentRef",
        "документобъект": "DocumentObject",
        "перечислениессылка": "EnumRef",
        "плансчетовссылка": "ChartOfAccountsRef",
        "планвидовхарактеристикссылка": "ChartOfCharacteristicTypesRef",
        "планвидоврасчётассылка": "ChartOfCalculationTypesRef",
        "планвидоврасчетассылка": "ChartOfCalculationTypesRef",
        "планобменассылка": "ExchangePlanRef",
        "бизнеспроцессссылка": "BusinessProcessRef",
        "задачассылка": "TaskRef",
        "определяемыйтип": "DefinedType",
    }

    def resolve_type_str(type_str):
        if not type_str:
            return type_str
        m = re.match(r"^([^(]+)\((.+)\)$", type_str)
        if m:
            base, params = m.group(1).strip(), m.group(2)
            r = _FORM_TYPE_SYNONYMS.get(base.lower())
            return f"{r}({params})" if r else type_str
        if "." in type_str:
            i = type_str.index(".")
            prefix, suffix = type_str[:i], type_str[i:]
            r = _FORM_TYPE_SYNONYMS.get(prefix.lower())
            return f"{r}{suffix}" if r else type_str
        r = _FORM_TYPE_SYNONYMS.get(type_str.lower())
        return r if r else type_str

    def emit_single_type(lines, type_str, indent):
        type_str = resolve_type_str(type_str)
        if type_str == "decimal":
            type_str = "decimal(15,0)"
        # boolean
        if type_str == "boolean":
            lines.append(f"{indent}<v8:Type>xs:boolean</v8:Type>")
            return

        # string or string(N)
        m = re.match(r"^string(\((\d+)\))?$", type_str)
        if m:
            length = m.group(2) if m.group(2) else "0"
            lines.append(f"{indent}<v8:Type>xs:string</v8:Type>")
            lines.append(f"{indent}<v8:StringQualifiers>")
            lines.append(f"{indent}\t<v8:Length>{length}</v8:Length>")
            lines.append(f"{indent}\t<v8:AllowedLength>Variable</v8:AllowedLength>")
            lines.append(f"{indent}</v8:StringQualifiers>")
            return

        # decimal(D,F) or decimal(D,F,nonneg)
        m = re.match(r"^decimal\((\d+),(\d+)(,nonneg)?\)$", type_str)
        if m:
            digits = m.group(1)
            fraction = m.group(2)
            sign = "Nonnegative" if m.group(3) else "Any"
            lines.append(f"{indent}<v8:Type>xs:decimal</v8:Type>")
            lines.append(f"{indent}<v8:NumberQualifiers>")
            lines.append(f"{indent}\t<v8:Digits>{digits}</v8:Digits>")
            lines.append(f"{indent}\t<v8:FractionDigits>{fraction}</v8:FractionDigits>")
            lines.append(f"{indent}\t<v8:AllowedSign>{sign}</v8:AllowedSign>")
            lines.append(f"{indent}</v8:NumberQualifiers>")
            return

        # date / dateTime / time
        m = re.match(r"^(date|dateTime|time)$", type_str)
        if m:
            fractions_map = {"date": "Date", "dateTime": "DateTime", "time": "Time"}
            fractions = fractions_map[type_str]
            lines.append(f"{indent}<v8:Type>xs:dateTime</v8:Type>")
            lines.append(f"{indent}<v8:DateQualifiers>")
            lines.append(f"{indent}\t<v8:DateFractions>{fractions}</v8:DateFractions>")
            lines.append(f"{indent}</v8:DateQualifiers>")
            return

        # V8 types
        if type_str in V8_TYPES:
            lines.append(f"{indent}<v8:Type>{V8_TYPES[type_str]}</v8:Type>")
            return

        if type_str == "SpreadsheetDocument":
            lines.append(
                f'{indent}<v8:Type xmlns:mxl="http://v8.1c.ru/8.2/data/spreadsheet">mxl:SpreadsheetDocument</v8:Type>'
            )
            return

        # UI types
        if type_str in UI_TYPES:
            lines.append(f"{indent}<v8:Type>{UI_TYPES[type_str]}</v8:Type>")
            return

        # DCS types
        if type_str.startswith("DataComposition"):
            if type_str in DCS_MAP:
                lines.append(f"{indent}<v8:Type>{DCS_MAP[type_str]}</v8:Type>")
                return

        # DynamicList
        if type_str == "DynamicList":
            lines.append(f"{indent}<v8:Type>cfg:DynamicList</v8:Type>")
            return

        # cfg: references
        if CFG_REF_PATTERN.match(type_str):
            lines.append(f"{indent}<v8:Type>cfg:{type_str}</v8:Type>")
            return

        # Fallback
        if "." in type_str:
            lines.append(f"{indent}<v8:Type>cfg:{type_str}</v8:Type>")
        else:
            lines.append(f"{indent}<v8:Type>{type_str}</v8:Type>")

    def emit_type(lines, type_str, indent):
        if not type_str:
            lines.append(f"{indent}<Type/>")
            return

        type_string = str(type_str)
        parts = [p.strip() for p in re.split(r"[|+]", type_string)]

        lines.append(f"{indent}<Type>")
        for part in parts:
            emit_single_type(lines, part, f"{indent}\t")
        lines.append(f"{indent}</Type>")

    # --- Element emitters ---

    def emit_element(lines, el, indent):
        type_key = element_kind(el)

        if not type_key:
            raise ValueError("Unknown element type")

        name = get_element_name(el, type_key)
        eid = new_id()

        emitters = {
            "group": emit_group,
            "input": emit_input,
            "check": emit_check,
            "radio": emit_radio,
            "progress": emit_progress,
            "label": emit_label,
            "labelField": emit_label_field,
            "spreadsheet": emit_spreadsheet,
            "table": emit_table,
            "pages": emit_pages,
            "page": emit_page,
            "button": emit_button,
            "picture": emit_picture_decoration,
            "picField": emit_picture_field,
            "calendar": emit_calendar,
            "cmdBar": emit_command_bar,
            "popup": emit_popup,
            "textDocument": emit_document_field("TextDocumentField"),
            "formattedDocument": emit_document_field("FormattedDocumentField"),
            "chart": emit_document_field("ChartField"),
            "columnGroup": emit_column_group,
            "buttonGroup": emit_button_group,
        }

        emitter = emitters.get(type_key)
        if emitter:
            emitter(lines, el, name, eid, indent)

    def emit_group(lines, el, name, eid, indent):
        lines.append(f'{indent}<UsualGroup name="{name}" id="{eid}">')
        inner = f"{indent}\t"

        emit_title(lines, el, name, inner)

        # Group orientation
        group_val = str(el.get("group", ""))
        orientation_map = {
            "horizontal": "Horizontal",
            "vertical": "Vertical",
            "alwaysHorizontal": "AlwaysHorizontal",
            "alwaysVertical": "AlwaysVertical",
        }
        orientation = orientation_map.get(group_val)
        if orientation:
            lines.append(f"{inner}<Group>{orientation}</Group>")

        # Behavior
        if group_val == "collapsible":
            lines.append(f"{inner}<Group>Vertical</Group>")
            lines.append(f"{inner}<Behavior>Collapsible</Behavior>")

        # Representation
        if el.get("representation"):
            repr_map = {
                "none": "None",
                "normal": "NormalSeparation",
                "weak": "WeakSeparation",
                "strong": "StrongSeparation",
            }
            repr_val = repr_map.get(str(el["representation"]), str(el["representation"]))
            lines.append(f"{inner}<Representation>{repr_val}</Representation>")

        # ShowTitle
        if "showTitle" in el:
            lines.append(f"{inner}<ShowTitle>{str(bool(el['showTitle'])).lower()}</ShowTitle>")

        # United
        if el.get("united") is False:
            lines.append(f"{inner}<United>false</United>")

        emit_common_flags(lines, el, inner)

        # Companion: ExtendedTooltip
        emit_companion(
            lines,
            "ExtendedTooltip",
            f"{name}\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
            inner,
        )

        # Children
        if el.get("children") and len(el["children"]) > 0:
            lines.append(f"{inner}<ChildItems>")
            for child in el["children"]:
                emit_element(lines, child, f"{inner}\t")
            lines.append(f"{inner}</ChildItems>")

        lines.append(f"{indent}</UsualGroup>")

    def emit_choice_list(lines, choices, indent):
        if not choices:
            return
        lines.append(f"{indent}<ChoiceList>")
        for choice in choices:
            lines.append(f"{indent}\t<xr:Item>")
            lines.append(f"{indent}\t\t<xr:Presentation/>")
            lines.append(f"{indent}\t\t<xr:CheckState>0</xr:CheckState>")
            lines.append(f'{indent}\t\t<xr:Value xsi:type="FormChoiceListDesTimeValue">')
            emit_mltext(lines, f"{indent}\t\t\t", "Presentation", str(choice["title"]))
            choice_type = choice.get("type")
            if choice_type is None:
                if isinstance(choice["value"], bool):
                    choice_type = "boolean"
                elif isinstance(choice["value"], (int, float)):
                    choice_type = "number"
            value_types: dict[object, str] = {"number": "xs:decimal", "boolean": "xs:boolean"}
            value_type = value_types.get(choice_type, "xs:string")
            if choice_type == "boolean":
                value = str(choice["value"]).lower()
            elif isinstance(choice["value"], (int, float)) and not isinstance(choice["value"], bool):
                value = decimal_text(choice["value"])
            else:
                value = str(choice["value"])
            lines.append(f'{indent}\t\t\t<Value xsi:type="{value_type}">{esc_xml(value)}</Value>')
            lines.append(f"{indent}\t\t</xr:Value>")
            lines.append(f"{indent}\t</xr:Item>")
        lines.append(f"{indent}</ChoiceList>")

    def emit_input(lines, el, name, eid, indent):
        lines.append(f'{indent}<InputField name="{name}" id="{eid}">')
        inner = f"{indent}\t"

        if el.get("path"):
            lines.append(f"{inner}<DataPath>{el['path']}</DataPath>")

        if el.get("title"):
            title = str(el["title"])
            emit_mltext(lines, inner, "Title", title if operation == "form.edit" else title.rstrip(":").rstrip())
        emit_common_flags(lines, el, inner)

        if el.get("titleLocation"):
            loc_map = {"none": "None", "left": "Left", "right": "Right", "top": "Top", "bottom": "Bottom"}
            loc = loc_map.get(str(el["titleLocation"]), str(el["titleLocation"]))
            lines.append(f"{inner}<TitleLocation>{loc}</TitleLocation>")

        if el.get("listChoiceMode") is True:
            lines.append(f"{inner}<ListChoiceMode>true</ListChoiceMode>")
        emit_choice_list(lines, el.get("choices", []), inner)

        if el.get("multiLine") is True:
            lines.append(f"{inner}<MultiLine>true</MultiLine>")
        if el.get("passwordMode") is True:
            lines.append(f"{inner}<PasswordMode>true</PasswordMode>")
        if el.get("choiceButton") is not None:
            lines.append(f"{inner}<ChoiceButton>{str(bool(el['choiceButton'])).lower()}</ChoiceButton>")
        if el.get("clearButton") is True:
            lines.append(f"{inner}<ClearButton>true</ClearButton>")
        if el.get("spinButton") is True:
            lines.append(f"{inner}<SpinButton>true</SpinButton>")
        if el.get("dropListButton") is True:
            lines.append(f"{inner}<DropListButton>true</DropListButton>")
        if el.get("markIncomplete") is True:
            lines.append(f"{inner}<AutoMarkIncomplete>true</AutoMarkIncomplete>")
        if el.get("skipOnInput") is True:
            lines.append(f"{inner}<SkipOnInput>true</SkipOnInput>")
        if el.get("autoMaxWidth") is False:
            lines.append(f"{inner}<AutoMaxWidth>false</AutoMaxWidth>")
        if el.get("autoMaxHeight") is False:
            lines.append(f"{inner}<AutoMaxHeight>false</AutoMaxHeight>")
        if el.get("width"):
            lines.append(f"{inner}<Width>{el['width']}</Width>")
        if el.get("height"):
            lines.append(f"{inner}<Height>{el['height']}</Height>")
        if el.get("horizontalStretch") is True:
            lines.append(f"{inner}<HorizontalStretch>true</HorizontalStretch>")
        if el.get("verticalStretch") is True:
            lines.append(f"{inner}<VerticalStretch>true</VerticalStretch>")

        if el.get("inputHint"):
            emit_mltext(lines, inner, "InputHint", str(el["inputHint"]))

        # Companions
        emit_companion(
            lines,
            "ContextMenu",
            f"{name}\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442\u043d\u043e\u0435\u041c\u0435\u043d\u044e",
            inner,
        )
        emit_companion(
            lines,
            "ExtendedTooltip",
            f"{name}\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
            inner,
        )

        emit_events(lines, el, name, inner)

        lines.append(f"{indent}</InputField>")

    def emit_spreadsheet(lines, el, name, eid, indent):
        lines.append(f'{indent}<SpreadSheetDocumentField name="{name}" id="{eid}">')
        inner = f"{indent}\t"
        if el.get("path"):
            lines.append(f"{inner}<DataPath>{el['path']}</DataPath>")
        lines.append(f"{inner}<TitleLocation>None</TitleLocation>")
        emit_common_flags(lines, el, inner)
        if el.get("horizontalStretch") is True:
            lines.append(f"{inner}<HorizontalStretch>true</HorizontalStretch>")
        if el.get("verticalStretch") is True:
            lines.append(f"{inner}<VerticalStretch>true</VerticalStretch>")
        emit_companion(lines, "ContextMenu", f"{name}КонтекстноеМеню", inner)
        emit_companion(lines, "ExtendedTooltip", f"{name}РасширеннаяПодсказка", inner)
        lines.append(f"{indent}</SpreadSheetDocumentField>")

    def emit_check(lines, el, name, eid, indent):
        lines.append(f'{indent}<CheckBoxField name="{name}" id="{eid}">')
        inner = f"{indent}\t"

        if el.get("path"):
            lines.append(f"{inner}<DataPath>{el['path']}</DataPath>")

        emit_title(lines, el, name, inner)
        emit_common_flags(lines, el, inner)

        if el.get("titleLocation"):
            lines.append(f"{inner}<TitleLocation>{el['titleLocation']}</TitleLocation>")

        # Companions
        emit_companion(
            lines,
            "ContextMenu",
            f"{name}\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442\u043d\u043e\u0435\u041c\u0435\u043d\u044e",
            inner,
        )
        emit_companion(
            lines,
            "ExtendedTooltip",
            f"{name}\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
            inner,
        )

        emit_events(lines, el, name, inner)

        lines.append(f"{indent}</CheckBoxField>")

    def emit_radio(lines, el, name, eid, indent):
        lines.append(f'{indent}<RadioButtonField name="{name}" id="{eid}">')
        inner = f"{indent}\t"
        if el.get("path"):
            lines.append(f"{inner}<DataPath>{el['path']}</DataPath>")
        lines.append(f"{inner}<RadioButtonType>Auto</RadioButtonType>")
        emit_choice_list(lines, el.get("choices", []), inner)
        emit_common_flags(lines, el, inner)
        if el.get("titleLocation"):
            lines.append(f"{inner}<TitleLocation>{str(el['titleLocation']).capitalize()}</TitleLocation>")
        emit_companion(lines, "ContextMenu", f"{name}КонтекстноеМеню", inner)
        emit_companion(lines, "ExtendedTooltip", f"{name}РасширеннаяПодсказка", inner)
        emit_events(lines, el, name, inner)
        lines.append(f"{indent}</RadioButtonField>")

    def emit_progress(lines, el, name, eid, indent):
        lines.append(f'{indent}<ProgressBarField name="{name}" id="{eid}">')
        inner = f"{indent}\t"
        if el.get("path"):
            lines.append(f"{inner}<DataPath>{el['path']}</DataPath>")
        if el.get("titleLocation"):
            lines.append(f"{inner}<TitleLocation>{str(el['titleLocation']).capitalize()}</TitleLocation>")
        emit_common_flags(lines, el, inner)
        emit_companion(lines, "ContextMenu", f"{name}КонтекстноеМеню", inner)
        emit_companion(lines, "ExtendedTooltip", f"{name}РасширеннаяПодсказка", inner)
        lines.append(f"{indent}</ProgressBarField>")

    def emit_label(lines, el, name, eid, indent):
        lines.append(f'{indent}<LabelDecoration name="{name}" id="{eid}">')
        inner = f"{indent}\t"

        if el.get("title"):
            formatted = "true" if el.get("hyperlink") is True else "false"
            lines.append(f'{inner}<Title formatted="{formatted}">')
            lines.append(f"{inner}\t<v8:item>")
            lines.append(f"{inner}\t\t<v8:lang>ru</v8:lang>")
            lines.append(f"{inner}\t\t<v8:content>{esc_xml(str(el['title']))}</v8:content>")
            lines.append(f"{inner}\t</v8:item>")
            lines.append(f"{inner}</Title>")

        emit_common_flags(lines, el, inner)

        if el.get("hyperlink") is True:
            lines.append(f"{inner}<Hyperlink>true</Hyperlink>")
        if el.get("textColor"):
            lines.append(f"{inner}<TextColor>{esc_xml(str(el['textColor']))}</TextColor>")
        if el.get("autoMaxWidth") is False:
            lines.append(f"{inner}<AutoMaxWidth>false</AutoMaxWidth>")
        if el.get("autoMaxHeight") is False:
            lines.append(f"{inner}<AutoMaxHeight>false</AutoMaxHeight>")
        if el.get("width"):
            lines.append(f"{inner}<Width>{el['width']}</Width>")
        if el.get("height"):
            lines.append(f"{inner}<Height>{el['height']}</Height>")

        # Companions
        emit_companion(
            lines,
            "ContextMenu",
            f"{name}\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442\u043d\u043e\u0435\u041c\u0435\u043d\u044e",
            inner,
        )
        emit_companion(
            lines,
            "ExtendedTooltip",
            f"{name}\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
            inner,
        )

        emit_events(lines, el, name, inner)

        lines.append(f"{indent}</LabelDecoration>")

    def emit_label_field(lines, el, name, eid, indent):
        lines.append(f'{indent}<LabelField name="{name}" id="{eid}">')
        inner = f"{indent}\t"

        if el.get("path"):
            lines.append(f"{inner}<DataPath>{el['path']}</DataPath>")

        emit_title(lines, el, name, inner)
        emit_common_flags(lines, el, inner)

        if el.get("hyperlink") is True:
            lines.append(f"{inner}<Hyperlink>true</Hyperlink>")

        # Companions
        emit_companion(
            lines,
            "ContextMenu",
            f"{name}\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442\u043d\u043e\u0435\u041c\u0435\u043d\u044e",
            inner,
        )
        emit_companion(
            lines,
            "ExtendedTooltip",
            f"{name}\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
            inner,
        )

        emit_events(lines, el, name, inner)

        lines.append(f"{indent}</LabelField>")

    def emit_table(lines, el, name, eid, indent):
        lines.append(f'{indent}<Table name="{name}" id="{eid}">')
        inner = f"{indent}\t"

        if el.get("path"):
            lines.append(f"{inner}<DataPath>{el['path']}</DataPath>")

        emit_title(lines, el, name, inner)
        emit_common_flags(lines, el, inner)

        if el.get("representation"):
            representation = {
                "picture": "Picture",
                "text": "Text",
                "pictureAndText": "PictureAndText",
                "auto": "Auto",
            }.get(str(el["representation"]), str(el["representation"]))
            lines.append(f"{inner}<Representation>{representation}</Representation>")
        if el.get("changeRowSet") is True:
            lines.append(f"{inner}<ChangeRowSet>true</ChangeRowSet>")
        if el.get("changeRowOrder") is True:
            lines.append(f"{inner}<ChangeRowOrder>true</ChangeRowOrder>")
        if el.get("height"):
            lines.append(f"{inner}<HeightInTableRows>{el['height']}</HeightInTableRows>")
        if el.get("header") is False:
            lines.append(f"{inner}<Header>false</Header>")
        if el.get("footer") is True:
            lines.append(f"{inner}<Footer>true</Footer>")

        if el.get("commandBarLocation"):
            lines.append(f"{inner}<CommandBarLocation>{el['commandBarLocation']}</CommandBarLocation>")
        if el.get("searchStringLocation"):
            lines.append(f"{inner}<SearchStringLocation>{el['searchStringLocation']}</SearchStringLocation>")

        # Companions
        emit_companion(
            lines,
            "ContextMenu",
            f"{name}\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442\u043d\u043e\u0435\u041c\u0435\u043d\u044e",
            inner,
        )
        buttons = el.get("commandBarButtons", [])
        if buttons:
            bar_name = (
                f"{name}\u041a\u043e\u043c\u0430\u043d\u0434\u043d\u0430\u044f\u041f\u0430\u043d\u0435\u043b\u044c"
            )
            lines.append(f'{inner}<AutoCommandBar name="{bar_name}" id="{new_id()}">')
            lines.append(f"{inner}\t<ChildItems>")
            for button in buttons:
                emit_element(lines, button, f"{inner}\t\t")
            lines.append(f"{inner}\t</ChildItems>")
            lines.append(f"{inner}</AutoCommandBar>")
        else:
            emit_companion(
                lines,
                "AutoCommandBar",
                f"{name}\u041a\u043e\u043c\u0430\u043d\u0434\u043d\u0430\u044f\u041f\u0430\u043d\u0435\u043b\u044c",
                inner,
            )
        emit_companion(
            lines,
            "ExtendedTooltip",
            f"{name}\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
            inner,
        )
        emit_companion(
            lines,
            "SearchStringAddition",
            f"{name}\u0421\u0442\u0440\u043e\u043a\u0430\u041f\u043e\u0438\u0441\u043a\u0430",
            inner,
        )
        emit_companion(
            lines,
            "ViewStatusAddition",
            f"{name}\u0421\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435\u041f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0430",
            inner,
        )
        emit_companion(
            lines,
            "SearchControlAddition",
            f"{name}\u0423\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435\u041f\u043e\u0438\u0441\u043a\u043e\u043c",
            inner,
        )

        # Columns
        if el.get("columns") and len(el["columns"]) > 0:
            lines.append(f"{inner}<ChildItems>")
            for col in el["columns"]:
                emit_element(lines, col, f"{inner}\t")
            lines.append(f"{inner}</ChildItems>")

        emit_events(lines, el, name, inner)

        lines.append(f"{indent}</Table>")

    def emit_pages(lines, el, name, eid, indent):
        lines.append(f'{indent}<Pages name="{name}" id="{eid}">')
        inner = f"{indent}\t"

        if el.get("pagesRepresentation"):
            lines.append(f"{inner}<PagesRepresentation>{el['pagesRepresentation']}</PagesRepresentation>")

        emit_common_flags(lines, el, inner)

        # Companion
        emit_companion(
            lines,
            "ExtendedTooltip",
            f"{name}\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
            inner,
        )

        emit_events(lines, el, name, inner)

        # Children (pages)
        if el.get("children") and len(el["children"]) > 0:
            lines.append(f"{inner}<ChildItems>")
            for child in el["children"]:
                emit_element(lines, child, f"{inner}\t")
            lines.append(f"{inner}</ChildItems>")

        lines.append(f"{indent}</Pages>")

    def emit_page(lines, el, name, eid, indent):
        lines.append(f'{indent}<Page name="{name}" id="{eid}">')
        inner = f"{indent}\t"

        emit_title(lines, el, name, inner)
        emit_common_flags(lines, el, inner)

        if el.get("group"):
            orientation_map = {
                "horizontal": "Horizontal",
                "vertical": "Vertical",
                "alwaysHorizontal": "AlwaysHorizontal",
                "alwaysVertical": "AlwaysVertical",
            }
            orientation = orientation_map.get(str(el["group"]))
            if orientation:
                lines.append(f"{inner}<Group>{orientation}</Group>")

        # Companion
        emit_companion(
            lines,
            "ExtendedTooltip",
            f"{name}\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
            inner,
        )

        # Children
        if el.get("children") and len(el["children"]) > 0:
            lines.append(f"{inner}<ChildItems>")
            for child in el["children"]:
                emit_element(lines, child, f"{inner}\t")
            lines.append(f"{inner}</ChildItems>")

        lines.append(f"{indent}</Page>")

    def emit_button(lines, el, name, eid, indent):
        lines.append(f'{indent}<Button name="{name}" id="{eid}">')
        inner = f"{indent}\t"

        # Type
        if el.get("type"):
            btn_type_map = {"usual": "UsualButton", "hyperlink": "Hyperlink", "commandBar": "CommandBarButton"}
            btn_type = btn_type_map.get(str(el["type"]), str(el["type"]))
            lines.append(f"{inner}<Type>{btn_type}</Type>")

        # CommandName
        if el.get("command"):
            lines.append(f"{inner}<CommandName>Form.Command.{el['command']}</CommandName>")
        if el.get("stdCommand"):
            sc = str(el["stdCommand"])
            m = re.match(r"^(.+)\.(.+)$", sc)
            if m:
                lines.append(f"{inner}<CommandName>Form.Item.{m.group(1)}.StandardCommand.{m.group(2)}</CommandName>")
            else:
                lines.append(f"{inner}<CommandName>Form.StandardCommand.{sc}</CommandName>")

        emit_title(lines, el, name, inner)
        emit_common_flags(lines, el, inner)

        if el.get("defaultButton") is True:
            lines.append(f"{inner}<DefaultButton>true</DefaultButton>")

        # Picture
        if el.get("picture"):
            lines.append(f"{inner}<Picture>")
            lines.append(f"{inner}\t<xr:Ref>{el['picture']}</xr:Ref>")
            lines.append(f"{inner}\t<xr:LoadTransparent>true</xr:LoadTransparent>")
            lines.append(f"{inner}</Picture>")

        if el.get("representation"):
            representation = {
                "picture": "Picture",
                "text": "Text",
                "pictureAndText": "PictureAndText",
                "auto": "Auto",
            }.get(str(el["representation"]), str(el["representation"]))
            lines.append(f"{inner}<Representation>{representation}</Representation>")

        if el.get("locationInCommandBar"):
            lines.append(f"{inner}<LocationInCommandBar>{el['locationInCommandBar']}</LocationInCommandBar>")

        # Companion
        emit_companion(
            lines,
            "ExtendedTooltip",
            f"{name}\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
            inner,
        )

        emit_events(lines, el, name, inner)

        lines.append(f"{indent}</Button>")

    def emit_picture_decoration(lines, el, name, eid, indent):
        lines.append(f'{indent}<PictureDecoration name="{name}" id="{eid}">')
        inner = f"{indent}\t"

        emit_title(lines, el, name, inner)
        emit_common_flags(lines, el, inner)

        if el.get("picture") or el.get("src"):
            ref = str(el.get("src") or el.get("picture"))
            lines.append(f"{inner}<Picture>")
            lines.append(f"{inner}\t<xr:Ref>{ref}</xr:Ref>")
            lines.append(f"{inner}\t<xr:LoadTransparent>true</xr:LoadTransparent>")
            lines.append(f"{inner}</Picture>")

        if el.get("hyperlink") is True:
            lines.append(f"{inner}<Hyperlink>true</Hyperlink>")
        if el.get("width"):
            lines.append(f"{inner}<Width>{el['width']}</Width>")
        if el.get("height"):
            lines.append(f"{inner}<Height>{el['height']}</Height>")

        # Companions
        emit_companion(
            lines,
            "ContextMenu",
            f"{name}\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442\u043d\u043e\u0435\u041c\u0435\u043d\u044e",
            inner,
        )
        emit_companion(
            lines,
            "ExtendedTooltip",
            f"{name}\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
            inner,
        )

        emit_events(lines, el, name, inner)

        lines.append(f"{indent}</PictureDecoration>")

    def emit_picture_field(lines, el, name, eid, indent):
        lines.append(f'{indent}<PictureField name="{name}" id="{eid}">')
        inner = f"{indent}\t"

        if el.get("path"):
            lines.append(f"{inner}<DataPath>{el['path']}</DataPath>")

        emit_title(lines, el, name, inner)
        emit_common_flags(lines, el, inner)

        if el.get("width"):
            lines.append(f"{inner}<Width>{el['width']}</Width>")
        if el.get("height"):
            lines.append(f"{inner}<Height>{el['height']}</Height>")

        # Companions
        emit_companion(
            lines,
            "ContextMenu",
            f"{name}\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442\u043d\u043e\u0435\u041c\u0435\u043d\u044e",
            inner,
        )
        emit_companion(
            lines,
            "ExtendedTooltip",
            f"{name}\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
            inner,
        )

        emit_events(lines, el, name, inner)

        lines.append(f"{indent}</PictureField>")

    def emit_calendar(lines, el, name, eid, indent):
        lines.append(f'{indent}<CalendarField name="{name}" id="{eid}">')
        inner = f"{indent}\t"

        if el.get("path"):
            lines.append(f"{inner}<DataPath>{el['path']}</DataPath>")

        emit_title(lines, el, name, inner)
        emit_common_flags(lines, el, inner)

        # Companions
        emit_companion(
            lines,
            "ContextMenu",
            f"{name}\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442\u043d\u043e\u0435\u041c\u0435\u043d\u044e",
            inner,
        )
        emit_companion(
            lines,
            "ExtendedTooltip",
            f"{name}\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
            inner,
        )

        emit_events(lines, el, name, inner)

        lines.append(f"{indent}</CalendarField>")

    def emit_document_field(tag):
        # Designer writes these fields with the same companions as InputField.
        def emit(lines, el, name, eid, indent):
            lines.append(f'{indent}<{tag} name="{name}" id="{eid}">')
            inner = f"{indent}\t"
            if el.get("path"):
                lines.append(f"{inner}<DataPath>{el['path']}</DataPath>")
            emit_title(lines, el, name, inner)
            emit_common_flags(lines, el, inner)
            emit_companion(lines, "ContextMenu", f"{name}КонтекстноеМеню", inner)
            emit_companion(lines, "ExtendedTooltip", f"{name}РасширеннаяПодсказка", inner)
            emit_events(lines, el, name, inner)
            lines.append(f"{indent}</{tag}>")

        return emit

    def emit_children(lines, el, inner):
        if el.get("children"):
            lines.append(f"{inner}<ChildItems>")
            for child in el["children"]:
                emit_element(lines, child, f"{inner}\t")
            lines.append(f"{inner}</ChildItems>")

    def emit_column_group(lines, el, name, eid, indent):
        lines.append(f'{indent}<ColumnGroup name="{name}" id="{eid}">')
        inner = f"{indent}\t"
        emit_title(lines, el, name, inner)
        emit_common_flags(lines, el, inner)
        if el.get("group"):
            group = {"horizontal": "Horizontal", "vertical": "Vertical", "inCell": "InCell"}.get(str(el["group"]))
            if group is None:
                raise ValueError("Invalid form parameters")
            lines.append(f"{inner}<Group>{group}</Group>")
        if "showTitle" in el:
            lines.append(f"{inner}<ShowTitle>{str(el['showTitle']).lower()}</ShowTitle>")
        emit_companion(
            lines,
            "ExtendedTooltip",
            f"{name}\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
            inner,
        )
        emit_children(lines, el, inner)
        lines.append(f"{indent}</ColumnGroup>")

    def emit_button_group(lines, el, name, eid, indent):
        lines.append(f'{indent}<ButtonGroup name="{name}" id="{eid}">')
        inner = f"{indent}\t"
        emit_title(lines, el, name, inner)
        emit_common_flags(lines, el, inner)
        if el.get("representation"):
            if el["representation"] not in metadata_form_schema.ELEMENT_ENUMS["ButtonGroupRepresentation"]:
                raise ValueError("Invalid form parameters")
            lines.append(f"{inner}<Representation>{el['representation']}</Representation>")
        emit_companion(
            lines,
            "ExtendedTooltip",
            f"{name}\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
            inner,
        )
        emit_children(lines, el, inner)
        lines.append(f"{indent}</ButtonGroup>")

    def emit_command_bar(lines, el, name, eid, indent):
        lines.append(f'{indent}<CommandBar name="{name}" id="{eid}">')
        inner = f"{indent}\t"

        if el.get("autofill") is True:
            lines.append(f"{inner}<Autofill>true</Autofill>")

        emit_common_flags(lines, el, inner)
        emit_companion(
            lines,
            "ExtendedTooltip",
            f"{name}\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
            inner,
        )

        # Children
        if el.get("children") and len(el["children"]) > 0:
            lines.append(f"{inner}<ChildItems>")
            for child in el["children"]:
                emit_element(lines, child, f"{inner}\t")
            lines.append(f"{inner}</ChildItems>")

        lines.append(f"{indent}</CommandBar>")

    def emit_popup(lines, el, name, eid, indent):
        lines.append(f'{indent}<Popup name="{name}" id="{eid}">')
        inner = f"{indent}\t"

        emit_title(lines, el, name, inner)
        emit_common_flags(lines, el, inner)

        if el.get("picture"):
            lines.append(f"{inner}<Picture>")
            lines.append(f"{inner}\t<xr:Ref>{el['picture']}</xr:Ref>")
            lines.append(f"{inner}\t<xr:LoadTransparent>true</xr:LoadTransparent>")
            lines.append(f"{inner}</Picture>")

        if el.get("representation"):
            lines.append(f"{inner}<Representation>{el['representation']}</Representation>")

        emit_companion(
            lines,
            "ExtendedTooltip",
            f"{name}\u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u0430\u044f\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0430",
            inner,
        )

        # Children
        if el.get("children") and len(el["children"]) > 0:
            lines.append(f"{inner}<ChildItems>")
            for child in el["children"]:
                emit_element(lines, child, f"{inner}\t")
            lines.append(f"{inner}</ChildItems>")

        lines.append(f"{indent}</Popup>")

    # --- Attribute emitter ---

    def emit_attributes(lines, attrs, indent):
        if not attrs or len(attrs) == 0:
            return

        lines.append(f"{indent}<Attributes>")
        for attr in attrs:
            attr_id = new_id()
            attr_name = str(attr["name"])

            lines.append(f'{indent}\t<Attribute name="{attr_name}" id="{attr_id}">')
            inner = f"{indent}\t\t"

            if attr.get("title"):
                emit_mltext(lines, inner, "Title", str(attr["title"]))

            # Type
            if attr.get("type"):
                emit_type(lines, str(attr["type"]), inner)
            else:
                lines.append(f"{inner}<Type/>")

            if attr.get("main") is True:
                lines.append(f"{inner}<MainAttribute>true</MainAttribute>")
            if attr.get("savedData") is True:
                lines.append(f"{inner}<SavedData>true</SavedData>")
            if attr.get("fillChecking"):
                lines.append(f"{inner}<FillChecking>{attr['fillChecking']}</FillChecking>")

            # Columns (for ValueTable/ValueTree)
            if attr.get("columns") and len(attr["columns"]) > 0:
                lines.append(f"{inner}<Columns>")
                for col in attr["columns"]:
                    col_id = new_id()
                    lines.append(f'{inner}\t<Column name="{col["name"]}" id="{col_id}">')
                    if col.get("title"):
                        emit_mltext(lines, f"{inner}\t\t", "Title", str(col["title"]))
                    emit_type(lines, str(col.get("type", "")), f"{inner}\t\t")
                    lines.append(f"{inner}\t</Column>")
                lines.append(f"{inner}</Columns>")

            lines.append(f"{indent}\t</Attribute>")
        lines.append(f"{indent}</Attributes>")

    # --- Parameter emitter ---

    def emit_parameters(lines, params, indent):
        if not params or len(params) == 0:
            return

        lines.append(f"{indent}<Parameters>")
        for param in params:
            lines.append(f'{indent}\t<Parameter name="{param["name"]}">')
            inner = f"{indent}\t\t"

            emit_type(lines, str(param.get("type", "")), inner)

            if param.get("key") is True:
                lines.append(f"{inner}<KeyParameter>true</KeyParameter>")

            lines.append(f"{indent}\t</Parameter>")
        lines.append(f"{indent}</Parameters>")

    # --- Command emitter ---

    def emit_commands(lines, cmds, indent):
        if not cmds or len(cmds) == 0:
            return

        lines.append(f"{indent}<Commands>")
        for cmd in cmds:
            cmd_id = new_id()
            lines.append(f'{indent}\t<Command name="{cmd["name"]}" id="{cmd_id}">')
            inner = f"{indent}\t\t"

            if cmd.get("title"):
                emit_mltext(lines, inner, "Title", str(cmd["title"]))

            actions = cmd.get("actions") or (
                [{"handler": cmd["action"], **({"callType": cmd["callType"]} if cmd.get("callType") else {})}]
                if cmd.get("action")
                else []
            )
            for action in actions:
                call = f' callType="{action["callType"]}"' if action.get("callType") else ""
                lines.append(f"{inner}<Action{call}>{action['handler']}</Action>")

            if cmd.get("shortcut"):
                lines.append(f"{inner}<Shortcut>{cmd['shortcut']}</Shortcut>")

            if cmd.get("picture"):
                lines.append(f"{inner}<Picture>")
                lines.append(f"{inner}\t<xr:Ref>{cmd['picture']}</xr:Ref>")
                lines.append(f"{inner}\t<xr:LoadTransparent>true</xr:LoadTransparent>")
                lines.append(f"{inner}</Picture>")

            if cmd.get("representation"):
                lines.append(f"{inner}<Representation>{cmd['representation']}</Representation>")

            lines.append(f"{indent}\t</Command>")
        lines.append(f"{indent}</Commands>")

    # --- Properties emitter ---

    PROP_MAP = {
        "autoTitle": "AutoTitle",
        "windowOpeningMode": "WindowOpeningMode",
        "commandBarLocation": "CommandBarLocation",
        "saveDataInSettings": "SaveDataInSettings",
        "autoSaveDataInSettings": "AutoSaveDataInSettings",
        "autoTime": "AutoTime",
        "usePostingMode": "UsePostingMode",
        "repostOnWrite": "RepostOnWrite",
        "autoURL": "AutoURL",
        "autoFillCheck": "AutoFillCheck",
        "customizable": "Customizable",
        "enterKeyBehavior": "EnterKeyBehavior",
        "verticalScroll": "VerticalScroll",
        "scalingMode": "ScalingMode",
        "useForFoldersAndItems": "UseForFoldersAndItems",
        "reportResult": "ReportResult",
        "detailsData": "DetailsData",
        "reportFormType": "ReportFormType",
        "autoShowState": "AutoShowState",
        "width": "Width",
        "height": "Height",
        "group": "Group",
    }

    def emit_properties(lines, props, indent):
        if not props:
            return

        for p_name, p_value in props.items():
            xml_name = PROP_MAP.get(p_name)
            if not xml_name:
                # Auto PascalCase
                xml_name = p_name[0].upper() + p_name[1:]

            # Convert boolean to lowercase
            if isinstance(p_value, bool):
                val = "true" if p_value else "false"
            else:
                val = str(p_value)
            lines.append(f"{indent}<{xml_name}>{val}</{xml_name}>")

    lines = []

    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        '<Form xmlns="http://v8.1c.ru/8.3/xcf/logform" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:dcscor="http://v8.1c.ru/8.1/data-composition-system/core" xmlns:dcssch="http://v8.1c.ru/8.1/data-composition-system/schema" xmlns:dcsset="http://v8.1c.ru/8.1/data-composition-system/settings" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.17">'
    )

    # Title
    form_title = defn.get("title")
    if not form_title and defn.get("properties") and defn["properties"].get("title"):
        form_title = defn["properties"]["title"]
    if form_title:
        emit_mltext(lines, "\t", "Title", str(form_title))

    # Properties (skip 'title' — handled above)
    if defn.get("properties"):
        props_clone = {k: v for k, v in defn["properties"].items() if k != "title"}
        emit_properties(lines, props_clone, "\t")

    # CommandSet (excluded commands)
    if defn.get("excludedCommands") and len(defn["excludedCommands"]) > 0:
        lines.append("\t<CommandSet>")
        for cmd in defn["excludedCommands"]:
            lines.append(f"\t\t<ExcludedCommand>{cmd}</ExcludedCommand>")
        lines.append("\t</CommandSet>")

    # AutoCommandBar (always present, id=-1)
    lines.append(
        '\t<AutoCommandBar name="\u0424\u043e\u0440\u043c\u0430\u041a\u043e\u043c\u0430\u043d\u0434\u043d\u0430\u044f\u041f\u0430\u043d\u0435\u043b\u044c" id="-1">'
    )
    lines.append("\t\t<HorizontalAlign>Right</HorizontalAlign>")
    lines.append("\t\t<Autofill>false</Autofill>")
    lines.append("\t</AutoCommandBar>")

    # Events
    if defn.get("events") or defn.get("formEvents"):
        lines.append("\t<Events>")
        for evt_name, evt_handler in defn.get("events", {}).items():
            lines.append(f'\t\t<Event name="{evt_name}">{evt_handler}</Event>')
        for event in defn.get("formEvents", []):
            call = f' callType="{event["callType"]}"' if event.get("callType") else ""
            lines.append(f'\t\t<Event name="{event["name"]}"{call}>{event["handler"]}</Event>')
        lines.append("\t</Events>")

    # ChildItems (elements)
    if defn.get("elements") and len(defn["elements"]) > 0:
        lines.append("\t<ChildItems>")
        for el in defn["elements"]:
            emit_element(lines, el, "\t\t")
        lines.append("\t</ChildItems>")

    # Attributes
    emit_attributes(lines, defn.get("attributes"), "\t")

    # Parameters
    emit_parameters(lines, defn.get("parameters"), "\t")

    # Commands
    emit_commands(lines, defn.get("commands"), "\t")

    # Close
    lines.append("</Form>")

    return ("\n".join(lines) + "\n").encode("utf-8-sig")
