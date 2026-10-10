"""Dead `.X<N>-lock` / `.X11-unix/X<N>` entries are reaped; live, fresh, reserved and foreign ones are kept.

The X server, Xpra and the platform binary are stubs inside tmp_path.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts.python import onec_xpra
from scripts.python.onec_xpra import reap_dead_x_displays

pytestmark = pytest.mark.skipif(os.name == "nt", reason="Linux X11 display files")

ROOT = Path(__file__).resolve().parents[2]
OLD = time.time() - 3600


def _dead_pid() -> int:
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait()
    return process.pid


def _lock(root: Path, number: int, pid: int, old: bool = True) -> Path:
    path = root / f".X{number}-lock"
    path.write_text(f"{pid:10d}\n", encoding="ascii")
    if old:
        os.utime(path, (OLD, OLD))
    return path


def _socket(root: Path, number: int, listen: bool = False, old: bool = True) -> tuple[Path, socket.socket | None]:
    path = root / ".X11-unix" / f"X{number}"
    server = socket.socket(socket.AF_UNIX)
    server.bind(str(path))
    kept: socket.socket | None = None
    if listen:
        server.listen(1)
        kept = server
    else:
        server.close()  # the file stays without a listener, as after SIGKILL
    if old:
        os.utime(path, (OLD, OLD))
    return path, kept


@pytest.fixture
def x_root(tmp_path: Path) -> Path:
    root = tmp_path / "x"
    (root / ".X11-unix").mkdir(parents=True)
    (tmp_path / "owners").mkdir()
    return root


def test_reaps_only_provably_dead_entries(tmp_path: Path, x_root: Path) -> None:
    owners = tmp_path / "owners"
    dead = _dead_pid()
    dead_lock = _lock(x_root, 50201, dead)
    dead_sock, _ = _socket(x_root, 50201)
    lock_only = _lock(x_root, 50202, dead)
    listening_lock = _lock(x_root, 50203, dead)
    listening_sock, listener = _socket(x_root, 50203, listen=True)
    fresh_lock = _lock(x_root, 50204, dead, old=False)
    fresh_sock, _ = _socket(x_root, 50204, old=False)
    alive_lock = _lock(x_root, 50205, os.getpid())
    _socket(x_root, 50205)
    reserved_lock = _lock(x_root, 50206, dead)
    (owners / "session-50206.owner").write_text("reserved\n", encoding="utf-8")
    no_lock_sock, _ = _socket(x_root, 50207)
    target = _lock(tmp_path, 50208, dead)
    symlink_lock = x_root / ".X50208-lock"
    symlink_lock.symlink_to(target)
    garbage_lock = x_root / ".X50209-lock"
    garbage_lock.write_text("not-a-pid\n", encoding="ascii")
    os.utime(garbage_lock, (OLD, OLD))
    outside = _lock(x_root, 50210, dead)
    try:
        reaped = reap_dead_x_displays(x_root, 50201, 50209, owners, 10)
    finally:
        assert listener is not None
        listener.close()
    assert reaped == [50201, 50202]
    assert not dead_lock.exists() and not os.path.lexists(dead_sock) and not lock_only.exists()
    for kept in (
        listening_lock,
        listening_sock,
        fresh_lock,
        fresh_sock,
        alive_lock,
        reserved_lock,
        no_lock_sock,
        symlink_lock,
        target,
        garbage_lock,
        outside,
    ):
        assert os.path.lexists(kept), kept


def test_foreign_owner_is_never_reaped(tmp_path: Path, x_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock = _lock(x_root, 50211, _dead_pid())
    sock, _ = _socket(x_root, 50211)
    monkeypatch.setattr(onec_xpra.os, "getuid", lambda: os.geteuid() + 1)
    assert reap_dead_x_displays(x_root, 50211, 50211, tmp_path / "owners", 10) == []
    assert lock.exists() and os.path.lexists(sock)


def test_display_zero_and_one_are_never_reaped(tmp_path: Path, x_root: Path) -> None:
    dead = _dead_pid()
    locks = [_lock(x_root, number, dead) for number in (0, 1)]
    assert reap_dead_x_displays(x_root, 0, 1, tmp_path / "owners", 10) == []
    assert all(lock.exists() for lock in locks)


def test_cli_prints_reaped_numbers(tmp_path: Path, x_root: Path) -> None:
    _lock(x_root, 50212, _dead_pid())
    result = subprocess.run(
        [sys.executable, "-m", "scripts.python.onec_xpra", "reap-x-displays", str(x_root), "50212", "50212",
         str(tmp_path / "owners"), "10"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["50212"]
    bad = subprocess.run(
        [sys.executable, "-m", "scripts.python.onec_xpra", "reap-x-displays", str(x_root)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert bad.returncode == 2 and "usage: reap-x-displays" in bad.stderr


def _stub_tools(tmp_path: Path) -> Path:
    binary = tmp_path / "bin"
    binary.mkdir()
    for name in ("Xvfb", "openbox", "1cv8"):
        path = binary / name
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        path.chmod(0o755)
    (binary / "xdpyinfo").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (binary / "xdpyinfo").chmod(0o755)
    # The stub records the display the adapter picked and fails, so no X server is started.
    (binary / "xpra").write_text(
        '#!/bin/sh\n[ "$1" = start-desktop ] && printf %s "$2" >"$FAKE_ROOT/selected"\nexit 1\n', encoding="utf-8"
    )
    (binary / "xpra").chmod(0o755)
    return binary


def _run_adapter(tmp_path: Path, x_root: Path, display: int) -> subprocess.CompletedProcess[str]:
    binary = _stub_tools(tmp_path)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    env = {
        **os.environ,
        "PATH": str(binary) + os.pathsep + os.environ["PATH"],
        "XDG_RUNTIME_DIR": str(runtime),
        "FAKE_ROOT": str(tmp_path),
        "ONEC_PYTHON": sys.executable,
        "ONEC_CAPABILITY_RUN_ROOT": str(tmp_path / "run"),
        "ONEC_DIRECT_PLATFORM_XPRA_ENABLED": "1",
        "ONEC_DIRECT_PLATFORM_XPRA_XVFB_ARGS": "Xvfb -screen 0 1024x768x24",
        "ONEC_DIRECT_PLATFORM_X11_TMP_ROOT": str(x_root),
        "ONEC_DIRECT_PLATFORM_XPRA_DISPLAY_MIN": str(display),
        "ONEC_DIRECT_PLATFORM_XPRA_DISPLAY_MAX": str(display),
    }
    return subprocess.run(
        ["bash", str(ROOT / "scripts/adapters/direct-platform.sh"), str(binary / "1cv8")],
        env=env, capture_output=True, text=True, timeout=60, check=False,
    )  # fmt: skip


def test_adapter_reclaims_dead_display_before_picking(tmp_path: Path, x_root: Path) -> None:
    dead_lock = _lock(x_root, 50220, _dead_pid())
    dead_sock, _ = _socket(x_root, 50220)
    result = _run_adapter(tmp_path, x_root, 50220)
    assert "removed dead X display entries: :50220" in result.stderr, result.stderr
    assert (tmp_path / "selected").read_text(encoding="utf-8") == ":50220"
    assert not dead_lock.exists() and not os.path.lexists(dead_sock)


def test_adapter_keeps_live_display_and_reports_exhausted_range(tmp_path: Path, x_root: Path) -> None:
    live_lock = _lock(x_root, 50230, _dead_pid())
    live_sock, listener = _socket(x_root, 50230, listen=True)
    try:
        result = _run_adapter(tmp_path, x_root, 50230)
    finally:
        assert listener is not None
        listener.close()
    assert result.returncode != 0
    assert "failed to pick a free xpra display in range 50230..50230" in result.stderr
    assert live_lock.exists() and os.path.lexists(live_sock)
    assert not (tmp_path / "selected").exists()
