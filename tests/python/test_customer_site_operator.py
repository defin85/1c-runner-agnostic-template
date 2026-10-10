"""Operator-host tools of the optional customer-site-operations module, run against fake X11 tools."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.python import site_operator
from scripts.python.site_operator import OperatorError

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "automation" / "optional" / "customer-site-operations" / "files" / "infra" / "site"
EXAMPLE = EXAMPLE / "operator.example.json"

FAKE_TOOL = """#!/bin/sh
name=$(basename "$0")
printf '%s %s\\n' "$name" "$*" >> "$FAKE_LOG"
case "$name $*" in
  "xclip "*"-in"*) cat > "$FAKE_CLIPBOARD" ;;
  "xclip "*"-out"*) cat "$FAKE_CLIPBOARD" ;;
  "xdotool type"*) cat > "$FAKE_TYPED" ;;
  "xdotool getactivewindow"*) printf '42\\n' ;;
  "xprop "*) printf 'WM_CLASS(STRING) = "%s", "%s"\\n' "$FAKE_WM_CLASS" "$FAKE_WM_CLASS" ;;
esac
"""

FAKE_CLIENT = """#!/bin/sh
env > "$(dirname "$1")/client-env.txt"
printf '%s\\n' "$@" > "$(dirname "$1")/client-args.txt"
"""

FAKE_SUDO = """#!/bin/sh
[ "$1" = "-n" ] && shift
exec "$@"
"""


class OperatorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("xclip", "xdotool", "xprop", "import", "xpra"):
            self._exec(self.bin / name, FAKE_TOOL)
        self._exec(self.bin / "sudo", FAKE_SUDO)
        self.client = self._exec(self.root / "vdi-client", FAKE_CLIENT)
        self.runtime = self.root / "runtime"
        self.log = self.root / "tools.log"
        profile = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        profile["vdi_client"] = str(self.client)
        self.profile_path = self.root / "operator.json"
        self.profile_path.write_text(json.dumps(profile), encoding="utf-8")
        env = {
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "XDG_RUNTIME_DIR": str(self.runtime),
            "FAKE_LOG": str(self.log),
            "FAKE_CLIPBOARD": str(self.root / "clipboard"),
            "FAKE_TYPED": str(self.root / "typed"),
            "FAKE_WM_CLASS": "VdiClient",
            "SITE_OPERATOR_CWD": str(self.root),
        }
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)
        self.profile = site_operator.load_profile(self.profile_path)

    @staticmethod
    def _exec(path: Path, text: str) -> Path:
        path.write_text(text, encoding="utf-8")
        path.chmod(0o755)
        return path

    def calls(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []

    def cli(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = site_operator.main(["--profile", str(self.profile_path), *args])
        return code, out.getvalue(), err.getvalue()


class ProfileTest(OperatorTestCase):
    def test_missing_profile_names_the_example(self) -> None:
        with self.assertRaisesRegex(OperatorError, "operator.example.json"):
            site_operator.load_profile(self.root / "absent.json")

    def test_xpra_desktop_has_no_clipboard_and_no_file_transfer(self) -> None:
        argv = site_operator.xpra_start_argv(self.profile)
        self.assertIn("--clipboard=no", argv)
        self.assertIn("--file-transfer=no", argv)
        self.assertIn("--attach=no", argv)
        self.assertEqual(argv[2], ":100")


class VdiConnectTest(OperatorTestCase):
    def test_client_gets_clean_environment_and_private_copy(self) -> None:
        source = self.root / "ticket.ica"
        source.write_text("[ApplicationServers]\nsecret-ticket-value\n", encoding="utf-8")
        extra = {"https_proxy": "http://proxy.example", "NO_PROXY": "x", "Http_Proxy": "y", "WAYLAND_DISPLAY": "w"}
        with patch.dict(os.environ, extra):
            code, out, err = self.cli("vdi-connect", "ticket.ica")
        self.assertEqual(code, 0, err)
        self.assertNotIn("secret-ticket-value", out + err)
        folder = self.runtime / "site-operator"
        env_file = folder / "client-env.txt"
        for _ in range(100):
            if env_file.exists() and env_file.stat().st_size:
                break
            time.sleep(0.05)
        env = dict(line.split("=", 1) for line in env_file.read_text(encoding="utf-8").splitlines() if "=" in line)
        self.assertFalse([key for key in env if key.lower().endswith("_proxy")])
        self.assertNotIn("WAYLAND_DISPLAY", env)
        self.assertEqual(env["DISPLAY"], ":100")
        self.assertEqual(env["TZ"], "UTC")
        self.assertEqual(stat.S_IMODE(folder.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((folder / "launch.ica").stat().st_mode), 0o600)
        self.assertEqual((folder / "client-args.txt").read_text(encoding="utf-8").strip(), str(folder / "launch.ica"))

    def test_missing_connection_file_is_refused(self) -> None:
        code, _, err = self.cli("vdi-connect", "absent.ica")
        self.assertEqual(code, 1)
        self.assertIn("fresh one", err)


class TypingTest(OperatorTestCase):
    def test_unsafe_commands_are_refused_before_typing(self) -> None:
        for command in ("", "echo привет", "ls\nrm -rf /", "echo ok; exit 1", "exec bash", "echo 'open", "x" * 4097):
            with self.subTest(command=command[:20]):
                with self.assertRaises(OperatorError):
                    site_operator.type_command(self.profile, command)
        self.assertEqual(self.calls(), [])

    def test_type_verify_enter_sequence(self) -> None:
        command = "systemctl status srv1cv8 --no-pager | head -n 5"
        self.assertIn("enter_sent=0", site_operator.type_command(self.profile, command))
        self.assertEqual((self.root / "typed").read_text(encoding="utf-8"), command)
        self.assertFalse(any("Return" in call for call in self.calls()))
        with self.assertRaisesRegex(OperatorError, "only after verify"):
            site_operator.enter(self.profile)
        with self.assertRaisesRegex(OperatorError, "first_difference=9"):
            site_operator.verify(self.profile, command, "systemctl|status srv1cv8 --no-pager | head -n 5")
        with self.assertRaisesRegex(OperatorError, "pending"):
            site_operator.type_command(self.profile, "true")
        self.assertIn("verify_match=1", site_operator.verify(self.profile, command, command + "\n"))
        self.assertEqual(site_operator.enter(self.profile), "enter_sent=1")
        self.assertTrue(self.calls()[-1].startswith("xdotool key Return"))
        with self.assertRaisesRegex(OperatorError, "No typed command"):
            site_operator.enter(self.profile)

    def test_verify_refuses_a_different_command(self) -> None:
        site_operator.type_command(self.profile, "uptime")
        with self.assertRaisesRegex(OperatorError, "differs"):
            site_operator.verify(self.profile, "hostname", "hostname")


class TransferTest(OperatorTestCase):
    def run_lines(self, lines: list[str]) -> str:
        env = dict(os.environ)
        result = subprocess.run(
            ["bash", "-c", "\n".join(lines)], capture_output=True, text=True, env=env, timeout=60, check=False
        )
        return result.stdout

    def test_transfer_installs_only_after_sha256_match(self) -> None:
        data = os.urandom(3000) + b"tail"
        source = self.root / "payload.bin"
        source.write_bytes(data)
        target = self.root / "installed" / "site-rac"
        target.parent.mkdir()
        lines = site_operator.transfer_lines(source.read_bytes(), str(target), "0640", None)
        self.assertGreater(len(lines), 3)
        self.assertTrue(all(len(line) <= site_operator.MAX_COMMAND and "\n" not in line for line in lines))
        output = self.run_lines(lines)
        self.assertIn("transfer_rc=0 sha256_match=1", output)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), hashlib.sha256(data).hexdigest())
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)

    def test_corrupted_chunk_leaves_target_unchanged(self) -> None:
        target = self.root / "target.txt"
        target.write_text("old", encoding="utf-8")
        lines = site_operator.transfer_lines(b"new content " * 100, str(target), "0644", None)
        # Change one base64 character in the middle of the compressed body (gzip ignores some header bytes).
        line = lines[1]
        index = len("printf '%s' '") + len(line.split("'")[3]) // 2
        lines[1] = line[:index] + ("A" if line[index] != "A" else "B") + line[index + 1 :]
        output = self.run_lines(lines)
        self.assertIn("sha256_match=0 target_unchanged=1", output)
        self.assertEqual(target.read_text(encoding="utf-8"), "old")

    def test_transfer_validates_mode_target_and_owner(self) -> None:
        for target, mode, owner in (("relative", "0644", None), ("/x", "999", None), ("/x", "0644", "root")):
            with self.subTest(target=target, mode=mode, owner=owner):
                with self.assertRaises(OperatorError):
                    site_operator.transfer_lines(b"x", target, mode, owner)
        line = site_operator.transfer_lines(b"x", "/opt/site/x", "0755", "root:root")[-1]
        self.assertIn("/usr/bin/install -o root -g root -m 0755", line)


class KeepaliveTest(OperatorTestCase):
    def test_moves_mouse_only_while_the_vdi_window_is_active(self) -> None:
        self.assertEqual(site_operator.keepalive(self.profile, check_only=True), "keepalive_guard=pass")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(site_operator.keepalive(self.profile, False, cycles=1), "keepalive_cycles=1")
        moves = [call for call in self.calls() if call.startswith("xdotool mousemove")]
        self.assertEqual(moves, ["xdotool mousemove 950 700", "xdotool mousemove 952 700"])
        self.assertFalse([call for call in self.calls() if " key" in call or "click" in call])

    def test_other_window_stops_without_moving(self) -> None:
        with patch.dict(os.environ, {"FAKE_WM_CLASS": "Terminal"}):
            with self.assertRaisesRegex(OperatorError, "not the VDI client"):
                site_operator.keepalive(self.profile, False, cycles=1)
        self.assertFalse([call for call in self.calls() if "mousemove" in call])


class PayloadTest(OperatorTestCase):
    def test_root_payload_is_wrapped_in_strict_bash(self) -> None:
        command = site_operator.build_payload("echo 'a b' | wc -c", sudo_check=False, no_sudo=False)
        self.assertTrue(command.startswith("sudo -n /bin/bash -c "))
        self.assertIn("set -euo pipefail;", command)
        check = site_operator.build_payload("id -u", sudo_check=True, no_sudo=False)
        self.assertIn("sudo -n -l /bin/bash -c", check)
        self.assertIn("sudo_payload_check_rc=", check)
        self.assertEqual(site_operator.build_payload("uptime", sudo_check=False, no_sudo=True), "uptime")

    def test_payload_refusals(self) -> None:
        cases = (
            ("exit 0", False),
            ("echo ok; logout", False),
            ("set -e; ls", True),
            ("echo 'broken", False),
            ("echo é", False),
            ("x" * 3976, False),
        )
        for raw, no_sudo in cases:
            with self.subTest(raw=raw[:20]):
                with self.assertRaises(OperatorError):
                    site_operator.build_payload(raw, sudo_check=False, no_sudo=no_sudo)
        with self.assertRaises(OperatorError):
            site_operator.build_payload("ls", sudo_check=True, no_sudo=True)

    def test_check_mode_does_not_touch_clipboard(self) -> None:
        code, out, err = self.cli("payload", "--check", "ls -l /etc")
        self.assertEqual(code, 0, err)
        self.assertIn("payload_check=ok strict=1", out)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
