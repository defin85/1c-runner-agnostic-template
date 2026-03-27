---
name: 1c-load-diff-src
description: >
  Этот скилл MUST быть вызван, когда пользователь просит загрузить в ИБ
  только текущие git-backed изменения исходников через repo-owned bridge.
allowed-tools:
  - Bash
  - Read
  - Glob
---

# /1c-load-diff-src

Repo script: `./scripts/platform/load-diff-src.sh`

## Use When

- Нужно загрузить в ИБ только текущий diff исходников внутри `src/cf`.
- Нужен repo-owned bridge от git-backed selection к `load-src --files`.
- Нужны machine-readable wrapper artifacts и delegated `load-src` summary.

## Usage

```bash
./scripts/platform/load-diff-src.sh --profile env/local.json
./scripts/platform/load-diff-src.sh --profile env/ci.json --run-root /tmp/load-diff-src-run
./scripts/platform/load-diff-src.sh --profile env/local.json --dry-run
```

## Rules

- Не переносить `git diff -> --files` shell logic в `SKILL.md`.
- Сначала читать wrapper `summary.json`, затем delegated `load-src` artifacts.
