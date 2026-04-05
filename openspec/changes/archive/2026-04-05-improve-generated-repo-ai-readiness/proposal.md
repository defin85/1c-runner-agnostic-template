# Change: improve-generated-repo-ai-readiness

## Why

Шаблон уже даёт generated repo хороший routing-first onboarding, но это ещё не максимальная AI-ready поверхность.
После bootstrap новый репозиторий остаётся частично generic: project-owned context seeds дают в основном scaffold-структуру, а не repo-derived first-pass карту; imported `cc-1c-skills` хорошо discoverable, но executable skills могут падать на отсутствующих Python/Node зависимостях; full skill catalog слишком широкий для первого часа и не даёт compact project-aware recommendations.

В результате агент быстро находит правильные документы, но всё ещё тратит лишний первый проход на три вещи:

- выяснение, какие части generated repo наиболее вероятны для текущего change scenario;
- ручной выбор нужного skill из большого каталога;
- диагностику того, runnable ли template-managed imported skill в текущем локальном контуре.

Если шаблон должен максимально готовить target repo под LLM с нулевым или почти нулевым onboarding, эти gaps нужно закрыть в template-managed surface, а не перекладывать на каждую generated codebase.

## What Changes

- усилить generated-project onboarding так, чтобы `make codex-onboard` и canonical docs показывали AI-readiness status, canonical readiness/bootstrap path и compact project-aware recommended workflows
- сделать seed-once project-owned context artifacts более фактическими: bootstrap должен закладывать repo-derived draft facts и first-pass routing, а не только generic scaffold
- ввести fail-closed readiness contract для executable imported skills, чтобы agent видел actionable bootstrap guidance вместо raw dependency tracebacks
- добавить generated-derived recommendation artifact для project-aware skill selection и first-hour workflow hints
- расширить verification contract шаблона representative readiness checks для imported skills и новой onboarding surface

## Impact

- Affected specs:
  - `generated-project-agent-guidance`
  - `generated-context-artifacts`
  - `project-scoped-skills`
- Affected code:
  - `scripts/qa/codex-onboard.sh`
  - `scripts/qa/agent-verify.sh`
  - `scripts/python/imported_skills.py`
  - `scripts/python/context.py`
  - `scripts/python/template_tools.py`
  - `scripts/bootstrap/generated-project-surface.sh`
  - `docs/agent/generated-project-index.md`
  - `docs/agent/generated-project-verification.md`
  - `.agents/skills/README.md`
  - `env/README.md`
  - `tests/python/test_cross_platform.py`
  - `tests/smoke/imported-skills-contract.sh`
  - `tests/smoke/agent-docs-contract.sh`
  - `tests/smoke/copier-update-ready.sh`
