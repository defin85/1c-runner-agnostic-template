# External Processors Source

Сюда помещаются исходники внешних обработок (`epf`).

Если обработка собирается из модулей, держите build logic рядом в отдельном подкаталоге обработки.
Шаблон также поставляет server-side xUnit harness starter в `src/epf/TemplateXUnitHarness`; если проект делает свой harness, не возвращайтесь к managed-form default shape без явной причины.
