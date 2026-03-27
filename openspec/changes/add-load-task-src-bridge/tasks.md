## 1. Contract

- [x] 1.1 Дополнить `agent-runtime-toolkit` требованием на repo-owned task-scoped load wrapper с machine-readable artifacts и fail-closed selection policy.
- [x] 1.2 Дополнить `ibcmd-capability-drivers` требованием на explicit `commits -> --files` bridge через canonical trailers и `--range` fallback без дублирования import logic.
- [x] 1.3 Дополнить `project-scoped-skills` intent mapping для сценария "загрузить в ИБ уже закомиченные изменения задачи".

## 2. Implementation

- [x] 2.1 Добавить `scripts/platform/load-task-src.sh` с repo-owned CLI для `--bead`, `--work-item`, `--range`, `--dry-run` и delegation в `scripts/platform/load-src.sh --files`.
- [x] 2.2 Добавить repo-owned helper/validation surface для canonical trailers `Bead:` и `Work-Item:` без скрытой auto-install логики на template update.
- [x] 2.3 Реализовать deterministic commit discovery и path filtering через git history entrypoint-ы, с machine-readable summary по selected commits, selected files, ignored/deleted paths и delegated run-root.
- [x] 2.4 Добавить/обновить project-scoped skills, docs routers и operator-facing guidance для нового task-scoped workflow.

## 3. Verification

- [x] 3.1 Добавить smoke для успешного `--bead` или `--work-item` selection с delegation в partial `load-src`.
- [x] 3.2 Добавить smoke для `--range` fallback и fail-closed случаев: пустой match, deleted-only selection, взаимоисключающие selector flags.
- [x] 3.3 Добавить smoke на helper/validation surface для canonical trailers.
- [x] 3.4 Добавить template delivery coverage, что новый script/skill/docs surface попадает в generated repo через template-managed path.
