# Runtime Profile SchemaVersion 3

`schemaVersion: 3` делает локальное выполнение поведением по умолчанию и отделяет capability driver/backend от optional remote transport.

Проверить преобразование локального schemaVersion 2 профиля без записи:

```bash
./scripts/template/migrate-runtime-profile-v3.sh env/local.json
```

PowerShell:

```powershell
.\scripts\template\migrate-runtime-profile-v3.ps1 env\local.json
```

Команда выводит dry-run report с вложенным `profile`. Для получения только целевого JSON используйте `--profile-only`. Исходный local-private файл не изменяется автоматически.

Правила преобразования:

- `runnerAdapter=direct-platform` удаляется: отсутствие `transport` означает локальное выполнение;
- `runnerAdapter=remote-windows` преобразуется в `transport.kind=remote-windows`;
- стандартный `diffSrc.command=["git","diff","--","./src"]` удаляется в пользу встроенного repo-owned поведения;
- остальные profile-defined `command` завершают миграцию fail-closed, пока для них не определён структурированный backend.
