## ADDED Requirements

### Requirement: Intent Mapping For Diff-To-Load Workflow

Шаблон MUST документировать и поставлять agent-facing mapping для намерения "загрузить в ИБ только текущие source changes".

#### Scenario: Agent looks for a repeatable diff-to-load workflow

- **WHEN** пользователь просит загрузить в ИБ только текущий diff исходников
- **THEN** repository MUST поставлять project-scoped skill или обновлённый skill contract для этого workflow
- **AND** skill ДОЛЖЕН указывать на repo-owned wrapper, а не на ad hoc shell snippet
- **AND** mapping ДОЛЖЕН оставаться updateable через template updates
