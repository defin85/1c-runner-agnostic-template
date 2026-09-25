## Why

Навыки поставляются в двух независимо редактируемых копиях: `.agents/skills` для Codex и `.claude/skills` для Claude Code. Тексты 79 навыков уже разошлись, а в созданных проектах собственные навыки попадают только в `.agents/skills`, поэтому Claude Code их не видит и продолжает показывать удалённые навыки. Кроме того, блок `AGENTS.md` требует push для завершения любой сессии в репозитории с remote, что противоречит правилу «commit и push только по запросу» пользовательских инструкций и остальным документам шаблона.

## What Changes

- `.agents/skills/<имя>` становится единственным источником навыка. `.claude/skills/<имя>` — побайтовое зеркало, которое строит репозиторная команда `sync-claude-skills`; навыки `openspec-*`, создаваемые OpenSpec для каждого агента, и `.claude/skills/README.md` в зеркало не входят.
- `sync-imported-skills` больше не рендерит отдельный Claude-вариант импортированного навыка, а строит зеркало.
- `check-skill-bindings` (входит в `agent-verify`) завершается ошибкой, если зеркало устарело, и называет команду исправления.
- Блок `AGENTS.md`: push в remote-backed репозитории выполняется по запросу пользователя или выбранного процесса публикации; Search Playbook уступает проектному поисковому runbook.

## Решения пользователя

- 2026-09-25: навыки для Claude Code в репозитории поставлять копией с проверкой актуальности, а не символическими ссылками: Windows-checkout без `core.symlinks` превращает ссылки в текстовые файлы.
- 2026-09-25: генерацию и правки блока `AGENTS.md` выполнять в шаблоне, затем переносить в созданные проекты; шаблон разрешено править напрямую.

## Capabilities

### Modified Capabilities

- `project-scoped-skills`: один источник навыков и зеркало для Claude Code.
- `generated-project-agent-guidance`: условный push и приоритет проектного поискового runbook.

## Impact

- `scripts/python/imported_skills.py`, `scripts/python/qa.py`, `scripts/python/cli.py`, `Makefile`, `make.ps1`, `scripts/bootstrap/agents-overlay.sh`.
- `.claude/skills/*` пересоздаётся из `.agents/skills/*`.
- Тесты: `tests/python/test_imported_skills.py`, smoke-проверки текста блока `AGENTS.md`.
- Созданные проекты после обновления выполняют `make sync-claude-skills`, чтобы их собственные навыки попали в зеркало.
