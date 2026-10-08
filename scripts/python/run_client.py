"""Interactive 1C client for the runtime-profile infobase: start, screenshot, key, click, status, stop.

Connection and password come only from the runtime profile (``infobase.auth.passwordEnv``);
they are never accepted as arguments and are printed as ``***``. On Linux the client runs in
an own Xpra session of ``direct-platform.sh`` that belongs to ``--run-root``; every session
command acts only on the display and the client process of that run-root. The launch is
observed by the shared adapter (``observation.jsonl`` and ``summary.json`` in the run-root).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .common import canonical_path, die, project_root, read_json, timestamp_utc, write_json
from .onec_xpra import adapter_command, observed_launch, redacted, secret_values
from .runtime import (
    append_auth_args,
    append_connection_args,
    direct_platform_xpra_enabled,
    load_direct_platform_xpra_start_child,
    load_direct_platform_xpra_xvfb_args,
    load_runtime_profile,
    platform_binary_path,
    require_runtime_profile,
    resolve_runtime_profile_path,
)
from .runtime_observation import (
    EXIT_MISSING_RESULT,
    EXIT_STALLED,
    EXIT_TIMEOUT,
    TERMINAL_EXTRA_FILE,
    build_observation_summary,
    positive_seconds,
)

STATE_FILE = "run-client.json"
PID_FILE = "process.pid"
SESSION_LOG = "session.log"
CLIENT_PROCESSES = {"1cv8", "1cv8c", "1cv8.exe", "1cv8c.exe"}
ACTIONS = {"start", "screenshot", "status", "stop", "key", "click"}
WINDOWS = os.name == "nt"

USAGE = """Usage:
  run-client [start] --profile <json> [--run-root <dir>]
             [--url <e1cib/...> | --c <parameter> | --execute <epf> [--c <parameter>]]
             [--wait [--timeout <sec>] [--result-file <path>] [--idle-timeout <sec> --progress-file <path>]]
             [--ready-timeout <sec>] [--dry-run]
  run-client screenshot --run-root <dir> [--out <png>]
  run-client key --run-root <dir> <keysym>...      (for example Escape, Return, ctrl+w)
  run-client click --run-root <dir> <x> <y>        (coordinates of the screenshot)
  run-client status --run-root <dir>
  run-client stop --run-root <dir> [--timeout <sec>]

start       open the profile infobase; returns after the client is ready, --wait waits for it to close
--timeout   with --wait: close the client of this run-root and return 124 if no progress was reported in time
--result-file  with --wait: success only if the file exists after the client closed (otherwise 70, no-result)
--idle-timeout --progress-file  with --wait: after the first write, if the progress file content does not change
            for N seconds, save screenshots/idle-timeout.png, close the client and return 125 (idle-timeout)
screenshot/key/click  Linux only: act on the Xpra display of this run-root
"""


def _parser(action: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"run-client {action}", allow_abbrev=False, add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("--run-root", default="")
    if action == "start":
        parser.add_argument("--profile", default="")
        parser.add_argument("--url", default="")
        parser.add_argument("--c", dest="c_param", default="")
        parser.add_argument("--execute", default="")
        parser.add_argument("--wait", action="store_true")
        parser.add_argument("--timeout", default="")
        parser.add_argument("--result-file", default="")
        parser.add_argument("--idle-timeout", default="")
        parser.add_argument("--progress-file", default="")
        parser.add_argument("--ready-timeout", default="90")
        parser.add_argument("--dry-run", action="store_true")
    elif action == "screenshot":
        parser.add_argument("--out", default="")
    elif action == "stop":
        parser.add_argument("--timeout", default="30")
    elif action == "key":
        parser.add_argument("keys", nargs="+")
    elif action == "click":
        parser.add_argument("x", type=int)
        parser.add_argument("y", type=int)
    return parser


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def _default_run_root() -> Path:
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    return project_root() / ".artifacts" / "run-client" / f"run-client-{stamp}-{os.getpid()}"


def _client_arguments(profile: Any, args: argparse.Namespace) -> list[str]:
    arguments = ["ENTERPRISE"]
    append_connection_args(profile, arguments)
    append_auth_args(profile, arguments, dry_run=args.dry_run)
    arguments += ["/DisableStartupMessages", "/DisableStartupDialogs"]
    if args.url:
        arguments += ["/URL", args.url]
    if args.execute:
        execute = canonical_path(args.execute)
        if not args.dry_run and not execute.is_file():
            die(f"external data processor not found: {execute}")
        arguments += ["/Execute", str(execute)]
    if args.c_param:
        arguments += ["/C", args.c_param]
    return arguments


def _validate_start(args: argparse.Namespace) -> dict[str, float | None]:
    if args.url and (args.c_param or args.execute):
        die("--url cannot be combined with --c or --execute")
    limits = {
        "timeout": positive_seconds(args.timeout, "--timeout"),
        "idle": positive_seconds(args.idle_timeout, "--idle-timeout"),
        "ready": positive_seconds(args.ready_timeout, "--ready-timeout"),
    }
    if (limits["timeout"] or args.result_file or limits["idle"] or args.progress_file) and not args.wait:
        die("--timeout, --result-file, --idle-timeout and --progress-file require --wait")
    if bool(limits["idle"]) != bool(args.progress_file):
        die("--idle-timeout and --progress-file must be used together")
    if args.progress_file and not args.dry_run and canonical_path(args.progress_file).exists():
        die(f"progress file already exists: {canonical_path(args.progress_file)}")
    if args.result_file and not args.dry_run and canonical_path(args.result_file).exists():
        die(f"result file already exists: {canonical_path(args.result_file)}")
    return limits


def _read_state(run_root_input: str) -> tuple[Path, dict[str, Any]]:
    if not run_root_input:
        die("--run-root is required")
    run_root = canonical_path(run_root_input)
    state_path = run_root / STATE_FILE
    if not state_path.is_file():
        die(f"run-client session not found: {state_path}")
    state = read_json(state_path)
    if not isinstance(state, dict):
        die(f"invalid run-client state: {state_path}")
    return run_root, state


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if WINDOWS:
        return _windows_image(pid) != ""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _windows_image(pid: int) -> str:
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    )
    line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    return line.split('","', 1)[0].strip('"').lower() if line.startswith('"') else ""


def _owns_process(pid: int, run_root: Path) -> bool:
    """The PID belongs to this run-root only while it is a platform client started for this run-root."""
    if pid <= 0 or not _alive(pid):
        return False
    if WINDOWS:
        return _windows_image(pid) in CLIENT_PROCESSES
    proc = Path(f"/proc/{pid}")
    try:
        name = (proc / "comm").read_text(encoding="utf-8").strip()
        environ = (proc / "environ").read_bytes().split(b"\0")
    except OSError:
        return False
    marker = f"ONEC_CAPABILITY_RUN_ROOT={run_root}".encode()
    return name in CLIENT_PROCESSES and marker in environ


def _client(run_root: Path) -> tuple[int, bool]:
    try:
        pid = int((run_root / PID_FILE).read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return 0, False
    return pid, _owns_process(pid, run_root)


def _display(run_root: Path) -> str:
    try:
        return (run_root / "xpra" / "active-display.env").read_text(encoding="utf-8").splitlines()[0].strip()
    except (OSError, IndexError):
        return ""


def _display_env(run_root: Path, display: str) -> dict[str, str]:
    return dict(os.environ, DISPLAY=display, XAUTHORITY=str(run_root / "home" / ".Xauthority"))


def _capture(run_root: Path, out: Path) -> bool:
    display = _display(run_root)
    if WINDOWS or not display or not _client(run_root)[1]:
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    old_umask = os.umask(0o077)
    try:
        result = subprocess.run(
            ["import", "-window", "root", str(out)],
            env=_display_env(run_root, display),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        os.umask(old_umask)
    return result.returncode == 0 and out.is_file()


def _launch(profile: Any, arguments: list[str], run_root: Path) -> tuple[list[str], dict[str, str]]:
    command, env = adapter_command(
        platform_binary_path(profile),
        arguments,
        run_root,
        xvfb_args=" ".join(load_direct_platform_xpra_xvfb_args(profile)),
        start_child=load_direct_platform_xpra_start_child(profile),
        # Interactive check: a modal dialog is something to look at, not a reason to kill the client.
        modal_policy="observe",
    )
    return command, env


def _terminal_status(code: int) -> str:
    return {
        0: "finished",
        EXIT_TIMEOUT: "timeout",
        EXIT_STALLED: "idle-timeout",
        EXIT_MISSING_RESULT: "no-result",
    }.get(code, "failed")


def _start(args: argparse.Namespace) -> int:
    limits = _validate_start(args)
    profile = require_runtime_profile(load_runtime_profile(resolve_runtime_profile_path(args.profile)))
    if profile.runner_adapter != "direct-platform":
        die(f"run-client supports only runnerAdapter=direct-platform, got {profile.runner_adapter}")
    if not WINDOWS and not direct_platform_xpra_enabled(profile):
        die("run-client on Linux requires platform.xpra.enabled=true in the runtime profile")
    run_root = canonical_path(args.run_root) if args.run_root else _default_run_root()
    if (run_root / STATE_FILE).exists():
        die(f"run-root already holds a run-client session: {run_root}")
    arguments = _client_arguments(profile, args)
    target = profile.name or "run-client"
    if args.dry_run:
        _print({"status": "dry-run", "run_root": str(run_root), "target": target, "command": redacted(arguments)})
        return 0
    secrets = secret_values(arguments)
    command, env = _launch(profile, arguments, run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    state: dict[str, Any] = {
        "schemaVersion": 1,
        "profile": str(profile.path),
        "target": target,
        "started_at": timestamp_utc(),
        "platform": "windows" if WINDOWS else "linux",
        "mode": "wait" if args.wait else "background",
    }
    write_json(run_root / STATE_FILE, state)
    summary = {"capability": {"id": "run-client", "label": "Run 1C client"}, "profile_path": str(profile.path)}
    if args.wait:
        progress = canonical_path(args.progress_file) if args.progress_file else None
        result_file = canonical_path(args.result_file) if args.result_file else None
        screenshots: dict[str, str] = {}

        def before_stop(reason: str) -> None:
            name = "idle-timeout" if reason == "stalled" else reason
            out = run_root / "screenshots" / f"{name}.png"
            if _capture(run_root, out):
                screenshots[name] = str(out)

        result = observed_launch(
            command,
            env,
            run_root,
            capability="run-client",
            target=target,
            secrets=secrets,
            summary=summary,
            progress_file=progress,
            stall_timeout_seconds=limits["idle"],
            timeout_seconds=limits["timeout"],
            expected_result=result_file,
            on_stop=before_stop,
        )
        payload: dict[str, Any] = {
            "status": _terminal_status(result.exit_code),
            "run_root": str(run_root),
            "exit_code": result.exit_code,
            "summary_json": str(run_root / "summary.json"),
        }
        if screenshots:
            payload["screenshot"] = next(iter(screenshots.values()))
        if result.exit_code == EXIT_STALLED:
            payload["hint"] = "client made no progress: check the screenshot for a modal window"
        if result_file is not None:
            payload["result_file"] = str(result_file)
        _print(payload)
        return result.exit_code
    request = {
        "command": command,
        "env": env,
        "run_root": str(run_root),
        "capability": "run-client",
        "target": target,
        "secrets": secrets,
        "summary": summary,
    }
    options: dict[str, Any] = {}
    if WINDOWS:
        options["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )
    else:
        options["start_new_session"] = True
    with (run_root / SESSION_LOG).open("ab") as log:
        # The request travels on stdin: the password is never part of the supervisor's command line.
        supervisor = subprocess.Popen(
            [sys.executable, "-m", "scripts.python.onec_xpra"],
            cwd=str(project_root()),
            stdin=subprocess.PIPE,
            stdout=log,
            stderr=subprocess.STDOUT,
            **options,
        )
        if supervisor.stdin is None:
            die("cannot pass the launch request to the run-client supervisor")
        supervisor.stdin.write(json.dumps(request).encode("utf-8"))
        supervisor.stdin.close()
    state["supervisor_pid"] = supervisor.pid
    write_json(run_root / STATE_FILE, state)
    deadline = time.monotonic() + (limits["ready"] or 90.0)
    while time.monotonic() < deadline:
        pid, alive = _client(run_root)
        display = "" if WINDOWS else _display(run_root)
        if alive and (WINDOWS or display):
            _print(
                {
                    "status": "started",
                    "run_root": str(run_root),
                    "display": display or None,
                    "client_pid": pid,
                    "session_log": str(run_root / SESSION_LOG),
                }
            )
            return 0
        if supervisor.poll() is not None:
            _print(
                {
                    "status": "failed",
                    "run_root": str(run_root),
                    "exit_code": supervisor.returncode,
                    "summary_json": str(run_root / "summary.json"),
                    "session_log": str(run_root / SESSION_LOG),
                }
            )
            return supervisor.returncode or 1
        time.sleep(0.2)
    _print({"status": "not-ready", "run_root": str(run_root), "session_log": str(run_root / SESSION_LOG)})
    return 1


def _session_display(action: str, run_root_input: str) -> tuple[Path, str]:
    if WINDOWS:
        die(f"run-client {action} is supported only on Linux (Xpra session)")
    run_root = _read_state(run_root_input)[0]
    pid, alive = _client(run_root)
    display = _display(run_root)
    if not alive or not display:
        die(f"client of this run-root is not running (pid={pid or 'unknown'})")
    return run_root, display


def _input(args: argparse.Namespace, action: str) -> int:
    run_root, display = _session_display(action, args.run_root)
    if action == "key":
        command = ["xdotool", "key", "--clearmodifiers", "--delay", "20", *args.keys]
    else:
        command = ["xdotool", "mousemove", str(args.x), str(args.y), "click", "1"]
    result = subprocess.run(
        command,
        env=_display_env(run_root, display),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        die(f"{action} failed: {result.stderr.strip()[:300]}")
    _print({"status": "sent", "action": action, "run_root": str(run_root), "display": display})
    return 0


def _screenshot(args: argparse.Namespace) -> int:
    run_root, display = _session_display("screenshot", args.run_root)
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    out = canonical_path(args.out) if args.out else run_root / "screenshots" / f"screen-{stamp}.png"
    if not _capture(run_root, out):
        die("screenshot failed")
    _print({"status": "captured", "run_root": str(run_root), "display": display, "screenshot": str(out)})
    return 0


def _status(args: argparse.Namespace) -> int:
    run_root, state = _read_state(args.run_root)
    pid, alive = _client(run_root)
    observation = build_observation_summary(run_root) or {}
    _print(
        {
            "run_root": str(run_root),
            "target": state.get("target"),
            "client_pid": pid or None,
            "client_alive": alive,
            "display": _display(run_root) or None,
            "supervisor_alive": _alive(int(state.get("supervisor_pid") or 0)),
            "terminal_event": observation.get("terminalEvent"),
            "terminal_reason": observation.get("terminalReason"),
            "summary_json": str(run_root / "summary.json"),
        }
    )
    return 0


def _signal_client(pid: int, force: bool) -> None:
    if WINDOWS:
        command = ["taskkill", "/PID", str(pid), "/T"] + (["/F"] if force else [])
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return
    try:
        os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
    except ProcessLookupError:
        pass


def _stop(args: argparse.Namespace) -> int:
    run_root, state = _read_state(args.run_root)
    timeout = positive_seconds(args.timeout, "--timeout") or 30.0
    pid, alive = _client(run_root)
    supervisor_pid = int(state.get("supervisor_pid") or 0)
    if alive:
        # The observer records the operator stop as the terminal reason instead of a bare exit code.
        (run_root / TERMINAL_EXTRA_FILE).write_text('{"terminalReason":"operator-stop"}\n', encoding="utf-8")
        _signal_client(pid, force=False)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and (_client(run_root)[1] or _alive(supervisor_pid)):
        time.sleep(0.3)
    if _client(run_root)[1]:
        _signal_client(pid, force=True)
        time.sleep(1)
    stopped = not _client(run_root)[1]
    _print(
        {
            "status": "stopped" if stopped else "still-running",
            "run_root": str(run_root),
            "client_pid": pid or None,
            "supervisor_alive": _alive(supervisor_pid),
            "summary_json": str(run_root / "summary.json"),
        }
    )
    return 0 if stopped else 1


def run_client(argv: list[str]) -> int:
    argv = list(argv)
    action = "start"
    if argv and argv[0] in ACTIONS:
        action = argv.pop(0)
    elif argv and argv[0] in {"-h", "--help"}:
        print(USAGE, end="")
        return 0
    try:
        args = _parser(action).parse_args(argv)
    except SystemExit:
        die(f"invalid arguments for run-client {action}; see --help", 2)
    if args.help:
        print(USAGE, end="")
        return 0
    if action in {"key", "click"}:
        return _input(args, action)
    handlers = {"start": _start, "screenshot": _screenshot, "status": _status, "stop": _stop}
    return handlers[action](args)
