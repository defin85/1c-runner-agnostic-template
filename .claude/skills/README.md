# Project-Scoped 1C Skills

Эти skills являются project-scoped фасадом над versioned repo scripts.
Codex-facing equivalents лежат в [.agents/skills/README.md](../../.agents/skills/README.md).

## Mapping

| User intent | Codex skill | Claude skill | Repo entrypoint |
| --- | --- | --- | --- |
| Проверить baseline docs/tooling/OpenSpec surface | `repo-agent-verify` | - | `./scripts/qa/agent-verify.sh` |
| Создать ИБ | `1c-create-ib` | `1c-create-ib` | `./scripts/platform/create-ib.sh` |
| Выгрузить конфигурацию в исходники | `1c-dump-src` | `1c-dump-src` | `./scripts/platform/dump-src.sh` |
| Загрузить исходники в ИБ | `1c-load-src` | `1c-load-src` | `./scripts/platform/load-src.sh` |
| Загрузить в ИБ только текущий diff исходников | `1c-load-diff-src` | `1c-load-diff-src` | `./scripts/platform/load-diff-src.sh` |
| Загрузить в ИБ уже закомиченные изменения задачи | `1c-load-task-src` | `1c-load-task-src` | `./scripts/platform/load-task-src.sh` |
| Применить изменения к БД | `1c-update-db` | `1c-update-db` | `./scripts/platform/update-db.sh` |
| Посмотреть diff исходников | `1c-diff-src` | `1c-diff-src` | `./scripts/platform/diff-src.sh` |
| Запустить xUnit | `1c-run-xunit` | `1c-run-xunit` | `./scripts/test/run-xunit.sh` |
| Запустить BDD | `1c-run-bdd` | `1c-run-bdd` | `./scripts/test/run-bdd.sh` |
| Запустить smoke | `1c-run-smoke` | `1c-run-smoke` | `./scripts/test/run-smoke.sh` |
| Проверить runtime readiness | `1c-doctor` | `1c-doctor` | `./scripts/diag/doctor.sh` |
| Опубликовать HTTP-сервис | `1c-publish-http` | `1c-publish-http` | `./scripts/platform/publish-http.sh` |

## Rules

- Source of truth для выполнения находится в `scripts/`, а не в `SKILL.md`.
- Если нужно поменять flags, artifact contract или adapter behavior, сначала меняйте repo script.
- Каждая automation-сессия должна использовать `summary.json`, `stdout.log` и `stderr.log` из `run-root`.
- Для явного выбора runtime profile используйте `--profile env/<name>.json`.
