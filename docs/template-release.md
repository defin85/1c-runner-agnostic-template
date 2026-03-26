# Template Release

Этот runbook относится только к source repo шаблона.
Для generated repos ongoing maintenance path остаётся в [docs/template-maintenance.md](template-maintenance.md).

## Когда сюда идти

- нужно выпустить новый overlay release tag шаблона;
- нужно установить repo-owned hook guardrail, который не даёт случайно push-ить `refs/tags/v*`;
- нужно понять, почему source release workflow завершился fail-closed.

## Канонический workflow

1. Один раз на clone установите source hooks:

```bash
./scripts/release/install-source-hooks.sh
```

2. Подготовьте и опубликуйте release-worthy commit в `origin/main`.
3. Выпустите tag только через repo-owned command:

```bash
./scripts/release/publish-overlay-release.sh --tag v0.3.6
```

## Fail-Closed Checks

`publish-overlay-release.sh` не публикует tag, если хотя бы одно условие не выполнено:

- репозиторий не распознан как template source repo;
- git worktree грязный;
- локальная ветка не `main`;
- `HEAD` не совпадает с `origin/main`;
- baseline verification не проходит;
- target tag уже существует локально или на `origin`.

Перед tag push workflow повторно прогоняет baseline verify, эквивалентный `make agent-verify`.

## Hook Guardrail

- repo-owned hook живёт в `.githooks/pre-push`;
- hook блокирует прямой push `refs/tags/v*`, включая случайный `git push --follow-tags`;
- сообщение об ошибке должно отправлять обратно к `./scripts/release/publish-overlay-release.sh --tag ...` и этому runbook.

## После публикации

- проверьте, что новый tag указывает на ожидаемый commit в `origin`;
- используйте [docs/template-maintenance.md](template-maintenance.md), чтобы подтянуть новый overlay release в generated repos.
