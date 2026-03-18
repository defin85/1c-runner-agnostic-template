## Контекст

Шаблон уже умеет прятать GUI через `platform.xvfb`, но linker compatibility contour для WSL/Linux пока решается только вручную через `env LD_PRELOAD=... ./scripts/...`. Это нарушает `script-first` подход репозитория: человек или агент вынужден помнить machine-specific префикс запуска, а canonical runtime path в `scripts/` остаётся неполным.

Для generated projects нужен repo-owned и проверяемый способ применить `LD_PRELOAD` только там, где он действительно нужен: к локальным `1cv8`/`1cv8c` при `runnerAdapter=direct-platform`.

## Цели

- Дать generated projects явный opt-in способ задавать `LD_PRELOAD` для локальных `1cv8`/`1cv8c` через structured runtime profile.
- Не менять публичные entrypoint-пути и intent capabilities.
- Сделать `env/wsl.example.json` готовым preset-ом для WSL/Arch Linux contour, где Linux runtime 1С требует `LD_PRELOAD`.
- Добавить fail-closed doctor/validation для отсутствующих библиотек, если contour включён.

## Не цели

- Не вводить generic `platform.env` или произвольные shell env overlays.
- Не пытаться автоматически угадывать library paths из конкретного дистрибутива.
- Не распространять contour на `remote-windows` или `vrunner`.
- Не подменять существующий `xvfb` contract; оба contour должны уметь сосуществовать.

## Решения

### 1. `LD_PRELOAD` задаётся как structured platform contour

В runtime profile появляется opt-in блок `platform.ldPreload`, который описывает linker compatibility policy для direct-platform launch path.

Минимальный shape:

- `platform.ldPreload.enabled`
- `platform.ldPreload.libraries`

`libraries` должен задаваться как массив строк с абсолютными путями к библиотекам, а не как готовая shell-строка. Launcher сам собирает из них значение `LD_PRELOAD`.

Если `enabled=false` или блок отсутствует, поведение direct-platform остаётся прежним.

### 2. Contour применяется только к локальным 1С binaries

По аналогии с `xvfb`, direct-platform adapter не должен безусловно подмешивать `LD_PRELOAD` к любой команде. Contour применяется только когда:

- runtime profile включил `platform.ldPreload.enabled=true`;
- исполняемый файл команды имеет basename `1cv8` или `1cv8c`.

Это правило должно работать и для standard-builder path, и для profile-defined command arrays. Команды `git`, `jq`, `bash` и любые custom wrappers с другим basename через этот contour не идут.

### 3. Реализация остаётся на adapter-layer

Launcher и builder’ы не должны заставлять пользователя писать `env LD_PRELOAD=...` в docs или `command` override. Parent shell передаёт adapter-специфичный контекст в `direct-platform` wrapper, а adapter уже решает, добавлять ли `LD_PRELOAD` перед `exec`.

Это сохраняет `runner-agnostic` contract: публичный entrypoint не меняется, а Linux-specific linker workaround остаётся за adapter boundary.

### 4. Doctor и runtime проверяют contour fail-closed

Если `platform.ldPreload.enabled=true`, toolkit должен:

- валидировать, что `platform.ldPreload.libraries` является непустым массивом;
- валидировать, что каждая запись является абсолютным путём;
- валидировать, что каждая библиотека существует локально;
- fail-closed завершаться и в `doctor`, и в runtime launch path до старта 1С, если обязательные preconditions не выполнены.

Автоматическое probing system libs в scope change не входит: contour работает только по явной structured настройке.

### 5. Артефакты отражают linker contour без утечки секретов

Capability summary и doctor summary должны публиковать structured `adapter_context`, отражающий включённый `LD_PRELOAD` contour.

Допустимо показывать:

- `enabled`
- массив library paths

Недопустимо:

- смешивать contour с unrelated secret-bearing env vars;
- писать в summary полный shell command prefix вроде `env LD_PRELOAD=... ./scripts/...`.

### 6. `env/wsl.example.json` становится canonical WSL/Arch Linux preset

Так как репозиторий по умолчанию ориентирован на WSL + Arch Linux, canonical Linux preset может показывать готовый `LD_PRELOAD` contour с системными библиотеками:

- `/usr/lib/libstdc++.so.6`
- `/usr/lib/libgcc_s.so.1`

При этом docs должны явно сказать, что на других Linux-дистрибутивах эти пути могут отличаться и профиль нужно подправить локально.

## Рассмотренные альтернативы

### Альтернатива A: документировать только ручной `env LD_PRELOAD=... ./scripts/...`

Отклонено. Это снова выносит operational truth из versioned runtime contract в ad-hoc shell usage.

### Альтернатива B: generic `platform.env`

Отклонено. Для текущего кейса это избыточно и слишком быстро размоет structured profile в свободную карту env overrides.

### Альтернатива C: автоматически определять подходящие системные библиотеки

Отклонено. Такой probing будет хрупким, distro-specific и плохо тестируемым в шаблоне.

### Альтернатива D: вшить `LD_PRELOAD` прямо в entrypoint scripts

Отклонено. Это сделает workaround глобальным и непрозрачным для профилей, которым он не нужен.

## Риски и компромиссы

- `env/wsl.example.json` станет более opinionated под Arch Linux, поэтому docs должны явно назвать это canonical preset-ом, а не универсальным Linux recipe.
- Абсолютные library paths являются host-specific, но не секретными. Это допустимо для локальных профилей и Arch/WSL example, но требует явной документации.
- Contour не поможет custom wrappers, которые запускают `1cv8` косвенно через другой basename; это сознательное ограничение первого этапа.

## План миграции

1. Добавить spec delta и profile schema contract для `platform.ldPreload`.
2. Реализовать adapter-level env contour с backward-compatible default и adapter context visibility.
3. Обновить `env/wsl.example.json`, docs и doctor.
4. Добавить smoke coverage для standard-builder, profile-command и fail-closed path.
5. После выпуска тега обновить generated project `do-rolf-sdd` через template update.

## Открытые вопросы

- Нет blocking open questions. Для первого этапа contract фиксируется как `enabled + libraries[] + basename(1cv8|1cv8c)`.
