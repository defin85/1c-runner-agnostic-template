## ADDED Requirements

### Requirement: Explicit Git-Diff Bridge To Partial Load-Src

Runtime toolkit MUST поддерживать repo-owned bridge, который превращает git-backed source diff в explicit selection для partial `load-src`, не меняя существующую import semantics capability `load-src`.

#### Scenario: Wrapper derives a partial import selection from git-backed source changes

- **WHEN** repo-owned diff-aware wrapper вычисляет changed files для `src/cf`
- **THEN** он ДОЛЖЕН передавать в `load-src` только explicit relative file paths внутри configured source tree
- **AND** удалённые или несуществующие paths НЕ ДОЛЖНЫ попадать в `--files`
- **AND** actual partial import semantics ДОЛЖНА оставаться за capability `load-src`

#### Scenario: Diff-aware wrapper stays independent from patch-oriented diff output

- **WHEN** template или generated project использует `scripts/platform/load-diff-src.sh`
- **THEN** wrapper НЕ ДОЛЖЕН парсить patch-output `scripts/platform/diff-src.sh`
- **AND** wrapper НЕ ДОЛЖЕН зависеть от произвольного profile-defined `capabilities.diffSrc.command` как machine-readable source of changed files
- **AND** selection logic ДОЛЖНА оставаться repo-owned и deterministic
