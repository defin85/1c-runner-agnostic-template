"""Правка содержимого табличных макетов (SpreadsheetDocument) через metadata (E7–E10).

Правила разметки, сдвига сетки, форматов, печати и импорта .xlsx перенесены на
Python из BslEdit рев. 53ee395 (packages/1c-preview-core/browser/template-markup.js
и xlsx-template.js; MIT, (c) 2026 1c-form-viewer contributors). BslEdit не
вызывается и не является зависимостью.

Проверки локальные: только структура XML и ссылки внутри Template.xml, не
поведение платформы. Регистрация макета у владельца не меняется (D6).
"""

from __future__ import annotations

import codecs
import copy
import io
import json
import math
import re
import zipfile
from decimal import ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path

import lxml.etree as etree

from .metadata_borrow import DIRECTORIES

SS = "http://v8.1c.ru/8.2/data/spreadsheet"
STUB = "http://v8.1c.ru/spreadsheet/document"
V8 = "http://v8.1c.ru/8.1/data/core"
V8UI = "http://v8.1c.ru/8.1/data/ui"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
MD = "http://v8.1c.ru/8.3/MDClasses"
BOM = codecs.BOM_UTF8
PREFIXES = {"v8": V8, "v8ui": V8UI, "xsi": XSI}

TEMPLATE_KINDS = (
    "SpreadsheetDocument",
    "DataCompositionSchema",
    "DataCompositionAppearanceTemplate",
    "TextDocument",
    "BinaryData",
    "HTMLDocument",
    "GraphicalSchema",
    "AddIn",
    "ActiveDocument",
    "GeographicalSchema",
)
OWNER_KINDS = (
    "Catalog",
    "Document",
    "Enum",
    "ExchangePlan",
    "Report",
    "DataProcessor",
    "InformationRegister",
    "AccumulationRegister",
    "ChartOfCharacteristicTypes",
    "ChartOfAccounts",
    "AccountingRegister",
    "ChartOfCalculationTypes",
    "CalculationRegister",
    "BusinessProcess",
    "Task",
    "DocumentJournal",
)
EXTERNAL_KINDS = ("ExternalDataProcessor", "ExternalReport")

XLSX_ENTRY_LIMIT = 32 * 1024 * 1024
XLSX_TOTAL_LIMIT = 64 * 1024 * 1024
XLSX_ENTRIES = 10000
GRID_LIMIT = 1_000_000


def _editor():
    from . import metadata

    return metadata


def _require(condition, message, code=2):
    # Messages of this module are fixed literals; the CLI shows them as the reason.
    if not condition:
        raise _editor().FixedRejected(message, code)


# ---------------------------------------------------------------- parameters

_POS = {"type": "integer", "minimum": 1, "maximum": GRID_LIMIT}
_TEXT = {"type": "string", "maxLength": 65536, "not": {"pattern": "[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f]"}}
_IDENT = {"type": "string", "maxLength": 128, "not": {"pattern": "[\\x00-\\x1f]"}}
_COLOR = {
    "anyOf": [
        {"type": "string", "pattern": "^\\s*(#[0-9a-fA-F]{6}|(style|web|win):[A-Za-zА-Яа-яЁё0-9_]+)\\s*$"},
        {"type": "null"},
    ]
}
_FONT = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "face": {"type": "string", "minLength": 1, "maxLength": 128, "not": {"pattern": '[\\x00-\\x1f"]'}},
        "size": {"type": "number", "exclusiveMinimum": 0, "maximum": 1000},
        "bold": {"type": "boolean"},
        "italic": {"type": "boolean"},
        "underline": {"type": "boolean"},
        "strikeout": {"type": "boolean"},
    },
}
LINE_STYLES = ("None", "Solid", "Dotted", "Double", "ThinDashed", "ThickDashed", "LargeDashed")
_BORDER = {
    "anyOf": [
        {"type": "string", "enum": list(LINE_STYLES)},
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["style"],
            "properties": {
                "style": {"type": "string", "enum": list(LINE_STYLES)},
                "width": {"type": "integer", "minimum": 1, "maximum": 20},
            },
        },
        {"type": "null"},
    ]
}
_MM = {"type": "number", "minimum": 0, "maximum": 1000}


def _closed(properties, required=()):
    return {"type": "object", "properties": properties, "additionalProperties": False, "required": list(required)}


PARAMETER_SCHEMAS = {
    "template.set-area": _closed(
        {
            "name": _IDENT,
            "beginRow": _POS,
            "endRow": _POS,
            "beginColumn": _POS,
            "endColumn": _POS,
            "remove": {"type": "boolean"},
        },
        ("name",),
    ),
    "template.set-parameter": _closed(
        {"row": _POS, "column": _POS, "name": _IDENT, "template": _TEXT, "text": _TEXT, "detail": _IDENT},
        ("row", "column"),
    ),
    "template.set-format": _closed(
        {
            "row": _POS,
            "column": _POS,
            "toRow": _POS,
            "toColumn": _POS,
            "font": {"anyOf": [_FONT, {"type": "null"}]},
            "horizontalAlignment": {"enum": ["Left", "Center", "Right", "Justify", "Auto", None]},
            "verticalAlignment": {"enum": ["Top", "Center", "Bottom", None]},
            "textPlacement": {"enum": ["Auto", "Wrap", "Cut", "Block", None]},
            "indent": {"anyOf": [{"type": "integer", "minimum": 0, "maximum": 1000}, {"type": "null"}]},
            "textColor": _COLOR,
            "backColor": _COLOR,
            "borderColor": _COLOR,
            "border": _BORDER,
            "leftBorder": _BORDER,
            "topBorder": _BORDER,
            "rightBorder": _BORDER,
            "bottomBorder": _BORDER,
            "format": {"anyOf": [_TEXT, {"type": "null"}]},
            "protection": {"type": "boolean"},
        },
        ("row", "column"),
    ),
    "template.insert-rows": _closed({"at": _POS, "count": _POS}, ("at",)),
    "template.delete-rows": _closed({"at": _POS, "count": _POS}, ("at",)),
    "template.insert-columns": _closed({"at": _POS, "count": _POS, "columnsId": _IDENT}, ("at",)),
    "template.delete-columns": _closed({"at": _POS, "count": _POS, "columnsId": _IDENT}, ("at",)),
    "template.merge-cells": _closed(
        {"row": _POS, "column": _POS, "rows": _POS, "columns": _POS, "unmerge": {"type": "boolean"}}, ("row", "column")
    ),
    "template.set-size": _closed(
        {
            "column": _POS,
            "toColumn": _POS,
            "width": {"type": "number", "minimum": 0, "maximum": 100000},
            "columnsId": _IDENT,
            "row": _POS,
            "toRow": _POS,
            "height": {"type": "number", "minimum": 0, "maximum": 100000},
        }
    ),
    "template.set-print-settings": _closed(
        {
            "orientation": {"enum": ["Portrait", "Landscape"]},
            "scale": {"type": "integer", "minimum": 10, "maximum": 400},
            "fitToPage": {"type": "boolean"},
            "blackAndWhite": {"type": "boolean"},
            "paper": {"type": "integer", "minimum": 0, "maximum": GRID_LIMIT},
            "copies": {"type": "integer", "minimum": 0, "maximum": GRID_LIMIT},
            "firstPageNumber": {"type": "integer", "minimum": 0, "maximum": GRID_LIMIT},
            "topMargin": _MM,
            "leftMargin": _MM,
            "bottomMargin": _MM,
            "rightMargin": _MM,
            "headerSize": _MM,
            "footerSize": _MM,
            "printArea": {
                "anyOf": [
                    {"type": "null"},
                    _closed({"beginRow": _POS, "endRow": _POS, "beginColumn": _POS, "endColumn": _POS}, ("beginRow",)),
                ]
            },
        }
    ),
    "template.set-header-footer": _closed(
        {
            "kind": {"enum": ["header", "footer"]},
            "left": _TEXT,
            "center": _TEXT,
            "right": _TEXT,
            "font": _FONT,
            "remove": {"type": "boolean"},
        },
        ("kind",),
    ),
    "template.import-xlsx": _closed(
        {
            "xlsx": {
                "type": "string",
                "minLength": 1,
                "maxLength": 4096,
                "pattern": "(?i)\\.xlsx$",
                "not": {"pattern": "[\\x00-\\x1f]"},
            },
            "sheet": {
                "anyOf": [
                    {"type": "string", "minLength": 1, "maxLength": 256, "not": {"pattern": "[\\x00-\\x1f]"}},
                    {"type": "integer", "minimum": 0, "maximum": 10000},
                ]
            },
            "replace": {"type": "boolean"},
        },
        ("xlsx",),
    ),
}


# ---------------------------------------------------------------- JS number semantics


def js_str(value) -> str:
    """String(value) for booleans and numbers as JavaScript prints them."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        if value == 0:
            return "0"
        sign = "-" if value < 0 else ""
        digits, exponent = _shortest(abs(value))
        k = len(digits)
        n = exponent
        if k <= n <= 21:
            return sign + digits + "0" * (n - k)
        if 0 < n <= 21:
            return sign + digits[:n] + "." + digits[n:]
        if -6 < n <= 0:
            return sign + "0." + "0" * (-n) + digits
        mantissa = digits[0] + ("." + digits[1:] if k > 1 else "")
        return sign + mantissa + "e" + ("+" if n - 1 >= 0 else "-") + str(abs(n - 1))
    return str(value)


def _shortest(value: float) -> tuple[str, int]:
    """Shortest round-trip digits d and n with value = 0.d × 10**n."""
    _, digits, exponent = Decimal(repr(value)).as_tuple()
    if not isinstance(exponent, int):
        raise TypeError("finite value required")
    text = "".join(map(str, digits))
    n = len(text) + exponent
    return text.rstrip("0") or "0", n


def js_number(text) -> float:
    """Number(text) / unary plus for attribute strings."""
    if text is None:
        return 0.0
    value = str(text).strip()
    if value == "":
        return 0.0
    try:
        if re.fullmatch(r"[+-]?(\d+\.?\d*([eE][+-]?\d+)?|\.\d+([eE][+-]?\d+)?)", value):
            return float(value)
        if re.fullmatch(r"0[xX][0-9a-fA-F]+", value):
            return float(int(value, 16))
    except (ValueError, OverflowError):
        pass
    if value in ("Infinity", "+Infinity"):
        return math.inf
    if value == "-Infinity":
        return -math.inf
    return math.nan


def js_parse_float(text) -> float:
    match = re.match(r"\s*([+-]?(\d+\.?\d*([eE][+-]?\d+)?|\.\d+([eE][+-]?\d+)?|Infinity))", str(text or ""))
    if not match:
        return math.nan
    return float(match.group(1).replace("Infinity", "inf"))


def js_round(value: float) -> float:
    if math.isnan(value) or math.isinf(value):
        return value
    return float(math.floor(value + 0.5))


def js_int(value: float):
    """Integer-valued numbers print without a fraction (as in JS)."""
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e21:
        return int(value)
    return value


def js_to_fixed(value: float, digits: int) -> str:
    if abs(value) >= 1e21 or math.isnan(value):
        return js_str(value)
    sign = "-" if value < 0 else ""
    quantum = Decimal(1).scaleb(-digits)
    with localcontext() as context:
        context.prec = 400
        text = format(Decimal(abs(value)).quantize(quantum, rounding=ROUND_HALF_UP), "f")
    return sign + text


def js_to_precision(value: float, precision: int) -> float:
    if value == 0 or math.isnan(value) or math.isinf(value):
        return value
    with localcontext() as context:
        context.prec = precision
        context.rounding = ROUND_HALF_UP
        return float(+Decimal(value))


def at(items, index):
    if isinstance(index, float):
        if math.isnan(index) or not index.is_integer():
            return None
        index = int(index)
    if isinstance(index, int) and 0 <= index < len(items):
        return items[index]
    return None


# ---------------------------------------------------------------- tree helpers


def ln(el) -> str:
    return el.tag.rpartition("}")[2] if isinstance(el.tag, str) else ""


def kid(el, name):
    if el is None:
        return None
    for child in el:
        if ln(child) == name:
            return child
    return None


def kids(el, name):
    return [child for child in el if ln(child) == name] if el is not None else []


def txt(el) -> str:
    return "" if el is None else (el.text or "")


def int_of(el, default):
    """parseInt(el.text, 10) with a default for absent or non-numeric text."""
    if el is None:
        return default
    match = re.match(r"\s*([+-]?\d+)", el.text or "")
    return int(match.group(1)) if match else default


TOKEN = re.compile(
    r'<(/?)([A-Za-z_][\w.:\-]*)((?:\s+[^\s=/>]+\s*=\s*(?:"[^"]*"|\'[^\']*\'))*)\s*(/?)>'
    r"|<!\[CDATA\[.*?\]\]>|<!--.*?-->|<\?.*?\?>|<![^>]*>|[^<]+",
    re.S,
)


def _escape_text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\r", "&#13;")


def _escape_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\t", "&#9;")
        .replace("\n", "&#10;")
        .replace("\r", "&#13;")
    )


class Template:
    """Template.xml as an lxml tree that reproduces untouched bytes exactly.

    Unchanged start tags, text and whitespace are taken from the source; new or
    changed nodes are written in the Designer layout (tab indentation, file EOL
    between elements, LF kept inside text values).
    """

    def __init__(self, data: bytes, *, allow_stub=False):
        editor = _editor()
        self.bom = data.startswith(BOM)
        try:
            source = data[len(BOM) if self.bom else 0 :].decode("utf-8")
        except UnicodeDecodeError:
            raise editor.FixedRejected("Invalid template encoding") from None
        parser = etree.XMLParser(
            load_dtd=False,
            resolve_entities=False,
            no_network=True,
            huge_tree=False,
            remove_blank_text=False,
            strip_cdata=False,
            remove_comments=False,
        )
        try:
            root = etree.fromstring(data, parser)
        except (etree.XMLSyntaxError, ValueError):
            raise editor.FixedRejected("Invalid XML") from None
        _require(
            not root.getroottree().docinfo.internalDTD and not root.getroottree().docinfo.doctype,
            "DTD/entities are unsupported",
        )
        self.stub = root.tag == f"{{{STUB}}}SpreadsheetDocument"
        # template-add leaves an empty <SpreadsheetDocument/> without a grid; BslEdit edits only
        # <document>, and inventing the empty grid is not supported: import-xlsx builds a whole one.
        _require(
            not self.stub or allow_stub,
            "Template is an empty stub without cells; fill it first with template.import-xlsx",
            3,
        )
        _require(root.tag == f"{{{SS}}}document" or self.stub, "Template is not an editable spreadsheet document")
        self.root = root
        self.eol = "\r\n" if re.match(r"[^\n]*\r\n", source) else "\n"
        self.fresh: set = set()
        self.raw: dict = {}
        elements = list(root.iter())
        _require(all(isinstance(el.tag, str) for el in elements), "Unsupported template serialization")
        index = 0
        stack = []
        buffer = []
        slot = None
        self.prolog = ""
        self.epilog = ""
        for match in TOKEN.finditer(source):
            token = match.group(0)
            name = match.group(2)
            if name:
                self._flush(slot, buffer)
                buffer = []
                if match.group(1):
                    _require(stack, "Unsupported template serialization")
                    element = stack.pop()
                    _require(token == f"</{self.qname(element)}>", "Unsupported template serialization")
                    self.raw[element]["end"] = token
                    slot = (element, "tail") if stack else ("epilog", None)
                    continue
                _require(index < len(elements), "Unsupported template serialization")
                element = elements[index]
                index += 1
                _require(name == self.qname(element), "Unsupported template serialization")
                empty = bool(match.group(4))
                self.raw[element] = {
                    "tag": element.tag,
                    "attrib": list(element.attrib.items()),
                    "start": token,
                    "empty": empty,
                    "end": None,
                    "text": None,
                    "textValue": element.text,
                    "tail": None,
                    "tailValue": element.tail,
                }
                if empty:
                    self.raw[element]["text"] = ""
                    slot = (element, "tail") if stack else ("epilog", None)
                else:
                    stack.append(element)
                    slot = (element, "text")
            elif (
                token.startswith("<!--")
                or token.startswith("<?")
                or (token.startswith("<!") and not token.startswith("<![CDATA["))
            ):
                _require(slot is None or slot[0] == "epilog", "Unsupported template serialization")
                buffer.append(token)
            else:
                buffer.append(token)
        self._flush(slot, buffer)
        _require(index == len(elements) and not stack, "Unsupported template serialization")
        _require(self.dump() == data, "Unsupported template serialization")

    def _flush(self, slot, buffer):
        value = "".join(buffer)
        if slot is None:
            self.prolog += value
        elif slot[0] == "epilog":
            self.epilog += value
        else:
            element, kind = slot
            self.raw[element][kind] = value

    @staticmethod
    def qname(element) -> str:
        local = ln(element)
        return f"{element.prefix}:{local}" if element.prefix else local

    # -- building

    def node(self, tag: str, text=None, children=()):
        prefix, _, local = tag.rpartition(":")
        namespace = PREFIXES[prefix] if prefix else SS
        _require(self.root.nsmap.get(prefix or None) == namespace, "Template lacks a required XML namespace")
        element = etree.Element(f"{{{namespace}}}{local}", nsmap=self.root.nsmap)
        if text is not None:
            element.text = js_str(text) if not isinstance(text, str) else text
        for child in children:
            element.append(child)
        self.fresh.add(element)
        return element

    def depth(self, element) -> int | None:
        depth = 0
        while element is not self.root:
            element = element.getparent()
            if element is None:
                return None
            depth += 1
        return depth

    def indent(self, element, depth: int) -> None:
        children = list(element)
        if not children:
            return
        element.text = "\n" + "\t" * (depth + 1)
        for child in children:
            child.tail = "\n" + "\t" * (depth + 1)
            self.indent(child, depth + 1)
        children[-1].tail = "\n" + "\t" * depth

    def insert(self, parent, index: int, element, depth: int | None = None) -> None:
        if depth is None:
            depth = self.depth(parent)
            if depth is None:
                # A fresh subtree is indented as a whole when it is attached.
                _require(parent in self.fresh, "Detached template parent")
                parent.insert(index, element)
                self.fresh.add(element)
                return
        if element in self.fresh:
            self.indent(element, depth + 1)
        existing = list(parent)
        if not existing:
            parent.text = "\n" + "\t" * (depth + 1)
            element.tail = "\n" + "\t" * depth
            parent.append(element)
        elif index >= len(existing):
            last = existing[-1]
            element.tail = last.tail
            last.tail = "\n" + "\t" * (depth + 1)
            parent.append(element)
        else:
            element.tail = "\n" + "\t" * (depth + 1)
            parent.insert(index, element)

    def append(self, parent, element, depth=None):
        self.insert(parent, len(parent), element, depth)

    def remove(self, element) -> None:
        parent = element.getparent()
        previous = element.getprevious()
        if previous is not None:
            previous.tail = element.tail
        elif len(parent) == 1:
            parent.text = None
        parent.remove(element)

    def replace(self, old, new) -> None:
        parent = old.getparent()
        self.insert(parent, parent.index(old), new)
        self.remove(old)

    # -- serialization

    def dump(self) -> bytes:
        out = [self.prolog]
        self._emit(self.root, out, None)
        out.append(self.epilog)
        return (BOM if self.bom else b"") + "".join(out).encode("utf-8")

    def _chars(self, element, kind: str) -> str:
        value = getattr(element, kind)
        record = self.raw.get(element)
        if record is not None and record[kind] is not None and value == record[kind + "Value"]:
            return record[kind]
        if not value:
            return ""
        if value.strip(" \t\r\n") == "":
            return value.replace("\r\n", "\n").replace("\n", self.eol)
        return _escape_text(value)

    def _start(self, element, parent_map) -> str:
        parts = ["<" + self.qname(element)]
        scope = element.nsmap
        for prefix, uri in scope.items():
            if (parent_map or {}).get(prefix) != uri:
                parts.append(f' xmlns:{prefix}="{_escape_attr(uri)}"' if prefix else f' xmlns="{_escape_attr(uri)}"')
        for key, value in element.attrib.items():
            if key.startswith("{"):
                uri, _, local = key[1:].partition("}")
                prefixes = [p for p, u in scope.items() if u == uri and p]
                _require(prefixes, "Unsupported template serialization")
                key = prefixes[0] + ":" + local
            parts.append(f' {key}="{_escape_attr(value)}"')
        return "".join(parts)

    def _emit(self, element, out, parent_map) -> None:
        _require(isinstance(element.tag, str), "Unsupported template serialization")
        record = self.raw.get(element)
        same = record is not None and record["tag"] == element.tag and record["attrib"] == list(element.attrib.items())
        children = list(element)
        qname = self.qname(element)
        text = self._chars(element, "text")
        if same and record is not None and record["empty"] and not children and not text:
            out.append(record["start"])
            return
        if same and record is not None and not record["empty"]:
            out.append(record["start"])
        else:
            start = self._start(element, parent_map)
            if not children and not text:
                out.append(start + "/>")
                return
            out.append(start + ">")
        out.append(text)
        scope = element.nsmap
        for child in children:
            self._emit(child, out, scope)
            out.append(self._chars(child, "tail"))
        out.append(record["end"] if same and record is not None and record["end"] else f"</{qname}>")


# ---------------------------------------------------------------- target resolution


def resolve(snapshot, target: str) -> dict:
    """Registered SpreadsheetDocument template by exact logical target (no guessing)."""
    editor = _editor()
    from . import metadata_borrow as borrow

    _require(isinstance(target, str) and len(target) <= 512, "Invalid template target")
    parts = target.split(".")
    _require(all(editor.NAME.fullmatch(part) for part in parts), "Invalid template target")
    if len(parts) == 2 and parts[0] == "CommonTemplate":
        name = parts[1]
        config, _ = borrow._checked(snapshot, "target", "Configuration.xml", "Configuration")
        _require(borrow._linked(borrow._registrations(config), "CommonTemplate", name), "Template is not registered")
        base = f"CommonTemplates/{name}"
        child_kind = "CommonTemplate"
    elif len(parts) == 4 and parts[2] == "Template":
        kind, owner_name, _, name = parts
        if kind in EXTERNAL_KINDS:
            root = editor.xml_read(snapshot.get("target", owner_name + ".xml"), f"{{{MD}}}MetaDataObject")
            _require(root.get("version") in {"2.17", "2.20"}, "Unsupported metadata version")
            nodes = [node for node in root if isinstance(node.tag, str)]
            _require(len(nodes) == 1 and nodes[0].tag == f"{{{MD}}}{kind}", "External object kind mismatch")
            owner = nodes[0]
            editor.identity(owner)
            _require(editor.node_name(owner) == owner_name, "Owner metadata name mismatch")
            base = f"{owner_name}/Templates/{name}"
        else:
            _require(kind in OWNER_KINDS, "Unsupported template owner")
            config, _ = borrow._checked(snapshot, "target", "Configuration.xml", "Configuration")
            _require(borrow._linked(borrow._registrations(config), kind, owner_name), "Owner is not registered")
            owner, _ = borrow._checked(snapshot, "target", f"{DIRECTORIES[kind]}/{owner_name}.xml", kind)
            _require(editor.node_name(owner) == owner_name, "Owner metadata name mismatch")
            base = f"{DIRECTORIES[kind]}/{owner_name}/Templates/{name}"
        containers = owner.findall(f"{{{MD}}}ChildObjects")
        _require(len(containers) == 1, "Template is not registered")
        _require(borrow._linked(containers[0], "Template", name), "Template is not registered")
        child_kind = "Template"
    else:
        raise editor.FixedRejected("Expected exact template target")
    descriptor_path = base + ".xml"
    descriptor, _ = borrow._checked(snapshot, "target", descriptor_path, child_kind)
    _require(editor.node_name(descriptor) == name, "Template name mismatch")
    _require(editor.prop(descriptor, "ObjectBelonging") in {"", "Native"}, "Borrowed templates are not editable")
    kind_value = editor.prop(descriptor, "TemplateType")
    if kind_value != "SpreadsheetDocument":
        raise editor.TemplateKindRejected(kind_value)
    return {
        "path": base + "/Ext/Template.xml",
        "descriptor": descriptor_path,
        "name": name,
        "uuid": editor.identity(descriptor),
    }


# ---------------------------------------------------------------- markup model

FORMAT_ORDER = [
    "font",
    "leftBorder",
    "topBorder",
    "rightBorder",
    "bottomBorder",
    "border",
    "borderColor",
    "height",
    "width",
    "widthWeightFactor",
    "horizontalAlignment",
    "drawingBorder",
    "verticalAlignment",
    "textColor",
    "backColor",
    "patternColor",
    "pattern",
    "textPlacement",
    "fillType",
    "protection",
    "hidden",
    "textOrientation",
    "detailsUse",
    "bySelectedColumns",
    "markNegatives",
    "containsValue",
    "valueType",
    "format",
    "hyperLink",
    "picIndex",
    "controlType",
    "autoMarkIncomplete",
    "markIncomplete",
    "indent",
    "autoIndent",
    "editFormat",
    "columnSizeChange",
    "mask",
    "pictureSizeMode",
    "picHorizontalAlignment",
    "picVerticalAlignment",
    "textPosition",
    "leftMargin",
    "topMargin",
    "rightMargin",
    "bottomMargin",
]
# Document children in the order Designer writes them (derived from every
# SpreadsheetDocument template of the project configuration; BslEdit's
# TAIL_ORDER puts printSettings before printArea and picture last, which real
# files never do).
DOC_ORDER = [
    "languageSettings",
    "columns",
    "rowsItem",
    "drawing",
    "leftHeader",
    "stepDirection",
    "centerHeader",
    "rightHeader",
    "leftFooter",
    "centerFooter",
    "rightFooter",
    "templateMode",
    "verticalPageBreak",
    "defaultFormatIndex",
    "repeatRows",
    "height",
    "vgLevels",
    "groupsBackColor",
    "vg",
    "vgRows",
    "groupsColor",
    "headersBackColor",
    "horizontalUnmerge",
    "headersColor",
    "merge",
    "verticalUnmerge",
    "namedItem",
    "printArea",
    "printSettings",
    "picture",
    "line",
    "font",
    "format",
]
PRINT_ORDER = [
    "pageOrientation",
    "scale",
    "collate",
    "copies",
    "perPage",
    "topMargin",
    "leftMargin",
    "bottomMargin",
    "rightMargin",
    "headerSize",
    "footerSize",
    "fitToPage",
    "blackAndWhite",
    "printerName",
    "paper",
    "paperSource",
    "pageWidth",
    "pageHeight",
    "duplexType",
    "pagePlacementAlternation",
    "firstPageNumber",
]
NAME_RE = re.compile(r"[A-Za-zА-Яа-яЁё_][0-9A-Za-zА-Яа-яЁё_]*\Z")


def valid_name(name: str) -> bool:
    return bool(NAME_RE.match(name or ""))


def language(doc) -> str:
    current = kid(kid(doc, "languageSettings"), "defaultLanguage")
    return current.text if current is not None and current.text else "ru"


def localized(tl, lang: str) -> str:
    items = kids(tl, "item")
    pick = next(
        (item for item in items if (item_lang := kid(item, "lang")) is not None and item_lang.text == lang),
        items[0] if items else None,
    )
    content = kid(pick, "content")
    return txt(content)


def template_names(text: str) -> list:
    out = []
    for match in re.finditer(r"\[([^\[\]]+)\]", text or ""):
        name = match.group(1).strip()
        if not re.fullmatch(r"\d+", name) and not name.startswith("&") and name not in out:
            out.append(name)
    return out


def row_cells(row) -> list:
    out = []
    col = 0
    for group in kids(row, "c"):
        index = kid(group, "i")
        if index is not None:
            col = int_of(index, col)
        out.append({"col": col, "group": group})
        col += 1
    return out


def column_count(doc) -> int:
    return max([int_of(kid(item, "size"), 0) for item in kids(doc, "columns")] + [0])


def format_at(formats, index):
    return formats[index - 1] if isinstance(index, int) and 0 < index <= len(formats) else None


def markup(doc) -> dict:
    """listMarkup: areas, parameters, template texts, intersections, print settings (1-based)."""
    formats = kids(doc, "format")
    lang = language(doc)
    result = {
        "rows": int_of(kid(doc, "height"), 0),
        "columns": column_count(doc),
        "areas": [],
        "parameters": [],
        "templates": [],
        "intersections": [],
    }
    sets = kids(doc, "columns")
    if len(sets) > 1:
        result["columnSets"] = [{"id": txt(kid(item, "id")), "size": int_of(kid(item, "size"), 0)} for item in sets]
    for item in kids(doc, "namedItem"):
        area = kid(item, "area")
        entry: dict | None = {"name": txt(kid(item, "name"))}
        if area is None:
            entry["type"] = "Drawing"
            result["areas"].append(entry)
            continue
        entry["type"] = txt(kid(area, "type")) if kid(area, "type") is not None else "Rows"
        begin_row, end_row = int_of(kid(area, "beginRow"), -1), int_of(kid(area, "endRow"), -1)
        begin_col, end_col = int_of(kid(area, "beginColumn"), -1), int_of(kid(area, "endColumn"), -1)
        if begin_row >= 0:
            entry["beginRow"], entry["endRow"] = begin_row + 1, end_row + 1
        if begin_col >= 0:
            entry["beginColumn"], entry["endColumn"] = begin_col + 1, end_col + 1
        result["areas"].append(entry)
    result["areas"].sort(key=lambda a: (a.get("beginRow", math.inf), a.get("beginColumn") or 0))

    def areas_at(row, column):
        names = []
        for area in result["areas"]:
            if area["type"] == "Drawing":
                continue
            in_rows = "beginRow" not in area or area["beginRow"] <= row <= area["endRow"]
            in_cols = "beginColumn" not in area or area["beginColumn"] <= column <= area["endColumn"]
            if in_rows and in_cols and area["type"] != "Columns":
                names.append(area["name"])
        return names

    for item in kids(doc, "rowsItem"):
        row_index = int_of(kid(item, "index"), 0)
        row = kid(item, "row")
        for cell in row_cells(row) if row is not None else []:
            content = kid(cell["group"], "c")
            if content is None:
                continue
            fmt = format_at(formats, int_of(kid(content, "f"), 0))
            fill = txt(kid(fmt, "fillType")) if fmt is not None else ""
            parameter = kid(content, "parameter")
            detail = kid(content, "detailParameter")
            entry = None
            where = {"row": row_index + 1, "column": cell["col"] + 1}
            if fill == "Parameter" or parameter is not None:
                entry = {**where, "name": txt(parameter)}
                result["parameters"].append(entry)
            elif fill == "Template":
                text = localized(kid(content, "tl"), lang)
                entry = {**where, "text": text, "names": template_names(text)}
                result["templates"].append(entry)
            elif detail is not None:
                entry = {**where, "name": ""}
                result["parameters"].append(entry)
            if entry is None:
                continue
            if detail is not None and detail.text:
                entry["detail"] = detail.text
            owners = areas_at(where["row"], where["column"])
            if owners:
                entry["areas"] = owners
    for area in result["areas"]:
        if area["type"] in ("Drawing", "Columns"):
            continue
        names = []
        for parameter in result["parameters"]:
            if area["name"] in parameter.get("areas", []) and parameter["name"] and parameter["name"] not in names:
                names.append(parameter["name"])
        for template in result["templates"]:
            if area["name"] in template.get("areas", []):
                names.extend(name for name in template["names"] if name not in names)
        area["parameters"] = names
    settings, print_area = kid(doc, "printSettings"), kid(doc, "printArea")
    printing: dict[str, dict] = {}
    if settings is not None:
        printing["settings"] = {
            ln(child): txt(child) for child in settings if isinstance(child.tag, str) and ln(child) != "printerName"
        }
    if print_area is not None:
        printing["area"] = {"type": txt(kid(print_area, "type"))}
        if int_of(kid(print_area, "beginRow"), -1) >= 0:
            printing["area"]["beginRow"] = int_of(kid(print_area, "beginRow"), 0) + 1
            printing["area"]["endRow"] = int_of(kid(print_area, "endRow"), 0) + 1
        if int_of(kid(print_area, "beginColumn"), -1) >= 0:
            printing["area"]["beginColumn"] = int_of(kid(print_area, "beginColumn"), 0) + 1
            printing["area"]["endColumn"] = int_of(kid(print_area, "endColumn"), 0) + 1
    for kind in ("Header", "Footer"):
        texts = {}
        for slot in ("left", "center", "right"):
            element = kid(doc, slot + kind)
            text = localized(kid(element, "tl"), lang) if element is not None else ""
            if text:
                texts[slot] = text
        if texts:
            printing[kind.lower()] = texts
    if printing:
        result["print"] = printing
    for rows in (a for a in result["areas"] if a["type"] == "Rows"):
        for columns in (a for a in result["areas"] if a["type"] == "Columns"):
            result["intersections"].append(rows["name"] + "|" + columns["name"])
    return result


def merge_rect(merge) -> dict:
    return {
        "r": int_of(kid(merge, "r"), 0),
        "c": int_of(kid(merge, "c"), 0),
        "h": int_of(kid(merge, "h"), 0),
        "w": int_of(kid(merge, "w"), 0),
    }


def row_column_sets(doc) -> dict:
    """Row index -> columnsID of that row ('' for the default set)."""
    result = {}
    for item in kids(doc, "rowsItem"):
        row = kid(item, "row")
        first = int_of(kid(item, "index"), 0)
        last = int_of(kid(item, "indexTo"), first) if kid(item, "indexTo") is not None else first
        row_id = txt(kid(row, "columnsID")) if row is not None else ""
        for index in range(first, min(last, first + 99999) + 1):
            result[index] = row_id
    return result


def merge_set(merge, row_sets) -> str:
    """A merge without columnsID uses the column set of the row it starts on."""
    if kid(merge, "columnsID") is not None:
        return txt(kid(merge, "columnsID"))
    return row_sets.get(int_of(kid(merge, "r"), 0), "")


def validate(doc) -> tuple[list, list]:
    """validateTemplate without the grid bounds that Designer exports contradict.

    Kept (BslEdit validateTemplate): references to formats, fonts, lines, pictures and
    column sets; row order; area types and names; negative sizes and positions.
    Dropped, because unchanged Designer exports of a typical BP 3.0 configuration contain them
    (see tests/python/test_metadata_template_designer_exports.py):
    - rows, merges, drawings and print area past <height>, and a missing <height>;
    - columns, cells and merges past the column set size, size 0 and columnsItem index -1;
    - areas with reversed or out-of-grid bounds (Designer keeps them after edits);
    - overlapping merges, nameless parameter cells, templates without [Имя] and
      parameter names that are not identifiers.
    """
    errors, warnings = [], []
    formats = kids(doc, "format")
    fonts = len(kids(doc, "font"))
    lines = len(kids(doc, "line"))
    pictures = len(kids(doc, "picture"))
    height_el = kid(doc, "height")
    height = int_of(height_el, -1) if height_el is not None else 0
    if height < 0:
        errors.append("Неверная высота документа <height>.")
    vg_rows = kid(doc, "vgRows")
    if vg_rows is not None and int_of(vg_rows, 0) > height:
        warnings.append(f"vgRows ({txt(vg_rows)}) больше height ({height}).")

    def check_format(index, where):
        if index is None:
            return
        if not 0 <= index <= len(formats):
            errors.append(f"{where}: формат {index} не существует (форматов {len(formats)}).")

    sets = set()
    for position, item in enumerate(kids(doc, "columns")):
        set_id = txt(kid(item, "id"))
        label = f"Набор колонок {set_id or 'по умолчанию'}"
        if set_id in sets:
            errors.append(f"{label} объявлен дважды.")
        if int_of(kid(item, "size"), 0 if kid(item, "size") is None else -1) < 0:
            errors.append(f"{label}: неверный size.")
        sets.add(set_id)
        if position == 0:
            sets.add("")
        for column in kids(item, "columnsItem"):
            # Designer writes index -1 for the set's own column format (ПФ_MXL_ФормаСЗВ_ИСХ).
            index = int_of(kid(column, "index"), -2)
            if index < -1:
                errors.append(f"{label}: неверный индекс колонки.")
            body = kid(column, "column")
            if body is not None and kid(body, "formatIndex") is not None:
                check_format(int_of(kid(body, "formatIndex"), -1), f"Колонка {index + 1}")

    def check_set(set_id, where):
        if (set_id or "") not in sets:
            errors.append(f"{where}: нет набора колонок {set_id}.")

    if kid(doc, "defaultFormatIndex") is not None:
        check_format(int_of(kid(doc, "defaultFormatIndex"), -1), "defaultFormatIndex")
    last_index = -1
    for item in kids(doc, "rowsItem"):
        first = int_of(kid(item, "index"), -1)
        last = int_of(kid(item, "indexTo"), -1) if kid(item, "indexTo") is not None else first
        label = f"Строка {first + 1}"
        if first < 0 or last < first:
            errors.append(f"{label}: неверный диапазон index/indexTo.")
            continue
        if first <= last_index:
            errors.append(f"{label}: строки идут не по порядку или повторяются.")
        last_index = last
        row = kid(item, "row")
        if row is None:
            continue
        check_set(txt(kid(row, "columnsID")), label)
        if kid(row, "formatIndex") is not None:
            check_format(int_of(kid(row, "formatIndex"), -1), label)
        for cell in row_cells(row):
            where = f"Ячейка {first + 1}:{cell['col'] + 1}"
            if cell["col"] < 0:
                errors.append(f"{where}: неверный номер колонки.")
            content = kid(cell["group"], "c")
            if content is None:
                continue
            index = int_of(kid(content, "f"), -1) if kid(content, "f") is not None else None
            check_format(index, where)
    for position, fmt in enumerate(formats):
        label = f"Формат {position + 1}"
        font = kid(fmt, "font")
        if font is not None and not 0 <= int_of(font, -1) < fonts:
            errors.append(f"{label}: шрифт {txt(font)} не существует (шрифтов {fonts}).")
        for name in ("border", "leftBorder", "topBorder", "rightBorder", "bottomBorder", "drawingBorder"):
            element = kid(fmt, name)
            if element is not None and not 0 <= int_of(element, -1) < lines:
                errors.append(f"{label}: линия {name}={txt(element)} не существует (линий {lines}).")
    row_sets = row_column_sets(doc)
    for merge in kids(doc, "merge"):
        rect = merge_rect(merge)
        label = f"Объединение {rect['r'] + 1}:{rect['c'] + 1}"
        check_set(merge_set(merge, row_sets), label)
        if rect["h"] < 0 or rect["w"] < 0 or rect["c"] < -1:
            errors.append(f"{label}: неверный размер.")
    names = set()
    for item in kids(doc, "namedItem"):
        name = txt(kid(item, "name"))
        label = f"Область «{name}»"
        if not valid_name(name):
            errors.append(f"{label}: имя не идентификатор 1С.")
        if name in names:
            errors.append(f"{label}: имя повторяется.")
        names.add(name)
        area = kid(item, "area")
        if area is None:
            continue
        kind = txt(kid(area, "type"))
        check_set(txt(kid(area, "columnsID")), label)
        if kind not in ("Rows", "Columns", "Rectangle"):
            errors.append(f"{label}: неизвестный тип {kind}.")
    print_area = kid(doc, "printArea")
    if print_area is not None:
        first, last = int_of(kid(print_area, "beginRow"), -1), int_of(kid(print_area, "endRow"), -1)
        if first >= 0 and last < first:
            errors.append(f"Область печати: неверные строки {first + 1}–{last + 1}.")
    settings = kid(doc, "printSettings")
    if settings is not None and kid(settings, "scale") is not None:
        scale = int_of(kid(settings, "scale"), 0)
        if scale < 10 or scale > 400:
            warnings.append(f"Масштаб печати {scale} вне 10–400.")
    for position, drawing in enumerate(kids(doc, "drawing")):
        label = f"Рисунок {position + 1}"
        if kid(drawing, "formatIndex") is not None:
            check_format(int_of(kid(drawing, "formatIndex"), -1), label)
        picture = kid(drawing, "pictureIndex")
        if picture is not None and not 1 <= int_of(picture, 0) <= pictures:
            errors.append(f"{label}: картинка {txt(picture)} не существует.")
    return errors, warnings


# ---------------------------------------------------------------- inspect / verify

SUPPORTED_OPERATIONS = tuple(PARAMETER_SCHEMAS)


def load(snapshot, target, *, allow_stub=False):
    context = resolve(snapshot, target)
    data = snapshot.read("target", context["path"], optional=True)
    # Earlier steps of the same plan edit the staged candidate, not the source.
    if context["path"] in snapshot.writes:
        data = snapshot.writes[context["path"]]
    _require(data is not None, "Template file is missing")
    template = Template(data, allow_stub=allow_stub)
    return context, template


def inspect(snapshot, target: str) -> dict:
    context, template = load(snapshot, target, allow_stub=True)
    if template.stub:
        layout = {"rows": 0, "columns": 0, "areas": [], "parameters": [], "templates": [], "intersections": []}
    else:
        layout = markup(template.root)
    snapshot.unchanged()
    return {
        "object": target,
        "file": context["path"],
        "uuid": context["uuid"],
        "kind": "SpreadsheetDocument",
        "format": "stub" if template.stub else "document",
        "columnSets": layout.get(
            "columnSets",
            [
                {"id": txt(kid(item, "id")), "size": int_of(kid(item, "size"), 0)}
                for item in kids(template.root, "columns")
            ],
        ),
        "markup": layout,
        "supportedOperations": list(SUPPORTED_OPERATIONS),
        "checks": {"platform": "not-run", "runtime": "not-run"},
    }


def verify_report(snapshot, target: str, *, detailed=False, max_errors=30) -> dict:
    context, template = load(snapshot, target, allow_stub=True)
    lines = [f"=== Validation: Template.{context['name']} ===", ""]
    errors, warnings = ([], []) if template.stub else validate(template.root)
    stopped = len(errors) >= max_errors
    shown_errors = errors[:max_errors]
    lines.extend(f"[ERROR] {message}" for message in shown_errors)
    lines.extend(f"[WARN]  {message}" for message in warnings)
    ok = 0 if errors or warnings else 1
    checks = ok + len(shown_errors) + len(warnings)
    if not shown_errors and not warnings and not detailed:
        lines = [f"=== Validation OK: Template.{context['name']} ({checks} checks) ==="]
    else:
        if detailed and ok:
            lines.append("[OK]    Template structure")
        lines.extend(["", f"=== Result: {len(shown_errors)} errors, {len(warnings)} warnings ({checks} checks) ==="])
    return {"lines": lines, "errors": len(shown_errors), "warnings": len(warnings), "ok": ok, "stopped": stopped}


# ---------------------------------------------------------------- edit operations


class Editor:
    """One operation over a parsed document; mirrors template-markup.js helpers."""

    def __init__(self, template: Template):
        self.t = template
        self.doc = template.root

    def node(self, tag, text=None, children=()):
        return self.t.node(tag, text, children)

    # placement
    def place_in_tail(self, element):
        rank = DOC_ORDER.index(ln(element))
        position = len(self.doc)
        for index, child in enumerate(self.doc):
            if (DOC_ORDER.index(ln(child)) if ln(child) in DOC_ORDER else -1) > rank:
                position = index
                break
        self.t.insert(self.doc, position, element)

    def grow_height(self, rows):
        for name in ("height", "vgRows"):
            element = kid(self.doc, name)
            if element is not None and int_of(element, 0) < rows:
                element.text = str(rows)

    def set_height(self, rows):
        for name in ("height", "vgRows"):
            element = kid(self.doc, name)
            if element is not None:
                element.text = str(max(rows, 1 if name == "height" else 0))

    def column_set_for(self, element):
        sets = kids(self.doc, "columns")
        set_id = txt(kid(element, "columnsID")) if element is not None else ""
        if not set_id:
            return sets[0] if sets else None
        return next((item for item in sets if txt(kid(item, "id")) == set_id), None)

    @staticmethod
    def grow_columns(column_set, columns):
        size = kid(column_set, "size")
        if size is not None and int_of(size, 0) < columns:
            size.text = str(columns)

    def column_set(self, columns_id):
        sets = kids(self.doc, "columns")
        want = columns_id or ""
        found = next((item for item in sets if txt(kid(item, "id")) == want), None)
        if found is None and not want and sets:
            found = sets[0]
        if found is None:
            raise _editor().FixedRejected("Template column set not found", 3)
        return found

    # rows
    def range_item(self, item, first, last):
        clone = copy.deepcopy(item)
        for child in list(clone):
            if ln(child) in ("index", "indexTo"):
                self.t.remove(child)
        self.t.insert(clone, 0, self.node("index", first), depth=1)
        if last != first:
            self.t.insert(clone, 1, self.node("indexTo", last), depth=1)
        return clone

    def item_bounds(self, item):
        first = int_of(kid(item, "index"), 0)
        to = kid(item, "indexTo")
        return first, (int_of(to, first) if to is not None else first)

    def row_for(self, index):
        for item in kids(self.doc, "rowsItem"):
            first = int_of(kid(item, "index"), -1)
            to = kid(item, "indexTo")
            last = int_of(to, first) if to is not None else first
            if index < first or index > last:
                continue
            if first == last:
                row = kid(item, "row")
                if row is None:
                    row = self.node("row")
                    self.t.append(item, row)
                return row
            position = self.doc.index(item)
            pieces = []
            if index > first:
                pieces.append(self.range_item(item, first, index - 1))
            single = self.range_item(item, index, index)
            pieces.append(single)
            if index < last:
                pieces.append(self.range_item(item, index + 1, last))
            for offset, piece in enumerate(pieces):
                self.t.insert(self.doc, position + offset, piece)
            self.t.remove(item)
            return kid(single, "row")
        fresh = self.node("rowsItem", None, [self.node("index", index), self.node("row")])
        after = -1
        for position, child in enumerate(self.doc):
            if ln(child) == "columns":
                after = max(after, position)
            if ln(child) == "rowsItem" and int_of(kid(child, "index"), 0) < index:
                after = position
        self.t.insert(self.doc, after + 1, fresh)
        self.grow_height(index + 1)
        return kid(fresh, "row")

    def write_row_cells(self, row, cells):
        cells.sort(key=lambda cell: cell["col"])
        for child in list(row):
            if ln(child) in ("c", "empty"):
                self.t.remove(child)
        expected = 0
        row_depth = self.t.depth(row)
        for cell in cells:
            group = cell["group"]
            for index in kids(group, "i"):
                self.t.remove(index)
            if cell["col"] != expected:
                if row_depth is None:
                    raise _editor().FixedRejected("Detached template parent")
                self.t.insert(group, 0, self.node("i", cell["col"]), depth=row_depth + 1)
            expected = cell["col"] + 1
            self.t.append(row, group, depth=row_depth)
        if not cells:
            self.t.append(row, self.node("empty", "true"), depth=row_depth)

    def cell(self, cells, col):
        found = next((cell for cell in cells if cell["col"] == col), None)
        if found is None:
            found = {"col": col, "group": self.node("c", None, [self.node("c")])}
            cells.append(found)
        return found

    def content(self, group):
        content = kid(group, "c")
        if content is None:
            content = self.node("c")
            self.t.append(group, content, depth=self._depth_or(group, 3))
        return content

    def _depth_or(self, element, default):
        depth = self.t.depth(element)
        return default if depth is None else depth

    # formats
    @staticmethod
    def canonical(element) -> str:
        def walk(node):
            return (
                node.tag,
                sorted(node.attrib.items()),
                (node.text or "").strip() if not len(node) else "",
                [walk(child) for child in node if isinstance(child.tag, str)],
            )

        return json.dumps(walk(element), ensure_ascii=False)

    def format_with(self, index, changes: dict) -> int:
        formats = kids(self.doc, "format")
        base = format_at(formats, index)
        base = copy.deepcopy(base) if base is not None else self.node("format")
        if base.tail is not None:
            base.tail = None
        self.t.fresh.add(base)
        for descendant in base.iter():
            self.t.fresh.add(descendant)
        for name, value in changes.items():
            for child in kids(base, name):
                base.remove(child)
            if value is None:
                continue
            element = value if isinstance(value, etree._Element) else self.node(name, value)
            rank = FORMAT_ORDER.index(name) if name in FORMAT_ORDER else -1
            position = len(base)
            if rank >= 0:
                for i, child in enumerate(base):
                    other = FORMAT_ORDER.index(ln(child)) if ln(child) in FORMAT_ORDER else -1
                    if other > rank:
                        position = i
                        break
            base.insert(position, element)
        key = self.canonical(base)
        for position, existing in enumerate(formats):
            if self.canonical(existing) == key:
                return position + 1
        self.place_in_tail(base)
        return len(formats) + 1

    def inherited_font(self, row, col, cell_format):
        formats = kids(self.doc, "format")

        def font_of(fmt):
            return int_of(kid(fmt, "font"), -1) if fmt is not None and kid(fmt, "font") is not None else -1

        def by_index(element):
            return format_at(formats, int_of(element, 0) if element is not None else 0)

        row_id = txt(kid(row, "columnsID"))
        column_set = next((item for item in kids(self.doc, "columns") if txt(kid(item, "id")) == row_id), None)
        if column_set is None and not row_id:
            column_set = (kids(self.doc, "columns") or [None])[0]
        column_format = None
        for item in kids(column_set, "columnsItem"):
            if int_of(kid(item, "index"), -1) == col:
                column_format = by_index(kid(kid(item, "column"), "formatIndex"))
        for fmt in (
            cell_format,
            by_index(kid(row, "formatIndex")),
            column_format,
            by_index(kid(self.doc, "defaultFormatIndex")),
        ):
            font = font_of(fmt)
            if font >= 0:
                return font
        return -1

    def font_index(self, base_index, changes) -> int:
        fonts = kids(self.doc, "font")
        base = at(fonts, base_index)

        def attr(name, default):
            return (base.get(name) or default) if base is not None else default

        props = {
            "faceName": attr("faceName", "Arial"),
            "height": attr("height", "8"),
            "bold": attr("bold", "false"),
            "italic": attr("italic", "false"),
            "underline": attr("underline", "false"),
            "strikeout": attr("strikeout", "false"),
            "kind": attr("kind", "Absolute"),
            "scale": attr("scale", "100"),
        }
        if changes.get("face") is not None:
            props["faceName"] = str(changes["face"])
        if changes.get("size") is not None:
            props["height"] = js_str(float(changes["size"]))
        for key in ("bold", "italic", "underline", "strikeout"):
            if changes.get(key) is not None:
                props[key] = "true" if changes[key] else "false"
        order = ["faceName", "height", "bold", "italic", "underline", "strikeout", "kind", "scale"]
        for position, font in enumerate(fonts):
            if all(font.get(key) == props[key] for key in order):
                return position
        element = self.node("font")
        for key in order:
            element.set(key, props[key])
        self.place_in_tail(element)
        return len(fonts)

    def line_index(self, spec) -> int:
        style = spec if isinstance(spec, str) else spec.get("style")
        style = style or "Solid"
        width = spec.get("width", 1) if isinstance(spec, dict) else 1
        lines = kids(self.doc, "line")
        for position, line in enumerate(lines):
            style_el = kid(line, "style")
            kind = style_el.get(f"{{{XSI}}}type", "") if style_el is not None else ""
            if (
                line.get("width") == str(width)
                and line.get("gap") != "true"
                and style_el is not None
                and style_el.text == style
                and "CellLineType" in kind
            ):
                return position
        style_el = self.node("v8ui:style", style)
        style_el.set(f"{{{XSI}}}type", "v8ui:SpreadsheetDocumentCellLineType")
        element = self.node("line", None, [style_el])
        element.set("width", str(width))
        element.set("gap", "false")
        self.place_in_tail(element)
        return len(lines)


def shift_span(begin, extent, position, count):
    end = begin + extent
    if count > 0:
        if begin >= position:
            return begin + count, extent
        if end >= position:
            return begin, extent + count
        return begin, extent
    gone = -count
    last = position + gone - 1
    if end < position:
        return begin, extent
    if begin > last:
        return begin - gone, extent
    kept_before = max(0, position - begin)
    kept_after = max(0, end - last)
    if kept_before + kept_after == 0:
        return None
    return min(begin, position), kept_before + kept_after - 1


def _set_int(element, name, value):
    child = kid(element, name)
    if child is not None:
        child.text = str(value)


def op_set_area(ed: Editor, p: dict) -> dict:
    name = p["name"].strip()
    _require(valid_name(name), "Invalid area name")
    existing = [item for item in kids(ed.doc, "namedItem") if txt(kid(item, "name")) == name]
    if p.get("remove"):
        _require(existing, "Template area not found", 3)
        for item in existing:
            ed.t.remove(item)
        return {"removed": name}
    has_rows = "beginRow" in p or "endRow" in p
    has_cols = "beginColumn" in p or "endColumn" in p
    _require(has_rows or has_cols, "Area rows or columns required")
    begin_row = end_row = begin_col = end_col = -1
    if has_rows:
        begin_row = (p["beginRow"] if "beginRow" in p else p["endRow"]) - 1
        end_row = (p["endRow"] if "endRow" in p else p["beginRow"]) - 1
        _require(end_row >= begin_row, "Area end row precedes begin row")
    if has_cols:
        begin_col = (p["beginColumn"] if "beginColumn" in p else p["endColumn"]) - 1
        end_col = (p["endColumn"] if "endColumn" in p else p["beginColumn"]) - 1
        _require(end_col >= begin_col, "Area end column precedes begin column")
    kind = "Rectangle" if has_rows and has_cols else "Rows" if has_rows else "Columns"
    item = ed.node(
        "namedItem",
        None,
        [
            ed.node("name", name),
            ed.node(
                "area",
                None,
                [
                    ed.node("type", kind),
                    ed.node("beginRow", begin_row),
                    ed.node("endRow", end_row),
                    ed.node("beginColumn", begin_col),
                    ed.node("endColumn", end_col),
                ],
            ),
        ],
    )
    item.set(f"{{{XSI}}}type", "NamedItemCells")
    if existing:
        # Replace in place: the area keeps its position among namedItem nodes.
        ed.t.replace(existing[0], item)
        for duplicate in existing[1:]:
            ed.t.remove(duplicate)
    else:
        ed.place_in_tail(item)
    if has_rows:
        ed.grow_height(end_row + 1)
    if has_cols:
        ed.grow_columns(ed.column_set_for(None), end_col + 1)
    entry = {"name": name, "type": kind}
    if has_rows:
        entry.update(beginRow=begin_row + 1, endRow=end_row + 1)
    if has_cols:
        entry.update(beginColumn=begin_col + 1, endColumn=end_col + 1)
    return {"area": entry, "replaced": bool(existing)}


def with_translation(ed: Editor, tl, lang, value):
    items = kids(tl, "item") if tl is not None else []
    replaced = False
    out = []
    for item in items:
        if replaced or (item_lang := kid(item, "lang")) is None or item_lang.text != lang:
            out.append(item)
            continue
        replaced = True
        out.append(ed.node("v8:item", None, [ed.node("v8:lang", lang), ed.node("v8:content", value)]))
    if not replaced:
        out.insert(0, ed.node("v8:item", None, [ed.node("v8:lang", lang), ed.node("v8:content", value)]))
    return out


def op_set_parameter(ed: Editor, p: dict) -> dict:
    r, c = p["row"] - 1, p["column"] - 1
    has_name, has_template, has_text, has_detail = ("name" in p), ("template" in p), ("text" in p), ("detail" in p)
    name = p.get("name", "").strip()
    detail = p.get("detail", "").strip()
    kinds_given = sum((has_name, has_template, has_text))
    _require(kinds_given <= 1 and (kinds_given or has_detail), "Pass one of name, template or text")
    _require(not name or valid_name(name), "Invalid parameter name")
    _require(not detail or valid_name(detail), "Invalid detail parameter name")
    row = ed.row_for(r)
    cells = row_cells(row)
    cell = ed.cell(cells, c)
    content = ed.content(cell["group"])
    f_el = kid(content, "f")
    lang = language(ed.doc)
    previous = {
        "text": localized(kid(content, "tl"), lang),
        "parameter": txt(kid(content, "parameter")),
        "detail": txt(kid(content, "detailParameter")),
    }
    if kinds_given:
        fill = "Parameter" if has_name else "Template" if has_template else ""
        head = [ed.node("f", ed.format_with(int_of(f_el, 0) if f_el is not None else 0, {"fillType": fill or None}))]
        if has_name:
            if name:
                head.append(ed.node("parameter", name))
        else:
            value = p["template"] if has_template else p["text"]
            if value != "":
                tl = ed.node("tl")
                for item in with_translation(ed, kid(content, "tl"), lang, value):
                    if item.getparent() is not None:
                        item.getparent().remove(item)
                    tl.append(item)
                head.append(tl)
    else:
        head = [child for child in content if ln(child) in ("f", "tl", "parameter")]
        f = int_of(f_el, 0) if f_el is not None else 0
        fmt = format_at(kids(ed.doc, "format"), f)
        fill = txt(kid(fmt, "fillType")) if fmt is not None else ""
    keep = [child for child in content if ln(child) not in ("f", "tl", "parameter", "detailParameter")]
    if has_detail:
        detail_nodes = [ed.node("detailParameter", detail)] if detail else []
    else:
        detail_nodes = [child for child in content if ln(child) == "detailParameter"]
    new_children = head + detail_nodes + keep
    if [id(child) for child in content] != [id(child) for child in new_children]:
        _replace_children(ed, content, new_children)
    ed.write_row_cells(row, cells)
    ed.grow_columns(ed.column_set_for(row), c + 1)
    result = {"row": r + 1, "column": c + 1, "fillType": fill or "Text"}
    if name:
        result["parameter"] = name
    if has_template:
        result["template"] = p["template"]
    if has_detail:
        result["detail"] = detail or None
    result["previous"] = previous
    return result


def _replace_children(ed: Editor, parent, children):
    """Set parent's children; unchanged existing children keep their bytes."""
    depth = ed.t.depth(parent)
    if depth is None:
        # A fresh cell: its children are indented when the group is inserted.
        for child in list(parent):
            parent.remove(child)
        for child in children:
            if child.getparent() is not None:
                child.getparent().remove(child)
            parent.append(child)
        return
    for child in list(parent):
        if child not in children:
            ed.t.remove(child)
    for position, child in enumerate(children):
        current = list(parent)
        if position < len(current) and current[position] is child:
            continue
        if child.getparent() is parent:
            ed.t.remove(child)
        ed.t.insert(parent, position, child, depth=depth)


def blank_format(ed: Editor, f) -> int:
    """Format of an inserted empty cell: the source look without its fill type.

    BslEdit copies the fill type too, which turns every copy of a parameter cell
    into a nameless parameter that validateTemplate itself reports.
    """
    index = int_of(f, 0)
    fmt = format_at(kids(ed.doc, "format"), index)
    if fmt is not None and txt(kid(fmt, "fillType")) in ("Parameter", "Template"):
        return ed.format_with(index, {"fillType": None})
    return index


def blank_copy(ed: Editor, item):
    row = kid(item, "row")
    if row is None:
        return item
    kept = []
    for cell in row_cells(row):
        content = kid(cell["group"], "c")
        f = kid(content, "f") if content is not None else None
        if f is None or int_of(f, 0) <= 0:
            continue
        group = ed.node("c", None, [ed.node("c", None, [ed.node("f", blank_format(ed, f))])])
        kept.append({"col": cell["col"], "group": group})
    for child in list(row):
        if ln(child) in ("c", "empty"):
            ed.t.remove(child)
    expected = 0
    for cell in sorted(kept, key=lambda value: value["col"]):
        if cell["col"] != expected:
            cell["group"].insert(0, ed.node("i", cell["col"]))
        expected = cell["col"] + 1
        ed.t.append(row, cell["group"], depth=2)
    if not kept:
        ed.t.append(row, ed.node("empty", "true"), depth=2)
    return item


def split_range_at(ed: Editor, position):
    for item in kids(ed.doc, "rowsItem"):
        first, last = ed.item_bounds(item)
        if first < position <= last:
            index = ed.doc.index(item)
            ed.t.insert(ed.doc, index, ed.range_item(item, first, position - 1))
            ed.t.insert(ed.doc, index + 1, ed.range_item(item, position, last))
            ed.t.remove(item)


def set_extent(ed: Editor, element, name, value, after):
    existing = kid(element, name)
    if value == 0:
        if existing is not None:
            ed.t.remove(existing)
        return
    if existing is not None:
        existing.text = str(value)
        return
    position = 0
    for index, child in enumerate(element):
        if ln(child) in after:
            position = index + 1
    ed.t.insert(element, position, ed.node(name, value))


def shift_rows(ed: Editor, p: dict, insert: bool) -> dict:
    position = p["at"] - 1
    count = p.get("count", 1)
    height = int_of(kid(ed.doc, "height"), 0)
    # Designer keeps rowsItem past <height>; those rows exist and are shifted or deleted too.
    used = max(
        [height]
        + [ed.item_bounds(item)[1] + 1 for item in kids(ed.doc, "rowsItem")]
        + [rect["r"] + rect["h"] + 1 for rect in map(merge_rect, kids(ed.doc, "merge")) if rect["r"] >= 0]
    )
    _require(insert or position < used, "No rows to delete", 3)
    if insert and position > used:
        position = used
    if not insert:
        count = min(count, used - position)
    delta = count if insert else -count
    # <height> changes only by the rows inserted or deleted inside it.
    inside = count if insert and position <= height else max(0, min(position + count, height) - position)
    new_height = height + (inside if insert else -inside)
    report = {"removedAreas": [], "removedMerges": 0, "removedDrawings": 0}
    split_range_at(ed, position)
    if not insert:
        split_range_at(ed, position + count)
    source = min(position, used - 1) if insert and used else -1
    source_item = None
    for item in kids(ed.doc, "rowsItem"):
        first, last = ed.item_bounds(item)
        if first <= source <= last:
            source_item = item
    copies = (
        [blank_copy(ed, ed.range_item(source_item, position + k, position + k)) for k in range(count)]
        if source_item is not None
        else []
    )
    for item in kids(ed.doc, "rowsItem"):
        first, last = ed.item_bounds(item)
        if first < position:
            continue
        if not insert and first < position + count:
            ed.t.remove(item)
            continue
        _set_int(item, "index", first + delta)
        if (index_to := kid(item, "indexTo")) is not None:
            index_to.text = str(last + delta)
    if copies:
        index = ed.doc.index(source_item) + (1 if source < position else 0)
        for offset, clone in enumerate(copies):
            ed.t.insert(ed.doc, index + offset, clone)
    for name in ("merge", "verticalUnmerge"):
        for merge in kids(ed.doc, name):
            r = int_of(kid(merge, "r"), 0)
            if r < 0:
                continue
            span = shift_span(r, int_of(kid(merge, "h"), 0), position, delta)
            if span is None:
                ed.t.remove(merge)
                report["removedMerges"] += 1
                continue
            _set_int(merge, "r", span[0])
            set_extent(ed, merge, "h", span[1], ("r", "c"))
    for item in kids(ed.doc, "namedItem"):
        area = kid(item, "area")
        if area is None:
            continue
        begin = int_of(kid(area, "beginRow"), -1)
        if begin < 0:
            continue
        span = shift_span(begin, int_of(kid(area, "endRow"), begin) - begin, position, delta)
        if span is None:
            ed.t.remove(item)
            report["removedAreas"].append(txt(kid(item, "name")))
            continue
        _set_int(area, "beginRow", span[0])
        _set_int(area, "endRow", span[0] + span[1])
    for drawing in kids(ed.doc, "drawing"):
        begin = int_of(kid(drawing, "beginRow"), -1)
        end = int_of(kid(drawing, "endRow"), begin)
        if begin < 0:
            continue
        span = shift_span(begin, end - begin, position, delta)
        if span is None:
            ed.t.remove(drawing)
            report["removedDrawings"] += 1
            continue
        _set_int(drawing, "beginRow", span[0])
        _set_int(drawing, "endRow", span[0] + span[1])
    if new_height != height:
        ed.set_height(new_height)
    report["rows"] = new_height
    report["inserted" if insert else "deleted"] = {"at": position + 1, "count": count}
    return report


def shift_columns(ed: Editor, p: dict, insert: bool) -> dict:
    column_set = ed.column_set(p.get("columnsId"))
    set_id = txt(kid(column_set, "id"))
    is_default = column_set is kids(ed.doc, "columns")[0]
    position = p["at"] - 1
    count = p.get("count", 1)
    size = int_of(kid(column_set, "size"), 0)
    row_sets = row_column_sets(ed.doc)
    # Designer keeps columnsItem and cells past the set size; they are shifted or deleted too.
    used = max(
        [size]
        + [int_of(kid(item, "index"), 0) + 1 for item in kids(column_set, "columnsItem")]
        + [
            cell["col"] + 1
            for item in kids(ed.doc, "rowsItem")
            if kid(item, "row") is not None
            and (
                txt(kid(kid(item, "row"), "columnsID")) == set_id
                or (not txt(kid(kid(item, "row"), "columnsID")) and is_default)
            )
            for cell in row_cells(kid(item, "row"))
        ]
        + [
            int_of(kid(merge, "c"), 0) + int_of(kid(merge, "w"), 0) + 1
            for merge in kids(ed.doc, "merge")
            if merge_set(merge, row_sets) == set_id or (not merge_set(merge, row_sets) and is_default)
        ]
    )
    _require(insert or position < used, "No columns to delete", 3)
    if insert and position > used:
        position = used
    if not insert:
        count = min(count, used - position)
    delta = count if insert else -count
    inside = count if insert and position <= size else max(0, min(position + count, size) - position)
    new_size = size + (inside if insert else -inside)
    report = {"removedAreas": [], "removedMerges": 0, "removedDrawings": 0}
    source = min(position, used - 1) if insert and used else -1
    source_item = None
    _set_int(column_set, "size", new_size)
    for item in kids(column_set, "columnsItem"):
        index = int_of(kid(item, "index"), 0)
        if index == source:
            source_item = item
        if index < position:
            continue
        if not insert and index < position + count:
            ed.t.remove(item)
            continue
        _set_int(item, "index", index + delta)
    if source_item is not None:
        index = column_set.index(source_item) + (1 if source < position else 0)
        for k in range(count):
            clone = copy.deepcopy(source_item)
            _set_int(clone, "index", position + k)
            ed.t.insert(column_set, index + k, clone)
    for item in kids(ed.doc, "rowsItem"):
        row = kid(item, "row")
        if row is None:
            continue
        row_id = txt(kid(row, "columnsID"))
        if not (row_id == set_id or (not row_id and is_default)):
            continue
        cells = row_cells(row)
        if not cells:
            continue
        kept = []
        changed = False
        for cell in cells:
            if cell["col"] == source:
                f = kid(kid(cell["group"], "c"), "f")
                for n in range(count if f is not None and int_of(f, 0) > 0 else 0):
                    kept.append(
                        {
                            "col": position + n,
                            "group": ed.node("c", None, [ed.node("c", None, [ed.node("f", blank_format(ed, f))])]),
                        }
                    )
                    changed = True
            if cell["col"] < position:
                kept.append(cell)
            elif insert:
                kept.append({"col": cell["col"] + count, "group": cell["group"]})
                changed = True
            elif cell["col"] >= position + count:
                kept.append({"col": cell["col"] - count, "group": cell["group"]})
                changed = True
            else:
                changed = True
        if changed:
            ed.write_row_cells(row, kept)

    def in_set(element_id):
        return element_id == set_id if element_id else is_default

    for name in ("merge", "verticalUnmerge"):
        for merge in kids(ed.doc, name):
            if not in_set(merge_set(merge, row_sets)):
                continue
            span = shift_span(int_of(kid(merge, "c"), 0), int_of(kid(merge, "w"), 0), position, delta)
            if span is None:
                ed.t.remove(merge)
                report["removedMerges"] += 1
                continue
            _set_int(merge, "c", span[0])
            set_extent(ed, merge, "w", span[1], ("r", "c", "h"))
    for item in kids(ed.doc, "namedItem"):
        area = kid(item, "area")
        if area is None or not in_set(txt(kid(area, "columnsID"))):
            continue
        begin = int_of(kid(area, "beginColumn"), -1)
        if begin < 0:
            continue
        span = shift_span(begin, int_of(kid(area, "endColumn"), begin) - begin, position, delta)
        if span is None:
            ed.t.remove(item)
            report["removedAreas"].append(txt(kid(item, "name")))
            continue
        _set_int(area, "beginColumn", span[0])
        _set_int(area, "endColumn", span[0] + span[1])
    if is_default:
        for drawing in kids(ed.doc, "drawing"):
            begin = int_of(kid(drawing, "beginColumn"), -1)
            end = int_of(kid(drawing, "endColumn"), begin)
            if begin < 0:
                continue
            span = shift_span(begin, end - begin, position, delta)
            if span is None:
                ed.t.remove(drawing)
                report["removedDrawings"] += 1
                continue
            _set_int(drawing, "beginColumn", span[0])
            _set_int(drawing, "endColumn", span[0] + span[1])
    report["columns"] = new_size
    report["inserted" if insert else "deleted"] = {"at": position + 1, "count": count}
    return report


def op_merge_cells(ed: Editor, p: dict) -> dict:
    r, c = p["row"] - 1, p["column"] - 1
    # Cells of a row are numbered in that row's column set; merges of other sets do not overlap them.
    row_sets = row_column_sets(ed.doc)
    target_set = row_sets.get(r, "")
    merges = [
        merge
        for merge in kids(ed.doc, "merge")
        if int_of(kid(merge, "r"), 0) >= 0 and merge_set(merge, row_sets) == target_set
    ]
    if p.get("unmerge"):
        hit = next(
            (
                merge
                for merge in merges
                if (lambda x: x["r"] <= r <= x["r"] + x["h"] and x["c"] <= c <= x["c"] + x["w"])(merge_rect(merge))
            ),
            None,
        )
        _require(hit is not None, "Cell is not merged", 3)
        gone = merge_rect(hit)
        ed.t.remove(hit)
        return {
            "unmerged": {"row": gone["r"] + 1, "column": gone["c"] + 1, "rows": gone["h"] + 1, "columns": gone["w"] + 1}
        }
    h, w = p.get("rows", 1) - 1, p.get("columns", 1) - 1
    _require(h or w, "Merge needs more than one cell")
    for merge in merges:
        x = merge_rect(merge)
        _require(
            not (r <= x["r"] + x["h"] and x["r"] <= r + h and c <= x["c"] + x["w"] and x["c"] <= c + w),
            "Merge overlaps an existing merge",
            3,
        )
    children = [ed.node("r", r), ed.node("c", c)]
    if h:
        children.append(ed.node("h", h))
    if w:
        children.append(ed.node("w", w))
    ed.place_in_tail(ed.node("merge", None, children))
    if r + h + 1 > int_of(kid(ed.doc, "height"), 0):
        ed.grow_height(r + h + 1)
    return {"merged": {"row": r + 1, "column": c + 1, "rows": h + 1, "columns": w + 1}}


def op_set_size(ed: Editor, p: dict) -> dict:
    changed = []
    if "column" in p:
        _require("width" in p and not {"row", "toRow", "height"} & set(p), "Column size needs width only")
        width = int(js_round(float(p["width"])))
        column_set = ed.column_set(p.get("columnsId"))
        first = p["column"] - 1
        last = p["toColumn"] - 1 if "toColumn" in p else first
        _require(last >= first, "to_column precedes column")
        for c in range(first, last + 1):
            item = next((it for it in kids(column_set, "columnsItem") if int_of(kid(it, "index"), -1) == c), None)
            if item is None:
                item = ed.node("columnsItem", None, [ed.node("index", c), ed.node("column")])
                after = -1
                for index, child in enumerate(column_set):
                    if ln(child) in ("size", "id") or (
                        ln(child) == "columnsItem" and int_of(kid(child, "index"), 0) < c
                    ):
                        after = index
                ed.t.insert(column_set, after + 1, item)
            column = kid(item, "column")
            if column is None:
                column = ed.node("column")
                ed.t.append(item, column)
            f_el = kid(column, "formatIndex")
            index = ed.format_with(int_of(f_el, 0) if f_el is not None else 0, {"width": width})
            if f_el is not None:
                f_el.text = str(index)
            else:
                ed.t.insert(column, 0, ed.node("formatIndex", index))
            changed.append({"column": c + 1, "width": width})
        if last + 1 > int_of(kid(column_set, "size"), 0):
            _set_int(column_set, "size", last + 1)
    elif "row" in p:
        _require(
            "height" in p and not {"column", "toColumn", "width", "columnsId"} & set(p), "Row size needs height only"
        )
        points = float(p["height"])
        first = p["row"] - 1
        last = p["toRow"] - 1 if "toRow" in p else first
        _require(last >= first, "to_row precedes row")
        for r in range(first, last + 1):
            row = ed.row_for(r)
            f_el = kid(row, "formatIndex")
            index = ed.format_with(
                int_of(f_el, 0) if f_el is not None else 0, {"height": int(js_round(points * 4)) if points else None}
            )
            if f_el is not None:
                f_el.text = str(index)
            else:
                ed.t.insert(row, 1 if kid(row, "columnsID") is not None else 0, ed.node("formatIndex", index))
            changed.append({"row": r + 1, "height": js_int(points) if points else "auto"})
    else:
        raise _editor().FixedRejected("Column or row size required")
    return {"changed": changed}


H_ALIGNS = ("Left", "Center", "Right", "Justify", "Auto")
FORMAT_KEYS = (
    "font",
    "horizontalAlignment",
    "verticalAlignment",
    "textPlacement",
    "indent",
    "textColor",
    "backColor",
    "border",
    "leftBorder",
    "topBorder",
    "rightBorder",
    "bottomBorder",
    "borderColor",
    "format",
    "protection",
)


def _color(value):
    value = value.strip()
    return value.upper() if value.startswith("#") else value


def op_set_format(ed: Editor, p: dict) -> dict:
    r0, c0 = p["row"] - 1, p["column"] - 1
    r1 = p["toRow"] - 1 if "toRow" in p else r0
    c1 = p["toColumn"] - 1 if "toColumn" in p else c0
    _require(r1 >= r0 and c1 >= c0, "to_row/to_column precede row/column")
    given = [key for key in FORMAT_KEYS if key in p]
    _require(given, "No format property given")
    fixed = {}
    for key in given:
        value = p[key]
        if value is None:
            fixed[key] = None
        elif key in ("textColor", "backColor", "borderColor"):
            fixed[key] = _color(value)
        elif key == "indent":
            fixed[key] = value or None
        elif key == "protection":
            fixed[key] = "true" if value else None
        elif key == "format":
            fixed[key] = value or None
        else:
            fixed[key] = value
    lang = language(ed.doc)
    touched = 0
    for r in range(r0, r1 + 1):
        row = ed.row_for(r)
        cells = row_cells(row)
        for c in range(c0, c1 + 1):
            cell = ed.cell(cells, c)
            content = ed.content(cell["group"])
            f_el = kid(content, "f")
            current = int_of(f_el, 0) if f_el is not None else 0
            base_format = format_at(kids(ed.doc, "format"), current)
            changes = {}
            for key, value in fixed.items():
                if key == "font":
                    changes["font"] = (
                        None if value is None else ed.font_index(ed.inherited_font(row, c, base_format), value)
                    )
                elif key == "border" or (key.endswith("Border") and key != "borderColor"):
                    sides = ("leftBorder", "topBorder", "rightBorder", "bottomBorder") if key == "border" else (key,)
                    if key == "border":
                        changes["border"] = None
                    for side in sides:
                        changes[side] = None if value is None else ed.line_index(value)
                elif key == "format":
                    changes["format"] = (
                        None
                        if value is None
                        else ed.node(
                            "format",
                            None,
                            [ed.node("v8:item", None, [ed.node("v8:lang", lang), ed.node("v8:content", value)])],
                        )
                    )
                else:
                    changes[key] = value
            index = ed.format_with(current, changes)
            if f_el is not None:
                f_el.text = str(index)
            else:
                depth = ed.t.depth(content)
                ed.t.insert(content, 0, ed.node("f", index), depth=depth)
            touched += 1
        ed.write_row_cells(row, cells)
        ed.grow_columns(ed.column_set_for(row), c1 + 1)
    return {"cells": touched, "properties": given}


def op_set_print_settings(ed: Editor, p: dict) -> dict:
    values = {}
    if "orientation" in p:
        values["pageOrientation"] = p["orientation"]
    if "scale" in p:
        values["scale"] = p["scale"]
    if "fitToPage" in p:
        values["fitToPage"] = "true" if p["fitToPage"] else "false"
    if "blackAndWhite" in p:
        values["blackAndWhite"] = "true" if p["blackAndWhite"] else "false"
    for key in ("paper", "copies", "firstPageNumber"):
        if key in p:
            values[key] = p[key]
    for key in ("topMargin", "leftMargin", "bottomMargin", "rightMargin", "headerSize", "footerSize"):
        if key in p:
            values[key] = int(js_round(float(p[key]) * 100))
    has_area = "printArea" in p
    _require(values or has_area, "No print setting given")
    if values:
        settings = kid(ed.doc, "printSettings")
        if settings is None:
            settings = ed.node("printSettings")
            ed.place_in_tail(settings)
        for key, value in values.items():
            existing = kid(settings, key)
            if existing is not None:
                existing.text = js_str(value) if not isinstance(value, str) else value
                continue
            rank = PRINT_ORDER.index(key)
            position = len(settings)
            for index, child in enumerate(settings):
                if (PRINT_ORDER.index(ln(child)) if ln(child) in PRINT_ORDER else -1) > rank:
                    position = index
                    break
            ed.t.insert(settings, position, ed.node(key, value))
    area = None
    if has_area:
        old = kid(ed.doc, "printArea")
        spec = p["printArea"]
        if spec:
            begin_row = spec["beginRow"] - 1
            end_row = spec.get("endRow", spec["beginRow"]) - 1
            has_cols = "beginColumn" in spec or "endColumn" in spec
            begin_col = spec.get("beginColumn", spec.get("endColumn")) - 1 if has_cols else -1
            end_col = spec.get("endColumn", spec.get("beginColumn")) - 1 if has_cols else -1
            _require(end_row >= begin_row and end_col >= begin_col, "Print area end precedes begin")
            element = ed.node(
                "printArea",
                None,
                [
                    ed.node("type", "Rectangle" if has_cols else "Rows"),
                    ed.node("beginRow", begin_row),
                    ed.node("endRow", end_row),
                    ed.node("beginColumn", begin_col),
                    ed.node("endColumn", end_col),
                ],
            )
            if old is not None:
                ed.t.replace(old, element)
            else:
                ed.place_in_tail(element)
            area = {"beginRow": begin_row + 1, "endRow": end_row + 1}
            if has_cols:
                area.update(beginColumn=begin_col + 1, endColumn=end_col + 1)
        elif old is not None:
            ed.t.remove(old)
    print_settings = kid(ed.doc, "printSettings")
    result: dict[str, object] = {
        "printSettings": {ln(child): txt(child) for child in (print_settings if print_settings is not None else [])}
    }
    if has_area:
        result["printArea"] = area
    return result


def op_set_header_footer(ed: Editor, p: dict) -> dict:
    kind = p["kind"]
    suffix = "Header" if kind == "header" else "Footer"
    slots = ("left", "center", "right")
    if p.get("remove"):
        for slot in slots:
            element = kid(ed.doc, slot + suffix)
            if element is not None:
                ed.t.remove(element)
        return {"removed": kind}
    _require(any(slot in p for slot in slots) or p.get("font"), "Pass left, center, right or font")
    lang = language(ed.doc)
    font_change = p.get("font")
    result = {}
    for slot in slots:
        element = kid(ed.doc, slot + suffix)
        if element is None:
            element = ed.node(slot + suffix, None, [ed.node("f", 0), ed.node("tl")])
            ed.place_in_tail(element)
        if slot in p:
            tl = kid(element, "tl")
            if tl is None:
                tl = ed.node("tl")
                ed.t.append(element, tl)
            for child in list(tl):
                ed.t.remove(child)
            if p[slot] != "":
                ed.t.append(tl, ed.node("v8:item", None, [ed.node("v8:lang", lang), ed.node("v8:content", p[slot])]))
        if font_change:
            f_el = kid(element, "f")
            if f_el is None:
                f_el = ed.node("f", 0)
                ed.t.insert(element, 0, f_el)
            current = int_of(f_el, 0)
            base_format = format_at(kids(ed.doc, "format"), current)
            base_font = (
                int_of(kid(base_format, "font"), 0)
                if base_format is not None and kid(base_format, "font") is not None
                else 0
            )
            f_el.text = str(ed.format_with(current, {"font": ed.font_index(base_font, font_change)}))
        result[slot] = localized(kid(element, "tl"), lang)
    return {"kind": kind, "slots": result}


OPERATIONS = {
    "template.set-area": op_set_area,
    "template.set-parameter": op_set_parameter,
    "template.set-format": op_set_format,
    "template.insert-rows": lambda ed, p: shift_rows(ed, p, True),
    "template.delete-rows": lambda ed, p: shift_rows(ed, p, False),
    "template.insert-columns": lambda ed, p: shift_columns(ed, p, True),
    "template.delete-columns": lambda ed, p: shift_columns(ed, p, False),
    "template.merge-cells": op_merge_cells,
    "template.set-size": op_set_size,
    "template.set-print-settings": op_set_print_settings,
    "template.set-header-footer": op_set_header_footer,
}


def edit(snapshot, operation: dict) -> dict:
    """Plan handler for template.* edits: read current view, edit, stage only this file."""
    context, template = load(snapshot, operation["target"])
    report = OPERATIONS[operation["op"]](Editor(template), operation["parameters"])
    data = template.dump()
    Template(data)  # the candidate must parse and round-trip in the same layout
    snapshot.stage(context["path"], data)
    return report


def import_xlsx(snapshot, operation: dict) -> dict:
    """template.import-xlsx: fill a registered empty template from an Excel sheet."""
    editor = _editor()
    parameters = operation["parameters"]
    context, template = load(snapshot, operation["target"], allow_stub=True)
    _require(parameters.get("replace") or is_empty(template), "Template is not empty; replace=true required", 3)
    source = Path(parameters["xlsx"])
    _require(source.is_absolute(), "xlsx path must be absolute")
    # The xlsx directory becomes a declared source root; apply keeps its journal next to --root.
    target_root = snapshot.roots["target"]
    state = target_root.with_name("." + target_root.name + ".metadata-state")
    _require(
        not state.is_relative_to(source.parent) and not target_root.is_relative_to(source.parent),
        "xlsx directory contains --root; move the xlsx to a directory outside the parent of --root",
        3,
    )
    alias = snapshot.source_root(source.parent)
    data = snapshot.read(alias, source.name)
    built, summary = convert(
        data, parameters.get("sheet"), eol=template.eol, trailing=template.epilog.endswith("\n"), bom=template.bom
    )
    candidate = Template(built)
    errors, _ = validate(candidate.root)
    _require(not errors, "Converted template failed structure checks", 4)
    snapshot.stage(context["path"], built)
    del editor
    return summary


def is_empty(template: Template) -> bool:
    if template.stub:
        return not len(template.root)
    content = (
        "namedItem",
        "merge",
        "verticalUnmerge",
        "drawing",
        "picture",
        "leftHeader",
        "centerHeader",
        "rightHeader",
        "leftFooter",
        "centerFooter",
        "rightFooter",
        "printArea",
    )
    if any(kid(template.root, name) is not None for name in content):
        return False
    return not any(kids(kid(item, "row"), "c") for item in kids(template.root, "rowsItem"))


# ---------------------------------------------------------------- xlsx reader


class El:
    __slots__ = ("name", "attrs", "kids", "text")

    def __init__(self, name, attrs=None, children=None, text=""):
        self.name, self.attrs, self.kids, self.text = name, attrs or {}, children or [], text

    def key(self):
        return [self.name, sorted(self.attrs.items()), [child.key() for child in self.kids], self.text]


def parse_xml(data: bytes | None) -> El:
    if not data:
        return El("#root")
    parser = etree.XMLParser(
        load_dtd=False,
        resolve_entities=False,
        no_network=True,
        huge_tree=False,
        remove_comments=True,
        remove_pis=True,
        strip_cdata=True,
    )
    try:
        root = etree.fromstring(data, parser)
    except (etree.XMLSyntaxError, ValueError):
        raise _editor().FixedRejected("Invalid xlsx part") from None
    _require(
        not root.getroottree().docinfo.internalDTD and not root.getroottree().docinfo.doctype,
        "DTD/entities are unsupported",
    )

    def convert_node(node):
        attrs = {}
        for key, value in node.attrib.items():
            attrs[key.rpartition("}")[2]] = value
        children = [convert_node(child) for child in node if isinstance(child.tag, str)]
        text = (node.text or "") + "".join(child.tail or "" for child in node)
        return El(node.tag.rpartition("}")[2], attrs, children, text)

    return convert_node(root)


def xkid(el, name):
    if el is None:
        return None
    return next((child for child in el.kids if child.name == name), None)


def xkids(el, name):
    return [child for child in el.kids if child.name == name] if el is not None else []


def deep_text(el) -> str:
    if el is None:
        return ""
    if el.name == "t":
        return el.text
    return "".join(deep_text(child) for child in el.kids if child.name != "rPh")


def bool_attr(el, name, default):
    if el is None:
        return default
    value = el.attrs.get(name)
    if value is None:
        return True
    return value in ("1", "true")


def col_index(letters: str) -> int:
    n = 0
    for char in letters:
        n = n * 26 + (ord(char) - 64)
    return n - 1


def parse_ref(ref):
    match = re.fullmatch(r"\$?([A-Z]+)\$?(\d+)", ref or "")
    return {"c": col_index(match.group(1)), "r": int(match.group(2)) - 1} if match else None


def parse_defined_range(text):
    t = str(text or "").strip()
    bang = t.rfind("!")
    sheet = re.sub(r"^'|'$", "", t[:bang]).replace("''", "'") if bang >= 0 else ""
    ref = t[bang + 1 :] if bang >= 0 else t
    if "," in ref or "#REF" in ref:
        return None
    parts = ref.replace("$", "").split(":")
    a = parts[0]
    b = parts[1] if len(parts) > 1 and parts[1] else parts[0]
    if re.fullmatch(r"\d+", a) and re.fullmatch(r"\d+", b):
        return {
            "sheet": sheet,
            "type": "Rows",
            "beginRow": int(a) - 1,
            "endRow": int(b) - 1,
            "beginColumn": -1,
            "endColumn": -1,
        }
    if re.fullmatch(r"[A-Z]+", a) and re.fullmatch(r"[A-Z]+", b):
        return {
            "sheet": sheet,
            "type": "Columns",
            "beginRow": -1,
            "endRow": -1,
            "beginColumn": col_index(a),
            "endColumn": col_index(b),
        }
    first, second = parse_ref(a), parse_ref(b)
    if not first or not second:
        return None
    return {
        "sheet": sheet,
        "type": "Rectangle",
        "beginRow": min(first["r"], second["r"]),
        "endRow": max(first["r"], second["r"]),
        "beginColumn": min(first["c"], second["c"]),
        "endColumn": max(first["c"], second["c"]),
    }


THEME_DEFAULT = [
    "FFFFFF",
    "000000",
    "EEECE1",
    "1F497D",
    "4F81BD",
    "C0504D",
    "9BBB59",
    "8064A2",
    "4BACC6",
    "F79646",
    "0000FF",
    "800080",
]
INDEXED = [
    "000000",
    "FFFFFF",
    "FF0000",
    "00FF00",
    "0000FF",
    "FFFF00",
    "FF00FF",
    "00FFFF",
    "000000",
    "FFFFFF",
    "FF0000",
    "00FF00",
    "0000FF",
    "FFFF00",
    "FF00FF",
    "00FFFF",
    "800000",
    "008000",
    "000080",
    "808000",
    "800080",
    "008080",
    "C0C0C0",
    "808080",
    "9999FF",
    "993366",
    "FFFFCC",
    "CCFFFF",
    "660066",
    "FF8080",
    "0066CC",
    "CCCCFF",
    "000080",
    "FF00FF",
    "FFFF00",
    "00FFFF",
    "800080",
    "800000",
    "008080",
    "0000FF",
    "00CCFF",
    "CCFFFF",
    "CCFFCC",
    "FFFF99",
    "99CCFF",
    "FF99CC",
    "CC99FF",
    "FFCC99",
    "3366FF",
    "33CCCC",
    "99CC00",
    "FFCC00",
    "FF9900",
    "FF6600",
    "666699",
    "969696",
    "003366",
    "339966",
    "003300",
    "333300",
    "993300",
    "993366",
    "333399",
    "333333",
]


def apply_tint(hex_value: str, tint: float) -> str:
    if not tint or math.isnan(tint):
        return hex_value
    out = ""
    for i in range(3):
        value = int(hex_value[i * 2 : i * 2 + 2], 16)
        value = value * (1 + tint) if tint < 0 else value + (255 - value) * tint
        out += format(int(js_round(max(0, min(255, value)))), "02X")
    return out


def color_of(el, theme) -> str:
    if el is None or el.attrs.get("auto") in ("1", "true"):
        return ""
    hex_value = ""
    if el.attrs.get("rgb"):
        hex_value = el.attrs["rgb"].lstrip("#")[-6:].upper()
    elif el.attrs.get("theme") is not None:
        hex_value = at(theme, js_number(el.attrs["theme"])) or ""
    elif el.attrs.get("indexed") is not None:
        hex_value = at(INDEXED, js_number(el.attrs["indexed"])) or ""
    if not re.fullmatch(r"[0-9A-F]{6}", hex_value):
        return ""
    return "#" + apply_tint(hex_value, js_parse_float(el.attrs.get("tint") or "0"))


def read_theme(data) -> list:
    theme = list(THEME_DEFAULT)
    if not data:
        return theme
    scheme = None

    def find(el):
        nonlocal scheme
        if scheme is not None or el is None:
            return
        if el.name == "clrScheme":
            scheme = el
            return
        for child in el.kids:
            find(child)

    find(parse_xml(data))
    if scheme is None:
        return theme
    order = [
        "lt1",
        "dk1",
        "lt2",
        "dk2",
        "accent1",
        "accent2",
        "accent3",
        "accent4",
        "accent5",
        "accent6",
        "hlink",
        "folHlink",
    ]
    for i, name in enumerate(order):
        e = xkid(scheme, name)
        c = e and (xkid(e, "srgbClr") or xkid(e, "sysClr"))
        if not c:
            continue
        val = c.attrs.get("val")
        v = "000000" if val == "windowText" else "FFFFFF" if val == "window" else (c.attrs.get("lastClr") or val)
        if v and re.fullmatch(r"[0-9A-Fa-f]{6}", v):
            theme[i] = v.upper()
    return theme


BUILTIN_DATE_FORMATS = {14: 1, 15: 1, 16: 1, 17: 1, 18: 2, 19: 2, 20: 2, 21: 2, 22: 1, 45: 2, 46: 2, 47: 2}
BUILTIN_CODES = {
    1: "0",
    2: "0.00",
    3: "#,##0",
    4: "#,##0.00",
    14: "dd.mm.yyyy",
    15: "d-mmm-yy",
    20: "h:mm",
    21: "h:mm:ss",
    22: "dd.mm.yyyy h:mm",
}


def _key(number) -> str:
    return js_str(number) if isinstance(number, float) else str(number)


def _builtin(table, number):
    if isinstance(number, float) and number.is_integer():
        number = int(number)
    return table.get(number) if isinstance(number, int) else None


def read_styles(data, theme) -> dict:
    st = {"fonts": [], "fills": [], "borders": [], "xfs": [], "numFmts": {}}
    if not data:
        return st
    doc = parse_xml(data)
    for n in xkids(xkid(doc, "numFmts"), "numFmt"):
        st["numFmts"][str(n.attrs.get("numFmtId"))] = n.attrs.get("formatCode") or ""
    for f in xkids(xkid(doc, "fonts"), "font"):
        u = xkid(f, "u")
        name_el = xkid(f, "name") or xkid(f, "rFont")
        st["fonts"].append(
            {
                "name": (name_el.attrs.get("val") if name_el else None) or "",
                "size": js_parse_float((sz.attrs.get("val") if (sz := xkid(f, "sz")) else None) or "") or 0,
                "bold": bool_attr(xkid(f, "b"), "val", False),
                "italic": bool_attr(xkid(f, "i"), "val", False),
                "underline": bool(u) and u.attrs.get("val") != "none",
                "strike": bool_attr(xkid(f, "strike"), "val", False),
                "color": color_of(xkid(f, "color"), theme),
            }
        )
    for f in xkids(xkid(doc, "fills"), "fill"):
        pattern = xkid(f, "patternFill")
        if pattern and pattern.attrs.get("patternType") == "solid":
            st["fills"].append(color_of(xkid(pattern, "fgColor"), theme) or color_of(xkid(pattern, "bgColor"), theme))
        else:
            st["fills"].append("")
    for b in xkids(xkid(doc, "borders"), "border"):
        out = {}
        for side in ("left", "right", "top", "bottom"):
            e = xkid(b, side)
            if e and e.attrs.get("style") and e.attrs["style"] != "none":
                out[side] = {"style": e.attrs["style"], "color": color_of(xkid(e, "color"), theme)}
        st["borders"].append(out)
    for x in xkids(xkid(doc, "cellXfs"), "xf"):
        al = xkid(x, "alignment")
        st["xfs"].append(
            {
                "font": js_number(x.attrs.get("fontId") or 0),
                "fill": js_number(x.attrs.get("fillId") or 0),
                "border": js_number(x.attrs.get("borderId") or 0),
                "numFmt": js_number(x.attrs.get("numFmtId") or 0),
                "h": (al.attrs.get("horizontal") or "") if al else "",
                "v": (al.attrs.get("vertical") or "") if al else "",
                "wrap": al.attrs.get("wrapText") in ("1", "true") if al else False,
                "indent": js_number(al.attrs.get("indent") or 0) if al else 0,
                "rotation": js_number(al.attrs.get("textRotation") or 0) if al else 0,
            }
        )
    return st


def _strip_codes(code: str) -> str:
    return re.sub(r'"[^"]*"|\[[^\]]*\]|\\.|_.|\*.', "", code)


def is_date_format(st, number) -> bool:
    if _builtin(BUILTIN_DATE_FORMATS, number):
        return True
    code = st["numFmts"].get(_key(number))
    if not code:
        return False
    code = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", code)
    return bool(re.search(r"[dmyhs]", code, re.I)) and not re.search(r"[#0]", re.sub(r"[dmyhs]", "", code, flags=re.I))


def one_c_format(st, number) -> str:
    code = st["numFmts"].get(_key(number))
    if code is None:
        code = _builtin(BUILTIN_CODES, number)
    if not code or re.match(r"(?:general|@)\Z", code, re.I):
        return ""
    section = code.split(";")[0]
    code = _strip_codes(section)
    builtin = _builtin(BUILTIN_CODES, number)
    if is_date_format(st, number) or (builtin and re.search(r"[dy]|h:", builtin)):

        def literal(match):
            quoted, escaped = match.group(1), match.group(2)
            value = quoted if quoted is not None else escaped if escaped is not None else ""
            return "" if re.search(r"[a-zа-яё'\"]", value, re.I) else value

        code = re.sub(r'"([^"]*)"|\[[^\]]*\]|\\(.)|_.|\*.', literal, section)
        has_time = bool(re.search("h", code, re.I))

        def token(match):
            t = match.group(0).lower()
            if t[0] == "y":
                return "yyyy" if len(t) > 2 else "yy"
            if t[0] == "d":
                return ("dddd" if len(t) > 3 else "ddd") if len(t) > 2 else t
            if t[0] == "h":
                return "HH" if len(t) > 1 else "H"
            if t[0] == "s":
                return t
            whole, offset = match.string, match.start()
            before = re.sub(r"[^a-z]", "", whole[:offset], flags=re.I)[-1:].lower()
            after = re.sub(r"[^a-z]", "", whole[offset + len(t) :], flags=re.I)[:1].lower()
            if has_time and (before == "h" or after == "s"):
                return "mm" if len(t) > 1 else "m"
            return ("MMMM" if len(t) > 3 else "MMM") if len(t) > 2 else t.upper()

        out = re.sub(r"(y+|m+|d+|h+|s+)", token, code, flags=re.I).strip()
        if not out:
            return ""
        return "ДФ='" + out + "'" if re.search(r"\s", out) else "ДФ=" + out
    if "%" in code or not re.search(r"[0#]", code):
        return ""
    decimals = len(re.sub(r"[^0#]", "", (code.split(".") + [""])[1]))
    parts = ["ЧДЦ=" + str(decimals)]
    if "," not in code:
        parts.append("ЧГ=0")
    return "; ".join(parts)


NBSP = " "


def display_number(num: float, st, number) -> str:
    code = st["numFmts"].get(_key(number))
    if code is None:
        code = _builtin(BUILTIN_CODES, number)
    main = _strip_codes(str(code).split(";")[0]) if code else ""
    percent = "%" in main
    value = num * 100 if percent else num
    if not main or re.fullmatch(r"general", main, re.I) or not re.search(r"[0#]", main):
        text = js_str(js_to_precision(value, 15))
        if "e" in text.lower():
            return text
        dot = text.find(".")
        if dot >= 0 and len(text) - dot - 1 > 10:
            fixed = js_to_fixed(value, 10)
            text = js_str(float(fixed)) if fixed not in ("NaN",) else fixed
        return text.replace(".", ",", 1)
    decimals = len(re.sub(r"[^0#]", "", (main.split(".") + [""])[1]))
    text = js_to_fixed(abs(value), decimals)
    parts = text.split(".")
    if "," in main:
        parts[0] = re.sub(r"\B(?=(\d{3})+(?!\d))", NBSP, parts[0])
    text = ",".join(parts)
    negative = value < 0 and float(text.replace(NBSP, "").replace(",", ".", 1)) != 0
    return ("-" if negative else "") + text + ("%" if percent else "")


def _civil(days: int):
    z = days + 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return y + (1 if m <= 2 else 0), m, d


def serial_to_date(serial: float, with_time: bool) -> str:
    ms = js_round((serial - 25569) * 86400000)
    if math.isnan(ms) or abs(ms) > 8.64e15:
        text = "NaN.NaN.NaN"
        if with_time or (not math.isnan(serial) and math.fmod(serial, 1)):
            text += " NaN:NaN:NaN"
        return text
    ms = int(ms)
    days, rest = divmod(ms, 86400000)
    year, month, day = _civil(days)
    text = f"{day:02d}.{month:02d}.{year}"
    if with_time or math.fmod(serial, 1):
        seconds = rest // 1000
        text += f" {seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
    return text


def resolve_part(base: str, target: str) -> str:
    if target.startswith("/"):
        return target[1:]
    parts = base.split("/")[:-1]
    for piece in target.split("/"):
        if piece == "..":
            if parts:
                parts.pop()
        elif piece != ".":
            parts.append(piece)
    return "/".join(parts)


def read_rels(data, base_path) -> dict:
    result = {}
    if not data:
        return result
    for rel in xkids(parse_xml(data), "Relationship"):
        target = rel.attrs.get("Target") or ""
        result[rel.attrs.get("Id")] = {
            "target": target if rel.attrs.get("TargetMode") == "External" else resolve_part(base_path, target),
            "type": rel.attrs.get("Type") or "",
        }
    return result


class Workbook:
    def __init__(self, data: bytes):
        editor = _editor()
        try:
            self.zip = zipfile.ZipFile(io.BytesIO(data))
            infos = self.zip.infolist()
        except (zipfile.BadZipFile, ValueError, EOFError):
            raise editor.FixedRejected("Invalid xlsx archive") from None
        _require(len(infos) <= XLSX_ENTRIES, "xlsx archive has too many entries")
        self.entries = {}
        for info in infos:
            self.entries[info.filename.replace("\\", "/")] = info
        self.total = 0

    def read(self, name: str) -> bytes | None:
        info = self.entries.get(name)
        if info is None:
            return None
        _require(not info.flag_bits & 0x1, "Encrypted xlsx entries are unsupported")
        _require(info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), "Unsupported xlsx compression")
        _require(info.file_size <= XLSX_ENTRY_LIMIT, "xlsx entry size limit exceeded")
        self.total += info.file_size
        _require(self.total <= XLSX_TOTAL_LIMIT, "xlsx size limit exceeded")
        try:
            with self.zip.open(info) as stream:
                data = stream.read(XLSX_ENTRY_LIMIT + 1)
        except (zipfile.BadZipFile, ValueError, EOFError, OSError, NotImplementedError, RuntimeError):
            raise _editor().FixedRejected("Invalid xlsx archive") from None
        _require(len(data) <= XLSX_ENTRY_LIMIT, "xlsx entry size limit exceeded")
        return data

    def text(self, name):
        data = self.read(name)
        return data if data else b""


def open_workbook(data: bytes) -> dict:
    book = Workbook(data)
    workbook = book.text("xl/workbook.xml")
    _require(workbook, "xlsx has no xl/workbook.xml")
    wb = parse_xml(workbook)
    rels = read_rels(book.text("xl/_rels/workbook.xml.rels"), "xl/workbook.xml")
    sheets = []
    for sheet in xkids(xkid(wb, "sheets"), "sheet"):
        rel = rels.get(sheet.attrs.get("id"))
        sheets.append(
            {
                "name": sheet.attrs.get("name") or "",
                "state": sheet.attrs.get("state") or "visible",
                "path": rel["target"] if rel else "",
            }
        )
    names = [
        {
            "name": d.attrs.get("name") or "",
            "localSheetId": d.attrs.get("localSheetId"),
            "hidden": d.attrs.get("hidden") == "1",
            "ref": d.text.strip(),
        }
        for d in xkids(xkid(wb, "definedNames"), "definedName")
    ]

    def rel_of(suffix):
        return next((rel for rel in rels.values() if re.search("/" + suffix + "$", rel["type"])), None)

    theme, styles, sst = rel_of("theme"), rel_of("styles"), rel_of("sharedStrings")
    return {
        "book": book,
        "sheets": sheets,
        "names": names,
        "themePath": theme["target"] if theme else "xl/theme/theme1.xml",
        "stylesPath": styles["target"] if styles else "xl/styles.xml",
        "sstPath": sst["target"] if sst else "xl/sharedStrings.xml",
    }


def read_sheet(workbook: dict, sheet_index: int, warnings: dict) -> dict:
    book = workbook["book"]
    sheet = workbook["sheets"][sheet_index]
    rel_path = re.sub(r"([^/]+)$", r"_rels/\1.rels", sheet["path"])
    sheet_data = book.text(sheet["path"])
    _require(sheet_data, "xlsx sheet part is missing")
    theme = read_theme(book.text(workbook["themePath"]))
    st = read_styles(book.text(workbook["stylesPath"]), theme)
    sst_data = book.text(workbook["sstPath"])
    sst = []
    for si in xkids(parse_xml(sst_data) if sst_data else None, "si"):
        runs = xkids(si, "r")
        if len(runs) > 1:
            fonts = [
                json.dumps(run_props.key() if (run_props := xkid(run, "rPr")) else {}, ensure_ascii=False)
                for run in runs
            ]
            if any(font != fonts[0] for font in fonts):
                warnings["richText"] = True
        sst.append(deep_text(si))
    ws = parse_xml(sheet_data)
    sheet_rels = read_rels(book.text(rel_path), sheet["path"])
    fmt = xkid(ws, "sheetFormatPr")
    if fmt and fmt.attrs.get("defaultColWidth"):
        def_col_chars = js_parse_float(fmt.attrs["defaultColWidth"])
    elif fmt and fmt.attrs.get("baseColWidth"):
        def_col_chars = js_parse_float(fmt.attrs["baseColWidth"]) + 0.71
    else:
        def_col_chars = 8.43
    cols = {}
    for c in xkids(xkid(ws, "cols"), "col"):
        low, high = js_number(c.attrs.get("min")) - 1, js_number(c.attrs.get("max")) - 1
        if math.isnan(low) or math.isnan(high):
            continue
        i = low
        while i <= high and i < 16384:
            index = int(i) if float(i).is_integer() else i
            cols[index] = {
                "width": js_parse_float(c.attrs["width"]) if c.attrs.get("width") is not None else def_col_chars,
                "hidden": c.attrs.get("hidden") in ("1", "true"),
                "style": js_number(c.attrs["style"]) if c.attrs.get("style") is not None else -1,
            }
            i += 1
    rows = []
    max_col = max_row = -1
    formulas = 0
    next_row = 0
    for r in xkids(xkid(ws, "sheetData"), "row"):
        ri = js_number(r.attrs["r"]) - 1 if r.attrs.get("r") else next_row
        _require(not math.isnan(ri) and float(ri).is_integer() and 0 <= ri <= GRID_LIMIT, "Invalid xlsx row")
        ri = int(ri)
        next_row = ri + 1
        row = {
            "index": ri,
            "height": js_parse_float(r.attrs["ht"]) if r.attrs.get("ht") is not None else None,
            "hidden": r.attrs.get("hidden") in ("1", "true"),
            "style": js_number(r.attrs.get("s") or 0) if r.attrs.get("customFormat") in ("1", "true") else -1,
            "cells": [],
        }
        next_col = 0
        for c in xkids(r, "c"):
            ref = parse_ref(c.attrs["r"]) if c.attrs.get("r") else {"c": next_col, "r": ri}
            if ref is None or not ref["c"] < 16384:
                raise _editor().FixedRejected("Invalid xlsx cell reference")
            next_col = ref["c"] + 1
            s = js_number(c.attrs.get("s") or 0)
            t = c.attrs.get("t") or "n"
            v = xkid(c, "v")
            value = ""
            if xkid(c, "f"):
                formulas += 1
            if t == "s" and v:
                item = at(sst, js_number(v.text))
                value = item if item is not None else ""
            elif t == "inlineStr":
                value = deep_text(xkid(c, "is"))
            elif t == "str" and v:
                value = v.text
            elif t == "b" and v:
                value = "Истина" if v.text == "1" else "Ложь"
            elif t == "e":
                value = ""
            elif v and v.text != "":
                num = js_parse_float(v.text)
                xf = at(st["xfs"], s)
                if xf and is_date_format(st, xf["numFmt"]) and not math.isnan(num):
                    value = serial_to_date(num, _builtin(BUILTIN_DATE_FORMATS, xf["numFmt"]) == 2)
                elif math.isnan(num):
                    value = v.text
                else:
                    value = display_number(num, st, xf["numFmt"] if xf else 0)
            row["cells"].append({"col": ref["c"], "style": s, "text": value})
            max_col = max(max_col, ref["c"])
        if row["cells"] or row["height"] is not None or row["style"] >= 0:
            rows.append(row)
            max_row = max(max_row, ri)
    if formulas:
        warnings["formulas"] = formulas
    merges = []
    for m in xkids(xkid(ws, "mergeCells"), "mergeCell"):
        parts = str(m.attrs.get("ref") or "").split(":")
        a, b = parse_ref(parts[0]), parse_ref(parts[1] if len(parts) > 1 else parts[0])
        if not a or not b:
            continue
        max_col = max(max_col, a["c"], b["c"])
        max_row = max(max_row, a["r"], b["r"])
        merges.append(
            {"r": min(a["r"], b["r"]), "c": min(a["c"], b["c"]), "h": abs(b["r"] - a["r"]), "w": abs(b["c"] - a["c"])}
        )
    _require(max_row < GRID_LIMIT and max_col < 16384, "xlsx sheet is too large")
    if xkid(ws, "conditionalFormatting"):
        warnings["conditionalFormatting"] = True
    if xkid(ws, "dataValidations"):
        warnings["dataValidations"] = True
    drawing = xkid(ws, "drawing")
    drawing_path = (
        sheet_rels[drawing.attrs["id"]]["target"] if drawing and drawing.attrs.get("id") in sheet_rels else ""
    )
    areas = []
    print_area = None
    for n in workbook["names"]:
        if n["name"].startswith("_xlnm."):
            if n["localSheetId"] is not None and js_number(n["localSheetId"]) != sheet_index:
                continue
            if n["name"] == "_xlnm.Print_Area":
                pa = parse_defined_range(n["ref"])
                if pa and (not pa["sheet"] or pa["sheet"] == sheet["name"]):
                    print_area = pa
            elif n["name"] == "_xlnm.Print_Titles":
                warnings["printTitles"] = True
            continue
        if n["hidden"]:
            continue
        if n["localSheetId"] is not None and js_number(n["localSheetId"]) != sheet_index:
            continue
        found = parse_defined_range(n["ref"])
        if not found:
            warnings.setdefault("skippedNames", []).append(n["name"])
            continue
        if found["sheet"] and found["sheet"] != sheet["name"]:
            continue
        areas.append(
            {
                "name": n["name"],
                "type": found["type"],
                "beginRow": found["beginRow"],
                "endRow": found["endRow"],
                "beginColumn": found["beginColumn"],
                "endColumn": found["endColumn"],
            }
        )
    page_setup = xkid(ws, "pageSetup")
    header_footer = xkid(ws, "headerFooter")
    printing = None
    margins = xkid(ws, "pageMargins")
    fit = xkid(xkid(ws, "sheetPr"), "pageSetUpPr")
    if page_setup or margins:
        printing = {}
        ps = page_setup.attrs if page_setup else {}
        printing["pageOrientation"] = "Landscape" if ps.get("orientation") == "landscape" else "Portrait"
        if ps.get("scale") and 10 <= js_number(ps["scale"]) <= 400:
            printing["scale"] = js_int(js_number(ps["scale"]))
        if margins:

            def hundredths(value):
                return js_int(js_round(js_parse_float(value or "0") * 2540))

            printing["topMargin"] = hundredths(margins.attrs.get("top"))
            printing["leftMargin"] = hundredths(margins.attrs.get("left"))
            printing["bottomMargin"] = hundredths(margins.attrs.get("bottom"))
            printing["rightMargin"] = hundredths(margins.attrs.get("right"))
            if margins.attrs.get("header") is not None:
                printing["headerSize"] = hundredths(margins.attrs["header"])
            if margins.attrs.get("footer") is not None:
                printing["footerSize"] = hundredths(margins.attrs["footer"])
        printing["fitToPage"] = "true" if fit and fit.attrs.get("fitToPage") in ("1", "true") else "false"
        if ps.get("blackAndWhite") in ("1", "true"):
            printing["blackAndWhite"] = "true"
        if ps.get("paperSize") and js_number(ps["paperSize"]) > 0:
            printing["paper"] = js_int(js_number(ps["paperSize"]))
    pictures = count_pictures(book, drawing_path) if drawing_path else 0
    return {
        "sheetName": sheet["name"],
        "styles": st,
        "defColChars": def_col_chars,
        "cols": cols,
        "rows": rows,
        "merges": merges,
        "areas": areas,
        "width": max_col + 1,
        "height": max_row + 1,
        "print": printing,
        "printArea": print_area,
        "header": parse_header_footer(
            odd_header.text if header_footer and (odd_header := xkid(header_footer, "oddHeader")) else ""
        ),
        "footer": parse_header_footer(
            odd_footer.text if header_footer and (odd_footer := xkid(header_footer, "oddFooter")) else ""
        ),
        "pictures": pictures,
    }


def count_pictures(book: Workbook, drawing_path: str) -> int:
    """Drawings are not transferred; count anchors so the result can list them."""
    data = book.text(drawing_path)
    if not data:
        return 0
    return sum(
        1 for anchor in parse_xml(data).kids if anchor.name in ("twoCellAnchor", "oneCellAnchor", "absoluteAnchor")
    )


def parse_header_footer(code: str) -> dict:
    out = {}
    if not code:
        return out
    section = "center"
    pattern = re.compile(r'&([LCR])|&"([^"]*)"|&(\d+)|&([PNDTFAZG])|&([BIUSEXY])|&&|([^&]+)|&')

    def current():
        return out.setdefault(section, {"text": "", "face": "", "size": 0, "bold": False, "italic": False})

    for match in pattern.finditer(code):
        if match.group(1):
            section = {"L": "left", "C": "center", "R": "right"}[match.group(1)]
        elif match.group(2) is not None:
            parts = match.group(2).split(",")
            part = current()
            if not part["face"] and parts[0] and parts[0] != "-":
                part["face"] = parts[0]
            style = (parts[1] if len(parts) > 1 else "").lower()
            if not part["text"]:
                part["bold"] = bool(re.search("bold|полужирный", style))
                part["italic"] = bool(re.search("italic|курсив", style))
        elif match.group(3):
            if not current()["size"]:
                current()["size"] = int(match.group(3))
        elif match.group(4):
            current()["text"] += {"P": "[&НомерСтраницы]", "N": "[&СтраницВсего]", "D": "[&Дата]", "T": "[&Время]"}.get(
                match.group(4), ""
            )
        elif match.group(0) == "&&":
            current()["text"] += "&"
        elif match.group(6) is not None:
            current()["text"] += match.group(6)
    for key in list(out):
        out[key]["text"] = out[key]["text"].replace("\r\n", "\n")
        if not out[key]["text"].strip():
            del out[key]
    return out


LINE_OF = {
    "thin": (1, "Solid"),
    "medium": (2, "Solid"),
    "thick": (3, "Solid"),
    "double": (3, "Double"),
    "hair": (1, "Dotted"),
    "dotted": (1, "Dotted"),
    "dashed": (1, "ThinDashed"),
    "dashDot": (1, "ThinDashed"),
    "dashDotDot": (1, "ThinDashed"),
    "mediumDashed": (2, "ThickDashed"),
    "mediumDashDot": (2, "ThickDashed"),
    "mediumDashDotDot": (2, "ThickDashed"),
    "slantDashDot": (2, "ThickDashed"),
}
H_ALIGN = {
    "left": "Left",
    "center": "Center",
    "centerContinuous": "Center",
    "right": "Right",
    "justify": "Justify",
    "distributed": "Justify",
    "fill": "Left",
}
V_ALIGN = {"top": "Top", "center": "Center", "bottom": "Bottom", "justify": "Center", "distributed": "Center"}
PARAM_ONLY = re.compile(r"^\s*\[([^\[\]]+)\]\s*$")
PARAM_INSIDE = re.compile(r"\[[^\[\]]+\]")
WIDTH_U_PER_CHAR = 48 / 7
HEIGHT_U_PER_PT = 4
XLSX_FORMAT_ORDER = [
    "font",
    "leftBorder",
    "topBorder",
    "rightBorder",
    "bottomBorder",
    "borderColor",
    "height",
    "width",
    "horizontalAlignment",
    "drawingBorder",
    "verticalAlignment",
    "textColor",
    "backColor",
    "pattern",
    "textPlacement",
    "fillType",
    "textOrientation",
    "format",
    "indent",
]
XLSX_PRINT_ORDER = [
    "pageOrientation",
    "scale",
    "topMargin",
    "leftMargin",
    "bottomMargin",
    "rightMargin",
    "headerSize",
    "footerSize",
    "fitToPage",
    "blackAndWhite",
    "paper",
]
LF_MARK = "\x00"


def esc(value) -> str:
    text = js_str(value) if not isinstance(value, str) else value
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\n", LF_MARK)
    )


class Pool:
    def __init__(self):
        self.keys = {}
        self.items = []

    def add(self, key, item):
        if key not in self.keys:
            self.keys[key] = len(self.items)
            self.items.append(item)
        return self.keys[key]


def excel_width(chars) -> int:
    return int(max(0, js_round(chars * WIDTH_U_PER_CHAR)))


def build_template(sheet: dict, lang="ru") -> tuple[str, dict]:
    st = sheet["styles"]
    fonts, lines, formats = Pool(), Pool(), Pool()
    stats = {"parameters": [], "templates": 0}

    def font_index(f):
        face = (f and f["name"]) or "Arial"
        size = (f and f["size"]) or 10
        font = {
            "faceName": face,
            "height": js_int(float(size)),
            "bold": bool(f and f["bold"]),
            "italic": bool(f and f["italic"]),
            "underline": bool(f and f.get("underline")),
            "strikeout": bool(f and f.get("strike")),
        }
        return fonts.add(json.dumps(font, ensure_ascii=False), font)

    def line_index(border):
        spec = LINE_OF.get(border["style"], (1, "Solid"))
        return lines.add(f"{spec[0]}:{spec[1]}", {"width": spec[0], "style": spec[1]})

    def format_index(fmt):
        return formats.add(json.dumps(fmt, ensure_ascii=False), fmt) + 1

    default_xf = {
        "font": 0,
        "fill": 0,
        "border": 0,
        "h": "",
        "v": "",
        "wrap": False,
        "indent": 0,
        "rotation": 0,
        "numFmt": 0,
    }

    def cell_format(style_index, fill_type, edges, layer=False):
        xf = at(st["xfs"], style_index) or at(st["xfs"], 0) or default_xf
        f = at(st["fonts"], xf["font"])
        fmt = {"font": font_index(f)}
        border = at(st["borders"], xf["border"]) or {}
        if edges:
            border = {
                "left": border.get("left"),
                "top": border.get("top"),
                "right": edges.get("right"),
                "bottom": edges.get("bottom"),
            }
        border_color = ""
        for side, key in (
            ("left", "leftBorder"),
            ("top", "topBorder"),
            ("right", "rightBorder"),
            ("bottom", "bottomBorder"),
        ):
            if border.get(side):
                fmt[key] = line_index(border[side])
                if not border_color and border[side]["color"] and border[side]["color"] != "#000000":
                    border_color = border[side]["color"]
        if border_color:
            fmt["borderColor"] = border_color
        if xf["h"] and xf["h"] in H_ALIGN:
            fmt["horizontalAlignment"] = H_ALIGN[xf["h"]]
        if V_ALIGN.get(xf["v"]) or not layer:
            fmt["verticalAlignment"] = V_ALIGN.get(xf["v"]) or "Bottom"
        if xf["wrap"] or xf["h"] == "justify" or xf["v"] == "justify":
            fmt["textPlacement"] = "Wrap"
        if xf["indent"]:
            fmt["indent"] = js_int(xf["indent"] * 3)
        rotation = xf["rotation"]
        if 0 < rotation <= 90:
            fmt["textOrientation"] = js_int(rotation * 10)
        elif 90 < rotation <= 180:
            fmt["textOrientation"] = js_int(3600 - (rotation - 90) * 10)
        elif rotation:
            stats["rotation"] = True
        if fill_type:
            fmt["fillType"] = fill_type
        if f and f["color"] and f["color"] != "#000000":
            fmt["textColor"] = f["color"]
        fill = at(st["fills"], xf["fill"])
        if fill:
            fmt["backColor"] = fill
            fmt["pattern"] = "Solid"
        data_format = one_c_format(st, xf.get("numFmt", 0))
        if data_format:
            fmt["format"] = data_format
        return fmt

    width = max(1, sheet["width"])
    height = max(1, sheet["height"])
    first_xf = at(st["xfs"], 0) or {"font": 0}
    default_format = format_index(
        {"font": font_index(at(st["fonts"], first_xf["font"])), "width": excel_width(sheet["defColChars"])}
    )
    column_formats = []
    for c in range(width):
        col = sheet["cols"].get(c)
        chars = col["width"] if col else sheet["defColChars"]
        fmt = cell_format(col["style"], "", None, True) if col and col["style"] > 0 else {}
        fmt["width"] = 0 if col and col["hidden"] else excel_width(chars)
        column_formats.append(format_index(fmt))
    style_at = {}
    for row in sheet["rows"]:
        for cell in row["cells"]:
            style_at[(row["index"], cell["col"])] = cell["style"]

    def border_of(r, c, side):
        xf = at(st["xfs"], style_at.get((r, c), math.nan))
        border = at(st["borders"], xf["border"]) if xf else None
        return border.get(side) if border else None

    merge_edges = {
        (m["r"], m["c"]): {
            "right": border_of(m["r"], m["c"] + m["w"], "right"),
            "bottom": border_of(m["r"] + m["h"], m["c"], "bottom"),
        }
        for m in sheet["merges"]
    }
    rows_xml = []
    for row in sheet["rows"]:
        row_format = cell_format(row["style"], "", None, True) if row["style"] > 0 else {}
        if row["hidden"]:
            row_format["height"] = 0
        elif row["height"] is not None:
            row_format["height"] = int(max(1, js_round(row["height"] * HEIGHT_U_PER_PT)))
        parts = []
        expected = 0
        for cell in row["cells"]:
            text = "" if cell["text"] is None else str(cell["text"])
            fill_type = ""
            parameter = ""
            match = PARAM_ONLY.match(text)
            if match:
                fill_type = "Parameter"
                parameter = match.group(1).strip()
                stats["parameters"].append(parameter)
            elif PARAM_INSIDE.search(text):
                fill_type = "Template"
                stats["templates"] += 1
            index = format_index(cell_format(cell["style"], fill_type, merge_edges.get((row["index"], cell["col"]))))
            body = f"\t\t\t\t\t<f>{index}</f>\n"
            if parameter:
                body += f"\t\t\t\t\t<parameter>{esc(parameter)}</parameter>\n"
            elif text != "":
                body += (
                    f"\t\t\t\t\t<tl>\n\t\t\t\t\t\t<v8:item>\n\t\t\t\t\t\t\t<v8:lang>{lang}</v8:lang>\n"
                    f"\t\t\t\t\t\t\t<v8:content>{esc(text)}</v8:content>\n\t\t\t\t\t\t</v8:item>\n\t\t\t\t\t</tl>\n"
                )
            head = f"\t\t\t\t<i>{cell['col']}</i>\n" if cell["col"] != expected else ""
            parts.append(f"\t\t\t<c>\n{head}\t\t\t\t<c>\n{body}\t\t\t\t</c>\n\t\t\t</c>\n")
            expected = cell["col"] + 1
        xml = f"\t<rowsItem>\n\t\t<index>{row['index']}</index>\n\t\t<row>\n"
        if row_format:
            xml += f"\t\t\t<formatIndex>{format_index(row_format)}</formatIndex>\n"
        if not parts:
            xml += "\t\t\t<empty>true</empty>\n"
        rows_xml.append(xml + "".join(parts) + "\t\t</row>\n\t</rowsItem>\n")
    code = "Русский" if lang == "ru" else lang
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        '<document xmlns="http://v8.1c.ru/8.2/data/spreadsheet" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" '
        'xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" '
        'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n',
        f"\t<languageSettings>\n\t\t<currentLanguage>{lang}</currentLanguage>\n\t\t<defaultLanguage>{lang}</defaultLanguage>\n"
        f"\t\t<languageInfo>\n\t\t\t<id>{lang}</id>\n\t\t\t<code>{code}</code>\n\t\t\t<description>{code}</description>\n"
        "\t\t</languageInfo>\n\t</languageSettings>\n",
        f"\t<columns>\n\t\t<size>{width}</size>\n",
    ]
    for c in range(width):
        out.append(
            f"\t\t<columnsItem>\n\t\t\t<index>{c}</index>\n\t\t\t<column>\n\t\t\t\t<formatIndex>"
            f"{column_formats[c]}</formatIndex>\n\t\t\t</column>\n\t\t</columnsItem>\n"
        )
    out.append("\t</columns>\n")
    out.extend(rows_xml)
    for kind, suffix in (("header", "Header"), ("footer", "Footer")):
        parts = sheet[kind] or {}
        fallback = parts.get("left") or parts.get("center") or parts.get("right")
        if not fallback:
            continue
        for side in ("left", "center", "right"):
            part = parts.get(side)
            face = (part and part["face"]) or fallback["face"]
            size = (part and part["size"]) or fallback["size"]
            index = format_index(
                {
                    "font": font_index(
                        {
                            "name": face or "Arial",
                            "size": size or 10,
                            "bold": bool(part and part["bold"]),
                            "italic": bool(part and part["italic"]),
                        }
                    ),
                    "verticalAlignment": "Bottom",
                }
            )
            body = (
                (
                    f"\t\t<tl>\n\t\t\t<v8:item>\n\t\t\t\t<v8:lang>{lang}</v8:lang>\n\t\t\t\t<v8:content>"
                    f"{esc(part['text'])}</v8:content>\n\t\t\t</v8:item>\n\t\t</tl>\n"
                )
                if part
                else "\t\t<tl/>\n"
            )
            out.append(f"\t<{side}{suffix}>\n\t\t<f>{index}</f>\n{body}\t</{side}{suffix}>\n")
    out.append("\t<templateMode>true</templateMode>\n")
    out.append(f"\t<defaultFormatIndex>{default_format}</defaultFormatIndex>\n")
    out.append(f"\t<height>{height}</height>\n")
    out.append(f"\t<vgRows>{height}</vgRows>\n")
    for m in sheet["merges"]:
        xml = f"\t<merge>\n\t\t<r>{m['r']}</r>\n\t\t<c>{m['c']}</c>\n"
        if m["h"]:
            xml += f"\t\t<h>{m['h']}</h>\n"
        if m["w"]:
            xml += f"\t\t<w>{m['w']}</w>\n"
        out.append(xml + "\t</merge>\n")
    for a in sheet["areas"]:
        out.append(
            f'\t<namedItem xsi:type="NamedItemCells">\n\t\t<name>{esc(a["name"])}</name>\n\t\t<area>\n'
            f"\t\t\t<type>{a['type']}</type>\n\t\t\t<beginRow>{a['beginRow']}</beginRow>\n\t\t\t<endRow>{a['endRow']}</endRow>\n"
            f"\t\t\t<beginColumn>{a['beginColumn']}</beginColumn>\n\t\t\t<endColumn>{a['endColumn']}</endColumn>\n"
            "\t\t</area>\n\t</namedItem>\n"
        )
    if sheet["print"]:
        xml = "\t<printSettings>\n"
        for key in XLSX_PRINT_ORDER:
            if sheet["print"].get(key) is not None:
                xml += f"\t\t<{key}>{esc(sheet['print'][key])}</{key}>\n"
        out.append(xml + "\t</printSettings>\n")
    if sheet["printArea"]:
        area = sheet["printArea"]
        out.append(
            f"\t<printArea>\n\t\t<type>{area['type']}</type>\n\t\t<beginRow>{area['beginRow']}</beginRow>\n"
            f"\t\t<endRow>{area['endRow']}</endRow>\n\t\t<beginColumn>{area['beginColumn']}</beginColumn>\n"
            f"\t\t<endColumn>{area['endColumn']}</endColumn>\n\t</printArea>\n"
        )
    for line in lines.items:
        out.append(
            f'\t<line width="{line["width"]}" gap="false">\n\t\t<v8ui:style xsi:type="v8ui:SpreadsheetDocument'
            f'CellLineType">{line["style"]}</v8ui:style>\n\t</line>\n'
        )
    for font in fonts.items:
        out.append(
            f'\t<font faceName="{esc(font["faceName"])}" height="{js_str(font["height"])}" bold="{js_str(font["bold"])}" '
            f'italic="{js_str(font["italic"])}" underline="{js_str(font["underline"])}" '
            f'strikeout="{js_str(font["strikeout"])}" kind="Absolute" scale="100"/>\n'
        )
    for fmt in formats.items:
        xml = "\t<format>\n"
        for key in XLSX_FORMAT_ORDER:
            if fmt.get(key) is None:
                continue
            if key == "format":
                xml += (
                    f"\t\t<format>\n\t\t\t<v8:item>\n\t\t\t\t<v8:lang>{lang}</v8:lang>\n\t\t\t\t<v8:content>"
                    f"{esc(fmt[key])}</v8:content>\n\t\t\t</v8:item>\n\t\t</format>\n"
                )
            else:
                xml += f"\t\t<{key}>{esc(fmt[key])}</{key}>\n"
        out.append(xml + "\t</format>\n")
    out.append("</document>\n")
    return "".join(out), stats


def summarize(sheet, stats, warnings) -> dict:
    notes = []
    if warnings.get("formulas"):
        notes.append(f"Формулы ({warnings['formulas']}): перенесены последние вычисленные значения.")
    if warnings.get("richText"):
        notes.append("Текст с разным оформлением внутри ячейки: взято оформление ячейки.")
    if warnings.get("conditionalFormatting"):
        notes.append("Условное форматирование не переносится.")
    if warnings.get("dataValidations"):
        notes.append("Проверка данных не переносится.")
    if sheet["pictures"]:
        notes.append(f"Картинки, фигуры и диаграммы не переносятся ({sheet['pictures']}).")
    if warnings.get("skippedNames"):
        notes.append("Имена с несколькими диапазонами или #REF пропущены: " + ", ".join(warnings["skippedNames"]) + ".")
    if stats.get("rotation"):
        notes.append("Вертикальный текст «столбиком» не переносится.")
    if warnings.get("printTitles"):
        notes.append("Сквозные строки и колонки печати (Print_Titles) не переносятся — задайте их в конфигураторе.")
    areas = []
    for area in sheet["areas"]:
        entry = {"name": area["name"], "type": area["type"]}
        if area["beginRow"] >= 0:
            entry.update(beginRow=area["beginRow"] + 1, endRow=area["endRow"] + 1)
        if area["beginColumn"] >= 0:
            entry.update(beginColumn=area["beginColumn"] + 1, endColumn=area["endColumn"] + 1)
        areas.append(entry)
    return {
        "sheet": sheet["sheetName"],
        "rows": sheet["height"],
        "columns": sheet["width"],
        "merges": len(sheet["merges"]),
        "pictures": 0,
        "areas": areas,
        "parameters": stats["parameters"],
        "templateCells": stats["templates"],
        "notTransferred": notes,
    }


def convert(data: bytes, sheet_option=None, *, eol="\r\n", trailing=False, bom=True, lang="ru") -> tuple[bytes, dict]:
    workbook = open_workbook(data)
    sheets = workbook["sheets"]
    _require(sheets, "xlsx has no sheets")
    visible = [i for i, sheet in enumerate(sheets) if sheet["state"] == "visible"]
    index = visible[0] if visible else 0
    if isinstance(sheet_option, int) and not isinstance(sheet_option, bool):
        index = sheet_option
    elif isinstance(sheet_option, str) and sheet_option:
        names = [sheet["name"] for sheet in sheets]
        _require(sheet_option in names, "xlsx sheet not found", 3)
        index = names.index(sheet_option)
    _require(0 <= index < len(sheets), "xlsx sheet not found", 3)
    warnings = {}
    sheet = read_sheet(workbook, index, warnings)
    text, stats = build_template(sheet, lang)
    summary = summarize(sheet, stats, warnings)
    summary["sheets"] = [item["name"] for item in sheets]
    text = text[:-1] + (eol if trailing else "")
    text = text.replace("\n", eol).replace(LF_MARK, "\n")
    return (BOM if bom else b"") + text.encode("utf-8"), summary
