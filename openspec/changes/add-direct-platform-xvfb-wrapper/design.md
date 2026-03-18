## Контекст

Шаблон уже даёт structured runtime profiles и стабильные shell entrypoints, но сейчас direct-platform adapter делает только `exec "$@"`. Из-за этого generated project не имеет канонического repo-owned способа скрыть GUI Designer/Thin Client при запуске из WSL/Linux.

Для batch-запусков 1С это не всегда функциональный блокер, но это важный operational requirement: агент или CI не должны открывать окна на хосте, если проект явно выбрал headless/isolated contour.

## Цели

- Дать generated projects явный opt-in способ запускать `1cv8`/`1cv8c` под `Xvfb` через structured runtime profile.
- Не менять публичные entrypoint-пути и intent capabilities.
- Сделать `env/wsl.example.json` готовым preset-ом для изолированных GUI launches в WSL/Linux.
- Добавить fail-closed doctor/validation для missing `xvfb-run`, если contour включён.

## Не цели

- Не вводить Windows-specific display wrapper.
- Не переводить `remote-windows` или `vrunner` на новый contract в этом change.
- Не решать автоматически произвольные локальные dependency issues платформы.

## Решения

### 1. Xvfb задаётся как structured platform contour

В runtime profile появляется opt-in блок `platform.xvfb`, который описывает GUI isolation для direct-platform launch path.

Минимальный shape:

- `platform.xvfb.enabled`
- `platform.xvfb.serverArgs`

`serverArgs` должен задаваться как массив строк, а не как shell-строка. Это сохраняет profile structured и machine-validated.

Если `enabled=false` или блок отсутствует, поведение direct-platform остаётся прежним.

### 2. Wrapper применяется только к локальным 1С GUI binaries

`direct-platform` adapter не должен безусловно оборачивать любую команду в `xvfb-run`. Wrapper применяется только когда:

- runtime profile включил `platform.xvfb.enabled=true`;
- исполняемый файл команды имеет basename `1cv8` или `1cv8c`.

Это правило должно работать и для standard-builder path, и для profile-defined command arrays. Команды `git`, `jq`, `bash` и любые custom wrappers с другим basename через `xvfb-run` не идут.

В scope первого этапа не входит распознавание произвольных shell wrappers поверх 1С-бинаря.

### 3. WSL preset становится canonical isolated contour

`env/wsl.example.json` должен явно показывать `Xvfb`-контур как recommended path для Linux/WSL-first direct-platform запусков.

При этом:

- `env/local.example.json` остаётся minimal mixed `designer/ibcmd` contour;
- Windows preset не получает `Xvfb`-поля.

### 4. Doctor, runtime и smoke должны проверять contour end-to-end

Если `platform.xvfb.enabled=true`, toolkit должен:

- валидировать наличие `xvfb-run` и `xauth`;
- fail-closed завершаться и в `doctor`, и в runtime launch path до старта 1С, если обязательные preconditions не выполнены;
- отражать выбранный wrapper в machine-readable artifacts через structured `adapter_context`;
- иметь smoke coverage для success path и fail-closed path.

Для диагностики wrapper должен использовать repo-owned defaults, а не перекладывать их на profile:

- `xvfb-run -a` для auto server number;
- `--error-file=/dev/stderr`, чтобы не терять вывод `Xvfb` и `xauth`.

## Рассмотренные альтернативы

### Альтернатива A: документировать только ручной `xvfb-run ./scripts/...`

Отклонено. Это снова выносит operational truth из repo-owned contract в ad-hoc shell usage и плохо обновляется через template.

### Альтернатива B: всегда включать `xvfb-run` для `direct-platform`

Отклонено. Это добавляет лишнюю обязательную зависимость для headless/server-only контуров, которым GUI isolation не нужна.

### Альтернатива C: добавлять `command` override в каждом generated project

Отклонено. Это работает как локальный обход, но не решает template-level consistency и не защищает от drift при `copier update`.

### Альтернатива D: хранить `serverArgs` как shell-строку

Отклонено. Это снова превращает structured runtime profile в partially free-form shell contour и усложняет валидацию.

## Риски и компромиссы

- Появляется новая локальная зависимость `xvfb-run` и `xauth` для WSL/Linux preset-ов, поэтому doctor и docs должны явно это объяснять.
- Wrapper на adapter-layer должен не ломать существующие direct-platform smoke fixtures, поэтому нужно сохранить backward-compatible default.
- В scope change не входит автоматическая классификация всех GUI/non-GUI custom commands; первый этап ограничивается basename `1cv8`/`1cv8c`.

## План миграции

1. Добавить spec delta и profile schema contract для `platform.xvfb`.
2. Реализовать direct-platform wrapper с backward-compatible default и adapter context visibility.
3. Обновить `env/wsl.example.json`, docs и doctor.
4. Добавить smoke coverage для standard-builder, profile-command и fail-closed path.
5. После выпуска тега обновить generated project `do-rolf-sdd` через template update.

## Открытые вопросы

- Нет blocking open questions. Для первого этапа contract фиксируется как `enabled + serverArgs[] + basename(1cv8|1cv8c)`.
