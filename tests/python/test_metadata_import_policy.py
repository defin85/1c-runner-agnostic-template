"""Import sync keeps the retired metadata editors out of the vendored pack (pytest)."""

from scripts.python import imported_skills

RETIRED = {
    "meta-info",
    "meta-compile",
    "meta-edit",
    "meta-remove",
    "meta-validate",
    "form-info",
    "form-add",
    "form-compile",
    "form-edit",
    "form-remove",
    "form-validate",
    "cfe-borrow",
}
RETAINED = {
    "template-add",
    "template-remove",
    "mxl-info",
    "mxl-compile",
    "mxl-decompile",
    "mxl-validate",
    "form-patterns",
    "cf-edit",
    "epf-build",
}


def test_retired_set_is_the_recorded_editor_list():
    assert imported_skills.RETIRED_METADATA_SKILLS == RETIRED
    assert "form-patterns" not in imported_skills.RETIRED_METADATA_SKILLS


def test_copy_excludes_retired_editors_and_preserves_other_skills(tmp_path, monkeypatch):
    source = tmp_path / "upstream"
    skills = source / ".claude" / "skills"
    skills.mkdir(parents=True)
    (source / "LICENSE").write_text("test license", encoding="utf-8")
    for name in RETIRED | RETAINED:
        folder = skills / name
        folder.mkdir()
        (folder / "SKILL.md").write_text(f"---\nname: {name}\n---\n{name}\n", encoding="utf-8")
    destination = tmp_path / "vendor"
    monkeypatch.setattr(imported_skills, "IMPORT_ROOT", destination)
    monkeypatch.setattr(imported_skills, "IMPORT_SKILLS_ROOT", destination / "skills")
    monkeypatch.setattr(imported_skills, "IMPORT_LICENSE", destination / "LICENSE")

    for _ in range(2):
        names = imported_skills._copy_skill_tree(source)
        assert set(names) == RETAINED
        assert {item.name for item in (destination / "skills").iterdir()} == RETAINED
        assert {item["name"] for item in imported_skills._build_skill_manifest(names)} == RETAINED


def test_sync_removes_retired_generated_surfaces(tmp_path, monkeypatch):
    for root in (".agents", ".claude"):
        for name in ("meta-edit", "cfe-borrow", "form-patterns"):
            folder = tmp_path / root / "skills" / name
            folder.mkdir(parents=True)
            (folder / "SKILL.md").write_text(name, encoding="utf-8")
    monkeypatch.setattr(imported_skills, "repo_path", lambda *parts: tmp_path.joinpath(*parts))

    imported_skills._remove_previous_generated_surfaces([])

    for root in (".agents", ".claude"):
        assert sorted(item.name for item in (tmp_path / root / "skills").iterdir()) == ["form-patterns"]


def test_stale_manifest_entry_of_retired_editor_is_not_dispatched(tmp_path, monkeypatch):
    manifest = tmp_path / "imported-skills.json"
    manifest.write_text(
        '{"skills": [{"name": "meta-edit", "runtime_kind": "python", "helper_path": "skills/meta-edit/x.py"}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(imported_skills, "IMPORT_MANIFEST", manifest)
    assert imported_skills._skill_entries() == []
