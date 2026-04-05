## 1. Generated Guidance

- [x] 1.1 Обновить generated-project onboarding docs и `make codex-onboard`, чтобы они показывали AI-readiness status, canonical imported-skill readiness/bootstrap path и compact first-hour skill routing.
- [x] 1.2 Убедиться, что root routers generated repo остаются краткими pointer surfaces и не дублируют полный catalog/workflow inline.

## 2. Repo-Derived Context Seeds

- [x] 2.1 Обновить bootstrap/update generation path так, чтобы `automation/context/project-map.md`, `docs/agent/architecture-map.md` и `docs/agent/runtime-quickstart.md` seed-ились repo-derived draft-фактами, а не только generic scaffold.
- [x] 2.2 Добавить generated-derived recommendation artifact для project-aware recommended skills/workflows и встроить routing к нему из onboarding surface.

## 3. Imported Skill Readiness

- [x] 3.1 Добавить repo-owned readiness/preflight contract для representative python-backed и node-backed imported skills.
- [x] 3.2 Сделать fail-closed actionable error path для missing dependencies вместо raw vendored stack traces.
- [x] 3.3 Поднять native-preference hints для overlapping native/imported workflows в discovery-facing skill metadata или equivalent first-pass mapping.

## 4. Verification

- [x] 4.1 Расширить baseline and fixture checks representative imported-skill readiness contract и новую generated onboarding/recommendation surface.
- [x] 4.2 Обновить docs/runbooks и проверить, что generated repo после bootstrap/update проходит новый AI-readiness baseline.
- [x] 4.3 Прогнать `openspec validate improve-generated-repo-ai-readiness --strict --no-interactive`.
