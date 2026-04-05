# Automation Context

Этот каталог предназначен для машинно-читаемого контекста проекта.

## Routing

- В template source repo authoritative live context начинается с `automation/context/template-source-project-map.md` и соседних `template-source-*`.
- В generated repo authoritative curated truth начинается с `automation/context/project-map.md`.
- В generated repo checked-in runtime truth начинается с `automation/context/runtime-support-matrix.md` и `automation/context/runtime-support-matrix.json`.
- В generated repo compact first-hour skill routing начинается с `automation/context/recommended-skills.generated.md`.
- В generated repo summary-first derived onboarding начинается с `automation/context/hotspots-summary.generated.md`.
- В generated repo derived inventory нужно читать через `automation/context/metadata-index.generated.json` и `automation/context/source-tree.generated.txt`, не принимая их за project-owned доменную истину.
- Policy для sanctioned checked-in runtime presets в generated repo живёт в `automation/context/runtime-profile-policy.json`.
- `automation/context/runtime-support-matrix.*` фиксирует, какие contour-ы `supported`, `unsupported`, `operator-local`, `provisioned`.
- Если вы вошли в generated repo и вам нужен onboarding route, начните с `docs/agent/generated-project-index.md`, а не с source-repo-centric `docs/agent/index.md`.

## Что здесь хранить

- truthful live context для template source repo;
- template-scoped skeleton context для generated projects;
- краткую карту проекта;
- индексы метаданных;
- reusable checklists;
- prompts для повторяемых задач;
- generated артефакты, которые помогают агентам быстрее ориентироваться.

## Layout

- `automation/context/template-source-*` описывает текущий template source repo.
- `automation/context/templates/` хранит skeleton files для generated projects.
- Generated projects не должны принимать `template-source-*` за свой live context или business-domain карту.
- `automation/context/project-map.md` остаётся project-owned router/картой generated repo.
- `automation/context/runtime-profile-policy.json` остаётся project-owned policy-файлом generated repo.
- `automation/context/runtime-support-matrix.md` и `automation/context/runtime-support-matrix.json` остаются project-owned runtime truth-файлами generated repo.
- `automation/context/recommended-skills.generated.md`, `automation/context/hotspots-summary.generated.md`, `automation/context/metadata-index.generated.json` и `automation/context/source-tree.generated.txt` остаются generated-derived и privacy-safe.

## Что не хранить

- секреты;
- большие бинарные артефакты;
- production dumps;
- временные логи выполнения;
- `local-private` runtime profiles и machine-specific Codex/MCP overrides.
