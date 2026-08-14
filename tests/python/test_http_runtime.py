from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.python.http_runtime import build_webinst_command, load_apache_publication, run_publish_http
from scripts.python.runtime_process import ProcessResult
from scripts.python.runtime_profiles import load_runtime_profile


class HttpRuntimeTests(unittest.TestCase):
    def make_profile(self, root: Path) -> Path:
        path = root / "profile.json"
        path.write_text(json.dumps({
            "schemaVersion": 3,
            "profileName": "http-test",
            "capabilities": {"publishHttp": {
                "backend": "apache-webinst",
                "webinstPath": "C:/Program Files/1cv8/webinst.exe",
                "configPath": "C:/Apache24/conf/httpd.conf",
                "directory": "C:/Apache24/htdocs/demo",
                "descriptor": "C:/Apache24/conf/demo.vrd",
                "name": "demo",
                "connectionString": "Srvr=localhost;Ref=demo;",
                "serviceName": "Apache2.4",
                "url": "http://localhost/demo/",
            }},
        }), encoding="utf-8")
        return path

    def test_webinst_command_preserves_paths_as_argv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile = load_runtime_profile(self.make_profile(Path(temp_dir)))
            command = build_webinst_command(load_apache_publication(profile))
            self.assertIn("C:/Program Files/1cv8/webinst.exe", command)
            self.assertIn("C:/Apache24/htdocs/demo", command)
            self.assertEqual(command[command.index("-descriptor") + 1], "C:/Apache24/conf/demo.vrd")
            self.assertEqual(command[command.index("-confPath") + 1], "C:/Apache24/conf/httpd.conf")

    def test_false_green_restart_fails_http_postcondition(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = self.make_profile(root)
            exit_code = run_publish_http(
                ["--profile", str(profile_path), "--run-root", str(root / "run")],
                service_manager=lambda *_args, **_kwargs: ProcessResult(["sc.exe"], 0, "", ""),
                http_probe=lambda _url: False,
                command_runner=lambda *_args, **_kwargs: 0,
                service_pid=lambda _name: 42,
            )
            summary = json.loads((root / "run" / "summary.json").read_text(encoding="utf-8"))
            self.assertNotEqual(exit_code, 0)
            self.assertEqual(summary["status"], "failed")
            self.assertIn("postcondition", summary["postcondition_failure"])

    def test_unchanged_service_pid_fails_even_when_http_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = self.make_profile(root)
            exit_code = run_publish_http(
                ["--profile", str(profile_path), "--run-root", str(root / "run")],
                service_manager=lambda *_args, **_kwargs: ProcessResult(["sc.exe"], 0, "", ""),
                http_probe=lambda _url: True,
                command_runner=lambda *_args, **_kwargs: 0,
                service_pid=lambda _name: 42,
            )
            self.assertNotEqual(exit_code, 0)

    def test_summary_redacts_connection_string(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = self.make_profile(root)
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
            payload["capabilities"]["publishHttp"]["connectionString"] = "Srvr=localhost;Usr=user;Pwd=SENTINEL_SECRET;"
            profile_path.write_text(json.dumps(payload), encoding="utf-8")
            run_publish_http(["--profile", str(profile_path), "--run-root", str(root / "run"), "--dry-run"])
            summary = (root / "run" / "summary.json").read_text(encoding="utf-8")
            self.assertNotIn("SENTINEL_SECRET", summary)
            self.assertIn("__REDACTED__", summary)

    def test_logs_redact_connection_string(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = self.make_profile(root)
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
            connection_string = "Srvr=localhost;Usr=user;Pwd=SENTINEL_SECRET;"
            payload["capabilities"]["publishHttp"]["connectionString"] = connection_string
            profile_path.write_text(json.dumps(payload), encoding="utf-8")

            def fake_run(*_args: object, stdout_path: Path, stderr_path: Path, **_kwargs: object) -> int:
                Path(stdout_path).write_text(connection_string, encoding="utf-8")
                Path(stderr_path).write_text(connection_string, encoding="utf-8")
                return 1

            run_publish_http(
                ["--profile", str(profile_path), "--run-root", str(root / "run")],
                command_runner=fake_run,
            )
            logs = (root / "run" / "stdout.log").read_text(encoding="utf-8") + (root / "run" / "stderr.log").read_text(encoding="utf-8")
            self.assertNotIn("SENTINEL_SECRET", logs)
            self.assertIn("__REDACTED_SECRET__", logs)

    def test_interruption_publishes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = self.make_profile(root)

            def interrupting_runner(*_args: object, **_kwargs: object) -> int:
                raise KeyboardInterrupt

            exit_code = run_publish_http(
                ["--profile", str(profile_path), "--run-root", str(root / "run")],
                command_runner=interrupting_runner,
            )
            summary = json.loads((root / "run" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 130)
            self.assertEqual(summary["status"], "interrupted")


if __name__ == "__main__":
    unittest.main()
