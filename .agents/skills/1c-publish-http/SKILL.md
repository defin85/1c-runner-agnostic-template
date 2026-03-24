---
name: 1c-publish-http
description: Используйте, когда нужно опубликовать HTTP-сервис или web contour через канонический repo entrypoint.
metadata:
  short-description: Публикация HTTP-контура.
---

# Agent Skill: 1c-publish-http

Repo script: `./scripts/platform/publish-http.sh`

## Use When

- Нужно опубликовать HTTP-сервис через project runtime contract.
- Нужен единый verdict и machine-readable артефакты.

## Usage

```bash
./scripts/platform/publish-http.sh --profile env/local.json
./scripts/platform/publish-http.sh --profile env/ci.json --run-root /tmp/publish-http
./scripts/platform/publish-http.sh --profile env/local.json --dry-run
```

## Rules

- Capability optional и project-specific, но script contract остаётся repo-owned.
- Не переносите platform/webinst logic в skill.
