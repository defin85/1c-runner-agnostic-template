from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from scripts.python.runtime import build_doctor_capability_drivers_json, build_ibcmd_driver_context
from scripts.python.runtime_profiles import RuntimeProfile


def make_profile(ibcmd: dict[str, Any], capabilities: dict[str, Any]) -> RuntimeProfile:
    payload: dict[str, Any] = {
        "schemaVersion": 3,
        "profileName": "fixture",
        "runnerAdapter": "direct-platform",
        "platform": {"binaryPath": "/opt/fixture/1cv8", "ibcmdPath": "/opt/fixture/ibcmd"},
        "infobase": {"mode": "file", "filePath": "/var/tmp/fixture-ib", "auth": {"mode": "os"}},
        "ibcmd": ibcmd,
        "capabilities": capabilities,
    }
    return RuntimeProfile(path=Path("fixture.json"), payload=payload, name="fixture", runner_adapter="direct-platform")


FILE_IBCMD = {
    "runtimeMode": "file-infobase",
    "serverAccess": {"mode": "data-dir", "dataDir": "/var/tmp/fixture-data"},
    "fileInfobase": {"databasePath": "/var/tmp/fixture-db"},
}

DBMS_IBCMD = {
    "runtimeMode": "dbms-infobase",
    "serverAccess": {"mode": "data-dir", "dataDir": "/var/tmp/fixture-data"},
    "auth": {"user": "ib-user", "passwordEnv": "FIXTURE_IB_PASSWORD"},
    "dbmsInfobase": {
        "kind": "PostgreSQL",
        "server": "localhost",
        "name": "fixture_db",
        "user": "db-user",
        "passwordEnv": "FIXTURE_DB_PASSWORD",
    },
}


class IbcmdDriverContextTests(unittest.TestCase):
    def test_file_infobase_context_has_runtime_mode_and_topology(self) -> None:
        context = build_ibcmd_driver_context(make_profile(FILE_IBCMD, {}))
        self.assertEqual(context["runtime_mode"], "file-infobase")
        self.assertEqual(context["server_access"], {"mode": "data-dir", "data_dir": "/var/tmp/fixture-data"})
        self.assertFalse(context["partial_import"])
        self.assertEqual(context["topology"], {"kind": "file-infobase", "database_path": "/var/tmp/fixture-db"})

    def test_dbms_context_reports_password_presence_not_value(self) -> None:
        context = build_ibcmd_driver_context(make_profile(DBMS_IBCMD, {}), partial_import=True)
        self.assertTrue(context["partial_import"])
        dbms = context["topology"]["dbms"]
        self.assertEqual(dbms["kind"], "PostgreSQL")
        self.assertTrue(dbms["password_configured"])
        self.assertNotIn("FIXTURE_DB_PASSWORD", repr(context))

    def test_doctor_reports_ibcmd_context_only_for_ibcmd_driver(self) -> None:
        profile = make_profile(
            FILE_IBCMD,
            {
                "createIb": {"driver": "designer"},
                "dumpSrc": {"driver": "designer"},
                "loadSrc": {"driver": "ibcmd"},
                "updateDb": {"driver": "designer"},
            },
        )
        drivers = build_doctor_capability_drivers_json(profile, "direct-platform")
        self.assertEqual(drivers["load-src"]["driver"], "ibcmd")
        self.assertEqual(drivers["load-src"]["context"]["runtime_mode"], "file-infobase")
        self.assertEqual(drivers["create-ib"]["context"], {})


if __name__ == "__main__":
    unittest.main()
