---
name: 1c-create-ib
description: Используйте, когда нужно создать информационную базу через канонический runtime contract проекта.
metadata:
  short-description: Создание ИБ через repo-owned launcher.
---

# Agent Skill: 1c-create-ib

Repo script: `./scripts/platform/create-ib.sh`
Windows launcher: `./scripts/platform/create-ib.ps1`

## Use When

- Нужно создать новую ИБ.
- Нужен machine-readable результат в `summary.json`.

## Usage

```bash
./scripts/platform/create-ib.sh --profile env/local.json
./scripts/platform/create-ib.sh --profile env/ci.json --run-root /tmp/create-ib-run
./scripts/platform/create-ib.sh --profile env/local.json --dry-run
```

- `capabilities.createIb.registerInCluster: true` после успешного `ibcmd infobase create` регистрирует ИБ в
  кластере утилитой `rac` (команда `infobase create`) с запретом регламентных заданий. Нужны `infobase.mode=client-server`,
  `ibcmd.runtimeMode=dbms-infobase`, `platform.racPath`, `cluster.ras`, `infobase.ref`; при `clusterAdmin.user`
  также `clusterAdmin.passwordEnv`. ИБ с тем же именем повторно не регистрируется. Итог — в секции
  `registration` файла `summary.json`.
- `ibcmd.locale` задаёт локаль создаваемой ИБ (`--locale=`) и регистрации в кластере.

## Rules

- Не переносите runtime logic в skill.
- После выполнения начинайте разбор с `summary.json`.
