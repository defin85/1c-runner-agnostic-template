---
name: 1c-load-src
description: Используйте, когда нужно загрузить исходники в информационную базу через канонический runtime contract проекта.
metadata:
  short-description: Загрузка исходников в ИБ.
---

# Agent Skill: 1c-load-src

Repo script: `./scripts/platform/load-src.sh`
Windows launcher: `./scripts/platform/load-src.ps1`

## Use When

- Нужно загрузить исходники конфигурации или расширения в ИБ.
- Нужен adapter-aware load с machine-readable артефактами.

## Usage

```bash
./scripts/platform/load-src.sh --profile env/local.json
./scripts/platform/load-src.sh --profile env/ci.json --run-root /tmp/load-src-run
./scripts/platform/load-src.sh --profile env/local.json --dry-run
./scripts/platform/load-src.sh --profile env/local.json --files "CommonModules/Module.xml,CommonModules/Module/Ext/Module.bsl"
./scripts/platform/load-src.sh --profile env/local.json --source-dir ./build/cf-candidate
```

- `--source-dir <dir>` подменяет `capabilities.loadSrc.sourceDir` на один запуск; профиль не меняется.
- `--override-unsupported-profile` разово снимает `capabilities.loadSrc.unsupportedReason`. Флаг принимается
  только с `--files` и явным `--run-root` и только для расходуемого профиля `env/<name>.json`, перечисленного в
  `automation/context/runtime-profile-policy.json` → `unsupportedOverride.loadSrc.allowedProfiles`.
  Причина снятого ограничения попадает в `summary.json` (`unsupported_override.reason`).

## Rules

- Не переносите shell/1C CLI в skill как inline logic.
- После выполнения сначала читайте `summary.json`.
- Частичная загрузка нового объекта должна включать его родителя: для общей формы — актуальный
  `Configuration.xml` с регистрацией формы. Для уже существующих объектов родитель не нужен.
- Не смешивайте в одной частичной загрузке Designer XML разных версий формата: выгружайте все файлы набора одной
  платформой или выравнивайте версию перед загрузкой.
