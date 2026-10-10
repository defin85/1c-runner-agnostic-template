"""Operator-host tools of the optional `customer-site-operations` module.

The customer VDI client runs inside a background Xpra desktop on the operator host. These tools
start that desktop, open a VDI connection file, take screenshots, type one checked command without
Enter, compare the typed line with the command, send Enter only after that check, generate chunked
file transfers with SHA-256 verification, keep the remote session awake with mouse moves only and
prepare root payloads for a manual RDP shell.

Settings come from the project-owned `infra/site/operator.json` (`operator.example.json` lists the
fields). The tools never print the content of a connection file and never use the host clipboard
for background work.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PROFILE = Path("infra/site/operator.json")
MAX_COMMAND = 4096
MAX_PAYLOAD = 3975
CHUNK = 240
SHELL_CLOSING = re.compile(r"(^|[\s;|&()])(exit|logout|exec)([\s;|&()]|$)")
STRICT_MODE = ("set -e", "set -u", "set -o pipefail")


class OperatorError(RuntimeError):
    """A refused or failed operator step; the message never holds secrets."""


@dataclass(frozen=True)
class Profile:
    display: str
    vdi_client: Path
    client_timezone: str
    screen: str
    view_display: str
    view_scaling: float
    typing_delay_ms: int
    window_class: str
    keepalive_points: tuple[tuple[int, int], tuple[int, int]]
    keepalive_interval: int
    runtime_dir: Path


def caller_path(value: str | Path) -> Path:
    """Resolve a path given by the operator against the directory the wrapper was started from."""
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(os.environ.get("SITE_OPERATOR_CWD") or os.getcwd()) / path


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise OperatorError(message)


def load_profile(path: Path) -> Profile:
    _require(
        path.is_file(),
        f"Operator profile {path} is missing; copy infra/site/operator.example.json to operator.json and fill it",
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(data, dict) and data.get("schema") == 1, "Operator profile must be a schema 1 object")
    display = str(data.get("display", ""))
    _require(re.fullmatch(r":[1-9][0-9]{0,3}", display) is not None, "display must look like :100")
    screen = str(data.get("screen", "1920x1080"))
    _require(re.fullmatch(r"[1-9][0-9]{2,4}x[1-9][0-9]{2,4}", screen) is not None, "screen must look like 1920x1080")
    keepalive = data.get("keepalive") or {}
    _require(isinstance(keepalive, dict), "keepalive must be an object")
    points = keepalive.get("points", [[950, 700], [952, 700]])
    _require(
        isinstance(points, list)
        and len(points) == 2
        and all(isinstance(p, list) and len(p) == 2 and all(type(v) is int and v >= 0 for v in p) for p in points),
        "keepalive.points must be two [x, y] pairs",
    )
    interval = keepalive.get("interval_seconds", 60)
    _require(type(interval) is int and 10 <= interval <= 600, "keepalive.interval_seconds must be 10..600")
    delay = data.get("typing_delay_ms", 20)
    _require(type(delay) is int and 10 <= delay <= 200, "typing_delay_ms must be 10..200")
    scaling = data.get("view_scaling", 0.85)
    _require(isinstance(scaling, (int, float)) and 0.25 <= scaling <= 2, "view_scaling must be 0.25..2")
    vdi_client = Path(str(data.get("vdi_client", "")))
    _require(vdi_client.is_absolute(), "vdi_client must be an absolute path")
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}") / "site-operator"
    return Profile(
        display=display,
        vdi_client=vdi_client,
        client_timezone=str(data.get("client_timezone", "UTC")),
        screen=screen,
        view_display=str(data.get("view_display", ":0")),
        view_scaling=float(scaling),
        typing_delay_ms=delay,
        window_class=str(keepalive.get("window_class", "")),
        keepalive_points=((points[0][0], points[0][1]), (points[1][0], points[1][1])),
        keepalive_interval=interval,
        runtime_dir=runtime,
    )


def private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    _require(path.stat().st_uid == os.getuid(), f"{path} must belong to the operator")
    return path


def run(argv: list[str], *, env: dict[str, str] | None = None, text_input: str | None = None) -> str:
    try:
        result = subprocess.run(
            argv,
            input=text_input,
            capture_output=True,
            text=True,
            env=env,
            timeout=180,
            check=False,
        )
    except FileNotFoundError:
        raise OperatorError(f"{argv[0]} is not installed") from None
    _require(result.returncode == 0, f"{Path(argv[0]).name} failed (rc={result.returncode})")
    return result.stdout


def display_env(display: str) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("WAYLAND_DISPLAY", None)
    env["DISPLAY"] = display
    return env


def client_env(profile: Profile) -> dict[str, str]:
    """Environment of the VDI client: no proxy variables (any case), no Wayland, the Xpra display."""
    env = {key: value for key, value in os.environ.items() if not key.lower().endswith("_proxy")}
    env.pop("WAYLAND_DISPLAY", None)
    env["DISPLAY"] = profile.display
    # The VDI passes the client time zone to the remote session; use the site time zone.
    env["TZ"] = profile.client_timezone
    return env


def xpra_start_argv(profile: Profile) -> list[str]:
    xvfb = f"Xvfb -screen 0 {profile.screen}x24 -nolisten tcp -noreset -auth $XAUTHORITY"
    return [
        "xpra",
        "start-desktop",
        profile.display,
        "--daemon=yes",
        "--attach=no",
        "--mdns=no",
        "--systemd-run=no",
        "--start=openbox",
        "--exit-with-children=no",
        "--html=off",
        "--clipboard=no",
        "--notifications=no",
        "--pulseaudio=no",
        "--webcam=no",
        "--printing=no",
        "--file-transfer=no",
        "--dbus=no",
        f"--xvfb={xvfb}",
    ]


def xpra_start(profile: Profile) -> str:
    socket = Path("/tmp/.X11-unix") / ("X" + profile.display[1:])
    _require(not socket.exists(), f"Display {profile.display} is busy; inspect it with xpra list, never restart it")
    run(xpra_start_argv(profile))
    return f"xpra_started display={profile.display} clipboard=no file_transfer=no"


def vdi_connect(profile: Profile, connection_file: Path) -> str:
    _require(connection_file.is_file(), "Connection file is missing; ask for a fresh one")
    _require(profile.vdi_client.is_file() and os.access(profile.vdi_client, os.X_OK), "vdi_client is not executable")
    folder = private_dir(profile.runtime_dir)
    target = folder / "launch.ica"
    data = connection_file.read_bytes()
    _require(0 < len(data) <= 1024 * 1024, "Connection file is empty or too large")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
    log = folder / "client.log"
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "ab") as stream:
        process = subprocess.Popen(
            [str(profile.vdi_client), str(target)],
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=stream,
            env=client_env(profile),
            cwd=folder,
            start_new_session=True,
        )
    return f"vdi_client_started pid={process.pid} display={profile.display} log={log}"


def screenshot(profile: Profile, crop: str | None, output: Path | None) -> str:
    folder = private_dir(profile.runtime_dir)
    target = output or folder / ("screen.png" if crop is None else "screen-crop.png")
    argv = ["import", "-window", "root"]
    if crop is not None:
        _require(re.fullmatch(r"[0-9]+x[0-9]+\+[0-9]+\+[0-9]+", crop) is not None, "--crop must look like WxH+X+Y")
        argv += ["-crop", crop, "+repage"]
    run(argv + [str(target)], env=display_env(profile.display))
    os.chmod(target, 0o600)
    return f"screenshot={target}"


VIEW_CONFIG = """# Viewer profile of the site Xpra desktop; inherited by Session Browser child clients.
env = GDK_BACKEND=x11
desktop-scaling = {scaling}
resize-display = no
opengl = yes
clipboard = no
file-transfer = no
printing = no
webcam = no
speaker = off
microphone = off
"""


def view_command(profile: Profile, browse: bool) -> tuple[list[str], dict[str, str]]:
    folder = private_dir(profile.runtime_dir / "xpra-view")
    (folder / "xpra.conf").write_text(VIEW_CONFIG.format(scaling=profile.view_scaling), encoding="utf-8")
    env = display_env(profile.view_display)
    env.update(GDK_BACKEND="x11", GDK_SCALE="1", GDK_DPI_SCALE="1", XPRA_USER_CONF_DIRS=str(folder))
    argv = ["xpra", "sessions"] if browse else ["xpra", "attach", profile.display]
    return argv, env


def check_command(command: str) -> None:
    _require(bool(command) and len(command) <= MAX_COMMAND, f"Expected one command of 1..{MAX_COMMAND} characters")
    _require(command.isascii(), "Only ASCII commands can be typed; the remote layout changes other characters")
    _require(not any(ord(c) < 32 or ord(c) == 127 for c in command), "Control characters and line breaks are refused")
    _require(SHELL_CLOSING.search(command) is None, "exit, logout and exec could close the remote shell")
    result = subprocess.run(["bash", "-n", "-c", command], capture_output=True, timeout=5, check=False)
    _require(result.returncode == 0, "bash -n rejected the command")


def pending_path(profile: Profile) -> Path:
    return private_dir(profile.runtime_dir) / "pending-command.json"


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def type_command(profile: Profile, command: str) -> str:
    check_command(command)
    path = pending_path(profile)
    _require(not path.exists(), "A typed command is still pending; verify and enter it or clear the line first")
    env = display_env(profile.display)
    # Round trip through the clipboard of the isolated display (not the host clipboard).
    clipboard = ["xclip", "-display", profile.display, "-selection", "clipboard"]
    run(clipboard + ["-in"], text_input=command)
    _require(run(clipboard + ["-out"]) == command, "Clipboard round trip differs; nothing typed")
    delay = str(profile.typing_delay_ms)
    run(["xdotool", "type", "--clearmodifiers", "--delay", delay, "--file", "-"], env=env, text_input=command)
    state = {"sha256": digest_text(command), "length": len(command), "verified": False, "typed_at": time.time()}
    path.write_text(json.dumps(state), encoding="utf-8")
    os.chmod(path, 0o600)
    return f"command_typed=1 length={len(command)} enter_sent=0 next=verify"


def compare(expected: str, observed: str) -> int | None:
    """Return the first differing position, or None when the strings match."""
    for index, (left, right) in enumerate(zip(expected, observed, strict=False)):
        if left != right:
            return index
    return None if len(expected) == len(observed) else min(len(expected), len(observed))


def verify(profile: Profile, command: str, observed: str) -> str:
    path = pending_path(profile)
    _require(path.is_file(), "No typed command is pending")
    state = json.loads(path.read_text(encoding="utf-8"))
    _require(digest_text(command) == state["sha256"], "The command differs from the one that was typed")
    observed = observed.rstrip("\r\n")
    position = compare(command, observed)
    if position is not None:
        raise OperatorError(f"verify_match=0 first_difference={position}; clear the line and type the command again")
    state["verified"] = True
    path.write_text(json.dumps(state), encoding="utf-8")
    return "verify_match=1 next=enter"


def enter(profile: Profile) -> str:
    path = pending_path(profile)
    _require(path.is_file(), "No typed command is pending")
    state = json.loads(path.read_text(encoding="utf-8"))
    _require(state.get("verified") is True, "Enter is sent only after verify_match=1")
    run(["xdotool", "key", "Return"], env=display_env(profile.display))
    path.unlink()
    return "enter_sent=1"


def clear_pending(profile: Profile) -> str:
    path = pending_path(profile)
    if path.exists():
        path.unlink()
    return "pending_cleared=1"


def transfer_lines(data: bytes, target: str, mode: str, owner: str | None) -> list[str]:
    """One-line shell commands that rebuild a file remotely and install it only after a SHA-256 match."""
    _require(target.startswith("/"), "Target must be absolute")
    _require(re.fullmatch(r"[0-7]{3,4}", mode) is not None, "Mode must be octal, for example 0644")
    _require(owner is None or re.fullmatch(r"[a-z_][a-z0-9_-]*:[a-z_][a-z0-9_-]*", owner) is not None, "Bad --owner")
    _require(re.fullmatch(r"[A-Za-z0-9._/-]+", target) is not None, "Target path must be plain ASCII")
    name = re.sub(r"[^A-Za-z0-9._-]", "", Path(target).name)
    _require(bool(name), "Target needs a file name")
    payload = base64.b64encode(gzip.compress(data, mtime=0)).decode("ascii")
    sha = hashlib.sha256(data).hexdigest()
    lines = [
        f"umask 077; u=$(mktemp /tmp/{name}.XXXXXX.b64); t=$(mktemp /tmp/{name}.XXXXXX.tmp); "
        "printf 'transfer_stage=ready\\n'"
    ]
    for start in range(0, len(payload), CHUNK):
        chunk = payload[start : start + CHUNK]
        lines.append(f"printf '%s' '{chunk}' >> \"$u\"; printf 'transfer_chunk=ok\\n'")
    owner_args = f"-o {owner.split(':')[0]} -g {owner.split(':')[1]} " if owner else ""
    lines.append(
        'set -o pipefail; rc=1; if base64 -d "$u" | gzip -d > "$t"; then '
        "a=$(sha256sum \"$t\" | awk '{print $1}'); "
        f"if test \"$a\" = '{sha}'; then sudo -n /usr/bin/install {owner_args}-m {mode} \"$t\" '{target}'; rc=$?; "
        "else rc=65; fi; fi; "
        'if test "$rc" -eq 0; then rm -f "$u" "$t"; printf \'transfer_rc=0 sha256_match=1\\n\'; '
        'else rm -f "$t"; printf \'transfer_rc=%s sha256_match=0 target_unchanged=1\\n\' "$rc"; fi'
    )
    for line in lines:
        _require(len(line) <= MAX_COMMAND and SHELL_CLOSING.search(line) is None, "Generated line is unsafe")
    return lines


def window_class(profile: Profile, window: str) -> str:
    return run(["xprop", "-id", window, "WM_CLASS"], env=display_env(profile.display)).strip()


def keepalive(profile: Profile, check_only: bool, cycles: int | None = None) -> str:
    _require(bool(profile.window_class), "keepalive.window_class is required in the operator profile")
    env = display_env(profile.display)
    expected = f'WM_CLASS(STRING) = "{profile.window_class}", "{profile.window_class}"'
    target = run(["xdotool", "getactivewindow"], env=env).strip()
    _require(window_class(profile, target) == expected, "The active window is not the VDI client; nothing moved")
    if check_only:
        return "keepalive_guard=pass"
    done = 0
    while cycles is None or done < cycles:
        _require(run(["xdotool", "getactivewindow"], env=env).strip() == target, "Active window changed; stopped")
        _require(window_class(profile, target) == expected, "VDI window class changed; stopped")
        (x1, y1), (x2, y2) = profile.keepalive_points
        run(["xdotool", "mousemove", str(x1), str(y1)], env=env)
        time.sleep(0.2)
        run(["xdotool", "mousemove", str(x2), str(y2)], env=env)
        print("mouse_pulse=1", flush=True)
        done += 1
        if cycles is None or done < cycles:
            time.sleep(profile.keepalive_interval)
    return f"keepalive_cycles={done}"


def build_payload(raw: str, *, sudo_check: bool, no_sudo: bool) -> str:
    """Wrap one checked Bash payload for a manual RDP shell; strict mode only inside `bash -c`."""
    _require(not (sudo_check and no_sudo), "--sudo-check and --no-sudo exclude each other")
    _require(bool(raw) and len(raw) <= MAX_PAYLOAD, f"Payload must have 1..{MAX_PAYLOAD} characters")
    _require("\r" not in raw and "\n" not in raw, "Payload must be one line")
    _require(all(32 <= ord(c) < 127 for c in raw), "Payload must be printable ASCII")
    _require(SHELL_CLOSING.search(raw) is None, "exit, logout and exec could close the remote shell")
    if no_sudo:
        _require(not any(item in raw for item in STRICT_MODE), "Strict mode would change the interactive shell")
        payload = raw
    else:
        payload = "set -euo pipefail; " + raw
    _require(subprocess.run(["bash", "-n", "-c", payload], check=False).returncode == 0, "bash -n rejected the payload")
    quoted = shlex.quote(payload)
    if sudo_check:
        command = f"sudo -n -l /bin/bash -c {quoted} >/dev/null; printf 'sudo_payload_check_rc=%s\\n' \"$?\""
    elif no_sudo:
        command = raw
    else:
        command = f"sudo -n /bin/bash -c {quoted}"
    _require(len(command) <= MAX_COMMAND, f"command_too_long length={len(command)} max={MAX_COMMAND}")
    _require(subprocess.run(["bash", "-n", "-c", command], check=False).returncode == 0, "bash -n rejected the command")
    return command


def copy_to_clipboard(command: str, backend: str) -> None:
    if backend == "wayland":
        run(["wl-copy"], text_input=command)
        _require(run(["wl-paste", "--type", "text", "--no-newline"]) == command, "Clipboard check failed")
    else:
        run(["xclip", "-selection", "clipboard", "-in"], text_input=command)
        _require(run(["xclip", "-selection", "clipboard", "-out"]) == command, "Clipboard check failed")


def read_one_line(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    _require(len(lines) == 1, "The file must hold exactly one line")
    return lines[0]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="site-operator", description=(__doc__ or "site-operator").splitlines()[0])
    parser.add_argument("--profile", help=f"Operator profile (default: {DEFAULT_PROFILE} in the project root)")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("xpra-start", help="Start the background Xpra desktop without clipboard and file transfer")
    connect = sub.add_parser("vdi-connect", help="Open a VDI connection file in the Xpra desktop")
    connect.add_argument("connection_file")
    shot = sub.add_parser("screenshot", help="Save a screenshot of the Xpra desktop to the private runtime directory")
    shot.add_argument("--crop", help="WxH+X+Y region, for example the bottom of the terminal")
    shot.add_argument("--output")
    view = sub.add_parser("view", help="Open a viewer window (only when the user asks)")
    view.add_argument("--browse", action="store_true", help="Open the Xpra session browser instead")
    typing = sub.add_parser("type", help="Type one checked command without Enter")
    group = typing.add_mutually_exclusive_group(required=True)
    group.add_argument("--command")
    group.add_argument("--file", help="File with exactly one command line")
    check = sub.add_parser("verify", help="Compare the typed line with the command before Enter")
    group = check.add_mutually_exclusive_group(required=True)
    group.add_argument("--command")
    group.add_argument("--file", help="File with exactly one command line")
    observed = check.add_mutually_exclusive_group(required=True)
    observed.add_argument("--observed-file", help="File with the line as read back from the remote terminal")
    observed.add_argument("--clipboard", action="store_true", help="Read the line from the Xpra display clipboard")
    sub.add_parser("enter", help="Send Enter after a successful verify")
    sub.add_parser("clear-pending", help="Forget a typed command after clearing the remote line by hand")
    transfer = sub.add_parser("transfer", help="Print one-line commands for a chunked transfer with SHA-256")
    transfer.add_argument("source")
    transfer.add_argument("target")
    transfer.add_argument("mode")
    transfer.add_argument("--owner", help="user:group of the installed file")
    transfer.add_argument("--output", help="Write the lines to this file instead of stdout")
    alive = sub.add_parser("keepalive", help="Move the mouse between two points while the VDI window is active")
    alive.add_argument("--check", action="store_true", help="Only check the window guard")
    payload = sub.add_parser("payload", help="Check a Bash payload and copy it for a manual RDP shell")
    payload.add_argument("--check", action="store_true", help="Check only; do not touch the clipboard")
    payload.add_argument("--sudo-check", action="store_true")
    payload.add_argument("--no-sudo", action="store_true")
    payload.add_argument("--clipboard", choices=("wayland", "x11"), default="wayland")
    group = payload.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="File with exactly one payload line")
    group.add_argument("text", nargs="?")
    return parser


def command_text(args: argparse.Namespace) -> str:
    return read_one_line(caller_path(args.file)) if args.file else str(args.command)


def dispatch(args: argparse.Namespace) -> str:
    if args.action == "payload":
        raw = read_one_line(caller_path(args.file)) if args.file else str(args.text)
        command = build_payload(raw, sudo_check=args.sudo_check, no_sudo=args.no_sudo)
        flags = f"strict={int(not args.no_sudo)} sudo_check={int(args.sudo_check)} no_sudo={int(args.no_sudo)}"
        if args.check:
            return f"payload_check=ok {flags} length={len(command)}"
        copy_to_clipboard(command, args.clipboard)
        return f"clipboard=ready {flags} length={len(command)}"
    if args.action == "transfer":
        lines = transfer_lines(caller_path(args.source).read_bytes(), args.target, args.mode, args.owner)
        if args.output:
            output = caller_path(args.output)
            output.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return f"transfer_lines={len(lines)} output={output}"
        return "\n".join(lines)
    # run-python.sh starts in the project root, so the default profile path is relative to it.
    profile = load_profile(caller_path(args.profile) if args.profile else DEFAULT_PROFILE.resolve())
    if args.action == "xpra-start":
        return xpra_start(profile)
    if args.action == "vdi-connect":
        return vdi_connect(profile, caller_path(args.connection_file))
    if args.action == "screenshot":
        return screenshot(profile, args.crop, caller_path(args.output) if args.output else None)
    if args.action == "view":
        argv, env = view_command(profile, args.browse)
        os.execvpe(argv[0], argv, env)
    if args.action == "type":
        return type_command(profile, command_text(args))
    if args.action == "verify":
        if args.clipboard:
            seen = run(["xclip", "-display", profile.display, "-selection", "clipboard", "-out"])
        else:
            seen = caller_path(args.observed_file).read_text(encoding="utf-8")
        return verify(profile, command_text(args), seen)
    if args.action == "enter":
        return enter(profile)
    if args.action == "clear-pending":
        return clear_pending(profile)
    return keepalive(profile, args.check)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if sys.platform == "win32":
        print("REFUSED: site-operator runs on a Linux operator host (Xpra, xdotool, bash)", file=sys.stderr)
        return 1
    try:
        print(dispatch(args))
    except OperatorError as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        print(f"FAILED: {type(error).__name__}; check the paths and the operator profile", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
