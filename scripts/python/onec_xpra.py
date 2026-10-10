"""Graphical 1C launches through the repository adapter and the shared observation adapter.

On Linux the platform process runs inside an own Xpra session of
``scripts/adapters/direct-platform.sh`` that belongs to one run-root. On Windows
the platform binary is started directly. Either way the launch is observed by
``runtime_observation`` and the password never appears in output or artifacts.

``python -m scripts.python.onec_xpra reap-x-displays`` removes the X display entries of a killed
Xvfb so the adapter's display range does not run out; see ``reap_dead_x_displays``.
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import socket
import stat
import sys
import time
from pathlib import Path
from typing import Any

from .runtime_observation import (
    ObservationRequest,
    ObservationResult,
    launch_identity,
    publish_observation_summary,
    run_observed,
)
from .runtime_techlog import plan_from_env

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "scripts" / "adapters" / "direct-platform.sh"
DEFAULT_XVFB_ARGS = "Xvfb -screen 0 1440x900x24 -nolisten tcp -noreset -auth $XAUTHORITY"
MASK = "***"
SECRET_FLAGS = {"/P", "--password", "--db-pwd"}


def resolve_v8path(value: str = "") -> str:
    """Path to the platform executable: explicit value first, then the newest standard installation."""
    if value:
        path = Path(value)
        if path.is_dir():
            names = ("1cv8.exe",) if os.name == "nt" else ("1cv8", "1cv8c")
            path = next((path / name for name in names if (path / name).is_file()), path)
        if path.is_file():
            return str(path)
        raise FileNotFoundError(f"1C executable not found at {path}")
    candidates = glob.glob(r"C:\Program Files\1cv8\*\bin\1cv8.exe") + glob.glob("/opt/1cv8/x86_64/*/1cv8")
    found = shutil.which("1cv8")
    if found:
        candidates.append(found)
    if not candidates:
        raise FileNotFoundError("1C executable not found; set platform.binaryPath in the runtime profile")
    return sorted(candidates)[-1]


def adapter_command(
    v8path: str,
    arguments: list[str],
    run_root: Path,
    *,
    xvfb_args: str = "",
    start_child: str = "",
    modal_policy: str = "",
) -> tuple[list[str], dict[str, str]]:
    """Command and extra environment that start the platform inside the run-root's own Xpra session."""
    env = {"ONEC_CAPABILITY_RUN_ROOT": str(run_root)}
    if os.name == "nt":
        return [v8path, *arguments], env
    if not ADAPTER.is_file():
        raise FileNotFoundError(f"Xpra adapter not found: {ADAPTER}")
    env["ONEC_DIRECT_PLATFORM_XPRA_ENABLED"] = "1"
    env["ONEC_DIRECT_PLATFORM_XPRA_XVFB_ARGS"] = xvfb_args or os.environ.get(
        "ONEC_DIRECT_PLATFORM_XPRA_XVFB_ARGS", DEFAULT_XVFB_ARGS
    )
    env["ONEC_DIRECT_PLATFORM_XPRA_START_CHILD"] = start_child or os.environ.get(
        "ONEC_DIRECT_PLATFORM_XPRA_START_CHILD", "openbox"
    )
    if modal_policy:
        env["ONEC_DIRECT_PLATFORM_XPRA_MODAL_POLICY"] = modal_policy
    return [str(ADAPTER), v8path, *arguments], env


def redacted(arguments: list[str]) -> list[str]:
    """Arguments safe to print: password values are replaced with ``***``."""
    result: list[str] = []
    hide_next = False
    for argument in arguments:
        if hide_next:
            result.append(MASK)
            hide_next = False
        elif argument in SECRET_FLAGS:
            result.append(argument)
            hide_next = True
        elif argument.startswith("/P") and len(argument) > 2:
            result.append("/P" + MASK)
        elif argument.startswith(("--password=", "--db-pwd=")):
            result.append(argument.split("=", 1)[0] + "=" + MASK)
        else:
            result.append(argument)
    return result


def secret_values(arguments: list[str]) -> list[str]:
    """Password values present in platform arguments; used to mask logs and summaries."""
    values: list[str] = []
    for index, argument in enumerate(arguments):
        if argument in SECRET_FLAGS and index + 1 < len(arguments):
            values.append(arguments[index + 1])
        elif argument.startswith("/P") and len(argument) > 2:
            values.append(argument[2:])
        elif argument.startswith(("--password=", "--db-pwd=")):
            values.append(argument.split("=", 1)[1])
    return [value for value in values if value]


def mask_text(text: str, secrets: list[str]) -> str:
    for secret in sorted(set(secrets), key=len, reverse=True):
        if secret:
            text = text.replace(secret, MASK)
    return text


def mask_files(paths: list[Path], secrets: list[str]) -> None:
    if not secrets:
        return
    for path in paths:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        masked = mask_text(content, secrets)
        if masked != content:
            path.write_text(masked, encoding="utf-8", newline="\n")


def observed_launch(
    command: list[str],
    env: dict[str, str],
    run_root: Path,
    *,
    capability: str,
    target: str,
    secrets: list[str],
    summary: dict[str, Any] | None = None,
    **request_options: Any,
) -> ObservationResult:
    """Run one platform command under observation and publish a masked ``summary.json``."""
    run_root.mkdir(parents=True, exist_ok=True)
    identity_env, on_started = launch_identity(run_root, command)
    merged_env = {**env, **identity_env}
    result = run_observed(
        ObservationRequest(
            capability=capability,
            target=target,
            run_root=run_root,
            command=command,
            env=merged_env,
            techlog=plan_from_env(run_root, process_id_file=run_root / "process.pid"),
            on_started=on_started,
            **request_options,
        )
    )
    mask_files([run_root / "stdout.log", run_root / "stderr.log"], secrets)
    payload = dict(summary or {})
    payload.update(
        status="success" if result.exit_code == 0 else "failed",
        exit_code=result.exit_code,
        run_root=str(run_root),
        command=redacted(command),
        artifacts={"stdout_log": str(run_root / "stdout.log"), "stderr_log": str(run_root / "stderr.log")},
    )
    summary_path = publish_observation_summary(run_root, payload)
    mask_files([summary_path], secrets)
    return result


def launch_from_stdin() -> int:
    """``python -m scripts.python.onec_xpra`` entry: JSON request on stdin keeps the password off argv."""
    request = json.load(sys.stdin)
    if not isinstance(request, dict):
        raise SystemExit("launch request must be a JSON object")
    command = [str(item) for item in request["command"]]
    result = observed_launch(
        command,
        {str(key): str(value) for key, value in dict(request.get("env", {})).items()},
        Path(str(request["run_root"])),
        capability=str(request.get("capability", "platform-launch")),
        target=str(request.get("target", "platform")),
        secrets=[str(item) for item in request.get("secrets", [])] or secret_values(command),
        summary=dict(request.get("summary", {})),
    )
    return result.exit_code


def _x_socket_state(address: str) -> bool | None:
    """True: the socket has a listener; False: provably no listener; None: state not proven."""
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    probe.settimeout(1.0)
    try:
        probe.connect(address)
    except (ConnectionRefusedError, FileNotFoundError):
        return False
    except OSError:
        return None
    else:
        return True
    finally:
        probe.close()


def _owned_entry(path: Path, kind: int) -> os.stat_result | None:
    """lstat of a file of the given type owned by the current user; None for anything else."""
    try:
        info = path.lstat()
    except OSError:
        return None
    if stat.S_IFMT(info.st_mode) != kind or info.st_uid != os.getuid():
        return None
    return info


def _lock_pid(path: Path) -> int | None:
    try:
        text = path.read_text(encoding="ascii")
    except (OSError, UnicodeDecodeError):
        return None
    value = text.strip()
    return int(value) if value.isdigit() and int(value) > 1 else None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        # A PID from another PID namespace may match a live host process.
        return Path(f"/proc/{pid}").exists()
    except OSError:
        return True
    return True


def reap_dead_x_displays(
    x_root: Path, minimum: int, maximum: int, owner_dir: Path, min_age: float, now: float | None = None
) -> list[int]:
    """Remove only provably dead ``.X<N>-lock`` / ``.X11-unix/X<N>`` pairs of the current user.

    An Xvfb killed with SIGKILL leaves both entries behind, and the adapter then treats the display
    as busy forever. A display is reaped only when all of these hold: the lock is a regular file of
    the current user, no ``<owner_dir>/session-<N>.owner`` reserves it, both entries are older than
    ``min_age`` seconds, the PID in the lock is dead, and neither the path socket nor the abstract
    socket of that display has a listener. Displays 0 and 1 are never touched. Returns the reaped
    display numbers.
    """
    reaped: list[int] = []
    current = time.time() if now is None else now
    for number in range(max(minimum, 2), maximum + 1):
        lock = x_root / f".X{number}-lock"
        sock = x_root / ".X11-unix" / f"X{number}"
        lock_info = _owned_entry(lock, stat.S_IFREG)
        if lock_info is None:
            continue  # no lock, a symlink or a file of another user
        if (owner_dir / f"session-{number}.owner").exists():
            continue  # reserved by a running launch
        sock_info = _owned_entry(sock, stat.S_IFSOCK)
        if sock_info is None and os.path.lexists(sock):
            continue  # the socket belongs to another user or is not a socket
        newest = max(lock_info.st_mtime, sock_info.st_mtime if sock_info else 0.0)
        if current - newest < min_age:
            continue  # the X server may have just started
        pid = _lock_pid(lock)
        if pid is None or _pid_alive(pid):
            continue
        if sock_info is not None and _x_socket_state(str(sock)) is not False:
            continue
        if _x_socket_state("\0" + str(sock)) is not False:
            continue  # abstract socket of the same display
        # Make sure a new X server did not replace the entries before removing them.
        again = _owned_entry(lock, stat.S_IFREG)
        if again is None or (again.st_ino, again.st_mtime) != (lock_info.st_ino, lock_info.st_mtime):
            continue
        if _lock_pid(lock) != pid:
            continue
        if sock_info is not None:
            sock_again = _owned_entry(sock, stat.S_IFSOCK)
            if sock_again is None or sock_again.st_ino != sock_info.st_ino:
                continue
            sock.unlink()
        lock.unlink()
        reaped.append(number)
    return reaped


def reap_x_displays_cli(arguments: list[str]) -> int:
    """``reap-x-displays <x-root> <min> <max> <owner-dir> <min-age-seconds>``: print reaped numbers."""
    if len(arguments) != 5:
        print("usage: reap-x-displays <x-root> <min> <max> <owner-dir> <min-age-seconds>", file=sys.stderr)
        return 2
    x_root, minimum, maximum, owner_dir, min_age = arguments
    for number in reap_dead_x_displays(Path(x_root), int(minimum), int(maximum), Path(owner_dir), float(min_age)):
        print(number)
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["reap-x-displays"]:
        raise SystemExit(reap_x_displays_cli(sys.argv[2:]))
    raise SystemExit(launch_from_stdin())
