# Change: add-codex-1c-skills-import

## Why

Шаблон уже поставляет native runner-agnostic skills для базовых runtime/test workflow, но не покрывает широкий набор XML/metadata/form/CFE helper-capability из `cc-1c-skills`.
Из-за этого агенты вынуждены заново изобретать ad hoc инструкции для типовых задач 1С или ссылаться на внешний репозиторий вне template-managed surface.

## What Changes

- добавить полный imported compatibility pack из `cc-1c-skills` как template-managed vendor source и сгенерированные `.agents/skills` / `.claude/skills` фасады
- сохранить contract-first архитектуру шаблона: публичный execution contract остаётся repo-owned и идёт через `scripts/skills/run-imported-skill.*`, а не через inline PowerShell snippets в `SKILL.md`
- зафиксировать provenance, commit pin и MIT license imported pack в checked-in vendor layer
- добавить generator/sync tooling, чтобы обновление imported pack было воспроизводимым, а не ручным
- покрыть imported pack contract через OpenSpec, cross-platform checks и generated-project delivery smoke

## Impact

- Affected specs:
  - `project-scoped-skills`
- Affected code:
  - `scripts/python/imported_skills.py`
  - `scripts/python/cli.py`
  - `scripts/skills/run-imported-skill.sh`
  - `scripts/skills/run-imported-skill.ps1`
  - `automation/vendor/cc-1c-skills/**`
  - `.agents/skills/**`
  - `.claude/skills/**`
  - `tests/python/test_cross_platform.py`
  - `tests/smoke/copier-update-ready.sh`
  - `tests/smoke/imported-skills-contract.sh`
  - `README.md`
