# Template Maintenance

Этот документ описывает ongoing template maintenance path для generated repos.
Он не является primary onboarding или feature-delivery workflow.
Для source repo release tag используйте отдельный runbook: [docs/template-release.md](template-release.md).

## Когда сюда идти

- нужно проверить, есть ли новый wrapper overlay release;
- нужно подтянуть `template-managed` слой в generated repo;
- нужно понять, какие части репозитория overlay apply может менять автоматически.

## Канонические команды

```bash
make template-check-update
make template-update
```

Или напрямую:

```bash
./scripts/template/check-update.sh
./scripts/template/update-template.sh
```

`template-check-update` сверяет текущую checked-in версию wrapper overlay в `.template-overlay-version`
с latest tagged release шаблона или с явно переданным `--vcs-ref`.
`template-update` materialize-ит выбранный template ref и применяет только manifest template-managed paths из `automation/context/template-managed-paths.txt`.
Если путь был демотирован из template-managed в project-owned, update path сохраняет текущий project file по списку `automation/context/template-update-preserve-paths.txt`, а не удаляет его.
Дополнительно migration cleanup удаляет retired template-seeded routing docs из deployable `src/cf`, если они остались от старых template release, например legacy `src/cf/AGENTS.md` и `src/cf/README.md`.

## Ownership Boundary

- `.copier-answers.yml` остаётся bootstrap provenance и хранит source location шаблона;
- `.template-overlay-version` хранит текущий applied wrapper overlay release;
- `template-managed` слой обновляется через versioned overlay apply, а не через reconciliation product source tree;
- если root `AGENTS.md` или `README.md` отсутствует, `template-update` восстанавливает generated-project entry surface перед refresh managed overlay/router;
- `seed-once / project-owned` артефакты вроде root `README.md`, `.codex/config.toml` и `automation/context/project-map.md` должны оставаться под контролем команды проекта;
- `generated-derived` артефакты refresh-ятся отдельной repo-owned командой `./scripts/llm/export-context.sh --write`;
- `local-private` machine-specific настройки не входят в checked-in template contract.

## Project-Owned Extension Points

Проектные дополнения к template-managed точкам входа держите в project-owned файлах. `template-update` их не создаёт, не перезаписывает и не удаляет, а шаблон не поставляет их содержимое. Пути перечислены в `automation/context/template-update-preserve-paths.txt`; запись с `/` в конце защищает весь каталог. Даже если в release шаблона попадёт такой путь, overlay sync его пропустит.

| Точка | Что делает | Как подключается |
| --- | --- | --- |
| `Makefile.project` | Проектные цели `make` | `Makefile` выполняет `-include Makefile.project` в конце файла. Добавляйте только новые имена целей: переопределение цели шаблона не поддерживается, `make` выдаст предупреждение `overriding recipe`. |
| `make.project.ps1` | Проектные цели `./make.ps1` | `make.ps1` dot-source-ит файл, если он есть. Файл добавляет записи в `$projectTargets` (имя → `@(сценарий, фиксированные аргументы...)`) и строки в `$projectHelp`. Если имя совпадает с целью шаблона, `make.ps1` завершается с ошибкой. |
| `scripts/qa/agent-verify.d/` | Дополнительные шаги `make agent-verify` / `./make.ps1 agent-verify` | Шаги выполняются после базовых проверок шаблона, в порядке имён файлов, из корня репозитория. Первый ненулевой код останавливает `agent-verify` и называет шаг. |
| Блок между маркерами в `.gitignore`, `.gitattributes`, `.contextignore` | Проектные строки этих файлов | `template-update` берёт новую версию файла из шаблона и переносит в неё блок проекта без изменений. |

Шаги `agent-verify.d`:

- `*.py` выполняется тем же Python, что и `scripts/python/run-python.*`, на любой ОС — это предпочтительный кроссплатформенный формат;
- `*.sh` выполняется через `bash` только на Linux/macOS, `*.ps1` — через PowerShell только на Windows; шаг для другой ОС пропускается с сообщением `Skip project agent-verify step for another platform`;
- `*.md`, `*.txt` и скрытые файлы игнорируются, любое другое расширение — ошибка;
- шаг не должен требовать 1С runtime, секретов или сети: `agent-verify` остаётся no-1C baseline.

Маркеры проектного блока (строки должны совпадать точно, по одному маркеру каждого вида):

```text
# >>> project-owned block: template-update keeps the lines up to the closing marker >>>
# <<< project-owned block <<<
```

Если маркеров в файле проекта нет, `template-update` просто заменяет файл версией шаблона, где блок пустой. Если маркеры повреждены (нет пары, повтор, обратный порядок), обновление останавливается с ошибкой и файл не меняется.

### Python-окружение проекта (seed-once)

`pyproject.toml`, `uv.lock`, `requirements-dev.txt` и `pyrightconfig.json` шаблон кладёт в проект один раз, после этого ими владеет проект:

- при `copier copy` файлы приходят из шаблона вместе с остальным деревом;
- `template-update` их не перезаписывает и не удаляет: они перечислены в `automation/context/template-update-preserve-paths.txt` и не входят в `template-managed-paths.txt`. Если в проекте какого-то файла нет (проект создан до появления Python-окружения), `template-update` один раз копирует его из release шаблона, существующие файлы не трогает;
- проект добавляет свои зависимости через `uv add --dev <пакет>` и пересобирает производный `requirements-dev.txt`:

  ```bash
  uv export --locked --format requirements-txt --no-hashes --no-emit-project --no-annotate --output-file requirements-dev.txt
  ```

- проект добавляет свои корни проверки типов в `include` (и при необходимости в `exclude`) своего `pyrightconfig.json`.

Что остаётся за шаблоном и проверяется `make verify-types` (`scripts/python/type_checking.py`):

- базовые правила типизации лежат в template-managed `scripts/qa/pyright-base.json`; проектный `pyrightconfig.json` обязан подключать его через `"extends": "scripts/qa/pyright-base.json"`;
- эффективный режим не ниже `standard`; проект может только ужесточать правила (`"error"`/`true`), значения `"none"`, `false`, `"warning"` и другие понижения отклоняются; `baselineFile` и `ignore` запрещены, baseline-файлы тоже;
- `requirements-dev.txt` закрепляет `ruff`, `basedpyright` и `pytest` не ниже минимальных версий шаблона и совпадает с `uv export` из `uv.lock` проекта. При нарушении проверка печатает команду исправления (`uv add --dev "<пакет>>=<версия>"`, затем `uv export ...`).

Когда шаблон поднимает минимальные версии инструментов, `template-update` файлы проекта не меняет: `make verify-types` сообщает, какой пин поднять.

Пример `Makefile.project`:

```make
.PHONY: project-report

project-report:
	@./scripts/project/report.sh
```

Пример `make.project.ps1`:

```powershell
$projectTargets["project-report"] = @((Join-Path $root "scripts\project\report.ps1"))
$projectHelp += "  ./make.ps1 project-report"
```

Проверка контракта: `bash tests/smoke/project-extension-points.sh`.

## Compatibility Note

- `copier copy` остаётся bootstrap-механизмом для новых generated repos;
- `copier update` допустим только как migration bridge для старых generated repos, которые ещё не получили overlay-aware scripts;
- после миграции ongoing maintenance path должен идти через `make template-check-update` и `make template-update`.

## Перед обновлением

1. Закоммитьте или хотя бы осознайте локальные project-owned изменения и держите git worktree чистым.
   Если проект создан до точек расширения `Makefile.project`/`make.project.ps1` и записей платформ в таблице поддержки сред, сначала выполните шаги из [docs/migrations/project-toolkit-update.md](migrations/project-toolkit-update.md): иначе обновление удалит собственные цели `make` и текст внутри блока шаблона в `AGENTS.md`.
2. Прогоните `make agent-verify`.
3. Если меняется bootstrap/overlay surface, добавьте fixture smoke:

```bash
bash tests/smoke/bootstrap-agents-overlay.sh
bash tests/smoke/copier-update-ready.sh
```

## После обновления

1. Проверьте root `README.md`, `AGENTS.md` и project-owned context.
2. Убедитесь, что `.template-overlay-version` обновился до ожидаемого release ref.
3. Если репозиторий обновлялся со старого шаблона, подтвердите, что stale `src/cf/AGENTS.md` и `src/cf/README.md` исчезли и `src/cf` снова остаётся чистым importable source tree.
4. Сверьте project-owned `automation/context/runtime-support-matrix.md`, `.json` и `docs/agent/runtime-quickstart.md` с новыми контурами шаблона. `template-update` на Linux создаёт эти файлы только при их отсутствии, поэтому новые контуры (`check-bsl`, `check-cf-modules`, `analyze-bsl-external`, `run-client`, `technological-log`, `artifact-storage`) нужно перенести вручную по образцу `automation/context/templates/generated-project-runtime-support-matrix.md`. Для Windows-записей не указывайте живое доказательство, пока команда не запускалась на Windows. Если у контуров нет записей `platforms.linux`/`platforms.windows`, добавьте их и пересоберите Markdown командой `./scripts/template/migrate-runtime-support-matrix.sh` (`.\scripts\template\migrate-runtime-support-matrix.ps1`): она дописывает только отсутствующие записи без живого доказательства и не меняет существующие поля.
5. Убедитесь, что выведенные навыки `meta-*`, `form-*` (кроме `form-patterns`) и `cfe-borrow` и цель `format-bsl` исчезли, а проектные ссылки на них заменены на `metadata-use` и `cfe-form-workflow`.
6. При необходимости refresh-ните generated-derived inventory:

```bash
./scripts/llm/export-context.sh --write
```

7. Повторно прогоните baseline verify:

```bash
make agent-verify
```
