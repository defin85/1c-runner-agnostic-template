# Automation Context

Этот каталог предназначен для машинно-читаемого контекста проекта.

## Что здесь хранить

- truthful live context для template source repo;
- template-scoped skeleton context для generated projects;
- краткую карту проекта;
- индексы метаданных;
- reusable checklists;
- prompts для повторяемых задач;
- generated артефакты, которые помогают агентам быстрее ориентироваться.

## Layout

- `automation/context/template-source-*` описывает текущий template source repo.
- `automation/context/templates/` хранит skeleton files для generated projects.
- Generated projects не должны принимать `template-source-*` за свой live context.

## Что не хранить

- секреты;
- большие бинарные артефакты;
- production dumps;
- временные логи выполнения.
