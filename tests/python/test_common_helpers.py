"""Shared helpers of scripts/python/common.py: archived OpenSpec evidence paths and JSON narrowing."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.python.common import object_dict, object_list, resolve_openspec_path


def test_archived_change_path_is_found_without_rewriting_evidence(tmp_path: Path) -> None:
    logical = tmp_path / "openspec/changes/completed-change/evidence.json"
    archived = tmp_path / "openspec/changes/archive/2026-01-02-completed-change/evidence.json"
    archived.parent.mkdir(parents=True)
    archived.write_bytes(b'{"path":"openspec/changes/completed-change/evidence.json"}\n')
    before = archived.read_bytes()

    assert resolve_openspec_path(logical, root=tmp_path) == archived
    assert archived.read_bytes() == before
    assert resolve_openspec_path(archived, root=tmp_path) == archived
    assert resolve_openspec_path(tmp_path / "other.json", root=tmp_path) == tmp_path / "other.json"


def test_active_change_wins_over_archive(tmp_path: Path) -> None:
    logical = tmp_path / "openspec/changes/completed-change/evidence.json"
    (tmp_path / "openspec/changes/archive/2026-01-02-completed-change").mkdir(parents=True)
    logical.parent.mkdir(parents=True)
    logical.write_text("active", encoding="utf-8")
    assert resolve_openspec_path(logical, root=tmp_path) == logical
    # The active change directory exists, so a missing file inside it is not looked up in the archive.
    logical.unlink()
    assert resolve_openspec_path(logical, root=tmp_path) == logical


@pytest.mark.parametrize(
    "relative",
    [
        "openspec/changes/archive/evidence.json",
        "openspec/changes/Not_A_Change/evidence.json",
        "openspec/changes/completed-change/../evidence.json",
        "openspec/specs/completed-change/spec.md",
    ],
)
def test_paths_outside_the_change_layout_are_returned_unchanged(tmp_path: Path, relative: str) -> None:
    (tmp_path / "openspec/changes/archive/2026-01-02-completed-change").mkdir(parents=True)
    path = tmp_path / relative
    assert resolve_openspec_path(path, root=tmp_path) == path


def test_path_outside_root_is_returned_unchanged(tmp_path: Path) -> None:
    outside = tmp_path.parent / "openspec/changes/completed-change/evidence.json"
    assert resolve_openspec_path(outside, root=tmp_path) == outside


def test_two_archived_copies_are_ambiguous(tmp_path: Path) -> None:
    archive = tmp_path / "openspec/changes/archive"
    (archive / "2026-01-02-completed-change").mkdir(parents=True)
    (archive / "2026-01-03-completed-change").mkdir()
    with pytest.raises(ValueError, match="ambiguous archived change: completed-change"):
        resolve_openspec_path(tmp_path / "openspec/changes/completed-change/evidence.json", root=tmp_path)


def test_object_dict_keeps_only_string_keys() -> None:
    assert object_dict({"a": 1, 2: "b", "c": None}) == {"a": 1, "c": None}
    for value in (None, [], "text", 1):
        assert object_dict(value) == {}


def test_object_list_copies_lists_only() -> None:
    source = [1, "a"]
    result = object_list(source)
    assert result == source and result is not source
    for value in (None, {}, "text", (1, 2)):
        assert object_list(value) == []
