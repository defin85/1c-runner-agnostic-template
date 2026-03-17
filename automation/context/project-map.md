# Project Map

Обновите этот файл после создания реального проекта.

## Бизнес-домен

- <описание домена>

## Главные bounded contexts

- <context-1>
- <context-2>

## Главные точки входа

- HTTP services:
- Scheduled jobs:
- Forms:
- External processors:
- Extensions:

## Ключевые артефакты

- Основная конфигурация: `src/cf`
- Расширения: `src/cfe`
- Внешние обработки: `src/epf`
- Внешние отчеты: `src/erf`
- OpenSpec workspace: `openspec/`

## Канонические проверки

- BSL static analysis: `./scripts/qa/analyze-bsl.sh`
- xUnit: `./scripts/test/run-xunit.sh`
- BDD: `./scripts/test/run-bdd.sh`
- Smoke: `./scripts/test/run-smoke.sh`
