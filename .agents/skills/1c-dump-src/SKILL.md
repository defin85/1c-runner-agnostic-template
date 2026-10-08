---
name: 1c-dump-src
description: Используйте, когда нужно выгрузить конфигурацию или расширение в исходники через канонический runtime contract проекта.
metadata:
  short-description: Выгрузка конфигурации в исходники.
---

# Agent Skill: 1c-dump-src

Repo script: `./scripts/platform/dump-src.sh`
Windows launcher: `./scripts/platform/dump-src.ps1`

## Use When

- Нужно выгрузить конфигурацию в исходники.
- Нужен repeatable dump через adapter-aware script contract.

## Usage

```bash
./scripts/platform/dump-src.sh --profile env/local.json
./scripts/platform/dump-src.sh --profile env/ci.json --run-root /tmp/dump-src-run
./scripts/platform/dump-src.sh --profile env/local.json --dry-run
./scripts/platform/dump-src.sh --profile env/local.json --output-dir ./build/dump --run-root /tmp/dump-src-run
./scripts/platform/dump-src.sh --profile env/local.json --info-only --output-dir ./build/dump-info
```

- `--output-dir <dir>` подменяет `capabilities.dumpSrc.outputDir` на один запуск.
- `--info-only` выгружает только `ConfigDumpInfo.xml` (`ibcmd config export info`); нужен драйвер `ibcmd`.
- Если в каталоге выгрузки уже есть `ConfigDumpInfo.xml`, ibcmd-выгрузка идёт инкрементально (`--sync`).
- `capabilities.dumpSrc.sourceFile` выгружает конфигурацию из файла `.cf` (`--file=`), а не из ИБ; с
  `--info-only` не сочетается.

## Rules

- Не описывайте вручную команды платформы внутри skill.
- Проверяйте `summary.json` как первичный verdict.
