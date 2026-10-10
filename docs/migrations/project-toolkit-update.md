# Обновление проекта, созданного до точек расширения и проектного Python-окружения

Документ для проекта, созданного из шаблона до выпуска, в котором появились `Makefile.project`, `make.project.ps1`, проектные `pyrightconfig.json` с `extends` и `ruff.toml` с `extend`, записи платформ в таблице поддержки сред и цель `make verify-types`. Обновление выполняется обычной командой `make template-update` (`./make.ps1 template-update`), но часть проектных правок она удаляет без предупреждения, а часть новых проверок `make agent-verify` не проходит без действий в проекте.

Признаки такого проекта:

- в `Makefile` или `make.ps1` есть собственные цели проекта, а файлов `Makefile.project` и `make.project.ps1` нет;
- проверка типов запускается через `make type-check`, рядом есть `make type-check-update-baseline` и файл baseline basedpyright;
- у контуров в `automation/context/runtime-support-matrix.json` нет поля `platforms`.

Порядок: шаги раздела «До обновления», затем `make template-update`, затем шаги раздела «После обновления». Все шаги выполняются в рабочем дереве без незакоммиченных изменений, чтобы `git diff` после обновления показывал только изменения шаблона.

## До обновления

### 1. Записать результат `make agent-verify`

Запустите `make agent-verify` и сохраните вывод. После обновления по нему видно, какие сбои появились из-за обновления, а какие были раньше.

### 2. Найти проектные правки в файлах шаблона

`template-update` заменяет файлы из `automation/context/template-managed-paths.txt` версией шаблона. Всё, что проект дописал в такие файлы после прошлого обновления, пропадёт: собственные цели в `Makefile` и `make.ps1`, разделы в документах `docs/agent/`, функции в модулях `scripts/python/`.

Список таких файлов:

```bash
base="$(git log -n 1 --format=%H -- .template-overlay-version)"
git diff --name-only "$base" HEAD | grep -Fx -f automation/context/template-managed-paths.txt
```

Для каждого файла из списка решите, куда перенести правку: в точку расширения из шагов 3–4, в собственный документ или модуль проекта. Если проектные тесты импортируют функции, которые проект добавлял в модули `scripts/python/` шаблона, после обновления эти тесты упадут с `ImportError` при сборе тестов `make verify-python-tests`; перенесите такие функции в модуль проекта.

### 3. Перенести собственные цели `make` в `Makefile.project` и `make.project.ps1`

`Makefile` и `make.ps1` принадлежат шаблону. Собственные цели проекта перенесите:

- из `Makefile` в `Makefile.project` — `Makefile` подключает его строкой `-include Makefile.project`;
- из `make.ps1` в `make.project.ps1` — `make.ps1` подключает его, если файл есть.

`template-update` эти файлы не создаёт и не меняет. Имя цели проекта не должно совпадать с целью шаблона: `make` выдаст предупреждение `overriding recipe`, а `./make.ps1` завершится с ошибкой `make.project.ps1 must not redefine template target`. Полный список целей шаблона печатают `make help` и `./make.ps1 help`. Например, цель `technological-log` теперь есть в шаблоне; если проект объявлял её сам, удалите проектное объявление.

Пример для цели `project-report`:

```make
.PHONY: project-report

project-report:
	@./scripts/project/report.sh
```

```powershell
$projectTargets["project-report"] = @((Join-Path $root "scripts\project\report.ps1"))
$projectHelp += "  ./make.ps1 project-report"
```

Формат точек расширения описан в [docs/template-maintenance.md](../template-maintenance.md#project-owned-extension-points).

### 4. Вынести собственный текст из блока шаблона в `AGENTS.md`

`template-update` удаляет из `AGENTS.md` всё между строками `<!-- RUNNER_AGNOSTIC_TEMPLATE:START -->` и `<!-- RUNNER_AGNOSTIC_TEMPLATE:END -->` и записывает блок заново в конец файла. Собственные правила проекта, оказавшиеся внутри блока, перенесите выше строки `<!-- RUNNER_AGNOSTIC_TEMPLATE:START -->`. Текст вне блока обновление сохраняет.

### 5. Вынести собственный текст из `runtime-support-matrix.md`

Команда миграции таблицы поддержки сред (шаг 5 после обновления) пересобирает `automation/context/runtime-support-matrix.md` из JSON целиком, а `make agent-verify` требует, чтобы файл совпадал с результатом сборки. Собственные разделы этого файла (описание целевого релиза, заметки о средах) перенесите в другой документ проекта, например в `automation/context/project-map.md`. Машинные поля можно оставить в JSON: команда сохраняет все существующие поля.

## Обновление

```bash
make template-update
```

PowerShell: `./make.ps1 template-update`. До коммита просмотрите `git diff`: удалённые строки в `Makefile`, `make.ps1`, `AGENTS.md` и документах шаблона показывают, что не было перенесено на шагах 2–5.

## После обновления

### 1. Перейти с `make type-check` на `make verify-types`

- Цели `type-check`, `type-check-setup`, `type-check-update-baseline` и `python-setup` удалены вместе со сценариями `scripts/qa/type-check-update-baseline.sh` и `.ps1`. Проверка типов — `make verify-types` (`./make.ps1 verify-types`), проверка стиля — `make verify-python-lint`, быстрые тесты — `make verify-python-tests ARGS="--fast"`. Отдельной подготовки окружения нет: инструменты запускаются через `uv run --locked`.
- Найдите старые вызовы в документах, CI и сценариях проекта и замените их:

  ```bash
  rg -n "make type-check|type-check-setup|type-check-update-baseline|python-setup" --glob '!openspec/changes/archive/**'
  ```

- Baseline basedpyright больше не допускается. Удалите файлы `basedpyright-baseline*` и `.basedpyright/baseline*`, удалите ключи `baselineFile` и `ignore` из `pyrightconfig.json` и исправьте ошибки типов, которые скрывал baseline.
- Добавьте в `pyrightconfig.json` строку `"extends": "scripts/qa/pyright-base.json"`. Режим проверки не ниже `standard`; понижать правила нельзя.
- Каждый `.py`-файл проекта должен лежать внутри одного из корней `include` в `pyrightconfig.json` или попадать под `exclude`. Если `make verify-types` пишет `Python files outside pyrightconfig.json include roots are not type-checked`, добавьте корни перечисленных файлов в `include` либо, если эти файлы осознанно не проверяются по типам, в `exclude`.

### 2. Закрепить версии `ruff`, `basedpyright` и `pytest` и подключить базовые правила `ruff`

`pyproject.toml`, `uv.lock` и `requirements-dev.txt` принадлежат проекту, а минимальные версии инструментов задаёт шаблон. `make verify-types` печатает команду исправления, если версия ниже минимальной или пакет не закреплён. Если `ruff` нет в окружении `uv` проекта, `make verify-python-lint` до запуска `ruff` завершается ошибкой `ruff is not installed in the project uv environment (uv.lock)` и печатает ту же команду исправления. Исправление:

```bash
uv add --dev "ruff>=<минимальная версия из сообщения>"
uv export --locked --format requirements-txt --no-hashes --no-emit-project --no-annotate --output-file requirements-dev.txt
```

`ruff.toml` теперь тоже принадлежит проекту (Р18), а правила `ruff` лежат в template-managed `scripts/qa/ruff-base.toml`. Если `ruff.toml` в проекте не было, `template-update` создаёт его со строкой `extend = "scripts/qa/ruff-base.toml"`. Существующий `ruff.toml` обновление не меняет, поэтому прежний файл без `extend` `make verify-python-lint` отклоняет с ошибкой `ruff.toml must keep extend = "scripts/qa/ruff-base.toml"`. Исправление:

1. Сохраните из прежнего `ruff.toml` только собственные настройки проекта: исключения файлов проекта и исключения правил для них. Настройки, которые совпадают с базой шаблона (`target-version`, `line-length`, `select`, исключение `automation/vendor` и `.artifacts`), удалите.
2. Запишите `ruff.toml` в таком виде, заменив пути примера путями проекта:

   ```toml
   extend = "scripts/qa/ruff-base.toml"
   extend-exclude = ["tests/contract"]

   [lint.per-file-ignores]
   "scripts/project/legacy/**" = ["E402"]
   ```

   Используйте `extend-exclude`, а не `exclude`: `exclude` заменяет стандартный список исключений `ruff` (`.git`, `.venv` и другие). Новые правила добавляйте через `extend-select`; `select` заменяет правила базы.
3. Если настройки `ruff` лежали в разделе `[tool.ruff]` файла `pyproject.toml`, перенесите их в `ruff.toml` и удалите раздел: при наличии `ruff.toml` `ruff` раздел `[tool.ruff]` не читает.
4. Запустите `make verify-python-lint`. Проверка отклоняет `ruff.toml`, если `ignore` или `extend-ignore` отключает правило базы, или если шаблон пути в `exclude`, `extend-exclude`, `lint.exclude`, `format.exclude`, `include` или `per-file-ignores` с правилом базы захватывает Python-файл из `automation/context/template-managed-paths.txt`. Сообщение называет ключ, шаблон пути и примеры таких файлов; сузьте шаблон до файлов проекта.

Правила базы применяются ко всему Python-коду проекта, кроме исключённых проектом файлов. Автоматически исправимые нарушения устраняют `uv run --locked ruff check --fix .` и `uv run --locked ruff format .`; остальные исправьте вручную.

### 3. Обновить ссылки на удалённые разделы о `meta-*` и `form-*`

Навыки `meta-*`, `form-*` (кроме `form-patterns`) и `cfe-borrow` выведены, их заменяет CLI `metadata` и навык `metadata-use` (подробности — [imported-skills-runtime-profile.md](imported-skills-runtime-profile.md)). Если проект дописывал раздел о них в документ шаблона, после обновления этого раздела нет, и `make check-agent-docs` пишет `missing markdown anchor in <файл>:<строка>: <ссылка>`. Замените такие ссылки ссылкой на [`.agents/skills/metadata-use/SKILL.md`](../../.agents/skills/metadata-use/SKILL.md) или на собственный документ проекта, куда перенесён раздел на шаге 2 до обновления. Для форм основной конфигурации в расширении используйте навык `cfe-form-workflow`.

### 4. Разрешить собственные профили в корне `env/`

`make check-agent-docs` отклоняет каждый `env/*.json`, который не входит в канонический набор шаблона и не перечислен в `rootEnvProfiles.sanctionedAdditionalProfiles` файла `automation/context/runtime-profile-policy.json`. Сообщение: `generated runtime profile policy leaves unsanctioned checked-in root profiles: <пути>`.

- Профиль или пример, который нужен всей команде и хранится в git, добавьте в `sanctionedAdditionalProfiles`, например `"env/team-shared.json"`. Такой файл должен существовать, не должен называться как канонический профиль (`env/local.json`, `env/local.example.json` и т. п.), не должен содержать `TODO:`, а команды `smoke` и `bdd` в нём должны вызывать `make <цель>` или сценарий репозитория.
- Локальный профиль одного оператора перенесите в `env/.local/`.

### 5. Добавить записи платформ в таблицу поддержки сред

`make agent-verify` требует для каждого контура в `automation/context/runtime-support-matrix.json` записи `platforms.linux` и `platforms.windows`. Без них проверка завершается ошибкой `runtime support matrix is missing capability/platform entry: <контур>/<платформа>`. `template-update` таблицу проекта не меняет. Записи добавляет команда:

```bash
./scripts/template/migrate-runtime-support-matrix.sh
```

PowerShell: `.\scripts\template\migrate-runtime-support-matrix.ps1`.

Что делает команда:

- дописывает только отсутствующие записи `platforms.linux` и `platforms.windows`; существующие записи и остальные поля JSON не меняет;
- каждая новая запись не проверена на платформе: `evidence: null`, `status` повторяет статус контура, `evidenceClass` — `contract-only` для контуров слоя `safe-local` и `contract-plus-live` для остальных; для контуров, которые работают только в Linux, запись `windows` получает `status: unsupported`;
- пересобирает `automation/context/runtime-support-matrix.md` из JSON тем же кодом, которым шаблон создаёт таблицу; прежнее содержимое Markdown-файла заменяется;
- печатает добавленные пары `<контур>/<платформа>`; повторный запуск ничего не меняет и сообщает `nothing changed`.

После запуска проверьте `git diff automation/context/runtime-support-matrix.json automation/context/runtime-support-matrix.md`. Если у контура вне слоя `safe-local` статус `supported`, новая запись требует живого доказательства (`evidence.fingerprint`, `timestamp`, `expiresAt`), иначе проверка сообщит `runtime support matrix lacks current live evidence`; укажите доказательство или понизьте статус записи. Новые контуры шаблона перенесите в таблицу по шагу 4 раздела «После обновления» в [docs/template-maintenance.md](../template-maintenance.md#после-обновления) и снова запустите команду миграции, чтобы добавить им записи платформ и пересобрать Markdown.

### 6. Исправить пути, которых нет в репозитории

`make check-agent-docs` проверяет, что пути в документах проекта существуют в репозитории. Сообщение `representative path is missing: <документ> -> <путь>` означает, что документ называет файл, которого нет в git, например локальный файл, исключённый через `.gitignore`. Исправьте путь или перепишите фразу без пути в обратных кавычках.

### 7. Перейти с BSL Language Server на `bsl-analyzer`

`make analyze-bsl` больше не запускает jar BSL Language Server: команда получает диагностики от MCP-сервера `bsl-analyzer`. Переменные `BSL_LANGUAGE_SERVER_JAR`, `BSL_LANGUAGE_SERVER_CONFIG`, `BSL_LS_XMX` и `BSL_REPORT_DIR` не читаются. Если они остались в `.env`, профиле CI или собственных целях `Makefile.project`, удалите их вместе с загрузкой jar и файлом настроек BSL Language Server.

1. Настройте сервер по [bsl-analyzer-workspace-runbook.md](../agent/bsl-analyzer-workspace-runbook.md): `bsl-analyzer-app` в `PATH` или в `BSL_ANALYZER_EXECUTABLE`, реестр `env/.local/bsl-onec-connections.json` (для анализа достаточно `{"connections": {}}`) и каталог исходников с `Configuration.xml` (`BSL_ANALYZER_SOURCE_CANDIDATES`, по умолчанию `src/cf`). Без этого команда завершается с ошибкой `bsl-analyzer is not configured`.
2. Запустите `make analyze-bsl`. Каждая диагностика, которую проект принимает осознанно, записывается точным исключением в `bsl-analyzer-exceptions.json` (формат — в том же документе). Отключения правил BSL Language Server в конфигурации и комментариях `// BSLLS:<Правило>-off` на результат `bsl-analyzer` не влияют.
3. Если CI проекта запускал `make analyze-bsl` с BSL Language Server, перенесите шаг на машину, где установлен `bsl-analyzer-app`, или уберите его из CI.

### 8. Обновить производный контекст и проверить проект

```bash
./scripts/llm/export-context.sh --write
make agent-verify
```

Сравните результат с выводом, сохранённым на шаге 1 до обновления. Оставшиеся сбои относятся к собственным файлам проекта, если сообщение называет путь вне `automation/context/template-managed-paths.txt`.

### 9. Включить необязательные модули, если они нужны проекту

Заготовки модулей площадки и КД 2.1 приходят в `automation/optional/`, но сами модули не включаются. Если проект хранит свои площадочные или КД-материалы, включите модуль после обновления отдельным коммитом:

```bash
make optional-module-init MODULE=customer-site-operations   # или kd21-migration
```

Команда завершается с ошибкой без изменений, если хотя бы один целевой путь модуля уже существует (например, `infra/site/` или `migration/kd21/`). Если проект уже держит материалы по этим путям, переместите их во временный каталог, выполните команду, затем перенесите свои материалы в созданные каталоги поверх заготовки. Созданные пути команда записывает в `automation/context/template-update-preserve-paths.txt`, и следующие `template-update` их не меняют. Формат заготовок и полное поведение команды описаны в [docs/template-maintenance.md](../template-maintenance.md#необязательные-модули).
