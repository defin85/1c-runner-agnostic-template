## Контекст

Шаблон уже закрыл первую волну generated-project agent surface:

- generated repos больше не стартуют с source-repo-centric onboarding;
- generated context artifacts получили privacy-safe routing и critical identity extraction;
- local-only и remote-backed closeout semantics уже различаются.

Новая проблема лежит глубже: generated repo может оставаться структурно зелёным и при этом смыслово вводить агента в заблуждение. Самый опасный случай — placeholder verification, которая выглядит как рабочий contour, но реально ничего не проверяет и возвращает `success`.

## Цели

- Исключить ложноположительную verification semantics из template-managed generated surface.
- Дать generated проектам reusable механизм для явной policy по checked-in runtime profiles.
- Снизить first-hour cost для нового агента через compact summary-first navigation.
- Сделать long-running и Codex workflows operationalized, а не просто перечисленными.

## Не-цели

- Не требуется сразу внедрять настоящие runtime contours во всех generated проектах.
- Не требуется уводить generated проекты в жёсткую одинаковую profile policy без project-owned расширений.
- Не требуется заменять raw inventory компактным summary для tooling use-cases.

## Решения

### 1. Placeholder verification должна быть fail-closed

Если generated repo использует placeholder contour, template-managed contract обязан сделать это видимым и небезопасным для baseline closeout:

- contour завершает выполнение non-zero;
- summary и логи явно показывают `unsupported` или `placeholder`;
- docs не описывают такой contour как green baseline path.

`success on TODO` запрещается.

### 2. Profile policy должна быть reusable, но не навязанной

Шаблон должен задавать общую рамку:

- canonical root-level names;
- local-private sandbox;
- способ явно объявить sanctioned checked-in shared presets, если проекту они нужны;
- machine-checkable drift detection.

Это решает конфликт между жёстким template allowlist и реальными generated проектами, где могут появляться осознанные team-shared profiles.

### 3. Raw inventory остаётся вторичным, onboarding идёт через compact summary

`metadata-index.generated.json` удобен для tooling и глубокого narrowing search, но плохо подходит для первого часа работы.

Нужен дополнительный compact artifact, который:

- коротко описывает identity и freshness;
- показывает counts по high-signal категориям;
- перечисляет hot paths и representative entrypoint-ы;
- даёт task-to-path routing hints.

### 4. Shared runbooks должны быть operationalized

Сейчас `.codex/README.md` и `docs/exec-plans/README.md` задают направление, но не дают нового generated проекту достаточно конкретный workflow.

Нужны:

- template long-running plan с обязательными секциями прогресса и решений;
- repo-specific Codex playbooks;
- локальные `AGENTS.md` рядом с зонами `env/`, `tests/`, `scripts/`.

### 5. Semantic gates должны подтверждать смысл, а не только структуру

Baseline checks и fixture smoke должны валить:

- placeholder verification, возвращающую `success`;
- несанкционированные checked-in root-level profiles;
- stale или inconsistent summary artifacts;
- docs, которые рекламируют unsupported contour как baseline-ready.

## Риски И Компромиссы

- Если reusable policy для sanctioned profiles окажется слишком сложной, generated проекты начнут обходить её локальными исключениями. Значит, policy должна быть короткой и прозрачной.
- Compact summary добавляет ещё один generated artifact и требует строгой freshness-проверки.
- Fail-closed placeholder policy может сломать привычные локальные сценарии у проектов, которые привыкли к `echo TODO`; это нужно компенсировать честными docs и migration notes.

## План Миграции

1. Сначала определить normative contract для placeholder verification и sanctioned profiles.
2. Затем обновить docs/runbooks так, чтобы они ссылались только на truthful contours.
3. После этого усилить semantic checks и fixture smoke.
4. В конце внедрить compact summary-first routing и локальные router-файлы.

## Открытые Вопросы

- Где лучше хранить project-owned sanctioned profile policy: в `env/README.md`, в отдельном machine-readable файле или в generated context?
- Должен ли compact summary быть Markdown, JSON или парой из обоих форматов?
