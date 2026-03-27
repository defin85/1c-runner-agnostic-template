## ADDED Requirements

### Requirement: Explicit Commit-Scoped Bridge To Partial Load-Src

Runtime toolkit MUST поддерживать repo-owned bridge, который превращает committed task scope в explicit selection для partial `load-src`, не меняя существующую import semantics capability `load-src`.

#### Scenario: Wrapper derives a partial import selection from canonical task markers

- **WHEN** repo-owned task-scoped wrapper вычисляет commit selection по trailer `Bead:` или `Work-Item:`
- **THEN** он ДОЛЖЕН передавать в `load-src` только explicit relative file paths внутри configured source tree
- **AND** удалённые, несуществующие или внешние paths НЕ ДОЛЖНЫ попадать в `--files`
- **AND** actual partial import semantics ДОЛЖНА оставаться за capability `load-src`

#### Scenario: Wrapper supports explicit range fallback without changing load-src semantics

- **WHEN** template или generated project использует `scripts/platform/load-task-src.sh --range <revset>`
- **THEN** wrapper ДОЛЖЕН строить file selection из указанного commit range без собственной runtime import реализации
- **AND** он ДОЛЖЕН делегировать actual partial import в существующий `load-src --files`
- **AND** range fallback НЕ ДОЛЖЕН подменять собой canonical trailer-based contract

#### Scenario: Task-scoped wrapper stays independent from git notes and patch parsing

- **WHEN** template или generated project использует `scripts/platform/load-task-src.sh`
- **THEN** wrapper НЕ ДОЛЖЕН зависеть от `git notes` как canonical metadata source
- **AND** wrapper НЕ ДОЛЖЕН парсить patch-output `scripts/platform/diff-src.sh`
- **AND** selection logic ДОЛЖНА оставаться repo-owned и deterministic
