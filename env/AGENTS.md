# Runtime Profiles

Этот каталог хранит runtime profile contract и его примеры.

- Начинайте с [env/README.md](README.md): это authoritative contract для `driver`, `command`, `unsupportedReason`, `xvfb`, `LD_PRELOAD` и layout policy.
- Project-owned sanctioned checked-in presets в generated repo объявляются через `automation/context/runtime-profile-policy.json`, а не через неявный drift в `env/*.json`.
- Shared runtime truth для generated repo живёт в `automation/context/runtime-support-matrix.md` и `automation/context/runtime-support-matrix.json`.
- `env/local.json`, `env/wsl.json`, `env/ci.json`, `env/windows-executor.json` и `env/.local/*.json` остаются `local-private`; не принимайте их за shared truth.
- Если contour ещё не wired, используйте fail-closed `unsupportedReason` вместо placeholder-команд с успешным выходом.
- Для first-pass проверки идите в `make agent-verify`, затем при необходимости в `./scripts/diag/doctor.sh --profile <file> --run-root <dir>`.
