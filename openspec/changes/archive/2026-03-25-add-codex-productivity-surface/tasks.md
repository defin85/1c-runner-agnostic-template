## 1. Information Architecture

- [x] 1.1 Добавить capability `repository-agent-guidance` и зафиксировать contract для root entrypoint, docs index, truthful context, baseline verification и execution plans.
- [x] 1.2 Определить authoritative documentation map для agent-facing surface и зафиксировать durable-doc linking policy.
- [x] 1.3 Зафиксировать target paths для system-of-record docs, execution plans и live-vs-template context split.

## 2. Agent Entrypoints And Docs

- [x] 2.1 Расширить корневой `AGENTS.md` коротким source-repo overlay без перегруза managed OpenSpec block.
- [x] 2.2 Добавить `docs/agent/index.md` и минимальный набор runbook-ов: architecture/overview, source-vs-generated boundary, verify, review.
- [x] 2.3 Добавить `docs/exec-plans/README.md` и versioned structure для `active/` и `completed/`.
- [x] 2.4 Обновить `README.md` и `docs/README.md`, чтобы они ссылались на новый docs index как на system of record.

## 3. Truthful Context And Baseline Verification

- [x] 3.1 Заменить live placeholder-ы в `automation/context/*` актуальным source-repo context и вынести generated-project skeleton context в явно template-scoped path.
- [x] 3.2 Обновить `scripts/llm/export-context.sh`, чтобы он генерировал/revalidated live context deterministically и оставлял machine-checkable freshness signal.
- [x] 3.3 Добавить repo-owned baseline entrypoint для onboarding verification (`scripts/qa/agent-verify.sh`, `make agent-verify` или эквивалент) и описать его в `docs/agent/verify.md`.
- [x] 3.4 Зафиксировать, какие проверки входят в baseline contour, а какие остаются в fixture/runtime contours.

## 4. Codex-Facing Reuse

- [x] 4.1 Добавить `.agents/skills/*` как Codex-discoverable thin wrappers над versioned repo scripts.
- [x] 4.2 Сохранить `.claude/skills/*` как thin facades и обновить единый intent-to-capability mapping для обеих packaging surfaces.
- [x] 4.3 Расширить `.codex/config.toml` и добавить `.codex/README.md` с repo-safe optional MCP/session guidance без обязательных host-specific зависимостей.

## 5. Freshness Enforcement And Verification

- [x] 5.1 Добавить `scripts/qa/check-agent-docs.sh` для проверки docs index coverage, broken internal links, placeholder leakage и freshness live context.
- [x] 5.2 Расширить `scripts/qa/check-skill-bindings.sh`, чтобы он валидировал Codex/Claude skill packaging against repo-owned script contracts.
- [x] 5.3 Обновить `.github/workflows/ci.yml`, чтобы static contour запускал новые agent-facing checks до fixture/runtime contours.
- [x] 5.4 Обновить `tests/smoke/bootstrap-agents-overlay.sh` и `tests/smoke/copier-update-ready.sh`, чтобы smoke подтверждал доставку agent docs, Codex skills и related template artifacts.
- [x] 5.5 Прогнать `openspec validate add-codex-productivity-surface --strict --no-interactive` и минимальный relevant verification set для новых checks.
