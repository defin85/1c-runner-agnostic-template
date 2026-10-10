"""Server wrappers of the optional customer-site-operations module, run against fake site tools.

The wrappers are extensionless Python 3.7 scripts in the module blueprint. These tests run them as
subprocesses with fake `rac`, `psql` and friends that only log their arguments, so no site is touched.
Set SITE_SERVER_PYTHON (or put python3.7 on PATH) to also run the read-only checks on Python 3.7.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="server wrappers run on Linux site servers (fcntl, rac, psql)"
)

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "automation" / "optional" / "customer-site-operations" / "files" / "infra" / "site" / "server"
EXAMPLE = SERVER.parent / "site.example.json"
CLUSTER_UUID = "00000000-0000-4000-8000-000000000000"
MAIN_UUID = "00000000-0000-4000-8000-000000000001"
COPY_UUID = "00000000-0000-4000-8000-000000000002"
HOST = socket.gethostname().split(".")[0]
# Syntax and standard-library names that need Python 3.8 or newer.
PY38_NAMES = (
    "missing_ok=",
    "shlex.join",
    "removeprefix",
    "removesuffix",
    "cached_property",
    "math.prod",
    "math.isqrt",
    "functools.cache(",
    "zoneinfo",
    "graphlib",
    "tomllib",
    "is_relative_to",
    "dirs_exist_ok",
)

FAKE_RAC = r"""#!/usr/bin/env python3
import json, os, sys

state_path = os.environ["FAKE_RAC_STATE"]
with open(os.environ["FAKE_RAC_LOG"], "a") as log:
    log.write(json.dumps(sys.argv[2:]) + "\n")
with open(state_path) as stream:
    state = json.load(stream)
mode, action = sys.argv[2], sys.argv[3]
options = dict(a.split("=", 1) for a in sys.argv[4:] if a.startswith("--") and "=" in a)
if (mode, action) == ("infobase", "summary"):
    for name, item in state["bases"].items():
        print("infobase : " + item["uuid"])
        print("name     : " + name)
        print()
elif (mode, action) == ("infobase", "info"):
    name = [n for n, i in state["bases"].items() if i["uuid"] == options["--infobase"]][0]
    item = state["bases"][name]
    for key, value in (("infobase", item["uuid"]), ("name", name), ("dbms", "PostgreSQL"),
                       ("db-server", state["db_host"]), ("db-name", name), ("db-user", "onec"),
                       ("sessions-deny", item["sessions"]), ("scheduled-jobs-deny", item["jobs"]),
                       ("license-distribution", item["license"])):
        print(key + " : " + value)
elif (mode, action) == ("infobase", "update"):
    name = [n for n, i in state["bases"].items() if i["uuid"] == options["--infobase"]][0]
    for option, key in (("--sessions-deny", "sessions"), ("--scheduled-jobs-deny", "jobs"),
                        ("--license-distribution", "license")):
        if option in options:
            state["bases"][name][key] = options[option]
elif (mode, action) == ("infobase", "drop"):
    name = [n for n, i in state["bases"].items() if i["uuid"] == options["--infobase"]][0]
    del state["bases"][name]
elif mode in ("session", "connection", "server", "process"):
    pass
with open(state_path, "w") as stream:
    json.dump(state, stream)
"""

FAKE_LOGGER = """#!/bin/sh
printf '%s\\n' "$0 $*" >> "$FAKE_TOOL_LOG"
exit 3
"""


def server_python() -> str | None:
    """Python 3.7 interpreter for the compatibility run, if one is available."""
    configured = os.environ.get("SITE_SERVER_PYTHON")
    if configured:
        return configured
    return shutil.which("python3.7")


def write_exec(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


class SiteFixture:
    """A temporary site: profile, fake rac and fake PostgreSQL tools that only log their arguments."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.rac_log = root / "rac.log"
        self.tool_log = root / "tools.log"
        self.state = root / "rac-state.json"
        bin_dir = root / "bin"
        bin_dir.mkdir()
        self.rac = write_exec(bin_dir / "rac", FAKE_RAC)
        for name in ("psql", "pg_dump", "pg_restore", "ibcmd"):
            write_exec(bin_dir / name, FAKE_LOGGER)
        self.data = root / "pgdata"
        (self.data / "pg_wal").mkdir(parents=True)
        self.profile_path = root / "site.json"
        self.profile: dict[str, Any] = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        self.profile.update(
            app_host=HOST,
            db_host=HOST,
            db_password_file="",
            pg_bin=str(bin_dir),
            db_data_directory=str(self.data),
        )
        self.profile["platform"].update(rac=str(self.rac), ibcmd=str(bin_dir / "ibcmd"))
        self.profile["cluster"].update(user="", password_file="")
        self.profile["infobases"] = {
            "app_main": {},
            "app_reference": {},
            "app_main_copy": {"auth_base": "app_main", "disposable": True},
        }
        self.profile["golden"].update(app_storage=str(root / "golden-app"), db_storage=str(root / "golden-db"))
        self.profile["archive"]["storage"] = str(root / "archive")
        self.save_profile()
        self.rac_state(
            {
                "app_main": {"uuid": MAIN_UUID, "sessions": "off", "jobs": "off", "license": "allow"},
                "app_main_copy": {"uuid": COPY_UUID, "sessions": "off", "jobs": "on", "license": "allow"},
            }
        )

    def save_profile(self) -> None:
        self.profile_path.write_text(json.dumps(self.profile), encoding="utf-8")

    def rac_state(self, bases: dict[str, dict[str, str]]) -> None:
        self.state.write_text(json.dumps({"db_host": HOST, "bases": bases}), encoding="utf-8")

    def bases(self) -> dict[str, dict[str, str]]:
        return json.loads(self.state.read_text(encoding="utf-8"))["bases"]

    def rac_calls(self) -> list[list[str]]:
        if not self.rac_log.exists():
            return []
        return [json.loads(line) for line in self.rac_log.read_text(encoding="utf-8").splitlines()]

    def tool_calls(self) -> list[str]:
        return self.tool_log.read_text(encoding="utf-8").splitlines() if self.tool_log.exists() else []

    def run(self, script: str, *args: str, python: str | None = None) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env.update(FAKE_RAC_LOG=str(self.rac_log), FAKE_RAC_STATE=str(self.state), FAKE_TOOL_LOG=str(self.tool_log))
        env["PATH"] = str(self.rac.parent) + os.pathsep + env.get("PATH", "")
        return subprocess.run(
            [python or sys.executable, str(SERVER / script), *args, "--profile", str(self.profile_path)],
            capture_output=True,
            text=True,
            env=env,
            cwd=self.root,
            timeout=60,
            check=False,
        )


class SiteServerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.site = SiteFixture(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def assertRefused(self, result: subprocess.CompletedProcess[str], text: str) -> None:
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("REFUSED:", result.stderr)
        self.assertIn(text, result.stderr)


class SiteRacTest(SiteServerTestCase):
    def test_unlisted_base_is_refused_before_any_cluster_call(self) -> None:
        for command in ("lock", "unlock", "jobs-on", "jobs-off", "license-on"):
            with self.subTest(command=command):
                result = self.site.run("site-rac", command, "foreign_base")
                self.assertRefused(result, "not listed in the site profile")
        self.assertEqual(self.site.rac_calls(), [])

    def test_unregister_requires_disposable_listed_copy(self) -> None:
        result = self.site.run("site-rac", "unregister", "app_main", "--confirm", "UNREGISTER app_main")
        self.assertRefused(result, "not marked disposable")
        self.assertEqual(self.site.rac_calls(), [])

    def test_jobs_off_then_on_changes_only_the_job_flag(self) -> None:
        result = self.site.run("site-rac", "jobs-off", "app_main")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual((output["jobs"], output["sessions"]), ("on", "off"))
        self.assertEqual(self.site.bases()["app_main"]["jobs"], "on")
        updates = [call for call in self.site.rac_calls() if call[:2] == ["infobase", "update"]]
        self.assertEqual(len(updates), 1)
        self.assertIn("--scheduled-jobs-deny=on", updates[0])
        result = self.site.run("site-rac", "jobs-on", "app_main")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.site.bases()["app_main"]["jobs"], "off")

    def test_lock_keeps_scheduled_jobs_flag(self) -> None:
        result = self.site.run("site-rac", "lock", "app_main")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.site.bases()["app_main"]["sessions"], "on")
        self.assertEqual(self.site.bases()["app_main"]["jobs"], "off")

    def test_unregister_drops_only_the_confirmed_copy(self) -> None:
        result = self.site.run("site-rac", "unregister", "app_main_copy", "--confirm", "UNREGISTER app_main_copy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("app_main_copy", self.site.bases())
        self.assertIn("app_main", self.site.bases())

    def test_read_only_info_on_listed_base(self) -> None:
        result = self.site.run("site-rac", "info", "app_main")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(output["infobase"], MAIN_UUID)
        self.assertEqual(output["license-distribution"], "allow")


@unittest.skipUnless(server_python(), "Python 3.7 is not available (set SITE_SERVER_PYTHON)")
class SitePython37Test(SiteServerTestCase):
    def test_read_only_commands_run_on_python37(self) -> None:
        python = server_python()
        version = subprocess.run([str(python), "--version"], capture_output=True, text=True, check=True)
        self.assertIn("3.7", version.stdout + version.stderr)
        for args in (("list",), ("info", "app_main"), ("sessions", "app_main")):
            with self.subTest(args=args):
                result = self.site.run("site-rac", *args, python=python)
                self.assertEqual(result.returncode, 0, result.stderr)
        result = self.site.run("site-rac", "lock", "foreign_base", python=python)
        self.assertRefused(result, "not listed in the site profile")
        # Every other wrapper must at least load on Python 3.7 and refuse before touching the site.
        refusals = (
            ("site-ibcmd", "config-info", "--base", "foreign_base", "--output", "/nonexistent/x"),
            ("site-dt-restore", "--base", "foreign_base", "--dt", "/nonexistent/x.dt", "--output", "/nonexistent/r"),
            ("site-golden-db", "discard-copy", "--database", "foreign_base", "--confirm", "DROP foreign_base"),
            ("site-golden-app", "prepare", "--for", "capture", "--confirm", "BLOCK nothing"),
            ("site-db-archive", "plan", "--database", "postgres"),
            ("site-license-request", "check"),
            ("site-techlog-control", "status"),
            ("site-v8users-recovery", "status", "--database", "app_main", "--host", "/x", "--work", "/nonexistent/w"),
        )
        for args in refusals:
            with self.subTest(args=args[0]):
                result = self.site.run(*args, python=python)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("REFUSED:", result.stderr)
        self.assertEqual(self.site.tool_calls(), [])


class SiteDatabaseWrappersTest(SiteServerTestCase):
    def test_dt_restore_refuses_unlisted_and_non_disposable_targets(self) -> None:
        common = ("--dt", "/nonexistent/x.dt", "--output", str(self.site.root / "run"))
        result = self.site.run("site-dt-restore", "--base", "foreign_base", *common)
        self.assertRefused(result, "not listed in the site profile")
        result = self.site.run("site-dt-restore", "--base", "app_main", "--create", *common)
        self.assertRefused(result, "not marked disposable")
        self.assertEqual(self.site.rac_calls(), [])
        self.assertEqual(self.site.tool_calls(), [])

    def test_ibcmd_refuses_unlisted_base(self) -> None:
        result = self.site.run("site-ibcmd", "config-info", "--base", "foreign_base", "--output", "/nonexistent/x")
        self.assertRefused(result, "not listed in the site profile")
        self.assertEqual(self.site.tool_calls(), [])

    def test_discard_copy_refuses_golden_and_unlisted_bases_before_dbms(self) -> None:
        for database, reason in (("app_main", "not marked disposable"), ("foreign_base", "not listed")):
            with self.subTest(database=database):
                result = self.site.run("site-golden-db", "discard-copy", "--database", database, "--confirm", "DROP x")
                self.assertRefused(result, reason)
        self.assertEqual(self.site.tool_calls(), [])

    def test_archive_refuses_profile_infobases_and_unlisted_databases(self) -> None:
        for database in ("app_main", "app_main_copy", "postgres", "not_in_allowlist"):
            with self.subTest(database=database):
                result = self.site.run("site-db-archive", "plan", "--database", database)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("REFUSED:", result.stderr)
        self.assertEqual(self.site.tool_calls(), [])

    def test_license_request_never_prints_secret_values(self) -> None:
        result = self.site.run("site-license-request", "check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("REFUSED:", result.stderr)


class SiteV8usersRecoveryTest(SiteServerTestCase):
    def enable(self, databases: list[str]) -> None:
        self.site.profile["v8users_recovery"] = {"enabled": True, "databases": databases}
        self.site.save_profile()

    def run_recovery(self, action: str, work: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return self.site.run(
            "site-v8users-recovery",
            action,
            "--database",
            "app_main_copy",
            "--host",
            "/nonexistent",
            "--work",
            str(work),
            "--confirm",
            "app_main_copy",
            *extra,
        )

    def test_disabled_option_refuses_every_stage(self) -> None:
        for action in ("status", "backup", "hide", "restore", "verify"):
            with self.subTest(action=action):
                result = self.run_recovery(action, self.site.root / "work")
                self.assertRefused(result, "v8users recovery is disabled")
        self.assertEqual(self.site.tool_calls(), [])

    def test_unlisted_database_is_refused(self) -> None:
        self.enable(["app_reference"])
        result = self.run_recovery("backup", self.site.root / "work")
        self.assertRefused(result, "not listed in v8users_recovery.databases")
        self.assertEqual(self.site.tool_calls(), [])

    def test_hide_without_backup_refuses_before_any_psql_call(self) -> None:
        self.enable(["app_main_copy"])
        work = self.site.root / "work"
        work.mkdir(mode=0o700)
        result = self.run_recovery("hide", work)
        self.assertRefused(result, "No verified backup")
        self.assertEqual(self.site.tool_calls(), [])


class SiteTechlogTest(SiteServerTestCase):
    def setUp(self) -> None:
        super().setUp()
        root = self.site.root
        (root / "conf").mkdir()
        self.site.profile["techlog"].update(
            config_dir=str(root / "conf"),
            log_dir=str(root / "log" / "lic"),
            locks_dir=str(root / "log" / "locks"),
            state_dir=str(root / "state"),
            min_free_mib=1,
        )
        self.site.save_profile()

    def techlog(self, *args: str) -> str:
        result = self.site.run("site-techlog-control", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_start_locks_report_and_stop_restore_previous_state(self) -> None:
        config = self.site.root / "conf" / "logcfg.xml"
        self.assertIn("techlog_state=started", self.techlog("start"))
        self.assertIn('value="lic"', config.read_text(encoding="utf-8"))
        self.assertIn("techlog_locks=started previous=active", self.techlog("locks-start"))
        self.assertIn('value="tlock"', config.read_text(encoding="utf-8"))
        locks = self.site.root / "log" / "locks" / "rphost_1"
        locks.mkdir(parents=True)
        (locks / "26010112.log").write_text(
            "12:00.000001-2500000,TLOCK,5,Regions=AccumRg1.Balance,Locks='AccumRg1.Balance Exclusive Fld1=1'\n"
            "12:00.000002-1500000,TLOCK,5,Regions=AccumRg1.Balance,Locks='AccumRg1.Balance Exclusive Fld1=2'\n"
            "12:00.000003-10,TTIMEOUT,5,WaitConnections=7\n",
            encoding="utf-8",
        )
        report = self.techlog("locks-report", "--minutes", "5")
        self.assertIn("events TLOCK=2 TTIMEOUT=1", report)
        self.assertIn("region=AccumRg1.Balance waits=2 wait_s=4.0", report)
        self.assertIn("restored=active", self.techlog("locks-stop"))
        self.assertNotIn('value="tlock"', config.read_text(encoding="utf-8"))
        self.assertIn("techlog_state=stopped", self.techlog("stop"))
        self.assertFalse(config.exists())
        self.assertTrue((self.site.root / "log" / "locks").is_dir(), "logs are preserved")

    def test_foreign_config_is_a_conflict(self) -> None:
        config = self.site.root / "conf" / "logcfg.xml"
        config.write_text("<config/>", encoding="utf-8")
        result = self.site.run("site-techlog-control", "start")
        self.assertRefused(result, "conflict")
        self.assertEqual(config.read_text(encoding="utf-8"), "<config/>")
        self.assertIn("techlog_state=conflict", self.techlog("status"))


class SitePython37SourceTest(unittest.TestCase):
    def test_every_server_file_parses_as_python37_and_avoids_newer_names(self) -> None:
        files = sorted(SERVER.glob("site-*"))
        self.assertGreaterEqual(len(files), 10)
        for path in files:
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                ast.parse(source, filename=path.name, feature_version=(3, 7))
                for name in PY38_NAMES:
                    self.assertNotIn(name, source, f"{name} needs Python 3.8+")
                if path.name != "site-common":
                    self.assertTrue(source.startswith("#!/usr/bin/env python3\n"))
                    self.assertTrue(path.stat().st_mode & stat.S_IXUSR, "wrapper must be executable")
                for line in source.splitlines():
                    stripped = line.strip()
                    if stripped.startswith(("import ", "from ")):
                        module = stripped.split()[1].split(".")[0]
                        self.assertIn(module, sys.stdlib_module_names, f"{module} is not in the standard library")


def postgres_bin() -> Path | None:
    for candidate in sorted(Path("/usr/lib/postgresql").glob("*/bin"), reverse=True):
        if (candidate / "initdb").is_file() and (candidate / "pg_ctl").is_file():
            return candidate
    return None


@unittest.skipUnless(postgres_bin() and os.geteuid() != 0, "Local PostgreSQL server binaries are not available")
class SiteV8usersRecoveryPostgresTest(unittest.TestCase):
    """Full backup -> hide -> restore -> verify cycle on a throwaway local PostgreSQL cluster."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.bin = postgres_bin()
        assert self.bin is not None
        self.socket = root / "socket"
        self.socket.mkdir()
        self.data = root / "data"
        subprocess.run(
            [str(self.bin / "initdb"), "-D", str(self.data), "-U", "postgres", "--auth=trust", "-E", "UTF8"],
            capture_output=True,
            check=True,
        )
        self.port = "54" + str(30 + os.getpid() % 60)
        options = f"-k {self.socket} -c listen_addresses='' -p {self.port}"
        subprocess.run(
            [str(self.bin / "pg_ctl"), "-D", str(self.data), "-o", options, "-w", "-l", str(root / "pg.log"), "start"],
            capture_output=True,
            check=True,
        )
        self.addCleanup(self.stop)
        self.psql("postgres", "CREATE DATABASE app_main_copy;")
        self.psql(
            "app_main_copy",
            textwrap.dedent(
                """
                CREATE TABLE public.v8users (id bytea, name text, data bytea);
                INSERT INTO public.v8users VALUES ('\\x01', 'Administrator', '\\x0a0b'), ('\\x02', 'User', NULL);
                CREATE TABLE public.params (filename varchar(128), creation timestamp, modified timestamp,
                  attributes int, datasize bigint, binarydata bytea);
                INSERT INTO public.params VALUES ('users.usr', now(), now(), 0, 2, '\\x0102'),
                  ('other.cfg', now(), now(), 0, 1, '\\x03');
                """
            ),
        )
        profile = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        profile.update(pg_bin=str(self.bin), db_port=int(self.port), db_password_file="")
        profile["infobases"] = {"app_main_copy": {"disposable": True}}
        profile["v8users_recovery"] = {"enabled": True, "databases": ["app_main_copy"]}
        self.profile = root / "site.json"
        self.profile.write_text(json.dumps(profile), encoding="utf-8")
        self.work = root / "work"

    def stop(self) -> None:
        subprocess.run([str(self.bin) + "/pg_ctl", "-D", str(self.data), "-m", "fast", "stop"], capture_output=True)
        self._tmp.cleanup()

    def psql(self, database: str, sql: str) -> str:
        argv = [str(self.bin) + "/psql", "-X", "-qAt", "-h", str(self.socket), "-p", self.port, "-U", "postgres"]
        result = subprocess.run(
            argv + ["-d", database, "-v", "ON_ERROR_STOP=1"],
            input=sql,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def stage(self, action: str, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SERVER / "site-v8users-recovery"), action, "--database", "app_main_copy"]
            + ["--host", str(self.socket), "--work", str(self.work), "--confirm", "app_main_copy"]
            + ["--profile", str(self.profile), *extra],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    def test_cycle_restores_the_original_users_list(self) -> None:
        before = self.psql("app_main_copy", "SELECT string_agg(name, ',' ORDER BY name) FROM public.v8users;")
        result = self.stage("hide")
        self.assertIn("No verified backup", result.stderr)
        result = self.stage("backup", "--scope", "tables")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BACKUP_VERIFIED", result.stdout)
        result = self.stage("hide")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.psql("app_main_copy", "SELECT count(*) FROM public.v8users;"), "0")
        self.psql("app_main_copy", "SELECT 1;")
        result = self.stage("restore")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.stage("verify")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BACKUP_RESTORE_VERIFIED", result.stdout)
        after = self.psql("app_main_copy", "SELECT string_agg(name, ',' ORDER BY name) FROM public.v8users;")
        self.assertEqual(before, after)
        self.assertEqual(self.psql("app_main_copy", "SELECT to_regclass('public.v8users_site_recovery');"), "")
        # The empty table created by hide is preserved for inspection, never dropped by the tool.
        self.assertEqual(self.psql("app_main_copy", "SELECT count(*) FROM public.v8users_site_created;"), "0")


if __name__ == "__main__":
    unittest.main()
