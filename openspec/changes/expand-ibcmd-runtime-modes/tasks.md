## 1. OpenSpec Contract

- [x] 1.1 Зафиксировать три `ibcmd.runtimeMode`: `standalone-server`, `file-infobase`, `dbms-infobase`.
- [x] 1.2 Зафиксировать mode-specific profile fields и secret indirection для DBMS-backed contour.
- [x] 1.3 Зафиксировать support matrix: `direct-platform` + `serverAccess.mode=data-dir` в scope, `pid/remote` вне scope.
- [x] 1.4 Зафиксировать machine-readable visibility `ibcmd.runtimeMode` и redacted mode context в artifacts.

## 2. Runtime Toolkit

- [x] 2.1 Обновить profile parser и validation layer под `ibcmd.runtimeMode` и mode-specific required fields.
- [x] 2.2 Исправить argv-сборку `ibcmd` для `create-ib` по реальному CLI contract.
- [x] 2.3 Исправить argv-сборку `ibcmd` для `dump-src` и `load-src`, включая full/partial import.
- [x] 2.4 Исправить argv-сборку `ibcmd` для `update-db`, включая non-interactive update policy.
- [x] 2.5 Обновить `doctor` и `summary.json`, чтобы они публиковали redacted `ibcmd` runtime mode/context.

## 3. Examples And Docs

- [x] 3.1 Обновить `env/README.md` и `README.md` под три topology modes.
- [x] 3.2 Добавить canonical examples для `standalone-server`, `file-infobase`, `dbms-infobase`.
- [x] 3.3 Явно задокументировать safety warning для DBMS-backed / cluster-derived contour.

## 4. Verification

- [x] 4.1 Добавить smoke coverage для mode-specific validation failures.
- [x] 4.2 Добавить smoke coverage для успешного argv assembly по всем трём `ibcmd.runtimeMode`.
- [x] 4.3 Добавить smoke coverage для partial import и update policy на `ibcmd` path.
- [x] 4.4 Прогнать `openspec validate --all --strict --no-interactive` и релевантные smoke tests.
