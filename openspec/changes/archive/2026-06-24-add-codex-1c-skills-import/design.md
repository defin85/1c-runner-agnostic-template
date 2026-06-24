## Context

В `1c-runner-agnostic-template` уже есть проектные skills и repo-owned runtime wrappers, но их scope ограничен runner-agnostic capability поверх `env/*.json` и canonical script entrypoint-ов.
Репозиторий `cc-1c-skills` содержит гораздо более широкий skill-pack для XML-исходников 1С, форм, СКД, ролей, конфигураций, расширений и web-test automation, но его `SKILL.md` часто содержит inline execution guidance и PowerShell snippets, что конфликтует с текущим contract-first правилом шаблона.

## Goals

- Поставить весь upstream pack как template-managed compatibility surface без дублирования runtime logic в `SKILL.md`
- Сделать import/update воспроизводимым из pinned upstream source
- Сохранить current native runner-agnostic skills как preferred workflow для template-owned runtime paths
- Доставлять imported pack и в source repo, и в generated repos через overlay/skills surfaces

## Non-Goals

- Переписать imported pack в новый доменно-специфичный native API
- Заменить native `1c-*` skills imported вариантами
- Гарантировать, что каждый imported skill полностью совпадает по UX с оригинальным Claude behavior

## Decisions

### Decision: использовать checked-in vendor layer

Upstream `cc-1c-skills` импортируется в `automation/vendor/cc-1c-skills/` вместе с commit pin, license и generated manifest.
Это делает generated repos self-contained и не требует внешнего clone в runtime.

### Decision: публичный contract идёт через один repo-owned dispatcher

Все imported skills указывают на `scripts/skills/run-imported-skill.sh` / `.ps1` с именем навыка как аргументом.
Dispatcher выбирает один из путей:

- vendored Python helper
- vendored Node helper
- native runner-agnostic alias для нескольких overlapping capability
- reference-only summary для upstream skills без helper-script

### Decision: native skills остаются предпочтительными

Если imported skill пересекается с уже существующим runner-agnostic workflow (`db-create`, `db-update`, `web-publish` и т.п.), imported surface остаётся compatibility layer и должен указывать на native preference в generated docs/skills.

### Decision: generated skill markdown должен быть полностью derived

`.agents/skills/<name>/SKILL.md`, `.claude/skills/<name>/SKILL.md` и оба `README.md` не редактируются вручную.
Они пересобираются через `python -m scripts.python.cli sync-imported-skills --source ...`.

## Risks / Trade-offs

- Template-managed surface заметно увеличится по количеству файлов
  - Mitigation: использовать один dispatcher вместо десятков hand-written wrappers и держать vendor provenance явно

- Некоторые upstream skills являются только markdown-инструкциями, без исполняемого helper-а
  - Mitigation: для них dispatcher остаётся reference-only и печатает canonical vendored reference вместо ложной имитации runtime

- Overlapping imported/native skills могут ухудшить skill discovery
  - Mitigation: generated README и skill docs явно помечают native runner-agnostic skills как preferred workflow там, где это применимо

## Verification Strategy

- `openspec validate add-codex-1c-skills-import --strict --no-interactive`
- `python -m unittest tests.python.test_cross_platform`
- `bash tests/smoke/imported-skills-contract.sh`
- `bash tests/smoke/copier-update-ready.sh`
- `make agent-verify`
