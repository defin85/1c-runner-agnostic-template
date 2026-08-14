# Трассировка требований

| Требование | Код | Автоматическое доказательство |
| --- | --- | --- |
| Runtime profile schema v3 и миграция v2 | `scripts/python/runtime_profiles.py`, `scripts/python/template_tools.py` | `tests/python/test_runtime_profile_v3.py` |
| Общее Python-ядро и безопасные примитивы | `scripts/python/runtime_*.py` | `tests/python/test_runtime_*.py` |
| Драйверы `designer`/`ibcmd` и core-команды | `scripts/python/runtime.py`, `scripts/python/runtime_selection.py` | `tests/python/test_runtime_selection.py`, `tests/python/test_thin_launchers.py`, `tests/python/test_cross_platform.py` |
| CFE lifecycle | `scripts/python/cfe_runtime.py` | `tests/python/test_cfe_runtime.py` |
| Apache/webinst и postconditions | `scripts/python/http_runtime.py`, `scripts/python/runtime_os.py` | `tests/python/test_http_runtime.py`, `tests/python/test_runtime_os.py` |
| BSL Analyzer MCP и штатный rendezvous | `scripts/python/bsl_mcp_runtime.py`, `scripts/platform/bsl-analyzer-mcp.*` | `tests/python/test_bsl_mcp_runtime.py` |
| POSIX-only Xpra/Xvfb/LD_PRELOAD | `scripts/python/runtime_profiles.py` | `tests/python/test_runtime_profile_v3.py` |
| Равная публичная поверхность | `Makefile`, `make.ps1`, `.agents/skills/`, `docs/` | `tests/python/test_thin_launchers.py`, `tests/python/test_cross_platform.py` |
| Платформенная матрица и срок доказательств | `scripts/python/template_tools.py`, `scripts/python/qa.py` | `tests/python/test_runtime_support_matrix.py` |
| Доставка управляемого слоя без перезаписи данных проекта | `automation/context/template-managed-paths.txt`, `scripts/template/` | `tests/smoke/copier-update-ready.sh`, `tests/smoke/template-release-workflow.sh` |
| Откат пары overlay/profile | `scripts/template/update-template.*`, `scripts/template/migrate-runtime-profile-v3.*` | `tests/smoke/runtime-overlay-rollback-contract.sh` |

## Откат

Откат выполняется штатным `template-update --vcs-ref <previous-tag>` вместе с восстановлением соответствующей schemaVersion 2 копии локального профиля. SchemaVersion 3 не записывается поверх локальных профилей автоматически; миграция сначала создаёт dry-run report. `src/**`, project-owned и local-private пути не входят в перезаписываемый слой.

Автоматическая репетиция обновляет проект с `v0.3.37` до текущего runtime, проверяет мигрированный schemaVersion 3 профиль, возвращает overlay на `v0.3.37` и запускает прежний `doctor` с неизменённым schemaVersion 2 профилем.
