## 1. Source Release Workflow

- [x] 1.1 Добавить repo-owned release command для source repo, который выпускает следующий overlay tag только из явного release path.
- [x] 1.2 Добавить hook-based guardrail, который не даёт случайно запушить overlay release tag вручную или через `--follow-tags`.
- [x] 1.3 Сделать release path fail-closed: чистый worktree, актуальный `origin/main`, явный tag target и успешная baseline verification перед publish.

## 2. Документация и контракты

- [x] 2.1 Добавить source-repo runbook для template release workflow.
- [x] 2.2 Подключить новый runbook в agent-facing source docs без дублирования detail в root entrypoint.
- [x] 2.3 Синхронизировать docs, hook workflow и advertised commands.

## 3. Проверки и релиз

- [x] 3.1 Добавить smoke/static coverage для source release workflow и tag push guardrail.
- [x] 3.2 Прогнать relevant verification set.
- [x] 3.3 Выпустить следующий template overlay release tag через новый guarded workflow.
