from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from scripts.python import run_client as run_client_module
from scripts.python.runtime_errors import CommandError
from scripts.python.runtime_observation import EXIT_STALLED, OBSERVATION_FILE

SECRET = "Fixture-Pa55-value"
PASSWORD_ENV = "RUN_CLIENT_FIXTURE_PASSWORD"


def write_profile(root: Path) -> Path:
    platform: dict[str, Any] = {"binaryPath": str(root / "bin" / "1cv8")}
    if os.name != "nt":
        # run-client on Linux requires xpra; a Windows profile must not enable this POSIX-only feature.
        platform["xpra"] = {
            "enabled": True,
            "startChild": "openbox",
            "xvfbArgs": ["Xvfb", "-screen", "0", "1024x768x24"],
        }
    profile = {
        "schemaVersion": 3,
        "profileName": "run-client-fixture",
        "platform": platform,
        "infobase": {
            "mode": "file",
            "filePath": str(root / "infobase"),
            "auth": {"mode": "user-password", "user": "Operator", "passwordEnv": PASSWORD_ENV},
        },
        "capabilities": {},
    }
    path = root / "profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    return path


def call(argv: list[str]) -> tuple[int, dict[str, Any]]:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = run_client_module.run_client(argv)
    lines = [line for line in stream.getvalue().splitlines() if line.startswith("{")]
    return code, json.loads(lines[-1]) if lines else {}


class RunClientTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        # run-client canonicalizes the run root; resolve here so Windows 8.3 temp aliases compare equal.
        self.root = Path(self._tmp.name).resolve()
        self.profile = write_profile(self.root)
        self.run_root = self.root / "run"
        patcher = mock.patch.dict(
            os.environ, {PASSWORD_ENV: SECRET, "ONEC_OBSERVATION_INTERVAL_SECONDS": "1"}, clear=False
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def all_artifacts_text(self) -> str:
        chunks = []
        for path in self.run_root.rglob("*"):
            if path.is_file() and path.suffix != ".png":
                chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        return "\n".join(chunks)


class RunClientStartTests(RunClientTestCase):
    def test_dry_run_masks_password(self) -> None:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = run_client_module.run_client(
                ["start", "--profile", str(self.profile), "--run-root", str(self.run_root), "--dry-run"]
            )
        self.assertEqual(code, 0)
        self.assertNotIn(SECRET, stream.getvalue())
        payload = json.loads(stream.getvalue())
        command = payload["command"]
        self.assertEqual(command[command.index("/P") + 1], "***")
        self.assertEqual(payload["target"], "run-client-fixture")

    def test_password_is_not_accepted_as_argument(self) -> None:
        with self.assertRaises(CommandError):
            run_client_module.run_client(["start", "--profile", str(self.profile), "--password", SECRET])

    def test_idle_timeout_returns_125_with_screenshot_and_masked_artifacts(self) -> None:
        progress = self.root / "progress.txt"
        code = (
            "import sys, time\n"
            "print(' '.join(sys.argv[1:]), flush=True)\n"
            f"open({str(progress)!r}, 'w').write('opened')\n"
            "time.sleep(60)\n"
        )

        def fake_launch(_profile: object, arguments: list[str], run_root: Path) -> tuple[list[str], dict[str, str]]:
            return [sys.executable, "-c", code, *arguments], {"ONEC_CAPABILITY_RUN_ROOT": str(run_root)}

        def fake_capture(_run_root: Path, out: Path) -> bool:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"\x89PNG fixture")
            return True

        with (
            mock.patch.object(run_client_module, "_launch", fake_launch),
            mock.patch.object(run_client_module, "_capture", fake_capture),
        ):
            exit_code, payload = call(
                [
                    "start",
                    "--profile",
                    str(self.profile),
                    "--run-root",
                    str(self.run_root),
                    "--wait",
                    "--idle-timeout",
                    "1.5",
                    "--progress-file",
                    str(progress),
                ]
            )
        self.assertEqual(exit_code, EXIT_STALLED)
        self.assertEqual(payload["status"], "idle-timeout")
        self.assertEqual(Path(payload["screenshot"]), self.run_root / "screenshots" / "idle-timeout.png")
        self.assertTrue((self.run_root / "screenshots" / "idle-timeout.png").is_file())
        self.assertIn("***", (self.run_root / "stdout.log").read_text(encoding="utf-8"))
        self.assertNotIn(SECRET, self.all_artifacts_text())
        summary = json.loads((self.run_root / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["observation"]["terminalReason"], "stalled")
        self.assertTrue((self.run_root / OBSERVATION_FILE).is_file())

    def test_run_root_with_session_is_not_reused(self) -> None:
        self.run_root.mkdir()
        (self.run_root / run_client_module.STATE_FILE).write_text("{}", encoding="utf-8")
        with self.assertRaises(CommandError):
            run_client_module.run_client(["start", "--profile", str(self.profile), "--run-root", str(self.run_root)])

    def test_idle_timeout_requires_progress_file_and_wait(self) -> None:
        with self.assertRaises(CommandError):
            run_client_module.run_client(["start", "--profile", str(self.profile), "--idle-timeout", "5"])
        with self.assertRaises(CommandError):
            run_client_module.run_client(
                ["start", "--profile", str(self.profile), "--wait", "--idle-timeout", "5", "--dry-run"]
            )


@unittest.skipUnless(sys.platform.startswith("linux"), "process ownership uses /proc")
class RunClientIsolationTests(RunClientTestCase):
    def start_fake_client(self, owner_root: Path) -> subprocess.Popen[bytes]:
        fake = self.root / "bin" / "1cv8"
        fake.parent.mkdir(parents=True, exist_ok=True)
        # A script named 1cv8 gets the process name of the platform client.
        fake.write_text("#!/bin/sh\nwhile :; do sleep 0.2; done\n", encoding="utf-8")
        fake.chmod(0o755)
        process = subprocess.Popen([str(fake)], env={**os.environ, "ONEC_CAPABILITY_RUN_ROOT": str(owner_root)})
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not run_client_module._owns_process(process.pid, owner_root):
            time.sleep(0.05)
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        return process

    def prepare_session(self, run_root: Path, pid: int) -> None:
        (run_root / "xpra").mkdir(parents=True)
        (run_root / run_client_module.STATE_FILE).write_text('{"schemaVersion": 1}', encoding="utf-8")
        (run_root / run_client_module.PID_FILE).write_text(f"{pid}\n", encoding="ascii")
        (run_root / "xpra" / "active-display.env").write_text(":4242\nxpra.log\n", encoding="utf-8")

    def test_client_of_another_run_root_is_not_controlled(self) -> None:
        other_root = (self.root / "other-run").resolve()
        process = self.start_fake_client(other_root)
        own_root = self.run_root.resolve()
        self.prepare_session(own_root, process.pid)
        self.assertTrue(run_client_module._owns_process(process.pid, other_root))
        self.assertFalse(run_client_module._owns_process(process.pid, own_root))
        for argv in (
            ["screenshot", "--run-root", str(own_root)],
            ["key", "--run-root", str(own_root), "Escape"],
            ["click", "--run-root", str(own_root), "10", "10"],
        ):
            with self.assertRaises(CommandError):
                run_client_module.run_client(argv)
        _, status = call(["status", "--run-root", str(own_root)])
        self.assertFalse(status["client_alive"])
        _, stopped = call(["stop", "--run-root", str(own_root), "--timeout", "1"])
        self.assertEqual(stopped["status"], "stopped")
        self.assertIsNone(process.poll())

    def test_process_that_is_not_a_client_is_not_owned(self) -> None:
        own_root = self.run_root.resolve()
        self.prepare_session(own_root, os.getpid())
        self.assertFalse(run_client_module._owns_process(os.getpid(), own_root))

    def test_stop_terminates_own_client_with_operator_reason(self) -> None:
        own_root = self.run_root.resolve()
        process = self.start_fake_client(own_root)
        self.prepare_session(own_root, process.pid)
        exit_code, payload = call(["stop", "--run-root", str(own_root), "--timeout", "5"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "stopped")
        self.assertIsNotNone(process.wait(timeout=5))
        extra = json.loads((own_root / "terminal-observation-extra.json").read_text(encoding="utf-8"))
        self.assertEqual(extra, {"terminalReason": "operator-stop"})


if __name__ == "__main__":
    unittest.main()
