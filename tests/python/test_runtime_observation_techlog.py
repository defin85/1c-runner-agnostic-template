from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.python.runtime_observation import OBSERVATION_FILE, ObservationRequest, run_observed
from scripts.python.runtime_techlog import (
    CONFIG_MARKER,
    FORBIDDEN_EVENTS,
    RESTORE_FILE,
    STATE_FILE,
    TechlogPlan,
    TechlogSession,
    _lock_paths,
    bounded_logcfg,
    cursor_read,
    plan_from_env,
    restore_from_record,
)

ORIGINAL = b'\xef\xbb\xbf<?xml version="1.0"?>\r\n<config xmlns="http://v8.1c.ru/v8/tech-log">\r\n</config>\r\n\x00tail'
RECORD = "00:01.000001-2500,EXCP,0,process=1cv8,level=ERROR,Descr='fixture failure'\n"


class TechlogTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.config = self.root / "conf" / "logcfg.xml"
        self.log_root = self.root / "techlog"
        self.run_root = self.root / "run"

    def tearDown(self) -> None:
        _, owner = _lock_paths(self.config.resolve())
        owner.unlink(missing_ok=True)
        self._tmp.cleanup()

    def plan(self) -> TechlogPlan:
        return TechlogPlan(config_path=self.config.resolve(), log_root=self.log_root, processes=["1cv8", "1cv8c"])

    def observe(self, code: str):
        return run_observed(
            ObservationRequest(
                capability="test-capability",
                target="fixture",
                run_root=self.run_root,
                command=[sys.executable, "-c", code],
                techlog=self.plan(),
                interval_seconds=1.0,
            )
        )


class BoundedConfigTests(unittest.TestCase):
    def test_bounded_config_has_no_forbidden_events(self) -> None:
        text = bounded_logcfg(Path("/var/log/onec-techlog")).decode("utf-8").lower()
        self.assertIn(CONFIG_MARKER, text)
        for event in FORBIDDEN_EVENTS:
            self.assertNotIn(f'value="{event.lower()}"', text)
        self.assertIn('history="1"', text)

    def test_plan_requires_config_path(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(plan_from_env(Path("run")))

    def test_client_server_filters_rphost_by_infobase(self) -> None:
        with mock.patch.dict(os.environ, {"TECHLOG_CONFIG_PATH": "logcfg.xml"}, clear=True):
            plan = plan_from_env(Path("run"), infobase_mode="client-server", infobase_ref="demo")
        assert plan is not None
        self.assertEqual(plan.processes, ["rphost"])
        self.assertEqual(plan.process_name, "demo")
        self.assertIsNone(plan.process_id_file)


class TechlogRestoreTests(TechlogTestCase):
    def test_original_config_is_restored_byte_for_byte(self) -> None:
        self.config.parent.mkdir(parents=True)
        self.config.write_bytes(ORIGINAL)
        seen = self.root / "seen.xml"
        code = f"import shutil; shutil.copyfile({str(self.config)!r}, {str(seen)!r})"
        result = self.observe(code)
        self.assertEqual(result.exit_code, 0)
        self.assertIn(CONFIG_MARKER.encode("utf-8"), seen.read_bytes())
        self.assertEqual(self.config.read_bytes(), ORIGINAL)
        self.assertTrue(json.loads((self.run_root / RESTORE_FILE).read_text(encoding="utf-8"))["restored"])
        self.assertTrue(result.extra["technologicalLog"]["restored"])

    def test_absent_config_is_removed_again(self) -> None:
        result = self.observe("raise SystemExit(2)")
        self.assertEqual(result.exit_code, 2)
        self.assertFalse(self.config.exists())

    def test_config_is_restored_when_observer_raises(self) -> None:
        self.config.parent.mkdir(parents=True)
        self.config.write_bytes(ORIGINAL)

        def broken(_pid: int) -> None:
            raise RuntimeError("hook failure")

        with self.assertRaises(RuntimeError):
            run_observed(
                ObservationRequest(
                    capability="test-capability",
                    target="fixture",
                    run_root=self.run_root,
                    command=[sys.executable, "-c", "import time; time.sleep(30)"],
                    techlog=self.plan(),
                    interval_seconds=1.0,
                    term_grace_seconds=2.0,
                    on_started=broken,
                )
            )
        self.assertEqual(self.config.read_bytes(), ORIGINAL)

    def test_restore_command_recovers_after_killed_observer(self) -> None:
        self.config.parent.mkdir(parents=True)
        self.config.write_bytes(ORIGINAL)
        session = TechlogSession(self.plan(), self.run_root)
        self.assertEqual(session.start()["status"], "enabled")
        self.assertNotEqual(self.config.read_bytes(), ORIGINAL)
        restore_from_record(self.run_root / RESTORE_FILE)
        self.assertEqual(self.config.read_bytes(), ORIGINAL)
        restore_from_record(self.run_root / RESTORE_FILE)
        self.assertEqual(self.config.read_bytes(), ORIGINAL)

    def test_dead_owner_is_restored_before_next_run(self) -> None:
        self.config.parent.mkdir(parents=True)
        self.config.write_bytes(ORIGINAL)
        first = TechlogSession(self.plan(), self.root / "first-run")
        first.start()
        _, owner = _lock_paths(self.config.resolve())
        record = json.loads(owner.read_text(encoding="utf-8"))
        record["pid"] = 999_999_999
        owner.write_text(json.dumps(record), encoding="utf-8")
        result = self.observe("pass")
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(self.config.read_bytes(), ORIGINAL)


class TechlogCursorTests(TechlogTestCase):
    def test_events_of_the_run_reach_observation_and_cursor(self) -> None:
        stale = self.log_root / "1cv8_100" / "26010100.log"
        stale.parent.mkdir(parents=True)
        stale.write_text("00:00.000001-1,EXCP,0,process=1cv8,level=ERROR,Descr='before run'\n", encoding="utf-8")
        current = self.log_root / "1cv8_200" / "26010101.log"
        code = (
            "import os, time\n"
            f"os.makedirs({str(current.parent)!r}, exist_ok=True)\n"
            f"open({str(current)!r}, 'w').write({RECORD!r})\n"
            "time.sleep(1.5)\n"
        )
        result = self.observe(code)
        self.assertEqual(result.exit_code, 0)
        lines = (self.run_root / OBSERVATION_FILE).read_text(encoding="utf-8").splitlines()
        tech = [json.loads(line) for line in lines if '"tech-event"' in line]
        self.assertEqual(len(tech), 1)
        self.assertEqual(tech[0]["techEvent"], "EXCP")
        self.assertNotIn("fixture failure", "\n".join(lines))

        with current.open("a", encoding="utf-8") as stream:
            stream.write("00:09.000001-1,EXCP,0,process=1cv8,level=ERROR,Descr='after run'\n")
        whole = cursor_read(self.run_root / STATE_FILE, whole_run=True)
        self.assertEqual([item["description"] for item in whole], ["fixture failure"])

    def test_unavailable_config_degrades_without_failing(self) -> None:
        self.config.parent.mkdir(parents=True)
        self.config.parent.chmod(0o500)
        try:
            if os.access(self.config.parent, os.W_OK):
                self.skipTest("directory permissions are not enforced for this user")
            result = self.observe("pass")
        finally:
            self.config.parent.chmod(0o700)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.extra.get("degradedReason"), "technological-log-config-access")
        state = json.loads((self.run_root / STATE_FILE).read_text(encoding="utf-8"))
        self.assertFalse(state["available"])


if __name__ == "__main__":
    unittest.main()
