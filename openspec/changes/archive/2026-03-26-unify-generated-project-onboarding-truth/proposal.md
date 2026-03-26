# Изменение: унифицировать onboarding truth generated проектов

## Зачем

Повторный аудит целевого generated проекта показал уже не structural gap, а конфликт между несколькими truth-сигналами:

- generated onboarding распределён по root `AGENTS.md`, root `README.md`, `docs/agent/generated-project-index.md` и `.codex/README.md`, поэтому новый агент тратит первые шаги на сверку повторяющихся router-ов;
- runnable runtime contours могут жить только в ignored `env/local.json`, но durable docs и smoke начинают ссылаться на такой contour как на фактический source of truth;
- у generated проекта нет одного read-only entrypoint, который за один запуск печатает identity, safe-local baseline, runtime support truth и следующие команды;
- semantic lint пока хорошо ловит structural drift, но не закрывает drift класса “local-private profile стал durable shared truth”.

Эти gaps reusable и лежат в template-managed generated-project surface, а не только в одном target repo.

## Что меняется

- Сделать `docs/agent/generated-project-index.md` единственным canonical onboarding router для generated проектов, а root `AGENTS.md`, root `README.md` и `.codex/README.md` сократить до role-specific pointer-ов.
- Добавить read-only generated-project entrypoint `make codex-onboard` / `scripts/qa/codex-onboard.sh`, который печатает identity, safe-local baseline, runtime support matrix, ключевые router-ы и следующие команды без записи в checked-in файлы.
- Ввести project-owned runtime support matrix в двух формах:
  - `automation/context/runtime-support-matrix.json` как machine-readable truth;
  - `automation/context/runtime-support-matrix.md` как human-readable companion.
- Зафиксировать статусы contour-ов (`supported`, `unsupported`, `operator-local`, `provisioned`) и связь с sanctioned checked-in profiles, runbook-ами и baseline commands.
- Усилить semantic QA и fixture smoke так, чтобы generated repo не мог использовать ignored local-private profile как durable shared truth без явной operator-local classification в runtime support matrix.
- Добавить в generated onboarding явную матрицу ролей `OpenSpec -> bd -> exec-plans`, чтобы planning surface не выглядел split-brain.

## Что не входит в изменение

- Реализовывать business-specific xUnit / BDD / smoke contour для конкретного generated проекта.
- Навязывать generated проектам одинаковый набор shared runtime presets сверх already supported sanctioned policy.
- Добавлять deep nested `AGENTS.md` во все тяжёлые поддеревья `src/`; это остаётся project-owned enrichment.
- Делать repo-specific audit/review skill внутри шаблона до стабилизации базового onboarding/runtime truth.

## Влияние

- Affected specs:
  - `generated-project-agent-guidance`
  - `generated-context-artifacts`
  - `generated-runtime-support-matrix`
  - `runtime-profile-schema`
  - `template-ci-contours`
- Affected code:
  - `Makefile`
  - `scripts/qa/check-agent-docs.sh`
  - `scripts/qa/codex-onboard.sh`
  - `scripts/llm/export-context.sh`
  - `scripts/bootstrap/generated-project-surface.sh`
  - `automation/context/templates/*`
  - `docs/agent/generated-project-index.md`
  - `docs/agent/generated-project-verification.md`
  - `.codex/README.md`
  - root `README.md`
  - root `AGENTS.md`
  - `env/README.md`
  - relevant smoke and fixture tests under `tests/smoke/`
