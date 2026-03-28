## 1. Contract

- [x] 1.1 Дополнить `agent-runtime-toolkit` требованием на repo-owned diff-aware wrapper с machine-readable artifacts и delegated `load-src` contract.
- [x] 1.2 Дополнить `ibcmd-capability-drivers` требованием на explicit `git diff -> --files` bridge без parsing patch-output и без дублирования import logic.
- [x] 1.3 Дополнить `project-scoped-skills` intent mapping для сценария "загрузить diff в ИБ".

## 2. Implementation

- [x] 2.1 Добавить `scripts/platform/load-diff-src.sh` с repo-owned CLI для git-backed selection и delegation в `scripts/platform/load-src.sh --files`.
- [x] 2.2 Реализовать fail-closed filtering: учитывать только существующие пути внутри `src/cf`, не пропускать пустой итоговый selection и не запускать runtime import без eligible files.
- [x] 2.3 Добавить machine-readable wrapper summary с selected/ignored files и ссылкой на delegated `load-src` run-root.
- [x] 2.4 Добавить/обновить agent skill packaging для нового workflow и обновить template-managed docs/entrypoint routers.

## 3. Verification

- [x] 3.1 Добавить smoke для успешного `diff -> partial load-src` delegation с machine-readable summary.
- [x] 3.2 Добавить smoke для fail-closed случаев: deleted-only diff, empty selection и пути вне `src/cf`.
- [x] 3.3 Добавить template delivery coverage, что новый script/skill попадает в generated repo через template-managed surface.
