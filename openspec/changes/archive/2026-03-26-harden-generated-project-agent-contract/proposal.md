# Изменение: ужесточить agent contract generated проектов

## Зачем

Последний аудит целевого generated проекта показал не столько structural drift, сколько semantic drift:

- verification contours в checked-in profiles могут завершаться успешно на placeholder-командах вроде `echo TODO`;
- docs и guardrails пока не дают reusable механизма для явного sanctioned policy по checked-in root-level runtime profiles;
- generated inventory остаётся полезным для tooling, но слишком тяжёл для first-hour onboarding без компактной карты hot paths;
- shared `docs/exec-plans/README.md`, `.codex/README.md` и локальные router-файлы ещё недостаточно operationalized для long-running и repo-specific Codex workflows.

Эти проблемы не являются project-specific для одного generated repo. Они показывают gaps именно в template-managed contract, который должен делать ложный зелёный сигнал невозможным и давать новым generated проектам более честный onboarding surface.

## Что меняется

- Сделать generated-project verification fail-closed относительно placeholder `smoke` / `xunit` / `bdd` contours.
- Ввести reusable contract для sanctioned checked-in root-level runtime profiles, чтобы generated repo мог явно объявить team-shared presets или запретить их без неявных warning-only исключений.
- Добавить compact summary-first generated context artifact для hot paths, counts, freshness metadata и task-to-path navigation.
- Переподключить generated-project onboarding docs и runbook на truthful verification semantics и summary-first route.
- Усилить shared long-running/Codex guidance: рабочий exec-plan template, repo-specific playbooks и локальные router-файлы в `env/`, `tests/`, `scripts/`.
- Расширить semantic CI/doc checks и fixture smoke так, чтобы placeholder verification, profile-policy drift и stale summary artifacts ловились механически.

## Что не входит в изменение

- Реализовывать реальные business-specific smoke/xUnit/BDD contours для конкретной конфигурации generated проекта.
- Навязывать generated проектам один фиксированный набор shared team presets поверх их project-owned решений.
- Автоматически строить domain-specific hotspot map за команду generated проекта без repo-owned enrichment.

## Влияние

- Affected specs:
  - `generated-project-agent-guidance`
  - `generated-context-artifacts`
  - `runtime-profile-schema`
  - `template-ci-contours`
- Affected code:
  - `scripts/test/run-smoke.sh`
  - `scripts/test/run-xunit.sh`
  - `scripts/test/run-bdd.sh`
  - `scripts/diag/doctor.sh`
  - `scripts/qa/check-agent-docs.sh`
  - `scripts/llm/export-context.sh`
  - `automation/context/templates/*`
  - `docs/agent/generated-project-index.md`
  - `docs/agent/generated-project-verification.md`
  - `docs/exec-plans/README.md`
  - `.codex/README.md`
  - `env/README.md`
  - nested `AGENTS.md` в `env/`, `tests/`, `scripts/`
  - relevant fixture and smoke tests under `tests/smoke/`
