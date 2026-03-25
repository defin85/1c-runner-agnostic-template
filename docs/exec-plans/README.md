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

## Обязательные секции

Для long-running handoff не полагайтесь на скрытый контекст чата. План должен быть самодостаточным и обновляться по мере движения задачи.

- `Progress` — что уже сделано и что ещё осталось.
- `Surprises & Discoveries` — факты, которые изменили план или понимание системы.
- `Decision Log` — какие развилки уже закрыты и почему.
- `Outcomes & Retrospective` — что в итоге landed, что осталось долгом, какие follow-up нужны.

## Рекомендуемый шаблон

```md
# <Короткое имя плана>

## Goal

## Scope And Non-Goals

## Dependencies And Invariants

## Execution Matrix

## Progress

## Chronological Steps

## Surprises & Discoveries

## Decision Log

## Verification State

## Outcomes & Retrospective
```
