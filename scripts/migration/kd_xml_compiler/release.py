"""Build a KD 2.01 rules release: five XML documents, three ZIP archives and `manifest.json`.

The release is a pure function of `scenario.json`, the release matrix and the two metadata structures
pinned in the scenario by SHA-256. Neither the build time nor the output path enter any byte of the
release, so a repeated build with the same inputs is byte-identical.

Application rules come from a `RuleProvider`. The core ships only `TechnicalRules` (empty rule sets
for the technical workbench); project layers implement the protocol outside this package.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
import zipfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from .compiler import exchange_document, registration_document
from .metadata import Configuration, load_structure
from .registration_order import normalize_registration_rules
from .serializer import XmlNode

FORMAT_VERSION = "2.01"
COMPATIBILITY_MODE = "РежимСовместимостиСБСП21"
MANIFEST_SCHEMA_VERSION = 1
DEFAULT_COMMENT = "Технический выпуск"

# Release document roles. A matrix maps every role to exactly one release path.
SOURCE_EXCHANGE = "source-exchange"
SOURCE_REGISTRATION = "source-registration"
TARGET_EXCHANGE = "target-exchange"
CORRESPONDENT_EXCHANGE = "correspondent-exchange"
TARGET_REGISTRATION = "target-registration"
DOCUMENT_ROLES = (
    SOURCE_EXCHANGE,
    SOURCE_REGISTRATION,
    TARGET_EXCHANGE,
    CORRESPONDENT_EXCHANGE,
    TARGET_REGISTRATION,
)
UUID_KEYS = ("forwardUuid", "reverseUuid", "sourceRegistrationUuid", "targetRegistrationUuid")
_IDENTIFIER = re.compile(r"[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*\Z")
_ZIP_EPOCH_YEAR = 1980


class ReleaseError(ValueError):
    """The release inputs are inconsistent; nothing was written."""


class RuleProvider(Protocol):
    """Application rule sets of one scenario. The core calls it once per release."""

    def global_handlers(self, scenario: Mapping[str, Any]) -> dict[str, str]: ...

    def parameters(self, scenario: Mapping[str, Any]) -> list[dict[str, str]]: ...

    def conversion_rules(
        self, scenario: Mapping[str, Any], source: Configuration, target: Configuration
    ) -> tuple[XmlNode, XmlNode]: ...

    def registration_rules(self, scenario: Mapping[str, Any], side: str, configuration: Configuration) -> XmlNode: ...

    def registration_composition(
        self, scenario: Mapping[str, Any], side: str, configuration: Configuration
    ) -> list[str]: ...


class TechnicalRules:
    """Empty rule sets: the platform still has to accept the five documents of the release."""

    def global_handlers(self, scenario: Mapping[str, Any]) -> dict[str, str]:
        return {}

    def parameters(self, scenario: Mapping[str, Any]) -> list[dict[str, str]]:
        return []

    def conversion_rules(
        self, scenario: Mapping[str, Any], source: Configuration, target: Configuration
    ) -> tuple[XmlNode, XmlNode]:
        return XmlNode("ПравилаКонвертацииОбъектов"), XmlNode("ПравилаВыгрузкиДанных")

    def registration_rules(self, scenario: Mapping[str, Any], side: str, configuration: Configuration) -> XmlNode:
        return XmlNode("ПравилаРегистрацииОбъектов")

    def registration_composition(
        self, scenario: Mapping[str, Any], side: str, configuration: Configuration
    ) -> list[str]:
        return []


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require(mapping: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in mapping:
        raise ReleaseError(f"{where} is missing {key}")
    return mapping[key]


def _release_path(value: object, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReleaseError(f"{where} must be a non-empty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ReleaseError(f"{where} must stay inside the release directory: {value}")
    return path.as_posix()


def validate_matrix(matrix: Mapping[str, Any]) -> tuple[dict[str, str], list[tuple[str, list[str]]]]:
    """Return `role -> path` for the five documents and `(archive, members)` pairs in matrix order."""
    files = matrix.get("files")
    archives = matrix.get("archives")
    if not isinstance(files, list) or not isinstance(archives, list):
        raise ReleaseError("matrix must contain the lists files and archives")
    roles: dict[str, str] = {}
    for index, item in enumerate(files):
        if not isinstance(item, Mapping):
            raise ReleaseError(f"matrix files[{index}] must be an object")
        role = item.get("role")
        if role not in DOCUMENT_ROLES or role in roles:
            raise ReleaseError(f"matrix files[{index}] has an unknown or repeated role: {role}")
        roles[str(role)] = _release_path(item.get("path"), f"matrix files[{index}].path")
    missing = [role for role in DOCUMENT_ROLES if role not in roles]
    if missing:
        raise ReleaseError("matrix lacks document roles: " + ", ".join(missing))
    if len(set(roles.values())) != len(roles):
        raise ReleaseError("matrix maps two document roles to one path")
    documents = set(roles.values())
    packed: list[tuple[str, list[str]]] = []
    for index, item in enumerate(archives):
        if not isinstance(item, Mapping):
            raise ReleaseError(f"matrix archives[{index}] must be an object")
        path = _release_path(item.get("path"), f"matrix archives[{index}].path")
        members = item.get("members")
        if not isinstance(members, list) or not members:
            raise ReleaseError(f"matrix archives[{index}].members must be a non-empty list")
        parent = PurePosixPath(path).parent
        names: list[str] = []
        for member in members:
            name = _release_path(member, f"matrix archives[{index}].members")
            if (parent / name).as_posix() not in documents:
                raise ReleaseError(f"matrix archive {path} packs a file outside the release documents: {name}")
            names.append(name)
        if path in documents or any(path == other for other, _members in packed):
            raise ReleaseError(f"matrix archive path is repeated: {path}")
        packed.append((path, names))
    return roles, packed


def _check_identifier(value: object, where: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ReleaseError(f"{where} must be a 1C identifier")
    return value


def _check_scenario(scenario: Mapping[str, Any]) -> None:
    conversion = _require(scenario, "conversion", "scenario")
    for key in UUID_KEYS:
        try:
            uuid.UUID(str(_require(conversion, key, "scenario conversion")))
        except ValueError:
            raise ReleaseError(f"scenario conversion.{key} must be a UUID") from None
    _check_identifier(_require(conversion, "namespace", "scenario conversion"), "scenario conversion.namespace")
    for side in ("source", "target"):
        _check_identifier(
            _require(conversion, side + "ExchangePlan", "scenario conversion"),
            f"scenario conversion.{side}ExchangePlan",
        )
    created_at = str(_require(scenario, "createdAt", "scenario"))
    try:
        datetime.fromisoformat(created_at)
    except ValueError:
        raise ReleaseError("scenario createdAt must be an ISO 8601 date and time") from None
    _require(scenario, "releaseId", "scenario")
    versions = _require(scenario, "versions", "scenario")
    inputs = _require(scenario, "inputs", "scenario")
    for side in ("source", "target"):
        _require(versions, side, "scenario versions")
        _require(inputs, side + "StructureSha256", "scenario inputs")


def _zip_timestamp(created_at: str) -> tuple[int, int, int, int, int, int]:
    created = datetime.fromisoformat(created_at)
    if created.year < _ZIP_EPOCH_YEAR:
        return (_ZIP_EPOCH_YEAR, 1, 1, 0, 0, 0)
    return (created.year, created.month, created.day, created.hour, created.minute, created.second)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compile_release(
    scenario: Mapping[str, Any],
    output: Path,
    *,
    source_structure: Path,
    target_structure: Path,
    matrix: Mapping[str, Any],
    rules: RuleProvider | None = None,
) -> dict[str, Any]:
    """Write the release into the new directory `output` and return its manifest.

    Every input check runs before `output` is created: a structure whose SHA-256 differs from the
    scenario pin stops the build with the structure path in the message and leaves no release behind.
    """
    provider: RuleProvider = rules if rules is not None else TechnicalRules()
    _check_scenario(scenario)
    roles, archives = validate_matrix(matrix)
    if output.exists() or output.is_symlink():
        raise ReleaseError(f"release directory must be new: {output}")
    inputs = scenario["inputs"]
    try:
        source = load_structure(source_structure, str(inputs["sourceStructureSha256"]))
        target = load_structure(target_structure, str(inputs["targetStructureSha256"]))
    except (OSError, ValueError) as error:
        raise ReleaseError(str(error)) from error
    for side, configuration in (("source", source), ("target", target)):
        if configuration.version != scenario["versions"][side]:
            raise ReleaseError(
                f"{side} structure version {configuration.version} differs from scenario version "
                f"{scenario['versions'][side]}"
            )

    conversion = scenario["conversion"]
    created_at = str(scenario["createdAt"])
    comment = str(conversion.get("comment") or DEFAULT_COMMENT)
    conversions, exports = provider.conversion_rules(scenario, source, target)
    forward = exchange_document(
        source,
        target,
        identifier=str(conversion["forwardUuid"]),
        name=f"{conversion['namespace']}_FORWARD",
        created_at=created_at,
        comment=comment,
        handlers=provider.global_handlers(scenario),
        parameters=provider.parameters(scenario),
        conversions=conversions,
        exports=exports,
    )
    reverse = exchange_document(
        target,
        source,
        identifier=str(conversion["reverseUuid"]),
        name=f"{conversion['namespace']}_REVERSE",
        created_at=created_at,
        comment=comment,
        handlers={},
        parameters=[],
        conversions=XmlNode("ПравилаКонвертацииОбъектов"),
        exports=XmlNode("ПравилаВыгрузкиДанных"),
    )
    documents: dict[str, str] = {
        roles[SOURCE_EXCHANGE]: forward,
        roles[TARGET_EXCHANGE]: reverse,
        roles[CORRESPONDENT_EXCHANGE]: forward,
    }
    registrations: list[str] = []
    for side, configuration, role, suffix in (
        ("source", source, SOURCE_REGISTRATION, "_SOURCE_REGISTRATION"),
        ("target", target, TARGET_REGISTRATION, "_TARGET_REGISTRATION"),
    ):
        documents[roles[role]] = registration_document(
            configuration,
            identifier=str(conversion[side + "RegistrationUuid"]),
            name=f"{conversion['namespace']}{suffix}",
            created_at=created_at,
            exchange_plan=str(conversion[side + "ExchangePlan"]),
            comment=comment,
            composition=provider.registration_composition(scenario, side, configuration),
            rules=provider.registration_rules(scenario, side, configuration),
        )
        registrations.append(roles[role])

    output.mkdir(parents=True)
    for relative, document in documents.items():
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(document, encoding="utf-8-sig", newline="\n")
    for relative in registrations:
        normalize_registration_rules(output / relative)

    timestamp = _zip_timestamp(created_at)
    for relative, members in archives:
        archive_path = output / relative
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for member in members:
                info = zipfile.ZipInfo(member, timestamp)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                info.create_system = 3
                archive.writestr(info, (archive_path.parent / member).read_bytes(), compresslevel=9)

    manifest: dict[str, Any] = {
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "releaseId": scenario["releaseId"],
        "createdAt": created_at,
        "formatVersion": FORMAT_VERSION,
        "compatibilityMode": COMPATIBILITY_MODE,
        "namespace": conversion["namespace"],
        "sourceVersion": scenario["versions"]["source"],
        "targetVersion": scenario["versions"]["target"],
        "sourceStructureSha256": str(inputs["sourceStructureSha256"]).lower(),
        "targetStructureSha256": str(inputs["targetStructureSha256"]).lower(),
        "conversionUuids": {key: conversion[key] for key in UUID_KEYS},
        "files": {roles[role]: sha256_file(output / roles[role]) for role in DOCUMENT_ROLES},
        "archives": {relative: sha256_file(output / relative) for relative, _members in archives},
    }
    _write_json(output / "manifest.json", manifest)
    return manifest
