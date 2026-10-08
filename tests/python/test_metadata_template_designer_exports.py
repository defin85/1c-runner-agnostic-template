"""template verify against unchanged Designer exports of a typical BP 3.0 configuration.

The export is not part of the template: set METADATA_DESIGNER_EXPORTS to its root
(by default the project main configuration root src/cf is used); without it the test is skipped.
By default it checks one template for each layout the former checks refused; with
METADATA_TEMPLATE_FULL_SCAN=1 it checks every spreadsheet template (minutes of CPU).
It proves only that the local structure check accepts Designer output; platform
loading is not checked here.
"""

import tests.python.metadata_test_support  # noqa: F401, I001 — runs first: skips the module without pytest, lxml, jsonschema
import os
from multiprocessing import Pool
from pathlib import Path

import pytest

from scripts.python import metadata_template_ops as templates


ROOT = Path(os.environ.get("METADATA_DESIGNER_EXPORTS") or Path(__file__).parents[2] / "src" / "cf")
# Each file held a layout that the former checks reported: rows past <height>, columns and
# cells past the set size, size 0, no <height>, reversed and out-of-grid areas, merges past
# the grid, overlapping merges, nameless parameter cells, templates without [Имя],
# parameter names with spaces, drawings and the print area past <height>, several column sets,
# columnsItem with index -1.
SAMPLES = [
    "DataProcessors/ИнтеграцияС1СДокументооборот3/Templates/ПФ_MXL_ПечатнаяФормаДО",
    "DataProcessors/ЭлектронноеВзаимодействие/Templates/ЭД_ИдентификаторДокумента_ru",
    "DataProcessors/ПечатьРасчетаСреднегоЗаработка/Templates/ПФ_MXL_РасчетСреднегоЗаработка",
    "DataProcessors/СверкаДанныхУчетаНДС/Templates/СверкаСчетовФактурСПоставщиками",
    "DataProcessors/ПечатьФормВоинскогоУчета/Templates/ПФ_MXL_ПланРаботыПоОсуществлениюВоинскогоУчета",
    "DataProcessors/ПроверкаКонтрагента/Templates/ИсторияИзмененийЗначений",
    "Reports/РегламентированноеУведомлениеСверкаРасчетовПоНалогам/Templates/Печать_Форма2020_1_Титульная",
    "DataProcessors/ДокументооборотСКонтролирующимиОрганами/Templates/ФССШаблонДляHTML",
    "Catalogs/КомплектыОтчетностиПерсУчета/Templates/ФормаРаздел25_2015",
    "InformationRegisters/УчетнаяПолитика/Templates/ПервичныеДокументы",
    "Reports/РегламентированныйОтчет3НДФЛ/Templates/МЧБ_2022кв1_Титульный",
    "DataProcessors/СервисДоставки/Templates/Заказ",
    "DataProcessors/ОбменСКонтрагентами/Templates/УКД_ИнформацияПродавца",
    "Documents/Бюджет/Templates/БюджетДоходовРасходов",
    "Documents/ВходящаяТранспортнаяОперацияВЕТИС/Templates/ВыявленныеНесоответствия",
    "Documents/СообщениеОбменСБанками/Templates/ЭД_ВыпискаБанка_ru",
    "Documents/ИнвентаризацияТоваровНаСкладе/Templates/ПФ_MXL_ИНВ19",
    "Documents/СведенияОЗаработкеСтажеЗастрахованныхЛицСЗВ_ИСХ/Templates/ПФ_MXL_ФормаСЗВ_ИСХ",
]


def check(path):
    data = Path(path).read_bytes()
    if b"<document" not in data[:400]:
        return path, None
    template = templates.Template(data, allow_stub=True)
    return path, templates.validate(template.root)


pytestmark = pytest.mark.skipif(not (ROOT / "Configuration.xml").is_file(), reason=f"Designer export is absent: {ROOT}")


@pytest.mark.parametrize("sample", SAMPLES)
def test_designer_template_passes_verify(sample):
    path = ROOT / sample / "Ext" / "Template.xml"
    if not path.is_file():
        pytest.skip(f"template is absent in this export: {sample}")
    assert check(str(path))[1] == ([], [])


@pytest.mark.skipif(os.environ.get("METADATA_TEMPLATE_FULL_SCAN") != "1", reason="full scan is opt-in")
def test_every_designer_spreadsheet_template_passes_verify():
    paths = [str(path) for path in ROOT.glob("*/*/Templates/*/Ext/Template.xml")]
    failures = {}
    with Pool(max(1, (os.cpu_count() or 2) - 2)) as pool:
        for path, result in pool.imap_unordered(check, paths, chunksize=4):
            if result is not None and result != ([], []):
                failures[path] = result
    assert not failures, sorted(failures.items())[:10]
