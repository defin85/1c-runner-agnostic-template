# Generated Recommended Skills Reference

Этот template-scoped reference описывает expected contract для `automation/context/recommended-skills.generated.md`.

## Recommendation Contract

- остаётся generated-derived, а не project-owned truth;
- показывает compact first-hour subset поверх полного `.agents/skills/README.md`;
- ссылается на `make imported-skills-readiness` и `./scripts/skills/run-imported-skill.sh --readiness` как canonical readiness/bootstrap path для executable imported compatibility skills;
- выводит concrete skill names или repo-owned entrypoints, а не prose-only советы;
- использует repo shape signals вроде subsystems, forms, extensions, reports, external processors и service edges для выбора subset;
- refresh-ится через `./scripts/llm/export-context.sh --write`.
- в базовых рекомендациях всегда показывает `1c-check-bsl` (`make check-bsl` / `./make.ps1 check-bsl`) для проверки изменённых модулей до загрузки в ИБ;
- для правки объектов метаданных и управляемых форм рекомендует `metadata-use` (metadata CLI: `metadata inspect`, `plan`, `apply`, `verify`), а для формы основной конфигурации через расширение — `cfe-form-workflow`;
- для обычных форм внешних обработок и отчётов рекомендует `ordinary-form-workflow`, для подготовки EPF/ERF к ручной правке BSL — `prepare-external-artifact`;
- в разделе follow-up routers называет `1c-observe-run` (разбор `observation.jsonl` и `progress.txt` длительного запуска) и `1c-run-client` (управление клиентом 1С);
- не рекомендует выведенные из шаблона `meta-*`, `form-*` (кроме справочника `form-patterns`) и `cfe-borrow`, а также удалённую цель `format-bsl`.

## Платформы

- Команды из рекомендаций имеют обёртки для Linux (`make <цель>`, `*.sh`) и Windows (`./make.ps1 <цель>`, `*.ps1`). Исключения: `v8std-fetch` и `v8std-search` поставляются только как Linux-скрипты, а навык `1c-linux-crash-diagnostics` относится только к серверу 1С на Linux.
- Windows-обёртки новых команд (`check-bsl`, `check-cf-modules`, `analyze-bsl-external`, `run-client`, `technological-log`, `artifact-storage`) ещё не запускались на Windows. Рекомендации не должны выдавать их за проверенные на Windows.
