from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts.python.runtime import build_ibcmd_dump_command, prepare_standard_capability_command
from scripts.python.runtime_cluster import (
    build_rac_create_command,
    cluster_registration_failure_reason,
    parse_rac_records,
    register_infobase_in_cluster,
)
from scripts.python.runtime_errors import CommandError
from scripts.python.runtime_options import (
    CapabilityOptions,
    require_unsupported_override,
    split_capability_options,
    unsupported_override_allowed,
)
from scripts.python.runtime_process import ProcessResult
from scripts.python.runtime_profiles import RuntimeProfile

FILE_IBCMD = {
    "runtimeMode": "file-infobase",
    "serverAccess": {"mode": "data-dir", "dataDir": "/var/tmp/fixture-data"},
    "fileInfobase": {"databasePath": "/var/tmp/fixture-db"},
    "auth": {"mode": "none"},
}

DBMS_IBCMD = {
    "runtimeMode": "dbms-infobase",
    "serverAccess": {"mode": "data-dir", "dataDir": "/var/tmp/fixture-data"},
    "locale": "en_US",
    "auth": {"user": "ib-user", "passwordEnv": "FIXTURE_IB_PASSWORD"},
    "dbmsInfobase": {
        "kind": "PostgreSQL",
        "server": "localhost",
        "name": "fixture_db",
        "user": "db-user",
        "passwordEnv": "FIXTURE_DB_PASSWORD",
    },
}


def make_profile(
    ibcmd: dict[str, Any],
    capabilities: dict[str, Any] | None = None,
    **extra: Any,
) -> RuntimeProfile:
    payload: dict[str, Any] = {
        "schemaVersion": 3,
        "profileName": "fixture",
        "runnerAdapter": "direct-platform",
        "platform": {"binaryPath": "/opt/fixture/1cv8", "ibcmdPath": "/opt/fixture/ibcmd"},
        "infobase": {"mode": "file", "filePath": "/var/tmp/fixture-ib", "auth": {"mode": "none"}},
        "ibcmd": ibcmd,
        "capabilities": capabilities or {},
        **extra,
    }
    return RuntimeProfile(path=Path("fixture.json"), payload=payload, name="fixture", runner_adapter="direct-platform")


def cluster_profile(**overrides: Any) -> RuntimeProfile:
    extra: dict[str, Any] = {
        "cluster": {"ras": "localhost:1545"},
        "clusterAdmin": {"user": "admin", "passwordEnv": "FIXTURE_CLUSTER_PASSWORD"},
    }
    extra.update(overrides)
    profile = make_profile(DBMS_IBCMD, {"createIb": {"driver": "ibcmd", "registerInCluster": True}}, **extra)
    profile.payload["infobase"] = {"mode": "client-server", "server": "localhost", "ref": "fixture_ib"}
    profile.payload["platform"]["racPath"] = "/opt/fixture/rac"
    return profile


class CapabilityOptionsTests(unittest.TestCase):
    def test_split_takes_only_options_of_the_capability(self) -> None:
        options, rest = split_capability_options("dump-src", ["--output-dir", "out", "--info-only", "--dry-run"])
        self.assertEqual((options.output_dir, options.info_only), ("out", True))
        self.assertEqual(rest, ["--dry-run"])
        options, rest = split_capability_options("doctor", ["--override-unsupported-profile"])
        self.assertFalse(options.override_unsupported)
        self.assertEqual(rest, ["--override-unsupported-profile"])

    def test_split_requires_option_values(self) -> None:
        with self.assertRaises(CommandError):
            split_capability_options("load-src", ["--source-dir"])

    def test_override_requires_policy_listing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "env").mkdir()
            (root / "automation" / "context").mkdir(parents=True)
            listed = root / "env" / "scratch.json"
            other = root / "env" / "shared.json"
            policy = {"unsupportedOverride": {"loadSrc": {"allowedProfiles": ["env/scratch.json"]}}}
            (root / "automation" / "context" / "runtime-profile-policy.json").write_text(
                json.dumps(policy), encoding="utf-8"
            )
            self.assertTrue(unsupported_override_allowed("loadSrc", listed, root))
            self.assertFalse(unsupported_override_allowed("loadSrc", other, root))
            self.assertFalse(unsupported_override_allowed("dumpSrc", listed, root))

    def test_override_requires_reason_files_and_run_root(self) -> None:
        profile_path = Path("env/scratch.json")
        cases = [
            ("dump-src", "reason", ["A.xml"], "run"),
            ("load-src", None, ["A.xml"], "run"),
            ("load-src", "reason", [], "run"),
            ("load-src", "reason", ["A.xml"], ""),
        ]
        for capability_id, reason, files, run_root in cases:
            with self.subTest(capability=capability_id, reason=reason, files=files), self.assertRaises(CommandError):
                require_unsupported_override(
                    capability_id, "loadSrc", profile_path, reason=reason, selected_files=files, run_root_input=run_root
                )


class DumpCommandTests(unittest.TestCase):
    def test_full_dump_uses_sync_over_existing_dump(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            profile = make_profile(FILE_IBCMD)
            command, _ = build_ibcmd_dump_command(profile, CapabilityOptions(output_dir=raw), dry_run=True)
            self.assertNotIn("--sync", command)
            self.assertEqual(command[-1], str(Path(raw).resolve()))
            (Path(raw) / "ConfigDumpInfo.xml").write_text("<x/>", encoding="utf-8")
            command, _ = build_ibcmd_dump_command(profile, CapabilityOptions(output_dir=raw), dry_run=True)
            self.assertEqual(command[-2], "--sync")

    def test_info_only_writes_to_out(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            options = CapabilityOptions(output_dir=raw, info_only=True)
            command, _ = build_ibcmd_dump_command(make_profile(FILE_IBCMD), options, dry_run=True)
        self.assertEqual(command[1:4], ["config", "export", "info"])
        self.assertEqual(command[-1], f"--out={Path(raw).resolve()}")

    def test_source_file_is_passed_and_conflicts_with_info_only(self) -> None:
        profile = make_profile(FILE_IBCMD, {"dumpSrc": {"driver": "ibcmd", "sourceFile": "/var/tmp/fixture.cf"}})
        with tempfile.TemporaryDirectory() as raw:
            command, _ = build_ibcmd_dump_command(profile, CapabilityOptions(output_dir=raw), dry_run=True)
            self.assertIn("--file=/var/tmp/fixture.cf", command)
            with self.assertRaises(CommandError):
                build_ibcmd_dump_command(profile, CapabilityOptions(output_dir=raw, info_only=True), dry_run=True)

    def test_ibcmd_auth_none_adds_no_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            command, _ = build_ibcmd_dump_command(
                make_profile(FILE_IBCMD), CapabilityOptions(output_dir=raw), dry_run=True
            )
        self.assertFalse(any(arg.startswith(("--user", "--password")) for arg in command))


class VendorCfTests(unittest.TestCase):
    def test_vendor_cf_update_runs_designer_with_batch_keys(self) -> None:
        profile = make_profile(FILE_IBCMD, {"updateDb": {"driver": "ibcmd"}})
        with tempfile.TemporaryDirectory() as raw:
            vendor_cf = Path(raw) / "vendor.cf"
            vendor_cf.write_bytes(b"cf")
            prepared = prepare_standard_capability_command(
                profile,
                "update-db",
                "Update DB",
                "direct-platform",
                [],
                dry_run=True,
                options=CapabilityOptions(vendor_cf=str(vendor_cf)),
                run_root_input=raw,
            )
        self.assertEqual(prepared.driver, "designer")
        command = prepared.command
        self.assertLess(command.index("/DisableStartupDialogs"), command.index("/UpdateCfg"))
        self.assertEqual(command[-1], "/UpdateDBCfg")
        self.assertTrue(prepared.context["vendor_cf"]["designer_out_log"].endswith("designer-out.log"))

    def test_vendor_cf_requires_run_root(self) -> None:
        profile = make_profile(FILE_IBCMD, {"updateDb": {"driver": "ibcmd"}})
        with tempfile.TemporaryDirectory() as raw:
            vendor_cf = Path(raw) / "vendor.cf"
            vendor_cf.write_bytes(b"cf")
            with self.assertRaises(CommandError):
                prepare_standard_capability_command(
                    profile,
                    "update-db",
                    "Update DB",
                    "direct-platform",
                    [],
                    dry_run=True,
                    options=CapabilityOptions(vendor_cf=str(vendor_cf)),
                )


class ClusterRegistrationTests(unittest.TestCase):
    def test_parse_rac_records_splits_blank_lines(self) -> None:
        output = 'cluster : aaa\nname    : "Main cluster"\n\ncluster : bbb\nname    : other\n'
        self.assertEqual(
            parse_rac_records(output),
            [{"cluster": "aaa", "name": "Main cluster"}, {"cluster": "bbb", "name": "other"}],
        )

    def test_registration_requires_client_server_topology(self) -> None:
        self.assertEqual(cluster_registration_failure_reason(cluster_profile()), "")
        profile = cluster_profile()
        profile.payload["infobase"]["mode"] = "file"
        self.assertIn("client-server", cluster_registration_failure_reason(profile))
        profile = cluster_profile(clusterAdmin={"user": "admin"})
        self.assertIn("passwordEnv", cluster_registration_failure_reason(profile))

    def test_rac_create_command_denies_scheduled_jobs(self) -> None:
        command = build_rac_create_command(cluster_profile(), "cluster-uuid", dry_run=True)
        self.assertIn("--scheduled-jobs-deny=on", command)
        self.assertIn("--dbms=PostgreSQL", command)
        self.assertIn("--locale=en_US", command)
        self.assertIn("--cluster-user=admin", command)

    def test_register_refuses_existing_infobase(self) -> None:
        responses = iter(
            [
                ProcessResult([], 0, "cluster : cluster-uuid\nname : main\n", ""),
                ProcessResult([], 0, "infobase : ib-uuid\nname : fixture_ib\n", ""),
            ]
        )
        env = {"FIXTURE_CLUSTER_PASSWORD": "secret"}
        with tempfile.TemporaryDirectory() as raw, patch.dict("os.environ", env):
            stdout_log, stderr_log = Path(raw) / "out.log", Path(raw) / "err.log"
            with patch("scripts.python.runtime_cluster.run_process", side_effect=lambda *a, **k: next(responses)):
                code, section = register_infobase_in_cluster(cluster_profile(), stdout_log, stderr_log)
        self.assertEqual(code, 1)
        self.assertEqual(section["status"], "failed")
        self.assertIn("existing infobase", section["reason"])

    def test_register_creates_infobase(self) -> None:
        responses = iter(
            [
                ProcessResult([], 0, "cluster : cluster-uuid\n", ""),
                ProcessResult([], 0, "infobase : other-uuid\nname : other\n", ""),
                ProcessResult([], 0, "infobase : new-uuid\n", ""),
            ]
        )
        env = {"FIXTURE_CLUSTER_PASSWORD": "secret", "FIXTURE_DB_PASSWORD": "db-secret"}
        with tempfile.TemporaryDirectory() as raw, patch.dict("os.environ", env):
            stdout_log, stderr_log = Path(raw) / "out.log", Path(raw) / "err.log"
            with patch("scripts.python.runtime_cluster.run_process", side_effect=lambda *a, **k: next(responses)):
                code, section = register_infobase_in_cluster(cluster_profile(), stdout_log, stderr_log)
        self.assertEqual(code, 0)
        self.assertEqual(section["infobase_uuid"], "new-uuid")
        self.assertTrue(section["scheduled_jobs_denied"])


if __name__ == "__main__":
    unittest.main()
