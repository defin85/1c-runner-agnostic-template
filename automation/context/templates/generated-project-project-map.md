# Generated Project Map Starter

Этот файл показывает структуру project-owned карты generated repo.
Живой curated контекст должен храниться в `automation/context/project-map.md`.

## Обязательные секции

- repository identity;
- known source roots;
- ownership model;
- canonical entrypoints;
- next enrichment steps.

## Что уточнять в project-owned карте

- бизнес-домен и ключевые bounded contexts;
- реальные metadata entrypoint-ы;
- HTTP services, scheduled jobs, forms, external processors и extensions;
- ограничения проекта, которые не принадлежат template-managed слою.

## Что не смешивать с этим файлом

- machine-generated inventory из `automation/context/metadata-index.generated.json`;
- машинно-зависимые настройки из `env/local.json`, `env/wsl.json`, `env/.local/*.json`;
- template maintenance notes, которые уже живут в `docs/template-maintenance.md`.
