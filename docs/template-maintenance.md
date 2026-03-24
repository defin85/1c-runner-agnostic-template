# Template Maintenance

Этот документ описывает template maintenance path для generated repos.
Он не является primary onboarding или feature-delivery workflow.

## Когда сюда идти

- нужно проверить, есть ли обновления шаблона;
- нужно подтянуть `template-managed` слой в generated repo;
- нужно понять, какие части репозитория template update может менять автоматически.

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

## Ownership Boundary

- `template-managed` слой может обновляться через `copier update` и post-update hooks;
- если root `AGENTS.md` или `README.md` отсутствует, template update восстанавливает generated-project entry surface перед refresh managed overlay/router;
- `seed-once / project-owned` артефакты вроде root `README.md`, `openspec/project.md` и `automation/context/project-map.md` должны оставаться под контролем команды проекта;
- `generated-derived` артефакты refresh-ятся отдельной repo-owned командой `./scripts/llm/export-context.sh --write`;
- `local-private` machine-specific настройки не входят в checked-in template contract.

## Перед обновлением

1. Закоммитьте или хотя бы осознайте локальные project-owned изменения.
2. Прогоните `make agent-verify`.
3. Если меняется bootstrap/copier surface, добавьте fixture smoke:

```bash
bash tests/smoke/bootstrap-agents-overlay.sh
bash tests/smoke/copier-update-ready.sh
```

## После обновления

1. Проверьте root `README.md`, `AGENTS.md` и project-owned context.
2. При необходимости refresh-ните generated-derived inventory:

```bash
./scripts/llm/export-context.sh --write
```

3. Повторно прогоните baseline verify:

```bash
make agent-verify
```
