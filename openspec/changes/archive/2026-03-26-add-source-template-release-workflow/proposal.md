# Change: source template release workflow

## Почему

Шаблон уже умеет versioned overlay delivery для generated repos, но source repo пока не даёт такого же явного и безопасного пути для публикации нового overlay release tag.
Сейчас следующий tag можно выпустить вручную, однако в репозитории нет repo-owned workflow, который бы отделял обычный `git push` от намеренной публикации нового template release.

## Что меняется

- добавляется repo-owned source release command для публикации нового template overlay tag;
- добавляется hook-based guardrail, который блокирует случайный push overlay release tag вне канонического release path;
- source-repo docs получают отдельный runbook для template release workflow;
- smoke/static checks начинают проверять source release workflow и его documentation contract;
- после стабилизации workflow публикуется следующий template release tag.

## Impact

- Affected specs:
  - `template-overlay-delivery`
  - `template-ci-contours`
  - `repository-agent-guidance`
- Affected code:
  - `scripts/release/**`
  - `.githooks/**`
  - `Makefile`
  - `docs/template-release.md`
  - `docs/agent/**`
  - `tests/smoke/**`
