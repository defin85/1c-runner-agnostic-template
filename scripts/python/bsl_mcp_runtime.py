from __future__ import annotations

import json
import os
import socket
import tempfile
from pathlib import Path
from typing import Any

from .common import WINDOWS, CommandError, project_root
from .runtime_atomic import atomic_write_json
from .runtime_process import resolve_executable, run_process


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"\''))


def load_available_connections(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    connections = payload.get("connections")
    if not isinstance(connections, dict):
        raise CommandError(f"BSL Analyzer connection registry is invalid: {path}")
    available: dict[str, Any] = {}
    for name, connection in connections.items():
        if not isinstance(connection, dict):
            raise CommandError(f"BSL Analyzer connection is invalid: {name}")
        refs = [str(connection.get(key) or "") for key in ("user_env", "password_env")]
        if all(not ref or os.environ.get(ref) for ref in refs):
            available[name] = connection
    return available


def select_source_dir(root: Path, candidates: list[str]) -> Path:
    for candidate in candidates:
        path = root / candidate
        resolved = path.resolve(strict=False)
        try:
            resolved.relative_to(root.resolve(strict=False))
        except ValueError:
            raise CommandError(f"BSL Analyzer source path escapes repository: {candidate}")
        if (resolved / "Configuration.xml").is_file():
            return path
    if (root / "bsl-analyzer.toml").is_file():
        return root
    raise CommandError("No configured 1C source root with Configuration.xml is available.")


def embedding_is_ready(host: str = "127.0.0.1", port: int = 8000) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def resolve_analyzer_executable() -> str:
    configured = os.environ.get("BSL_ANALYZER_EXECUTABLE")
    if configured:
        resolved = resolve_executable(configured)
        if WINDOWS and Path(resolved).name.lower() == "bsl-analyzer.exe":
            raise CommandError("bsl-analyzer-app.exe is required on Windows; the auto-update launcher is not a stable broker parent")
        return resolved
    if WINDOWS:
        cached_app = Path.home() / ".bsl-analyzer" / "bin" / "bsl-analyzer-app.exe"
        if cached_app.is_file():
            return str(cached_app)
        try:
            return resolve_executable("bsl-analyzer-app.exe")
        except CommandError as error:
            raise CommandError(
                "bsl-analyzer-app.exe is required on Windows; the bsl-analyzer.exe "
                "auto-update launcher can terminate the detached broker daemon"
            ) from error
    return resolve_executable("bsl-analyzer-app")


def run_bsl_analyzer_mcp(argv: list[str]) -> int:
    if argv:
        raise CommandError("bsl-analyzer-mcp does not accept positional arguments")
    root = project_root()
    load_dotenv(root / ".env")
    registry_path = Path(os.environ.get("BSL_ONEC_CONNECTIONS_FILE", root / "env" / ".local" / "bsl-onec-connections.json"))
    if not registry_path.is_file():
        raise CommandError(f"BSL Analyzer connection registry is missing: {registry_path}")
    candidates = [item for item in os.environ.get("BSL_ANALYZER_SOURCE_CANDIDATES", "src/cf").split(os.pathsep) if item]
    source_dir = select_source_dir(root, candidates)
    executable = resolve_analyzer_executable()
    available = load_available_connections(registry_path)
    runtime_registry = Path(tempfile.gettempdir()) / f"bsl-onec-connections-{os.getpid()}.json"
    atomic_write_json(runtime_registry, {"connections": available})
    child_env = {
        "BSL_ONEC_CONNECTIONS_FILE": str(runtime_registry),
        "BSL_MCP_BROKER": os.environ.get("BSL_MCP_BROKER", "1"),
        "BSL_MCP_IDLE_TTL_SECS": os.environ.get("BSL_MCP_IDLE_TTL_SECS", "1800"),
    }
    if embedding_is_ready():
        child_env.update({"EMBEDDING_URL": os.environ.get("EMBEDDING_URL", "http://127.0.0.1:8000"), "EMBEDDING_MODEL": os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3"), "EMBEDDING_DIM": os.environ.get("EMBEDDING_DIM", "1024"), "EMBEDDING_BATCH_SIZE": os.environ.get("EMBEDDING_BATCH_SIZE", "32")})
    try:
        return run_process([executable, "mcp", "serve", "--profile", "workspace", "--source-dir", str(source_dir)], cwd=root, env=child_env, capture_output=False).returncode
    finally:
        runtime_registry.unlink(missing_ok=True)
