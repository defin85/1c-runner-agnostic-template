# Change: enforce-runtime-profile-layout

## Why

В generated projects локальные runtime profiles быстро расползаются в корне `env/`: появляются `develop.json`, `do-rolf.json`, `tmp.json`, `*-ibcmd.json` и другие ad-hoc файлы. Это размывает канонический layout, делает default path менее очевидным, а документацию про `env/local.json`, `env/wsl.json`, `env/ci.json` и `env/windows-executor.json` фактически недостоверной.

Нужен repo-owned контроль, который удерживает корень `env/` коротким и предсказуемым, но не ломает локальные эксперименты и machine-specific profiles.

## What Changes

- Вводится канонический layout для runtime profiles в generated project:
  - versioned examples остаются в корне `env/` как `*.example.json`;
  - canonical local working profiles в корне `env/` ограничиваются фиксированным allowlist;
  - ad-hoc и экспериментальные локальные profiles переносятся в `env/.local/`.
- Шаблон начинает поставлять `env/.local/` как явное место для временных и machine-specific runtime profiles.
- `doctor` получает non-fatal layout drift check: он должен предупреждать о неожиданных `env/*.json` в корне каталога `env/`, если они не входят в allowlist и не являются versioned examples.
- `.gitignore`, docs и update/copy flow синхронизируются с новым layout contract.
- Default runtime resolution не меняется: launcher по-прежнему автоматически использует только `env/local.json`, если профиль не передан явно.

## Out Of Scope

- Жёсткий fail runtime launch только из-за лишних локальных profile files.
- Автоматическая миграция или перенос всех существующих ad-hoc profiles в уже созданных проектах.
- Изменение semantics `ONEC_PROFILE` или default resolution order.
- Generic policy для любых файлов под `env/` кроме runtime profiles JSON.

## Impact

- Affected specs:
  - `runtime-profile-schema`
  - `agent-runtime-toolkit`
- Affected code:
  - `.gitignore`
  - `env/README.md`
  - `README.md`
  - `scripts/diag/doctor.sh`
  - `scripts/lib/runtime-profile.sh` (если потребуется только для explicit helper messaging, без смены default resolution)
  - `tests/smoke/runtime-doctor-contract.sh`
  - `tests/smoke/copier-update-ready.sh`
