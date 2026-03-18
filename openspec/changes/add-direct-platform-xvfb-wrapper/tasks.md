## 1. Contract

- [x] 1.1 Зафиксировать structured `platform.xvfb` contract для direct-platform runtime profiles.
- [x] 1.2 Зафиксировать, что `Xvfb` wrapper является opt-in и не меняет default behavior без явного включения.
- [x] 1.3 Зафиксировать `env/wsl.example.json` как canonical WSL/Linux preset для isolated GUI launches.
- [x] 1.4 Зафиксировать scope wrapper для standard-builder и profile-defined command arrays с basename `1cv8`/`1cv8c`.

## 2. Runtime

- [x] 2.1 Добавить adapter-level wrapper для запуска `1cv8`/`1cv8c` через `xvfb-run`, когда contour включён.
- [x] 2.2 Сохранить backward-compatible direct execution для профилей без `platform.xvfb.enabled=true`.
- [x] 2.3 Добавить doctor/runtime preflight checks для наличия `xvfb-run` и `xauth`.
- [x] 2.4 Добавить machine-readable visibility выбранного wrapper в capability summary и doctor summary.

## 3. Docs And Examples

- [x] 3.1 Обновить `README.md` и `env/README.md` с описанием `Xvfb` contour для WSL/Linux.
- [x] 3.2 Обновить `env/wsl.example.json` и related examples так, чтобы checked-in preset показывал canonical isolated path.

## 4. Verification

- [x] 4.1 Добавить smoke tests на success path для standard-builder с direct-platform + `platform.xvfb.enabled=true`.
- [x] 4.2 Добавить smoke tests на success path для profile-command contour с basename `1cv8`/`1cv8c`.
- [x] 4.3 Добавить fail-closed smoke tests для missing `xvfb-run`/`xauth` и убедиться, что default path без `platform.xvfb` не ломается.
- [x] 4.4 Добавить update/copy smoke, который подтверждает доставку `Xvfb` contour в generated project.
- [x] 4.5 Прогнать `openspec validate --strict --no-interactive` и релевантные smoke tests.
