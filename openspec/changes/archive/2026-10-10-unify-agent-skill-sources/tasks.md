## 1. Один источник навыков

- [x] 1.1 Добавить `sync-claude-skills [--check]` в `imported_skills.py` и CLI, цели `make sync-claude-skills` и `./make.ps1 sync-claude-skills`; `sync-imported-skills` строит зеркало вместо отдельного Claude-рендера.
- [x] 1.2 Включить проверку зеркала в `check-skill-bindings`.
- [x] 1.3 Пересоздать `.claude/skills` шаблона из `.agents/skills` и проверить README-навигацию.
- [x] 1.4 Добавить тесты зеркала: копирование, удаление устаревших навыков, сохранение `openspec-*` и README, режим проверки.

## 2. Блок AGENTS.md

- [x] 2.1 Переформулировать Landing the Plane и добавить приоритет проектного поискового runbook в `agents-overlay.sh`; обновить smoke-проверки текста.

## 3. Проверка и передача

- [x] 3.1 Выполнить `openspec validate unify-agent-skill-sources --strict`, unit-тесты и `make agent-verify`.
- [x] 3.2 Описать для созданных проектов шаг переноса после обновления шаблона.
  - Перенос в проект выполняется не в этом репозитории: проект обновляется до релиза с этим change (`v0.4.0`) и выполняет `make sync-claude-skills` и `make agent-verify`. Шаг добавлен в `docs/migrations/project-toolkit-update.md` (раздел «После обновления», шаг 8).

Проверка 2026-09-25: `openspec validate unify-agent-skill-sources --strict`, `python3 -m unittest tests.python.test_imported_skills` (3 теста), `make agent-verify`, `tests/smoke/bootstrap-agents-overlay.sh` и `tests/smoke/agent-docs-contract.sh` прошли. `tests/smoke/copier-update-ready.sh` падает на `runtime-doctor-runtime-mode` так же на чистом `origin/main` 5c2389a; это существующий сбой вне этого change.
