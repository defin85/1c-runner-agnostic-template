"""Multi-file publication faults on disposable trees, never application data."""

from tests.python.metadata_test_support import present  # noqa: I001 — runs first: skips the module without pytest, lxml, jsonschema
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.python import metadata as editor, metadata_ops
from tests.python.test_metadata_object_ops import rename_owner


def removal_plan(tmp_path, operation, keep_files=False):
    root, logical = rename_owner(tmp_path, "Catalog")
    setup = {
        "schemaVersion": 1,
        "operations": [
            {"op": "form.create", "target": logical, "parameters": {"name": "Удаляемая", "setDefault": True}}
        ],
    }
    editor.apply(root, None, editor.plan_make(editor.Snapshot(root), setup))
    module = root / "Catalogs/Владелец/Forms/Удаляемая/Ext/Form/Module.bsl"
    module.write_text("КодУдаляемойФормы();", encoding="utf-8")
    payload = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": operation,
                "target": logical + ".Form.Удаляемая" if operation == "form.remove" else logical,
                "parameters": {} if operation == "form.remove" else {"keepFiles": keep_files},
            }
        ],
    }
    return root, module, editor.plan_make(editor.Snapshot(root), payload)


@pytest.mark.parametrize(
    "operation,keep_files", [("object.remove", False), ("object.remove", True), ("form.remove", False)]
)
@pytest.mark.parametrize("change", ["modify", "add"])
def test_real_removal_stale_excluded_subtree(tmp_path, operation, keep_files, change):
    root, module, plan = removal_plan(tmp_path, operation, keep_files)
    (module if change == "modify" else module.with_name("New.bsl")).write_bytes(b"changed")
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected):
        editor.apply(root, None, plan)
    assert before == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert not journal_path(root).exists()


@pytest.mark.parametrize("operation", ["object.remove", "form.remove"])
@pytest.mark.parametrize("rollback_fails", [False, True])
def test_real_removal_second_delete_failure_and_recovery(tmp_path, monkeypatch, operation, rollback_fails):
    root, _, plan = removal_plan(tmp_path, operation)
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    deletions = [root / item["path"] for item in plan["writes"] if not item["after"]["present"]]
    assert len(deletions) >= 2
    unlink, put = Path.unlink, editor._replace_bytes
    interrupted = False

    def fail_delete(path, *args, **kwargs):
        nonlocal interrupted
        unlink(path, *args, **kwargs)
        if path == deletions[1] and not interrupted:
            interrupted = True
            raise OSError("injected second deletion failure")

    def fail_restore(path, *args):
        if rollback_fails and interrupted and path in deletions:
            raise OSError("injected rollback failure")
        return put(path, *args)

    monkeypatch.setattr(Path, "unlink", fail_delete)
    monkeypatch.setattr(editor, "_replace_bytes", fail_restore)
    with pytest.raises(OSError):
        editor.apply(root, None, plan)
    assert interrupted
    assert journal_path(root).exists() == rollback_fails
    if not rollback_fails:
        assert before == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    monkeypatch.setattr(Path, "unlink", unlink)
    monkeypatch.setattr(editor, "_replace_bytes", put)
    assert editor.apply(root, None, plan) == "applied"
    assert editor.apply(root, None, plan) == "already-applied"
    assert all(not p.exists() for p in deletions)
    assert not journal_path(root).exists()


@pytest.fixture
def publication(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    (root / "Existing.xml").write_bytes(b"original")
    (root / "Old.xml").write_bytes(b"delete me")
    (root / "ReadOnly").write_bytes(b"untouched")

    def changes(snapshot, _operation):
        snapshot.list_directory("target")
        snapshot.read("target", "ReadOnly")
        snapshot.stage("A/Nested/New.xml", b"created")
        snapshot.stage("Existing.xml", b"replaced")
        snapshot.stage("Old.xml", None)

    monkeypatch.setattr(metadata_ops, "HANDLERS", {"object.borrow": changes})
    plan = editor.plan_make(
        editor.Snapshot(root),
        {
            "schemaVersion": 1,
            "operations": [{"op": "object.borrow", "target": "Catalog.Demo", "parameters": {"baseRoot": "unused"}}],
        },
    )
    return root, plan


def journal_path(root):
    return root.with_name("." + root.name + ".metadata-state") / "journal.json"


def assert_original(root):
    assert (root / "Existing.xml").read_bytes() == b"original"
    assert (root / "Old.xml").read_bytes() == b"delete me"
    assert (root / "ReadOnly").read_bytes() == b"untouched"
    assert not (root / "A").exists()
    assert sorted(path.name for path in root.iterdir()) == ["Existing.xml", "Old.xml", "ReadOnly"]


def test_publish_and_repeat(publication, monkeypatch):
    root, plan = publication
    assert editor.apply(root, None, plan) == "applied"
    assert (root / "A/Nested/New.xml").read_bytes() == b"created"
    assert (root / "Existing.xml").read_bytes() == b"replaced"
    assert not (root / "Old.xml").exists()
    assert not journal_path(root).exists()

    def no_replace(*_args):
        raise AssertionError("Already-applied must not rewrite files")

    monkeypatch.setattr(editor.os, "replace", no_replace)
    assert editor.apply(root, None, plan) == "already-applied"


def test_journal_cannot_claim_existing_empty_parent(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    (root / "ExistingDir").mkdir()
    monkeypatch.setattr(
        metadata_ops,
        "HANDLERS",
        {"object.borrow": lambda snapshot, operation: snapshot.stage("ExistingDir/New.xml", b"new")},
    )
    plan = editor.plan_make(
        editor.Snapshot(root),
        {
            "schemaVersion": 1,
            "operations": [{"op": "object.borrow", "target": "Catalog.Demo", "parameters": {"baseRoot": "unused"}}],
        },
    )
    journal = editor._journal_data(root, plan)
    journal["createdDirectories"] = ["ExistingDir"]
    with editor.file_lock(root):
        journal_path(root).write_text(json.dumps(journal), encoding="utf-8")
    (root / "ExistingDir/New.xml").write_bytes(b"new")
    with pytest.raises(editor.Rejected):
        editor.apply(root, None, plan)
    assert (root / "ExistingDir/New.xml").read_bytes() == b"new"
    assert journal_path(root).exists()


@pytest.mark.parametrize("failure", ["create", "replace", "delete"])
def test_handled_failure_restores_all_own_writes(publication, monkeypatch, failure):
    root, plan = publication
    replace, unlink = editor._replace_bytes, Path.unlink
    pending = True

    def fail_replace(path, *args):
        nonlocal pending
        replace(path, *args)
        if pending and path == root / ("A/Nested/New.xml" if failure == "create" else "Existing.xml"):
            pending = False
            if failure != "delete":
                raise OSError("injected after replacement")

    def fail_unlink(path, *args, **kwargs):
        nonlocal pending
        unlink(path, *args, **kwargs)
        if pending and failure == "delete" and path == root / "Old.xml":
            pending = False
            raise OSError("injected after deletion")

    monkeypatch.setattr(editor, "_replace_bytes", fail_replace)
    if failure == "delete":
        monkeypatch.setattr(editor, "_replace_bytes", replace)
    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(OSError):
        editor.apply(root, None, plan)
    assert_original(root)
    assert not journal_path(root).exists()
    assert editor.apply(root, None, plan) == "applied"


def test_failed_rollback_retains_journal_for_same_plan(publication, monkeypatch):
    root, plan = publication
    original = editor._replace_bytes

    def fail(path, data, *args):
        if path == root / "Existing.xml":
            if data == b"replaced":
                original(path, data, *args)
            raise OSError("publication or rollback failed")
        return original(path, data, *args)

    monkeypatch.setattr(editor, "_replace_bytes", fail)
    with pytest.raises(OSError):
        editor.apply(root, None, plan)
    assert journal_path(root).is_file()
    monkeypatch.setattr(editor, "_replace_bytes", original)
    assert editor.apply(root, None, plan) == "applied"
    assert not journal_path(root).exists()


def test_foreign_file_blocks_entire_rollback(publication, monkeypatch):
    root, plan = publication
    original = editor._replace_bytes

    def fail(path, *args):
        original(path, *args)
        if path == root / "Existing.xml":
            (root / "A/Nested/New.xml").write_bytes(b"foreign edit")
            raise OSError("interrupted")

    monkeypatch.setattr(editor, "_replace_bytes", fail)
    with pytest.raises(editor.Rejected, match="Foreign file"):
        editor.apply(root, None, plan)
    assert (root / "A/Nested/New.xml").read_bytes() == b"foreign edit"
    assert (root / "Existing.xml").read_bytes() == b"replaced"
    assert journal_path(root).exists()
    monkeypatch.setattr(editor, "_replace_bytes", original)
    with pytest.raises(editor.Rejected):
        editor.apply(root, None, plan)
    assert (root / "Existing.xml").read_bytes() == b"replaced"


def test_foreign_contents_in_created_directory_are_not_removed(publication, monkeypatch):
    root, plan = publication
    original = editor._replace_bytes

    def fail(path, *args):
        original(path, *args)
        (root / "A/foreign.txt").write_bytes(b"keep")
        raise OSError("interrupted")

    monkeypatch.setattr(editor, "_replace_bytes", fail)
    with pytest.raises(editor.Rejected, match="Foreign contents"):
        editor.apply(root, None, plan)
    assert (root / "A/foreign.txt").read_bytes() == b"keep"
    assert journal_path(root).exists()


@pytest.mark.parametrize("content", ["{}", '{"schemaVersion":1,"schemaVersion":1}', "not json"])
def test_corrupt_journal_blocks_without_source_writes(publication, content):
    root, plan = publication
    path = journal_path(root)
    path.parent.mkdir()
    path.write_text(content, encoding="utf-8")
    with pytest.raises(editor.Rejected):
        editor.apply(root, None, plan)
    assert_original(root)
    assert path.read_text(encoding="utf-8") == content


def test_mixed_state_without_journal_is_not_adopted(publication):
    root, plan = publication
    (root / "Existing.xml").write_bytes(b"replaced")
    with pytest.raises(editor.Rejected):
        editor.apply(root, None, plan)
    assert not journal_path(root).exists()
    assert not (root / "A").exists()


def test_other_plan_cannot_take_over_recovery(publication):
    root, plan = publication
    journal = editor._journal_data(root, plan)
    path = journal_path(root)
    path.parent.mkdir()
    journal["planHash"] = "0" * 64
    path.write_text(json.dumps(journal), encoding="utf-8")
    with pytest.raises(editor.Rejected, match="another plan"):
        editor.apply(root, None, plan)
    assert_original(root)


def test_root_lock_is_nonblocking_across_processes(publication):
    root, plan = publication
    script = (
        "import sys,time; from pathlib import Path; from scripts.python.metadata import file_lock\n"
        "with file_lock(Path(sys.argv[1])):\n"
        ' print("locked",flush=True)\n time.sleep(20)\n'
    )
    process = subprocess.Popen(
        [sys.executable, "-c", script, str(root)],
        cwd=editor.PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert present(process.stdout).readline().strip() == "locked"
        assert process.poll() is None
        with pytest.raises(editor.Rejected, match="Lock conflict"):
            editor.apply(root, None, plan)
        assert_original(root)
    finally:
        process.terminate()
        process.communicate(timeout=10)


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing semantics")
def test_windows_sharing_violation_rolls_back_previous_create(publication):
    import ctypes
    from ctypes import wintypes

    root, plan = publication
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(root / "Existing.xml"), 0x80000000, 1, None, 3, 0x80, None)
    assert handle != ctypes.c_void_p(-1).value
    try:
        with pytest.raises(OSError):
            editor.apply(root, None, plan)
        assert_original(root)
        assert not journal_path(root).exists()
    finally:
        kernel.CloseHandle(handle)


@pytest.mark.parametrize("crash", ["delete", "rollback-before", "rollback-after"])
def test_process_crash_after_delete_and_during_rollback(publication, tmp_path, crash):
    root, plan = publication
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    program = """import json,os,sys
from pathlib import Path
from scripts.python import metadata as m, metadata_ops as ops
root=Path(sys.argv[1]); plan=json.loads(Path(sys.argv[2]).read_text()); crash=sys.argv[3]
def changes(snapshot,operation):
 snapshot.list_directory('target'); snapshot.read('target','ReadOnly')
 snapshot.stage('A/Nested/New.xml',b'created'); snapshot.stage('Existing.xml',b'replaced'); snapshot.stage('Old.xml',None)
ops.HANDLERS={'object.borrow':changes}
unlink=Path.unlink; put=m._replace_bytes
def interrupt(path,*args,**kwargs):
 unlink(path,*args,**kwargs)
 if path==root/'Old.xml':
  if crash=='delete': os._exit(81)
  raise OSError('trigger rollback')
def rollback_crash(path,data,*args):
 if path==root/'Old.xml' and data==b'delete me':
  if crash=='rollback-after': put(path,data,*args)
  os._exit(81)
 return put(path,data,*args)
Path.unlink=interrupt; m._replace_bytes=rollback_crash
m.apply(root,None,plan)
"""
    process = subprocess.run(
        [sys.executable, "-c", program, str(root), str(plan_path), crash],
        cwd=editor.PROJECT_ROOT,
        capture_output=True,
        timeout=30,
    )
    assert process.returncode == 81, process.stderr
    assert journal_path(root).exists()
    expected = "already-applied" if crash in ("delete", "rollback-before") else "applied"
    assert editor.apply(root, None, plan) == expected
    assert editor.verify_plan(root, plan)[0] == "after"
    assert not journal_path(root).exists()


def test_temporary_sibling_name_stays_short_for_windows_paths(tmp_path):
    # Windows without LongPathsEnabled rejects paths over 260 characters, the temporary sibling included.
    from scripts.python import metadata as engine

    temporary = engine._temporary(tmp_path, "Catalogs/Товары/Forms/ФормаЭлемента/Ext/Form.xml", "a" * 64)
    assert temporary.parent == tmp_path / "Catalogs/Товары/Forms/ФормаЭлемента/Ext"
    assert temporary.name.startswith(".metadata-") and len(temporary.name) <= 30
    assert temporary == engine._temporary(tmp_path, "Catalogs/Товары/Forms/ФормаЭлемента/Ext/Form.xml", "a" * 64)
