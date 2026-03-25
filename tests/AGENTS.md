# Test Routing

Этот каталог хранит automated evidence для runtime, docs и template-maintenance contract.

- Verification matrix для generated repo описана в [docs/agent/generated-project-verification.md](../docs/agent/generated-project-verification.md).
- Lightweight baseline начинается с `make agent-verify`; не рекламируйте deeper runtime contours как safe-local path без реального prerequisites contract.
- Для runtime/profile изменений синхронно обновляйте `tests/smoke/`, [env/README.md](../env/README.md) и `automation/context/runtime-profile-policy.json`, если меняется sanctioned checked-in profile policy.
- Для onboarding/context изменений держите в согласии `tests/smoke/agent-docs-contract.sh`, `scripts/qa/check-agent-docs.sh` и `scripts/llm/export-context.sh`.
- Требование к завершению то же, что и в корне: `Requirement -> Code -> Test` должно быть явным.
