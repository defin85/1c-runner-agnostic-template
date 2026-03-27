## ADDED Requirements

### Requirement: Intent Mapping For Task-To-Load Workflow

Шаблон MUST документировать и поставлять agent-facing mapping для намерения "загрузить в ИБ уже закомиченные изменения задачи".

#### Scenario: Agent looks for a repeatable task-to-load workflow

- **WHEN** пользователь просит загрузить в ИБ изменения конкретной задачи, уже попавшие в commit history
- **THEN** repository MUST поставлять project-scoped skill или обновлённый skill contract для этого workflow
- **AND** skill ДОЛЖЕН указывать на repo-owned wrapper, а не на ad hoc shell snippet
- **AND** mapping ДОЛЖЕН документировать canonical selectors `--bead`, `--work-item` и `--range`
- **AND** mapping ДОЛЖЕН оставаться updateable через template updates
