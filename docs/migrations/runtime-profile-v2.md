# Migration To Runtime Profile SchemaVersion 2

`schemaVersion: 1` больше не поддерживается. Launcher-скрипты и `doctor.sh` теперь принимают только `schemaVersion: 2`.

## Почему это breaking change

Старая схема хранила topology, authentication и shell-команды в `shellEnv`. Новая схема разделяет:

- `platform`
- `infobase`
- `capabilities`
- ссылки на секреты через `passwordEnv`

Это нужно, чтобы:

- валидировать profile как данные, а не как текст shell-команд;
- не хранить секреты в versioned JSON;
- собирать 1С argv из structured fields;
- делать doctor и summary redaction предсказуемыми.

## Что важно для existing generated projects

`copier update` не перепишет ignored local files:

- `env/local.json`
- `env/ci.json`
- `env/windows-executor.json`

Их владелец проекта должен мигрировать вручную.

## Быстрый путь

Сгенерируйте skeleton из legacy profile:

```bash
./scripts/template/migrate-runtime-profile-v2.sh env/local.json > /tmp/local.v2.json
```

Затем:

1. Проверьте `platform.binaryPath`.
2. Проверьте `infobase.mode`, `server`/`ref` или `filePath`.
3. Задайте `passwordEnv` вместо literal password.
4. Проверьте `capabilities.xunit`, `capabilities.bdd`, `capabilities.smoke` и `capabilities.publishHttp`.
   Generic shell placeholders, no-op commands и shell-wrapper chains helper теперь переводит в `unsupportedReason`.
   Автоматически сохраняются только прямой repo-owned entrypoint вроде `./scripts/...` или `make <target>` без `||`, `&&`, `;`, pipe/redirection.
5. Замените старый profile новым.
6. Прогоните `./scripts/diag/doctor.sh --profile <new-profile>`.

## Manual Mapping

### Было

```json
{
  "schemaVersion": 1,
  "shellEnv": {
    "LOAD_SRC_CMD": "/opt/1cv8/1cv8 DESIGNER /S localhost/project /LoadConfigFromFiles ./src/cf",
    "XUNIT_RUN_CMD": "echo run xunit"
  }
}
```

### Стало

```json
{
  "schemaVersion": 2,
  "runnerAdapter": "direct-platform",
  "platform": {
    "binaryPath": "/opt/1cv8/1cv8"
  },
  "infobase": {
    "mode": "client-server",
    "server": "localhost",
    "ref": "project",
    "auth": {
      "mode": "os",
      "user": null,
      "passwordEnv": null
    }
  },
  "capabilities": {
    "loadSrc": {
      "sourceDir": "./src/cf"
    },
    "xunit": {
      "unsupportedReason": "Legacy xUnit contour looked like a placeholder or no-op command; replace it with a repo-owned entrypoint before treating this profile as green."
    }
  }
}
```

## Secrets

Не переносите literal passwords из legacy command strings в JSON.

Используйте:

```bash
export ONEC_IB_PASSWORD='...'
```

И в profile:

```json
{
  "auth": {
    "mode": "user-password",
    "user": "ci-user",
    "passwordEnv": "ONEC_IB_PASSWORD"
  }
}
```
