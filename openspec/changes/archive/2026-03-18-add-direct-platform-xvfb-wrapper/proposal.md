# Change: add-direct-platform-xvfb-wrapper

## Why

При запуске `1cv8`/`1cv8c` из WSL/Linux через `direct-platform` Designer и другие GUI-компоненты 1С могут создавать реальные окна на хост-машине. Для generated projects это создаёт шум и мешает безопасно автоматизировать `dump-src`, `load-src`, `update-db` и другие direct-platform сценарии, где пользователь ожидает repo-owned способ изоляции GUI без ad-hoc shell-обёрток.

## What Changes

- Добавляется structured runtime contract для opt-in GUI isolation через `platform.xvfb`, где минимальный shape это `enabled: boolean` и `serverArgs: string[]`.
- `direct-platform` adapter получает repo-owned wrapper для запуска локальных `1cv8`/`1cv8c` под `xvfb-run`, когда это включено в runtime profile.
- Wrapper contour распространяется не только на standard-builder core capabilities, но и на profile-defined command arrays, если их исполняемый файл имеет basename `1cv8` или `1cv8c`.
- `env/wsl.example.json` становится каноническим preset для WSL/Linux с `Xvfb`-изоляцией GUI-contour.
- `doctor`, examples и smoke tests начинают проверять наличие и wiring `Xvfb`-contour для direct-platform профилей, включая fail-closed preflight для `xvfb-run` и `xauth`.
- Машиночитаемые артефакты получают явную structured visibility выбранного wrapper без утечки секретов.

- Вне scope:

- Windows-specific GUI isolation и удалённые display-contours.
- Автоматическое навязывание `Xvfb` всем адаптерам и всем командам без явного opt-in.
- Решение machine-specific проблем вроде `LD_PRELOAD` для конкретной локальной установки платформы.

## Impact

- Affected specs:
  - `runtime-profile-schema`
  - `agent-runtime-toolkit`
- Affected code:
  - `scripts/adapters/direct-platform.sh`
  - `scripts/lib/capability.sh`
  - `scripts/lib/onec.sh`
  - `scripts/diag/doctor.sh`
  - `env/*.example.json`
  - `README.md`
  - `env/README.md`
  - `tests/smoke/*`
