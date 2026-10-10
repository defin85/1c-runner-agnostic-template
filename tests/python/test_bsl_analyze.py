"""`make analyze-bsl` through the `bsl-analyzer` MCP server, checked against a fake MCP server."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from scripts.python import bsl_analyze
from scripts.python.common import CommandError

FAKE_SERVER = r"""
import json, os, subprocess, sys, time

mode = os.environ["FAKE_MCP_MODE"]
findings = json.loads(os.environ.get("FAKE_MCP_FINDINGS", "{}"))
pid_file = os.environ.get("FAKE_MCP_PID_FILE")
if pid_file:
    with open(pid_file, "w", encoding="utf-8") as handle:
        handle.write(str(os.getpid()))
status_calls = 0


def reply(request, result):
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)


for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    if "id" not in request:
        continue
    if method == "initialize":
        reply(request, {"serverInfo": {"name": "fake-bsl-analyzer", "version": "0.0.1"}})
        if mode == "hang":
            child = os.environ["FAKE_MCP_CHILD_SCRIPT"]
            subprocess.Popen([sys.executable, "-c", child, os.environ["FAKE_MCP_HELD_FILE"]],
                             stdin=subprocess.DEVNULL)
            time.sleep(300)
        continue
    arguments = request["params"]["arguments"]
    if arguments["action"] == "status":
        status_calls += 1
        state = "loading" if status_calls == 1 else ("failed" if mode == "failed" else "ready")
        reply(request, {"structuredContent": {"state": state, "generation": 1, "files": 1, "error": "index broken"}})
        continue
    items = findings.get(arguments["path"], [])
    counts = {"error": 0, "warning": len(items), "info": 0, "hint": 0}
    reply(request, {"structuredContent": {"revision": 7, "result": {"findings": items, "counts": counts}}})
"""

# Holds a file open and sleeps: a descendant that must not survive the stopped server.
HELD_CHILD = (
    "import os, sys, time\n"
    "handle = open(sys.argv[1], 'w')\n"
    "handle.write(str(os.getpid())); handle.flush()\n"
    "time.sleep(300)\n"
)

MODULE = "src/cf/CommonModules/Common/Ext/Module.bsl"


def _finding(line: int, code: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "warning",
        "message": message,
        "range": {"start_line": line, "start_column": 0, "end_line": line, "end_column": 5},
    }


def _exception(identifier: str, line: int, rule: str, message: str) -> dict[str, Any]:
    exact = {"path": MODULE, "line": line, "rule": rule, "message": message}
    return {"finding": identifier, **exact, "fingerprint": bsl_analyze._diagnostic_fingerprint(exact)}


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in list(os.environ):
        if name.startswith(("BSL_", "FAKE_MCP_")):
            monkeypatch.delenv(name)
    module = tmp_path / MODULE
    module.parent.mkdir(parents=True)
    module.write_text("Процедура Тест()\nКонецПроцедуры\n", encoding="utf-8")
    (tmp_path / "src/cf/Configuration.xml").write_text("<MetaDataObject/>", encoding="utf-8")
    server = tmp_path / "fake_mcp_server.py"
    server.write_text(FAKE_SERVER, encoding="utf-8")
    monkeypatch.setattr(bsl_analyze, "project_root", lambda: tmp_path)
    monkeypatch.setenv("BSL_ANALYZER_MCP_BIN", str(server))
    monkeypatch.setenv("BSL_ANALYZER_MCP_TIMEOUT", "10")
    monkeypatch.setenv("FAKE_MCP_MODE", "ok")
    return tmp_path


def test_reports_unexpected_diagnostics(
    workspace: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FAKE_MCP_FINDINGS", json.dumps({MODULE: [_finding(1, "UnusedVariable", "unused x")]}))
    report = workspace / "out/report.json"
    monkeypatch.setenv("BSL_ANALYZER_REPORT", str(report))

    assert bsl_analyze.analyze_bsl([]) == 1

    assert f"- {MODULE}:2: UnusedVariable — unused x" in capsys.readouterr().err
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["analyzer"] == {"name": "fake-bsl-analyzer", "version": "0.0.1"}
    assert payload["sourceRoot"] == "src/cf"
    assert payload["moduleCount"] == 1 and payload["total"] == 1
    assert payload["analyzerRevisions"] == [7]
    assert payload["diagnostics"][0]["line"] == 2 and payload["diagnostics"][0]["column"] == 1


def test_clean_tree_passes(workspace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert bsl_analyze.analyze_bsl() == 0
    assert "BSL analysis passed: 1 modules, 0 diagnostics, 0 exact exceptions" in capsys.readouterr().out


def test_exact_exceptions_hide_only_registered_findings(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    known = _finding(1, "UnusedVariable", "unused x")
    findings = {MODULE: [known]}
    monkeypatch.setenv("FAKE_MCP_FINDINGS", json.dumps(findings))
    registry = workspace / bsl_analyze.DEFAULT_EXCEPTIONS_FILE
    registry.write_text(
        json.dumps({"schemaVersion": 1, "exceptions": [_exception("EX-001", 2, "UnusedVariable", "unused x")]}),
        encoding="utf-8",
    )
    assert bsl_analyze.analyze_bsl() == 0

    findings[MODULE].append(_finding(1, "UnusedVariable", "new issue"))
    monkeypatch.setenv("FAKE_MCP_FINDINGS", json.dumps(findings))
    assert bsl_analyze.analyze_bsl() == 1

    monkeypatch.setenv("FAKE_MCP_FINDINGS", "{}")
    with pytest.raises(CommandError, match="stale or drifted"):
        bsl_analyze.analyze_bsl()


@pytest.mark.parametrize("identifier", ["", "ex-1", "EX", "EX-1a"])
def test_exception_registry_rejects_invalid_identifiers(tmp_path: Path, identifier: str) -> None:
    registry = tmp_path / "exceptions.json"
    entry = _exception(identifier, 2, "Rule", "message")
    registry.write_text(json.dumps({"schemaVersion": 1, "exceptions": [entry]}), encoding="utf-8")
    with pytest.raises(CommandError, match="invalid exact BSL diagnostic exception"):
        bsl_analyze._load_diagnostic_exceptions(registry)


def test_refresh_moves_exceptions_to_new_lines(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_MCP_FINDINGS", json.dumps({MODULE: [_finding(4, "UnusedVariable", "unused x")]}))
    registry = workspace / "exceptions.json"
    registry.write_text(
        json.dumps({"schemaVersion": 1, "exceptions": [_exception("EX-002", 2, "UnusedVariable", "unused x")]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("BSL_ANALYZER_EXCEPTIONS", str(registry))
    monkeypatch.setenv("BSL_ANALYZER_REFRESH_RELOCATED_EXCEPTIONS", "1")

    assert bsl_analyze.analyze_bsl() == 0

    refreshed = json.loads(registry.read_text(encoding="utf-8"))["exceptions"]
    assert refreshed == [_exception("EX-002", 5, "UnusedVariable", "unused x")]


def test_resident_failure_stops_the_command(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_MCP_MODE", "failed")
    with pytest.raises(CommandError, match="resident failed: index broken"):
        bsl_analyze.analyze_bsl()


def test_missing_analyzer_points_to_runbook(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BSL_ANALYZER_MCP_BIN")
    monkeypatch.setenv("BSL_ANALYZER_EXECUTABLE", str(workspace / "missing-analyzer"))
    with pytest.raises(CommandError) as error:
        bsl_analyze.analyze_bsl()
    assert "bsl-analyzer is not configured" in str(error.value)
    assert bsl_analyze.RUNBOOK in str(error.value)
    assert error.value.exit_code != 0


def test_missing_connection_registry_points_to_runbook(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BSL_ANALYZER_MCP_BIN")
    analyzer = workspace / "bin" / "bsl-analyzer-app"
    analyzer.parent.mkdir()
    analyzer.write_text("", encoding="utf-8")
    monkeypatch.setenv("BSL_ANALYZER_EXECUTABLE", str(analyzer))
    with pytest.raises(CommandError, match=r"connection registry is missing.*bsl-analyzer-workspace-runbook\.md"):
        bsl_analyze.analyze_bsl()


def test_missing_source_root_points_to_runbook(workspace: Path) -> None:
    (workspace / "src/cf/Configuration.xml").unlink()
    with pytest.raises(CommandError, match=r"not configured.*bsl-analyzer-workspace-runbook\.md"):
        bsl_analyze.analyze_bsl()


def test_missing_launcher_points_to_runbook(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BSL_ANALYZER_MCP_BIN", str(workspace / "absent.py"))
    with pytest.raises(CommandError, match=r"not configured.*bsl-analyzer-workspace-runbook\.md"):
        bsl_analyze.analyze_bsl()


def test_default_command_starts_repository_mcp_server(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BSL_ANALYZER_MCP_BIN")
    registry = workspace / "env/.local/bsl-onec-connections.json"
    registry.parent.mkdir(parents=True)
    registry.write_text('{"connections": {}}', encoding="utf-8")
    with patch.object(bsl_analyze, "resolve_analyzer_executable", return_value="bsl-analyzer-app"):
        assert bsl_analyze._mcp_command(workspace) == [
            sys.executable,
            "-m",
            "scripts.python.cli",
            "bsl-analyzer-mcp",
        ]


def test_rejects_positional_arguments() -> None:
    with pytest.raises(CommandError, match="does not accept arguments"):
        bsl_analyze.analyze_bsl(["src/cf"])


def _process_gone(pid: int) -> bool:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        try:
            stat = Path(f"/proc/{pid}/stat").read_text(encoding="ascii", errors="replace")
        except OSError:
            stat = ""
        if stat.rpartition(")")[2].split()[:1] == ["Z"]:
            return True  # Stopped but not reaped by a container PID 1.
        time.sleep(0.1)
    return False


def test_hung_server_times_out_and_its_tree_is_stopped(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    server_pid = workspace / "server.pid"
    held = workspace / "held.txt"
    monkeypatch.setenv("FAKE_MCP_MODE", "hang")
    monkeypatch.setenv("FAKE_MCP_PID_FILE", str(server_pid))
    monkeypatch.setenv("FAKE_MCP_CHILD_SCRIPT", HELD_CHILD)
    monkeypatch.setenv("FAKE_MCP_HELD_FILE", str(held))
    monkeypatch.setenv("BSL_ANALYZER_MCP_TIMEOUT", "3")

    with pytest.raises(CommandError, match="request timed out: tools/call"):
        bsl_analyze.analyze_bsl()

    assert not bsl_analyze._mcp_process_cleanup
    if os.name == "nt":
        held.unlink()  # Windows refuses while the descendant still holds the file.
        return
    assert _process_gone(int(server_pid.read_text(encoding="utf-8")))
    assert _process_gone(int(held.read_text(encoding="utf-8")))


@pytest.mark.parametrize("mode", ["eof", "invalid", "error"])
def test_protocol_failures_do_not_echo_server_output(mode: str) -> None:
    script = (
        "import sys, json\n"
        "request = json.loads(sys.stdin.readline())\n"
        "mode = sys.argv[1]\n"
        "if mode == 'invalid': print('invalid secret-canary', flush=True)\n"
        "if mode == 'error': print(json.dumps({'id': request['id'], "
        "'error': {'code': -42, 'message': 'secret-canary'}}), flush=True)\n"
    )
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr:
        process = bsl_analyze._spawn_mcp_process([sys.executable, "-c", script, mode], Path.cwd(), stderr)
        responses, reader = bsl_analyze._start_mcp_reader(process)
        try:
            with pytest.raises(CommandError) as error:
                bsl_analyze._mcp_request(process, 1, "initialize", {}, 5, responses)
            assert "secret-canary" not in str(error.value)
        finally:
            bsl_analyze._stop_mcp_process(process, reader)
    assert process.poll() is not None and not reader.is_alive()


def test_cleanup_error_still_reaps_process_and_reader() -> None:
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr:
        process = bsl_analyze._spawn_mcp_process(
            [sys.executable, "-c", "import time; time.sleep(30)"], Path.cwd(), stderr
        )
        _, reader = bsl_analyze._start_mcp_reader(process)
        stop = bsl_analyze._mcp_process_cleanup[process.pid]

        def failed_stop() -> None:
            stop()
            raise OSError("job accounting query failed")

        bsl_analyze._mcp_process_cleanup[process.pid] = failed_stop
        with pytest.raises(OSError, match="job accounting"):
            bsl_analyze._stop_mcp_process(process, reader)
    assert process.poll() is not None and not reader.is_alive()
    assert process.stdout is not None and process.stdout.closed


def test_launcher_command_by_suffix(tmp_path: Path) -> None:
    script = tmp_path / "с пробелом.py"
    assert bsl_analyze._mcp_launcher_command(script) == [sys.executable, str(script)]
    assert bsl_analyze._mcp_launcher_command(script.with_suffix(".sh")) == ["bash", str(script.with_suffix(".sh"))]
    with patch.object(bsl_analyze.shutil, "which", return_value="pwsh"):
        assert bsl_analyze._mcp_launcher_command(script.with_suffix(".ps1")) == [
            "pwsh",
            "-NoLogo",
            "-NoProfile",
            "-File",
            str(script.with_suffix(".ps1")),
        ]


# Windows model: the real Job object is exercised only by the Windows CI job; here the spawn order is checked.


def _fake_popen() -> MagicMock:
    process = MagicMock(spec=subprocess.Popen)
    process.pid = 4242
    process.stdin = MagicMock()
    process.stdout = MagicMock()
    return process


def test_windows_spawn_starts_suspended_and_registers_job() -> None:
    process = _fake_popen()
    close_job = MagicMock()
    with (
        patch.object(bsl_analyze.subprocess, "Popen", return_value=process) as popen,
        patch.object(bsl_analyze, "_windows_mcp_job", return_value=close_job) as job,
    ):
        spawned = bsl_analyze._spawn_mcp_process(["server"], Path.cwd(), MagicMock(), windows=True)
    assert spawned is process
    options = popen.call_args.kwargs
    assert options["creationflags"] == bsl_analyze.CREATE_SUSPENDED
    assert options["start_new_session"] is False
    job.assert_called_once_with(process)
    assert bsl_analyze._mcp_process_cleanup.pop(process.pid) is close_job


def test_windows_spawn_kills_launcher_when_job_assignment_fails() -> None:
    process = _fake_popen()
    with (
        patch.object(bsl_analyze.subprocess, "Popen", return_value=process),
        patch.object(bsl_analyze, "_windows_mcp_job", side_effect=OSError("access denied")),
        pytest.raises(OSError, match="access denied"),
    ):
        bsl_analyze._spawn_mcp_process(["server"], Path.cwd(), MagicMock(), windows=True)
    process.kill.assert_called_once_with()
    assert process.pid not in bsl_analyze._mcp_process_cleanup


def test_stop_closes_the_windows_job_after_grace_period() -> None:
    process = _fake_popen()
    process.wait.side_effect = [subprocess.TimeoutExpired("server", 2), 0]
    calls: list[str] = []
    process.stdin.close.side_effect = lambda: calls.append("stdin")
    bsl_analyze._mcp_process_cleanup[process.pid] = lambda: calls.append("job")
    bsl_analyze._stop_mcp_process(process)
    assert calls == ["stdin", "job"]
    assert process.pid not in bsl_analyze._mcp_process_cleanup


@pytest.mark.skipif(sys.platform == "win32", reason="checks the non-Windows guard")
def test_windows_job_is_refused_outside_windows() -> None:
    with pytest.raises(OSError, match="only on Windows"):
        bsl_analyze._windows_mcp_job(_fake_popen())


# Standalone mode: `bsl-analyzer-app analyze` without the resident server.


def _standalone_run(module: Path, diagnostics: list[dict[str, Any]], scenario: str = "clean"):
    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, stdout="test-analyzer\n")
        assert command[1:] == ["analyze", "--source-dir", str(module.parent), "--workers", "1", "--format", "jsonl"]
        if scenario != "missing":
            event = {"type": "file", "path": str(module), "diagnostics": diagnostics}
            kwargs["stdout"].write(json.dumps(event) + "\n")
        kwargs["stdout"].write(json.dumps({"type": "done", "failed_files": 0}) + "\n")
        return subprocess.CompletedProcess(command, 1 if scenario == "failed" else 0)

    return run


@pytest.mark.parametrize(("scenario", "expected"), [("clean", 0), ("missing", 1), ("finding", 1), ("failed", 1)])
def test_standalone_reports_exact_coverage(tmp_path: Path, scenario: str, expected: int) -> None:
    module = tmp_path / "Module.bsl"
    module.write_text("", encoding="utf-8")
    report = tmp_path / "evidence/report.json"
    diagnostics = [{"code": "Rule", "message": "m", "start_line": 0}] if scenario == "finding" else []
    with (
        patch.object(bsl_analyze, "analyzer_available", return_value=True),
        patch("subprocess.run", side_effect=_standalone_run(module, diagnostics, scenario)),
    ):
        assert bsl_analyze._analyze_bsl_standalone(tmp_path, [module], report) == expected
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["version"] == "test-analyzer"
    assert result["files"] == [str(module)]
    assert result["exit_code"] == expected


def test_standalone_uses_exact_exceptions(tmp_path: Path) -> None:
    module = tmp_path / "Module.bsl"
    module.write_text("", encoding="utf-8")
    report = tmp_path / "evidence/report.json"
    exceptions = tmp_path / "exceptions.json"
    diagnostic = {"code": "TypeMismatch", "message": "known mismatch", "severity": "warning", "start_line": 2}
    exact = {"path": "Module.bsl", "line": 3, "rule": "TypeMismatch", "message": "known mismatch"}
    entry = {"finding": "EX-010", **exact, "fingerprint": bsl_analyze._diagnostic_fingerprint(exact)}
    exceptions.write_text(json.dumps({"schemaVersion": 1, "exceptions": [entry]}), encoding="utf-8")
    diagnostics = [diagnostic]
    with (
        patch.object(bsl_analyze, "analyzer_available", return_value=True),
        patch("subprocess.run", side_effect=_standalone_run(module, diagnostics)),
    ):
        assert bsl_analyze._analyze_bsl_standalone(tmp_path, [module], report, exceptions, tmp_path) == 0
        diagnostics.append({**diagnostic, "message": "new issue"})
        assert bsl_analyze._analyze_bsl_standalone(tmp_path, [module], report, exceptions, tmp_path) == 1
        assert json.loads(report.read_text(encoding="utf-8"))["unexpected_findings"] == 1
        diagnostics.clear()
        with pytest.raises(CommandError, match="stale or drifted"):
            bsl_analyze._analyze_bsl_standalone(tmp_path, [module], report, exceptions, tmp_path)
        assert json.loads(report.read_text(encoding="utf-8"))["exit_code"] == 1


def test_standalone_without_analyzer_points_to_runbook(tmp_path: Path) -> None:
    with (
        patch.object(bsl_analyze, "analyzer_available", return_value=False),
        pytest.raises(CommandError, match=r"not configured.*bsl-analyzer-workspace-runbook\.md"),
    ):
        bsl_analyze._analyze_bsl_standalone(tmp_path, [tmp_path / "Module.bsl"], tmp_path / "report.json")
