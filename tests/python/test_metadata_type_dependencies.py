"""Direct type dependencies are explicit and participate in plan replay."""

from tests.python.metadata_test_support import present  # noqa: I001 — runs first: skips the module without pytest, lxml, jsonschema
import json
import shutil
from pathlib import Path

import lxml.etree as etree
import pytest

from scripts.python import metadata as editor, metadata_create


def create(kind, name, **fields):
    return {
        "op": "object.create",
        "target": f"{kind}.{name}",
        "parameters": {"definition": {"type": kind, "name": name, **fields}},
    }


@pytest.mark.parametrize(
    "kind,family",
    [("Catalog", "CatalogRef"), ("DefinedType", "DefinedType"), ("ChartOfCharacteristicTypes", "Characteristic")],
)
def test_missing_dependency_is_public_and_explicit(tmp_path, capsys, kind, family):
    root = tmp_path / "private-path"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", root)
    operation = create("Catalog", "Правила", attributes=[{"name": "Аналитика", "type": f"{family}.Значения"}])
    request = {"schemaVersion": 1, "operations": [operation]}
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    request_path, plan_path = tmp_path / "request.json", tmp_path / "plan.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    assert editor.main(["plan", "--root", str(root), "--request", str(request_path), "--out", str(plan_path)]) == 3
    output = capsys.readouterr().out
    message = json.loads(output)["error"]["message"]
    assert "Правила.Аналитика" in message and f"{kind}.Значения" in message
    assert "object.borrow" in message and "object.create" in message
    assert "private-path" not in output and len(output.encode("utf-8")) < 8192
    assert not plan_path.exists()
    assert before == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}

    # Dependency declared later in the same request is sufficient.
    request["operations"].append(create(kind, "Значения"))
    plan = editor.plan_make(editor.Snapshot(root), request)
    assert editor.apply(root, None, plan) == "applied"
    assert editor.apply(root, None, plan) == "already-applied"


def test_dependency_change_invalidates_plan(tmp_path):
    root = tmp_path / "extension"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", root)
    dependency = {"schemaVersion": 1, "operations": [create("Catalog", "Значения")]}
    editor.apply(root, None, editor.plan_make(editor.Snapshot(root), dependency))
    request = {
        "schemaVersion": 1,
        "operations": [create("Catalog", "Правила", attributes=[{"name": "Аналитика", "type": "CatalogRef.Значения"}])],
    }
    plan = editor.plan_make(editor.Snapshot(root), request)
    path = root / "Catalogs/Значения.xml"
    path.write_bytes(path.read_bytes() + b"\n")
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    with pytest.raises(editor.Rejected):
        editor.apply(root, None, plan)
    assert before == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_existing_unresolved_type_is_preserved_only_when_unchanged(tmp_path):
    root = tmp_path / "extension"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", root)
    name = "ИсторическийОбъект"
    config_path = root / "Configuration.xml"
    config_bytes = config_path.read_bytes()
    config = editor.metadata(config_bytes, "Configuration")
    etree.SubElement(config.find("m:ChildObjects", editor.NS), f"{{{editor.MD}}}Catalog").text = name
    config_path.write_bytes(editor.serialize_like(config.getparent(), config_bytes))
    (root / "Catalogs").mkdir()
    object_data = metadata_create.render_object(
        {
            "type": "Catalog",
            "name": name,
            "attributes": [{"name": "СтараяСсылка", "type": "CatalogRef.ИсторическаяБаза"}],
        },
        editor.identity(config),
        {},
    )
    object_tree = editor.xml_read(object_data, f"{{{editor.MD}}}MetaDataObject")
    typed = object_tree.find("m:Catalog/m:ChildObjects/m:Attribute/m:Properties/m:Type/v8:Type", editor.NS)
    parent = typed.getparent()
    local_type = etree.Element(
        f"{{{editor.V8}}}Type", nsmap={"v8": editor.V8, "cfg": "http://v8.1c.ru/8.1/data/enterprise/current-config"}
    )
    local_type.text = typed.text
    parent.replace(typed, local_type)
    owner = object_tree.find("m:Catalog", editor.NS)
    local_root = etree.Element(
        f"{{{editor.MD}}}MetaDataObject",
        nsmap={None: editor.MD, "xr": "http://v8.1c.ru/8.3/xcf/readable"},
        version=object_tree.get("version"),
    )
    local_root.append(owner)
    assert "v8" not in local_root.nsmap and local_type.nsmap["v8"] == editor.V8
    (root / f"Catalogs/{name}.xml").write_bytes(etree.tostring(local_root, encoding="UTF-8", xml_declaration=True))
    edit = {
        "schemaVersion": 1,
        "operations": [
            {
                "op": "object.edit",
                "target": f"Catalog.{name}",
                "parameters": {
                    "definition": {
                        "add": {"attributes": [{"name": "НоваяСсылка", "type": "CatalogRef.ИсторическаяБаза"}]}
                    }
                },
            }
        ],
    }
    before = {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}

    with pytest.raises(editor.TypeDependencyRejected, match="НоваяСсылка.*Catalog.ИсторическаяБаза"):
        editor.plan_make(editor.Snapshot(root), edit)
    assert {
        path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()
    } == before

    edit["operations"][0]["parameters"]["definition"] = {
        "modify": {"properties": {"Synonym": "Переименованное представление"}}
    }
    snapshot = editor.Snapshot(root)
    plan = editor.plan_make(snapshot, edit)
    assert [entry["path"] for entry in plan["writes"]] == [f"Catalogs/{name}.xml"]
    unchanged = editor.metadata(present(snapshot.writes[f"Catalogs/{name}.xml"]), "Catalog")
    assert (
        unchanged.findtext("m:ChildObjects/m:Attribute/m:Properties/m:Type/v8:Type", namespaces=editor.NS)
        == "cfg:CatalogRef.ИсторическаяБаза"
    )

    edit["operations"][0]["parameters"]["definition"] = {
        "modify": {"attributes": {"СтараяСсылка": {"type": "CatalogRef.ДругаяИсторическаяБаза"}}}
    }
    before = {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    with pytest.raises(editor.TypeDependencyRejected, match="СтараяСсылка.*Catalog.ДругаяИсторическаяБаза"):
        editor.plan_make(editor.Snapshot(root), edit)
    assert {
        path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()
    } == before


def test_form_dependency_is_checked_after_all_operations(tmp_path):
    root = tmp_path / "extension"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", root)
    request = {
        "schemaVersion": 1,
        "operations": [
            create("Catalog", "Правила"),
            {
                "op": "form.create",
                "target": "Catalog.Правила",
                "parameters": {"name": "ФормаЭлемента", "purpose": "Object", "setDefault": True},
            },
            {
                "op": "form.compile",
                "target": "Catalog.Правила.Form.ФормаЭлемента",
                "parameters": {"definition": {"attributes": [{"name": "Аналитика", "type": "CatalogRef.Значения"}]}},
            },
        ],
    }
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    with pytest.raises(editor.TypeDependencyRejected, match="Аналитика.*Catalog.Значения"):
        editor.plan_make(editor.Snapshot(root), request)
    assert before == {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    request["operations"].append(create("Catalog", "Значения"))
    assert editor.plan_make(editor.Snapshot(root), request)["checks"]["structure"] == "passed"


@pytest.mark.parametrize("typename", ["Unknown", "unknown:Value", "cfg:Unknown.Value"])
def test_unknown_form_type_is_rejected(tmp_path, typename):
    root = tmp_path / "extension"
    shutil.copytree(Path(__file__).parents[1] / "fixtures/managed-form-cli/own-cfe", root)
    request = {
        "schemaVersion": 1,
        "operations": [
            create("Catalog", "Правила"),
            {"op": "form.create", "target": "Catalog.Правила", "parameters": {"name": "ФормаЭлемента"}},
            {
                "op": "form.compile",
                "target": "Catalog.Правила.Form.ФормаЭлемента",
                "parameters": {"definition": {"attributes": [{"name": "Аналитика", "type": typename}]}},
            },
        ],
    }
    with pytest.raises(editor.Rejected):
        editor.plan_make(editor.Snapshot(root), request)
