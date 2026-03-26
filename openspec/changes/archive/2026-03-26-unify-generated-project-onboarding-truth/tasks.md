## 1. Canonical Generated Onboarding Router

- [x] 1.1 Сделать `docs/agent/generated-project-index.md` единственным canonical onboarding router для generated проекта.
- [x] 1.2 Сократить root `AGENTS.md`, root `README.md` и `.codex/README.md` до role-specific pointer-ов без дублирования полного onboarding route.
- [x] 1.3 Добавить в canonical router явную матрицу “когда OpenSpec, когда `bd`, когда `docs/exec-plans/README.md`”.

## 2. One-Command Codex Onboarding

- [x] 2.1 Добавить read-only entrypoint `make codex-onboard` / `scripts/qa/codex-onboard.sh`.
- [x] 2.2 Сделать вывод onboarding command достаточным для первого экрана новой Codex-сессии: identity, safe-local checks, runtime support statuses, ключевые router-ы и next commands.
- [x] 2.3 Подключить canonical generated docs и fixture smoke к новому onboarding command.

## 3. Runtime Support Matrix

- [x] 3.1 Добавить project-owned `automation/context/runtime-support-matrix.json` как machine-readable source of truth для supported / unsupported / operator-local / provisioned contour-ов.
- [x] 3.2 Добавить human-readable companion `automation/context/runtime-support-matrix.md` и связать его с generated onboarding route.
- [x] 3.3 Зафиксировать contract между runtime support matrix, sanctioned checked-in profiles и local-private contours в docs и generated templates.

## 4. Semantic Drift Guards

- [x] 4.1 Расширить `scripts/qa/check-agent-docs.sh`, чтобы он ловил local-private runtime file как durable shared truth без operator-local classification в support matrix.
- [x] 4.2 Проверять freshness и consistency между runtime support matrix, project map, generated onboarding router и verification docs.
- [x] 4.3 Обновить fixture smoke и regression tests под новый onboarding/runtime-truth contract.

## 5. Проверка

- [x] 5.1 Прогнать `openspec validate unify-generated-project-onboarding-truth --strict --no-interactive`.
- [x] 5.2 После реализации прогнать `make agent-verify` и relevant fixture/smoke tests для generated-project onboarding/runtime surface.
