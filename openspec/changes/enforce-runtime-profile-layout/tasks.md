## 1. Contract

- [x] 1.1 Зафиксировать canonical allowlist для root-level runtime profiles в `env/`.
- [x] 1.2 Зафиксировать `env/.local/` как место для ad-hoc и machine-specific profiles.
- [x] 1.3 Зафиксировать, что default runtime resolution не сканирует `env/.local/` и не меняет текущий `env/local.json` path.
- [x] 1.4 Зафиксировать, что layout drift отражается через non-fatal `doctor` warning, а не через hard runtime failure.

## 2. Template Layout And Runtime

- [x] 2.1 Обновить ignore rules и template layout так, чтобы `env/.local/` был discoverable и не попадал в Git.
- [x] 2.2 Добавить `doctor` detection для неожиданных `env/*.json` в корне `env/`, которые не входят в allowlist и не являются `*.example.json`.
- [x] 2.3 Добавить machine-readable warning section в `doctor` summary для runtime profile layout drift.
- [x] 2.4 Сохранить существующий default profile resolution без implicit fallback на `env/.local/*`.

## 3. Docs

- [x] 3.1 Обновить `env/README.md` и `README.md` с описанием allowlist и `env/.local/`.
- [x] 3.2 Добавить marker file или README в `env/.local/`, чтобы generated project показывал canonical место для ad-hoc profiles.

## 4. Verification

- [x] 4.1 Добавить smoke test, что `doctor` предупреждает о root-level drift, но не падает, если runtime preconditions соблюдены.
- [x] 4.2 Добавить smoke test, что `env/.local/` и обновлённые ignore rules приезжают в generated project через copy/update.
- [x] 4.3 Прогнать `openspec validate --strict --no-interactive` для change.
