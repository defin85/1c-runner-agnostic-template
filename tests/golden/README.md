# Golden Baseline

`golden-baseline` является обязательным проектным регрессионным контуром.

По умолчанию `tests/golden/run.sh` восстанавливает PostgreSQL snapshot через `tests/golden/restore.sh`.
Snapshot создаётся командой:

```bash
./tests/golden/create.sh --profile env/local.json --target target-id
```

Путь по умолчанию: `.artifacts/golden/target-id.dump`.

Для другого типа эталона замените `tests/golden/run.sh` на исполняемый проектный скрипт, который возвращает ненулевой код при расхождении.

До настройки профиля и snapshot `make golden-baseline` завершается fail-closed.
