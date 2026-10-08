"""template.* через metadata: разметка (E7), правка (E8) и локальная проверка (E10).

Проверяется поведение инструмента и структура XML внутри Template.xml;
платформенная загрузка макета здесь не доказывается.
"""

import tests.python.metadata_test_support  # noqa: F401, I001 — runs first: skips the module without pytest, lxml, jsonschema
import codecs
import difflib
import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from scripts.python import metadata, metadata_ops


FIXTURE = Path(__file__).parents[1] / "fixtures" / "metadata-template" / "config"
PRINT = "Catalog.Товары.Template.Печать"
PRINT_FILE = "Catalogs/Товары/Templates/Печать/Ext/Template.xml"
STUB = "Catalog.Товары.Template.Пустой"
BLANK = "CommonTemplate.Бланк"
BLANK_FILE = "CommonTemplates/Бланк/Ext/Template.xml"


@pytest.fixture
def root(tmp_path):
    target = tmp_path / "config"
    shutil.copytree(FIXTURE, target)
    return target


def run(capsys, *argv):
    code = metadata.main([str(item) for item in argv])
    out = capsys.readouterr().out
    assert len(out.splitlines()) == 1
    result = json.loads(out)
    Draft202012Validator(metadata_ops.RESULT_SCHEMA).validate(result)
    return code, result


def plan(capsys, root, operations, name="plan.json"):
    request = root.parent / ("request-" + name)
    request.write_text(json.dumps({"schemaVersion": 1, "operations": operations}, ensure_ascii=False), encoding="utf-8")
    out = root.parent / name
    code, result = run(capsys, "plan", "--root", root, "--request", request, "--out", out)
    return code, result, out


def apply(capsys, root, operations, name="plan.json"):
    code, result, out = plan(capsys, root, operations, name)
    assert code == 0, result
    code, applied = run(capsys, "apply", "--root", root, "--plan", out)
    assert code == 0 and applied["status"] == "applied", applied
    return result["changes"], out


def op(operation, target=PRINT, **parameters):
    return {"op": operation, "target": target, "parameters": parameters}


def inspect(capsys, root, target=PRINT):
    code, result = run(capsys, "inspect", "--root", root, "--object", target)
    assert code == 0, result
    return result["changes"]


def verify(capsys, root, target=PRINT):
    return run(capsys, "verify", "--root", root, "--object", target)


def changed_lines(before: bytes, after: bytes):
    old = before.decode("utf-8-sig").splitlines(keepends=True)
    new = after.decode("utf-8-sig").splitlines(keepends=True)
    return [line for line in difflib.ndiff(old, new) if line[:1] in "+-"]


def assert_designer_layout(data: bytes, eol=b"\r\n"):
    assert data.startswith(codecs.BOM_UTF8)
    assert not data.endswith(b"\n")
    body = data.replace(b"\r\n", b"")
    if eol == b"\r\n":
        # LF survives only inside the multi-line text value.
        assert body.count(b"\n") == 1
    else:
        assert b"\r" not in data


# ---------------------------------------------------------------- E7


def test_inspect_lists_areas_parameters_and_details(capsys, root):
    changes = inspect(capsys, root)
    assert changes["object"] == PRINT and changes["kind"] == "SpreadsheetDocument"
    assert changes["file"] == PRINT_FILE
    assert changes["checks"] == {"platform": "not-run", "runtime": "not-run"}
    markup = changes["markup"]
    assert markup["rows"] == 6 and markup["columns"] == 4
    assert markup["areas"] == [
        {"name": "Шапка", "type": "Rows", "beginRow": 1, "endRow": 3, "parameters": []},
        {"name": "Строка", "type": "Rows", "beginRow": 4, "endRow": 6, "parameters": ["Номер"]},
    ]
    assert markup["parameters"] == [{"row": 4, "column": 2, "name": "Номер", "detail": "Ссылка", "areas": ["Строка"]}]
    assert markup["templates"] == [] and markup["intersections"] == []
    assert "template.import-xlsx" in changes["supportedOperations"]


def test_inspect_of_common_template_and_empty_stub(capsys, root):
    assert inspect(capsys, root, BLANK)["markup"]["parameters"] == [
        {"row": 1, "column": 1, "name": "Дата", "areas": ["Шапка"]}
    ]
    stub = inspect(capsys, root, STUB)
    assert stub["format"] == "stub"
    assert stub["markup"] == {
        "rows": 0,
        "columns": 0,
        "areas": [],
        "parameters": [],
        "templates": [],
        "intersections": [],
    }


@pytest.mark.parametrize(
    "target,kind",
    [
        ("Catalog.Товары.Template.Схема", "DataCompositionSchema"),
        ("CommonTemplate.СхемаОбщая", "DataCompositionSchema"),
    ],
)
def test_other_template_kinds_are_rejected_with_their_kind(capsys, root, target, kind):
    code, result = run(capsys, "inspect", "--root", root, "--object", target)
    assert code == 2 and result["error"]["code"] == 2 and kind in result["error"]["message"]
    code, result, _ = plan(capsys, root, [op("template.set-area", target, name="А", beginRow=1)])
    assert code == 2 and kind in result["error"]["message"]


@pytest.mark.parametrize(
    "target",
    [
        "Catalog.Товары.Template.Лишний",
        "CommonTemplate.Нет",
        "Catalog.Нет.Template.Печать",
        "Document.Товары.Template.Печать",
    ],
)
def test_unregistered_templates_are_rejected(capsys, root, target):
    code, result = run(capsys, "inspect", "--root", root, "--object", target)
    assert code == 2, result
    code, result, _ = plan(capsys, root, [op("template.set-area", target, name="А", beginRow=1)])
    assert code == 2


def test_inspect_options_for_objects_do_not_apply_to_templates(capsys, root):
    code, _ = run(capsys, "inspect", "--root", root, "--object", PRINT, "--mode", "brief")
    assert code == 2


# ---------------------------------------------------------------- E8


def test_insert_rows_shifts_areas_merges_and_keeps_bytes(capsys, root):
    before = (root / PRINT_FILE).read_bytes()
    changes, plan_path = apply(capsys, root, [op("template.insert-rows", at=4, count=2)])
    after = (root / PRINT_FILE).read_bytes()
    assert_designer_layout(after)
    markup = inspect(capsys, root)["markup"]
    assert [(a["name"], a["beginRow"], a["endRow"]) for a in markup["areas"]] == [("Шапка", 1, 3), ("Строка", 6, 8)]
    assert markup["rows"] == 8
    assert markup["parameters"][0]["row"] == 6
    report = json.loads(plan_path.read_text(encoding="utf-8"))["operationReports"]
    assert report == [
        {
            "index": 1,
            "op": "template.insert-rows",
            "target": PRINT,
            "report": {
                "removedAreas": [],
                "removedMerges": 0,
                "removedDrawings": 0,
                "rows": 8,
                "inserted": {"at": 4, "count": 2},
            },
        }
    ]
    # Only indexes, height and the shifted coordinates change; the new rows copy
    # the formats of row 4 without the parameter fill, which needs one new
    # format record appended after the existing ones.
    diff = changed_lines(before, after)
    assert not [line for line in diff if line.startswith("-") and ("<font" in line or "format>" in line)]
    assert sum(1 for line in diff if line.startswith("+") and line.strip("+ \r\n\t") == "<format>") == 1
    assert sum(1 for line in diff if line.startswith("-")) == 5
    assert verify(capsys, root)[0] == 0


def test_delete_row_inside_merge_shrinks_merge_and_area(capsys, root):
    apply(capsys, root, [op("template.delete-rows", at=5)])
    data = (root / PRINT_FILE).read_bytes().decode("utf-8-sig")
    assert "<merge>\r\n\t\t<r>3</r>\r\n\t\t<c>1</c>\r\n\t\t<h>1</h>\r\n\t</merge>" in data
    markup = inspect(capsys, root)["markup"]
    assert [(a["name"], a["beginRow"], a["endRow"]) for a in markup["areas"]] == [("Шапка", 1, 3), ("Строка", 4, 5)]
    assert markup["rows"] == 5
    assert verify(capsys, root)[0] == 0


def test_repeated_plan_is_already_applied(capsys, root):
    _, plan_path = apply(capsys, root, [op("template.insert-columns", at=2)])
    code, result = run(capsys, "apply", "--root", root, "--plan", plan_path)
    assert code == 0 and result["status"] == "already-applied"


def test_plan_diff_names_only_the_template_file(capsys, root):
    code, result, plan_path = plan(capsys, root, [op("template.set-area", name="Подвал", beginRow=6)])
    assert code == 0
    stored = json.loads(plan_path.read_text(encoding="utf-8"))
    assert [entry["path"] for entry in stored["writes"]] == [PRINT_FILE]
    assert "<name>Подвал</name>" in stored["diff"]
    assert (root / PRINT_FILE).read_bytes() == (FIXTURE / PRINT_FILE).read_bytes()


def test_set_area_adds_and_replaces_in_place(capsys, root):
    apply(
        capsys,
        root,
        [
            op("template.set-area", name="Подвал", beginRow=6, beginColumn=1, endColumn=2),
            op("template.set-area", name="Шапка", beginRow=1, endRow=2),
        ],
        "p1.json",
    )
    areas = inspect(capsys, root)["markup"]["areas"]
    assert [(a["name"], a["type"], a["beginRow"], a["endRow"]) for a in areas] == [
        ("Шапка", "Rows", 1, 2),
        ("Строка", "Rows", 4, 6),
        ("Подвал", "Rectangle", 6, 6),
    ]
    data = (root / PRINT_FILE).read_bytes().decode("utf-8-sig")
    assert data.index("<name>Шапка</name>") < data.index("<name>Строка</name>") < data.index("<name>Подвал</name>")
    apply(capsys, root, [op("template.set-area", name="Подвал", remove=True)], "p2.json")
    assert [a["name"] for a in inspect(capsys, root)["markup"]["areas"]] == ["Шапка", "Строка"]
    code, result, _ = plan(capsys, root, [op("template.set-area", name="Подвал", remove=True)], "p3.json")
    assert code == 3


def test_set_parameter_template_and_text_cells(capsys, root):
    apply(
        capsys,
        root,
        [
            op("template.set-parameter", row=5, column=3, name="Сумма", detail="Ссылка"),
            op("template.set-parameter", row=2, column=1, template="Итого: [Всего]"),
            op("template.set-parameter", row=4, column=2, text="Номер"),
        ],
    )
    markup = inspect(capsys, root)["markup"]
    # The text cell keeps its detail parameter, as BslEdit does.
    assert markup["parameters"] == [
        {"row": 4, "column": 2, "name": "", "detail": "Ссылка", "areas": ["Строка"]},
        {"row": 5, "column": 3, "name": "Сумма", "detail": "Ссылка", "areas": ["Строка"]},
    ]
    assert markup["templates"] == [
        {"row": 2, "column": 1, "text": "Итого: [Всего]", "names": ["Всего"], "areas": ["Шапка"]}
    ]
    data = (root / PRINT_FILE).read_bytes()
    assert_designer_layout(data)
    assert verify(capsys, root)[0] == 0


def test_set_format_appends_font_and_format_without_renumbering(capsys, root):
    before = (root / PRINT_FILE).read_bytes().decode("utf-8-sig")
    apply(
        capsys,
        root,
        [
            op(
                "template.set-format",
                row=1,
                column=1,
                toColumn=2,
                font={"bold": True},
                backColor="#ffee00",
                border="Dotted",
            )
        ],
    )
    after = (root / PRINT_FILE).read_bytes().decode("utf-8-sig")
    tail = before[before.index("\t<line ") : before.index("</document>")]
    # Existing table records keep their order and bytes; new ones follow them.
    # Column 2 inherits no font, so its bold font starts from Arial 8 (as in BslEdit).
    assert after.count("<font faceName=") == 3 and after.count("\t<line ") == 2
    for record in tail.split("\r\n\t<"):
        assert record in after
    assert 'bold="true"' in after and "<backColor>#FFEE00</backColor>" in after
    assert verify(capsys, root)[0] == 0
    # Same format again reuses the records instead of adding duplicates.
    code, _, out = plan(
        capsys,
        root,
        [
            op(
                "template.set-format",
                row=1,
                column=1,
                toColumn=2,
                font={"bold": True},
                backColor="#ffee00",
                border="Dotted",
            )
        ],
        "again.json",
    )
    assert code == 0
    code, applied = run(capsys, "apply", "--root", root, "--plan", out)
    assert code == 0 and applied["status"] == "already-applied", applied
    assert (root / PRINT_FILE).read_bytes().decode("utf-8-sig") == after


def test_merge_cells_conflicts_and_unmerge(capsys, root):
    code, result, _ = plan(capsys, root, [op("template.merge-cells", row=1, column=2, columns=2)])
    assert code == 3
    apply(
        capsys,
        root,
        [
            op("template.merge-cells", row=6, column=3, rows=1, columns=2),
            op("template.merge-cells", row=1, column=1, unmerge=True),
        ],
    )
    data = (root / PRINT_FILE).read_bytes().decode("utf-8-sig")
    assert "<r>0</r>" not in data and "<merge>\r\n\t\t<r>5</r>\r\n\t\t<c>2</c>\r\n\t\t<w>1</w>" in data
    code, _, _ = plan(capsys, root, [op("template.merge-cells", row=1, column=1, unmerge=True)], "x.json")
    assert code == 3


def test_delete_columns_shrinks_merge_and_moves_cells(capsys, root):
    apply(capsys, root, [op("template.delete-columns", at=2)])
    data = (root / PRINT_FILE).read_bytes().decode("utf-8-sig")
    assert "<size>3</size>" in data
    assert "<merge>\r\n\t\t<r>0</r>\r\n\t\t<c>0</c>\r\n\t\t<w>1</w>" in data
    # The parameter cell in column 2 is deleted with its column and its merge.
    assert inspect(capsys, root)["markup"]["parameters"] == []
    assert "<h>2</h>" not in data


COLUMN_SETS = Path(__file__).parents[1] / "fixtures" / "metadata-template" / "column-sets" / "Template.xml"
SET_ID = "5d1b7f0e-3c2a-4b8e-9f61-2a7c4e0d9b13"
DEFAULT_MERGE = "<merge>\r\n\t\t<r>0</r>\r\n\t\t<c>{c}</c>\r\n\t\t<w>2</w>\r\n\t</merge>"
SET_MERGE = "<merge>\r\n\t\t<r>1</r>\r\n\t\t<c>{c}</c>\r\n\t\t<w>1</w>\r\n"


@pytest.fixture
def column_sets(root):
    """Печать is replaced by a layout with a second column set used by row 2 (as in ПФ_MXL_ИНВ19)."""
    shutil.copyfile(COLUMN_SETS, root / PRINT_FILE)
    return root


def test_insert_columns_moves_merges_of_their_row_set_only(capsys, column_sets):
    # A merge without columnsID belongs to the column set of its row.
    apply(capsys, column_sets, [op("template.insert-columns", at=1)])
    data = (column_sets / PRINT_FILE).read_bytes().decode("utf-8-sig")
    assert DEFAULT_MERGE.format(c=2) in data and SET_MERGE.format(c=0) in data
    assert verify(capsys, column_sets)[0] == 0
    apply(capsys, column_sets, [op("template.insert-columns", at=1, columnsId=SET_ID)], "set.json")
    data = (column_sets / PRINT_FILE).read_bytes().decode("utf-8-sig")
    assert DEFAULT_MERGE.format(c=2) in data and SET_MERGE.format(c=1) in data
    assert f"<id>{SET_ID}</id>\r\n\t\t<size>4</size>" in data
    assert verify(capsys, column_sets)[0] == 0


def test_delete_default_columns_keeps_merges_of_other_sets(capsys, column_sets):
    apply(capsys, column_sets, [op("template.delete-columns", at=1)])
    data = (column_sets / PRINT_FILE).read_bytes().decode("utf-8-sig")
    assert DEFAULT_MERGE.format(c=0) in data and SET_MERGE.format(c=0) in data
    assert verify(capsys, column_sets)[0] == 0


def test_merge_cells_compares_merges_of_the_row_set(capsys, column_sets):
    path = column_sets / PRINT_FILE
    data = path.read_bytes().decode("utf-8-sig")
    # The same merge with an explicit columnsID of its row set.
    path.write_bytes(
        b"\xef\xbb\xbf"
        + data.replace(
            SET_MERGE.format(c=0), SET_MERGE.format(c=0) + f"\t\t<columnsID>{SET_ID}</columnsID>\r\n"
        ).encode("utf-8")
    )
    assert verify(capsys, column_sets)[0] == 0
    code, _, _ = plan(capsys, column_sets, [op("template.merge-cells", row=2, column=2, columns=2)])
    assert code == 3
    apply(capsys, column_sets, [op("template.merge-cells", row=2, column=1, unmerge=True)], "unmerge.json")
    assert "<r>1</r>" not in path.read_bytes().decode("utf-8-sig")


def test_size_print_settings_and_header_footer(capsys, root):
    apply(
        capsys,
        root,
        [
            op("template.set-size", column=2, toColumn=3, width=40),
            op("template.set-size", row=1, height=20),
            op(
                "template.set-print-settings",
                orientation="Landscape",
                scale=80,
                topMargin=10,
                printArea={"beginRow": 1, "endRow": 6},
            ),
            op("template.set-header-footer", kind="footer", center="Стр. [&НомерСтраницы]", font={"size": 8}),
        ],
    )
    markup = inspect(capsys, root)["markup"]
    assert markup["print"]["settings"] == {"pageOrientation": "Landscape", "scale": "80", "topMargin": "1000"}
    assert markup["print"]["area"] == {"type": "Rows", "beginRow": 1, "endRow": 6}
    assert markup["print"]["footer"] == {"center": "Стр. [&НомерСтраницы]"}
    data = (root / PRINT_FILE).read_bytes().decode("utf-8-sig")
    order = [
        data.index(tag)
        for tag in (
            "<rightFooter>",
            "<templateMode>",
            "<namedItem",
            "<printArea>",
            "<printSettings>",
            "<line ",
            "<font ",
            "<format>",
        )
    ]
    assert order == sorted(order)
    assert verify(capsys, root)[0] == 0


def test_lf_template_keeps_its_line_endings(capsys, root):
    apply(capsys, root, [op("template.insert-rows", BLANK, at=1)])
    data = (root / BLANK_FILE).read_bytes()
    assert_designer_layout(data, eol=b"\n")
    assert inspect(capsys, root, BLANK)["markup"]["parameters"][0]["row"] == 2


def test_edits_of_foreign_kind_are_rejected(capsys, root):
    code, result, _ = plan(capsys, root, [op("template.insert-rows", "Catalog.Товары.Template.Схема", at=1)])
    assert code == 2 and "DataCompositionSchema" in result["error"]["message"]


@pytest.mark.parametrize(
    "operation",
    [
        op("template.set-area", STUB, name="А", beginRow=1),
        op("template.set-parameter", STUB, row=1, column=1, text="А"),
        op("template.set-size", STUB, column=1, width=10),
    ],
)
def test_edits_of_empty_stub_name_the_reason(capsys, root, operation):
    # template-add leaves <SpreadsheetDocument/> without a grid; BslEdit edits only <document>.
    code, result, _ = plan(capsys, root, [operation])
    assert code == 3 and result["status"] == "rejected"
    assert result["error"]["message"] == (
        "Template is an empty stub without cells; fill it first with template.import-xlsx"
    )


@pytest.mark.parametrize(
    "operation",
    [
        op("template.set-area", name="1А", beginRow=1),
        op("template.set-area", name="А", beginRow=3, endRow=2),
        op("template.set-parameter", row=1, column=1, name="А", text="Б"),
        op("template.insert-rows", at=0),
        op("template.set-format", row=1, column=1),
        op("template.set-format", row=1, column=1, horizontalAlignment="left"),
        op("template.set-size", column=1, height=5),
        op("template.set-print-settings", scale=5),
        op("template.set-header-footer", kind="side", left="x"),
        op("template.set-area", name="А", beginRow=1, unknown=True),
    ],
)
def test_invalid_parameters_are_rejected(capsys, root, operation):
    code, result, _ = plan(capsys, root, [operation])
    assert code == 2 and result["error"]["code"] == 2


def test_delete_past_the_end_is_a_state_conflict(capsys, root):
    code, result, _ = plan(capsys, root, [op("template.delete-rows", at=7)])
    assert code == 3 and result["error"]["message"] == "No rows to delete"


# ---------------------------------------------------------------- E10


def test_verify_passes_on_the_fixture(capsys, root):
    code, result = verify(capsys, root)
    assert code == 0 and result["status"] == "verified"
    report = result["checks"]["local"]["objects"][0]["report"]
    assert report["lines"] == ["=== Validation OK: Template.Печать (1 checks) ==="]
    assert result["checks"]["platform"] == "not-run" and result["checks"]["runtime"] == "not-run"


BROKEN = [
    ("<f>3</f>", "<f>9</f>", "формат 9 не существует"),
    ("<font>0</font>\r\n\t\t<width>", "<font>5</font>\r\n\t\t<width>", "шрифт 5 не существует"),
    ("<leftBorder>0</leftBorder>", "<leftBorder>4</leftBorder>", "линия leftBorder=4 не существует"),
    (
        "<index>3</index>\r\n\t\t<row>\r\n",
        "<index>3</index>\r\n\t\t<row>\r\n\t\t\t<columnsID>нет</columnsID>\r\n",
        "Строка 4: нет набора колонок нет",
    ),
    ("<index>3</index>", "<index>1</index>", "строки идут не по порядку"),
    ("<h>2</h>", "<h>-2</h>", "Объединение 4:2: неверный размер"),
    ("<size>4</size>", "<size>-1</size>", "неверный size"),
    ("<name>Строка</name>", "<name>Шапка</name>", "Область «Шапка»: имя повторяется"),
    ("<name>Строка</name>", "<name>1Строка</name>", "имя не идентификатор"),
    ("<type>Rows</type>\r\n\t\t\t<beginRow>3", "<type>Cells</type>\r\n\t\t\t<beginRow>3", "неизвестный тип Cells"),
    ("<height>6</height>", "<height>-1</height>", "Неверная высота документа"),
    # A warning is a rejection too (code 4).
    ("<height>6</height>", "<height>3</height>", "vgRows (6) больше height (3)"),
]


# Found unchanged in Designer exports of a typical BP 3.0 configuration (ПФ_MXL_ПечатнаяФормаДО, ЭД_ИдентификаторДокумента_ru,
# ФормаРаздел25_2015, ИсторияИзмененийЗначений, СервисДоставки/Заказ ...): verify must accept them.
DESIGNER_LEGAL = [
    [("<height>6</height>\r\n\t<vgRows>6</vgRows>", "<height>3</height>\r\n\t<vgRows>3</vgRows>")],
    [("<size>4</size>", "<size>0</size>")],
    [("<height>6</height>\r\n\t<vgRows>6</vgRows>", "<vgRows>0</vgRows>")],
    [("<endRow>5</endRow>", "<endRow>1</endRow>")],
    [("<parameter>Номер</parameter>", "<parameter>Номер [Ссылка]</parameter>")],
    [("\t\t\t\t\t<parameter>Номер</parameter>\r\n", "")],
    [("<r>0</r>\r\n\t\t<c>0</c>\r\n\t\t<w>2</w>", "<r>0</r>\r\n\t\t<c>0</c>\r\n\t\t<w>2</w>\r\n\t\t<h>4</h>")],
]


@pytest.mark.parametrize("edits", DESIGNER_LEGAL)
def test_verify_accepts_designer_layouts(capsys, root, edits):
    path = root / PRINT_FILE
    data = path.read_bytes().decode("utf-8")
    for old, new in edits:
        assert data.count(old) == 1, old
        data = data.replace(old, new)
    path.write_bytes(data.encode("utf-8"))
    code, result = verify(capsys, root)
    assert code == 0, result["checks"]["local"]["objects"][0]["report"]["lines"]


def test_rows_and_columns_past_the_declared_extent_are_edited(capsys, root):
    path = root / PRINT_FILE
    data = path.read_bytes().decode("utf-8")
    path.write_bytes(
        data.replace("<height>6</height>\r\n\t<vgRows>6</vgRows>", "<height>3</height>\r\n\t<vgRows>3</vgRows>")
        .replace("<size>4</size>", "<size>1</size>")
        .encode("utf-8")
    )
    # Row 4 and column 2 exist past <height> and the column set size.
    apply(capsys, root, [op("template.delete-rows", at=4), op("template.delete-columns", at=2)])
    text = path.read_bytes().decode("utf-8-sig")
    assert "<index>3</index>" not in text and "<parameter>Номер</parameter>" not in text
    assert "<height>3</height>" in text and "<size>1</size>" in text
    assert verify(capsys, root)[0] == 0


@pytest.mark.parametrize("old,new,message", BROKEN)
def test_verify_names_each_violation(capsys, root, old, new, message):
    path = root / PRINT_FILE
    data = path.read_bytes().decode("utf-8")
    assert data.count(old) == 1
    path.write_bytes(data.replace(old, new).encode("utf-8"))
    code, result = verify(capsys, root)
    assert code == 4 and result["status"] == "rejected" and result["error"]["code"] == 4
    lines = result["checks"]["local"]["objects"][0]["report"]["lines"]
    assert any(message in line for line in lines), lines


def test_verify_of_other_kind_names_it(capsys, root):
    code, result = verify(capsys, root, "Catalog.Товары.Template.Схема")
    assert code == 2
    assert "DataCompositionSchema" in result["checks"]["local"]["objects"][0]["error"]


def test_verify_respects_error_limit(capsys, root):
    path = root / PRINT_FILE
    data = path.read_bytes().decode("utf-8")
    path.write_bytes(data.replace("<f>3</f>", "<f>9</f>").replace("<f>2</f>", "<f>8</f>").encode("utf-8"))
    code, result = run(capsys, "verify", "--root", root, "--object", PRINT, "--max-errors", "1")
    report = result["checks"]["local"]["objects"][0]["report"]
    assert code == 4 and report["stopped"] and report["errors"] == 1
