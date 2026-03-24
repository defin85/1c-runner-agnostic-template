## Context

У шаблона уже есть сильный reusable слой для generated repositories:

- versioned launcher scripts;
- runtime profile contract;
- project-scoped skills;
- agent docs и baseline verification path.

Но generated repository это уже не template source repo и не должен воспринимать template-owned docs как свою доменную truth.

Наблюдаемая проблема состоит не только в качестве onboarding, а в отсутствии update-safe ownership model:

- `README.md` одновременно играет роль template overview и будущего project README;
- `AGENTS.md` получает reusable overlay, но не имеет формального разделения между template-managed guidance и project-owned truth;
- `automation/context/templates/*` задаёт skeletons, но generated repo не получает явно описанный curated-vs-generated split;
- `scripts/llm/export-context.sh` сегодня моделирует source-repo export flow и не подходит как безопасный generated-project inspection path;
- fixture smoke для `copier` уже показывает, что advertised maintenance path сам по себе является частью agent-facing contract и должен проверяться как first-class artifact.

## Goals

- Зафиксировать ownership classes для agent-facing artifacts generated project.
- Дать generated repository правильную first-screen identity: это конкретный проект, а не шаблон.
- Разделить curated project truth и generated-derived inventories.
- Сохранить безопасный `copier update` без перетирания project-owned truth.
- Сделать context/export/verification contract безопасным для read-first agent workflows.

## Non-Goals

- Извлекать полную бизнес-модель из `src/cf/**` без участия команды проекта.
- Доставлять machine-specific Codex/MCP config как часть checked-in template contract.
- Подменять project-owned domain docs template-managed generated output.

## Decisions

### 1. Ввести четыре ownership class

Generated-project agent surface делится на четыре класса:

1. `template-managed`
   - reusable runbooks, shared skills, CI contours, example configs, managed blocks;
   - эти артефакты могут обновляться через template update.
2. `seed-once / project-owned`
   - project identity и curated truth про конкретный generated repo;
   - template может создать начальную версию на `copier copy`, но не должен потом молча перетирать эти файлы.
3. `generated-derived`
   - machine-generated inventories и индексы;
   - они регенерируются через явный repo-owned command и проверяются на freshness.
4. `local-private`
   - machine-specific secrets, runtime profiles, MCP paths, personal Codex overrides;
   - эти настройки не входят в checked-in template contract.

### 2. Развести reusable contract и project truth по разным артефактам

Шаблон должен владеть reusable operational contract, а не смысловым описанием конкретного бизнеса.

Практическая раскладка:

- `README.md` в generated repo должен быть project-first и отвечать на вопросы «что это за проект», «где код», «какой safe verification path».
- template maintenance guidance должна жить в отдельном документе и не быть primary onboarding path.
- root `AGENTS.md` должен оставаться коротким router-файлом; reusable template rules можно обновлять через managed block, а project-specific truth должна жить в project-owned docs.

### 3. Seed-once файлы должны быть concrete, а не placeholder-only

Generated repo не должен стартовать с raw template placeholders вроде `<context-1>` или инструкций, адресованных template source repo.

Начальный project context должен использовать Copier answers и текущий repo layout, чтобы сразу быть хотя бы минимально truthful:

- project name / description;
- known source roots (`src/cf`, `src/cfe`, `src/epf`, `src/erf`);
- known verification entrypoints;
- ownership rules, по которым команда позже enrich-ит этот контекст.

### 4. Curated context и generated inventory нельзя смешивать

Curated project docs и generated inventories обслуживают разные цели:

- curated docs нужны агенту как trustable human-maintained summary;
- generated inventories нужны как machine-readable evidence about current tree.

Поэтому change предлагает:

- curated `project-map.md` как `seed-once / project-owned` truth;
- generated metadata/index artifacts с явным suffix/path, который показывает generated status;
- deterministic refresh path для generated artifacts.

### 5. Context export должен быть side-effect-transparent

Read-first agent workflow не должен случайно писать в repo только потому, что агент хочет понять контракт.

Поэтому repo-owned export/update tooling должен иметь:

- `--help` или эквивалентный usage path без записи;
- `--check` / preview mode без мутаций;
- отдельный explicit write path;
- детерминированные имена output artifacts.

### 6. CI должен проверять ownership contract, а не только shell/runtime

Если template advertises:

- `copier update` как maintenance path;
- generated-project onboarding docs;
- generated context artifacts;

то эти вещи должны стать CI/smoke contract:

- fixture smoke подтверждает advertised maintenance path;
- static checks ловят raw placeholders и ownership drift;
- freshness checks подтверждают, что generated-derived artifacts можно валидировать машинно.

## Alternatives Considered

### Альтернатива A: оставить generated repos полностью на усмотрение конечной команды

Отклонено. Это снижает конфликтность update path, но убирает reusable onboarding surface и снова заставляет каждого агента собирать contract из сырых файлов.

### Альтернатива B: сделать всю agent-facing документацию template-managed

Отклонено. Тогда template update будет постоянно конфликтовать с project truth и с большой вероятностью перетирать важный контекст конкретного продукта.

### Альтернатива C: пытаться автоматически строить полную доменную карту из `src/cf`

Отклонено как первый шаг. Для больших 1С-экспортов это дорого, шумно и рискованно как source of truth. Safe first step — curated project map плюс generated-derived inventory.

## Migration Plan

Для новых generated repos:

- ownership classes и файлы применяются сразу при `copier copy`.

Для существующих generated repos:

- template update должен добавлять missing template-managed files и managed blocks;
- project-owned files должны сохраняться как есть или получать только non-destructive bootstrap path;
- generated-derived artifacts могут появиться как новые файлы, refresh-имые явным command path.

## Risks / Trade-offs

- Слишком жёсткий placeholder lint может сделать свежесгенерированный repo невалидным до ручной доработки.
  - Митигируем через concrete starter content из Copier answers, а не raw placeholders.
- Слишком много ownership classes усложнит mental model.
  - Митигируем коротким documented contract и CI checks только на важные границы.
- Попытка сразу решить и domain mapping, и update safety приведёт к переусложнению.
  - Митигируем тем, что change ограничен reusable template layer и truthful starter context.
