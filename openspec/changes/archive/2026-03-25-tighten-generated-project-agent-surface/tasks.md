## 1. Generated-Project Guidance Routing

- [x] 1.1 Нормализовать shared docs и nested instruction chain для generated repos, чтобы `docs/`, `automation/` и `src/` не уводили в source-repo-centric onboarding.
- [x] 1.2 Сделать generated root guidance и related docs/router-файлы короче и явнее: verify, review, skills, Codex-first onboarding, long-running plans, local-only closeout.
- [x] 1.3 Обновить starter surface для project-owned enrichment без подмены project-specific domain truth.

## 2. Generated Context Artifacts

- [x] 2.1 Усилить `scripts/llm/export-context.sh` для generated repos: корректно вытягивать critical identity из `src/cf/Configuration.xml`, исключать `local-private` leakage и выдавать entrypoint-oriented inventory.
- [x] 2.2 Обновить checked-in generated context/templates и related docs под новый artifact contract.

## 3. Semantic Verification

- [x] 3.1 Расширить `scripts/qa/check-agent-docs.sh` semantic checks для generated repos: onboarding conflicts, privacy leaks, non-empty critical fields, local-only closeout semantics.
- [x] 3.2 Добавить или обновить fixture smoke/doc contract tests, чтобы drift валился механически.
- [x] 3.3 Прогнать `openspec validate tighten-generated-project-agent-surface --strict --no-interactive`, `make agent-verify` и relevant smoke tests.
