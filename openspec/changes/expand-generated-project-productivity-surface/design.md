## Context

Generated-project surface уже хорошо объясняет process-layer, ownership model и safe-local verification, но остаётся слишком абстрактным для плотного прикладного кода.
Проблемы повторяются:

- между compact summary и raw metadata слишком большой прыжок;
- project-owned code navigation и runtime truth не сведены в короткие dedicated digests;
- `src/` guidance заканчивается слишком рано;
- long-running workflow требует импровизации, потому что есть только README-контракт;
- curated truth (`project-map.md`, runtime quick answers) пока не имеет такого же сильного freshness gate, как generated-derived artifacts.

## Goals

- сократить first-hour cost в generated repo без зашивания target-specific доменной логики в шаблон;
- дать project-owned scaffolds, которые generated repos смогут наполнять своими фактами;
- surfaced Codex session controls и long-running workflow раньше, чем агент углубится в raw inventory;
- удерживать curated truth в актуальном состоянии механическими checks.

## Non-Goals

- не поставлять finished architecture map для конкретного бизнес-домена generated repo;
- не делать template root/router docs длиннее ради project-specific деталей;
- не вводить сразу большой новый набор skills до стабилизации docs и checks;
- не делать project-specific smoke обязательным для всех generated repos без явного extension slot.

## Decisions

- Decision: `docs/agent/architecture-map.md` и `docs/agent/runtime-quickstart.md` будут seeded как project-owned scaffolds.
  - Rationale: это reusable шаблон для generated repos, но содержимое должно оставаться domain-specific и принадлежать проекту.
- Decision: `src/cf/AGENTS.md` станет ближайшим local router для плотного code tree; более глубокие subtree routers останутся optional follow-up surface.
  - Rationale: нужен immediate win по proximity guidance без массового размножения локальных файлов.
- Decision: `make codex-onboard` будет раньше surfaced `/plan`, `/compact`, `/review`, `/ps`, `/mcp` и optional project-specific baseline extension slot.
  - Rationale: эти controls полезны именно в первые минуты, а не после чтения всего `.codex/README.md`.
- Decision: exec-plan surface получит copy-ready `TEMPLATE.md` и минимальный example artifact.
  - Rationale: generated repo должен давать self-contained starting point для multi-session work без импровизации.
- Decision: semantic checks будут валить stale curated truth и broken references между project map, runtime quick reference, runtime support matrix и onboarding router.
  - Rationale: concise curated docs опаснее stale, чем raw generated inventory, потому что агент доверяет им сильнее.

## Risks / Trade-offs

- Новые seeded docs могут устаревать и создавать ложное ощущение completeness.
  - Mitigation: явная project-owned ownership marker + checks на broken references и runtime consistency.
- Более глубокий routing увеличивает число agent-facing файлов.
  - Mitigation: `src/cf/AGENTS.md` остаётся коротким local router, а deeper subtree routers пока не обязательны.
- Optional project baseline extension slot может быть понятым как mandatory smoke.
  - Mitigation: docs и onboarding должны явно различать template baseline и project-specific extension.

## Verification Plan

- `openspec validate expand-generated-project-productivity-surface --strict --no-interactive`
- `make agent-verify`
- relevant fixture/smoke coverage for generated scaffolds and onboarding contracts
