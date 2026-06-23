# Change: Перенос переиспользуемых runtime-контуров

## Why
В прикладном репозитории накопились общие runtime-утилиты для generated 1C projects: стабильный GUI-контур под Linux/WSL, загрузка расширений, диагностика после падений и быстрый YAxUnit feedback.

## What Changes
- Добавить direct-platform `xpra` wrapper и профильный блок `platform.xpra`.
- Добавить `check-x11-contour` как no-1C preflight.
- Уточнить `ibcmd` auth validation для файловых ИБ и пустых паролей.
- Добавить reusable CFE, port lease, web-client diagnostic и YAxUnit контуры как opt-in/operator-local инфраструктуру.
- Добавить минимальный обязательный `golden-baseline` контур как fail-closed project hook без Delans-эталонов.
- Обновить generated-project docs, runtime matrix, Makefile и smoke contracts.

## Impact
- Affected specs: `runtime-profile-schema`, `ibcmd-capability-drivers`, `template-ci-contours`, `generated-runtime-support-matrix`
- Affected code: `scripts/`, `tests/smoke/`, `automation/context/templates/`, `copier.yml`, `Makefile`, `docs/`
