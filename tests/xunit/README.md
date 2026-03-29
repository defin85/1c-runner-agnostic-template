# xUnit / TDD

Используйте этот каталог для code-level проверок и повторно используемой бизнес-логики.

## Рекомендации

- Сначала фиксируйте red-case.
- Затем реализуйте минимальный green.
- После этого делайте refactor без изменения поведения.

## Хорошие кандидаты

- вычисления;
- классификаторы;
- валидации;
- преобразования структур данных;
- правила маршрутизации.

## Shipped Contour

Template-managed direct-platform contour использует:

- `./scripts/test/run-xunit.sh` как outer launcher boundary
- `./scripts/test/run-xunit-direct-platform.sh` как shipped runner
- `./scripts/test/tdd-xunit.sh` как canonical local loop для `src/cf`
- `tests/xunit/smoke.quickstart.json` как starter config
- `src/epf/TemplateXUnitHarness` как server-side harness starter

Если меняются только add/modify/untracked файлы под `src/cf`, используйте `./scripts/test/tdd-xunit.sh`.
Если в diff есть delete/rename-style изменения, wrapper завершится fail-closed и попросит manual `load-src -> update-db -> run-xunit`.
