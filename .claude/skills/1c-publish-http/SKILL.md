---
name: 1c-publish-http
description: >
  Этот скилл SHOULD быть вызван, когда пользователь просит опубликовать
  HTTP-сервис или веб-контур через канонический repo entrypoint.
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /1c-publish-http

Repo script: `./scripts/platform/publish-http.sh`

## Use When

- Нужно опубликовать HTTP-сервис через project runtime contract.
- Нужно получить единый verdict и machine-readable артефакты прогона.

## Usage

```bash
./scripts/platform/publish-http.sh --profile env/local.json
./scripts/platform/publish-http.sh --profile env/ci.json --run-root /tmp/publish-http
./scripts/platform/publish-http.sh --profile env/local.json --dry-run
```

## Rules

- Capability optional и project-specific, но script contract остаётся repo-owned.
- Не переносить в skill platform/webinst-логику.
