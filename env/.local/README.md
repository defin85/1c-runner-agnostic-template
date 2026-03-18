# Local Runtime Profile Sandbox

Этот каталог предназначен для ad-hoc и machine-specific runtime profiles.

Сюда складывайте временные контуры вроде:

- `develop.json`
- `do-rolf.json`
- `local-ibcmd.json`

Корень `env/` оставляйте только для канонических имён:

- `env/local.json`
- `env/wsl.json`
- `env/ci.json`
- `env/windows-executor.json`
- versioned `env/*.example.json`

Важно:

- launcher по умолчанию автоматически ищет только `env/local.json`;
- `env/.local/*` не сканируется как implicit default;
- JSON-профили внутри `env/.local/` игнорируются Git.
