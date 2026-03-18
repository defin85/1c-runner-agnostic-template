## Контекст

Сейчас шаблон уже описывает канонические runtime profiles, но фактически не ограничивает layout локальных JSON-файлов в `env/`. В живом проекте это быстро приводит к drift:

- канонические профили (`local`, `wsl`, `ci`, `windows-executor`) перемешиваются с ad-hoc файлами;
- default path (`env/local.json`) остаётся прежним, но discoverability падает;
- docs перестают совпадать с operational reality.

Проблема не в самом существовании временных профилей, а в отсутствии выделенного места для них.

## Цели

- Сделать корень `env/` коротким и предсказуемым.
- Сохранить возможность локальных экспериментов без необходимости коммитить их или придумывать новые root-level naming conventions.
- Дать `doctor` machine-readable visibility по layout drift, не превращая это в hard blocker для runtime execution.
- Не менять default resolution semantics.

## Не цели

- Не запрещать пользователю вручную запускать любой профиль через `--profile`.
- Не делать runtime launch fail-closed только по layout drift.
- Не превращать `env/.local/` в обязательный runtime source для default path.
- Не добавлять глобальный файловый policy engine за пределами runtime profile JSON.

## Решения

### 1. Корень `env/` получает allowlist

В корне `env/` остаются только:

- versioned examples `*.example.json`;
- canonical local working profiles:
  - `env/local.json`
  - `env/wsl.json`
  - `env/ci.json`
  - `env/windows-executor.json`

Любой другой локальный JSON profile в корне `env/` считается layout drift.

### 2. Для ad-hoc profiles вводится `env/.local/`

`env/.local/` становится явным sandbox-каталогом для:

- временных профилей вроде `develop.json`;
- machine-specific variants;
- специальных `ibcmd`/experiment contours.

Это лучше, чем плодить новые root-level filenames, потому что canonical surface остаётся неизменной.

### 3. Контроль делается через `doctor`, не через hard runtime failure

Layout drift важен для maintainability и discoverability, но не влияет напрямую на correctness runtime invocation. Поэтому:

- `doctor` должен отражать drift как warning/non-canonical check;
- warning должен быть machine-readable и human-readable;
- статус `doctor` не должен становиться `failed`, если все runtime preconditions в остальном соблюдены.

### 4. Default resolution не меняется

`resolve_runtime_profile_path()` продолжает автоматически выбирать только:

1. `--profile`
2. `ONEC_PROFILE`
3. `env/local.json`

`env/.local/*` никогда не используется как implicit default source.

### 5. Template должен явно доставлять новый layout

Чтобы generated project сразу показывал правильный способ хранения ad-hoc profiles, template update/copy должны поставлять:

- ignore rules для `env/.local/`;
- discoverable каталог `env/.local/` с marker file;
- docs, которые описывают allowlist и drift policy.

## Рассмотренные альтернативы

### Альтернатива A: запретить любые дополнительные JSON-файлы в `env/`

Отклонено. Это слишком жёстко для реальных проектов, где временные профили действительно нужны.

### Альтернатива B: ничего не менять, оставить только docs convention

Отклонено. Без runtime-visible warning convention быстро теряет силу.

### Альтернатива C: автоматически сканировать `env/` и выбирать “похожий” профиль

Отклонено. Это ломает predictability default path и повышает риск запуска не того контура.

## Риски и компромиссы

- Existing generated projects с ad-hoc profiles в корне `env/` начнут видеть warning в `doctor`; это ожидаемая и желаемая обратная связь.
- `env/.local/` остаётся convention, а не жёстким ACL. Пользователь всё ещё сможет явно передать любой `--profile`, и это нормально.
- Потребуется аккуратно выбрать machine-readable shape warning, чтобы он не ломал существующие consumer expectations `doctor` summary.

## План миграции

1. Добавить spec delta на canonical layout и doctor warning contract.
2. Обновить docs и template layout (`.gitignore`, `env/.local/` marker).
3. Добавить `doctor`-проверку unexpected root-level `env/*.json`.
4. Добавить smoke на copy/update delivery и на non-fatal warning path.

## Открытые вопросы

- Нет blocking open questions. В первом релизе policy будет warning-only, без hard failure runtime launch.
