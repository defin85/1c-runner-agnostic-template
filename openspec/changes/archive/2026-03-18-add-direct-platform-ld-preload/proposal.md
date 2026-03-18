# Change: add-direct-platform-ld-preload

## Why

В некоторых WSL/Linux контурах локальный `1cv8`/`1cv8c` не стартует штатно из-за несовместимости bundled `libstdc++`/`libgcc` платформы 1С с системными библиотеками хоста. Сейчас generated projects вынуждены обходить это ad-hoc запуском вида `env LD_PRELOAD=... ./scripts/...`, что выносит operational truth за пределы repo-owned runtime contract и плохо переживает `copier update`.

## What Changes

- Добавляется structured runtime contract для opt-in linker compatibility contour через `platform.ldPreload`, где минимальный shape это `enabled: boolean` и `libraries: string[]`.
- `direct-platform` adapter получает repo-owned способ выставлять `LD_PRELOAD` для локальных `1cv8`/`1cv8c`, когда contour явно включён в runtime profile.
- Contour распространяется и на standard-builder core capabilities, и на profile-defined command arrays, если их исполняемый файл имеет basename `1cv8` или `1cv8c`.
- `doctor`, examples и smoke tests начинают проверять наличие и wiring `LD_PRELOAD`-contour для direct-platform профилей, включая fail-closed preflight для отсутствующих library paths.
- Машиночитаемые артефакты получают structured visibility выбранного linker-env contour без утечки секретов.
- `env/wsl.example.json` становится canonical WSL/Arch Linux preset, показывающим repo-owned `LD_PRELOAD` contour для локального запуска Designer/Thin client.

## Out Of Scope

- Generic environment overrides для любых переменных окружения.
- Автоматическое определение или probing system library paths без явной настройки в runtime profile.
- Автоматическое применение `LD_PRELOAD` ко всем адаптерам и всем командам без явного opt-in.
- Решение Windows-specific runtime issues и non-Linux linker contours.

## Impact

- Affected specs:
  - `runtime-profile-schema`
  - `agent-runtime-toolkit`
- Affected code:
  - `scripts/adapters/direct-platform.sh`
  - `scripts/lib/capability.sh`
  - `scripts/lib/onec.sh`
  - `scripts/diag/doctor.sh`
  - `env/wsl.example.json`
  - `README.md`
  - `env/README.md`
  - `tests/smoke/*`
