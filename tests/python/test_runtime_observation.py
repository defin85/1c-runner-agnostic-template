from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from scripts.python.runtime_observation import (
    EXIT_LAUNCH_FAILED,
    EXIT_MISSING_RESULT,
    EXIT_STALLED,
    EXIT_TIMEOUT,
    OBSERVATION_FILE,
    TERMINAL_EXTRA_FILE,
    ObservationRequest,
    build_observation_summary,
    launch_identity,
    publish_observation_summary,
    run_observed,
)

TERMINAL_EVENTS = {"completed", "failed"}


def python_command(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def read_events(run_root: Path) -> list[dict[str, Any]]:
    lines = (run_root / OBSERVATION_FILE).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


class ObservationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.run_root = self.root / "run"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def observe(self, command: list[str], **options: Any):
        options.setdefault("interval_seconds", 1.0)
        options.setdefault("term_grace_seconds", 2.0)
        return run_observed(
            ObservationRequest(
                capability="test-capability", target="fixture", run_root=self.run_root, command=command, **options
            )
        )

    def assert_process_gone(self, pid: int) -> None:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.1)
        self.fail(f"process {pid} of the stopped group is still alive")

    def assert_single_terminal(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        self.assertEqual([item["event"] for item in events].count("started"), 1)
        self.assertEqual(events[0]["event"], "started")
        terminals = [item for item in events if item["event"] in TERMINAL_EVENTS]
        self.assertEqual(len(terminals), 1)
        self.assertIs(events[-1], terminals[0])
        self.assertEqual([item["seq"] for item in events], list(range(1, len(events) + 1)))
        for item in events:
            self.assertEqual(item["schemaVersion"], 1)
        return terminals[0]


class RunObservedTests(ObservationTestCase):
    def test_success_writes_one_started_heartbeats_and_one_terminal(self) -> None:
        result = self.observe(python_command("import time; time.sleep(2.3)"))
        events = read_events(self.run_root)
        terminal = self.assert_single_terminal(events)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(terminal["event"], "completed")
        self.assertEqual(terminal["terminalReason"], "completed")
        self.assertGreaterEqual(sum(item["event"] == "heartbeat" for item in events), 1)

    def test_command_exit_code_is_preserved(self) -> None:
        result = self.observe(python_command("raise SystemExit(3)"))
        terminal = self.assert_single_terminal(read_events(self.run_root))
        self.assertEqual(result.exit_code, 3)
        self.assertEqual(terminal["event"], "failed")
        self.assertEqual(terminal["terminalReason"], "command-exit")
        self.assertEqual(terminal["exitCode"], 3)

    def test_missing_expected_result_fails_even_with_zero_exit(self) -> None:
        result = self.observe(python_command("pass"), expected_result=self.run_root / "result.txt")
        terminal = self.assert_single_terminal(read_events(self.run_root))
        self.assertEqual(result.exit_code, EXIT_MISSING_RESULT)
        self.assertEqual(terminal["event"], "failed")
        self.assertEqual(terminal["terminalReason"], "missing-result")
        self.assertEqual(terminal["expectedResult"], "result.txt")

    def test_present_expected_result_completes(self) -> None:
        result_file = self.run_root / "result.txt"
        code = f"open({str(result_file)!r}, 'w').write('ok')"
        result = self.observe(python_command(code), expected_result=result_file)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(self.assert_single_terminal(read_events(self.run_root))["event"], "completed")

    def test_launch_failure_is_one_failed_terminal(self) -> None:
        result = self.observe([str(self.root / "missing-binary")])
        terminal = self.assert_single_terminal(read_events(self.run_root))
        self.assertEqual(result.exit_code, EXIT_LAUNCH_FAILED)
        self.assertEqual(terminal["terminalReason"], "launch-failed")
        self.assertEqual(terminal["source"], "launch")

    def test_stalled_progress_stops_process_group_only_with_threshold(self) -> None:
        progress = self.run_root / "progress.txt"
        child_pid = self.run_root / "child.pid"
        code = (
            "import subprocess, sys, time\n"
            f"open({str(progress)!r}, 'w').write('stage-1')\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            f"open({str(child_pid)!r}, 'w').write(str(child.pid))\n"
            "time.sleep(60)\n"
        )
        self.run_root.mkdir(parents=True)
        result = self.observe(python_command(code), progress_file=progress, stall_timeout_seconds=1.5)
        terminal = self.assert_single_terminal(read_events(self.run_root))
        self.assertEqual(result.exit_code, EXIT_STALLED)
        self.assertEqual(terminal["terminalReason"], "stalled")
        self.assertEqual(terminal["lastProgress"], "stage-1")
        self.assertGreaterEqual(terminal["stageAgeSeconds"], 1)
        if os.name != "nt":
            self.assert_process_gone(int(child_pid.read_text(encoding="ascii")))

    def test_without_threshold_heartbeat_reports_stage_age_and_no_stop(self) -> None:
        progress = self.run_root / "progress.txt"
        code = f"import time\nopen({str(progress)!r}, 'w').write('stage-1')\ntime.sleep(3.2)\n"
        self.run_root.mkdir(parents=True)
        result = self.observe(python_command(code), progress_file=progress)
        events = read_events(self.run_root)
        terminal = self.assert_single_terminal(events)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(terminal["terminalReason"], "completed")
        ages = [
            item["stageAgeSeconds"] for item in events if item["event"] == "heartbeat" and "stageAgeSeconds" in item
        ]
        self.assertTrue(ages)
        self.assertGreaterEqual(max(ages), 1)
        self.assertTrue(all(item.get("status") == "stage-1" for item in events if "stageAgeSeconds" in item))

    def test_free_text_progress_is_not_copied_into_heartbeat(self) -> None:
        progress = self.run_root / "progress.txt"
        code = f"import time\nopen({str(progress)!r}, 'w').write('Customer data: secret value')\ntime.sleep(1.6)\n"
        self.run_root.mkdir(parents=True)
        self.observe(python_command(code), progress_file=progress)
        text = (self.run_root / OBSERVATION_FILE).read_text(encoding="utf-8")
        self.assertNotIn("secret value", text)
        self.assertIn('"status":"unreported"', text.replace(" ", ""))

    def test_general_timeout_applies_only_before_first_progress(self) -> None:
        result = self.observe(python_command("import time; time.sleep(60)"), timeout_seconds=1.0)
        terminal = self.assert_single_terminal(read_events(self.run_root))
        self.assertEqual(result.exit_code, EXIT_TIMEOUT)
        self.assertEqual(terminal["terminalReason"], "timeout")

        progress = self.root / "progress-2.txt"
        code = f"import time\nopen({str(progress)!r}, 'w').write('stage-1')\ntime.sleep(2.2)\n"
        self.run_root = self.root / "run-2"
        result = self.observe(python_command(code), progress_file=progress, timeout_seconds=1.0)
        self.assertEqual(result.exit_code, 0)

    def test_on_stop_hook_runs_before_termination(self) -> None:
        progress = self.run_root / "progress.txt"
        code = f"import time\nopen({str(progress)!r}, 'w').write('stage')\ntime.sleep(60)\n"
        self.run_root.mkdir(parents=True)
        reasons: list[str] = []
        result = self.observe(
            python_command(code), progress_file=progress, stall_timeout_seconds=1.0, on_stop=reasons.append
        )
        self.assertEqual(result.exit_code, EXIT_STALLED)
        self.assertEqual(reasons, ["stalled"])

    def test_terminal_extra_is_merged_and_invalid_extra_fails(self) -> None:
        extra = self.run_root / TERMINAL_EXTRA_FILE
        code = f"open({str(extra)!r}, 'w').write('{{\"terminalReason\":\"operator-stop\"}}')"
        result = self.observe(python_command(code))
        self.assertEqual(result.terminal_reason, "operator-stop")
        self.assertEqual(self.assert_single_terminal(read_events(self.run_root))["terminalReason"], "operator-stop")

        self.run_root = self.root / "run-2"
        extra = self.run_root / TERMINAL_EXTRA_FILE
        code = f"open({str(extra)!r}, 'w').write('{{\"event\":\"completed\"}}')"
        result = self.observe(python_command(code))
        self.assertEqual(result.exit_code, 70)
        self.assertEqual(result.terminal_reason, "invalid-terminal-observation-extra")

    def test_exception_inside_observer_still_writes_one_terminal(self) -> None:
        def broken(_pid: int) -> None:
            raise RuntimeError("hook failure")

        with self.assertRaises(RuntimeError):
            self.observe(python_command("import time; time.sleep(30)"), on_started=broken)
        self.assert_single_terminal(read_events(self.run_root))

    def test_summary_section_is_derived_from_observation(self) -> None:
        self.observe(python_command("raise SystemExit(5)"))
        summary = build_observation_summary(self.run_root)
        assert summary is not None
        self.assertEqual(summary["terminalEvent"], "failed")
        self.assertEqual(summary["exitCode"], 5)
        path = publish_observation_summary(self.run_root, {"capability": {"id": "test-capability"}})
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["observation"]["terminalReason"], "command-exit")
        self.assertEqual(payload["artifacts"]["observation_jsonl"], str(self.run_root / OBSERVATION_FILE))


class LaunchIdentityTests(unittest.TestCase):
    def test_platform_binary_pid_is_recorded_by_observer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            env, on_started = launch_identity(run_root, ["/opt/platform/1cv8", "ENTERPRISE"])
            self.assertEqual(env, {})
            assert on_started is not None
            on_started(4242)
            self.assertEqual((run_root / "process.pid").read_text(encoding="ascii").strip(), "4242")

    def test_wrapper_receives_pid_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            env, on_started = launch_identity(run_root, ["scripts/adapters/direct-platform.sh", "1cv8"])
            self.assertIsNone(on_started)
            self.assertEqual(env["ONEC_DIRECT_PLATFORM_COMMAND_PID_FILE"], str(run_root / "process.pid"))


class IntervalTests(unittest.TestCase):
    def test_interval_must_be_bounded_integer(self) -> None:
        from scripts.python.runtime_errors import CommandError
        from scripts.python.runtime_observation import interval_from_env

        with mock.patch.dict(os.environ, {"ONEC_OBSERVATION_INTERVAL_SECONDS": "31"}):
            with self.assertRaises(CommandError):
                interval_from_env()
        with mock.patch.dict(os.environ, {"ONEC_OBSERVATION_INTERVAL_SECONDS": "5"}):
            self.assertEqual(interval_from_env(), 5.0)


if __name__ == "__main__":
    unittest.main()
