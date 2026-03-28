## ADDED Requirements

### Requirement: Repo-Owned Diff-Aware Load Wrapper

Шаблон MUST поставлять repo-owned wrapper для сценария "взять source diff и загрузить только его" без дублирования runtime import logic.

#### Scenario: Generated project invokes diff-aware load wrapper

- **WHEN** generated project или source repo вызывает `scripts/platform/load-diff-src.sh`
- **THEN** wrapper ДОЛЖЕН вычислить explicit selection changed files внутри `src/cf`
- **AND** wrapper ДОЛЖЕН делегировать actual import в существующий `scripts/platform/load-src.sh --files`
- **AND** public intent wrapper-а ДОЛЖЕН оставаться отдельным от full `load-src`

#### Scenario: Wrapper publishes machine-readable execution artifacts

- **WHEN** `scripts/platform/load-diff-src.sh` завершает работу
- **THEN** он ДОЛЖЕН писать собственный `summary.json`
- **AND** summary ДОЛЖЕН явно отражать selected files, ignored files и delegated `load-src` artifact path
- **AND** wrapper ДОЛЖЕН возвращать non-zero exit code на failure

#### Scenario: After filtering there are no eligible source files

- **WHEN** diff не даёт ни одного существующего eligible path внутри `src/cf`
- **THEN** wrapper НЕ ДОЛЖЕН запускать `load-src`
- **AND** wrapper ДОЛЖЕН завершаться fail-closed с диагностикой в `stderr.log` и `summary.json`
