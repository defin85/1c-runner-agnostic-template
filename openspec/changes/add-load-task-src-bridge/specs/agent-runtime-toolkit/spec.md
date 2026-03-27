## ADDED Requirements

### Requirement: Repo-Owned Task-Scoped Load Wrapper

Шаблон MUST поставлять repo-owned wrapper для сценария "взять уже закомиченные изменения задачи и загрузить только их" без дублирования runtime import logic.

#### Scenario: Generated project invokes task-scoped load wrapper

- **WHEN** generated project или source repo вызывает `scripts/platform/load-task-src.sh` c selector-ом `--bead`, `--work-item` или `--range`
- **THEN** wrapper ДОЛЖЕН вычислить explicit selection changed files внутри `src/cf`
- **AND** wrapper ДОЛЖЕН делегировать actual import в существующий `scripts/platform/load-src.sh --files`
- **AND** public intent wrapper-а ДОЛЖЕН оставаться отдельным от worktree-oriented `load-diff-src`

#### Scenario: Wrapper publishes machine-readable selection artifacts

- **WHEN** `scripts/platform/load-task-src.sh` завершает работу
- **THEN** он ДОЛЖЕН писать собственный `summary.json`
- **AND** summary ДОЛЖЕН явно отражать selector mode, selected commits, selected files, ignored или deleted paths и delegated `load-src` artifact path
- **AND** wrapper ДОЛЖЕН возвращать non-zero exit code на failure

#### Scenario: Selector does not resolve an eligible task-scoped import

- **WHEN** selector не находит подходящих commits или после фильтрации не остаётся eligible paths внутри `src/cf`
- **THEN** wrapper НЕ ДОЛЖЕН запускать `load-src`
- **AND** wrapper ДОЛЖЕН завершаться fail-closed с диагностикой в `stderr.log` и `summary.json`
