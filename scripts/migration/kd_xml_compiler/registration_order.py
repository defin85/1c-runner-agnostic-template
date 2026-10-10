"""Deterministically order registration rules without changing their content."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree


def _identifier(element: ElementTree.Element, name: str, path: Path) -> str:
    value = element.findtext(name)
    if value is None or not value.strip():
        raise ValueError(f"registration rule is missing {name}: {path}")
    return value.strip()


def _sort_children(parent: ElementTree.Element, path: Path) -> None:
    children = list(parent)
    groups = [child for child in children if child.tag == "Группа"]
    rules = [child for child in children if child.tag == "Правило"]

    group_keys = [
        (
            _identifier(group, "ТипГруппы", path),
            _identifier(group, "Код", path),
        )
        for group in groups
    ]
    rule_keys = [
        (
            _identifier(rule, "ОбъектМетаданныхИмя", path),
            _identifier(rule, "Код", path),
        )
        for rule in rules
    ]
    if len(group_keys) != len(set(group_keys)):
        raise ValueError(f"registration groups have duplicate sort keys: {path}")
    if len(rule_keys) != len(set(rule_keys)):
        raise ValueError(f"registration rules have duplicate sort keys: {path}")

    ordered_groups = iter(group for _, group in sorted(zip(group_keys, groups, strict=True), key=lambda pair: pair[0]))
    ordered_rules = iter(rule for _, rule in sorted(zip(rule_keys, rules, strict=True), key=lambda pair: pair[0]))
    for index, child in enumerate(children):
        if child.tag == "Группа":
            children[index] = next(ordered_groups)
            _sort_children(children[index], path)
        elif child.tag == "Правило":
            children[index] = next(ordered_rules)

    parent[:] = children


def registration_bytes(tree: ElementTree.ElementTree[ElementTree.Element], path: Path) -> bytes:
    section = tree.getroot().find("ПравилаРегистрацииОбъектов")
    if section is None:
        raise ValueError(f"registration rules section is missing: {path}")
    _sort_children(section, path)
    ElementTree.indent(tree, space="\t")
    return ElementTree.tostring(tree.getroot(), encoding="utf-8") + b"\n"


def normalize_registration_rules(path: Path | str) -> None:
    """Sort registration groups and rules by metadata identity and code.

    An empty ``ПравилаРегистрацииОбъектов`` section is valid for technical
    releases. The file is written only after the full tree passes validation.
    """
    registration_path = Path(path)
    parser = ElementTree.XMLParser(
        target=ElementTree.TreeBuilder(insert_comments=True),
    )
    tree = ElementTree.parse(registration_path, parser=parser)
    registration_path.write_bytes(registration_bytes(tree, registration_path))
