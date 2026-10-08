"""template.import-xlsx: an Excel sheet fills a registered spreadsheet template through plan/apply."""

import tests.python.metadata_test_support  # noqa: F401, I001 — runs first: skips the module without pytest, lxml, jsonschema
import io
import json
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.python import metadata, metadata_template_ops

ROOT = Path(__file__).resolve().parents[2]

FIXTURE = ROOT / "tests/fixtures/metadata-template/config"
STUB = "Catalog.Товары.Template.Пустой"
STUB_FILE = "Catalogs/Товары/Templates/Пустой/Ext/Template.xml"
PRINT = "Catalog.Товары.Template.Печать"
PRINT_FILE = "Catalogs/Товары/Templates/Печать/Ext/Template.xml"
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"

STYLES = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="{MAIN}">
<numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0.00"/></numFmts>
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="14"/><color rgb="FFC00000"/><name val="Arial"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFFEE00"/></patternFill></fill></fills>
<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>
<border><left style="thin"/><right style="thin"/><top style="thin"/><bottom style="medium"/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment horizontal="center" wrapText="1"/></xf>
<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
<xf numFmtId="14" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/></cellXfs>
</styleSheet>'''

SHEET = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="{MAIN}" xmlns:r="{REL}">
<sheetFormatPr defaultRowHeight="15"/>
<cols><col min="1" max="1" width="30" customWidth="1"/><col min="2" max="3" width="12" customWidth="1"/></cols>
<sheetData>
<row r="1" ht="24" customHeight="1"><c r="A1" s="1" t="s"><v>0</v></c></row>
<row r="2"><c r="A2" t="s"><v>1</v></c><c r="B2" s="3"><v>45292</v></c></row>
<row r="3"><c r="A3" t="s"><v>2</v></c><c r="B3" s="2"><v>1234.5</v></c><c r="C3" s="2"><f>B3*2</f><v>2469</v></c></row>
<row r="4"><c r="A4" t="inlineStr"><is><t>Итого: [Сумма] руб.</t></is></c><c r="B4" t="s"><v>3</v></c></row>
</sheetData>
<mergeCells count="1"><mergeCell ref="A1:C1"/></mergeCells>
<pageMargins left="0.5" right="0.5" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>
<pageSetup paperSize="9" orientation="landscape"/>
<headerFooter><oddHeader>&amp;LОтчёт&amp;RСтр. &amp;P из &amp;N</oddHeader><oddFooter>&amp;C&amp;D</oddFooter></headerFooter>
<drawing r:id="rId1"/>
</worksheet>'''

DRAWING = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing">'
    "<xdr:twoCellAnchor><xdr:from><xdr:col>3</xdr:col><xdr:row>0</xdr:row></xdr:from>"
    "<xdr:to><xdr:col>4</xdr:col><xdr:row>2</xdr:row></xdr:to><xdr:clientData/></xdr:twoCellAnchor></xdr:wsDr>"
)


def sst(*strings):
    items = "".join(f'<si><t xml:space="preserve">{s}</t></si>' for s in strings)
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><sst xmlns="{MAIN}">{items}</sst>'


def build_xlsx(drawing=True, second_sheet=False) -> bytes:
    sheets = '<sheet name="Макет" sheetId="1" r:id="rId1"/>'
    rels = f'<Relationship Id="rId1" Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/>'
    if second_sheet:
        sheets += '<sheet name="Второй" sheetId="2" r:id="rId4"/>'
        rels += f'<Relationship Id="rId4" Type="{REL}/worksheet" Target="worksheets/sheet2.xml"/>'
    rels += (
        f'<Relationship Id="rId2" Type="{REL}/styles" Target="styles.xml"/>'
        f'<Relationship Id="rId3" Type="{REL}/sharedStrings" Target="sharedStrings.xml"/>'
    )
    workbook = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="{MAIN}" xmlns:r="{REL}">'
        f"<sheets>{sheets}</sheets><definedNames>"
        '<definedName name="Шапка">Макет!$1:$2</definedName>'
        '<definedName name="Строка">Макет!$3:$4</definedName>'
        '<definedName name="Колонка">Макет!$B:$C</definedName>'
        '<definedName name="Битое">#REF!</definedName>'
        '<definedName name="_xlnm.Print_Area" localSheetId="0">Макет!$A$1:$C$4</definedName>'
        "</definedNames></workbook>"
    )
    parts = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        "_rels/.rels": f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{PKG}"/>',
        "xl/workbook.xml": workbook,
        "xl/_rels/workbook.xml.rels": f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{PKG}">{rels}</Relationships>',
        "xl/styles.xml": STYLES,
        "xl/sharedStrings.xml": sst("Накладная № [Номер]", "Дата", "[Товар]", "[Количество]"),
        "xl/worksheets/sheet1.xml": SHEET if drawing else SHEET.replace('<drawing r:id="rId1"/>', ""),
    }
    if drawing:
        parts["xl/worksheets/_rels/sheet1.xml.rels"] = (
            f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{PKG}">'
            f'<Relationship Id="rId1" Type="{REL}/drawing" Target="../drawings/drawing1.xml"/></Relationships>'
        )
        parts["xl/drawings/drawing1.xml"] = DRAWING
    if second_sheet:
        parts["xl/worksheets/sheet2.xml"] = (
            f'<worksheet xmlns="{MAIN}"><sheetData><row r="1">'
            '<c r="A1" t="inlineStr"><is><t>[Один]</t></is></c></row></sheetData></worksheet>'
        )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in parts.items():
            archive.writestr(name, text.encode("utf-8"))
    return buffer.getvalue()


@pytest.fixture
def root(tmp_path):
    target = tmp_path / "config"
    shutil.copytree(FIXTURE, target)
    return target


@pytest.fixture
def xlsx(tmp_path):
    folder = tmp_path / "input"
    folder.mkdir()
    path = folder / "layout.xlsx"
    path.write_bytes(build_xlsx())
    return path


def run(capsys, *argv):
    code = metadata.main([str(item) for item in argv])
    out = capsys.readouterr().out
    assert len(out.splitlines()) == 1
    return code, json.loads(out)


def plan(capsys, root, target, name="plan.json", **parameters):
    request = root.parent / ("request-" + name)
    request.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "operations": [{"op": "template.import-xlsx", "target": target, "parameters": parameters}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out = root.parent / name
    code, result = run(capsys, "plan", "--root", root, "--request", request, "--out", out)
    return code, result, out


def apply(capsys, root, target, name="plan.json", **parameters):
    code, result, out = plan(capsys, root, target, name, **parameters)
    assert code == 0, result
    code, applied = run(capsys, "apply", "--root", root, "--plan", out)
    assert code == 0, applied
    return result, applied


def test_import_into_stub_builds_verified_template(capsys, root, xlsx):
    result, applied = apply(capsys, root, STUB, xlsx=str(xlsx))
    assert applied["status"] == "applied"
    plan_data = json.loads((root.parent / "plan.json").read_text(encoding="utf-8"))
    summary = plan_data["operationReports"][0]["report"]
    assert summary["sheet"] == "Макет" and summary["rows"] == 4 and summary["columns"] == 3
    assert summary["merges"] == 1 and summary["pictures"] == 0
    assert summary["areas"] == [
        {"name": "Шапка", "type": "Rows", "beginRow": 1, "endRow": 2},
        {"name": "Строка", "type": "Rows", "beginRow": 3, "endRow": 4},
        {"name": "Колонка", "type": "Columns", "beginColumn": 2, "endColumn": 3},
    ]
    notes = "\n".join(summary["notTransferred"])
    assert "Формулы (1)" in notes and "Картинки" in notes and "Битое" in notes
    data = (root / STUB_FILE).read_bytes()
    # The stub had LF endings, a BOM and no final newline; the result keeps all three.
    assert data.startswith(b"\xef\xbb\xbf") and b"\r\n" not in data and data.endswith(b"</document>")
    code, inspected = run(capsys, "inspect", "--root", root, "--object", STUB)
    assert code == 0
    markup = inspected["changes"]["markup"]
    names = {(p["row"], p["column"], p["name"]) for p in markup["parameters"]}
    assert names == {(3, 1, "Товар"), (4, 2, "Количество")}
    templates = {(t["row"], t["column"], tuple(t["names"])) for t in markup["templates"]}
    assert templates == {(1, 1, ("Номер",)), (4, 1, ("Сумма",))}
    assert [a["name"] for a in markup["areas"]] == ["Шапка", "Строка", "Колонка"]
    assert markup["print"]["area"] and markup["print"]["header"] and markup["print"]["footer"]
    code, verified = run(capsys, "verify", "--root", root, "--object", STUB)
    assert code == 0, verified


def test_repeat_is_already_applied(capsys, root, xlsx):
    apply(capsys, root, STUB, xlsx=str(xlsx))
    before = (root / STUB_FILE).read_bytes()
    code, _, out = plan(capsys, root, STUB, "again.json", xlsx=str(xlsx), replace=True)
    assert code == 0
    code, applied = run(capsys, "apply", "--root", root, "--plan", out)
    assert code == 0 and applied["status"] == "already-applied"
    assert (root / STUB_FILE).read_bytes() == before


def test_stub_is_edited_after_import_in_the_same_plan(capsys, root, xlsx):
    request = root.parent / "request-chain.json"
    request.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "operations": [
                    {"op": "template.import-xlsx", "target": STUB, "parameters": {"xlsx": str(xlsx)}},
                    {
                        "op": "template.set-parameter",
                        "target": STUB,
                        "parameters": {"row": 2, "column": 3, "name": "Итог"},
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    code, result = run(capsys, "plan", "--root", root, "--request", request, "--out", root.parent / "chain.json")
    assert code == 0, result
    assert run(capsys, "apply", "--root", root, "--plan", root.parent / "chain.json")[0] == 0
    assert "<parameter>Итог</parameter>" in (root / STUB_FILE).read_bytes().decode("utf-8-sig")


def test_xlsx_in_an_ancestor_of_root_is_refused_with_its_reason(capsys, root, tmp_path):
    # The xlsx directory becomes a declared source root; --root, its state directory and
    # the plan must stay outside it, so the plan is refused before any write.
    ancestor = tmp_path / "layout.xlsx"
    ancestor.write_bytes(build_xlsx())
    before = (root / STUB_FILE).read_bytes()
    code, result, out = plan(capsys, root, STUB, xlsx=str(ancestor))
    assert code == 3 and result["status"] == "rejected" and not out.exists()
    assert result["error"]["message"] == (
        "xlsx directory contains --root; move the xlsx to a directory outside the parent of --root"
    )
    assert (root / STUB_FILE).read_bytes() == before


def test_plan_output_inside_the_xlsx_directory_names_the_reason(capsys, root, xlsx):
    request = root.parent / "request-inside.json"
    request.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "operations": [{"op": "template.import-xlsx", "target": STUB, "parameters": {"xlsx": str(xlsx)}}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out = xlsx.parent / "plan.json"
    code, result = run(capsys, "plan", "--root", root, "--request", request, "--out", out)
    assert code == 3 and not out.exists()
    assert "Plan output is inside a declared source root" in result["error"]["message"]


def test_non_empty_template_requires_replace(capsys, root, xlsx):
    before = (root / PRINT_FILE).read_bytes()
    code, result, _ = plan(capsys, root, PRINT, xlsx=str(xlsx))
    assert code == 3, result
    assert (root / PRINT_FILE).read_bytes() == before
    apply(capsys, root, PRINT, "replace.json", xlsx=str(xlsx), replace=True)
    data = (root / PRINT_FILE).read_bytes()
    # The CRLF template keeps CRLF and its BOM; no final newline, as before.
    assert data.startswith(b"\xef\xbb\xbf") and b"\r\n" in data and not data.endswith(b"\n")
    assert b"<parameter>" in data and "Строка".encode() in data
    assert run(capsys, "verify", "--root", root, "--object", PRINT)[0] == 0


def test_sheet_selection_and_errors(capsys, root, tmp_path):
    folder = tmp_path / "input"
    folder.mkdir()
    path = folder / "two.xlsx"
    path.write_bytes(build_xlsx(drawing=False, second_sheet=True))
    code, _, _ = plan(capsys, root, STUB, "missing.json", xlsx=str(path), sheet="Нет")
    assert code == 3
    code, _, _ = plan(capsys, root, STUB, "index.json", xlsx=str(path), sheet=5)
    assert code == 3
    apply(capsys, root, STUB, "second.json", xlsx=str(path), sheet="Второй")
    code, inspected = run(capsys, "inspect", "--root", root, "--object", STUB)
    assert [p["name"] for p in inspected["changes"]["markup"]["parameters"]] == ["Один"]
    bad = folder / "bad.xlsx"
    bad.write_bytes(b"not a zip")
    code, _, _ = plan(capsys, root, STUB, "bad.json", xlsx=str(bad), replace=True)
    assert code == 2
    code, _, _ = plan(capsys, root, STUB, "rel.json", xlsx="input/two.xlsx", replace=True)
    assert code == 2


def test_other_template_kind_is_rejected(capsys, root, xlsx):
    code, result, _ = plan(capsys, root, "Catalog.Товары.Template.Схема", xlsx=str(xlsx))
    assert code == 2 and "DataCompositionSchema" in json.dumps(result, ensure_ascii=False)


def test_convert_is_deterministic():
    data = build_xlsx()
    first = metadata_template_ops.convert(data, eol="\n", trailing=True, bom=True)
    second = metadata_template_ops.convert(data, eol="\n", trailing=True, bom=True)
    assert first == second
    crlf, _ = metadata_template_ops.convert(data)
    assert crlf.replace(b"\r\n", b"\n") + b"\n" == first[0]
