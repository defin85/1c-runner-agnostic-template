"""Metadata editor; platform qualification is a separate operation."""

from __future__ import annotations

import argparse
import base64
import codecs
import copy
import difflib
import hashlib
import json
import math
import os
import re
import stat
import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import TypedDict, cast

import lxml.etree as etree

from . import metadata_ops
from .common import PROJECT_ROOT

FORM = "http://v8.1c.ru/8.3/xcf/logform"
MD = "http://v8.1c.ru/8.3/MDClasses"
XS = "http://www.w3.org/2001/XMLSchema"
V8 = "http://v8.1c.ru/8.1/data/core"
NS = {"f": FORM, "m": MD, "v8": V8}
NAME = re.compile(r"[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]{0,127}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
FILE_LIMIT = 16 * 1024 * 1024
CLOSURE_LIMIT = 128 * 1024 * 1024
PLAN_LIMIT = 32 * 1024 * 1024
PUBLIC_ERRORS = {
    2: "Invalid or unsupported metadata input",
    3: "Metadata state conflict",
    4: "Metadata structure check failed",
    5: "Metadata execution failed",
}
ENGINE_FILES = (
    "scripts/python/metadata.py",
    "scripts/python/metadata_ops.py",
    "scripts/python/metadata_form_schema.py",
    "scripts/python/metadata_object_schema.py",
    "scripts/python/metadata_object_ops.py",
    "scripts/python/metadata_predefined.py",
    "scripts/python/metadata_create.py",
    "scripts/python/metadata_predefined_ops.py",
    "scripts/python/metadata_form_ops.py",
    "scripts/python/metadata_form_compile.py",
    "scripts/python/metadata_borrow.py",
    "scripts/python/metadata_template_ops.py",
    "scripts/python/cli.py",
    "scripts/python/common.py",
    "uv.lock",
)
OPTIONAL_ENGINE_FILES = frozenset({"uv.lock"})
COMPANIONS = {"ContextMenu": "КонтекстноеМеню", "ExtendedTooltip": "РасширеннаяПодсказка"}
OWNER_TYPES = {
    "Catalogs": "Catalog",
    "Documents": "Document",
    "DataProcessors": "DataProcessor",
    "Reports": "Report",
    "ChartsOfAccounts": "ChartOfAccounts",
    "ChartsOfCharacteristicTypes": "ChartOfCharacteristicTypes",
    "ChartsOfCalculationTypes": "ChartOfCalculationTypes",
    "BusinessProcesses": "BusinessProcess",
    "Tasks": "Task",
    "InformationRegisters": "InformationRegister",
    "AccumulationRegisters": "AccumulationRegister",
    "AccountingRegisters": "AccountingRegister",
    "CalculationRegisters": "CalculationRegister",
    "ExchangePlans": "ExchangePlan",
}


class PackageManifestEntry(TypedDict):
    kind: str
    name: str
    root: str
    operation: str


class PackageManifest(TypedDict):
    schemaVersion: int
    packageId: str
    entries: list[PackageManifestEntry]


class Rejected(Exception):
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


class TemplateKindRejected(Rejected):
    """Public diagnostic naming the unsupported kind of a registered template."""

    KINDS = (
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

    def __init__(self, kind: str):
        shown = kind if kind in self.KINDS else "unknown"
        super().__init__(
            f"Template kind {shown} is not SpreadsheetDocument; template.* edits only spreadsheet templates", 2
        )


def is_template_target(target: str) -> bool:
    parts = target.split(".") if isinstance(target, str) else []
    return (len(parts) == 2 and parts[0] == "CommonTemplate") or (len(parts) == 4 and parts[2] == "Template")


class TypeDependencyRejected(Rejected):
    """Public diagnostic restricted to validated metadata identifiers."""

    def __init__(self, members: list[str], kind: str, name: str):
        require(
            0 < len(members) <= 8
            and all(NAME.fullmatch(part) for part in members)
            and NAME.fullmatch(kind)
            and NAME.fullmatch(name),
            "Invalid dependency diagnostic",
        )
        super().__init__(
            "Unresolved type dependency: "
            + ".".join(members)
            + " -> "
            + kind
            + "."
            + name
            + ". Add explicit object.create or object.borrow "
            "to the request; automatic adoption is disabled.",
            3,
        )


class FixedRejected(Rejected):
    """Public diagnostic whose text is a literal of the engine, never request data or paths."""

    def __init__(self, reason: str, code: int = 2):
        require(
            isinstance(reason, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9 ,.;:()=*/_-]{0,255}", reason) is not None,
            "Invalid public diagnostic",
        )
        super().__init__(reason, code)


class PublicRejected(Rejected):
    """Public diagnostic: a fixed reason and validated metadata identifiers only."""

    def __init__(self, reason: str, identifiers: list[str], code: int = 2):
        require(
            isinstance(reason, str)
            and re.fullmatch(r"[A-Za-z][A-Za-z ,()-]{0,127}", reason) is not None
            and 0 < len(identifiers) <= 32
            and all(
                isinstance(item, str) and all(NAME.fullmatch(part) for part in item.split(".")) for item in identifiers
            ),
            "Invalid public diagnostic",
        )
        super().__init__(reason + ": " + ", ".join(identifiers), code)


def require(condition, message: str, code: int = 2):
    if not condition:
        raise Rejected(message, code)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relative(value: str) -> str:
    require(isinstance(value, str) and bool(value), "Expected relative path")
    require(not any(c in value for c in "\\:\x00"), "Unsafe relative path")
    for part in value.split("/"):
        require(part not in {"", ".", ".."} and part.rstrip(" .") == part, "Unsafe path component")
        require(not any(ord(c) < 32 or c in '<>"|?*' for c in part), "Unsafe path characters")
        require(not re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(?:\..*)?", part), "Device path")
    return value


def safe_path(path: Path, *, missing: bool = False, writable: bool = False, hardlinks: bool = False) -> Path:
    # hardlinks=True only for read-only source roots: a hardlinked base dump is
    # never written, while a hardlinked target file would leak writes elsewhere.
    if os.name == "nt":
        require(
            not path.drive or re.fullmatch(r"[A-Za-z]:", path.drive) and path.is_absolute(), "Unsupported native path"
        )
        for part in path.parts[1 if path.anchor else 0 :]:
            if part not in {".", ".."}:
                relative(part)
    path = Path(os.path.abspath(path))
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
        kernel.GetDriveTypeW.restype = wintypes.UINT
        require(kernel.GetDriveTypeW(path.anchor) in {2, 3, 6}, "Expected a local drive")
        kernel.GetVolumeInformationW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPWSTR,
            wintypes.DWORD,
        ]
        kernel.GetVolumeInformationW.restype = wintypes.BOOL
        filesystem = ctypes.create_unicode_buffer(32)
        require(
            kernel.GetVolumeInformationW(path.anchor, None, 0, None, None, None, filesystem, len(filesystem)),
            "Cannot determine filesystem",
            5,
        )
        require(filesystem.value == "NTFS", "Expected NTFS filesystem")
    for component in (*reversed(path.parents), path):
        try:
            info = component.lstat()
        except FileNotFoundError:
            require(missing and component == path, "Missing path")
            continue
        require(
            not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
            "Links/reparse points are unsupported",
        )
        if component == path:
            require(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode), "Unsupported file type")
            require(
                not stat.S_ISREG(info.st_mode) or info.st_nlink == 1 or hardlinks and not writable,
                "Hardlinks are unsupported",
            )
            if writable:
                require(
                    bool(info.st_mode & 0o222) and not getattr(info, "st_file_attributes", 0) & 1, "Read-only target", 5
                )
    return path


def read_file(path: Path, limit: int, *, hardlinks: bool = False) -> bytes:
    path = safe_path(path, hardlinks=hardlinks)
    require(path.is_file(), "Expected a file")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    require(len(data) <= limit, "Input size limit exceeded")
    return data


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def json_read(path: Path, limit: int) -> dict:
    def finite_number(text: str) -> float:
        value = float(text)
        require(math.isfinite(value), "Non-finite JSON number")
        return value

    try:
        data = json.loads(
            read_file(path, limit).decode("utf-8-sig"),
            object_pairs_hook=unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(Rejected("Non-finite JSON number")),
            parse_float=finite_number,
        )
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise Rejected("Invalid JSON") from exc
    require(type(data) is dict, "Expected JSON object")
    return data


def keys(value, required, optional=()):
    require(
        type(value) is dict and set(required) <= value.keys() <= set(required) | set(optional),
        "Unknown or missing keys",
    )


def xml_read(data: bytes, tag: str):
    try:
        parser = etree.XMLParser(
            load_dtd=False,
            resolve_entities=False,
            no_network=True,
            huge_tree=False,
            remove_blank_text=False,
            strip_cdata=False,
        )
        root = etree.fromstring(data, parser)
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise Rejected("Invalid XML") from exc
    require(
        not root.getroottree().docinfo.doctype and not root.getroottree().docinfo.internalDTD,
        "DTD/entities are unsupported",
    )
    require(root.tag == tag, "Unknown XML format")
    return root


def identity(node) -> str:
    value = node.get("uuid", "")
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError) as exc:
        raise Rejected("Missing/invalid metadata UUID") from exc


def allocate_uuid(
    root_uuid: str, kind: str, logical_path: str, role: str, occupied: dict[tuple[str, str, str], str]
) -> str:
    """Reserve deterministic identity in the current candidate's UUID inventory."""
    try:
        namespace = uuid.UUID(root_uuid)
        require(namespace.int != 0, "Missing root UUID")
        normalized = {key: str(uuid.UUID(value)) for key, value in occupied.items()}
    except (ValueError, AttributeError, TypeError):
        raise Rejected("Invalid UUID inventory", 4) from None
    key = (kind, logical_path, role)
    require(
        all(isinstance(part, str) and part and all(ord(c) >= 32 for c in part) for part in key), "Invalid identity key"
    )
    require(len(set(normalized.values())) == len(normalized), "Existing UUID collision", 4)
    if key in normalized:
        return normalized[key]
    # JSON tuple framing prevents ambiguous concatenations of paths and roles.
    value = str(uuid.uuid5(namespace, json.dumps(key, ensure_ascii=False, separators=(",", ":"))))
    require(value not in normalized.values(), "Generated UUID collision", 3)
    occupied[key] = value
    return value


def allocate_form_ids(tree, count: int) -> list[int]:
    """Allocate one batch; caller attaches it before allocating the next batch.

    BaseForm may repeat existing IDs, but every occurrence reserves that number.
    No existing node or ID is changed, including attributes and commands.
    """
    require(type(count) is int and 0 < count <= FILE_LIMIT, "Invalid ID count")
    used = []
    for node in tree.iter():
        value = node.get("id")
        if value is not None:
            require(re.fullmatch(r"-?[0-9]{1,10}", value) is not None, "Invalid existing form ID", 4)
            number = int(value)
            require(-1 <= number <= 2147483647, "Existing form ID is out of range", 4)
            used.append(number)
    start = max(used, default=0) + 1
    start = max(start, 1000000 if tree.find("f:BaseForm", NS) is not None else 1)
    require(start + count - 1 <= 2147483647, "Form ID pool exhausted", 3)
    return list(range(start, start + count))


def check_new_element_names(tree, names: list[str]) -> None:
    """Check element and companion names in both working and borrowed trees."""
    roots = [tree, *tree.findall("f:BaseForm", NS)]
    existing = {node.get("name").casefold() for root in roots for node in working_nodes(root) if node.get("name")}
    pending = set()
    for name in names:
        require(isinstance(name, str) and NAME.fullmatch(name), "Invalid element name")
        folded = name.casefold()
        require(folded not in existing and folded not in pending, "Element/companion name conflict", 3)
        pending.add(folded)


def prop(node, name: str) -> str:
    return node.findtext(f"m:Properties/m:{name}", namespaces=NS) or ""


def node_name(node) -> str:
    name = prop(node, "Name")
    require(NAME.fullmatch(name), "Invalid metadata name")
    return name


def metadata(data: bytes, kind: str):
    root = xml_read(data, f"{{{MD}}}MetaDataObject")
    found = root.findall(f"m:{kind}", NS)
    require(len(found) == 1 and len(root) == 1, "Ambiguous metadata object")
    identity(found[0])
    return found[0]


def require_registration(owner, kind: str, name: str) -> None:
    containers = owner.findall("m:ChildObjects", NS)
    require(len(containers) == 1, "Missing or ambiguous ChildObjects", 4)
    matches = [
        node
        for node in containers[0]
        if node.tag == f"{{{MD}}}{kind}" and (node.text or "").casefold() == name.casefold()
    ]
    require(len(matches) == 1 and matches[0].text == name, "Missing or ambiguous registration", 4)


def layout(form: str) -> tuple[str, str, str, str]:
    parts = relative(form).split("/")
    require(parts[-2:] == ["Ext", "Form.xml"], "Expected Designer Form.xml layout")
    if len(parts) == 4 and parts[0] == "CommonForms":
        return f"CommonForms/{parts[1]}.xml", "Configuration.xml", "Configuration.xml", "CommonForm"
    if len(parts) == 6 and parts[0] in OWNER_TYPES and parts[2] == "Forms":
        return "/".join(parts[:4]) + ".xml", "/".join(parts[:2]) + ".xml", "Configuration.xml", OWNER_TYPES[parts[0]]
    if len(parts) == 5 and parts[1] == "Forms":
        return "/".join(parts[:3]) + ".xml", parts[0] + ".xml", parts[0] + ".xml", "external"
    raise Rejected("Unsupported Designer layout")


class Snapshot:
    """Read closure plus ordered candidate writes; never writes the source tree."""

    def __init__(
        self,
        root: Path,
        form: str | None = None,
        base_root: Path | None = None,
        *,
        preimages: dict[str, bytes | None] | None = None,
        directory_preimages: dict[tuple[str, str], dict[str, str] | None] | None = None,
    ):
        self.roots = {"target": safe_path(root)}
        require(self.roots["target"].is_dir(), "Root must be a directory")
        if base_root is not None:
            self.roots["base"] = safe_path(base_root)
            require(self.roots["base"].is_dir(), "Base root must be a directory")
        self.blobs: dict[tuple[str, str], bytes | None] = {}
        self.writes: dict[str, bytes | None] = {}
        # Structural rename owns XML descriptors, not code or embedded artifacts.
        self.pending_dependencies: dict[str, dict] = {}
        self.rename_type_baselines: dict[str, bytes] = {}
        self.enumerations: dict[tuple[str, str], dict[str, str] | None] = {}
        self.preimages = preimages
        self.directory_preimages = directory_preimages or {}
        if form is not None:
            self.load_form(form, base_root)

    def load_form(self, form: str, base_root: Path | None = None, *, inspect_only=False) -> None:
        """Read form context from the current ordered view, including staged XML."""
        base_alias = self.source_root(base_root) if base_root is not None else None
        self.form = relative(form)
        fm, owner_path, config_path, kind = layout(form)
        form_node = metadata(self.get("target", fm), "CommonForm" if kind == "CommonForm" else "Form")
        if kind == "external":
            external = xml_read(self.get("target", config_path), f"{{{MD}}}MetaDataObject")
            require(
                len(external) == 1 and external[0].tag in {f"{{{MD}}}ExternalDataProcessor", f"{{{MD}}}ExternalReport"},
                "Unsupported external metadata",
            )
            owner = external[0]
            identity(owner)
            config = owner
        else:
            config = metadata(self.get("target", config_path), "Configuration")
            owner = config if kind == "CommonForm" else metadata(self.get("target", owner_path), kind)
        parts = form.split("/")
        require(node_name(form_node) == parts[-3], "Form metadata name mismatch")
        child_kind = "CommonForm" if kind == "CommonForm" else "Form"
        require_registration(owner, child_kind, node_name(form_node))
        if owner is not config or kind == "external":
            require(node_name(owner) == parts[1 if kind != "external" else 0], "Owner metadata name mismatch")
        if owner is not config:
            require_registration(config, kind, node_name(owner))
        self.tree = xml_read(self.get("target", form), f"{{{FORM}}}Form")
        # verify and inspect report an unknown format version as a structure failure (E10).
        require(
            self.tree.get("version") in {"2.17", "2.20"}, "Unsupported managed form version", 4 if inspect_only else 2
        )
        self.owner = owner
        self.module = form.removesuffix(".xml") + "/Module.bsl"
        if not inspect_only:
            self.get("target", self.module, optional=True)
        extension = bool(prop(config, "ConfigurationExtensionPurpose"))
        belonging = prop(form_node, "ObjectBelonging")
        require(belonging in {"", "Native", "Adopted"}, "Unknown ObjectBelonging")
        adopted = belonging == "Adopted"
        require(adopted or not prop(form_node, "ExtendedConfigurationObject"), "Unexpected base form reference")
        base_forms = self.tree.findall("f:BaseForm", NS)
        require(len(base_forms) <= 1, "Ambiguous BaseForm")
        require(not adopted or extension, "Adopted form outside CFE")
        self.kind = "borrowed-cfe" if adopted else "own-cfe" if extension else "standalone"
        require(bool(base_forms) == adopted, "BaseForm classification mismatch")
        require(
            (base_root is not None) == adopted or (inspect_only and base_root is None),
            "base-root required only for borrowed CFE",
        )
        self.uuids = {"configuration": identity(config), "owner": identity(owner), "form": identity(form_node)}
        if adopted and base_root is not None:
            assert base_alias is not None
            base_config = metadata(self.get(base_alias, config_path), "Configuration")
            require(not prop(base_config, "ConfigurationExtensionPurpose"), "Base root must be a main configuration")
            base_owner = base_config if kind == "CommonForm" else metadata(self.get(base_alias, owner_path), kind)
            base_form = metadata(self.get(base_alias, fm), child_kind)
            require(
                prop(form_node, "ExtendedConfigurationObject").lower() == identity(base_form), "Base form UUID mismatch"
            )
            if owner is not config:
                require(
                    prop(owner, "ObjectBelonging") == "Adopted"
                    and prop(owner, "ExtendedConfigurationObject").lower() == identity(base_owner),
                    "Base owner UUID mismatch",
                )
                require_registration(base_config, kind, node_name(base_owner))
            require_registration(base_owner, child_kind, node_name(base_form))
            require(
                node_name(base_form) == node_name(form_node) and node_name(base_owner) == node_name(owner)
                if owner is not config
                else node_name(base_form) == node_name(form_node),
                "Base metadata name mismatch",
            )
            xml_read(self.get(base_alias, form), f"{{{FORM}}}Form")
            if not inspect_only:
                self.get(base_alias, self.module, optional=True)
            self.uuids["baseForm"] = identity(base_form)
        self.attributes = {}
        for attribute in self.tree.findall("f:Attributes/f:Attribute", NS):
            name = attribute.get("name", "")
            require(
                NAME.fullmatch(name) and name.casefold() not in {key.casefold() for key in self.attributes},
                "Duplicate/unnamed form attribute",
            )
            types = attribute.findall("f:Type/v8:Type", NS)
            scalar = None
            if len(types) == 1 and types[0].text and not attribute.findall("f:Type/v8:TypeSet", NS):
                value = types[0].text.strip().split(":")
                prefix, local = value if len(value) == 2 else (None, value[0])
                if types[0].nsmap.get(prefix) == XS and local in {"string", "decimal", "boolean", "dateTime"}:
                    scalar = local
            self.attributes[name] = scalar

    def source_root(self, root: Path) -> str:
        """Name a declared source once, in request order; no recursive discovery."""
        root = safe_path(root)
        require(root.is_dir(), "Source root must be a directory")
        for alias, existing in self.roots.items():
            if os.path.normcase(str(root)) == os.path.normcase(str(existing)):
                return alias
        alias = f"source-{len(self.roots)}"
        self.roots[alias] = root
        return alias

    def _path(self, alias: str, path: str) -> Path:
        require(alias in self.roots, "Unknown source root")
        relative(path)
        # The same snapshot must not use two spellings for one Windows path.
        require(
            not any(a == alias and p != path and p.casefold() == path.casefold() for a, p in self.blobs),
            "Case-ambiguous source path",
            3,
        )
        return self.roots[alias] / path

    def _absent(self, full: Path) -> None:
        # Missing parents are allowed for new forms/objects. Validate the nearest
        # existing ancestor, including junctions, before accepting absence.
        existing = full.parent
        while not existing.exists() and not existing.is_symlink():
            existing = existing.parent
        require(safe_path(existing).is_dir(), "File blocks a parent directory", 3)

    def _limit(self) -> None:
        size = sum(len(blob or b"") for blob in self.blobs.values())
        size += sum(len(blob or b"") for blob in self.writes.values())
        size += sum(
            len(json.dumps(entries, ensure_ascii=False).encode("utf-8")) for entries in self.enumerations.values()
        )
        require(size <= CLOSURE_LIMIT, "Closure size limit exceeded")

    def read(self, alias: str, path: str, *, optional=False) -> bytes | None:
        full = self._path(alias, path)
        key = alias, relative(path)
        if key not in self.blobs:
            if alias == "target" and self.preimages is not None and path in self.preimages:
                if full.exists() or full.is_symlink():
                    require(safe_path(full).is_file(), "Expected a source file")
                else:
                    self._absent(full)
                self.blobs[key] = self.preimages[path]
            elif not full.exists() and not full.is_symlink():
                self._absent(full)
                self.blobs[key] = None
            else:
                self.blobs[key] = read_file(full, FILE_LIMIT, hardlinks=alias != "target")
            self._limit()
        value = self.writes[path] if alias == "target" and path in self.writes else self.blobs[key]
        require(optional or value is not None, "Required source file is absent")
        return value

    def get(self, alias: str, path: str, optional=False) -> bytes:
        # Preserve the old form reader's optional-module convention.
        return self.read(alias, path, optional=optional) or b""

    def stage(self, path: str, value: bytes | None) -> None:
        require(value is None or isinstance(value, bytes), "Candidate must be bytes or absent")
        require(value is None or len(value) <= FILE_LIMIT, "Candidate size limit exceeded")
        self.read("target", path, optional=True)
        parts = path.split("/")
        require(
            not any(self.writes.get("/".join(parts[:i])) is not None for i in range(1, len(parts))),
            "Candidate file blocks a directory",
            3,
        )
        require(
            value is None or not any(p.startswith(path + "/") and b is not None for p, b in self.writes.items()),
            "Candidate directory blocks a file",
            3,
        )
        if value == self.blobs["target", path]:
            self.writes.pop(path, None)
        else:
            self.writes[path] = value
        self._limit()

    def _directory(self, alias: str, path: str) -> dict[str, str] | None:
        full = self.roots[alias] if not path else self._path(alias, path)
        if not full.exists() and not full.is_symlink():
            self._absent(full)
            return None
        require(safe_path(full).is_dir(), "Expected a source directory")
        entries = {}
        size = 0
        with os.scandir(full) as items:
            for item in items:
                relative(item.name)
                checked = safe_path(Path(item.path), hardlinks=alias != "target")
                size += len(item.name.encode("utf-8")) + 16
                require(size <= CLOSURE_LIMIT, "Directory listing size limit exceeded")
                entries[item.name] = "directory" if checked.is_dir() else "file"
        require(len({name.casefold() for name in entries}) == len(entries), "Case-ambiguous directory", 3)
        return dict(sorted(entries.items()))

    def list_directory(self, alias: str, path: str = "", *, optional=False) -> dict[str, str] | None:
        require(alias in self.roots, "Unknown source root")
        if path:
            relative(path)
        key = alias, path
        if key not in self.enumerations:
            self.enumerations[key] = (
                copy.deepcopy(self.directory_preimages[key])
                if key in self.directory_preimages
                else self._directory(alias, path)
            )
            self._limit()
        initial = self.enumerations[key]
        result = dict(initial or {})
        virtual = False
        if alias == "target":
            require(path not in self.writes or self.writes[path] is None, "Candidate file blocks a directory", 3)
            prefix = path + "/" if path else ""
            for written, value in self.writes.items():
                if not written.startswith(prefix):
                    continue
                tail = written[len(prefix) :]
                name, slash, _ = tail.partition("/")
                if value is not None:
                    virtual = True
                    result[name] = "directory" if slash else "file"
                elif not slash:
                    result.pop(name, None)
        require(len({name.casefold() for name in result}) == len(result), "Case-ambiguous candidate directory", 3)
        require(optional or initial is not None or virtual, "Required source directory is absent")
        return dict(sorted(result.items())) if initial is not None or virtual else None

    def manifest(self) -> list[dict]:
        return [
            {"root": a, "path": p, "present": b is not None, "sha256": digest(b) if b is not None else None}
            for (a, p), b in sorted(self.blobs.items())
        ]

    def package_manifest(self) -> tuple[PackageManifest, bytes] | None:
        """Read a registered package fragment when no Configuration.xml exists."""
        if self.read("target", "Configuration.xml", optional=True) is not None:
            return None
        data = self.read("target", "manifest.json", optional=True)
        if data is None:
            return None
        try:
            value = json.loads(data.decode("utf-8-sig"), object_pairs_hook=unique_pairs)
        except (ValueError, UnicodeError, RecursionError):
            raise Rejected("Invalid package manifest") from None
        if type(value) is not dict:
            raise Rejected("Unsupported package manifest")
        manifest_values = cast(dict[str, object], value)
        raw_entries = manifest_values.get("entries")
        require(
            manifest_values.get("schemaVersion") == 1
            and isinstance(manifest_values.get("packageId"), str)
            and manifest_values.get("packageId")
            and type(raw_entries) is list,
            "Unsupported package manifest",
        )
        from . import metadata_borrow as borrow

        seen = set()
        for raw_entry in cast(list[object], raw_entries):
            if type(raw_entry) is not dict:
                raise Rejected("Unsupported package manifest entry")
            entry_values = cast(dict[str, object], raw_entry)
            kind = entry_values.get("kind")
            name = entry_values.get("name")
            root = entry_values.get("root")
            operation = entry_values.get("operation")
            if not (
                isinstance(kind, str)
                and isinstance(name, str)
                and NAME.fullmatch(name)
                and kind in borrow.DIRECTORIES
                and isinstance(root, str)
                and root == borrow.DIRECTORIES[kind] + "/" + name
                and operation == "add-or-update"
            ):
                raise Rejected("Unsupported package manifest entry")
            key = kind, name.casefold()
            require(key not in seen, "Duplicate package manifest registration", 4)
            seen.add(key)
        return cast(PackageManifest, value), data

    def package_entry(self, kind: str, name: str) -> PackageManifestEntry | None:
        manifest = self.package_manifest()
        if manifest is None:
            return None
        entries = [
            entry
            for entry in manifest[0]["entries"]
            if entry["kind"] == kind and entry["name"].casefold() == name.casefold()
        ]
        require(
            len(entries) <= 1 and (not entries or entries[0]["name"] == name),
            "Ambiguous package manifest registration",
            4,
        )
        return entries[0] if entries else None

    def rename_package_entry(self, kind: str, old_name: str, new_name: str) -> None:
        manifest_data = self.package_manifest()
        if manifest_data is None:
            raise Rejected("Package manifest required")
        manifest, original = manifest_data
        entries = [
            item
            for item in manifest["entries"]
            if item["kind"] == kind and item["name"].casefold() == old_name.casefold()
        ]
        require(len(entries) == 1 and entries[0]["name"] == old_name, "Object registration missing", 4)
        require(
            not any(
                item["kind"] == kind and item["name"].casefold() == new_name.casefold() for item in manifest["entries"]
            ),
            "Rename destination is registered",
            3,
        )
        entry = entries[0]
        entry["name"] = new_name
        from . import metadata_borrow as borrow

        entry["root"] = borrow.DIRECTORIES[kind] + "/" + new_name
        text = json.dumps(manifest, ensure_ascii=False, indent=2) + ("\n" if original.endswith(b"\n") else "")
        self.stage("manifest.json", text.encode("utf-8"))

    def unchanged(self):
        for (alias, path), blob in self.blobs.items():
            full = self.roots[alias] / path
            if blob is None:
                require(not full.exists() and not full.is_symlink(), "Source changed", 3)
                self._absent(full)
            else:
                require(read_file(full, FILE_LIMIT, hardlinks=alias != "target") == blob, "Source changed", 3)
        for (alias, path), entries in self.enumerations.items():
            require(self._directory(alias, path) == entries, "Source directory changed", 3)


def working_nodes(tree):
    for tag in ("ChildItems", "AutoCommandBar"):
        for section in tree.findall(f"f:{tag}", NS):
            # Event names identify handlers' slots, not form elements; many fields
            # legitimately declare the same OnChange/StartChoice event.
            yield from (node for node in section.iter() if node.tag != f"{{{FORM}}}Event")


def _addressable(tree):
    for node in working_nodes(tree):
        # Extended tooltips are service children, not globally addressable form elements.
        # Keep them in working_nodes so their IDs remain reserved by the allocator.
        if (
            not isinstance(node.tag, str)
            or not node.tag.startswith(f"{{{FORM}}}")
            or node.tag == f"{{{FORM}}}ExtendedTooltip"
        ):
            continue
        if node.get("name"):
            yield node


def named(tree) -> dict:
    result = {}
    for node in _addressable(tree):
        name = node.get("name")
        require(name.casefold() not in result, "Duplicate existing element name", 4)
        result[name.casefold()] = node
    return result


def duplicate_names(tree) -> set:
    """Casefolded element names that occur more than once; form.rename-element repairs them one by one."""
    seen, result = set(), set()
    for node in _addressable(tree):
        name = node.get("name").casefold()
        (result if name in seen else seen).add(name)
    return result


def placement(snapshot: Snapshot, operation: dict, *, applied=False):
    scalar = snapshot.attributes.get(operation["attribute"])
    if scalar is None:
        raise Rejected("Attribute must be a declared scalar form attribute")
    nodes = named(snapshot.tree)
    parent_name = operation["parent"]
    parent = snapshot.tree if parent_name == "$root" else nodes.get(parent_name.casefold())
    require(
        parent is not None
        and (parent is snapshot.tree or parent.tag == f"{{{FORM}}}UsualGroup" and parent.get("name") == parent_name),
        "Unknown/unsupported parent",
    )
    assert parent is not None
    containers = parent.findall("f:ChildItems", NS)
    require(len(containers) <= 1, "Ambiguous ChildItems", 4)
    container = containers[0] if containers else None
    if "after" in operation:
        anchor = nodes.get(operation["after"].casefold())
        require(
            anchor is not None and anchor.get("name") == operation["after"] and anchor.getparent() is container,
            "Anchor is not a direct child",
        )
    if not applied:
        for name in [operation["name"], *(operation["name"] + suffix for suffix in COMPANIONS.values())]:
            require(name.casefold() not in nodes, "Element/companion name conflict", 3)
    return scalar, container


def signature(node):
    def content(text, has_elements):
        return None if has_elements and text is not None and not text.strip() else text

    children = list(node)
    return (
        str(node.tag),
        tuple(sorted(node.attrib.items())),
        tuple(sorted((k or "", v) for k, v in node.nsmap.items())),
        content(node.text, bool(children)),
        tuple((signature(child), content(child.tail, True)) for child in children),
    )


def element_check(snapshot: Snapshot, operation: dict, *, check_position=True):
    scalar, container = placement(snapshot, operation, applied=True)
    require(container is not None, "Missing added field", 4)
    assert container is not None
    fields = [n for n in container if n.get("name") == operation["name"]]
    expected = "CheckBoxField" if scalar == "boolean" else "InputField"
    require(len(fields) == 1 and fields[0].tag == f"{{{FORM}}}{expected}", "Wrong added field", 4)
    field = fields[0]
    require(field.findtext("f:DataPath", namespaces=NS) == operation["attribute"], "Wrong DataPath", 4)
    titles = field.findall("f:Title/v8:item", NS)
    require(
        len(titles) == 1
        and titles[0].findtext("v8:lang", namespaces=NS) == "ru"
        and titles[0].findtext("v8:content", namespaces=NS) == operation["title"],
        "Wrong title",
        4,
    )
    allowed = {f"{{{FORM}}}{t}" for t in ("DataPath", "Title", *COMPANIONS)}
    require(all(n.tag in allowed for n in field) and len(field) == 4, "Unexpected added field properties", 4)
    require(set(field.attrib) == {"name", "id"}, "Unexpected field attributes", 4)
    for kind, suffix in COMPANIONS.items():
        companions = field.findall(f"f:{kind}", NS)
        require(
            len(companions) == 1
            and companions[0].get("name") == operation["name"] + suffix
            and set(companions[0].attrib) == {"name", "id"}
            and not len(companions[0]),
            "Wrong companion",
            4,
        )
    all_ids = [n.get("id") for n in working_nodes(snapshot.tree) if n.get("id") is not None]
    require(len(set(all_ids)) == len(all_ids), "Element ID collision", 4)
    ids = [n.get("id", "") for n in field.iter() if n.get("id") is not None]
    require(len(ids) == 3 and all(re.fullmatch(r"[0-9]+", i) for i in ids), "Invalid added IDs", 4)
    if snapshot.kind == "borrowed-cfe":
        base_ids = {n.get("id") for n in snapshot.tree.find("f:BaseForm", NS).iter() if n.get("id") is not None}
        require(all(int(i) >= 1000000 and i not in base_ids for i in ids), "Borrowed ID collision", 4)
    index = list(container).index(field)
    require(
        not check_position
        or index
        == (
            next(i for i, n in enumerate(container) if n.get("name") == operation["after"]) + 1
            if "after" in operation
            else len(container) - 1
        ),
        "Wrong field position",
        4,
    )
    return field


def engine_fingerprint() -> str:
    h = hashlib.sha256()
    for relative_path in sorted(ENGINE_FILES):
        # uv.lock appears only after the project adopts uv; its absence is a stable fingerprint input.
        if relative_path in OPTIONAL_ENGINE_FILES and not (PROJECT_ROOT / relative_path).exists():
            data = b"<absent>"
        else:
            data = read_file(PROJECT_ROOT / relative_path, FILE_LIMIT)
        # Length framing prevents concatenation ambiguities.
        for part in (relative_path.encode("utf-8"), data):
            h.update(len(part).to_bytes(8, "big"))
            h.update(part)
    return h.hexdigest()


def serialize_like(tree, original: bytes, *, preserve_mixed_eol=False) -> bytes:
    text = original.decode("utf-8-sig")
    lf = text.count("\n")
    crlf = text.count("\r\n")
    mixed = bool(crlf and crlf != lf)
    require((not mixed or preserve_mixed_eol) and text.count("\r") == crlf, "Mixed EOL unsupported")
    # XML parsers normalize physical line endings, while lxml serializes value CR
    # as &#13;. Verify the parsed tree below so line-ending conversion cannot
    # silently alter text values (including whitespace-only leaves and CDATA).
    body = etree.tostring(tree, encoding="unicode")
    eol = "\r\n" if crlf else "\n"
    if crlf:
        body = body.replace("\n", "\r\n")
    # Keep the file's own spelling of the UTF-8 declaration (Designer writes
    # utf-8 in forms): only touched nodes may differ from the original.
    kept = re.match(r'<\?xml version="1\.0" encoding="(?:UTF|utf)-8"\?>', text)
    declaration = kept.group(0) if kept else '<?xml version="1.0" encoding="UTF-8"?>'
    result = (declaration + eol + body + (eol if text.endswith("\n") else "")).encode("utf-8")
    if mixed:
        # Rename changes names, not layout. Preserve each physical line ending;
        # reject structural serialization changes instead of guessing an EOL.
        old_lines = text.splitlines(keepends=True)
        new_lines = result.decode("utf-8").splitlines(keepends=True)
        require(len(old_lines) == len(new_lines), "Mixed EOL layout changed")
        result = "".join(
            new.rstrip("\r\n") + old[len(old.rstrip("\r\n")) :] for old, new in zip(old_lines, new_lines, strict=False)
        ).encode("utf-8")
    require(signature(xml_read(result, tree.tag)) == signature(tree), "Serialization changed content", 4)
    return (codecs.BOM_UTF8 if original.startswith(codecs.BOM_UTF8) else b"") + result


def diff_text(before: bytes, after: bytes, form: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.decode("utf-8-sig").splitlines(keepends=True),
            after.decode("utf-8-sig").splitlines(keepends=True),
            fromfile=form,
            tofile=form,
        )
    )


def _type_context(node):
    """Return a stable structural key for a typed node in one XML descriptor."""

    def marker(item):
        name = item.get("name")
        if name is None:
            names = item.findall("m:Properties/m:Name", NS)
            if len(names) == 1:
                name = names[0].text
        return name, item.get("uuid"), item.get("id")

    result = []
    current = node
    while current is not None:
        parent = current.getparent()
        value = marker(current)
        siblings = (
            [item for item in parent if item.tag == current.tag and marker(item) == value]
            if parent is not None
            else [current]
        )
        result.append((current.tag, value, next(index for index, item in enumerate(siblings) if item is current)))
        current = parent
    return tuple(reversed(result))


def check_type_dependencies(snapshot: Snapshot, *, rename_only=False) -> None:
    """Check direct named types in changed CF/CFE XML against the final snapshot.

    This is not a BSL/transitive dependency scan. External artifacts have no
    configuration tree of their own and retain their existing qualification path.
    """
    from . import metadata_borrow as borrow
    from . import metadata_object_schema as object_schema

    config_data = snapshot.read("target", "Configuration.xml", optional=True)
    if config_data is None:
        return
    registrations = borrow._registrations(metadata(config_data, "Configuration"))
    owners = {prefix: kind for kind, generated in borrow.GENERATED_TYPES.items() for prefix, _ in generated}
    builtin_namespaces = {
        XS,
        V8,
        "http://v8.1c.ru/8.1/data/ui",
        "http://v8.1c.ru/8.2/managed-application/core",
        "http://v8.1c.ru/8.2/managed-application/logform",
        "http://v8.1c.ru/8.2/data/spreadsheet",
        "http://v8.1c.ru/8.1/data-composition-system/core",
        "http://v8.1c.ru/8.1/data-composition-system/schema",
        "http://v8.1c.ru/8.1/data-composition-system/settings",
    }
    checked = set()
    for path, data in sorted(snapshot.writes.items()):
        if data is None or not path.endswith(".xml"):
            continue
        if path in snapshot.pending_dependencies:
            continue
        if path == "ConfigDumpInfo.xml":
            from . import metadata_object_ops

            metadata_object_ops.read_config_dump_info(data, path)
            continue
        form_body = path.endswith("/Ext/Form.xml")
        if "/Ext/" in path and not form_body:
            continue
        tree = xml_read(data, f"{{{FORM}}}Form" if form_body else f"{{{MD}}}MetaDataObject")
        # A rename baseline keeps structural paths of the pre-rename object;
        # other changed descriptors are compared by stable structural context.
        baseline = snapshot.rename_type_baselines.get(path)
        by_path = rename_only or baseline is not None
        if baseline is None:
            baseline = snapshot.blobs.get(("target", path))
        old_tree = xml_read(baseline, tree.tag) if baseline is not None else None
        old_types = {}
        if old_tree is not None and not by_path:
            for previous in old_tree.iter(f"{{{V8}}}Type", f"{{{V8}}}TypeSet"):
                old_types.setdefault(_type_context(previous), []).append(previous)
        for typed in tree.iter(f"{{{V8}}}Type", f"{{{V8}}}TypeSet"):
            if old_tree is not None:
                previous = (
                    old_types.get(_type_context(typed), [])
                    if not by_path
                    else old_tree.xpath(
                        tree.getroottree().getpath(typed),
                        namespaces={key: value for key, value in typed.nsmap.items() if key},
                    )
                )
                if (
                    len(previous) == 1
                    and signature(previous[0]) == signature(typed)
                    and previous[0].nsmap == typed.nsmap
                ):
                    continue
            prefix, separator, local = (typed.text or "").partition(":")
            namespace = typed.nsmap.get(prefix) if separator else None
            require(separator and local and namespace, "Invalid type QName")
            if namespace != borrow.CFG:
                require(
                    namespace in builtin_namespaces and NAME.fullmatch(local) and typed.tag == f"{{{V8}}}Type",
                    "Unsupported type namespace or representation",
                )
                continue
            if local == "DynamicList" and tree.tag == f"{{{FORM}}}Form" and typed.tag == f"{{{V8}}}Type":
                continue
            family, dot, name = local.partition(".")
            if not dot:
                # A bare generated type (e.g. DocumentManager in a subscription
                # source) means every object of the family, not a named dependency.
                bare_type_set = local == "DocumentRef" and typed.tag == f"{{{V8}}}TypeSet" and not len(typed)
                require(
                    (local in object_schema.BARE_TYPE_NAMES or local in owners)
                    and (typed.tag == f"{{{V8}}}Type" or bare_type_set),
                    "Unsupported metadata type or representation",
                )
                continue
            require(dot and family in owners and NAME.fullmatch(name), "Unsupported metadata type")
            require(
                (typed.tag == f"{{{V8}}}TypeSet") == (family in {"DefinedType", "Characteristic"}),
                "Invalid metadata type set representation",
            )
            kind = owners[family]
            if (kind, name) in checked:
                continue
            descriptor = f"{borrow.DIRECTORIES[kind]}/{name}.xml"
            dependency = snapshot.read("target", descriptor, optional=True)
            if not borrow._linked(registrations, kind, name) or dependency is None:
                members = []
                for ancestor in reversed(list(typed.iterancestors())):
                    member = ancestor.get("name") or ancestor.findtext("m:Properties/m:Name", namespaces=NS)
                    if member and NAME.fullmatch(member):
                        members.append(member)
                raise TypeDependencyRejected(members[-8:] or ["Type"], kind, name)
            node, _ = borrow._checked(snapshot, "target", descriptor, kind)
            require(node_name(node) == name, "Dependency metadata name mismatch", 3)
            identity(node)
            checked.add((kind, name))


def plan_make(snapshot: Snapshot, request: dict) -> dict:
    from jsonschema import Draft202012Validator, ValidationError

    try:
        Draft202012Validator(metadata_ops.REQUEST_ENVELOPE_SCHEMA).validate(request)
    except ValidationError:
        raise Rejected("Invalid request structure") from None
    normalized = {"schemaVersion": 1, "operations": []}
    operation_reports = []
    for index, raw in enumerate(request["operations"], 1):
        print(f"metadata: plan operation {index}/{len(request['operations'])}", file=sys.stderr, flush=True)
        require(raw["op"] in metadata_ops.HANDLERS, "Operation is not connected")
        try:
            steps = metadata_ops.normalize_operation(raw, properties=metadata_ops.operation_context(snapshot, raw))
        except ValueError:
            raise Rejected("Invalid operation parameters") from None
        for step in steps:
            report = metadata_ops.HANDLERS[step["op"]](snapshot, step)
            normalized["operations"].append(step)
            if step["op"].startswith("template."):
                operation_reports.append(
                    {
                        "index": len(normalized["operations"]),
                        "op": step["op"],
                        "target": step["target"],
                        "report": report,
                    }
                )
    print("metadata: plan dependency preconditions", file=sys.stderr, flush=True)
    check_type_dependencies(
        snapshot, rename_only=all(step["op"] == "object.rename" for step in normalized["operations"])
    )
    # Record original parent existence even when a handler only reads files.
    # Recovery must never infer directory ownership from the mutable journal.
    for path in snapshot.writes:
        parent = Path(path).parent
        while parent != Path("."):
            snapshot.list_directory("target", parent.as_posix(), optional=True)
            parent = parent.parent
    writes = [
        {"path": path, "before": byte_state(snapshot.blobs["target", path]), "after": byte_state(value)}
        for path, value in sorted(snapshot.writes.items())
    ]
    result = {
        "schemaVersion": 1,
        "editorVersion": 2,
        "request": normalized,
        "roots": {alias: str(root) for alias, root in snapshot.roots.items()},
        "engineFingerprint": engine_fingerprint(),
        "manifest": snapshot.manifest(),
        "directories": [
            {"root": alias, "path": path, "entries": entries}
            for (alias, path), entries in sorted(snapshot.enumerations.items())
        ],
        "writes": writes,
        "diff": "".join(
            file_diff(snapshot.blobs["target", path], data, path) for path, data in sorted(snapshot.writes.items())
        ),
        "checks": {"structure": "passed", "platform": "not-run", "runtime": "not-run"},
    }
    if operation_reports:
        result["operationReports"] = operation_reports
    if snapshot.pending_dependencies:
        result["pendingDependencies"] = [
            {
                "path": path,
                "sha256": digest(snapshot.get("target", path)),
                "reason": item["reason"],
                "targets": sorted(item["targets"]),
            }
            for path, item in sorted(snapshot.pending_dependencies.items())
        ]
        result["checks"]["dependencies"] = "pending"
        result["checks"]["structure"] = "supported-descriptors-only"
    require(len(json.dumps(result, ensure_ascii=False).encode("utf-8")) <= PLAN_LIMIT, "Plan size limit exceeded")
    print("metadata: plan snapshot preconditions", file=sys.stderr, flush=True)
    if snapshot.preimages is None:
        snapshot.unchanged()
    return result


def byte_state(data: bytes | None) -> dict:
    return {
        "present": data is not None,
        "sha256": digest(data) if data is not None else None,
        "data": base64.b64encode(data).decode("ascii") if data is not None else None,
    }


def file_diff(before: bytes | None, after: bytes | None, path: str) -> str:
    """Show presence and BOM changes which text-only diffs can conceal."""

    def description(data):
        return "absent" if data is None else f"{len(data)} bytes, SHA-256 {digest(data)}"

    heading = f"# {path}: {description(before)} -> {description(after)}\n"
    old, new = before or b"", after or b""
    if old.startswith(codecs.BOM_UTF8) != new.startswith(codecs.BOM_UTF8):
        heading += f"# UTF-8 BOM: {old.startswith(codecs.BOM_UTF8)} -> {new.startswith(codecs.BOM_UTF8)}\n"
    return heading + diff_text(old, new, path)


def state_bytes(state: dict) -> bytes | None:
    keys(state, ("present", "sha256", "data"))
    require(type(state["present"]) is bool, "Invalid file presence")
    if not state["present"]:
        require(state["sha256"] is None and state["data"] is None, "Invalid absent file state")
        return None
    require(isinstance(state["sha256"], str) and HASH.fullmatch(state["sha256"]), "Invalid state hash")
    require(
        isinstance(state["data"], str) and len(state["data"]) <= (FILE_LIMIT + 2) // 3 * 4, "Invalid encoded snapshot"
    )
    try:
        data = base64.b64decode(state["data"], validate=True)
    except ValueError:
        raise Rejected("Invalid encoded snapshot") from None
    require(
        len(data) <= FILE_LIMIT
        and digest(data) == state["sha256"]
        and base64.b64encode(data).decode("ascii") == state["data"],
        "Snapshot hash/encoding mismatch",
    )
    return data


def check_metadata_plan(plan: dict) -> None:
    from jsonschema import Draft202012Validator, ValidationError

    keys(
        plan,
        (
            "schemaVersion",
            "editorVersion",
            "request",
            "roots",
            "engineFingerprint",
            "manifest",
            "directories",
            "writes",
            "diff",
            "checks",
        ),
        ("pendingDependencies", "operationReports"),
    )
    require(
        type(plan["schemaVersion"]) is int
        and plan["schemaVersion"] == 1
        and type(plan["editorVersion"]) is int
        and plan["editorVersion"] == 2,
        "Unknown plan version",
    )
    try:
        Draft202012Validator(metadata_ops.REQUEST_ENVELOPE_SCHEMA).validate(plan["request"])
    except ValidationError:
        raise Rejected("Invalid planned request") from None
    require(isinstance(plan["roots"], dict) and "target" in plan["roots"], "Missing planned roots")
    for alias, root in plan["roots"].items():
        require(isinstance(alias, str) and re.fullmatch(r"target|base|source-[0-9]+", alias), "Invalid root alias")
        require(isinstance(root, str) and Path(root).is_absolute(), "Invalid root path")
    require(
        isinstance(plan["engineFingerprint"], str) and HASH.fullmatch(plan["engineFingerprint"]),
        "Invalid engine fingerprint",
    )
    expected_checks = {"structure": "passed", "platform": "not-run", "runtime": "not-run"}
    if "operationReports" in plan:
        reports = plan["operationReports"]
        require(isinstance(reports, list) and bool(reports), "Invalid operation reports")
        for item in reports:
            keys(item, ("index", "op", "target", "report"))
            require(
                type(item["index"]) is int
                and isinstance(item["op"], str)
                and item["op"].startswith("template.")
                and isinstance(item["target"], str)
                and isinstance(item["report"], dict),
                "Invalid operation report",
            )
    if "pendingDependencies" in plan:
        pending = plan["pendingDependencies"]
        require(isinstance(pending, list) and bool(pending), "Invalid pending dependencies")
        paths = set()
        for item in pending:
            keys(item, ("path", "sha256", "reason", "targets"))
            path = relative(item["path"])
            require(path not in paths, "Duplicate pending dependency")
            paths.add(path)
            require(isinstance(item["sha256"], str) and HASH.fullmatch(item["sha256"]), "Invalid dependency hash")
            require(
                isinstance(item["reason"], str) and item["reason"] in {"bsl-review", "embedded-artifact-review"},
                "Invalid dependency reason",
            )
            require(
                isinstance(item["targets"], list)
                and bool(item["targets"])
                and all(isinstance(value, str) for value in item["targets"]),
                "Invalid dependency targets",
            )
        expected_checks.update(structure="supported-descriptors-only", dependencies="pending")
    require(plan["checks"] == expected_checks, "Invalid planned checks")
    require(isinstance(plan["diff"], str), "Invalid diff")
    for field in ("manifest", "directories", "writes"):
        require(isinstance(plan[field], list), "Invalid plan section")
    seen = set()
    for item in plan["manifest"]:
        keys(item, ("root", "path", "present", "sha256"))
        require(isinstance(item["root"], str) and item["root"] in plan["roots"], "Unknown manifest root")
        relative(item["path"])
        key = item["root"], item["path"]
        require(key not in seen and type(item["present"]) is bool, "Invalid/duplicate manifest entry")
        seen.add(key)
        require(
            isinstance(item["sha256"], str) and HASH.fullmatch(item["sha256"])
            if item["present"]
            else item["sha256"] is None,
            "Invalid manifest hash",
        )
    seen_directories = set()
    for item in plan["directories"]:
        keys(item, ("root", "path", "entries"))
        require(isinstance(item["root"], str) and item["root"] in plan["roots"], "Unknown directory root")
        require(isinstance(item["path"], str), "Invalid directory path")
        if item["path"]:
            relative(item["path"])
        key = item["root"], item["path"]
        require(key not in seen_directories, "Duplicate directory entry")
        seen_directories.add(key)
        entries = item["entries"]
        require(entries is None or isinstance(entries, dict), "Invalid directory entries")
        for name, kind in (entries or {}).items():
            relative(name)
            require("/" not in name and kind in ("file", "directory"), "Invalid directory member")
    seen_writes = set()
    for item in plan["writes"]:
        keys(item, ("path", "before", "after"))
        path = relative(item["path"])
        require(path not in seen_writes and ("target", path) in seen, "Unobserved/duplicate write")
        seen_writes.add(path)
        require(state_bytes(item["before"]) != state_bytes(item["after"]), "No-op write in plan")
    require(len(json.dumps(plan, ensure_ascii=False).encode("utf-8")) <= PLAN_LIMIT, "Plan size limit exceeded")


def replay_plan(root: Path, plan: dict) -> Snapshot:
    """Recompute candidates; preimages do not prove historical origin."""
    print("metadata: replay plan", file=sys.stderr, flush=True)
    check_metadata_plan(plan)
    require(engine_fingerprint() == plan["engineFingerprint"], "Engine fingerprint changed", 3)
    require(str(safe_path(root)) == plan["roots"]["target"], "Plan root mismatch", 3)
    preimages = {entry["path"]: state_bytes(entry["before"]) for entry in plan["writes"]}
    directories = {
        (entry["root"], entry["path"]): entry["entries"] for entry in plan["directories"] if entry["root"] == "target"
    }
    snapshot = Snapshot(root, preimages=preimages, directory_preimages=directories)
    regenerated = plan_make(snapshot, plan["request"])
    require(regenerated == plan, "Plan replay mismatch", 3)
    return snapshot


def verify_plan(root: Path, plan: dict) -> tuple[str, Snapshot]:
    """Compare actual before/after state after independent candidate replay."""
    snapshot = replay_plan(root, plan)
    print("metadata: compare source state", file=sys.stderr, flush=True)
    before = after = True
    actual = Snapshot(root)
    actual.roots = dict(snapshot.roots)
    for (alias, path), expected in snapshot.blobs.items():
        current = actual.read(alias, path, optional=True)
        if alias == "target" and path in snapshot.writes:
            before &= current == expected
            after &= current == snapshot.writes[path]
        else:
            require(current == expected, "Read-only source changed", 3)
    for (alias, path), expected in snapshot.enumerations.items():
        current = actual.list_directory(alias, path, optional=True)
        if alias == "target":
            before &= current == expected
            after &= current == snapshot.list_directory(alias, path, optional=True)
        else:
            require(current == expected, "Read-only directory changed", 3)
    require(before or after, "Mixed or foreign source state", 3)
    actual.unchanged()
    return ("after" if after else "before"), snapshot


@contextmanager
def file_lock(target: Path):
    target = safe_path(target)
    require(target.is_dir() and target.parent != target, "Invalid publication root")
    directory = safe_path(target.with_name("." + target.name + ".metadata-state"), missing=True)
    directory.mkdir(exist_ok=True)
    require(safe_path(directory).is_dir(), "Invalid state directory")
    sidecar = safe_path(directory / "lock", missing=True)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(sidecar, flags, 0o600)
    try:
        require(os.fstat(fd).st_nlink == 1, "Hardlinked lock")
        if os.name == "nt":
            import msvcrt

            if os.fstat(fd).st_size == 0:
                os.write(fd, b"\0")
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise Rejected("Lock conflict", 3) from exc
        else:
            import fcntl

            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Rejected("Lock conflict", 3) from exc
        yield
    finally:
        os.close(fd)


def apply(root: Path, base_root: Path | None, plan: dict) -> str:
    require(base_root is None, "Sources are declared by metadata request")
    return publish_plan(root, plan)


def _temporary(root: Path, path: str, plan_hash: str) -> Path:
    # Short name: the Windows MAX_PATH limit (260) applies to the temporary sibling as well.
    token = digest((plan_hash + "\0" + path).encode("utf-8"))[:16]
    return (root / path).with_name(".metadata-" + token + ".tmp")


def _replace_bytes(target: Path, data: bytes, mode: int, temporary: Path) -> None:
    safe_path(target, missing=True, writable=True)
    safe_path(temporary, missing=True)
    with temporary.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, mode)
    safe_path(target, missing=True, writable=True)
    os.replace(temporary, target)


def _journal_data(root: Path, plan: dict) -> dict:
    directories, modes = set(), {}
    plan_hash = digest(json.dumps(plan, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    for item in plan["writes"]:
        path = root / item["path"]
        if path.exists():
            modes[item["path"]] = stat.S_IMODE(safe_path(path, writable=True).stat().st_mode)
        else:
            modes[item["path"]] = 0o600
        require(modes[item["path"]] <= 0o777, "Unsupported special file permissions")
        parent = path.parent
        while parent != root and not parent.exists():
            directories.add(parent.relative_to(root).as_posix())
            parent = parent.parent
        require(safe_path(parent).is_dir(), "Invalid target parent")
        temporary = _temporary(root, item["path"], plan_hash)
        require(not temporary.exists() and not temporary.is_symlink(), "Temporary path is occupied", 3)
    return {
        "schemaVersion": 1,
        "root": str(root),
        "planHash": plan_hash,
        "writes": plan["writes"],
        "modes": modes,
        "createdDirectories": sorted(directories, key=lambda p: (p.count("/"), p)),
    }


def _check_journal(root: Path, plan: dict, journal: dict) -> None:
    keys(journal, ("schemaVersion", "root", "planHash", "writes", "modes", "createdDirectories"))
    require(type(journal["schemaVersion"]) is int and journal["schemaVersion"] == 1, "Invalid journal version", 3)
    require(
        journal["root"] == str(root)
        and journal["planHash"] == digest(json.dumps(plan, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        and journal["writes"] == plan["writes"],
        "Journal belongs to another plan",
        3,
    )
    require(
        isinstance(journal["modes"], dict) and set(journal["modes"]) == {item["path"] for item in plan["writes"]},
        "Invalid journal modes",
        3,
    )
    require(
        all(type(mode) is int and 0 <= mode <= 0o777 for mode in journal["modes"].values()),
        "Invalid journal permissions",
        3,
    )
    directories = journal["createdDirectories"]
    require(
        isinstance(directories, list) and all(isinstance(p, str) for p in directories), "Invalid journal directories", 3
    )
    require(len(directories) == len(set(directories)), "Duplicate journal directory", 3)
    expected = {
        entry["path"]
        for entry in plan["directories"]
        if entry["root"] == "target"
        and entry["entries"] is None
        and any(item["path"].startswith(entry["path"] + "/") and item["after"]["present"] for item in plan["writes"])
    }
    require(set(directories) == expected, "Journal directory ownership mismatch", 3)
    for directory in directories:
        relative(directory)
        require(
            any(item["path"].startswith(directory + "/") and item["after"]["present"] for item in plan["writes"]),
            "Journal directory is outside writes",
            3,
        )


def _recovery_check(root: Path, plan: dict, journal: dict) -> tuple[Snapshot, list[Path]]:
    """Validate ALL paths before restoring even the first file."""
    snapshot = replay_plan(root, plan)
    actual = Snapshot(root)
    actual.roots = dict(snapshot.roots)
    current_view = copy.copy(snapshot)
    current_view.writes = {}
    for (alias, path), before in snapshot.blobs.items():
        current = actual.read(alias, path, optional=True)
        if alias == "target" and path in snapshot.writes:
            require(current in (before, snapshot.writes[path]), "Foreign file blocks recovery", 3)
            if current != before:
                current_view.writes[path] = current
        else:
            require(current == before, "Read-only source blocks recovery", 3)
    temporaries = []
    for item in plan["writes"]:
        temporary = _temporary(root, item["path"], journal["planHash"])
        if temporary.exists() or temporary.is_symlink():
            data = read_file(temporary, FILE_LIMIT)
            # A crash during write may leave only a prefix. The path was checked
            # absent before journaling and is derived only from this plan.
            require(
                any(
                    value is not None and value.startswith(data)
                    for value in (state_bytes(item["before"]), state_bytes(item["after"]))
                ),
                "Foreign temporary file blocks recovery",
                3,
            )
            temporaries.append(temporary)
    present_directories = set()
    for path in journal["createdDirectories"]:
        full = root / path
        if full.exists() or full.is_symlink():
            require(safe_path(full).is_dir(), "Foreign directory blocks recovery", 3)
            present_directories.add(path)
            allowed = {
                Path(item["path"]).name for item in plan["writes"] if Path(item["path"]).parent.as_posix() == path
            }
            allowed |= {
                Path(other).name for other in journal["createdDirectories"] if Path(other).parent.as_posix() == path
            }
            allowed |= {temp.name for temp in temporaries if temp.parent == full}
            require(
                set(actual.list_directory("target", path) or {}) <= allowed,
                "Foreign contents block directory recovery",
                3,
            )
    for (alias, path), expected in snapshot.enumerations.items():
        current = actual.list_directory(alias, path, optional=True)
        if alias == "target":
            projected = current_view.list_directory(alias, path, optional=True)
            if path in present_directories and projected is None:
                projected = {}
            for directory in present_directories:
                parent = Path(directory).parent.as_posix()
                if ("" if parent == "." else parent) == path:
                    projected = dict(projected or {})
                    projected[Path(directory).name] = "directory"
            if current is not None:
                current = dict(current)
                for temporary in temporaries:
                    if temporary.parent == snapshot.roots[alias] / path:
                        current.pop(temporary.name, None)
            require(current == projected, "Foreign directory state blocks recovery", 3)
        else:
            require(current == expected, "Read-only directory blocks recovery", 3)
    actual.unchanged()
    return snapshot, temporaries


def _rollback(root: Path, plan: dict, journal: dict) -> None:
    _, temporaries = _recovery_check(root, plan, journal)
    for temporary in temporaries:
        safe_path(temporary, writable=True).unlink()
    for item in reversed(plan["writes"]):
        path = root / item["path"]
        before, after = state_bytes(item["before"]), state_bytes(item["after"])
        current = Snapshot(root).read("target", item["path"], optional=True)
        require(current in (before, after), "Foreign file blocks rollback", 3)
        if current == before:
            continue
        if before is None:
            safe_path(path, writable=True).unlink()
        else:
            _replace_bytes(
                path, before, journal["modes"][item["path"]], _temporary(root, item["path"], journal["planHash"])
            )
    for directory in sorted(journal["createdDirectories"], key=lambda p: (p.count("/"), p), reverse=True):
        path = root / directory
        if path.exists():
            safe_path(path).rmdir()
    require(verify_plan(root, plan)[0] in ("before", "after"), "Rollback verification failed", 4)


def publish_plan(root: Path, plan: dict) -> str:
    check_metadata_plan(plan)
    root = safe_path(root)
    require(root.is_dir() and root.parent != root, "Invalid publication root")
    directory = root.with_name("." + root.name + ".metadata-state")
    if not all(not directory.is_relative_to(Path(source)) for source in plan["roots"].values()):
        raise FixedRejected(
            "Publication state directory next to --root is inside a declared source root "
            "(for template.import-xlsx: the xlsx directory); keep sources outside the parent of --root",
            3,
        )
    with file_lock(root):
        journal_path = safe_path(directory / "journal.json", missing=True)
        if journal_path.exists():
            journal = json_read(journal_path, PLAN_LIMIT)
            _check_journal(root, plan, journal)
            _recovery_check(root, plan, journal)
            try:
                state, _ = verify_plan(root, plan)
            except Rejected:
                state = "mixed"
            if state == "after":
                _, temporaries = _recovery_check(root, plan, journal)
                for temporary in temporaries:
                    safe_path(temporary, writable=True).unlink()
                journal_path.unlink()
                return "already-applied"
            _rollback(root, plan, journal)
            journal_path.unlink()
        state, _ = verify_plan(root, plan)
        if state == "after":
            return "already-applied"
        journal = _journal_data(root, plan)
        data = json.dumps(journal, ensure_ascii=False).encode("utf-8")
        require(len(data) <= PLAN_LIMIT, "Journal size limit exceeded")
        fd, temporary = tempfile.mkstemp(prefix=".journal-", dir=directory)
        os.close(fd)
        temporary_path = Path(temporary)
        try:
            # This staging file is outside every source root.
            with temporary_path.open("wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, journal_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        try:
            for directory_name in journal["createdDirectories"]:
                parent = root / directory_name
                safe_path(parent, missing=True).mkdir()
            for index, item in enumerate(plan["writes"], 1):
                print(f"metadata: publish file {index}/{len(plan['writes'])}", file=sys.stderr, flush=True)
                target = root / item["path"]
                require(
                    Snapshot(root).read("target", item["path"], optional=True) == state_bytes(item["before"]),
                    "Source changed during publication",
                    3,
                )
                value = state_bytes(item["after"])
                if value is None:
                    safe_path(target, writable=True).unlink()
                else:
                    _replace_bytes(
                        target,
                        value,
                        journal["modes"][item["path"]],
                        _temporary(root, item["path"], journal["planHash"]),
                    )
            require(verify_plan(root, plan)[0] == "after", "Publication verification failed", 4)
        except Exception:
            # On rollback failure retain the journal and original evidence.
            _rollback(root, plan, journal)
            journal_path.unlink()
            raise
        journal_path.unlink()
        return "applied"


class MetadataParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse includes unknown options and values in its default message.
        raise Rejected("Invalid metadata arguments")


def report_page(lines, limit, offset, **options):
    require(type(limit) is int and limit >= 0 and type(offset) is int and offset >= 0, "Invalid pagination")
    shown = lines[offset : offset + limit] if limit else lines[offset:]
    end = offset + len(shown)
    return {
        **options,
        "lines": shown,
        "totalLines": len(lines),
        "offset": offset,
        "nextOffset": end if end < len(lines) else None,
    }


def read_form_context(snapshot: Snapshot, target: str, *, verify=False, base_root=None):
    from . import metadata_form_ops as forms

    path = forms.form_path(target)
    descriptor_path, owner_path, config_path, kind = layout(path)
    parts = target.split(".")
    descriptor_kind = "CommonForm" if parts[0] == "CommonForm" else "Form"
    descriptor = metadata(snapshot.get("target", descriptor_path), descriptor_kind)
    adopted = prop(descriptor, "ObjectBelonging") == "Adopted"
    require(not verify or not adopted or base_root is not None, "Verification requires exact base-root")
    snapshot.load_form(path, base_root=base_root if adopted else None, inspect_only=True)
    for metadata_path in {descriptor_path, owner_path, config_path}:
        root = xml_read(snapshot.get("target", metadata_path), f"{{{MD}}}MetaDataObject")
        require(root.get("version") in {"2.17", "2.20"}, "Unsupported form context version")
    if kind == "external":
        require(etree.QName(snapshot.owner).localname == parts[0], "External object kind mismatch")
    return path, descriptor


def inspect_form(snapshot: Snapshot, target: str, expand="", limit=150, offset=0) -> dict:
    from . import metadata_borrow as borrow
    from . import metadata_form_ops as forms
    from . import metadata_info

    require(
        isinstance(expand, str) and len(expand) <= 1024 and not any(ord(c) < 32 for c in expand),
        "Invalid expand selection",
    )
    path, descriptor = read_form_context(snapshot, target)
    parts = target.split(".")
    context = "CommonForms" if parts[0] == "CommonForm" else borrow.DIRECTORIES.get(parts[0], parts[0]) + "." + parts[1]
    lines = metadata_info.form_report(snapshot.tree, parts[-1], context, expand)
    members = []
    dependencies = []
    for node in snapshot.tree.iter():
        if not isinstance(node.tag, str):
            continue
        location = node.getroottree().getpath(node)
        if node.get("name") is not None or node.get("id") is not None:
            members.append(
                {"path": location, "kind": etree.QName(node).localname, "name": node.get("name"), "id": node.get("id")}
            )
        if (
            node.tag
            in {f"{{{FORM}}}{name}" for name in ("DataPath", "CommandName", "MainTable", "Action", "Event")}
            | {f"{{{V8}}}Type", f"{{{V8}}}TypeSet"}
            and (node.text or "").strip()
        ):
            dependencies.append({"path": location, "property": etree.QName(node).localname, "value": node.text})
    result = {
        "object": target,
        "file": path,
        "uuid": snapshot.uuids["form"],
        "rootUuid": snapshot.uuids["configuration"],
        "version": snapshot.tree.get("version"),
        "belonging": prop(descriptor, "ObjectBelonging") or "Native",
        "baseLink": "not-checked" if snapshot.kind == "borrowed-cfe" else "not-applicable",
        "elements": forms.list_elements(snapshot.tree),
        "members": members,
        "dependencies": {"scope": "form-xml-only", "resolved": False, "items": dependencies},
        "supportedOperations": [
            "form.compile",
            "form.edit",
            "form.add-input",
            "form.remove",
            *forms.ELEMENT_OPERATIONS,
        ],
        "operationChecks": "not-run",
        "report": report_page(lines, limit, offset, expand=expand),
    }
    require(len(json.dumps(result, ensure_ascii=False).encode("utf-8")) <= FILE_LIMIT, "Inspect output limit exceeded")
    return result


def inspect_object(
    snapshot: Snapshot, target: str, mode="overview", name="", limit=150, offset=0, base_root=None
) -> dict:
    from . import metadata_borrow as borrow
    from . import metadata_form_ops as forms
    from . import metadata_info
    from . import metadata_object_ops as objects

    require(mode in {"overview", "brief", "full"} and (not name or NAME.fullmatch(name)), "Invalid inspect options")
    require(type(limit) is int and limit >= 0 and type(offset) is int and offset >= 0, "Invalid pagination")
    config, node, path, _ = objects.read_object(snapshot, target)
    try:
        lines = metadata_info.object_report(node, mode, name)
    except ValueError:
        raise Rejected("Unknown report member") from None
    members = []

    def children(owner, logical):
        for child in owner.findall("m:ChildObjects/*", NS):
            kind = etree.QName(child).localname
            require(child.tag == f"{{{MD}}}{kind}", "Unknown child namespace", 4)
            member_name = node_name(child) if child.find("m:Properties", NS) is not None else child.text or ""
            require(NAME.fullmatch(member_name), "Invalid child name", 4)
            member_path = logical + "." + kind + "." + member_name
            members.append({"object": member_path, "uuid": identity(child) if child.get("uuid") else None})
            children(child, member_path)

    children(node, target)
    dependencies = []
    for field in node.iter():
        if not isinstance(field.tag, str):
            continue
        value = field.text or ""
        if not value.strip():
            continue
        qname = etree.QName(field)
        if field.tag in {f"{{{V8}}}Type", f"{{{V8}}}TypeSet"}:
            prefix, colon, typename = value.partition(":")
            if colon and field.nsmap.get(prefix) == borrow.CFG:
                dependencies.append({"property": qname.localname, "value": typename, "namespace": borrow.CFG})
        elif field.tag in {f"{{{borrow.XR}}}Item", f"{{{borrow.XR}}}Field"}:
            dependencies.append({"property": qname.localname, "value": value, "namespace": borrow.XR})
        elif qname.namespace == MD and (
            qname.localname.endswith("Form")
            or qname.localname in {"ExtendedConfigurationObject", "Handler", "MethodName", "MainDataCompositionSchema"}
        ):
            if not len(field) and field.getparent().tag == f"{{{MD}}}Properties":
                dependencies.append({"property": qname.localname, "value": value, "namespace": MD})
    kind = etree.QName(node).localname
    operations = ["object.edit"]
    if config is None:
        if kind in objects.RENAME_OBJECT_TYPES:
            operations.append("object.rename")
    elif kind in objects.REMOVE_DIRECTORIES:
        operations.append("object.remove")
    if kind in forms.FORM_OBJECT_TYPES and node.getparent().get("version") == "2.17":
        operations.append("form.create")
    internal = node.find(f"{{{MD}}}InternalInfo")
    property_states = []
    if internal is not None:
        for state in internal.findall(f"{{{borrow.XR}}}PropertyState"):
            property_states.append(
                {
                    "property": state.findtext(f"{{{borrow.XR}}}Property") or "",
                    "state": state.findtext(f"{{{borrow.XR}}}State") or "",
                }
            )
    properties = node.find(f"{{{MD}}}Properties")
    scalar_properties = []
    type_summaries = []
    if properties is not None:
        for value in properties:
            if not isinstance(value.tag, str) or etree.QName(value).namespace != MD:
                continue
            local_name = etree.QName(value).localname
            if len(value) == 0:
                scalar_properties.append({"name": local_name, "value": value.text or ""})
            if local_name != "Type":
                continue

            def type_values(container):
                return [
                    (item.text or "").strip()
                    for item in container.findall(f".//{{{V8}}}Type")
                    if (item.text or "").strip()
                ]

            type_summary = {
                "valueType": value.get("{http://www.w3.org/2001/XMLSchema-instance}type", ""),
                "checkValue": [],
                "extendValue": [],
                "directTypes": [],
            }
            check = value.findall(f"{{{borrow.XR}}}CheckValue")
            extend = value.findall(f"{{{borrow.XR}}}ExtendValue")
            type_summary["checkValue"] = [type_values(item) for item in check]
            type_summary["extendValue"] = [type_values(item) for item in extend]
            nested_tags = {f"{{{borrow.XR}}}CheckValue", f"{{{borrow.XR}}}ExtendValue"}
            type_summary["directTypes"] = [
                (item.text or "").strip()
                for item in value.findall(f".//{{{V8}}}Type")
                if (item.text or "").strip()
                and not any(ancestor.tag in nested_tags for ancestor in item.iterancestors())
            ]
            type_summaries.append(type_summary)
    result = {
        "object": target,
        "file": path,
        "uuid": identity(node),
        "rootUuid": identity(config) if config is not None else None,
        "version": node.getparent().get("version"),
        "belonging": prop(node, "ObjectBelonging") or "Native",
        "propertyStates": property_states,
        "scalarProperties": scalar_properties,
        "typeSummary": type_summaries,
        "members": members,
        "dependencies": {"scope": "descriptor-only", "resolved": False, "items": dependencies},
        "supportedOperations": operations,
        "operationChecks": "not-run",
        "report": report_page(lines, limit, offset, mode=mode, name=name),
    }
    if kind in {"ChartOfAccounts", "ChartOfCharacteristicTypes", "Catalog"}:
        from . import metadata_predefined

        try:
            predefined_page = metadata_predefined.inspect(snapshot, target, limit, offset, base_root)
        except Rejected as exc:
            if kind != "ChartOfCharacteristicTypes":
                raise
            result["predefinedItems"] = []
            result["predefinedItemsTotal"] = None
            result["predefinedItemsNextOffset"] = None
            result["predefinedItemsError"] = {
                "code": exc.code if exc.code in PUBLIC_ERRORS else 4,
                "message": PUBLIC_ERRORS.get(exc.code, PUBLIC_ERRORS[4]),
            }
        else:
            result["predefinedItems"] = predefined_page["items"]
            result["predefinedItemsTotal"] = predefined_page["total"]
            result["predefinedItemsNextOffset"] = predefined_page["nextOffset"]
        if prop(node, "ObjectBelonging") == "Adopted" and prop(config, "ConfigurationExtensionPurpose"):
            result["supportedOperations"].append("predefined.create")
            if kind == "ChartOfAccounts":
                result["supportedOperations"].append("predefined.update")
    require(len(json.dumps(result, ensure_ascii=False).encode("utf-8")) <= FILE_LIMIT, "Inspect output limit exceeded")
    return result


def verify_objects(snapshot: Snapshot, targets: list[str], detailed=False, max_errors=30, base_root=None) -> dict:
    from . import metadata_borrow as borrow
    from . import metadata_object_ops as objects
    from . import metadata_validate

    require(type(max_errors) is int and max_errors > 0, "Invalid error limit")
    require(type(detailed) is bool and type(targets) is list and targets, "Invalid verification options")
    require(all(isinstance(target, str) and len(target) <= 512 for target in targets), "Invalid target")
    require(len(targets) <= 100, "Too many verification targets")
    base_alias = snapshot.source_root(base_root) if base_root is not None else None
    reports = []
    for target in targets:
        try:
            if is_template_target(target):
                from . import metadata_template_ops

                report = metadata_template_ops.verify_report(snapshot, target, detailed=detailed, max_errors=max_errors)
                code = 4 if report["errors"] or report["warnings"] or report["stopped"] else 0
                reports.append({"object": target, "code": code, "report": report})
                continue
            if target.startswith("CommonForm.") or ".Form." in target:
                read_form_context(snapshot, target, verify=True, base_root=base_root)
                report = metadata_validate.form_report(
                    snapshot.tree, target.split(".")[-1], detailed=detailed, max_errors=max_errors
                )
                code = 4 if report["errors"] or report["warnings"] or report["stopped"] else 0
                reports.append(
                    {
                        "object": target,
                        "code": code,
                        "report": report,
                        "baseLink": "checked" if snapshot.kind == "borrowed-cfe" else "not-applicable",
                    }
                )
                continue
            parts = target.split(".")
            if len(parts) == 2 and parts[0] in {"ExternalDataProcessor", "ExternalReport"}:
                # EPF/ERF root: <Name>.xml beside the <Name>/ directory, no Configuration.xml.
                require(NAME.fullmatch(parts[1]), "Unsupported verification target")
                root = xml_read(snapshot.get("target", parts[1] + ".xml"), f"{{{MD}}}MetaDataObject")
                nodes = [node for node in root if isinstance(node.tag, str)]
                require(len(nodes) == 1 and nodes[0].tag == f"{{{MD}}}{parts[0]}", "Object kind mismatch", 4)
                require(prop(nodes[0], "Name") == parts[1], "Object name mismatch", 4)
                report = metadata_validate.object_report(root, detailed=detailed, max_errors=max_errors)
                code = 4 if report["errors"] or report["warnings"] or report["stopped"] else 0
                reports.append({"object": target, "code": code, "report": report})
                continue
            require(
                len(parts) == 2 and parts[0] in metadata_ops.OBJECT_TYPES and NAME.fullmatch(parts[1]),
                "Unsupported verification target",
            )
            kind, name = parts
            configuration = snapshot.read("target", "Configuration.xml", optional=True)
            if configuration is None:
                require(kind == "CommonModule", "Configuration.xml required for this object type")
                entry = snapshot.package_entry(kind, name)
                if entry is None:
                    raise Rejected("Object registration missing", 4)
                registrations = None
                path = entry["root"] + ".xml"
            else:
                config = metadata(configuration, "Configuration")
                registrations = borrow._registrations(config)
                require(borrow._linked(registrations, kind, name), "Object registration missing", 4)
                path = borrow.DIRECTORIES[kind] + "/" + name + ".xml"
            root = xml_read(snapshot.get("target", path), f"{{{MD}}}MetaDataObject")
            nodes = [node for node in root if isinstance(node.tag, str)]
            require(len(nodes) == 1 and nodes[0].tag == f"{{{MD}}}{kind}", "Object kind mismatch", 4)
            require(prop(nodes[0], "Name") == name, "Object name mismatch", 4)
            references = None
            modules = None
            if kind in {"AccumulationRegister", "AccountingRegister", "CalculationRegister"} or (
                kind == "InformationRegister" and prop(nodes[0], "WriteMode") == "RecorderSubordinate"
            ):
                if registrations is None:
                    raise Rejected("Configuration.xml required for this object type", 4)
                references = set()
                adopted_register = prop(nodes[0], "ObjectBelonging") == "Adopted"
                source_registrations = [registrations]
                if adopted_register:
                    require(base_alias is not None, "Verification requires exact base-root", 4)
                    base_config, _ = borrow._checked(snapshot, base_alias, "Configuration.xml", "Configuration")
                    base_registrations = borrow._registrations(base_config)
                    require(borrow._linked(base_registrations, kind, name), "Base object registration missing", 4)
                    borrow._checked(snapshot, base_alias, path, kind)
                    objects.exact_base_owner(snapshot, nodes[0], path)
                    source_registrations.append(base_registrations)
                document_names = {}
                for source in source_registrations:
                    for entry in source.findall(f"{{{MD}}}Document"):
                        entry_name = entry.text or ""
                        folded = entry_name.casefold()
                        require(
                            NAME.fullmatch(entry_name)
                            and (folded not in document_names or document_names[folded] == entry_name),
                            "Ambiguous document registration",
                            4,
                        )
                        document_names[folded] = entry_name
                for document_name in document_names.values():
                    target_path = "Documents/" + document_name + ".xml"
                    target_document = None
                    target_entry = next(
                        (entry for entry in registrations.findall(f"{{{MD}}}Document") if entry.text == document_name),
                        None,
                    )
                    if target_entry is not None:
                        target_document, _ = borrow._checked(snapshot, "target", target_path, "Document")
                        require(node_name(target_document) == document_name, "Document name mismatch", 4)
                    if target_document is None:
                        document, _ = borrow._checked(snapshot, base_alias, target_path, "Document")
                        _, values = objects.read_reference_list(document, "RegisterRecords")
                    elif (
                        prop(target_document, "ObjectBelonging") == "Adopted"
                        and base_alias is None
                        and not target_document.findall(f"{{{MD}}}Properties/{{{MD}}}RegisterRecords")
                    ):
                        # Without base-root an adopted descriptor inherits RegisterRecords
                        # from the base configuration that cannot be read here.
                        values = []
                    elif prop(target_document, "ObjectBelonging") == "Adopted":
                        require(base_alias is not None, "Verification requires exact base-root", 4)
                        base_document, _ = borrow._checked(snapshot, base_alias, target_path, "Document")
                        require(node_name(base_document) == document_name, "Base document name mismatch", 4)
                        inherited = objects.exact_base_owner(snapshot, target_document, target_path)
                        _, inherited_values = objects.read_reference_list(inherited, "RegisterRecords")
                        containers = target_document.findall(f"{{{MD}}}Properties/{{{MD}}}RegisterRecords")
                        if len(containers) == 0:
                            values = inherited_values
                        else:
                            _, own_values = objects.read_reference_list(target_document, "RegisterRecords")
                            values = [*inherited_values, *own_values]
                    else:
                        _, values = objects.read_reference_list(target_document, "RegisterRecords")
                    for value in values:
                        linked = value.split(".")
                        require(
                            len(linked) == 2 and linked[0] in objects.REGISTER_KINDS and NAME.fullmatch(linked[1]),
                            "Invalid register reference",
                            4,
                        )
                    references.update(values)
            if kind in {"EventSubscription", "ScheduledJob"} and registrations is not None:
                reference = prop(nodes[0], "Handler" if kind == "EventSubscription" else "MethodName")
                pieces = reference.split(".")
                module_name = (
                    pieces[1]
                    if len(pieces) == 3 and pieces[0] == "CommonModule"
                    else (pieces[0] if len(pieces) == 2 else "")
                )
                modules = set()
                if (
                    module_name
                    and NAME.fullmatch(module_name)
                    and borrow._linked(registrations, "CommonModule", module_name)
                ):
                    module, _ = borrow._checked(
                        snapshot, "target", "CommonModules/" + module_name + ".xml", "CommonModule"
                    )
                    require(node_name(module) == module_name, "CommonModule name mismatch", 4)
                    modules.add(module_name)
            report = metadata_validate.object_report(
                root, detailed=detailed, max_errors=max_errors, registrar_references=references, common_modules=modules
            )
            if kind in {"ChartOfAccounts", "ChartOfCharacteristicTypes", "Catalog"}:
                from . import metadata_predefined

                metadata_predefined.verify(snapshot, target, base_root)
            code = 4 if report["errors"] or report["warnings"] or report["stopped"] else 0
            reports.append({"object": target, "code": code, "report": report})
        except (Rejected, OSError, UnicodeError, ValueError, TypeError, RecursionError, etree.Error) as exc:
            code = exc.code if isinstance(exc, Rejected) and exc.code in PUBLIC_ERRORS else 5
            reports.append(
                {
                    "object": target,
                    "code": code,
                    "error": str(exc) if isinstance(exc, TemplateKindRejected) else PUBLIC_ERRORS[code],
                }
            )
    snapshot.unchanged()
    code = next((code for code in (5, 3, 4, 2) if any(item["code"] == code for item in reports)), 0)
    result = {"code": code, "objects": reports}
    require(
        len(json.dumps(result, ensure_ascii=False).encode("utf-8")) <= FILE_LIMIT, "Verification output limit exceeded"
    )
    return result


def dispatch(args: argparse.Namespace) -> tuple[str, dict | None]:
    if args.action == "capabilities":
        return "capabilities", metadata_ops.capabilities()
    if args.action == "verify":
        result = verify_objects(
            Snapshot(Path(args.root)),
            args.object,
            args.detailed,
            args.max_errors,
            Path(args.base_root) if args.base_root else None,
        )
        return ("verified" if result["code"] == 0 else "failed" if result["code"] == 5 else "rejected"), result
    if args.action == "inspect":
        if is_template_target(args.object):
            from . import metadata_template_ops

            require(
                args.mode == "overview"
                and not args.name
                and not args.expand
                and not args.base_root
                and args.limit == 150
                and args.offset == 0,
                "Object report options do not apply to templates",
            )
            return "inspected", metadata_template_ops.inspect(Snapshot(Path(args.root)), args.object)
        if args.object.startswith("CommonForm.") or ".Form." in args.object:
            require(args.mode == "overview" and not args.name, "Object report options do not apply to forms")
            return "inspected", inspect_form(
                Snapshot(Path(args.root)), args.object, args.expand, args.limit, args.offset
            )
        require(not args.expand, "Expand applies only to forms")
        return "inspected", inspect_object(
            Snapshot(Path(args.root)),
            args.object,
            args.mode,
            args.name,
            args.limit,
            args.offset,
            Path(args.base_root) if args.base_root else None,
        )
    if args.action == "apply":
        plan = json_read(Path(args.plan), PLAN_LIMIT)
        check_metadata_plan(plan)
        status = apply(Path(args.root), None, plan)
        return status, (
            {"pendingDependencies": plan["pendingDependencies"], "checks": plan["checks"]}
            if "pendingDependencies" in plan
            else None
        )
    if args.action == "plan":
        request = json_read(Path(args.request), PLAN_LIMIT)
        require("operations" in request, "Expected metadata request")
        out = safe_path(Path(args.out), missing=True)
        require(not out.exists(), "Output already exists", 3)
        snapshot = Snapshot(Path(args.root))
        result = plan_make(snapshot, request)
        if not all(not out.is_relative_to(root) for root in snapshot.roots.values()):
            raise FixedRejected(
                "Plan output is inside a declared source root (for template.import-xlsx: "
                "the xlsx directory); choose --out outside --root and outside the xlsx directory",
                3,
            )
        data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        require(len(data) <= PLAN_LIMIT, "Plan size limit exceeded")
        try:
            with out.open("xb") as stream:
                stream.write(data)
        except FileExistsError:
            raise Rejected("Output already exists", 3) from None
        return "planned", result
    # A declared schema is not an executable handler. Do not forward to the old
    # form CLI: its request and publication guarantees differ from metadata.
    raise Rejected("Metadata action is not connected")


def main(argv: list[str]) -> int:
    try:
        parser = MetadataParser(prog="metadata", add_help=False, allow_abbrev=False)
        actions = parser.add_subparsers(dest="action", required=True)
        for action in ("capabilities", "inspect", "plan", "apply", "verify"):
            command = actions.add_parser(action, add_help=False, allow_abbrev=False)
            if action != "capabilities":
                command.add_argument("--root", required=True)
            if action in ("inspect", "verify"):
                command.add_argument("--object", required=True, action="append" if action == "verify" else "store")
                if action == "inspect":
                    command.add_argument("--mode", choices=("overview", "brief", "full"), default="overview")
                    command.add_argument("--name", default="")
                    command.add_argument("--limit", type=int, default=150)
                    command.add_argument("--offset", type=int, default=0)
                    command.add_argument("--expand", default="")
                    command.add_argument("--base-root")
                else:
                    command.add_argument("--detailed", action="store_true")
                    command.add_argument("--max-errors", type=int, default=30)
                    command.add_argument("--base-root")
            elif action == "plan":
                command.add_argument("--request", required=True)
                command.add_argument("--out", required=True)
            elif action == "apply":
                command.add_argument("--plan", required=True)
        args = parser.parse_args(argv)
        status, changes = dispatch(args)
        result = {
            "schemaVersion": 1,
            "status": status,
            "checks": {"platform": "not-run", "runtime": "not-run"},
            "changes": changes,
            "error": None,
        }
        code = 0
        if args.action == "verify":
            assert changes is not None
            code = changes["code"]
            result["checks"]["local"] = changes
            result["changes"] = None
            if code:
                result["error"] = {"code": code, "message": PUBLIC_ERRORS[code]}
    except (Rejected, OSError, UnicodeError, ValueError, TypeError, RecursionError, etree.Error) as exc:
        code = exc.code if isinstance(exc, Rejected) and exc.code in (2, 3, 4, 5) else 5
        # Do not echo paths, request content, BSL or exception text. Fixed public
        # diagnostics are bounded below 8 KiB in UTF-8, not merely characters.
        message = (
            str(exc)
            if isinstance(exc, (TypeDependencyRejected, PublicRejected, TemplateKindRejected, FixedRejected))
            else PUBLIC_ERRORS[code]
        )
        result = {
            "schemaVersion": 1,
            "status": "failed" if code == 5 else "rejected",
            "checks": {"platform": "not-run", "runtime": "not-run"},
            "changes": None,
            "error": {"code": code, "message": message},
        }
    print(json.dumps(result, ensure_ascii=False))
    return code
