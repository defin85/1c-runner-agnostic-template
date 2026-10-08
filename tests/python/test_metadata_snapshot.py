"""Ordered candidates are virtual; read preconditions cover only observed state."""

import tests.python.metadata_test_support  # noqa: F401, I001 — runs first: skips the module without pytest, lxml, jsonschema
import pytest

from scripts.python import metadata as editor


def contents(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_ordered_create_replace_delete_and_noop_leave_sources_untouched(tmp_path):
    original = b"\xef\xbb\xbfexisting\r\n"
    (tmp_path / "Existing.xml").write_bytes(original)
    (tmp_path / "Empty.xml").write_bytes(b"")
    before = contents(tmp_path)
    snapshot = editor.Snapshot(tmp_path)
    assert snapshot.read("target", "Existing.xml") == original
    snapshot.stage("Existing.xml", b"replaced\n")
    assert snapshot.read("target", "Existing.xml") == b"replaced\n"
    snapshot.stage("Forms/New/Ext/Form.xml", b"new\n")
    assert snapshot.read("target", "Forms/New/Ext/Form.xml") == b"new\n"
    assert snapshot.blobs["target", "Forms/New/Ext/Form.xml"] is None
    snapshot.stage("Empty.xml", None)
    assert snapshot.read("target", "Empty.xml", optional=True) is None
    with pytest.raises(editor.Rejected, match="absent"):
        snapshot.read("target", "Empty.xml")
    assert snapshot.blobs["target", "Empty.xml"] == b""
    snapshot.stage("Existing.xml", original)
    snapshot.stage("Empty.xml", b"")
    snapshot.stage("Forms/New/Ext/Form.xml", None)
    assert snapshot.writes == {}
    snapshot.unchanged()
    assert contents(tmp_path) == before
    assert not (tmp_path / "Forms").exists()


def test_directory_overlay_and_missing_directory_preconditions(tmp_path):
    (tmp_path / "Keep.xml").write_bytes(b"keep")
    (tmp_path / "Remove.xml").write_bytes(b"remove")
    snapshot = editor.Snapshot(tmp_path)
    snapshot.stage("Remove.xml", None)
    snapshot.stage("New/Forms/Form.xml", b"form")
    assert snapshot.list_directory("target") == {"Keep.xml": "file", "New": "directory"}
    assert snapshot.list_directory("target", "New") == {"Forms": "directory"}
    assert snapshot.list_directory("target", "New/Forms") == {"Form.xml": "file"}
    assert snapshot.enumerations["target", "New"] is None
    assert snapshot.enumerations["target", ""] == {"Keep.xml": "file", "Remove.xml": "file"}
    snapshot.unchanged()
    (tmp_path / "New").mkdir()
    with pytest.raises(editor.Rejected, match="directory changed"):
        snapshot.unchanged()


def test_cached_absence_does_not_satisfy_required_read(tmp_path):
    snapshot = editor.Snapshot(tmp_path)
    assert snapshot.read("target", "missing", optional=True) is None
    with pytest.raises(editor.Rejected, match="absent"):
        snapshot.read("target", "missing")
    assert snapshot.list_directory("target", "missing-dir", optional=True) is None
    with pytest.raises(editor.Rejected, match="absent"):
        snapshot.list_directory("target", "missing-dir")
    (tmp_path / "missing").write_bytes(b"new")
    with pytest.raises(editor.Rejected, match="Source changed"):
        snapshot.unchanged()


def test_source_roots_are_explicit_deduplicated_and_read_only(tmp_path):
    target, source = tmp_path / "target", tmp_path / "source"
    target.mkdir()
    source.mkdir()
    (source / "Object.xml").write_bytes(b"source")
    snapshot = editor.Snapshot(target)
    alias = snapshot.source_root(source)
    assert snapshot.source_root(source) == alias
    assert snapshot.source_root(target) == "target"
    assert snapshot.read(alias, "Object.xml") == b"source"
    snapshot.stage("Object.xml", b"target")
    assert snapshot.read(alias, "Object.xml") == b"source"
    assert snapshot.read("target", "Object.xml") == b"target"
    assert not (target / "Object.xml").exists()
    assert (source / "Object.xml").read_bytes() == b"source"
    snapshot.unchanged()
    (source / "Object.xml").write_bytes(b"changed")
    with pytest.raises(editor.Rejected, match="Source changed"):
        snapshot.unchanged()


def test_unrelated_files_only_invalidate_observed_listings(tmp_path):
    (tmp_path / "Object.xml").write_bytes(b"object")
    (tmp_path / "Other").mkdir()
    exact = editor.Snapshot(tmp_path)
    listed = editor.Snapshot(tmp_path)
    exact.read("target", "Object.xml")
    listed.list_directory("target")
    (tmp_path / "Other" / "new.xml").write_bytes(b"unrelated")
    exact.unchanged()
    listed.unchanged()
    (tmp_path / "New.xml").write_bytes(b"new root registration")
    exact.unchanged()
    with pytest.raises(editor.Rejected, match="directory changed"):
        listed.unchanged()


@pytest.mark.parametrize("path", ["../out.xml", "/out.xml", "dir/../out.xml", "file:stream", "NUL"])
def test_unsafe_candidate_paths_are_rejected(tmp_path, path):
    snapshot = editor.Snapshot(tmp_path)
    with pytest.raises(editor.Rejected):
        snapshot.stage(path, b"data")
    assert snapshot.writes == {} and contents(tmp_path) == {}


def test_virtual_file_cannot_be_a_parent_directory(tmp_path):
    snapshot = editor.Snapshot(tmp_path)
    snapshot.stage("New", b"file")
    with pytest.raises(editor.Rejected, match="blocks a directory"):
        snapshot.stage("New/Form.xml", b"child")
    with pytest.raises(editor.Rejected, match="blocks a directory"):
        snapshot.list_directory("target", "New")
    snapshot.stage("New", None)
    snapshot.stage("New/Form.xml", b"child")
    with pytest.raises(editor.Rejected, match="blocks a file"):
        snapshot.stage("New", b"file")


def test_limits_cover_candidates_and_existing_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(editor, "FILE_LIMIT", 10)
    monkeypatch.setattr(editor, "CLOSURE_LIMIT", 15)
    (tmp_path / "Existing").write_bytes(b"1234567890")
    snapshot = editor.Snapshot(tmp_path)
    with pytest.raises(editor.Rejected, match="Candidate size"):
        snapshot.stage("New", b"12345678901")
    with pytest.raises(editor.Rejected, match="Closure size"):
        snapshot.stage("Existing", b"123456")
    assert (tmp_path / "Existing").read_bytes() == b"1234567890"


def test_same_file_cannot_have_two_case_spellings(tmp_path):
    snapshot = editor.Snapshot(tmp_path)
    snapshot.stage("New.xml", b"data")
    with pytest.raises(editor.Rejected, match="Case-ambiguous"):
        snapshot.stage("new.xml", b"different")


@pytest.mark.skipif(editor.os.name != "nt", reason="Windows volume restrictions")
@pytest.mark.parametrize("drive,filesystem,readable", [(4, "NTFS", True), (3, "FAT32", True), (3, "NTFS", False)])
def test_windows_volume_rejected_before_snapshot(tmp_path, monkeypatch, drive, filesystem, readable):
    import ctypes
    from unittest.mock import Mock

    kernel = Mock()
    kernel.GetDriveTypeW.return_value = drive

    def information(*args):
        args[6].value = filesystem
        return readable

    kernel.GetVolumeInformationW.side_effect = information
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: kernel)
    with pytest.raises(editor.Rejected):
        editor.Snapshot(tmp_path)
    assert list(tmp_path.iterdir()) == []
