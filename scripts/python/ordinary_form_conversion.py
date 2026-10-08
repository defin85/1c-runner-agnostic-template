from __future__ import annotations

import argparse
import hashlib
import json
import ntpath
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from .common import CommandError, canonical_path, project_root, timestamp_utc, write_json
from .runtime import RuntimeProfile, load_runtime_profile, resolve_secret_value
from .v8unpack_erf_form import __version__ as V8UNPACK_VERSION
from .v8unpack_erf_form import decode_form

SUPPORTED_V8UNPACK = "1.2.6"
SUPPORTED_FORMS = {("9", "0-26"), ("12", "0-27"), ("13", "0-27")}
ELEMENT_TYPES = {
    "Label": "label",
    "Field": "input",
    "InputField": "input",
    "SelectField": "input",
    "CheckBox": "check",
    "RadioBtn": "radio",
    "Indicator": "progress",
    "Group": "group",
    "Panel": "group",
    "CommandPanel": "cmdBar",
    "Table": "table",
    "TableField": "spreadsheet",
    "Button": "button",
}
ROOT_FILES = {"ExternalDataProcessor.json": "ExternalDataProcessor", "ExternalReport.json": "ExternalReport"}
REPORT_STATUSES = {
    "analyzed",
    "structure-converted",
    "structure-converted-with-warnings",
    "structure-remediation-required",
    "agent-remediation-required",
    "ready",
    "failed",
}
SECRET_VALUE = re.compile(r"(?i)(\b(?:pwd|password|usr|user)\s*=\s*)([^;\s]+)")
MD_NS = "http://v8.1c.ru/8.3/MDClasses"
V8_NS = "http://v8.1c.ru/8.1/data/core"
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
OPAQUE_FORM_TYPES = {
    "acf6192e-81ca-46ef-93a6-5a6968b78663": "ValueTable",
    "bb356e79-e8e6-4912-8561-ad29cca2604f": "CatalogRef.Пользователи",
    "6cb9f3e2-00cb-4e6e-9f35-618d6eac528f": "CatalogRef.БанковскиеСчета",
    "9f6206b2-1ed6-423c-9b08-fd4978930c49": "CatalogRef.Контрагенты",
    "c92a1124-c41e-42a4-bda7-3bbac9c6039e": "CatalogRef.Организации",
    "6f58a5c7-f511-498f-abeb-390cf5afab39": "ChartOfAccountsRef.Хозрасчетный",
    "5e6e9630-024b-4b36-a35c-0d3729ad2b37": "CatalogRef.ПрочиеДоходыИРасходы",
    "57289853-6dd7-4527-87a8-a23fa8981f5f": "DocumentRef.ПоступлениеТоваровУслуг",
    "f5c65050-3bbb-11d5-b988-0050bae0a95d": "TypeDescription",
}


@dataclass(frozen=True)
class SourceForm:
    name: str
    directory: Path
    metadata: dict[str, Any]
    elements: dict[str, Any]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _input_sha(path: Path) -> str:
    if path.is_file():
        return _sha(path)
    digest = hashlib.sha256()
    for item in sorted(
        (entry for entry in path.rglob("*") if entry.is_file()), key=lambda entry: entry.relative_to(path).as_posix()
    ):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(_sha(item).encode("ascii"))
    return digest.hexdigest()


def _managed_source_sha(root_xml: Path, object_tree: Path) -> str:
    digest = hashlib.sha256()
    files = [root_xml, *(entry for entry in object_tree.rglob("*") if entry.is_file())]
    for item in sorted(
        files,
        key=lambda entry: (
            entry.name if entry == root_xml else f"{object_tree.name}/{entry.relative_to(object_tree).as_posix()}"
        ),
    ):
        relative = item.name if item == root_xml else f"{object_tree.name}/{item.relative_to(object_tree).as_posix()}"
        digest.update(relative.encode("utf-8"))
        digest.update(item.read_bytes())
    return digest.hexdigest()


def _redact(value: object) -> object:
    if isinstance(value, str):
        return SECRET_VALUE.sub(r"\1<redacted>", value)
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    return value


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _safe_windows_segment(value: object) -> str:
    segment = "".join("_" if ord(char) < 32 or char in '<>:"/\\|?*' else char for char in str(value).strip()).rstrip(
        " ."
    )
    if not segment or segment in {".", ".."}:
        return "_"
    if segment.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        return f"_{segment}"
    return segment


def _available_windows_name(name: object, occupied: set[str]) -> str:
    safe_name = _safe_windows_segment(name)
    occupied_casefold = {item.casefold() for item in occupied}
    if safe_name.casefold() not in occupied_casefold:
        return safe_name
    stem, extension = ntpath.splitext(safe_name)
    index = 2
    while True:
        candidate = f"{stem} ({index}){extension}"
        if candidate.casefold() not in occupied_casefold:
            return candidate
        index += 1


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CommandError(f"invalid JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CommandError(f"JSON root must be an object: {path}")
    return value


def _v8unpack_python(tool: str) -> Path:
    executable = Path(shutil.which(tool) or tool)
    if not executable.is_file():
        raise CommandError(f"v8unpack executable not found: {tool}")
    data = executable.read_bytes()
    match = re.search(rb'#!"?([^"\r\n]*python(?:\d+(?:\.\d+)*)?(?:\.exe)?)"?', data)
    if not match:
        # uv/pip write a /bin/sh trampoline when the interpreter path exceeds
        # the kernel shebang limit: #!/bin/sh + '''exec' '<python>' "$0" "$@".
        match = re.match(rb"#!/bin/sh\r?\n'''exec' '([^'\r\n]*python(?:\d+(?:\.\d+)*)?)' \"\$0\" \"\$@\"", data)
    if not match:
        raise CommandError(f"cannot resolve Python runtime used by v8unpack: {executable}")
    runtime = Path(os.fsdecode(match.group(1)))
    if not runtime.is_file():
        raise CommandError(f"v8unpack Python runtime not found: {runtime}")
    return runtime


def _extract_erf(input_path: Path, destination: Path, tool: str, profile_path: Path, run_root: Path) -> Path:
    designer_root = run_root / "designer-source"
    _dump_object_source(input_path, designer_root, profile_path, run_root, tool, "ExternalReport")
    helper = project_root() / "scripts/python/v8unpack_erf_form.py"
    completed = subprocess.run(
        [str(_v8unpack_python(tool)), str(helper), str(designer_root), str(destination)],
        cwd=project_root(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode:
        raise CommandError(
            f"ERF form extraction failed: {(completed.stderr or completed.stdout).strip()}", completed.returncode
        )
    return destination


def _extract(
    input_path: Path, destination: Path, tool: str, profile_path: Path | None = None, run_root: Path | None = None
) -> Path:
    if input_path.is_dir():
        return input_path
    if input_path.suffix.lower() not in {".epf", ".erf"}:
        raise CommandError("input must be an EPF, ERF, or a v8unpack directory")
    if input_path.suffix.lower() == ".erf":
        if profile_path is None or run_root is None:
            raise CommandError("ERF extraction requires --profile for Designer XML dump")
        return _extract_erf(input_path, destination, tool, profile_path, run_root)
    command = [tool, "-E", str(input_path), str(destination)]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode:
        raise CommandError(f"v8unpack extract failed: {completed.stderr.strip()}", completed.returncode)
    return destination


def _read_source(root: Path) -> tuple[str, dict[str, Any], list[SourceForm]]:
    roots = [(path, kind) for filename, kind in ROOT_FILES.items() if (path := root / filename).is_file()]
    if len(roots) != 1:
        raise CommandError("v8unpack tree must contain exactly one supported root JSON")
    root_path, kind = roots[0]
    metadata = _load_object(root_path)
    if metadata.get("root") is not True or metadata.get("v8unpack") != SUPPORTED_V8UNPACK:
        raise CommandError(f"unsupported v8unpack tree version; expected {SUPPORTED_V8UNPACK}")
    forms_root = root / "Form"
    forms: list[SourceForm] = []
    if not forms_root.is_dir():
        if kind == "ExternalReport":
            return kind, metadata, forms
        raise CommandError("v8unpack tree has no Form directory")
    for directory in sorted((item for item in forms_root.iterdir() if item.is_dir()), key=lambda item: item.name):
        required = [directory / name for name in ("Form.json", "Form.elem.json", "Form.id.json", "Form.obj.bsl")]
        missing = [path.name for path in required if not path.is_file()]
        if missing:
            raise CommandError(f"form {directory.name} is missing: {', '.join(missing)}")
        form_meta = _load_object(required[0])
        elements = _load_object(required[1])
        if (str(form_meta.get("obj_version")), str(form_meta.get("Версия элементов формы"))) not in SUPPORTED_FORMS:
            raise CommandError(f"unsupported ordinary form schema: {directory.name}")
        if set(elements) != {"params", "props", "commands", "tree", "data"}:
            raise CommandError(f"unexpected Form.elem.json schema: {directory.name}")
        forms.append(SourceForm(str(form_meta.get("name") or directory.name), directory, form_meta, elements))
    return kind, metadata, forms


def _procedures(module: Path) -> list[dict[str, object]]:
    text = module.read_text(encoding="utf-8-sig", errors="replace")
    pattern = re.compile(r"(?im)^\s*(?:&\S+\s*)*(Процедура|Функция)\s+([\wА-Яа-яЁё]+)\s*\(")
    return [
        {"kind": match.group(1), "name": match.group(2), "line": text.count("\n", 0, match.start()) + 1}
        for match in pattern.finditer(text)
    ]


def _at(value: object, *indexes: int) -> object:
    """Index a nested raw Form.bin tree; raises IndexError/TypeError/KeyError exactly like direct indexing."""
    current: Any = value
    for index in indexes:
        current = current[index]
    return current


def _raw_strings(value: object) -> list[str]:
    result: list[str] = []
    if isinstance(value, str):
        decoded = value[1:-1] if len(value) >= 2 and value.startswith('"') and value.endswith('"') else value
        if decoded and decoded not in result:
            result.append(decoded)
    elif isinstance(value, list):
        for item in value:
            for decoded in _raw_strings(item):
                if decoded not in result:
                    result.append(decoded)
    elif isinstance(value, dict):
        for item in value.values():
            for decoded in _raw_strings(item):
                if decoded not in result:
                    result.append(decoded)
    return result


def _table_column_titles(raw: object, column_names: list[str]) -> dict[str, str]:
    def fallback() -> dict[str, str]:
        strings = _raw_strings(raw)
        return {
            name: next(
                (value for value in strings if re.sub(r"[^А-Яа-яЁё0-9]", "", value).casefold() == name.casefold()),
                name,
            )
            for name in column_names
        }

    try:
        entries = _at(raw, 2, 2, 1, 23)
    except (IndexError, TypeError):
        entries = None
    if entries is None:
        return fallback()
    if not isinstance(entries, list) or not entries or not str(entries[0]).isdigit():
        return fallback()
    titles: dict[str, str] = {}
    for entry in entries[1:]:
        try:
            payload = entry[1][1][1]
            name = _raw_strings(payload[30])
            title = _raw_strings(payload[1])
        except (IndexError, TypeError):
            raise CommandError("unsupported ordinary table column presentation") from None
        if len(name) != 1 or name[0] in titles:
            raise CommandError("unsupported ordinary table column presentation")
        if name[0] not in column_names:
            continue
        titles[name[0]] = next((title[index + 1] for index, value in enumerate(title[:-1]) if value == "ru"), name[0])
    return titles or fallback()


def _russian_presentation(raw: object) -> str | None:
    strings = _raw_strings(raw)
    for index, value in enumerate(strings[:-1]):
        if value == "ru" and re.search(r"[А-Яа-яЁё]", strings[index + 1]):
            return strings[index + 1]
    return None


def _command_panel_action_source(raw: object, panel_name: str) -> str | None:
    if not isinstance(raw, list):
        return None
    for item in raw:
        if not isinstance(item, list) or len(item) < 3 or str(item[0]) != "14":
            continue
        if _raw_strings(item[1]) == [panel_name] and str(item[2]).isdigit() and str(item[2]) != "0":
            return str(item[2])
    return None


def _text_color(raw: object) -> str | None:
    try:
        color = _at(raw, 2, 1, 0, 3)
        value = int(str(_at(color, 2, 0)))
    except (IndexError, TypeError, ValueError):
        return None
    if not isinstance(color, list) or len(color) < 3 or str(color[0]) != "3" or str(color[1]) != "0":
        return None
    return f"#{value & 0xFF:02X}{value >> 8 & 0xFF:02X}{value >> 16 & 0xFF:02X}"


def _command_panel_buttons(raw: object, procedure_names: set[str]) -> list[tuple[str, str, str]] | None:
    def single_handler() -> list[tuple[str, str, str]] | None:
        handlers = list(dict.fromkeys(value for value in _raw_strings(raw) if value in procedure_names))
        if len(handlers) != 1:
            return None
        handler = handlers[0]
        command = handler.removesuffix("Нажатие")
        title = (
            _russian_presentation(raw)
            or re.sub(r"(?<!^)([А-ЯЁ])", r" \1", command.removeprefix("Кнопка")).strip()
            or command
        )
        return [(command, title, handler)]

    def legacy() -> list[tuple[str, str, str]] | None:
        try:
            items = _at(raw, 2, 1, 7, 9)
        except (IndexError, TypeError):
            return None
        if not isinstance(items, list):
            return None
        titles: list[tuple[str, str]] = []
        for item in items:
            if not isinstance(item, list) or len(item) < 5 or str(item[0]) != "8":
                continue
            names, title = _raw_strings(item[1]), _raw_strings(item[4])
            if len(title) < 2 or title[-2] != "ru":
                continue
            if len(names) != 1:
                return None
            titles.append((names[0], title[-1]))
        result = []
        for handler in dict.fromkeys(value for value in _raw_strings(raw) if value in procedure_names):
            command = handler.removesuffix("Нажатие")
            matches = [(name, title) for name, title in titles if name.endswith(command.removeprefix("Кнопка"))]
            if len(matches) != 1:
                return None
            result.append((command, matches[0][1], handler))
        return result

    try:
        payload = _at(raw, 2, 1, 7)
    except (IndexError, TypeError):
        return legacy() or single_handler()
    if not isinstance(payload, list):
        return legacy() or single_handler()
    definitions = {
        item[1]: item
        for item in payload
        if isinstance(item, list) and len(item) > 4 and str(item[0]) in {"6", "7"} and isinstance(item[1], str)
    }
    presentation = next(
        (
            item
            for item in reversed(payload)
            if isinstance(item, list)
            and item
            and str(item[0]) == "5"
            and any(isinstance(child, list) and child and str(child[0]) == "8" for child in item)
        ),
        None,
    )
    if presentation is None:
        direct: list[tuple[str, str, str]] = []
        for definition in definitions.values():
            handlers = (
                [value for value in _raw_strings(definition[4][1]) if value in procedure_names]
                if isinstance(definition[4], list)
                else []
            )
            if not handlers:
                continue
            if len(handlers) != 1:
                return None
            try:
                title = _raw_strings(definition[6][2][1])
            except (IndexError, TypeError):
                title = []
            if not title:
                try:
                    title = _raw_strings(definition[4][2][2])
                except (IndexError, TypeError):
                    return None
            if not title:
                return None
            direct.append((handlers[0].removesuffix("Нажатие"), title[-1], handlers[0]))
        return direct or legacy() or single_handler()
    buttons: list[tuple[str, str, str]] = []
    for index in range(len(presentation) - 1):
        identifier, item = presentation[index : index + 2]
        if not isinstance(identifier, str) or not isinstance(item, list) or not item or str(item[0]) != "8":
            continue
        definition = definitions.get(identifier)
        if definition is None:
            continue
        names = _raw_strings(item[1])
        title = _raw_strings(item[4])
        if len(title) < 2 or title[-2] != "ru":
            continue
        if len(names) != 1:
            return None
        handlers = [value for value in _raw_strings(definition[4]) if value in procedure_names]
        if len(handlers) > 1:
            return None
        if handlers:
            buttons.append((handlers[0].removesuffix("Нажатие"), title[-1], handlers[0]))
    return buttons or legacy() or single_handler()


def _command_panel_tree(raw: object, procedure_names: set[str]) -> list[dict[str, object]] | None:
    try:
        payload = _at(raw, 2, 1, 7)
    except (IndexError, TypeError):
        return None
    if not isinstance(payload, list):
        return None
    definitions = {
        item[1]: item
        for item in payload
        if isinstance(item, list) and len(item) > 4 and str(item[0]) in {"6", "7"} and isinstance(item[1], str)
    }
    groups = {
        item[1]: item
        for item in payload
        if isinstance(item, list) and len(item) > 5 and str(item[0]) == "5" and isinstance(item[1], str)
    }
    referenced = {
        str(definition[4][1])
        for group in groups.values()
        for identifier in group
        if isinstance(identifier, str)
        for definition in [definitions.get(identifier)]
        if definition is not None
        and isinstance(definition[4], list)
        and len(definition[4]) > 1
        and str(definition[4][1]) in groups
    }
    roots = [identifier for identifier in groups if identifier not in referenced]
    if len(roots) != 1:
        return None

    def title(item: list[object]) -> str | None:
        values = _raw_strings(item[4]) if len(item) > 4 else []
        return values[-1] if len(values) >= 2 and values[-2] == "ru" else None

    def standard_picture(definition: list[object]) -> str | None:
        if not definition or str(definition[0]) not in {"6", "7"}:
            return None
        try:
            return {"-10": "StdPicture.CheckAll", "-11": "StdPicture.UncheckAll"}.get(str(_at(definition, 6, 2, 0)))
        except (IndexError, TypeError):
            return None

    def children(group_id: str, seen: set[str]) -> list[dict[str, object]] | None:
        if group_id in seen:
            return None
        group = groups[group_id]
        result: list[dict[str, object]] = []
        for index in range(len(group) - 1):
            identifier, item = group[index : index + 2]
            if not isinstance(identifier, str) or not isinstance(item, list) or not item or str(item[0]) != "8":
                continue
            item_title = title(item)
            names = _raw_strings(item[1])
            definition = definitions.get(identifier)
            if item_title is None and definition is not None:
                item_title = _russian_presentation(definition)
            nested_id = (
                str(definition[4][1])
                if definition is not None and isinstance(definition[4], list) and len(definition[4]) > 1
                else ""
            )
            if nested_id in groups:
                nested = children(nested_id, {*seen, group_id})
                if len(names) != 1 or not item_title or not nested:
                    return None
                result.append({"popup": names[0], "title": item_title, "children": nested})
                continue
            if definition is not None:
                handlers = [value for value in _raw_strings(definition[4]) if value in procedure_names]
                if not handlers:
                    continue
                if len(handlers) != 1 or len(names) != 1 or not item_title:
                    return None
                command = handlers[0].removesuffix("Нажатие")
                button: dict[str, object] = {
                    "button": command,
                    "command": command,
                    "title": item_title,
                    "_action": handlers[0],
                }
                picture = standard_picture(definition)
                if picture:
                    button.update({"picture": picture, "representation": "picture"})
                result.append(button)
                continue
        return result

    return children(roots[0], set())


def _radio_choice(raw: object) -> tuple[str, str, str] | None:
    try:
        element = _at(raw, 2)
        title = _raw_strings(_at(element, 2, 0, 2, 2))
        value = _at(element, 4)
    except (IndexError, TypeError):
        return None
    value_types = _raw_strings(value[:1]) if isinstance(value, list) else []
    decoded_value = _raw_strings(value[1]) if isinstance(value, list) and len(value) == 2 else []
    if len(title) != 2 or title[0] != "ru" or len(decoded_value) != 1 or value_types not in (["N"], ["B"], ["S"]):
        return None
    return title[1], decoded_value[0], {"N": "number", "B": "boolean", "S": "string"}[value_types[0]]


def _input_choice_list(raw: object) -> list[dict[str, str]]:
    try:
        source_items = _at(raw, 2, 1, 26, 2, 6)
    except (IndexError, TypeError):
        return []
    if not isinstance(source_items, list) or len(source_items) < 2 or str(source_items[0]) != "1":
        return []
    result: list[dict[str, str]] = []
    for source_item in source_items[2:]:
        try:
            value = _raw_strings(source_item[3])
            presentation = _raw_strings(source_item[4])
        except (IndexError, TypeError):
            return []
        if len(value) != 2 or len(presentation) < 2 or presentation[-2] != "ru" or value[0] not in {"S", "N", "B"}:
            return []
        result.append(
            {
                "title": presentation[-1],
                "value": value[1],
                "type": {"S": "string", "N": "number", "B": "boolean"}[value[0]],
            }
        )
    return result


def _form_events(raw: object) -> list[tuple[str, str]] | None:
    try:
        records = _at(raw, 0, 0, 4)
    except (IndexError, TypeError):
        return None
    if not isinstance(records, list):
        return None
    events: list[tuple[str, str]] = []
    for record in records[1:]:
        if not isinstance(record, list) or len(record) < 3 or str(record[0]) != "70001":
            continue
        handlers = _raw_strings(record[2][1]) if isinstance(record[2], list) and len(record[2]) > 1 else []
        if len(handlers) != 1:
            return None
        events.append(("OnOpen", handlers[0]))
    return events


def _rectangle(record: dict[str, object]) -> tuple[int, int, int, int] | None:
    raw = record.get("raw")
    if not isinstance(raw, list) or len(raw) < 4 or not isinstance(raw[3], list):
        return None
    geometry = raw[3]
    if len(geometry) < 5 or str(geometry[0]) != "8":
        return None
    try:
        values = tuple(int(str(value)) for value in geometry[1:5])
    except ValueError:
        return None
    return values if len(values) == 4 else None


def _arrange_page(
    items: list[tuple[dict[str, object], tuple[int, int, int, int] | None, int]],
) -> list[dict[str, object]]:
    def order(item: tuple[dict[str, object], tuple[int, int, int, int] | None, int]) -> tuple[int, int, int]:
        rect = item[1]
        if "cmdBar" in item[0]:
            return (-1, 0, item[2])
        return (rect[1], rect[0], item[2]) if rect else (10**9, 1 if "cmdBar" in item[0] else 0, item[2])

    groups = [item for item in items if item[0].get("group") in {"vertical", "horizontal"}]
    owners: dict[int, int] = {}
    for _element, rect, index in items:
        if rect is None:
            continue
        left, top_edge, right, bottom = rect
        candidates: list[tuple[int, int]] = []
        for _group, group_rect, group_index in groups:
            if group_rect is None or group_index == index:
                continue
            group_left, group_top, group_right, group_bottom = group_rect
            group_area = (group_right - group_left) * (group_bottom - group_top)
            area = (right - left) * (bottom - top_edge)
            if (
                group_area > area
                and group_left <= left
                and group_top <= top_edge
                and right <= group_right
                and bottom <= group_bottom
            ):
                candidates.append((group_area, group_index))
        if candidates:
            owners[index] = min(candidates)[1]
    by_group = {group[2]: [] for group in groups}
    top: list[tuple[dict[str, object], tuple[int, int, int, int] | None, int]] = []
    for item in items:
        owner = owners.get(item[2])
        (by_group[owner] if owner is not None else top).append(item)
    for group, _rect, index in groups:
        children = sorted(by_group[index], key=order)
        if children:
            positioned = [child[1] for child in children if child[1] is not None]
            if len(positioned) > 1:
                horizontal = max(rect[1] for rect in positioned) < min(rect[3] for rect in positioned)
                group["group"] = "horizontal" if horizontal else "vertical"
            group["children"] = _arrange_page(children)

    paired_rows: list[tuple[dict[str, object], tuple[int, int, int, int], int, set[int]]] = []
    for label, label_rect, label_index in top:
        if label_rect is None or "label" not in label:
            continue
        matches = [
            item
            for item in top
            if item[1] is not None
            and "input" in item[0]
            and label_rect[1] < item[1][3]
            and item[1][1] < label_rect[3]
            and label_rect[2] <= item[1][0]
        ]
        if len(matches) != 1:
            continue
        field, field_rect, field_index = matches[0]
        assert field_rect is not None  # matches excludes unpositioned fields
        paired_rows.append(
            (
                {
                    "group": "horizontal",
                    "name": f"Строка{label_index}",
                    "showTitle": False,
                    "verticalStretch": False,
                    "children": [label, field],
                },
                (label_rect[0], min(label_rect[1], field_rect[1]), field_rect[2], max(label_rect[3], field_rect[3])),
                label_index,
                {label_index, field_index},
            )
        )
    for first_row in paired_rows:
        aligned = [row for row in paired_rows if row[1][0] == first_row[1][0] and row[1][2] == first_row[1][2]]
        aligned.sort(key=lambda row: row[1][1])
        if len(aligned) < 2 or any(left[1][3] > right[1][1] for left, right in zip(aligned, aligned[1:], strict=False)):
            continue
        member_indexes = set().union(*(row[3] for row in aligned))
        neighbors = [item for item in top if item[2] not in member_indexes and item[1] is not None]
        if not any(
            item[1] is not None
            and (item[1][2] <= first_row[1][0] or aligned[0][1][2] <= item[1][0])
            and sum(row[1][1] < item[1][3] and item[1][1] < row[1][3] for row in aligned) >= 2
            for item in neighbors
        ):
            continue
        top = [item for item in top if item[2] not in member_indexes]
        top.append(
            (
                {
                    "group": "horizontal",
                    "name": f"Колонка{aligned[0][2]}",
                    "showTitle": False,
                    "children": [
                        {
                            "group": "vertical",
                            "name": f"КолонкаПодписей{aligned[0][2]}",
                            "showTitle": False,
                            "children": [cast(list[dict[str, object]], row[0]["children"])[0] for row in aligned],
                        },
                        {
                            "group": "vertical",
                            "name": f"КолонкаПолей{aligned[0][2]}",
                            "showTitle": False,
                            "children": [cast(list[dict[str, object]], row[0]["children"])[1] for row in aligned],
                        },
                    ],
                },
                (aligned[0][1][0], aligned[0][1][1], aligned[0][1][2], aligned[-1][1][3]),
                aligned[0][2],
            )
        )
        break
    arranged: list[dict[str, object]] = []
    pending = sorted(top, key=order)
    while pending:
        first = pending.pop(0)
        first_rect = first[1]
        row = [first]
        while (
            "cmdBar" not in first[0]
            and first_rect is not None
            and pending
            and pending[0][1] is not None
            and pending[0][1][1] < min(cast(tuple[int, int, int, int], item[1])[3] for item in row)
        ):
            row.append(pending.pop(0))
        if len(row) == 1 and first_rect is not None and "label" in first[0]:
            matches = [
                item
                for item in pending
                if item[1] is not None
                and "input" in item[0]
                and first_rect[1] < item[1][3]
                and item[1][1] < first_rect[3]
                and first_rect[2] <= item[1][0]
            ]
            if len(matches) == 1:
                pending.remove(matches[0])
                row.append(matches[0])
        if len(row) == 1 or any("cmdBar" in item[0] for item in row):
            arranged.extend(item[0] for item in row)
        else:
            row_name = (
                f"СтрокаСКолонкой{row[0][2]}"
                if any(str(item[0].get("name", "")).startswith("Колонка") for item in row)
                else f"Строка{row[0][2]}"
            )
            arranged.append(
                {
                    "group": "horizontal",
                    "name": row_name,
                    "showTitle": False,
                    "verticalStretch": False,
                    "children": [
                        item[0]
                        for item in sorted(row, key=lambda item: (cast(tuple[int, int, int, int], item[1])[0], item[2]))
                    ],
                }
            )
    return arranged


def _form_dsl(
    form: SourceForm,
    procedure_names: set[str],
    object_kind: str,
    object_name: str,
    object_entities: list[dict[str, object]] | None = None,
) -> tuple[dict[str, object], list[dict[str, str]], dict[str, int], list[dict[str, str]]]:
    tree = form.elements["tree"]
    props = form.elements["props"]
    commands = form.elements["commands"]
    data = form.elements["data"]
    if (
        not isinstance(tree, list)
        or not isinstance(props, list)
        or not isinstance(commands, list)
        or not isinstance(data, dict)
    ):
        raise CommandError(f"invalid entity arrays in form {form.name}")
    tree_entries: list[tuple[object, str, str, str | None]] = []

    def collect(items: list[object], prefix: str = "", path_prefix: str = "element", parent: str | None = None) -> None:
        for index, item in enumerate(items):
            path = f"form/{form.name}/{path_prefix}/{index}"
            if not isinstance(item, dict):
                tree_entries.append((item, "", path, parent))
                continue
            page = item.get("page")
            name = item.get("name")
            data_key = "/".join(part for part in (prefix, page, name) if isinstance(part, str) and part)
            tree_entries.append((item, data_key, path, parent))
            children = item.get("child")
            if isinstance(children, list):
                collect(children, data_key, f"{path_prefix}/{index}/child", data_key)

    collect(tree)
    diagnostics: list[dict[str, str]] = []
    outcomes: list[dict[str, str]] = []
    attributes: list[dict[str, object]] = []
    form_attribute_names: set[str] = set()
    main_attribute = "ОбработкаОбъект" if object_kind == "ExternalDataProcessor" else "ОтчетОбъект"
    object_attributes = {str(item["name"]) for item in object_entities or [] if item.get("kind") == "attribute"}
    object_attribute_types = {
        str(item["name"]): item.get("type") for item in object_entities or [] if item.get("kind") == "attribute"
    }
    object_tables = {str(item["name"]) for item in object_entities or [] if item.get("kind") == "tabular-section"}
    object_columns = {
        table: [
            str(item["name"])
            for item in object_entities or []
            if item.get("kind") == "column" and item.get("owner") == table
        ]
        for table in object_tables
    }
    form_tables: dict[str, list[str]] = {}
    form_table_titles: dict[str, dict[str, str]] = {}
    for item, data_key, _path, _parent in tree_entries:
        record = data.get(data_key)
        if not isinstance(item, dict) or item.get("type") != "Table" or not isinstance(record, dict):
            continue
        name = item.get("name")
        if isinstance(name, str):
            table_name = (
                name
                if name in object_tables
                else next(iter(object_tables))
                if object_entities is not None and len(object_tables) == 1
                else None
            )
            column_candidates = (
                object_columns[table_name]
                if table_name
                else [
                    value
                    for value in _raw_strings(record.get("raw"))
                    if value not in {name, "НомерСтроки"}
                    and value not in procedure_names
                    and re.fullmatch(r"[А-Яа-яЁё_]\w*", value)
                ]
            )
            form_table_titles[name] = _table_column_titles(record.get("raw"), column_candidates)
            form_tables[name] = column_candidates if table_name else list(form_table_titles[name])
            binding = record.get("prop")
            if isinstance(binding, str) and binding != main_attribute:
                form_tables[binding] = form_tables[name]
                form_table_titles[binding] = form_table_titles[name]
    form_attribute_types: dict[str, str] = {}
    for index, item in enumerate(props):
        path = f"form/{form.name}/property/{index}"
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            diagnostics.append({"code": "unsupported-property", "path": path})
            outcomes.append({"category": "property", "path": path, "outcome": "manual"})
            continue
        if item["name"] != main_attribute:
            if item["name"] in form_tables:
                attributes.append(
                    {
                        "name": item["name"],
                        "type": "ValueTable",
                        "columns": [
                            {
                                "name": name,
                                **(
                                    {"title": form_table_titles[item["name"]][name]}
                                    if name in form_table_titles[item["name"]]
                                    else {}
                                ),
                            }
                            for name in form_tables[item["name"]]
                        ],
                    }
                )
                form_attribute_names.add(item["name"])
                form_attribute_types[item["name"]] = "ValueTable"
                outcomes.append({"category": "property", "path": path, "outcome": "converted"})
                continue
            raw_types = set(_raw_strings(item.get("raw")))
            for record in data.values():
                if isinstance(record, dict) and record.get("prop") == item["name"]:
                    raw_types.update(_raw_strings(record.get("raw")))
            scalar_types = {
                marker: target
                for marker, target in {"D": "date", "S": "string", "N": "number", "B": "boolean"}.items()
                if marker in raw_types
            }
            opaque_types = {value for marker, value in OPAQUE_FORM_TYPES.items() if marker in raw_types}
            if "Pattern" in raw_types and len(scalar_types) + len(opaque_types) <= 1:
                attribute_type = next(iter(scalar_types.values() or opaque_types), "")
                if attribute_type:
                    attributes.append({"name": item["name"], "type": attribute_type})
                    form_attribute_names.add(item["name"])
                    form_attribute_types[item["name"]] = attribute_type
                    outcomes.append({"category": "property", "path": path, "outcome": "converted"})
                    continue
            diagnostics.append({"code": "unsupported-form-property", "path": path, "name": str(item["name"])})
            outcomes.append({"category": "property", "path": path, "outcome": "manual"})
            continue
        attributes.append({"name": main_attribute, "type": f"{object_kind}Object.{object_name}", "main": True})
        form_attribute_names.add(main_attribute)
        outcomes.append({"category": "property", "path": path, "outcome": "converted"})
    if object_entities is not None and main_attribute not in form_attribute_names:
        attributes.append({"name": main_attribute, "type": f"{object_kind}Object.{object_name}", "main": True})
        form_attribute_names.add(main_attribute)
    if not attributes:
        diagnostics.append({"code": "missing-main-object-property", "path": f"form/{form.name}/property"})
    output_elements: list[dict[str, object]] = []
    output_pages: list[str] = []
    output_rectangles: list[tuple[int, int, int, int] | None] = []
    output_indexes: list[int] = []
    output_keys: list[str] = []
    output_parents: list[str | None] = []
    panel_pages: dict[str, list[str]] = {}
    output_commands: list[dict[str, str]] = []
    command_actions: dict[str, str] = {}

    def register_command(name: str, action: str) -> bool:
        current = command_actions.get(name)
        if current is None:
            command_actions[name] = action
            output_commands.append({"name": name, "action": action})
            return True
        return current == action

    trailing_command_bars: list[
        tuple[dict[str, object], str, tuple[int, int, int, int] | None, int, str, str | None]
    ] = []
    label_titles: dict[int, str] = {}
    for index, (item, data_key, _path, _parent) in enumerate(tree_entries):
        if not isinstance(item, dict) or item.get("type") != "Label":
            continue
        record = data.get(data_key)
        if isinstance(record, dict):
            strings = _raw_strings(record.get("raw"))
            title = next(
                (value for value in strings if re.search(r"[А-Яа-яЁё]", value) and value != item.get("name")), ""
            )
            if title:
                label_titles[index] = title
    fields = []
    for index, (item, data_key, path, parent) in enumerate(tree_entries):
        record = data.get(data_key)
        rectangle = _rectangle(record) if isinstance(record, dict) else None
        if (
            isinstance(item, dict)
            and item.get("type") in {"Field", "InputField", "SelectField"}
            and rectangle is not None
        ):
            fields.append((index, item, path, parent, rectangle))
    field_labels: set[int] = set()
    field_label_titles: dict[int, str] = {}
    for field_index, field, field_path, field_parent, field_rect in fields:
        candidates: list[int] = []
        for label_index in label_titles:
            label, label_key, _label_path, label_parent = tree_entries[label_index]
            label_record = data.get(label_key)
            label_rect = _rectangle(label_record) if isinstance(label_record, dict) else None
            if not isinstance(label, dict) or label_rect is None:
                continue
            same_row = label_rect[1] < field_rect[3] and field_rect[1] < label_rect[3]
            field_between = any(
                other_index != field_index
                and other.get("page") == field.get("page")
                and other_parent == field_parent
                and label_rect[2] <= other_rect[0]
                and other_rect[2] <= field_rect[0]
                and other_rect[1] < field_rect[3]
                and field_rect[1] < other_rect[3]
                for other_index, other, _other_path, other_parent, other_rect in fields
            )
            if (
                label.get("page") == field.get("page")
                and label_parent == field_parent
                and same_row
                and label_rect[2] <= field_rect[0]
                and not field_between
            ):
                candidates.append(label_index)
        presentation_outcome = "converted" if len(candidates) == 1 else "manual"
        if len(candidates) == 1:
            field_labels.add(field_index)
            field_label_titles[field_index] = label_titles[candidates[0]]
        elif len(candidates) > 1:
            diagnostics.append({"code": "ambiguous-field-label", "path": field_path})
        if candidates:
            outcomes.extend(
                (
                    {
                        "category": "presentation",
                        "path": f"{field_path}/presentation/separate-label",
                        "outcome": presentation_outcome,
                    },
                    {
                        "category": "presentation",
                        "path": f"{field_path}/presentation/field-title",
                        "outcome": presentation_outcome,
                    },
                )
            )
    for index, (item, data_key, path, parent) in enumerate(tree_entries):
        if not isinstance(item, dict) or not all(isinstance(item.get(key), str) for key in ("name", "type", "page")):
            diagnostics.append({"code": "invalid-element", "path": path})
            outcomes.append({"category": "element", "path": path, "outcome": "manual"})
            continue
        source_type = str(item["type"])
        target_type = ELEMENT_TYPES.get(source_type)
        if target_type is None:
            source_record = data.get(data_key)
            decorative_image = (
                source_type == "Image"
                and isinstance(source_record, dict)
                and not source_record.get("prop")
                and not any(value in procedure_names for value in _raw_strings(source_record.get("raw")))
            )
            if source_type == "Separator" or decorative_image:
                outcomes.append({"category": "element", "path": path, "outcome": "excluded"})
                continue
            diagnostics.append({"code": "unsupported-element", "path": path, "type": source_type})
            outcomes.append({"category": "element", "path": path, "outcome": "manual"})
            continue
        name = str(item["name"])
        record = data.get(data_key)
        if not isinstance(record, dict):
            diagnostics.append({"code": "missing-element-data", "path": path})
            outcomes.append({"category": "element", "path": path, "outcome": "manual"})
            continue
        strings = _raw_strings(record.get("raw"))
        rectangle = _rectangle(record)
        target: dict[str, Any] = {target_type: name}
        if target_type == "group":
            target = {"group": "vertical", "name": name}
            if source_type == "Group":
                group_title = _russian_presentation(record.get("raw"))
                target.update({"representation": "normal", "showTitle": bool(group_title)})
                if group_title:
                    target["title"] = group_title
                outcomes.append(
                    {"category": "presentation", "path": f"{path}/presentation/frame", "outcome": "converted"}
                )
            if source_type == "Panel":
                pages_value = data.get(f"{data_key}/-pages-")
                if (
                    not isinstance(pages_value, list)
                    or not pages_value
                    or not all(isinstance(page, str) for page in pages_value)
                ):
                    diagnostics.append({"code": "invalid-panel-pages", "path": path})
                    outcomes.append({"category": "element", "path": path, "outcome": "manual"})
                    continue
                panel_pages[data_key] = pages_value
        if target_type == "spreadsheet":
            attributes.append({"name": name, "type": "SpreadsheetDocument"})
            target.update({"path": name, "horizontalStretch": True, "verticalStretch": True})
        if target_type in {"input", "check", "radio", "progress", "table"}:
            binding = record.get("prop")
            if binding == "РеквизитПоУмолчанию" and name in object_attributes | object_tables:
                binding = main_attribute
            if binding is None and target_type == "input":
                raw_types = set(strings)
                scalar_types = [
                    target
                    for marker, target in {"D": "date", "S": "string", "N": "number", "B": "boolean"}.items()
                    if marker in raw_types
                ]
                if "Pattern" in raw_types and len(scalar_types) == 1:
                    attributes.append({"name": name, "type": scalar_types[0]})
                    form_attribute_names.add(name)
                    form_attribute_types[name] = scalar_types[0]
                    binding = name
            if target_type == "radio" and not binding:
                sibling_bindings = {
                    sibling_record.get("prop")
                    for sibling, sibling_key, _sibling_path, sibling_parent in tree_entries
                    for sibling_record in [data.get(sibling_key)]
                    if sibling_parent == parent
                    and isinstance(sibling, dict)
                    and sibling.get("type") == "RadioBtn"
                    and isinstance(sibling_record, dict)
                    and sibling_record.get("prop") in form_attribute_names
                }
                choice_attributes = sibling_bindings or {
                    attribute_name
                    for attribute_name, type_name in form_attribute_types.items()
                    if type_name in {"number", "boolean"}
                }
                binding = next(iter(choice_attributes)) if len(choice_attributes) == 1 else None
            if target_type == "table" and not binding and name in form_tables:
                attributes.append(
                    {
                        "name": name,
                        "type": "ValueTable",
                        "columns": [
                            {
                                "name": column,
                                **(
                                    {"title": form_table_titles[name][column]}
                                    if column in form_table_titles[name]
                                    else {}
                                ),
                            }
                            for column in form_tables[name]
                        ],
                    }
                )
                form_attribute_names.add(name)
                form_attribute_types[name] = "ValueTable"
                binding = name
            select_form_attribute = (
                source_type == "SelectField"
                and binding == main_attribute
                and object_entities is not None
                and name not in object_attributes
            )
            if select_form_attribute:
                attributes.append({"name": name, "type": "string"})
                form_attribute_names.add(name)
                target["path"] = name
            elif binding == main_attribute:
                target_name = name
                if (
                    object_entities is not None
                    and target_name not in object_attributes
                    and target_name not in object_tables
                ):
                    choice = _radio_choice(record.get("raw")) if target_type == "radio" else None
                    compatible_types = {
                        "string": {"xs:string"},
                        "number": {"xs:decimal", "xs:integer", "xs:int"},
                        "boolean": {"xs:boolean"},
                    }
                    compatible_attributes = {
                        attribute_name
                        for attribute_name, attribute_type in object_attribute_types.items()
                        if choice is not None
                        and set(attribute_type if isinstance(attribute_type, list) else [attribute_type])
                        & compatible_types[choice[2]]
                    }
                    target_name = (
                        next(iter(object_tables))
                        if target_type == "table" and len(object_tables) == 1
                        else next(iter(compatible_attributes))
                        if target_type == "radio" and len(compatible_attributes) == 1
                        else field_label_titles.get(index, "").rstrip(": ")
                    )
                    if target_name not in object_attributes and target_name not in object_tables:
                        attribute_type = None
                        if target_type == "table" and name in form_tables:
                            attribute_type = "ValueTable"
                            attributes.append(
                                {
                                    "name": name,
                                    "type": attribute_type,
                                    "columns": [
                                        {
                                            "name": column,
                                            **(
                                                {"title": form_table_titles[name][column]}
                                                if column in form_table_titles[name]
                                                else {}
                                            ),
                                        }
                                        for column in form_tables[name]
                                    ],
                                }
                            )
                        elif target_type == "input":
                            scalar_types = {
                                target
                                for marker, target in {
                                    "D": "date",
                                    "S": "string",
                                    "N": "number",
                                    "B": "boolean",
                                }.items()
                                if marker in set(strings)
                            }
                            opaque_types = {
                                value for marker, value in OPAQUE_FORM_TYPES.items() if marker in set(strings)
                            }
                            if "Pattern" in strings and len(scalar_types) + len(opaque_types) <= 1:
                                resolved_type = next(iter(scalar_types or opaque_types), "")
                                if resolved_type:
                                    attribute_type = resolved_type
                                    attributes.append({"name": name, "type": attribute_type})
                        if attribute_type is None:
                            diagnostics.append({"code": "missing-object-data", "path": path, "name": name})
                            outcomes.append({"category": "element", "path": path, "outcome": "manual"})
                            continue
                        form_attribute_names.add(name)
                        form_attribute_types[name] = attribute_type
                        target["path"] = name
                    else:
                        target["path"] = f"{main_attribute}.{target_name}"
                else:
                    target["path"] = f"{main_attribute}.{target_name}"
            elif binding in form_attribute_names:
                target["path"] = binding
            else:
                diagnostics.append({"code": "unsupported-data-binding", "path": path})
                outcomes.append({"category": "element", "path": path, "outcome": "manual"})
                continue
            if index in field_labels:
                target["titleLocation"] = "none"
            elif binding == name and target_type == "input":
                target["titleLocation"] = "none"
        if target_type == "radio":
            choice = _radio_choice(record.get("raw"))
            if choice is None:
                diagnostics.append({"code": "unsupported-radio-choice", "path": path})
                outcomes.append({"category": "element", "path": path, "outcome": "manual"})
                continue
            target["choices"] = [{"title": choice[0], "value": choice[1], "type": choice[2]}]
            target["titleLocation"] = "none"
        if target_type == "progress":
            target["titleLocation"] = "none"
        if target_type == "input":
            choices = _input_choice_list(record.get("raw"))
            if choices:
                target.update({"listChoiceMode": True, "choices": choices})
        if target_type in {"check", "button"}:
            presentation = _russian_presentation(record.get("raw"))
            if presentation:
                target["title"] = presentation
        if target_type == "label":
            target["title"] = next(
                (
                    value
                    for value in strings
                    if value != name and value not in procedure_names and re.search(r"[А-Яа-яЁё]", value)
                ),
                name,
            )
            if rectangle is not None:
                target.update({"autoMaxWidth": False, "width": max(1, round((rectangle[2] - rectangle[0]) / 8))})
            text_color = _text_color(record.get("raw"))
            if text_color:
                target["textColor"] = text_color
        handler = f"{name}ПриИзменении"
        if (
            target_type in {"input", "check", "radio", "progress", "table"}
            and handler in strings
            and handler in procedure_names
        ):
            if target_type == "progress":
                diagnostics.append({"code": "unsupported-progress-event", "path": f"{path}/event/OnChange"})
            else:
                target["on"] = ["OnChange"]
                target["handlers"] = {"OnChange": handler}
            outcomes.append(
                {
                    "category": "event",
                    "path": f"{path}/event/OnChange",
                    "outcome": "manual" if target_type == "progress" else "converted",
                }
            )
        start_choice_handler = f"{name}НачалоВыбора"
        if target_type == "input" and start_choice_handler in strings and start_choice_handler in procedure_names:
            target["choiceButton"] = True
            target["on"] = [*target.get("on", []), "StartChoice"]
            target.setdefault("handlers", {})["StartChoice"] = start_choice_handler
            outcomes.append(
                {
                    "category": "event",
                    "path": f"{path}/event/StartChoice",
                    "outcome": "converted",
                }
            )
        if target_type == "button":
            handlers = list(dict.fromkeys(value for value in strings if value in procedure_names))
            if not handlers and name == "Закрыть":
                target["stdCommand"] = "Close"
            elif len(handlers) != 1:
                diagnostics.append({"code": "missing-or-ambiguous-button-handler", "path": path})
                outcomes.append({"category": "element", "path": path, "outcome": "manual"})
                continue
            else:
                target["command"] = name
                if not register_command(name, handlers[0]):
                    diagnostics.append({"code": "ambiguous-command-handler", "path": path})
                    outcomes.append({"category": "event", "path": f"{path}/event/{handlers[0]}", "outcome": "manual"})
                    outcomes.append({"category": "element", "path": path, "outcome": "manual"})
                    continue
                outcomes.append({"category": "event", "path": f"{path}/event/{handlers[0]}", "outcome": "converted"})
        if target_type == "table":
            column_names = form_tables.get(name)
            if column_names is None:
                table_name = name
                if object_entities is not None and table_name not in object_tables and len(object_tables) == 1:
                    table_name = next(iter(object_tables))
                    target["path"] = f"{main_attribute}.{table_name}"
                column_names = (
                    object_columns.get(table_name)
                    if object_entities is not None
                    else [
                        value
                        for value in strings
                        if value not in {name, "НомерСтроки"}
                        and value not in procedure_names
                        and re.fullmatch(r"[А-Яа-яЁё_]\w*", value)
                    ]
                )
            if "НомерСтроки" in strings:
                # Form element names are unique across the whole form; scope the
                # synthetic row-number column by its table, as Designer does.
                target["columns"] = [
                    {"input": f"{name}НомерСтроки", "path": f"{main_attribute}.{name}.НомерСтроки", "title": "N"}
                ]
            if column_names:
                target.setdefault("columns", []).extend(
                    {
                        "input": column,
                        "path": f"{target['path']}.{column}",
                        **(
                            {"title": form_table_titles[name][column]}
                            if column in form_table_titles.get(name, {})
                            else {}
                        ),
                    }
                    for column in column_names
                )
            target["title"] = re.sub(r"(?<!^)([А-Я])", r" \1", name).capitalize()
            # ponytail: ordinary-form geometry is positional; keep a compact row-height default until a second real fixture proves a general decoder.
            target["height"] = 7
        if target_type == "cmdBar":
            children = []
            source_tree = _command_panel_tree(record.get("raw"), procedure_names)
            source_buttons = (
                None if source_tree is not None else _command_panel_buttons(record.get("raw"), procedure_names)
            )
            if source_tree is None and source_buttons is None:
                if not any(value in procedure_names for value in strings):
                    outcomes.append({"category": "element", "path": path, "outcome": "excluded"})
                    continue
                diagnostics.append({"code": "missing-or-ambiguous-command-presentation", "path": path})
                outcomes.append({"category": "element", "path": path, "outcome": "manual"})
                continue
            coverage_occurrences: dict[str, int] = {}

            def occurrence_path(base: str, *, occurrences: dict[str, int] = coverage_occurrences) -> str:
                occurrence = occurrences.get(base, 0) + 1
                occurrences[base] = occurrence
                return base if occurrence == 1 else f"{base}/occurrence/{occurrence}"

            def append_button(
                command_name: str,
                title: str,
                event_handler: str,
                destination: list[dict[str, object]],
                picture: str | None = None,
                representation: str | None = None,
                *,
                path: str = path,
            ) -> None:
                event_path = occurrence_path(f"{path}/event/{event_handler}")
                title_path = occurrence_path(f"{path}/presentation/{command_name}/title")
                membership_path = occurrence_path(f"{path}/presentation/{command_name}/panel-membership")
                if not command_name or not title:
                    diagnostics.append({"code": "missing-or-ambiguous-command-presentation", "path": path})
                    outcomes.extend(
                        (
                            {"category": "presentation", "path": title_path, "outcome": "manual"},
                            {"category": "presentation", "path": membership_path, "outcome": "manual"},
                        )
                    )
                    return
                if not register_command(command_name, event_handler):
                    diagnostics.append({"code": "ambiguous-command-handler", "path": path})
                    outcomes.extend(
                        (
                            {"category": "event", "path": event_path, "outcome": "manual"},
                            {"category": "presentation", "path": title_path, "outcome": "manual"},
                            {"category": "presentation", "path": membership_path, "outcome": "manual"},
                        )
                    )
                    return
                button: dict[str, object] = {"button": command_name, "command": command_name, "title": title}
                if picture:
                    button["picture"] = picture
                if representation:
                    button["representation"] = representation
                destination.append(button)
                outcomes.append(
                    {
                        "category": "event",
                        "path": event_path,
                        "outcome": "converted",
                    }
                )
                outcomes.extend(
                    (
                        {"category": "presentation", "path": title_path, "outcome": "converted"},
                        {"category": "presentation", "path": membership_path, "outcome": "converted"},
                    )
                )

            def append_tree(nodes: object, destination: list[dict[str, object]]) -> None:
                if not isinstance(nodes, list):
                    return
                for node in nodes:
                    if not isinstance(node, dict):
                        continue
                    if "popup" in node:
                        nested: list[dict[str, object]] = []
                        append_tree(node.get("children", []), nested)
                        destination.append({"popup": node["popup"], "title": node["title"], "children": nested})
                    else:
                        append_button(
                            str(node["button"]),
                            str(node["title"]),
                            str(node["_action"]),
                            destination,
                            node.get("picture"),
                            node.get("representation"),
                        )

            if source_tree is not None:
                append_tree(source_tree, children)
            else:
                for command_name, title, event_handler in source_buttons or []:
                    append_button(command_name, title, event_handler, children)
            if children:
                direct_buttons = [child for child in children if "button" in child]
                if name == "ОсновныеДействияФормы" and direct_buttons:
                    direct_buttons[0]["defaultButton"] = True
                action_source = _command_panel_action_source(record.get("raw"), name)
                table_name = next(
                    (
                        str(source_item["name"])
                        for source_item, source_key, _source_path, _source_parent in tree_entries
                        if isinstance(source_item, dict)
                        and source_item.get("type") == "Table"
                        and isinstance(data.get(source_key), dict)
                        and str(data[source_key].get("id")) == action_source
                    ),
                    name.removeprefix("КоманднаяПанель") if name.startswith("КоманднаяПанель") else "",
                )
                table = next((element for element in output_elements if element.get("table") == table_name), None)
                if table is not None:
                    table["commandBarButtons"] = children
                else:
                    target["children"] = children
                    trailing_command_bars.append((target, str(item["page"]), rectangle, index, data_key, parent))
                outcomes.append({"category": "element", "path": path, "outcome": "converted"})
            else:
                outcomes.append({"category": "element", "path": path, "outcome": "excluded"})
            continue
        output_elements.append(target)
        output_pages.append(str(item["page"]))
        output_rectangles.append(rectangle)
        output_indexes.append(index)
        output_keys.append(data_key)
        output_parents.append(parent)
        outcomes.append({"category": "element", "path": path, "outcome": "converted"})
    for target, page, rectangle, index, data_key, parent in trailing_command_bars:
        output_elements.append(target)
        output_pages.append(page)
        output_rectangles.append(rectangle)
        output_indexes.append(index)
        output_keys.append(data_key)
        output_parents.append(parent)
    for index, _command in enumerate(commands):
        path = f"form/{form.name}/command/{index}"
        diagnostics.append({"code": "ordinary-command-schema-not-decoded", "path": path})
        outcomes.append({"category": "command", "path": path, "outcome": "manual"})
    form_events = _form_events(form.metadata.get("form"))
    dsl_events: dict[str, str] = {}
    if form_events is not None:
        for event_name, handler in form_events:
            event_path = f"form/{form.name}/event/{event_name}"
            if handler in procedure_names and event_name not in dsl_events:
                dsl_events[event_name] = handler
                outcomes.append({"category": "event", "path": event_path, "outcome": "converted"})
            else:
                diagnostics.append({"code": "missing-or-ambiguous-form-event", "path": event_path})
                outcomes.append({"category": "event", "path": event_path, "outcome": "manual"})
    expected_data = {data_key for _item, data_key, _path, _parent in tree_entries if data_key}
    expected_data.update({"-pages-", *[page for page in data.get("-pages-", []) if isinstance(page, str)]})
    for panel_key, pages_value in panel_pages.items():
        expected_data.add(f"{panel_key}/-pages-")
        expected_data.update(f"{panel_key}/{page}" for page in pages_value)
    for key in data:
        outcome = "converted" if key in expected_data else "manual"
        if outcome == "manual":
            diagnostics.append({"code": "unsupported-data-record", "path": f"form/{form.name}/data/{key}"})
        outcomes.append({"category": "data", "path": f"form/{form.name}/data/{key}", "outcome": outcome})
    coverage = {"input": len(outcomes), "converted": 0, "manual": 0, "excluded": 0}
    for item in outcomes:
        coverage[item["outcome"]] += 1
    if coverage["input"] != coverage["converted"] + coverage["manual"] + coverage["excluded"]:
        raise CommandError(f"coverage invariant failed for form {form.name}")
    if len({item["path"] for item in outcomes}) != len(outcomes):
        raise CommandError(f"coverage paths are not unique for form {form.name}")
    pages = data.get("-pages-")
    if not isinstance(pages, list) or not all(isinstance(page, str) for page in pages):
        raise CommandError(f"invalid page list in form {form.name}")
    nodes = list(
        zip(output_elements, output_pages, output_rectangles, output_indexes, output_keys, output_parents, strict=True)
    )

    def arranged(parent: str | None, page: str) -> list[dict[str, object]]:
        selected = []
        for element, source_page, rectangle, index, data_key, source_parent in nodes:
            if source_parent != parent or source_page != page:
                continue
            child_pages = panel_pages.get(data_key)
            if child_pages:
                children = []
                for child_page in child_pages:
                    page_record = data.get(f"{data_key}/{child_page}")
                    page_title = (
                        _russian_presentation(page_record.get("raw")) if isinstance(page_record, dict) else None
                    )
                    children.append(
                        {
                            "page": child_page,
                            "title": page_title or child_page,
                            "children": arranged(data_key, child_page),
                        }
                    )
                element.clear()
                element.update({"pages": str(data_key.rsplit("/", 1)[-1]), "children": children})
            selected.append((element, rectangle, index))
        return _arrange_page(selected)

    if len(pages) > 1:
        by_page = {page: arranged(None, page) for page in pages}
        layout = [
            {
                "pages": "Страницы",
                "children": [{"page": page, "title": page, "children": by_page[page]} for page in pages],
            }
        ]
    else:
        layout = [
            {"group": "vertical", "name": "ОсновнаяГруппа", "showTitle": False, "children": arranged(None, pages[0])}
        ]
    title_candidates = [
        value for value in _raw_strings(form.metadata.get("form")) if " " in value and re.search(r"[А-Яа-яЁё]", value)
    ]
    title = (
        title_candidates[0]
        if title_candidates
        else str(
            form.metadata.get("name2", {}).get("ru") if isinstance(form.metadata.get("name2"), dict) else form.name
        )
    )
    dsl = {
        "title": title,
        "properties": {"autoTitle": False},
        "attributes": attributes,
        "commands": output_commands,
        "elements": layout,
    }
    if dsl_events:
        dsl["events"] = dsl_events
    return dsl, diagnostics, coverage, outcomes


def _stable_uuid(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"onec-template:ordinary-form-conversion:{seed}"))


def _xml_text(node: ElementTree.Element, path: str) -> str:
    value = node.findtext(path, namespaces={"md": MD_NS, "v8": V8_NS})
    if not value:
        raise CommandError(f"object XML is missing {path}")
    return value


def _xml_types(node: ElementTree.Element) -> str | list[str]:
    values = [
        value.text for value in node.findall("md:Properties/md:Type/v8:Type", {"md": MD_NS, "v8": V8_NS}) if value.text
    ]
    return values[0] if len(values) == 1 else values


def _object_inventory(root_xml: Path, expected_kind: str) -> list[dict[str, object]]:
    try:
        document = ElementTree.parse(root_xml)
    except (OSError, ElementTree.ParseError) as error:
        raise CommandError(f"invalid object XML {root_xml}: {error}") from error
    object_node = document.getroot().find(f"md:{expected_kind}", {"md": MD_NS})
    if object_node is None:
        raise CommandError(f"object XML does not contain {expected_kind}")
    child_objects = object_node.find("md:ChildObjects", {"md": MD_NS})
    if child_objects is None:
        raise CommandError("object XML has no ChildObjects")
    result: list[dict[str, object]] = []
    for child in child_objects:
        kind = child.tag.rsplit("}", 1)[-1]
        if kind == "Attribute":
            name = _xml_text(child, "md:Properties/md:Name")
            attribute_type = _xml_types(child)
            result.append(
                {
                    "kind": "attribute",
                    "name": name,
                    "path": f"object/attribute/{name}",
                    "type": attribute_type,
                    "outcome": "converted" if attribute_type else "manual",
                }
            )
        elif kind == "TabularSection":
            name = _xml_text(child, "md:Properties/md:Name")
            result.append(
                {
                    "kind": "tabular-section",
                    "name": name,
                    "path": f"object/tabular-section/{name}",
                    "outcome": "converted",
                }
            )
            columns = child.find("md:ChildObjects", {"md": MD_NS})
            if columns is None:
                continue
            for column in columns:
                if column.tag.rsplit("}", 1)[-1] != "Attribute":
                    continue
                column_name = _xml_text(column, "md:Properties/md:Name")
                result.append(
                    {
                        "kind": "column",
                        "name": column_name,
                        "owner": name,
                        "path": f"object/tabular-section/{name}/column/{column_name}",
                        "type": _xml_types(column),
                        "outcome": "converted",
                    }
                )
    return result


def _profile_target(profile: RuntimeProfile) -> str:
    """Evidence key of the infobase a build or live check ran against: the runtime profile name."""
    return profile.name or profile.path.stem


def _dump_object_source(
    input_path: Path, destination: Path, profile_path: Path, run_root: Path, v8unpack: str, kind: str
) -> Path:
    profile = load_runtime_profile(profile_path)
    if profile is None:
        raise CommandError("runtime profile is required to preserve object data types")
    _load_local_env()
    run_root.mkdir(parents=True, exist_ok=True)
    destination = destination.resolve()
    artifact = (run_root / ("source.epf" if kind == "ExternalDataProcessor" else "source.erf")).resolve()
    if artifact.exists():
        raise CommandError(f"temporary source artifact already exists: {artifact}")
    if input_path.is_dir():
        completed = subprocess.run(
            [v8unpack, "-B", str(input_path), str(artifact)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode or not artifact.is_file():
            raise CommandError(f"v8unpack build failed: {completed.stderr.strip()}", completed.returncode or 1)
    else:
        shutil.copy2(input_path, artifact)
    command = [
        sys.executable,
        "-m",
        "scripts.python.cli",
        "imported-skill",
        "epf-dump",
        "-Profile",
        str(profile_path),
    ]
    command.extend(["-InputFile", str(artifact), "-OutputDir", str(destination)])
    completed = subprocess.run(
        command, cwd=project_root(), capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if completed.returncode:
        detail = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
        raise CommandError(f"object XML dump failed: {detail}", completed.returncode)
    roots = list(destination.glob("*.xml"))
    if len(roots) != 1:
        raise CommandError("object XML dump must contain exactly one root XML")
    return roots[0]


def _relative_to_repo(path: Path) -> str:
    return path.relative_to(project_root()).as_posix()


def _validate_designer_epf(root_xml: Path) -> tuple[str, Path, list[dict[str, object]]]:
    staging = root_xml.parent
    for path in (staging, *staging.rglob("*")):
        if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
            raise CommandError(f"Designer staging contains symlink or reparse point: {path.relative_to(staging)}")
    if list(staging.glob("*.xml")) != [root_xml]:
        raise CommandError("Designer staging must contain exactly one root XML")
    processor = ElementTree.parse(root_xml).getroot().find(f"{{{MD_NS}}}ExternalDataProcessor")
    if processor is None:
        raise CommandError("Designer staging root must be ExternalDataProcessor")
    name = processor.findtext(f"{{{MD_NS}}}Properties/{{{MD_NS}}}Name") or ""
    if not name.isidentifier() or _safe_windows_segment(name) != name:
        raise CommandError(f"unsafe ExternalDataProcessor name: {name}")
    object_root = staging / name
    if not object_root.is_dir() or root_xml.name != f"{name}.xml":
        raise CommandError(f"Designer staging object directory must match {name}")
    return name, object_root, _object_inventory(root_xml, "ExternalDataProcessor")


def _designer_parts(
    root_xml: Path, object_root: Path
) -> tuple[list[tuple[str, str, Path]], list[dict[str, object]], set[Path]]:
    forms: list[tuple[str, str, Path]] = []
    inventory: list[dict[str, object]] = []
    allowed_bins: set[Path] = set()
    processor = ElementTree.parse(root_xml).getroot().find(f"{{{MD_NS}}}ExternalDataProcessor")
    children = None if processor is None else processor.find(f"{{{MD_NS}}}ChildObjects")
    declared_forms = (
        set()
        if children is None
        else {child.text for child in children if child.tag == f"{{{MD_NS}}}Form" and child.text}
    )
    declared_templates = (
        set()
        if children is None
        else {child.text for child in children if child.tag == f"{{{MD_NS}}}Template" and child.text}
    )
    form_descriptors = sorted((object_root / "Forms").glob("*.xml"))
    template_descriptors = sorted((object_root / "Templates").glob("*.xml"))
    if {path.stem for path in form_descriptors} != declared_forms:
        raise CommandError("Designer form descriptors do not match root ChildObjects")
    if {path.stem for path in template_descriptors} != declared_templates:
        raise CommandError("Designer template descriptors do not match root ChildObjects")
    for descriptor in form_descriptors:
        node = ElementTree.parse(descriptor).getroot().find(f"{{{MD_NS}}}Form")
        if node is None:
            raise CommandError(f"invalid form descriptor: {descriptor}")
        name = node.findtext(f"{{{MD_NS}}}Properties/{{{MD_NS}}}Name") or descriptor.stem
        form_type = node.findtext(f"{{{MD_NS}}}Properties/{{{MD_NS}}}FormType") or ""
        binary = object_root / "Forms" / name / "Ext" / "Form.bin"
        if form_type == "Ordinary" and binary.is_file():
            allowed_bins.add(binary)
            forms.append((name, node.attrib.get("uuid", ""), binary))
        elif form_type == "Managed" and not binary.exists() and binary.with_suffix(".xml").is_file():
            inventory.append({"kind": "form", "name": name, "type": form_type, "outcome": "preserved-by-rule"})
        elif binary.exists() or form_type == "Ordinary":
            raise CommandError(f"unsupported ordinary form content: {binary}")
        else:
            raise CommandError(f"unsupported managed form content: {name} ({form_type})")
    for descriptor in template_descriptors:
        node = ElementTree.parse(descriptor).getroot().find(f"{{{MD_NS}}}Template")
        if node is None:
            raise CommandError(f"invalid template descriptor: {descriptor}")
        name = node.findtext(f"{{{MD_NS}}}Properties/{{{MD_NS}}}Name") or descriptor.stem
        template_type = node.findtext(f"{{{MD_NS}}}Properties/{{{MD_NS}}}TemplateType") or ""
        binary = object_root / "Templates" / name / "Ext" / "Template.bin"
        xml = binary.with_suffix(".xml")
        if template_type == "BinaryData" and binary.is_file():
            allowed_bins.add(binary)
            outcome = "preserved-by-rule"
        elif xml.is_file() and not binary.exists():
            outcome = "converted"
        else:
            raise CommandError(f"unsupported template content: {name} ({template_type})")
        inventory.append({"kind": "template", "name": name, "type": template_type, "outcome": outcome})
    return forms, inventory, allowed_bins


def _convert_designer_epf(designer: Path, managed: Path, temporary: Path) -> dict[str, Any]:
    if V8UNPACK_VERSION != SUPPORTED_V8UNPACK:
        raise CommandError(f"unsupported v8unpack version: {V8UNPACK_VERSION}")
    root_xml = next(designer.glob("*.xml"))
    name, object_root, entities = _validate_designer_epf(root_xml)
    forms, inventory, allowed_bins = _designer_parts(root_xml, object_root)
    unknown = sorted(path for path in designer.rglob("*.bin") if path not in allowed_bins)
    if unknown:
        raise CommandError(f"unsupported binary: {unknown[0].relative_to(designer).as_posix()}")
    shutil.copytree(designer, managed)
    modules: list[str] = []
    for form_name, form_uuid, binary in forms:
        decoded = temporary / form_name
        decode_form(binary, decoded, form_name, form_uuid)
        form = SourceForm(
            form_name, decoded, _load_object(decoded / "Form.json"), _load_object(decoded / "Form.elem.json")
        )
        dsl, diagnostics, _coverage, _outcomes = _form_dsl(
            form,
            {str(item["name"]) for item in _procedures(decoded / "Form.obj.bsl")},
            "ExternalDataProcessor",
            name,
            entities,
        )
        if diagnostics:
            raise CommandError(f"unsupported ordinary form {form_name}: {diagnostics}")
        shutil.rmtree(managed / name / "Forms" / form_name)
        dsl_path, module = _compile_form(managed / name, form, dsl)
        dsl_path.unlink()
        modules.append(module.relative_to(managed).as_posix())
        inventory.append({"kind": "form", "name": form_name, "outcome": "converted"})
    return {"name": name, "modules": modules, "inventory": inventory}


def _check_expected_sha(input_path: Path, expected_sha256: str | None) -> None:
    if expected_sha256 is None:
        return
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256) or _sha(input_path).lower() != expected_sha256.lower():
        raise CommandError("input SHA-256 does not match expected value")


def _prepare_sources(
    input_path: Path,
    profile_path: Path,
    v8unpack: str,
    repository_name: str | None = None,
    expected_sha256: str | None = None,
) -> dict[str, object]:
    if input_path.suffix.lower() != ".epf" or not input_path.is_file():
        raise CommandError("prepare-sources requires an existing EPF file")
    _check_expected_sha(input_path, expected_sha256)
    if repository_name is not None and not repository_name.isidentifier():
        raise CommandError("repository-name must be one identifier")
    artifacts_parent = project_root() / ".artifacts" / "ordinary-form-conversion"
    artifacts_parent.mkdir(parents=True, exist_ok=True)
    run_root = artifacts_parent / uuid.uuid4().hex
    work = run_root / "work"
    designer = work / "designer"
    run_root.mkdir()
    stages: list[Path] = []
    sensitive: list[str] = []
    try:
        _load_local_env()
        profile = load_runtime_profile(profile_path)
        if profile is None:
            raise CommandError("runtime profile is required")
        for value in (
            profile.string("infobase", "filePath"),
            profile.string("infobase", "server"),
            profile.string("infobase", "ref"),
            profile.string("infobase", "auth", "user"),
        ):
            if value:
                sensitive.append(value)
        if profile.has("infobase", "auth", "passwordEnv"):
            sensitive.append(resolve_secret_value(profile.require_string("infobase", "auth", "passwordEnv")))
        root_xml = _dump_object_source(input_path, designer, profile_path, work, v8unpack, "ExternalDataProcessor")
        name, _object_root, _entities = _validate_designer_epf(root_xml)
        target_name = repository_name or name
        ordinary_target = project_root() / "src" / "epf" / "ordinary" / target_name
        managed_target = project_root() / "src" / "epf" / "managed" / target_name
        legacy_target = ordinary_target.with_name(f"{target_name}.v8unpack")
        existing = [path for path in (ordinary_target, managed_target, legacy_target) if path.exists()]
        if existing:
            raise CommandError(
                "existing canonical source targets; move them to reserve: "
                f"{_relative_to_repo(ordinary_target)}, {_relative_to_repo(managed_target)}"
                + (f", legacy {_relative_to_repo(legacy_target)}" if legacy_target.exists() else "")
            )
        ordinary_stage = ordinary_target.parent / f".{target_name}.{uuid.uuid4().hex}"
        managed_stage = managed_target.parent / f".{target_name}.{uuid.uuid4().hex}"
        stages = [ordinary_stage, managed_stage]
        ordinary_target.parent.mkdir(parents=True, exist_ok=True)
        managed_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(designer, ordinary_stage)
        conversion = _convert_designer_epf(designer, managed_stage, work / "decoded")
        designer_hash = _input_sha(designer)
        if _input_sha(ordinary_stage) != designer_hash:
            raise CommandError("ordinary staging differs from Designer staging")
        published: list[tuple[Path, Path]] = []
        try:
            for source, target in ((ordinary_stage, ordinary_target), (managed_stage, managed_target)):
                os.replace(source, target)
                published.append((source, target))
        except Exception:
            for source, target in reversed(published):
                if target.exists():
                    os.replace(target, source)
            raise
        summary = {
            "schemaVersion": 1,
            "status": "agent-remediation-required",
            "inputSha256": _sha(input_path),
            "actualKind": "ExternalDataProcessor",
            "designerName": name,
            "repositoryName": target_name,
            "designerTreeSha256": designer_hash,
            "ordinaryTreeSha256": _input_sha(ordinary_target),
            "managedTreeSha256": _input_sha(managed_target),
            "ordinaryPath": _relative_to_repo(ordinary_target),
            "managedPath": _relative_to_repo(managed_target),
            "modules": [f"{_relative_to_repo(managed_target)}/{path}" for path in conversion["modules"]],
            "inventory": conversion["inventory"],
            "versions": {
                "platform": canonical_path(profile.require_string("platform", "binaryPath")).parent.parent.name,
                "converter": "1",
                "v8unpack": V8UNPACK_VERSION,
            },
        }
        write_json(run_root / "preparation-summary.json", _redact(summary))
        shutil.rmtree(work)
        return summary
    except BaseException as error:
        shutil.rmtree(work, ignore_errors=True)
        for stage in stages:
            state_directory = stage.with_name("." + stage.name + ".metadata-state")
            plan_path = stage.with_name("." + stage.name + ".metadata-plan.json")
            if not os.path.lexists(state_directory) and not os.path.lexists(plan_path):
                shutil.rmtree(stage, ignore_errors=True)
        message = (
            str(error)
            .replace(str(project_root()), ".")
            .replace(str(work), "<work>")
            .replace(str(input_path), "<input>")
            .replace(str(profile_path), "<profile>")
        )
        for value in sorted((value for value in sensitive if value), key=len, reverse=True):
            message = message.replace(value, "<redacted>")
        message = re.sub(r"(?i)\b[A-Z]:[\\/][^\r\n,;]+", "<external-path>", message)
        message = re.sub(r"(?<!\w)/(?:home|tmp|var|opt|Users)/[^\s,;]+", "<external-path>", message)
        failure: dict[str, object] = {"status": "failed", "type": type(error).__name__, "message": message}
        failure["recoveryRoots"] = [
            _relative_to_repo(stage)
            for stage in stages
            if os.path.lexists(stage.with_name("." + stage.name + ".metadata-state"))
            or os.path.lexists(stage.with_name("." + stage.name + ".metadata-plan.json"))
        ]
        unsupported = re.fullmatch(r"unsupported binary: (.+)", str(error))
        if unsupported:
            failure["inventory"] = [{"kind": "binary", "path": unsupported.group(1), "outcome": "unsupported"}]
        elif str(error).startswith("unsupported ordinary form") or str(error).startswith("unsupported managed form"):
            failure["inventory"] = [{"kind": "form", "reason": message, "outcome": "unsupported"}]
        elif str(error).startswith("unsupported v8unpack version"):
            failure["inventory"] = [{"kind": "form-container", "reason": message, "outcome": "unsupported"}]
        write_json(run_root / "preparation-failure.json", _redact(failure))
        if isinstance(error, Exception):
            raise CommandError(message) from None
        raise


def _prepare_object_root(
    input_path: Path,
    source_tree: Path,
    staging: Path,
    kind: str,
    profile_path: Path,
    run_root: Path,
    v8unpack: str,
    ordinary_output: Path | None = None,
) -> tuple[Path, list[dict[str, object]]]:
    designer_source = source_tree / "Designer"
    if kind == "ExternalReport" and designer_source.is_dir():
        shutil.copytree(designer_source, staging, dirs_exist_ok=True)
        roots = list(staging.glob("*.xml"))
        if len(roots) != 1:
            raise CommandError("preserved Designer source must contain exactly one root XML")
        root_xml = roots[0]
    else:
        root_xml = _dump_object_source(input_path, staging, profile_path, run_root, v8unpack, kind)
    inventory = _object_inventory(root_xml, kind)
    if ordinary_output is not None:
        shutil.copytree(staging, ordinary_output)
    object_root = root_xml.with_suffix("")
    forms = object_root / "Forms"
    if forms.is_symlink():
        raise CommandError("dumped Forms directory must not be a symbolic link")
    if forms.exists():
        shutil.rmtree(forms)
    return object_root, inventory


def _compile_form(object_root: Path, form: SourceForm, dsl: dict[str, object]) -> tuple[Path, Path]:
    from . import metadata, metadata_form_compile, metadata_form_schema

    try:
        definition = metadata_form_schema.normalize_parameters("form.compile", {"definition": dsl})["definition"]
        main_attributes = [attribute for attribute in definition.get("attributes", []) if attribute.get("main")]
        if len(main_attributes) != 1:
            raise CommandError("conversion requires exactly one main form attribute")
        seed = metadata_form_compile.render_form({"attributes": main_attributes})
        root = metadata.xml_read(
            metadata.read_file(object_root.with_suffix(".xml"), metadata.FILE_LIMIT), f"{{{MD_NS}}}MetaDataObject"
        )
        owners = [
            node for node in root if node.tag in {f"{{{MD_NS}}}ExternalDataProcessor", f"{{{MD_NS}}}ExternalReport"}
        ]
        if len(owners) != 1:
            raise CommandError("conversion requires one external object descriptor")
        kind = owners[0].tag.rsplit("}", 1)[-1]
    except (metadata.Rejected, ValueError, OSError):
        raise CommandError(f"invalid metadata form description: {form.name}") from None
    form_root = object_root / "Forms" / form.name
    ext_root = form_root / "Ext"
    module_root = ext_root / "Form"
    module_root.mkdir(parents=True)
    descriptor = f'''<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.17"><Form uuid="{_stable_uuid(object_root.name + ":" + form.name)}"><Properties><Name>{escape(form.name)}</Name><Synonym><v8:item><v8:lang>ru</v8:lang><v8:content>{escape(form.name)}</v8:content></v8:item></Synonym><Comment/><FormType>Managed</FormType><IncludeHelpInContents>false</IncludeHelpInContents><UsePurposes><v8:Value xsi:type="app:ApplicationUsePurpose">PlatformApplication</v8:Value></UsePurposes><ExtendedPresentation/></Properties></Form></MetaDataObject>
'''
    (object_root / "Forms").mkdir(exist_ok=True)
    (object_root / "Forms" / f"{form.name}.xml").write_text(descriptor, encoding="utf-8", newline="\n")
    dsl_path = form_root / "form.dsl.json"
    write_json(dsl_path, dsl)
    output_path = ext_root / "Form.xml"
    # This directory is a new conversion staging tree, never a published form.
    # Seed its original main attribute before the preserving merge operation.
    with output_path.open("xb") as stream:
        stream.write(seed)
    source_module = form.directory / "Form.obj.bsl"
    target_module = module_root / "Module.bsl"
    shutil.copyfile(source_module, target_module)
    if _sha(source_module) != _sha(target_module):
        raise CommandError(f"BSL byte-copy verification failed for {form.name}")
    logical = f"{kind}.{object_root.name}.Form.{form.name}"
    request = {
        "schemaVersion": 1,
        "operations": [{"op": "form.compile", "target": logical, "parameters": {"definition": definition}}],
    }
    try:
        state_directory = metadata.safe_path(
            object_root.parent.with_name("." + object_root.parent.name + ".metadata-state"), missing=True
        )
        plan_path = metadata.safe_path(
            object_root.parent.with_name("." + object_root.parent.name + ".metadata-plan.json"), missing=True
        )
        if state_directory.exists() or plan_path.exists():
            raise CommandError("conversion staging already has metadata recovery state")
        plan = metadata.plan_make(metadata.Snapshot(object_root.parent), request)
        # Keep the exact request/preimages outside the target for failed apply recovery.
        with plan_path.open("x", encoding="utf-8") as stream:
            json.dump(plan, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        metadata.apply(object_root.parent, None, plan)
        # This unique conversion tree has no other writers. Never remove a
        # recovery journal, an unknown entry, or a pre-existing state directory.
        state_directory = metadata.safe_path(state_directory, writable=True)
        if sorted(path.name for path in state_directory.iterdir()) != ["lock"]:
            raise CommandError("unexpected metadata state after conversion apply")
        lock = metadata.safe_path(state_directory / "lock", writable=True)
        if not lock.is_file():
            raise CommandError("invalid conversion metadata lock")
        lock.unlink()
        state_directory.rmdir()
        metadata.safe_path(plan_path, writable=True).unlink()
        if metadata.verify_objects(metadata.Snapshot(object_root.parent), [logical])["code"]:
            raise CommandError(f"metadata form verification failed: {form.name}")
    except (metadata.Rejected, OSError):
        raise CommandError(f"metadata form compilation failed: {form.name}") from None
    return dsl_path, target_module


def _report(
    kind: str, metadata: dict[str, Any], forms: list[SourceForm], object_entities: list[dict[str, object]] | None = None
) -> dict[str, Any]:
    details = []
    diagnostics: list[dict[str, str]] = []
    total = {"input": 0, "converted": 0, "manual": 0, "excluded": 0}
    for form in forms:
        procedures = _procedures(form.directory / "Form.obj.bsl")
        dsl, form_diagnostics, coverage, outcomes = _form_dsl(
            form,
            {str(item["name"]) for item in procedures},
            kind,
            str(metadata.get("name") or ""),
            object_entities,
        )
        diagnostics.extend(form_diagnostics)
        for key in total:
            total[key] += coverage[key]
        module = form.directory / "Form.obj.bsl"
        details.append(
            {
                "name": form.name,
                "dsl": dsl,
                "coverage": coverage,
                "coverageOutcomes": outcomes,
                "bsl": {
                    "sourceSha256": _sha(module),
                    "procedures": procedures,
                    "agentPlan": [
                        {"procedure": item["name"], "line": item["line"], "status": "pending-agent-review"}
                        for item in procedures
                    ],
                },
            }
        )
    status = "structure-remediation-required" if diagnostics else "analyzed"
    return {
        "schemaVersion": 1,
        "status": status,
        "stages": {
            "analysis": status,
            "structure": "pending",
            "agent": "pending",
            "build": "pending",
            "live": "pending",
        },
        "source": {"kind": kind, "name": metadata.get("name"), "v8unpack": metadata.get("v8unpack")},
        "coverage": total,
        "diagnostics": diagnostics,
        "forms": details,
    }


def _load_local_env() -> None:
    dotenv = project_root() / ".env"
    if not dotenv.is_file():
        return
    for raw_line in dotenv.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(name, value)


def _conversion_report(output: Path) -> tuple[Path, dict[str, Any]]:
    path = output / "conversion-report.json"
    report = _load_object(path)
    if report.get("schemaVersion") != 1 or report.get("status") not in REPORT_STATUSES:
        raise CommandError("output has no supported conversion report")
    return path, report


def _require_resolved_dependencies(report: dict[str, Any], stage: str) -> None:
    dependencies = report.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise CommandError("conversion report dependencies field has invalid type")
    unresolved: list[str] = []
    for item in dependencies:
        if not isinstance(item, dict):
            unresolved.append("unknown")
            continue
        blocked_stages = item.get("blockedStages")
        if item.get("status") != "resolved" and (
            blocked_stages is None or not isinstance(blocked_stages, list) or stage in blocked_stages
        ):
            unresolved.append(str(item.get("id", "unknown")))
    if unresolved:
        raise CommandError(f"dependency-manifest-required: {', '.join(unresolved)}")


def _agent_verification_accepted(checks: object) -> bool:
    return (
        isinstance(checks, dict)
        and (checks.get("analyzerClean") is True or checks.get("analyzerStatus") == "excluded-external-artifact")
        and checks.get("allBindingsPresent") is True
        and checks.get("allProceduresVerified") is True
        and checks.get("diagnostics", []) == []
    )


def _verify_remediation(output: Path, run_root: Path, evidence_path: Path | None = None) -> dict[str, object]:
    report_path, report = _conversion_report(output)
    structural = report.get("diagnostics", [])
    if structural:
        if evidence_path is None or not evidence_path.is_file():
            raise CommandError("structural remediation requires --evidence")
        evidence = _load_object(evidence_path)
        decisions = evidence.get("structuralDiagnostics")
        if not isinstance(decisions, list):
            raise CommandError("structural remediation evidence is invalid")
        expected = {(item.get("code"), item.get("path")) for item in structural if isinstance(item, dict)}
        actual = {
            (item.get("code"), item.get("path"))
            for item in decisions
            if isinstance(item, dict) and item.get("outcome") in {"removed", "replaced"}
        }
        if len(expected) != len(structural) or actual != expected or len(actual) != len(decisions):
            raise CommandError("structural remediation evidence must resolve every diagnostic exactly once")
        validation = _validate_forms(output)
        if not validation:
            raise CommandError("structural remediation requires successful profile validation of affected forms")
        coverage = report.get("coverage")
        if (
            not isinstance(coverage, dict)
            or any(not isinstance(coverage.get(key), int) for key in ("input", "converted", "manual", "excluded"))
            or coverage["input"] != coverage["converted"] + coverage["manual"] + coverage["excluded"]
            or coverage["manual"] < len(structural)
        ):
            raise CommandError("structural remediation coverage is inconsistent")
        report["resolvedDiagnostics"] = [
            {
                **diagnostic,
                "outcome": next(
                    item["outcome"]
                    for item in decisions
                    if item.get("code") == diagnostic.get("code") and item.get("path") == diagnostic.get("path")
                ),
            }
            for diagnostic in structural
        ]
        report["diagnostics"] = []
        removed = sum(item["outcome"] == "removed" for item in report["resolvedDiagnostics"])
        replaced = len(report["resolvedDiagnostics"]) - removed
        coverage["manual"] -= len(report["resolvedDiagnostics"])
        coverage["excluded"] += removed
        coverage["converted"] += replaced
        report.setdefault("stages", {})["structure"] = "verified"
        report["structureChecks"] = {"validation": validation, "verifiedAt": timestamp_utc()}
    bindings: list[dict[str, object]] = []
    procedure_checks: list[dict[str, object]] = []
    diagnostics: list[dict[str, object]] = []
    current_hashes: dict[str, str] = {}
    for form in report.get("forms", []):
        if not isinstance(form, dict) or not isinstance(form.get("name"), str):
            continue
        form_name = form["name"]
        candidates = list(output.glob(f"*/Forms/{form_name}/Ext/Form/Module.bsl"))
        xml_candidates = list(output.glob(f"*/Forms/{form_name}/Ext/Form.xml"))
        if len(candidates) != 1 or len(xml_candidates) != 1:
            raise CommandError(f"managed form artifacts are incomplete: {form_name}")
        module = candidates[0]
        module_text = module.read_text(encoding="utf-8-sig")
        procedure_names = {str(item["name"]) for item in _procedures(module)}
        claimed_procedures: set[str] = set()
        bsl = form.get("bsl")
        if isinstance(bsl, dict):
            for item in bsl.get("agentPlan", []):
                if not isinstance(item, dict) or not isinstance(item.get("procedure"), str):
                    continue
                procedure = item["procedure"]
                outcome = str(item.get("outcome", "present"))
                targets = item.get("targets", [])
                if outcome == "present":
                    claimed_procedures.add(procedure)
                    if isinstance(targets, list) and all(isinstance(target, str) for target in targets):
                        claimed_procedures.update(targets)
                        verified = procedure in procedure_names and all(target in procedure_names for target in targets)
                    else:
                        verified = False
                elif outcome == "removed":
                    verified = procedure not in procedure_names
                elif (
                    outcome == "replaced"
                    and isinstance(targets, list)
                    and targets
                    and all(isinstance(target, str) for target in targets)
                ):
                    claimed_procedures.update(targets)
                    verified = procedure not in procedure_names and all(target in procedure_names for target in targets)
                else:
                    verified = False
                procedure_checks.append(
                    {
                        "form": form_name,
                        "procedure": procedure,
                        "outcome": outcome,
                        "targets": targets,
                        "verified": verified,
                    }
                )
                item["status"] = "verified" if verified else "remediation-open"
        for procedure in sorted(procedure_names - claimed_procedures):
            procedure_checks.append(
                {"form": form_name, "procedure": procedure, "outcome": "unclaimed", "targets": [], "verified": False}
            )
        xml = xml_candidates[0].read_text(encoding="utf-8-sig")
        handlers = re.findall(r"<(?:Event\s+name=\"[^\"]+\"|Action)>([^<]+)</(?:Event|Action)>", xml)
        for handler in handlers:
            bindings.append({"form": form_name, "handler": handler, "present": handler in procedure_names})
        for code, pattern in (
            ("ordinary-form-elements-api", r"\bЭлементыФормы\b"),
            ("ordinary-form-status-api", r"\bСостояние\s*\("),
            ("ordinary-form-cancel-api", r"\bОбработкаПрерыванияПользователя\s*\("),
            ("form-data-template-api", r"\b(?:Объект|ОтчетОбъект|ОбработкаОбъект)\.ПолучитьМакет\s*\("),
            ("com-api", r"\bНовый\s+COMObject\s*\("),
            ("external-application-api", r"\bЗапуститьПриложение\s*\("),
            ("ordinary-form-folder-api", r"\bРаботаСФайлами\.ВыбратьКаталог\s*\("),
        ):
            if re.search(pattern, module_text):
                diagnostics.append({"code": code, "form": form_name})
        current_hashes[form_name] = _sha(module)
        if isinstance(bsl, dict):
            bsl["currentSha256"] = current_hashes[form_name]
    checks = {
        "analyzerStatus": "excluded-external-artifact",
        "diagnostics": diagnostics,
        "bindings": bindings,
        "allBindingsPresent": all(bool(item["present"]) for item in bindings),
        "procedures": procedure_checks,
        "allProceduresVerified": all(bool(item["verified"]) for item in procedure_checks),
        "verifiedAt": timestamp_utc(),
    }
    report["agentChecks"] = checks
    report["status"] = "agent-remediation-required"
    report.setdefault("stages", {})["agent"] = "verified" if _agent_verification_accepted(checks) else "failed"
    write_json(report_path, _redact(report))
    write_json(run_root / "remediation-summary.json", _redact(checks))
    return report


def _compatibility_for_profile(profile: RuntimeProfile) -> str:
    dump_dir = profile.string("capabilities", "dumpSrc", "outputDir")
    if not dump_dir:
        return "unknown"
    configuration = canonical_path(project_root() / dump_dir) / "Configuration.xml"
    if not configuration.is_file():
        return "unknown"
    match = re.search(r"<CompatibilityMode>([^<]+)</CompatibilityMode>", configuration.read_text(encoding="utf-8-sig"))
    return match.group(1) if match else "unknown"


def _validate_forms(output: Path, object_name: str | None = None) -> list[dict[str, object]]:
    from . import metadata

    evidence: list[dict[str, object]] = []
    pattern = f"{object_name}/Forms/*/Ext/Form.xml" if object_name else "*/Forms/*/Ext/Form.xml"
    for form in sorted(output.glob(pattern)):
        relative = form.relative_to(output)
        owner_name, form_name = relative.parts[0], relative.parts[2]
        try:
            descriptor = metadata.xml_read(
                metadata.read_file(output / f"{owner_name}.xml", metadata.FILE_LIMIT), f"{{{MD_NS}}}MetaDataObject"
            )
        except (metadata.Rejected, OSError):
            raise CommandError("invalid external object descriptor for form validation") from None
        owners = [
            node
            for node in descriptor
            if node.tag in {f"{{{MD_NS}}}ExternalDataProcessor", f"{{{MD_NS}}}ExternalReport"}
        ]
        if len(owners) != 1:
            raise CommandError("form validation requires one external object descriptor")
        kind = owners[0].tag.rsplit("}", 1)[-1]
        logical = f"{kind}.{owner_name}.Form.{form_name}"
        item: dict[str, object] = {"form": str(relative), "engine": "metadata"}
        # Retain historical report keys; each value comes from a fresh invocation.
        for action, report_key, status in (
            ("verify", "form-validate", "verified"),
            ("inspect", "form-info", "inspected"),
        ):
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.python.cli",
                    "metadata",
                    action,
                    "--root",
                    str(output),
                    "--object",
                    logical,
                ],
                cwd=project_root(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if completed.returncode:
                raise CommandError(f"metadata {action} failed for {form}", completed.returncode)
            try:
                result = json.loads(completed.stdout)
            except (ValueError, TypeError):
                raise CommandError(f"invalid metadata {action} result") from None
            if (
                completed.stderr
                or not isinstance(result, dict)
                or result.get("schemaVersion") != 1
                or result.get("status") != status
                or result.get("error") is not None
            ):
                raise CommandError(f"invalid metadata {action} result")
            item[report_key] = "passed"
        evidence.append(item)
    return evidence


def _build_for_profile(
    output: Path,
    profile_path: Path,
    artifact: Path,
    run_root: Path,
    report_output: Path | None = None,
    object_name: str | None = None,
) -> dict[str, object]:
    report_path, report = _conversion_report(report_output or output)
    _require_resolved_dependencies(report, "build")
    coverage = report.get("coverage")
    if report.get("diagnostics") or not isinstance(coverage, dict) or coverage.get("manual") != 0:
        raise CommandError("build requires a complete structure conversion")
    checks = report.get("agentChecks")
    if not _agent_verification_accepted(checks):
        raise CommandError("build requires clean remediation verification")
    profile = load_runtime_profile(profile_path)
    if profile is None:
        raise CommandError("runtime profile is required")
    if profile.string("infobase", "mode") != "client-server":
        raise CommandError("only client-server profiles are supported for conversion builds")
    if artifact.exists():
        raise CommandError(f"artifact already exists: {artifact}")
    if _is_within(artifact, output):
        raise CommandError("artifact must be outside the conversion output")
    managed_relative = _relative_to_repo(output)
    artifact_relative = _relative_to_repo(artifact)
    validation = _validate_forms(output, object_name)
    roots = [output / f"{object_name}.xml"] if object_name else list(output.glob("*.xml"))
    if len(roots) != 1 or not roots[0].is_file():
        raise CommandError("conversion output must contain exactly one root XML")
    _load_local_env()
    binary = canonical_path(profile.require_string("platform", "binaryPath"))
    artifact.parent.mkdir(parents=True, exist_ok=True)
    root_text = roots[0].read_text(encoding="utf-8-sig", errors="replace")
    skill = "erf-build" if "<ExternalReport" in root_text else "epf-build"
    object_tree = output / roots[0].stem
    if not object_tree.is_dir():
        raise CommandError("conversion output must contain a matching object tree")
    command = [
        sys.executable,
        "-m",
        "scripts.python.cli",
        "imported-skill",
        skill,
        "-Profile",
        str(profile_path),
        "-SourceFile",
        str(roots[0]),
        "-OutputFile",
        str(artifact),
    ]
    completed = subprocess.run(
        command, cwd=project_root(), capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if completed.returncode or not artifact.is_file():
        log = completed.stdout + completed.stderr
        raise CommandError(f"platform build failed for {profile.name}: {log.strip()}", completed.returncode or 1)
    evidence = {
        "target": _profile_target(profile),
        "profile": profile.name,
        "managed": managed_relative,
        "managedTreeSha256": _managed_source_sha(roots[0], object_tree),
        "platformVersion": binary.parent.parent.name,
        "compatibilityMode": _compatibility_for_profile(profile),
        "artifactSha256": _sha(artifact),
        "artifact": artifact_relative,
        "validation": validation,
        "builtAt": timestamp_utc(),
    }
    builds = report.setdefault("builds", [])
    if not isinstance(builds, list):
        raise CommandError("conversion report builds field has invalid type")
    builds.append(evidence)
    report.setdefault("stages", {})["build"] = "passed"
    write_json(report_path, _redact(report))
    write_json(run_root / "build-summary.json", _redact(evidence))
    return evidence


def _build_sources(output: Path, profile_path: Path, artifact: Path, run_root: Path) -> dict[str, object]:
    suffix = artifact.suffix.lower()
    if suffix not in {".epf", ".erf"}:
        raise CommandError("build-sources artifact must be .epf or .erf")
    managed_root = canonical_path(project_root() / "src" / suffix[1:] / "managed")
    if output.parent != managed_root or not output.is_dir() or not output.name.isidentifier():
        raise CommandError(f"build-sources requires src/{suffix[1:]}/managed/<name>")
    for path in (output, *output.rglob("*")):
        if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
            raise CommandError(f"managed source contains symlink or reparse point: {path.relative_to(output)}")
    roots = list(output.glob("*.xml"))
    if len(roots) != 1 or not roots[0].is_file() or not (output / roots[0].stem).is_dir():
        raise CommandError("managed source must contain one matching root XML and object directory")
    if artifact.exists() or _is_within(artifact, output):
        raise CommandError("artifact must be a new path outside managed source")
    if run_root.exists():
        raise CommandError("build-sources requires a new run-root")
    profile = load_runtime_profile(profile_path)
    if profile is None or profile.string("infobase", "mode") != "client-server":
        raise CommandError("build-sources requires a client-server runtime profile")
    _load_local_env()
    binary = canonical_path(profile.require_string("platform", "binaryPath"))
    password = resolve_secret_value(profile.require_string("infobase", "auth", "passwordEnv"))
    command = [
        sys.executable,
        "-m",
        "scripts.python.cli",
        "imported-skill",
        f"{suffix[1:]}-build",
        "-Profile",
        str(profile_path),
        "-SourceFile",
        str(roots[0]),
    ]
    run_root.mkdir(parents=True)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    temporary = artifact.with_name(f".{artifact.stem}.{uuid.uuid4().hex}.tmp{artifact.suffix}")
    command.extend(["-OutputFile", str(temporary)])
    try:
        completed = subprocess.run(
            command, cwd=project_root(), capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if completed.returncode or not temporary.is_file():
            detail = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
            raise CommandError(f"platform build failed for {profile.name}: {detail}", completed.returncode or 1)
        os.link(temporary, artifact)
        temporary.unlink()
        evidence: dict[str, object] = {
            "status": "built",
            "managed": _relative_to_repo(output),
            "designerName": roots[0].stem,
            "repositoryName": output.name,
            "managedTreeSha256": _input_sha(output),
            "profile": profile.name,
            "target": _profile_target(profile),
            "platformVersion": binary.parent.parent.name,
            "artifact": _relative_to_repo(artifact),
            "artifactSha256": _sha(artifact),
            "builtAt": timestamp_utc(),
        }
        write_json(run_root / "build-summary.json", evidence)
        return evidence
    except Exception as error:
        temporary.unlink(missing_ok=True)
        detail = str(error).replace(password, "<redacted>")
        raise CommandError(detail, getattr(error, "returncode", 1)) from error


def _live_start(
    output: Path, profile_path: Path, artifact: Path, run_root: Path, allow_current_target: bool
) -> dict[str, object]:
    if not allow_current_target:
        raise CommandError("live smoke is fail-closed; pass --allow-current-target after explicit approval")
    report_path, report = _conversion_report(output)
    _require_resolved_dependencies(report, "live-start")
    profile = load_runtime_profile(profile_path)
    if profile is None:
        raise CommandError("runtime profile is required")
    target = _profile_target(profile)
    builds = report.get("builds")
    if not isinstance(builds, list) or not any(
        isinstance(item, dict) and item.get("target") == target and item.get("artifactSha256") == _sha(artifact)
        for item in builds
    ):
        raise CommandError("live smoke requires a matching successful build evidence")
    _load_local_env()
    binary = canonical_path(profile.require_string("platform", "binaryPath"))
    password = resolve_secret_value(profile.require_string("infobase", "auth", "passwordEnv"))
    server = profile.require_string("infobase", "server")
    ref = profile.require_string("infobase", "ref")
    user = profile.require_string("infobase", "auth", "user")
    command = [
        str(binary),
        "ENTERPRISE",
        f"/S{server}\\{ref}",
        f"/N{user}",
        f"/P{password}",
        "/Execute",
        str(artifact),
        "/Out",
        str(run_root / "enterprise.log"),
        "/DisableStartupDialogs",
    ]
    process = subprocess.Popen(command, cwd=run_root)
    try:
        exit_code = process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        exit_code = None
    if exit_code is not None:
        log_path = run_root / "enterprise.log"
        log = log_path.read_text(encoding="utf-8-sig", errors="replace") if log_path.is_file() else ""
        raise CommandError(f"live client exited before readiness (code {exit_code}): {log.strip()}", exit_code or 1)
    evidence = {
        "target": target,
        "profile": profile.name,
        "artifactSha256": _sha(artifact),
        "processId": process.pid,
        "status": "started",
        "startedAt": timestamp_utc(),
    }
    attempts = report.setdefault("liveAttempts", [])
    if not isinstance(attempts, list):
        raise CommandError("conversion report liveAttempts field has invalid type")
    attempts.append(evidence)
    write_json(report_path, _redact(report))
    write_json(run_root / "live-start-summary.json", _redact(evidence))
    return evidence


def _live_confirm(
    output: Path,
    profile_path: Path,
    artifact: Path,
    process_id: int | None,
    evidence_text: str,
    run_root: Path,
    allow_manual_acceptance: bool = False,
) -> dict[str, object]:
    report_path, report = _conversion_report(output)
    _require_resolved_dependencies(report, "live-confirm")
    profile = load_runtime_profile(profile_path)
    if profile is None:
        raise CommandError("runtime profile is required")
    target = _profile_target(profile)
    artifact_hash = _sha(artifact)
    if allow_manual_acceptance:
        builds = report.get("builds")
        if not isinstance(builds, list) or not any(
            isinstance(item, dict) and item.get("target") == target and item.get("artifactSha256") == artifact_hash
            for item in builds
        ):
            raise CommandError("manual live confirmation requires matching build evidence")
    else:
        attempts = report.get("liveAttempts")
        matching = (
            [
                item
                for item in attempts
                if isinstance(item, dict) and item.get("target") == target and item.get("processId") == process_id
            ]
            if isinstance(attempts, list)
            else []
        )
        if len(matching) != 1 or matching[0].get("artifactSha256") != artifact_hash:
            raise CommandError("no matching live-start evidence")
    evidence_path = canonical_path(evidence_text)
    if not evidence_path.is_file():
        raise CommandError("live confirmation requires an existing evidence file")
    confirmation = {
        "target": target,
        "profile": profile.name,
        "artifactSha256": artifact_hash,
        "processId": process_id,
        "mode": "operator-manual" if allow_manual_acceptance else "managed-start",
        "status": "passed",
        "evidence": {"path": str(evidence_path), "sha256": _sha(evidence_path)},
        "confirmedAt": timestamp_utc(),
    }
    live_checks = report.setdefault("liveChecks", [])
    if not isinstance(live_checks, list):
        raise CommandError("conversion report liveChecks field has invalid type")
    live_checks.append(confirmation)
    report.setdefault("stages", {})["live"] = "passed"
    write_json(report_path, _redact(report))
    write_json(run_root / "live-confirm-summary.json", _redact(confirmation))
    return confirmation


def _mark_ready(output: Path, profile_path: Path, artifact: Path, run_root: Path) -> dict[str, Any]:
    report_path, report = _conversion_report(output)
    _require_resolved_dependencies(report, "ready")
    profile = load_runtime_profile(profile_path)
    if profile is None:
        raise CommandError("runtime profile is required")
    target = _profile_target(profile)
    artifact_hash = _sha(artifact)
    checks = report.get("agentChecks")
    if report.get("diagnostics") or not _agent_verification_accepted(checks):
        raise CommandError("ready requires clean structure and handler bindings")
    plans: list[object] = []
    for form in report.get("forms", []):
        bsl = form.get("bsl") if isinstance(form, dict) else None
        if not isinstance(bsl, dict) or not isinstance(bsl.get("agentPlan"), list):
            raise CommandError("ready requires a closed BSL agent plan")
        plans.extend(bsl["agentPlan"])
    if any(not isinstance(item, dict) or item.get("status") != "verified" for item in plans):
        raise CommandError("ready requires every BSL procedure to be verified")
    builds = report.get("builds", [])
    lives = report.get("liveChecks", [])

    def matches(item: object) -> bool:
        return isinstance(item, dict) and item.get("target") == target and item.get("artifactSha256") == artifact_hash

    build_matches = [item for item in builds if matches(item)]
    if not any(
        isinstance(item.get("validation"), list)
        and item["validation"]
        and item.get("compatibilityMode") not in {None, "", "unknown"}
        and (
            bool(item.get("platformVersion"))
            or (isinstance(item.get("platform"), dict) and bool(item["platform"].get("version")))
        )
        and all(
            isinstance(check, dict)
            and check.get("engine") == "metadata"
            and check.get("form-validate") == "passed"
            and check.get("form-info") == "passed"
            for check in item["validation"]
        )
        for item in build_matches
    ) or not any(matches(item) and item.get("status") == "passed" for item in lives):
        raise CommandError("ready requires matching build and live acceptance evidence")
    report["status"] = "ready"
    report.setdefault("stages", {})["ready"] = "passed"
    report["ready"] = {
        "target": target,
        "profile": profile.name,
        "artifactSha256": artifact_hash,
        "verifiedAt": timestamp_utc(),
    }
    write_json(report_path, _redact(report))
    write_json(run_root / "ready-summary.json", _redact(report["ready"]))
    return report["ready"]


def _publish_sources(
    input_path: Path,
    output: Path,
    run_root: Path,
    v8unpack: str,
    profile_path: Path | None = None,
    repository_name: str | None = None,
) -> dict[str, object]:
    report_path, report = _conversion_report(output)
    _require_resolved_dependencies(report, "publish")
    coverage = report.get("coverage")
    checks = report.get("agentChecks")
    if report.get("diagnostics") or not isinstance(coverage, dict) or coverage.get("manual") != 0:
        raise CommandError("source publication requires a complete structure conversion")
    if not _agent_verification_accepted(checks):
        raise CommandError("source publication requires clean remediation verification")
    root_xml_candidates = list(output.glob("*.xml"))
    if len(root_xml_candidates) != 1:
        raise CommandError("managed source tree must contain exactly one root XML")
    root_xml = root_xml_candidates[0]
    object_tree = output / root_xml.stem
    if not object_tree.is_dir():
        raise CommandError("managed source tree is incomplete")
    managed_hash = _managed_source_sha(root_xml, object_tree)

    builds = report.get("builds")
    forms = report.get("forms")
    valid_builds = (
        []
        if not isinstance(builds, list)
        else [
            item
            for item in builds
            if isinstance(item, dict)
            and isinstance(item.get("artifact"), str)
            and canonical_path(project_root() / item["artifact"]).is_file()
            and item.get("artifactSha256") == _sha(canonical_path(project_root() / item["artifact"]))
            and item.get("managedTreeSha256") == managed_hash
            and isinstance(forms, list)
            and isinstance(item.get("validation"), list)
            and len(item["validation"]) == len(forms)
            and all(
                isinstance(validation, dict)
                and validation.get("engine") == "metadata"
                and validation.get("form-validate") == "passed"
                and validation.get("form-info") == "passed"
                for validation in item["validation"]
            )
        ]
    )
    if not valid_builds:
        raise CommandError("source publication requires a matching successful control build")
    summary: dict[str, object] | None = None
    if input_path.is_dir():
        package_root = input_path.parent
        summary_path = package_root / "preparation-summary.json"
        if not summary_path.is_file():
            raise CommandError("prepared source publication requires its package summary")
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CommandError("prepared source package summary is invalid") from error
        if not isinstance(summary, dict):
            raise CommandError("prepared source package summary is invalid")
        source_path = summary.get("sourcePath")
        managed_path = summary.get("managedPath")
        report_relative = summary.get("reportPath")
        if (
            not isinstance(source_path, str)
            or not isinstance(managed_path, str)
            or not isinstance(report_relative, str)
        ):
            raise CommandError("prepared source package paths must be relative and contained")
        relative_paths = (source_path, managed_path, report_relative)
        if any(
            not isinstance(item, str) or Path(item).is_absolute() or ".." in Path(item).parts for item in relative_paths
        ):
            raise CommandError("prepared source package paths must be relative and contained")
        if (
            canonical_path(package_root / source_path) != input_path
            or canonical_path(package_root / managed_path) != output
            or canonical_path(package_root / report_relative) != report_path
            or summary.get("sourceTreeSha256") != _input_sha(input_path)
            or summary.get("inputSha256") != report.get("inputSha256")
        ):
            raise CommandError("prepared source package identity does not match the conversion report")
        summary_source = summary.get("source")
        report_source = report.get("source")
        if (
            not isinstance(summary_source, dict)
            or not isinstance(report_source, dict)
            or any(summary_source.get(key) != report_source.get(key) for key in ("kind", "name"))
        ):
            raise CommandError("prepared source package identity does not match the conversion report")
    elif report.get("inputSha256") != _input_sha(input_path):
        raise CommandError("source publication input does not match the converted input")

    source = report.get("source")
    if not isinstance(source, dict):
        raise CommandError("conversion report has no source identity")
    name = source.get("name")
    kind = source.get("kind")
    if not isinstance(name, str) or not name.isidentifier() or kind not in {"ExternalReport", "ExternalDataProcessor"}:
        raise CommandError("source publication identity does not match the conversion report")
    if root_xml != output / f"{name}.xml" or object_tree != output / name:
        raise CommandError("managed source tree is incomplete")

    target_name = repository_name or name
    if not target_name.isidentifier():
        raise CommandError("repository-name must be a valid 1C identifier")
    if kind == "ExternalDataProcessor":
        if summary is None or summary.get("ordinaryPath") is None:
            raise CommandError("EPF source publication requires a prepared package with ordinary sources")
        ordinary_relative = summary["ordinaryPath"]
        if (
            not isinstance(ordinary_relative, str)
            or Path(ordinary_relative).is_absolute()
            or ".." in Path(ordinary_relative).parts
        ):
            raise CommandError("prepared ordinary path must be relative and contained")
        ordinary_source = canonical_path(input_path.parent / ordinary_relative)
        if not ordinary_source.is_dir() or summary.get("ordinaryTreeSha256") != _input_sha(ordinary_source):
            raise CommandError("prepared ordinary sources do not match the package summary")
        source_root = project_root() / "src" / "epf"
    else:
        extracted = _extract(input_path, run_root / "publish-extracted", v8unpack, profile_path, run_root)
        roots = [path for filename in ROOT_FILES if (path := extracted / filename).is_file()]
        if roots:
            extracted_kind, metadata, _forms = _read_source(extracted)
            if extracted_kind != kind or metadata.get("name") != name:
                raise CommandError("source publication identity does not match the conversion report")
        elif forms or not (extracted / "Designer" / f"{name}.xml").is_file():
            raise CommandError("source publication identity does not match the conversion report")
        ordinary_source = extracted
        source_root = project_root() / "src" / "erf"
    ordinary_parent = source_root / "ordinary"
    managed_parent = source_root / "managed"
    ordinary_target = ordinary_parent / (target_name if kind == "ExternalDataProcessor" else f"{target_name}.v8unpack")
    managed_bundle_target = managed_parent / target_name
    managed_xml_target = managed_bundle_target / root_xml.name
    managed_tree_target = managed_bundle_target / name
    targets = (ordinary_target, managed_bundle_target)
    if any(target.exists() for target in targets):
        raise CommandError("canonical source target already exists; refusing to overwrite")
    ordinary_parent.mkdir(parents=True, exist_ok=True)
    managed_parent.mkdir(parents=True, exist_ok=True)
    staging_id = uuid.uuid4().hex
    ordinary_stage = ordinary_parent / f".{name}.v8unpack.{staging_id}"
    managed_bundle_stage = managed_parent / f".{name}.{staging_id}"
    staging_paths = (ordinary_stage, managed_bundle_stage)
    published: list[tuple[Path, Path]] = []
    publication_summary = run_root / "source-publication-summary.json"
    report_backup = report_path.with_name(f".{report_path.name}.publication-backup.{staging_id}")
    shutil.copy2(report_path, report_backup)
    try:
        shutil.copytree(ordinary_source, ordinary_stage)
        managed_bundle_stage.mkdir()
        shutil.copy2(root_xml, managed_bundle_stage / root_xml.name)
        shutil.copytree(object_tree, managed_bundle_stage / name)
        moves = (
            (ordinary_stage, ordinary_target),
            (managed_bundle_stage, managed_bundle_target),
        )
        for source_path, target_path in moves:
            os.replace(source_path, target_path)
            published.append((source_path, target_path))
        evidence = {
            "ordinary": {"path": _relative_to_repo(ordinary_target), "sha256": _input_sha(ordinary_target)},
            "managed": {
                "rootXml": _relative_to_repo(managed_xml_target),
                "objectTree": _relative_to_repo(managed_tree_target),
                "sha256": _managed_source_sha(managed_xml_target, managed_tree_target),
            },
            "publicationBuildSha256": valid_builds[-1]["artifactSha256"],
            "repositoryName": target_name,
            "publishedAt": timestamp_utc(),
        }
        report["canonicalSources"] = evidence
        write_json(report_path, _redact(report))
        write_json(publication_summary, _redact(evidence))
    except BaseException:
        for source_path, target_path in reversed(published):
            if target_path.exists():
                os.replace(target_path, source_path)
        publication_summary.unlink(missing_ok=True)
        os.replace(report_backup, report_path)
        raise
    finally:
        for staging_path in staging_paths:
            if staging_path.is_dir():
                shutil.rmtree(staging_path, ignore_errors=True)
            elif staging_path.exists():
                staging_path.unlink(missing_ok=True)
        report_backup.unlink(missing_ok=True)

    return evidence


def _build_published_sources(output: Path, profile_path: Path, artifact: Path, run_root: Path) -> dict[str, object]:
    _report_path, report = _conversion_report(output)
    source = report.get("source")
    canonical = report.get("canonicalSources")
    if not isinstance(source, dict):
        raise CommandError("published build requires canonical source evidence")
    name = source.get("name")
    kind = source.get("kind")
    if (
        not isinstance(name, str)
        or not name.isidentifier()
        or kind not in {"ExternalReport", "ExternalDataProcessor"}
        or not isinstance(canonical, dict)
    ):
        raise CommandError("published build requires canonical source evidence")
    managed = canonical.get("managed")
    repository_name = canonical.get("repositoryName")
    if not isinstance(managed, dict) or not isinstance(repository_name, str) or not repository_name.isidentifier():
        raise CommandError("published managed sources do not match canonical evidence")
    root_xml = canonical_path(project_root() / str(managed.get("rootXml", "")))
    object_tree = canonical_path(project_root() / str(managed.get("objectTree", "")))
    managed_root = root_xml.parent
    family = "erf" if kind == "ExternalReport" else "epf"
    managed_parent = canonical_path(project_root() / "src" / family / "managed")
    if (
        not _is_within(root_xml, managed_parent)
        or not _is_within(object_tree, managed_parent)
        or root_xml.parent != object_tree.parent
        or root_xml.parent.name != repository_name
        or root_xml.name != f"{name}.xml"
        or object_tree.name != name
        or not root_xml.is_file()
        or not object_tree.is_dir()
        or managed.get("sha256") != _managed_source_sha(root_xml, object_tree)
    ):
        raise CommandError("published managed sources do not match canonical evidence")
    evidence = _build_for_profile(
        managed_root,
        profile_path,
        artifact,
        run_root,
        report_output=output,
        object_name=name,
    )
    write_json(run_root / "published-build-summary.json", _redact(evidence))
    return evidence


def _convert_into(
    input_path: Path,
    output: Path,
    run_root: Path,
    profile_path: Path,
    v8unpack: str,
    artifact_output_root: str | None = None,
    ordinary_output: Path | None = None,
) -> tuple[dict[str, Any], Path]:
    extracted = _extract(input_path, run_root / "extracted", v8unpack, profile_path, run_root)
    kind, metadata, forms = _read_source(extracted)
    expected_kind = {".epf": "ExternalDataProcessor", ".erf": "ExternalReport"}.get(input_path.suffix.lower())
    if expected_kind and kind != expected_kind:
        raise CommandError(f"input extension does not match v8unpack root: expected {expected_kind}, got {kind}")
    arguments = (input_path, extracted, output, kind, profile_path, run_root, v8unpack)
    object_root, object_entities = (
        _prepare_object_root(*arguments, ordinary_output)
        if ordinary_output is not None
        else _prepare_object_root(*arguments)
    )
    report = _report(kind, metadata, forms, object_entities)
    report["startedAt"] = timestamp_utc()
    report["inputSha256"] = _input_sha(input_path)
    report["object"] = {"entities": object_entities}
    report["artifacts"] = {
        "outputRoot": artifact_output_root or str(output),
        "forms": [f"{object_root.name}/Forms/{form.name}/Ext/Form.xml" for form in forms],
        "modules": [f"{object_root.name}/Forms/{form.name}/Ext/Form/Module.bsl" for form in forms],
    }
    report["coverage"]["input"] += len(object_entities)
    for entity in object_entities:
        outcome = str(entity.get("outcome") or "manual")
        report["coverage"][outcome if outcome in {"converted", "manual", "excluded"} else "manual"] += 1
    for form, detail in zip(forms, report["forms"], strict=True):
        _, module = _compile_form(object_root, form, detail.pop("dsl"))
        detail["bsl"]["copiedSha256"] = _sha(module)
    report["status"] = "structure-remediation-required" if report["diagnostics"] else "agent-remediation-required"
    report["stages"]["structure"] = "failed" if report["diagnostics"] else "structure-converted"
    report["stages"]["agent"] = "required"
    write_json(output / "conversion-report.json", _redact(report))
    return report, extracted


def _prepare_package(
    input_path: Path, output: Path, profile_path: Path, v8unpack: str, expected_sha256: str | None = None
) -> dict[str, Any]:
    _check_expected_sha(input_path, expected_sha256)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    evidence = Path(tempfile.mkdtemp(prefix=f".{output.name}.evidence.", dir=output.parent))
    try:
        managed = staging / "managed"
        managed.mkdir()
        report, extracted = _convert_into(
            input_path,
            managed,
            evidence,
            profile_path,
            v8unpack,
            "managed",
            staging / "ordinary" if input_path.suffix.lower() == ".epf" else None,
        )
        shutil.copytree(extracted, staging / "source")
        source = report["source"]
        family = "erf" if source["kind"] == "ExternalReport" else "epf"
        modules = [f"managed/{path}" for path in report["artifacts"]["modules"]]
        summary = {
            "schemaVersion": 1,
            "status": report["status"],
            "source": {"kind": source["kind"], "family": family, "name": source["name"]},
            "inputSha256": report["inputSha256"],
            "sourceTreeSha256": _input_sha(staging / "source"),
            "sourcePath": "source",
            "managedPath": "managed",
            "reportPath": "managed/conversion-report.json",
            "modules": modules,
            "canonicalRootHint": f"src/{family}",
            "nextAction": "resolve-structure" if report["status"] == "structure-remediation-required" else "adapt-bsl",
        }
        if (staging / "ordinary").is_dir():
            summary.update({"ordinaryPath": "ordinary", "ordinaryTreeSha256": _input_sha(staging / "ordinary")})
        write_json(staging / "preparation-summary.json", _redact(summary))
        os.replace(staging, output)
        shutil.rmtree(evidence, ignore_errors=True)
        return summary
    except BaseException as error:
        recovery_preserved = os.path.lexists(staging / ".managed.metadata-state") or os.path.lexists(
            staging / ".managed.metadata-plan.json"
        )
        if not recovery_preserved:
            shutil.rmtree(staging, ignore_errors=True)
        raw_detail = str(error)
        detail = (
            str(_redact(raw_detail))
            if raw_detail.startswith("input extension does not match v8unpack root:")
            else type(error).__name__
        )
        write_json(
            evidence / "preparation-failure.json",
            _redact(
                {
                    "status": "failed",
                    "type": type(error).__name__,
                    "message": detail,
                    "recoveryPreserved": recovery_preserved,
                    "recoveryRoot": str(staging) if recovery_preserved else None,
                }
            ),
        )
        raise CommandError(f"preparation failed: {detail}; redacted evidence: {evidence}") from error


def run_ordinary_form_conversion(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="ordinary-form-conversion")
    parser.add_argument(
        "action",
        choices=(
            "analyze",
            "convert",
            "prepare",
            "prepare-sources",
            "verify-remediation",
            "build",
            "build-sources",
            "build-published",
            "live-start",
            "live-confirm",
            "ready",
            "publish-sources",
        ),
    )
    parser.add_argument("--input")
    parser.add_argument("--run-root")
    parser.add_argument("--output")
    parser.add_argument("--v8unpack", default=os.environ.get("V8UNPACK", "v8unpack"))
    parser.add_argument("--profile")
    parser.add_argument("--artifact")
    parser.add_argument("--repository-name")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--allow-current-target", action="store_true")
    parser.add_argument("--allow-manual-acceptance", action="store_true")
    parser.add_argument("--process-id", type=int)
    parser.add_argument("--evidence")
    args = parser.parse_args(argv)
    if args.action == "prepare-sources":
        if (
            args.output
            or args.run_root
            or args.artifact
            or args.allow_current_target
            or args.allow_manual_acceptance
            or args.process_id
            or args.evidence
        ):
            raise CommandError("prepare-sources does not accept output, run-root, or downstream-stage arguments")
        if not args.input or not args.profile:
            raise CommandError("prepare-sources requires --input and --profile")
        summary = _prepare_sources(
            canonical_path(args.input),
            canonical_path(args.profile),
            args.v8unpack,
            args.repository_name,
            args.expected_sha256,
        )
        print(json.dumps(_redact(summary), ensure_ascii=False, indent=2))
        return 0
    if args.repository_name and args.action != "publish-sources":
        raise CommandError("repository-name is only supported by prepare-sources and publish-sources")
    if args.expected_sha256 and args.action != "prepare":
        raise CommandError("expected-sha256 is only supported by prepare and prepare-sources")
    if args.action == "prepare":
        if (
            args.run_root
            or args.artifact
            or args.allow_current_target
            or args.allow_manual_acceptance
            or args.process_id
            or args.evidence
        ):
            raise CommandError("prepare does not accept downstream-stage arguments")
        if not args.input or not args.output or not args.profile:
            raise CommandError("prepare requires --input, --output, and --profile")
        input_path = canonical_path(args.input)
        output = canonical_path(args.output)
        profile_path = canonical_path(args.profile)
        source_root = project_root() / "src"
        if not input_path.exists():
            raise CommandError(f"input does not exist: {input_path}")
        if not profile_path.is_file():
            raise CommandError(f"profile does not exist: {profile_path}")
        if (
            output.exists()
            or _is_within(output, source_root)
            or (input_path.is_dir() and _is_within(output, input_path))
        ):
            raise CommandError("output must be a new path outside src and the input tree")
        summary = _prepare_package(input_path, output, profile_path, args.v8unpack, args.expected_sha256)
        print(json.dumps(_redact(summary), ensure_ascii=False, indent=2))
        return 0
    if not args.run_root:
        parser.error("--run-root is required")
    run_root = canonical_path(args.run_root)
    if args.action in {
        "verify-remediation",
        "build",
        "build-sources",
        "build-published",
        "live-start",
        "live-confirm",
        "ready",
        "publish-sources",
    }:
        if not args.output:
            raise CommandError(f"{args.action} requires --output")
        output = canonical_path(args.output)
        if _is_within(run_root, output):
            raise CommandError("run-root must be outside the conversion output")
        if args.action != "build-sources":
            run_root.mkdir(parents=True, exist_ok=True)
        if args.action == "publish-sources":
            if not args.input:
                raise CommandError("publish-sources requires --input")
            input_path = canonical_path(args.input)
            source_root = project_root() / "src"
            if (
                not input_path.exists()
                or _is_within(run_root, source_root)
                or (input_path.is_dir() and _is_within(run_root, input_path))
            ):
                raise CommandError("publish-sources requires an existing input and run-root outside src and input")
            if input_path.suffix.lower() == ".epf" or (
                input_path.is_dir()
                and (input_path / "ExternalDataProcessor.json").is_file()
                and not (input_path.parent / "preparation-summary.json").is_file()
            ):
                raise CommandError(
                    "EPF source publication requires a prepared package; use prepare-sources or prepare first"
                )
            profile_path = canonical_path(args.profile) if args.profile else None
            evidence = _publish_sources(input_path, output, run_root, args.v8unpack, profile_path, args.repository_name)
            print(json.dumps(_redact(evidence), ensure_ascii=False, indent=2))
            return 0
        if args.action == "verify-remediation":
            report = _verify_remediation(output, run_root, canonical_path(args.evidence) if args.evidence else None)
            print(json.dumps(_redact(report), ensure_ascii=False, indent=2))
            return 0
        if args.action == "build-published":
            if not args.profile or not args.artifact:
                raise CommandError("build-published requires --profile and --artifact")
            evidence = _build_published_sources(
                output, canonical_path(args.profile), canonical_path(args.artifact), run_root
            )
            print(json.dumps(_redact(evidence), ensure_ascii=False, indent=2))
            return 0
        if not args.profile or not args.artifact:
            raise CommandError(f"{args.action} requires --profile and --artifact")
        if args.action == "build-sources":
            evidence = _build_sources(output, canonical_path(args.profile), canonical_path(args.artifact), run_root)
        elif args.action == "build":
            evidence = _build_for_profile(output, canonical_path(args.profile), canonical_path(args.artifact), run_root)
        elif args.action == "live-start":
            evidence = _live_start(
                output,
                canonical_path(args.profile),
                canonical_path(args.artifact),
                run_root,
                args.allow_current_target,
            )
        elif args.action == "live-confirm":
            if not args.evidence or (not args.allow_manual_acceptance and not args.process_id):
                raise CommandError(
                    "live-confirm requires --evidence and either --process-id or --allow-manual-acceptance"
                )
            evidence = _live_confirm(
                output,
                canonical_path(args.profile),
                canonical_path(args.artifact),
                args.process_id,
                args.evidence,
                run_root,
                args.allow_manual_acceptance,
            )
        else:
            evidence = _mark_ready(output, canonical_path(args.profile), canonical_path(args.artifact), run_root)
        print(json.dumps(_redact(evidence), ensure_ascii=False, indent=2))
        return 0
    if not args.input:
        raise CommandError(f"{args.action} requires --input")
    input_path = canonical_path(args.input)
    if not input_path.exists():
        raise CommandError(f"input does not exist: {input_path}")
    if args.action == "convert" and not args.output:
        raise CommandError("convert requires --output")
    if args.action == "convert" and not args.profile:
        raise CommandError("convert requires --profile to preserve object data types")
    output = canonical_path(args.output) if args.output else None
    source_root = project_root() / "src"
    if _is_within(run_root, source_root) or (input_path.is_dir() and _is_within(run_root, input_path)):
        raise CommandError("run-root must be outside src and the input tree")
    if output and (
        output.exists() or _is_within(output, source_root) or (input_path.is_dir() and _is_within(output, input_path))
    ):
        raise CommandError("output must be a new path outside src")
    run_root.mkdir(parents=True, exist_ok=True)
    profile_path = canonical_path(args.profile) if args.profile else None
    report: dict[str, Any] = {
        "schemaVersion": 1,
        "status": "failed",
        "stages": {
            "analysis": "failed",
            "structure": "pending",
            "agent": "pending",
            "build": "pending",
            "live": "pending",
        },
        "inputSha256": _input_sha(input_path),
    }
    if args.action == "convert" and output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
        try:
            report, _ = _convert_into(
                input_path, staging, run_root, canonical_path(args.profile), args.v8unpack, str(output)
            )
            os.replace(staging, output)
        except BaseException as error:
            shutil.rmtree(staging, ignore_errors=True)
            report["status"] = "failed"
            report.setdefault("stages", {})["structure"] = "failed"
            report["failure"] = {"type": type(error).__name__, "message": str(error)}
            write_json(run_root / "conversion-report.json", _redact(report))
            raise
    else:
        extracted = _extract(input_path, run_root / "extracted", args.v8unpack, profile_path, run_root)
        kind, metadata, forms = _read_source(extracted)
        expected_kind = {".epf": "ExternalDataProcessor", ".erf": "ExternalReport"}.get(input_path.suffix.lower())
        if expected_kind and kind != expected_kind:
            raise CommandError(f"input extension does not match v8unpack root: expected {expected_kind}, got {kind}")
        report = _report(kind, metadata, forms)
        report["startedAt"] = timestamp_utc()
        report["inputSha256"] = _input_sha(input_path)
    public_report = _redact(report)
    write_json(run_root / "conversion-report.json", public_report)
    print(json.dumps(public_report, ensure_ascii=False, indent=2))
    return 0
