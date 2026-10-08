"""Shared observation adapter for long 1C operations (Linux and Windows).

``run_observed`` starts the command in its own process group and writes
``<run-root>/observation.jsonl`` (schema v1): one ``started`` event, heartbeats
every ``ONEC_OBSERVATION_INTERVAL_SECONDS`` (default 30) and exactly one terminal
``completed`` or ``failed`` event. The caller may pass an application progress
file and a stall threshold: only then the adapter stops the process group when
the progress content stops changing. Without a threshold heartbeats report
``stageAgeSeconds`` and the operation keeps running.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .runtime_atomic import atomic_write_json
from .runtime_errors import CommandError
from .runtime_techlog import TechlogPlan, TechlogSession

OBSERVATION_FILE = "observation.jsonl"
PROGRESS_FILE = "progress.txt"
TERMINAL_EXTRA_FILE = "terminal-observation-extra.json"
SCHEMA_VERSION = 1
MAX_BYTES = 1_048_576
MAX_LINE_BYTES = 4096
TERMINAL_RESERVE_BYTES = 4096
EXIT_MISSING_RESULT = 70
EXIT_TIMEOUT = 124
EXIT_STALLED = 125
EXIT_LAUNCH_FAILED = 127
RESERVED_KEYS = {
    "schemaVersion",
    "seq",
    "timestamp",
    "elapsedSeconds",
    "capability",
    "target",
    "event",
    "source",
    "exitCode",
    "droppedEvents",
}
SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
SAFE_TARGET = re.compile(r"^[A-Za-z0-9_.:/-]{1,256}$")
SAFE_PROGRESS = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
WINDOWS = os.name == "nt"


PLATFORM_PROCESSES = {"1cv8", "1cv8c", "1cv8.exe", "1cv8c.exe"}


def launch_identity(run_root: Path, command: Sequence[str]) -> tuple[dict[str, str], Callable[[int], None] | None]:
    """Where the PID of the actual platform process is recorded for log correlation and run-client.

    A platform binary started directly is the observed child itself; a wrapper such as
    ``direct-platform.sh`` writes the PID of the platform process it starts.
    """
    pid_file = run_root / "process.pid"
    pid_file.unlink(missing_ok=True)
    if command and Path(str(command[0])).name.lower() in PLATFORM_PROCESSES:

        def record(pid: int) -> None:
            pid_file.write_text(f"{pid}\n", encoding="ascii")

        return {}, record
    return {"ONEC_DIRECT_PLATFORM_COMMAND_PID_FILE": str(pid_file)}, None


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def interval_from_env() -> float:
    value = os.environ.get("ONEC_OBSERVATION_INTERVAL_SECONDS", "30").strip()
    if not value.isdigit() or not 1 <= int(value) <= 30:
        raise CommandError("ONEC_OBSERVATION_INTERVAL_SECONDS must be an integer 1..30")
    return float(value)


def positive_seconds(value: str | float | None, name: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise CommandError(f"{name} must be a positive number of seconds") from None
    if not number > 0 or number == float("inf"):
        raise CommandError(f"{name} must be a positive number of seconds")
    return number


def stall_timeout_from_env() -> float | None:
    return positive_seconds(
        os.environ.get("ONEC_OBSERVATION_STALL_TIMEOUT_SECONDS"), "ONEC_OBSERVATION_STALL_TIMEOUT_SECONDS"
    )


@dataclass(slots=True)
class ObservationRequest:
    capability: str
    target: str
    run_root: Path
    command: Sequence[str]
    stdout_log: Path | None = None
    stderr_log: Path | None = None
    cwd: Path | None = None
    env: Mapping[str, str] | None = None
    progress_file: Path | None = None
    stall_timeout_seconds: float | None = None
    timeout_seconds: float | None = None
    expected_result: Path | None = None
    techlog: TechlogPlan | None = None
    interval_seconds: float | None = None
    term_grace_seconds: float = 10.0
    on_started: Callable[[int], None] | None = None
    on_stop: Callable[[str], None] | None = None


@dataclass(slots=True)
class ObservationResult:
    exit_code: int
    event: str
    terminal_reason: str
    observation_path: Path
    signal: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class _Writer:
    def __init__(self, path: Path, capability: str, target: str, started: float) -> None:
        self.path = path
        self.capability = capability if SAFE_ID.fullmatch(capability) else "redacted"
        self.target = target if SAFE_TARGET.fullmatch(target) else "redacted"
        self.started = started
        self.seq = 0
        self.size = 0
        self.dropped = 0
        self.terminal_written = False
        self.lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        self.stream = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")

    def _line(self, event: str, source: str, extra: Mapping[str, Any]) -> str:
        payload: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "seq": self.seq + 1,
            "timestamp": _timestamp(),
            "elapsedSeconds": int(time.monotonic() - self.started),
            "capability": self.capability,
            "target": self.target,
            "event": event,
            "source": source,
        }
        payload.update({key: value for key, value in extra.items() if key not in payload})
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n"

    def emit(self, event: str, source: str, **extra: Any) -> None:
        with self.lock:
            terminal = event in {"completed", "failed"}
            if self.terminal_written:
                return
            if terminal:
                extra["droppedEvents"] = self.dropped
            line = self._line(event, source, extra)
            if len(line.encode("utf-8")) > MAX_LINE_BYTES:
                self.dropped += 1
                if not terminal:
                    return
                minimal = {key: extra[key] for key in ("exitCode", "terminalReason") if key in extra} | {
                    "droppedEvents": self.dropped
                }
                line = self._line(event, source, minimal)
            size = len(line.encode("utf-8"))
            if not terminal and self.size + size > MAX_BYTES - TERMINAL_RESERVE_BYTES:
                self.dropped += 1
                return
            self.stream.write(line)
            self.stream.flush()
            self.seq += 1
            self.size += size
            self.terminal_written = terminal

    def close(self) -> None:
        self.stream.close()


class _Progress:
    """Tracks the content of the application progress file; the stall clock starts at the first value."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.digest: str | None = None
        self.status: str | None = None
        self.changed_at: float | None = None
        self.changed_since_heartbeat = False
        self.probe_failed = False

    def poll(self, now: float) -> None:
        if self.path is None:
            return
        try:
            with self.path.open("rb") as stream:
                data = stream.read(MAX_LINE_BYTES)
        except FileNotFoundError:
            return
        except OSError:
            self.probe_failed = True
            return
        digest = hashlib.sha256(data).hexdigest()
        if digest != self.digest:
            self.digest = digest
            self.changed_at = now
            self.changed_since_heartbeat = True
            text = data.decode("utf-8", errors="replace").strip().splitlines()
            value = text[-1].strip() if text else ""
            # Free text may carry data of the infobase: only short tokens are reported.
            self.status = value if SAFE_PROGRESS.fullmatch(value) else None

    def heartbeat_extra(self, now: float) -> dict[str, Any]:
        if self.path is None:
            return {}
        if self.changed_at is None:
            return {"progress": "pending"}
        extra: dict[str, Any] = {"stageAgeSeconds": int(now - self.changed_at)}
        extra["status"] = self.status if self.status is not None else "unreported"
        return extra


def _output_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _relative(path: Path, run_root: Path) -> str:
    try:
        return path.resolve().relative_to(run_root.resolve()).as_posix()
    except (OSError, ValueError):
        return path.name


def _signal_group(process: subprocess.Popen[bytes], signum: int) -> None:
    if WINDOWS:
        return
    try:
        os.killpg(process.pid, signum)
    except (ProcessLookupError, PermissionError):
        pass


def terminate_process_tree(process: subprocess.Popen[bytes], grace_seconds: float) -> None:
    """Stop the whole process group of the observed command: TERM first, KILL after the grace period."""
    if process.poll() is not None and WINDOWS:
        return
    if WINDOWS:
        try:
            process.send_signal(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM))
        except (OSError, ValueError):
            pass
    else:
        _signal_group(process, signal.SIGTERM)
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        if WINDOWS:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            process.kill()
        else:
            _signal_group(process, signal.SIGKILL)
        process.wait()
    if not WINDOWS:
        # Descendants that ignored TERM still belong to the group after the leader exited.
        _signal_group(process, signal.SIGKILL)


def _read_terminal_extra(run_root: Path) -> tuple[dict[str, Any], bool]:
    path = run_root / TERMINAL_EXTRA_FILE
    if not path.exists() and not path.is_symlink():
        return {}, True
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 3072:
            return {}, False
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, False
    if not isinstance(value, dict) or RESERVED_KEYS & set(value):
        return {}, False
    return value, True


def run_observed(request: ObservationRequest) -> ObservationResult:
    """Run ``request.command`` under observation and return the terminal outcome."""
    if not request.command:
        raise CommandError("observed command must not be empty")
    run_root = request.run_root.resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    interval = request.interval_seconds if request.interval_seconds is not None else interval_from_env()
    stdout_log = request.stdout_log or run_root / "stdout.log"
    stderr_log = request.stderr_log or run_root / "stderr.log"
    observation_path = run_root / OBSERVATION_FILE
    started = time.monotonic()
    try:
        writer = _Writer(observation_path, request.capability, request.target, started)
    except OSError as error:
        raise CommandError(f"cannot create observation artifact: {observation_path}", 70) from error
    (run_root / TERMINAL_EXTRA_FILE).unlink(missing_ok=True)
    degraded_reason = ""
    writer.emit(
        "started",
        "launch",
        **({"progressFile": _relative(request.progress_file, run_root)} if request.progress_file else {}),
    )

    techlog = TechlogSession(request.techlog, run_root) if request.techlog is not None else None
    techlog_status: dict[str, Any] = {"status": "not-configured"}
    if techlog is not None:
        techlog_status = techlog.start()
        if techlog_status.get("status") == "not-available":
            degraded_reason = f"technological-log-{techlog_status.get('reason', 'unavailable')}"

    def emit_tech_events(events: list[dict[str, Any]]) -> None:
        nonlocal degraded_reason
        for item in events:
            if item.get("techlog") == "event":
                writer.emit(
                    "tech-event",
                    "technological-log",
                    techEvent=item.get("event"),
                    level=item.get("level"),
                    duration=item.get("duration"),
                    process=item.get("process"),
                    processName=item.get("processName"),
                )
            elif item.get("techlog") == "not-available" and not degraded_reason:
                degraded_reason = f"technological-log-{item.get('reason', 'unavailable')}"

    progress = _Progress(request.progress_file)
    outputs = {stdout_log: "stdout.log", stderr_log: "stderr.log"}
    sizes = {path: _output_size(path) for path in outputs}
    forwarded: list[str] = []
    stop_reason = ""
    exit_code = 0
    environment = os.environ.copy()
    if request.env:
        environment.update(request.env)
    process: subprocess.Popen[bytes] | None = None
    previous_handlers: dict[int, Any] = {}
    try:
        try:
            with stdout_log.open("ab") as stdout_stream, stderr_log.open("ab") as stderr_stream:
                process = subprocess.Popen(
                    [str(item) for item in request.command],
                    cwd=str(request.cwd) if request.cwd else None,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_stream,
                    stderr=stderr_stream,
                    start_new_session=not WINDOWS,
                    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if WINDOWS else 0,
                )
        except OSError as error:
            with stderr_log.open("a", encoding="utf-8") as stream:
                stream.write(f"cannot start observed command: {error.strerror or error}\n")
            exit_code = EXIT_LAUNCH_FAILED
            stop_reason = "launch-failed"
        if process is not None:
            if request.on_started is not None:
                request.on_started(process.pid)
            running = process

            def forward(signum: int, _frame: object) -> None:
                forwarded.append(signal.Signals(signum).name)
                if running.poll() is not None:
                    return
                if WINDOWS:
                    try:
                        running.send_signal(getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM))
                    except (OSError, ValueError):
                        running.terminate()
                else:
                    # Background jobs of non-interactive shells ignore SIGINT: the group always gets SIGTERM.
                    _signal_group(running, signal.SIGTERM)

            if threading.current_thread() is threading.main_thread():
                for signum in (signal.SIGINT, signal.SIGTERM):
                    previous_handlers[signum] = signal.getsignal(signum)
                    signal.signal(signum, forward)
            next_heartbeat = started + interval
            while process.poll() is None:
                now = time.monotonic()
                progress.poll(now)
                if (
                    request.stall_timeout_seconds is not None
                    and progress.changed_at is not None
                    and now - progress.changed_at >= request.stall_timeout_seconds
                ):
                    stop_reason = "stalled"
                elif (
                    request.timeout_seconds is not None
                    and progress.changed_at is None
                    and now - started >= request.timeout_seconds
                ):
                    # A general time limit applies only until the operation reports progress.
                    stop_reason = "timeout"
                if stop_reason:
                    if request.on_stop is not None:
                        try:
                            request.on_stop(stop_reason)
                        except Exception as error:  # the evidence hook must never block the stop
                            print(f"[observation] stop hook failed: {error}", file=sys.stderr)
                    terminate_process_tree(process, request.term_grace_seconds)
                    break
                if now >= next_heartbeat:
                    extra = progress.heartbeat_extra(now)
                    source = "quiet"
                    if progress.changed_since_heartbeat:
                        source = "progress"
                        progress.changed_since_heartbeat = False
                    grown = []
                    for path, name in outputs.items():
                        size = _output_size(path)
                        if size > sizes[path]:
                            grown.append({"path": name, "bytesDelta": size - sizes[path]})
                        sizes[path] = size
                    if source == "quiet" and grown:
                        source = "output"
                        extra["outputs"] = grown
                    if techlog is not None:
                        emit_tech_events(techlog.read_events())
                    if progress.probe_failed and not degraded_reason:
                        degraded_reason = "progress-probe"
                    if degraded_reason:
                        extra.update(degraded=True, degradedReason=degraded_reason)
                    writer.emit("heartbeat", source, **extra)
                    stage = ""
                    if "stageAgeSeconds" in extra:
                        stage = f" stage={extra['status']} stage_age={extra['stageAgeSeconds']}s"
                    print(
                        f"[observation] capability={writer.capability} target={writer.target} event=heartbeat "
                        f"elapsed={int(now - started)}s source={source}{stage} liveness=running",
                        file=sys.stderr,
                        flush=True,
                    )
                    next_heartbeat = now + interval
                time.sleep(0.1)
            return_code = process.wait()
            if stop_reason == "stalled":
                exit_code = EXIT_STALLED
            elif stop_reason == "timeout":
                exit_code = EXIT_TIMEOUT
            else:
                exit_code = 128 - return_code if return_code < 0 else return_code
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        if process is not None and process.poll() is None:
            terminate_process_tree(process, request.term_grace_seconds)
        techlog_final: dict[str, Any] = techlog_status
        if techlog is not None:
            events, techlog_final = techlog.finish()
            emit_tech_events(events)
        terminal: dict[str, Any] = {"exitCode": exit_code}
        reason = stop_reason or ("completed" if exit_code == 0 else "command-exit")
        if stop_reason == "stalled":
            terminal["stageAgeSeconds"] = int(time.monotonic() - (progress.changed_at or started))
            terminal["lastProgress"] = progress.status if progress.status is not None else "unreported"
        if exit_code == 0 and request.expected_result is not None and not request.expected_result.is_file():
            exit_code = EXIT_MISSING_RESULT
            reason = "missing-result"
            terminal.update(exitCode=exit_code, expectedResult=_relative(request.expected_result, run_root))
        extra_values, extra_valid = _read_terminal_extra(run_root)
        if not extra_valid:
            exit_code = exit_code or 70
            reason = "invalid-terminal-observation-extra"
            terminal["exitCode"] = exit_code
        terminal.update(extra_values)
        terminal.setdefault("terminalReason", reason)
        if forwarded:
            terminal["signal"] = forwarded[0]
        if techlog is not None:
            terminal["technologicalLog"] = {
                key: techlog_final[key] for key in ("status", "reason", "restored") if key in techlog_final
            }
            if techlog_final.get("restored") is False:
                degraded_reason = degraded_reason or "technological-log-restore"
        if degraded_reason:
            terminal.update(degraded=True, degradedReason=degraded_reason)
        event = "completed" if exit_code == 0 else "failed"
        writer.emit(event, "command" if process is not None else "launch", **terminal)
        writer.close()
    return ObservationResult(
        exit_code=exit_code,
        event=event,
        terminal_reason=str(terminal["terminalReason"]),
        observation_path=observation_path,
        signal=forwarded[0] if forwarded else None,
        extra=terminal,
    )


def build_observation_summary(run_root: Path) -> dict[str, Any] | None:
    """Terminal section of ``summary.json`` derived from ``observation.jsonl``."""
    path = run_root / OBSERVATION_FILE
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            events.append(value)
    if not events:
        return None
    terminal = next((item for item in reversed(events) if item.get("event") in {"completed", "failed"}), None)
    last = terminal or events[-1]
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "status": "degraded" if any(item.get("degraded") is True for item in events) else "ok",
        "path": str(path),
        "heartbeatCount": sum(item.get("event") == "heartbeat" for item in events),
        "diagnosticCount": sum(item.get("event") == "tech-event" for item in events),
        "droppedEvents": last.get("droppedEvents", 0),
        "startedAt": events[0].get("timestamp"),
        "finishedAt": last.get("timestamp"),
        "terminalEvent": terminal.get("event") if terminal else None,
        "terminalReason": terminal.get("terminalReason") if terminal else "running",
        "exitCode": terminal.get("exitCode") if terminal else None,
        "logs": {
            "observation": str(path),
            "stdout": str(run_root / "stdout.log"),
            "stderr": str(run_root / "stderr.log"),
        },
    }
    if terminal and "technologicalLog" in terminal:
        summary["technologicalLog"] = terminal["technologicalLog"] | {
            "cursor": str(run_root / "technological-log-cursor.json")
        }
    return summary


def attach_observation(payload: dict[str, Any], run_root: Path) -> dict[str, Any]:
    observation = build_observation_summary(run_root)
    if observation is not None:
        payload["observation"] = observation
        artifacts = payload.setdefault("artifacts", {})
        if isinstance(artifacts, dict):
            artifacts["observation_jsonl"] = observation["path"]
    return payload


def publish_observation_summary(run_root: Path, base: dict[str, Any] | None = None) -> Path:
    """Merge the terminal observation section into ``<run-root>/summary.json``."""
    summary_path = run_root / "summary.json"
    payload: dict[str, Any] = {}
    try:
        current = json.loads(summary_path.read_text(encoding="utf-8"))
        if isinstance(current, dict):
            payload = current
    except (OSError, ValueError):
        payload = {}
    if base:
        payload.update(base)
    attach_observation(payload, run_root)
    observation = payload.get("observation") or {}
    if "exit_code" not in payload and isinstance(observation, dict):
        payload["exit_code"] = observation.get("exitCode")
    if "status" not in payload and isinstance(observation, dict):
        payload["status"] = "success" if observation.get("terminalEvent") == "completed" else "failed"
    atomic_write_json(summary_path, payload)
    return summary_path


OBSERVE_USAGE = """Usage:
  observe-command --capability <id> --target <id> --run-root <dir>
                  [--progress-file <path>] [--stall-timeout <sec>] [--timeout <sec>]
                  [--expected-result <path>] [--stdout <path>] [--stderr <path>] -- <command> [args...]
  observe-command --stdin-json        (the same arguments as a JSON array on stdin)
"""


def observe_command_cli(argv: list[str]) -> int:
    """CLI bridge for shell wrappers: the command may come through stdin so its arguments stay off argv."""
    if argv == ["--stdin-json"]:
        try:
            loaded = json.load(sys.stdin)
        except (ValueError, UnicodeError):
            raise CommandError("observe-command received invalid JSON", 2) from None
        if not isinstance(loaded, list) or not all(isinstance(item, str) for item in loaded):
            raise CommandError("observe-command requires a JSON array of strings", 2)
        argv = list(loaded)
    if not argv or argv[0] in {"-h", "--help"}:
        print(OBSERVE_USAGE, end="")
        return 0
    if "--" not in argv:
        raise CommandError("observe-command requires -- before the command", 2)
    split = argv.index("--")
    options, command = argv[:split], argv[split + 1 :]
    parser = argparse.ArgumentParser(prog="observe-command", add_help=False, allow_abbrev=False)
    parser.add_argument("--capability", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--progress-file", default="")
    parser.add_argument("--stall-timeout", default="")
    parser.add_argument("--timeout", default="")
    parser.add_argument("--expected-result", default="")
    parser.add_argument("--stdout", default="")
    parser.add_argument("--stderr", default="")
    try:
        args = parser.parse_args(options)
    except SystemExit:
        raise CommandError("invalid observe-command arguments", 2) from None
    if not command:
        raise CommandError("observe-command requires a command", 2)
    run_root = Path(args.run_root).resolve()
    stall = positive_seconds(args.stall_timeout, "--stall-timeout")
    progress_file = Path(args.progress_file).resolve() if args.progress_file else None
    if stall is not None and progress_file is None:
        raise CommandError("--stall-timeout requires --progress-file", 2)
    from .runtime_techlog import plan_from_env

    run_root.mkdir(parents=True, exist_ok=True)
    identity_env, on_started = launch_identity(run_root, command)
    if progress_file is not None:
        identity_env["ONEC_OBSERVATION_PROGRESS_FILE"] = str(progress_file)
    result = run_observed(
        ObservationRequest(
            capability=args.capability,
            target=args.target,
            run_root=run_root,
            command=command,
            stdout_log=Path(args.stdout).resolve() if args.stdout else None,
            stderr_log=Path(args.stderr).resolve() if args.stderr else None,
            env=identity_env,
            progress_file=progress_file,
            stall_timeout_seconds=stall,
            timeout_seconds=positive_seconds(args.timeout, "--timeout"),
            expected_result=Path(args.expected_result).resolve() if args.expected_result else None,
            techlog=plan_from_env(run_root, process_id_file=run_root / "process.pid"),
            on_started=on_started,
        )
    )
    publish_observation_summary(run_root, {"capability": {"id": args.capability}, "run_root": str(run_root)})
    if result.signal == "SIGINT":
        raise KeyboardInterrupt
    return result.exit_code
