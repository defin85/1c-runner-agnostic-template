# Generated Project Map Starter

Этот файл показывает структуру project-owned карты generated repo.
Живой curated контекст должен храниться в `automation/context/project-map.md`.

## Обязательные секции

- repository identity;
- known source roots;
- ownership model;
- canonical entrypoints;
- immediate routers;
- next enrichment steps.

## Что уточнять в project-owned карте

- бизнес-домен и ключевые bounded contexts;
- реальные metadata entrypoint-ы;
- HTTP services, scheduled jobs, forms, external processors и extensions;
- review / env / skills / exec-plan routers, если команда меняет стартовый onboarding;
- ограничения проекта, которые не принадлежат template-managed слою.

## Что не смешивать с этим файлом

- compact generated summary из `automation/context/hotspots-summary.generated.md`, если нужна summary-first навигация;
- machine-generated inventory из `automation/context/metadata-index.generated.json`;
- project-owned sanctioned profile policy из `automation/context/runtime-profile-policy.json`, если речь про checked-in team-shared presets;
- машинно-зависимые настройки из `env/local.json`, `env/wsl.json`, `env/.local/*.json`;
- push-only closeout contract, если репозиторий local-only и remote не настроен;
- template maintenance notes, которые уже живут в `docs/template-maintenance.md`.
