# Project Context

## Purpose
`1c-runner-agnostic-template` это шаблон репозитория для 1С-проектов.
Его цель:

- задавать каноническую структуру проекта вокруг `OpenSpec -> Beads -> Code`;
- поставлять стабильные entrypoint-скрипты для запуска, тестов и QA без жесткой привязки к одному runner;
- упрощать bootstrap новых 1С-репозиториев и их последующее обновление через `copier update`;
- давать агентам и людям единый contract-first workflow для работы с требованиями, задачами, кодом и проверками.

Этот репозиторий является исходником шаблона, а не готовым прикладным 1С-решением.

## Tech Stack
- Bash shell scripts
- Copier template (`copier.yml`, post-copy/post-update hooks)
- OpenSpec for spec-driven development
- Beads (`bd`) for local issue tracking in generated projects
- Markdown documentation and operational checklists
- Git and Git tags for template versioning and update flow
- 1C runtime adapters (`direct-platform`, `remote-windows`, optional `vrunner`)
- Typical CLI helpers used by scripts: `jq`, `rg`, `git`, `curl`

## Project Conventions

### Code Style
- Документация, планы, спецификации и change-артефакты ведутся на русском языке по умолчанию.
- Shell-скрипты должны быть POSIX/Bash-friendly, с `set -euo pipefail`, явной проверкой зависимостей и понятными сообщениями об ошибках.
- Предпочтителен `script-first` подход: вся исполняемая логика живет в versioned скриптах репозитория, а не в ad-hoc командах из документации.
- Для поиска по репозиторию канонический порядок: semantic search при наличии, затем `ast-index`, затем `rg`, затем `rg --files`.
- Production behavior change сначала отражается в `openspec/changes/<change-id>/`, а затем реализуется в коде.

### Architecture Patterns
- Репозиторий разделяет intent, execution и source tree:
  - `openspec/` для требований и change proposals;
  - `.beads/` в generated projects для live task graph;
  - `src/` для deployable source tree;
  - `scripts/` для канонических entrypoint’ов людей, CI и агентов.
- Шаблон следует `runner-agnostic` модели: публичный интерфейс задается shell entrypoint’ами, а конкретный backend выбирается через adapter.
- Для generated projects update path должен проходить через `copier update`, а не через ручное копирование файлов из шаблона.
- AGENT instructions строятся как managed overlay поверх `openspec init`, чтобы template updates могли refresh-ить правила без ручного merge.

### Testing Strategy
- Для behavior-changing задач обязателен explicit execution matrix `Requirement/Scenario -> Code -> Test`.
- Для обязательных требований нужны automated checks в `tests/` или `features/`, либо явно согласованное исключение.
- Для shell/runtime логики предпочтительны smoke/fixture tests, которые можно запускать без реальной 1С-платформы.
- Для самого шаблона ключевые проверки:
  - smoke tests bootstrap/update flow;
  - shell syntax checks;
  - `openspec validate --strict --no-interactive` для change proposals;
  - при необходимости integration smoke через локальный `copier copy/update`.

### Git Workflow
- Шаблон версионируется в Git и публикует update-ready версии через теги.
- Generated projects должны хранить `.copier-answers.yml` и обновляться от tagged versions шаблона.
- Сессия с кодовыми изменениями не считается завершенной, пока `git push` не выполнен успешно, если нет внешнего блокера.
- Для крупных и новых изменений сначала оформляется OpenSpec change proposal; production code начинается только после явного согласования (`Go!`).

## Domain Context
- Домен проекта: автоматизация разработки 1С-репозиториев и agent-friendly operational tooling вокруг 1С.
- В generated projects ожидаются операции вроде:
  - создание и подключение ИБ;
  - загрузка и выгрузка конфигурации;
  - применение обновления БД;
  - запуск xUnit, BDD и smoke-проверок;
  - публикация HTTP-сервисов и диагностические проверки.
- Шаблон не должен навязывать единственный инструмент запуска; `vrunner` допустим как адаптер, но не как фундамент.
- Важная цель следующего этапа развития: дать агентам project-scoped skills и стабильные repo-owned скрипты для взаимодействия с 1С-runtime.

## Important Constraints
- Репозиторий должен оставаться пригодным как template source и как источник безопасных `copier update`.
- Bootstrap и update hooks нельзя смешивать: одноразовая инициализация (`openspec`, `git`, `bd`) не должна повторяться на update.
- Шаблон не должен содержать секреты, реальные строки подключения и machine-specific credentials.
- Решения должны работать без обязательной зависимости на Windows-only tooling.
- Нельзя подменять `bd` markdown TODO-списками для code-change, если beads включен.
- Для новых и крупных изменений код нельзя начинать до явного `Go!`.

## External Dependencies
- `openspec` CLI
- `bd` CLI (опционально, но по умолчанию используется в generated projects)
- `copier`
- Git/GitHub для версии шаблона и update flow
- 1С platform CLI/tools в generated projects:
  - `1cv8`
  - `1cv8c`
  - `rac`
  - `webinst`
- Потенциальные agent-side integrations:
  - project-scoped Claude skills
  - Codex `.codex/config.toml`
  - semantic code search / MCP servers при наличии в конкретном контуре
