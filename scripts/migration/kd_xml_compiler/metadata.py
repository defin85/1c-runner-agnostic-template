"""Neutral metadata model for KD structure exports."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree


@dataclass
class MetadataValue:
    name: str
    synonym: str
    predefined: bool
    parent: str = ""
    deleted: bool = False


@dataclass
class MetadataField:
    name: str
    path: str
    kind: str
    types: tuple[str, ...]
    qualifiers: dict[str, str]
    ref: str = ""
    code: str = ""


@dataclass
class MetadataObject:
    full_name: str
    name: str
    synonym: str
    kind: str
    fields: dict[str, MetadataField] = field(default_factory=dict)
    values: list[MetadataValue] = field(default_factory=list)
    lookup_fields: list[MetadataField] = field(default_factory=list)


@dataclass
class Configuration:
    name: str
    synonym: str
    version: str
    objects: dict[str, MetadataObject]


_PRIMITIVES = {"Число", "Строка", "Дата", "Булево"}
_ZERO_UUID = "00000000-0000-0000-0000-000000000000"
_HASH_RE = re.compile(r"[0-9a-fA-F]{64}\Z")


def _full_name(kind: str, name: str) -> str:
    return kind if kind in _PRIMITIVES or kind == name else f"{kind}.{name}"


def _required_text(element: ElementTree.Element, tag: str) -> str:
    value = element.findtext(tag)
    if not value:
        raise ValueError(f"KD structure record is missing {tag}")
    return value


def load_structure(path: Path | str, expected_sha256: str) -> Configuration:
    """Read a KD metadata structure after verifying its pinned SHA-256."""
    structure_path = Path(path)
    if not _HASH_RE.fullmatch(expected_sha256):
        raise ValueError("expected_sha256 must be a 64-character hexadecimal digest")
    hasher = hashlib.sha256()
    with structure_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    if digest.lower() != expected_sha256.lower():
        raise ValueError(f"KD structure SHA-256 mismatch: {structure_path}")

    config: tuple[str, str, str] | None = None
    objects_by_ref: dict[str, MetadataObject] = {}
    raw_fields: list[tuple[str, str, str, str, str, tuple[str, ...], dict[str, str], str]] = []
    raw_values: list[tuple[str, str, str, str, str, bool, bool]] = []

    for _, element in ElementTree.iterparse(structure_path, events=("end",)):
        if element.tag == "CatalogObject.Конфигурации":
            config = (
                _required_text(element, "Имя"),
                element.findtext("Синоним") or "",
                element.findtext("Версия") or "",
            )
            element.clear()
        elif element.tag == "CatalogObject.Объекты":
            reference = _required_text(element, "Ref")
            name = _required_text(element, "Имя")
            kind = element.findtext("Тип") or ""
            if not kind:
                # Top-level grouping rows (for example, "Документы") are
                # present in the KD export but are not metadata objects.
                element.clear()
                continue
            item = MetadataObject(
                full_name=_full_name(kind, name),
                name=name,
                synonym=element.findtext("Синоним") or "",
                kind=kind,
            )
            objects_by_ref[reference] = item
            element.clear()
        elif element.tag == "CatalogObject.Свойства":
            owner = element.findtext("Owner") or ""
            name = element.findtext("Имя") or element.findtext("Description") or ""
            if owner in objects_by_ref and name:
                type_refs = tuple(value.text or "" for value in element.findall("./Типы/Row/Тип") if value.text)
                raw_fields.append(
                    (
                        owner,
                        element.findtext("Ref") or "",
                        element.findtext("Parent") or _ZERO_UUID,
                        name,
                        element.findtext("Вид") or "",
                        type_refs,
                        {
                            "numberDigits": element.findtext("КвалификаторыЧисла_Длина") or "0",
                            "numberFractionDigits": element.findtext("КвалификаторыЧисла_Точность") or "0",
                            "numberNonnegative": element.findtext("КвалификаторыЧисла_Неотрицательное") or "false",
                            "stringLength": element.findtext("КвалификаторыСтроки_Длина") or "0",
                            "dateComposition": element.findtext("КвалификаторыДаты_Состав") or "",
                        },
                        element.findtext("Code") or "",
                    )
                )
            element.clear()
        elif element.tag == "CatalogObject.Значения":
            owner = element.findtext("Owner") or ""
            if owner in objects_by_ref:
                raw_values.append(
                    (
                        owner,
                        element.findtext("Ref") or "",
                        element.findtext("Parent") or _ZERO_UUID,
                        element.findtext("Имя") or element.findtext("Description") or "",
                        element.findtext("Синоним") or "",
                        (element.findtext("Предопределенное") or "false").lower() == "true",
                        (element.findtext("DeletionMark") or "false").lower() == "true",
                    )
                )
            element.clear()

    if config is None:
        raise ValueError(f"KD structure has no configuration record: {structure_path}")

    type_names = {reference: item.full_name for reference, item in objects_by_ref.items()}
    property_kinds = {reference: kind for _, reference, _, _, kind, _, _, _ in raw_fields}
    parent_paths: dict[str, str] = {}
    for owner, reference, parent, name, kind, type_refs, qualifiers, code in raw_fields:
        path_name = parent_paths.get(parent)
        field_path = f"{path_name}.{name}" if path_name else name
        parent_paths[reference] = field_path
        owner_object = objects_by_ref[owner]
        item = MetadataField(
            name=name,
            path=field_path,
            kind=kind,
            types=tuple(sorted({type_names[value] for value in type_refs if value in type_names})),
            qualifiers=qualifiers,
            ref=reference,
            code=code,
        )
        # Lookups by property name ignore Parent and need the serialized row order, so every row is
        # kept here; rule matching below uses only metadata fields.
        owner_object.lookup_fields.append(item)
        # KD also exports register movement sets and their dimensions/resources as properties. They are
        # runtime movements, not fields for conversion rules: a document may have a table part and a
        # movement set with the same name, and the movement row would overwrite the table part.
        if kind.startswith("НаборДвижений") or property_kinds.get(parent, "").startswith("НаборДвижений"):
            continue
        owner_object.fields[field_path] = item

    value_names: dict[tuple[str, str], str] = {}
    for owner, reference, _parent, name, _synonym, _predefined, _deleted in raw_values:
        value_names[(owner, reference)] = name
    value_paths: dict[tuple[str, str], str] = {}
    for owner, reference, parent, name, synonym, predefined, deleted in raw_values:
        parent_name = value_names.get((owner, parent), "")
        parent_path = value_paths.get((owner, parent), "")
        path = f"{parent_path}.{parent_name}" if parent_path else parent_name
        value_paths[(owner, reference)] = path
        objects_by_ref[owner].values.append(
            MetadataValue(
                name=name,
                synonym=synonym,
                predefined=predefined,
                parent=path,
                deleted=deleted,
            )
        )

    return Configuration(
        name=config[0],
        synonym=config[1],
        version=config[2],
        objects={item.full_name: item for item in objects_by_ref.values()},
    )
