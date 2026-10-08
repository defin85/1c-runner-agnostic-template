"""Plan/replay tests exercise the engine; subject operations are tested separately."""

import tests.python.metadata_test_support  # noqa: F401, I001 — runs first: skips the module without pytest, lxml, jsonschema
import copy
import json
import pytest

from scripts.python import metadata as editor, metadata_ops


@pytest.fixture
def subject_functions(monkeypatch):
    monkeypatch.setattr(metadata_ops, "operation_context", lambda snapshot, operation: None)

    # Narrow deterministic stand-ins let these tests isolate plan/preimage
    # security from the separate XML borrow/edit acceptance scenarios.
    def create(snapshot, operation):
        snapshot.list_directory("target")
        snapshot.read("target", "ReadOnly", optional=True)
        name = operation["parameters"]["definition"]["name"]
        snapshot.stage(f"{name}.xml", b"created\n")

    def edit(snapshot, operation):
        name = operation["target"].split(".")[1]
        previous = snapshot.read("target", f"{name}.xml")
        snapshot.stage(f"{name}.xml", previous + b"edited\n")

    def remove(snapshot, operation):
        name = operation["target"].split(".")[1]
        snapshot.stage(f"{name}.xml", None)

    monkeypatch.setattr(
        metadata_ops, "HANDLERS", {"object.create": create, "object.edit": edit, "object.remove": remove}
    )


def request():
    return {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.create",
                "target": "Catalog.New",
                "parameters": {"definition": {"type": "Catalog", "name": "New"}},
            },
            {
                "op": "object.edit",
                "target": "Catalog.New",
                "parameters": {"operation": "add-attribute", "value": "Flag: Boolean"},
            },
            {"op": "object.remove", "target": "Catalog.Old", "parameters": {}},
        ],
    }


def sources(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "Old.xml").write_bytes(b"old\r\n")
    (root / "ReadOnly").write_bytes(b"keep")
    return root


def publish_for_test(root, plan, side="after"):
    # Only test-owned exact paths are touched, never a user source tree.
    for item in plan["writes"]:
        target = root / item["path"]
        value = editor.state_bytes(item[side])
        if value is None:
            target.unlink(missing_ok=True)
        else:
            target.write_bytes(value)


def test_plan_replays_before_and_after_without_reapplying_add(subject_functions, tmp_path):
    root = sources(tmp_path)
    plan = editor.plan_make(editor.Snapshot(root), request())
    assert not (root / "New.xml").exists()
    assert (root / "Old.xml").read_bytes() == b"old\r\n"
    assert plan == editor.plan_make(editor.Snapshot(root), request())
    assert plan["request"]["operations"][1]["parameters"]["definition"]["add"]["attributes"] == [
        {"name": "Flag", "type": "Boolean"}
    ]
    assert editor.verify_plan(root, plan)[0] == "before"
    publish_for_test(root, plan)
    assert (root / "New.xml").read_bytes() == b"created\nedited\n"
    assert editor.verify_plan(root, plan)[0] == "after"
    assert (root / "New.xml").read_bytes() == b"created\nedited\n"


def test_mixed_foreign_and_readonly_changes_conflict(subject_functions, tmp_path):
    root = sources(tmp_path)
    plan = editor.plan_make(editor.Snapshot(root), request())
    (root / "New.xml").write_bytes(b"created\nedited\n")
    with pytest.raises(editor.Rejected):
        editor.verify_plan(root, plan)
    publish_for_test(root, plan)
    (root / "ReadOnly").write_bytes(b"changed")
    with pytest.raises(editor.Rejected):
        editor.verify_plan(root, plan)
    (root / "ReadOnly").write_bytes(b"keep")
    (root / "New.xml").write_bytes(b"foreign")
    with pytest.raises(editor.Rejected):
        editor.verify_plan(root, plan)


@pytest.mark.parametrize("mutation", ["hash", "after", "extra-write", "request", "diff", "checks", "fingerprint"])
def test_plan_tampering_is_rejected(subject_functions, tmp_path, mutation):
    root = sources(tmp_path)
    plan = editor.plan_make(editor.Snapshot(root), request())
    if mutation == "hash":
        plan["writes"][0]["after"]["sha256"] = "0" * 64
    elif mutation == "after":
        plan["writes"][0]["after"] = editor.byte_state(b"forged but internally consistent")
    elif mutation == "extra-write":
        plan["writes"].append(
            {"path": "Unrelated.xml", "before": editor.byte_state(None), "after": editor.byte_state(b"forged")}
        )
    elif mutation == "request":
        plan["request"]["operations"][0]["target"] = "Catalog.Other"
    elif mutation == "diff":
        plan["diff"] = "forged"
    elif mutation == "checks":
        plan["checks"]["runtime"] = "passed"
    else:
        plan["engineFingerprint"] = "0" * 64
    with pytest.raises(editor.Rejected):
        editor.verify_plan(root, plan)
    assert not (root / "New.xml").exists()


def test_directory_changes_and_unobserved_file_content(subject_functions, tmp_path):
    root = sources(tmp_path)
    (root / "Unrelated").write_bytes(b"one")
    plan = editor.plan_make(editor.Snapshot(root), request())
    (root / "Unrelated").write_bytes(b"two")
    assert editor.verify_plan(root, plan)[0] == "before"
    (root / "Another").write_bytes(b"new name")
    with pytest.raises(editor.Rejected):
        editor.verify_plan(root, plan)


def test_plan_cli_does_not_overwrite_or_write_inside_source(subject_functions, tmp_path, capsys):
    root = sources(tmp_path)
    input_path = tmp_path / "request.json"
    input_path.write_text(json.dumps(request()), encoding="utf-8")
    out = tmp_path / "plan.json"
    args = ["plan", "--root", str(root), "--request", str(input_path), "--out", str(out)]
    assert editor.main(args) == 0
    original = out.read_bytes()
    assert editor.main(args) == 3
    assert out.read_bytes() == original
    assert editor.main([*args[:-1], str(root / "plan.json")]) == 3
    assert not (root / "plan.json").exists()
    assert len(capsys.readouterr().out.splitlines()) == 3


def test_size_limit_and_invalid_before_encoding(subject_functions, tmp_path, monkeypatch):
    root = sources(tmp_path)
    plan = editor.plan_make(editor.Snapshot(root), request())
    tampered = copy.deepcopy(plan)
    tampered["writes"][0]["before"]["present"] = True
    tampered["writes"][0]["before"]["sha256"] = "0" * 64
    tampered["writes"][0]["before"]["data"] = "not base64"
    with pytest.raises(editor.Rejected):
        editor.check_metadata_plan(tampered)
    monkeypatch.setattr(editor, "PLAN_LIMIT", 20)
    with pytest.raises(editor.Rejected, match="Plan size"):
        editor.plan_make(editor.Snapshot(root), request())


def test_empty_file_creation_and_bom_are_visible_in_diff():
    assert "absent -> 0 bytes" in editor.file_diff(None, b"", "Empty.xml")
    assert "UTF-8 BOM: True -> False" in editor.file_diff(b"\xef\xbb\xbftext", b"text", "Text.xml")


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e10000", "-1e10000"])
def test_json_rejects_nonfinite_numbers_including_exponent_overflow(tmp_path, number):
    path = tmp_path / "bad.json"
    path.write_text('{"value":' + number + "}", encoding="utf-8")
    with pytest.raises(editor.Rejected, match="Non-finite"):
        editor.json_read(path, editor.PLAN_LIMIT)
