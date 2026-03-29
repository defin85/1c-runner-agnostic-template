# Template Maintenance

Этот документ описывает ongoing template maintenance path для generated repos.
Он не является primary onboarding или feature-delivery workflow.
Для source repo release tag используйте отдельный runbook: [docs/template-release.md](template-release.md).

## Когда сюда идти

- нужно проверить, есть ли новый wrapper overlay release;
- нужно подтянуть `template-managed` слой в generated repo;
- нужно понять, какие части репозитория overlay apply может менять автоматически.

## Канонические команды

```bash
make template-check-update
make template-update
```

Или напрямую:

```bash
./scripts/template/check-update.sh
./scripts/template/update-template.sh
```

`template-check-update` сверяет текущую checked-in версию wrapper overlay в `.template-overlay-version`
с latest tagged release шаблона или с явно переданным `--vcs-ref`.
`template-update` materialize-ит выбранный template ref и применяет только manifest template-managed paths из `automation/context/template-managed-paths.txt`.
Если путь был демотирован из template-managed в project-owned, update path сохраняет текущий project file по списку `automation/context/template-update-preserve-paths.txt`, а не удаляет его.
Дополнительно migration cleanup удаляет retired template-seeded routing docs из deployable `src/cf`, если они остались от старых template release, например legacy `src/cf/AGENTS.md` и `src/cf/README.md`.

## Ownership Boundary

- `.copier-answers.yml` остаётся bootstrap provenance и хранит source location шаблона;
- `.template-overlay-version` хранит текущий applied wrapper overlay release;
- `template-managed` слой обновляется через versioned overlay apply, а не через reconciliation product source tree;
- если root `AGENTS.md` или `README.md` отсутствует, `template-update` восстанавливает generated-project entry surface перед refresh managed overlay/router;
- `seed-once / project-owned` артефакты вроде root `README.md`, `openspec/project.md`, `.codex/config.toml` и `automation/context/project-map.md` должны оставаться под контролем команды проекта;
- `generated-derived` артефакты refresh-ятся отдельной repo-owned командой `./scripts/llm/export-context.sh --write`;
- `local-private` machine-specific настройки не входят в checked-in template contract.

## Compatibility Note

- `copier copy` остаётся bootstrap-механизмом для новых generated repos;
- `copier update` допустим только как migration bridge для старых generated repos, которые ещё не получили overlay-aware scripts;
- после миграции ongoing maintenance path должен идти через `make template-check-update` и `make template-update`.

## Перед обновлением

1. Закоммитьте или хотя бы осознайте локальные project-owned изменения и держите git worktree чистым.
2. Прогоните `make agent-verify`.
3. Если меняется bootstrap/overlay surface, добавьте fixture smoke:

```bash
bash tests/smoke/bootstrap-agents-overlay.sh
bash tests/smoke/copier-update-ready.sh
```

## После обновления

1. Проверьте root `README.md`, `AGENTS.md` и project-owned context.
2. Убедитесь, что `.template-overlay-version` обновился до ожидаемого release ref.
3. Если репозиторий обновлялся со старого шаблона, подтвердите, что stale `src/cf/AGENTS.md` и `src/cf/README.md` исчезли и `src/cf` снова остаётся чистым importable source tree.
4. При необходимости refresh-ните generated-derived inventory:

```bash
./scripts/llm/export-context.sh --write
```

4. Повторно прогоните baseline verify:

```bash
make agent-verify
```
