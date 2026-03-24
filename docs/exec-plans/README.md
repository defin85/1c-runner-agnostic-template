# Execution Plans

Этот каталог хранит versioned execution plans для long-running или cross-cutting agent work.

## Когда использовать

Создавайте plan artifact, если задача:

- не помещается в одну короткую сессию;
- требует handoff между сессиями;
- затрагивает несколько крупных зон репозитория;
- зависит от явного порядка шагов и checkpoints.

## Структура

- `docs/exec-plans/active/` — текущие планы;
- `docs/exec-plans/completed/` — завершённые планы.

## Минимальный шаблон

План должен фиксировать:

- цель;
- зависимости и инварианты;
- шаги в хронологическом порядке;
- completion criteria;
- последнюю известную verification state.
