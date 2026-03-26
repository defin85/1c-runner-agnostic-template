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
- `docs/exec-plans/TEMPLATE.md` — copy-ready стартовая точка для нового long-running плана.
- `docs/exec-plans/EXAMPLE.md` — минимальный пример заполненного execution plan artifact.

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

## Как начинать

1. Скопируйте `docs/exec-plans/TEMPLATE.md` в `docs/exec-plans/active/<короткое-имя>.md`.
2. Если нужен ориентир по уровню детализации, сначала посмотрите `docs/exec-plans/EXAMPLE.md`.
3. Держите план самодостаточным: новый агент должен понять состояние без скрытого контекста чата.
