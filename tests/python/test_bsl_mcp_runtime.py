from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.python.bsl_mcp_runtime import load_available_connections, load_dotenv, resolve_analyzer_executable, run_bsl_analyzer_mcp, select_source_dir
from scripts.python.runtime_process import ProcessResult
from scripts.python.runtime_errors import CommandError


class BslMcpRuntimeTests(unittest.TestCase):
    def test_dotenv_preserves_existing_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / ".env"
            path.write_text("TOKEN=from-file\r\nNAME=Тест\r\n", encoding="utf-8")
            with patch.dict(os.environ, {"TOKEN": "from-process"}, clear=True):
                load_dotenv(path)
                self.assertEqual(os.environ["TOKEN"], "from-process")
                self.assertEqual(os.environ["NAME"], "Тест")

    def test_registry_filters_only_connections_with_available_secret_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "connections.json"
            path.write_text(json.dumps({"connections": {
                "ready": {"user_env": "USER", "password_env": "PASS"},
                "missing": {"user_env": "USER", "password_env": "MISSING"},
            }}), encoding="utf-8")
            with patch.dict(os.environ, {"USER": "chatgpt", "PASS": "secret"}, clear=True):
                self.assertEqual(list(load_available_connections(path)), ["ready"])

    def test_source_selection_is_repo_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src" / "cf" / "Тест"
            source.mkdir(parents=True)
            (source / "Configuration.xml").write_text("", encoding="utf-8")
            self.assertEqual(select_source_dir(root, ["src/cf/Тест"]), source)
            with self.assertRaises(CommandError):
                select_source_dir(root, ["../foreign"])

    def test_launcher_delegates_broker_identity_and_cold_start_to_analyzer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src" / "cf"
            source.mkdir(parents=True)
            (source / "Configuration.xml").write_text("", encoding="utf-8")
            registry = root / "connections.json"
            registry.write_text('{"connections": {}}', encoding="utf-8")
            captured: dict[str, object] = {}

            def fake_run(command: list[str], **kwargs: object) -> ProcessResult:
                captured.update(command=command, env=kwargs["env"])
                return ProcessResult(command, 0, "", "")

            with (
                patch("scripts.python.bsl_mcp_runtime.project_root", return_value=root),
                patch("scripts.python.bsl_mcp_runtime.resolve_analyzer_executable", return_value="bsl-analyzer-app"),
                patch("scripts.python.bsl_mcp_runtime.embedding_is_ready", return_value=False),
                patch("scripts.python.bsl_mcp_runtime.run_process", side_effect=fake_run),
                patch.dict(os.environ, {"BSL_ONEC_CONNECTIONS_FILE": str(registry)}, clear=True),
            ):
                self.assertEqual(run_bsl_analyzer_mcp([]), 0)

            self.assertEqual(captured["command"], ["bsl-analyzer-app", "mcp", "serve", "--profile", "workspace", "--source-dir", str(source)])
            self.assertEqual(captured["env"]["BSL_MCP_BROKER"], "1")
            self.assertNotIn("BSL_MCP_BROKER_REGISTRY", captured["env"])

    def test_windows_rejects_auto_update_launcher_as_broker_parent(self) -> None:
        with (
            patch("scripts.python.bsl_mcp_runtime.WINDOWS", True),
            patch("scripts.python.bsl_mcp_runtime.Path.home", return_value=Path("C:/missing")),
            patch("scripts.python.bsl_mcp_runtime.resolve_executable", side_effect=CommandError("missing")),
            patch.dict(os.environ, {}, clear=True),
        ):
            with self.assertRaisesRegex(CommandError, "auto-update launcher"):
                resolve_analyzer_executable()

    def test_windows_rejects_explicit_auto_update_launcher(self) -> None:
        with (
            patch("scripts.python.bsl_mcp_runtime.WINDOWS", True),
            patch("scripts.python.bsl_mcp_runtime.resolve_executable", return_value="C:/tools/bsl-analyzer.exe"),
            patch.dict(os.environ, {"BSL_ANALYZER_EXECUTABLE": "C:/tools/bsl-analyzer.exe"}, clear=True),
        ):
            with self.assertRaisesRegex(CommandError, "stable broker parent"):
                resolve_analyzer_executable()

    def test_cancelled_proxy_removes_only_its_temporary_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src" / "cf"
            source.mkdir(parents=True)
            (source / "Configuration.xml").write_text("", encoding="utf-8")
            registry = root / "connections.json"
            registry.write_text('{"connections": {}}', encoding="utf-8")
            runtime_registry = root / "runtime-connections.json"
            with (
                patch("scripts.python.bsl_mcp_runtime.project_root", return_value=root),
                patch("scripts.python.bsl_mcp_runtime.resolve_analyzer_executable", return_value="bsl-analyzer-app"),
                patch("scripts.python.bsl_mcp_runtime.embedding_is_ready", return_value=False),
                patch("scripts.python.bsl_mcp_runtime.tempfile.gettempdir", return_value=temp_dir),
                patch("scripts.python.bsl_mcp_runtime.os.getpid", return_value=123),
                patch("scripts.python.bsl_mcp_runtime.run_process", side_effect=KeyboardInterrupt),
                patch.dict(os.environ, {"BSL_ONEC_CONNECTIONS_FILE": str(registry)}, clear=True),
            ):
                runtime_registry = root / "bsl-onec-connections-123.json"
                with self.assertRaises(KeyboardInterrupt):
                    run_bsl_analyzer_mcp([])
                self.assertFalse(runtime_registry.exists())


if __name__ == "__main__":
    unittest.main()
