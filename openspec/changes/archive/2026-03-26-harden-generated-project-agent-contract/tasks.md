## 1. Fail-Closed Contract Для Verification

- [x] 1.1 Определить reusable policy для placeholder `smoke` / `xunit` / `bdd` contours в generated проектах.
- [x] 1.2 Обновить launcher/runtime contract так, чтобы placeholder verification не могла завершаться успешным статусом.
- [x] 1.3 Обновить generated-project verification docs, чтобы unsupported contours не рекламировались как готовый baseline path.

## 2. Sanctioned Policy Для Runtime Profiles

- [x] 2.1 Спроектировать reusable contract для sanctioned checked-in root-level runtime profiles в generated проектах.
- [x] 2.2 Обновить runtime profile docs, doctor и related guardrails под новый policy contract.

## 3. Summary-First Context Surface

- [x] 3.1 Добавить compact generated summary artifact для hot paths, counts, freshness metadata и task-to-path navigation.
- [x] 3.2 Оставить raw inventory tooling-friendly, но переподключить generated onboarding route на summary-first path.

## 4. Operational Generated Runbooks

- [x] 4.1 Усилить `docs/exec-plans/README.md` до self-contained long-running plan template.
- [x] 4.2 Дополнить `.codex/README.md` generated-project-specific playbooks для `first 15 minutes`, `long-running change`, `runtime investigation`, `review-only session`, `parallel research`.
- [x] 4.3 Добавить маленькие nested `AGENTS.md` в `env/`, `tests/` и `scripts/`.

## 5. Semantic Baseline Gates

- [x] 5.1 Расширить `scripts/qa/check-agent-docs.sh` и related checks на placeholder verification, sanctioned profile drift и freshness/consistency summary artifacts.
- [x] 5.2 Обновить fixture smoke/regression tests так, чтобы возврат к `success on TODO` или stale summary artifacts валил baseline механически.

## 6. Проверка

- [x] 6.1 Прогнать `openspec validate harden-generated-project-agent-contract --strict --no-interactive`.
- [x] 6.2 Прогнать `make agent-verify` и relevant smoke tests для generated-project agent surface.

## 7. Post-Review Closure

- [x] 7.1 Закрыть bypass в helper миграции runtime profile, чтобы default migration path не реинтродуцировал `success on TODO`.
- [x] 7.2 Выровнять semantics `unsupportedReason` между `doctor`, runtime-profile policy docs и semantic QA gates, включая optional `publish-http`.
- [x] 7.3 Довести summary-first onboarding до default generated-docs path без raw-inventory-first шага.
- [x] 7.4 Перепрогнать acceptance verification после post-review fixes и обновить трассировку `Requirement -> Code -> Test`.
- [x] 7.5 Закрыть gap на `equivalent no-op success path` в checked-in `smoke` / `xunit` / `bdd` contours, чтобы semantic baseline отклонял trivial success commands, а shipped examples оставались fail-closed.
- [x] 7.6 Поднять reusable launcher env contract для profile-defined `command`, чтобы project-owned repo entrypoint получал `project root`, `profile path`, `adapter`, `capability id/label` и `run-root` без форка template-managed launcher.
