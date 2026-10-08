from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from collections import namedtuple
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts.python import artifact_storage as storage
from scripts.python.cli import main as cli_main

ROOT = Path(__file__).resolve().parents[2]
DiskUsage = namedtuple("DiskUsage", "total used free")
HAS_BLOCKS = hasattr(os.stat_result, "st_blocks")


def _can_symlink(base: Path) -> bool:
    probe = base / "symlink-probe"
    try:
        probe.symlink_to(base, target_is_directory=True)
    except (OSError, NotImplementedError):
        return False
    probe.unlink()
    return True


class ArtifactStorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._temp.name).resolve()
        self.root = self.tmp / "shared-artifacts"
        environment = {
            "ONEC_ARTIFACT_ROOT": str(self.root),
            "ONEC_ARTIFACT_MIN_FREE_BYTES": "0",
            "ONEC_ARTIFACT_MIN_FREE_INODES": "0",
            "ONEC_ARTIFACT_RETENTION_DAYS": "0",
        }
        self._env = patch.dict(os.environ, environment)
        self._env.start()
        for name in ("ONEC_ARTIFACT_MAX_BYTES", "ONEC_ARTIFACT_MAX_INODES", "ONEC_ARTIFACT_DB_PATH"):
            os.environ.pop(name, None)

    def tearDown(self) -> None:
        self._env.stop()
        for path in self.tmp.rglob("*"):
            if path.is_file() and not path.is_symlink():
                path.chmod(0o644)
        self._temp.cleanup()

    def passport(self, run_id: str) -> Path:
        return self.root / "runs" / f"{run_id}.json"


class StorageRootTests(ArtifactStorageTestCase):
    def test_default_root_is_repo_named_sibling_of_checkout(self) -> None:
        os.environ.pop("ONEC_ARTIFACT_ROOT")
        repo = self.tmp / "my-project"
        repo.mkdir()
        with patch.object(storage, "project_root", return_value=repo):
            self.assertEqual(storage.storage_root(), self.tmp / "my-project-artifacts")

    def test_root_inside_checkout_relative_or_filesystem_root_is_rejected(self) -> None:
        for value, message in (
            (str(ROOT / "artifacts"), "outside the repository"),
            ("relative/artifacts", "absolute"),
            (Path(ROOT.anchor).as_posix(), "outside the repository"),
        ):
            with self.subTest(value=value), patch.dict(os.environ, {"ONEC_ARTIFACT_ROOT": value}):
                with self.assertRaisesRegex(ValueError, message):
                    storage.storage_root()

    def test_symlinked_root_is_rejected(self) -> None:
        if not _can_symlink(self.tmp):
            self.skipTest("symlinks are not available")
        actual = self.tmp / "actual"
        actual.mkdir()
        link = self.tmp / "linked"
        link.symlink_to(actual, target_is_directory=True)
        with patch.dict(os.environ, {"ONEC_ARTIFACT_ROOT": str(link / "artifacts")}):
            with self.assertRaisesRegex(ValueError, "symlink"):
                storage.storage_root()


class BudgetAndReserveTests(ArtifactStorageTestCase):
    def test_byte_budget_refuses_before_passport_or_run_root_exists(self) -> None:
        run_root = self.tmp / "run"
        with patch.dict(os.environ, {"ONEC_ARTIFACT_MAX_BYTES": "1000"}):
            with self.assertRaisesRegex(OSError, "artifact byte budget exceeded"):
                storage.begin_run("build", run_root, reserve_bytes=5000)
        self.assertFalse(run_root.exists())
        self.assertEqual(list((self.root / "runs").glob("*.json")) if (self.root / "runs").exists() else [], [])

    def test_active_reserve_counts_until_run_finishes(self) -> None:
        with patch.dict(os.environ, {"ONEC_ARTIFACT_MAX_BYTES": "100000"}):
            first = storage.begin_run("first", self.tmp / "first", reserve_bytes=60000)
            self.assertEqual(storage.status()["reserved_bytes"], 60000)
            with self.assertRaisesRegex(OSError, "artifact byte budget exceeded"):
                storage.begin_run("second", self.tmp / "second", reserve_bytes=60000)
            storage.finish_run(first, "failed")
            self.assertEqual(storage.status()["reserved_bytes"], 0)
            storage.begin_run("second", self.tmp / "second", reserve_bytes=60000)

    def test_free_space_reserve_is_checked(self) -> None:
        with (
            patch.dict(os.environ, {"ONEC_ARTIFACT_MIN_FREE_BYTES": "100"}),
            patch.object(storage, "free_space", return_value=(1000, 10_000)),
        ):
            storage.begin_run("small", self.tmp / "small", reserve_bytes=100)
            with self.assertRaisesRegex(OSError, "insufficient free bytes"):
                storage.begin_run("large", self.tmp / "large", reserve_bytes=850)

    def test_inode_budget_applies_on_linux(self) -> None:
        with (
            patch.object(storage, "WINDOWS", False),
            patch.dict(os.environ, {"ONEC_ARTIFACT_MAX_INODES": "1"}),
        ):
            with self.assertRaisesRegex(OSError, "artifact inode budget exceeded"):
                storage.begin_run("inodes", self.tmp / "inodes")

    def test_capacity_reservations_are_serialized_across_threads(self) -> None:
        outcomes: list[str] = []
        barrier = threading.Barrier(2)

        def start(index: int) -> None:
            barrier.wait()
            try:
                outcomes.append(storage.begin_run(f"job-{index}", self.tmp / f"run-{index}", reserve_bytes=60000))
            except OSError:
                outcomes.append("rejected")

        with patch.dict(os.environ, {"ONEC_ARTIFACT_MAX_BYTES": "100000"}):
            threads = [threading.Thread(target=start, args=(index,)) for index in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(outcomes.count("rejected"), 1)
            self.assertEqual(storage.status()["reserved_bytes"], 60000)
        self.assertFalse((self.root / ".storage.lock").exists())


class WindowsSimulationTests(ArtifactStorageTestCase):
    def test_disk_usage_without_inode_limits(self) -> None:
        calls: list[Path] = []

        def disk_usage(path: Any) -> DiskUsage:
            calls.append(Path(path))
            return DiskUsage(10_000, 5_000, 5_000)

        with (
            patch.object(storage, "WINDOWS", True),
            patch.object(storage.shutil, "disk_usage", side_effect=disk_usage),
            patch.object(storage.os, "statvfs", side_effect=AssertionError("statvfs is not used"), create=True),
            patch.dict(
                os.environ,
                {"ONEC_ARTIFACT_MAX_INODES": "0", "ONEC_ARTIFACT_MIN_FREE_INODES": "999999999"},
            ),
        ):
            self.assertEqual(storage.free_space(self.tmp), (5_000, None))
            run_id = storage.begin_run("windows", self.tmp / "run", reserve_bytes=100)
            self.assertFalse(storage.status()["inode_limits"])
            with patch.dict(os.environ, {"ONEC_ARTIFACT_MIN_FREE_BYTES": "4900"}):
                with self.assertRaisesRegex(OSError, "insufficient free bytes"):
                    storage.begin_run("too-large", self.tmp / "other", reserve_bytes=200)
        self.assertTrue(calls)
        self.assertTrue(self.passport(run_id).is_file())

    def test_allocated_bytes_fall_back_to_size_without_blocks(self) -> None:
        sample = self.tmp / "sample.bin"
        sample.write_bytes(b"x" * 1234)
        real = sample.stat()
        values = [getattr(real, name) for name in ("st_mode", "st_ino", "st_dev", "st_nlink", "st_uid", "st_gid")]
        fake = os.stat_result((*values, 1234, int(real.st_atime), int(real.st_mtime), int(real.st_ctime)))
        self.assertEqual(storage._allocated_bytes(fake), 1234)  # pyright: ignore[reportPrivateUsage]


class LockTests(ArtifactStorageTestCase):
    def test_stale_lock_of_dead_owner_is_recovered(self) -> None:
        self.root.mkdir(parents=True)
        (self.root / ".storage.lock").write_text(json.dumps({"pid": 2**22 + 12345, "operation": "x"}), "utf-8")
        with patch.dict(os.environ, {"ONEC_ARTIFACT_LOCK_TIMEOUT_SECONDS": "2"}):
            storage.begin_run("after-crash", self.tmp / "run")
        self.assertFalse((self.root / ".storage.lock").exists())

    def test_live_lock_times_out_without_creating_run(self) -> None:
        self.root.mkdir(parents=True)
        (self.root / ".storage.lock").write_text(json.dumps({"pid": os.getpid(), "operation": "x"}), "utf-8")
        with patch.dict(os.environ, {"ONEC_ARTIFACT_LOCK_TIMEOUT_SECONDS": "0"}):
            with self.assertRaisesRegex(Exception, "resource lock timeout"):
                storage.begin_run("blocked", self.tmp / "run")
        self.assertFalse((self.tmp / "run").exists())


class ScratchTests(ArtifactStorageTestCase):
    def test_success_removes_only_declared_scratch_and_keeps_passport(self) -> None:
        run_root = self.tmp / "run"
        scratch = run_root / "scratch"
        scratch.mkdir(parents=True)
        (scratch / "large.tmp").write_bytes(b"temporary")
        readonly = scratch / "readonly.tmp"
        readonly.write_bytes(b"readonly")
        readonly.chmod(0o444)
        kept = run_root / "result.json"
        kept.write_text("{}", encoding="utf-8")
        run_id = storage.begin_run("build", run_root, scratch=[scratch])

        storage.finish_run(run_id, "success")

        self.assertFalse(scratch.exists())
        self.assertTrue(kept.exists())
        self.assertEqual(json.loads(self.passport(run_id).read_text(encoding="utf-8"))["status"], "success")
        self.assertEqual(storage.prune(apply=True)["removed"], [])

    def test_pinned_success_keeps_scratch(self) -> None:
        run_root = self.tmp / "pinned"
        scratch = run_root / "temp"
        scratch.mkdir(parents=True)
        run_id = storage.begin_run("accepted", run_root, scratch=[scratch])
        storage.finish_run(run_id, "success", pinned=True)
        self.assertTrue(scratch.exists())
        self.assertTrue(json.loads(self.passport(run_id).read_text(encoding="utf-8"))["pinned"])

    def test_prune_removes_only_expired_failed_scratch(self) -> None:
        active_root = self.tmp / "active"
        active_scratch = active_root / "temp"
        active_scratch.mkdir(parents=True)
        storage.begin_run("active", active_root, scratch=[active_scratch])

        failed_root = self.tmp / "failed"
        failed_scratch = failed_root / "temp"
        failed_scratch.mkdir(parents=True)
        (failed_scratch / "x").write_text("keep", encoding="utf-8")
        failed = storage.begin_run("failed", failed_root, scratch=[failed_scratch])
        storage.finish_run(failed, "failed")

        legacy = self.tmp / "legacy"
        legacy.mkdir()
        (legacy / "keep").write_text("legacy", encoding="utf-8")

        dry_run = storage.prune()
        self.assertEqual([item["path"] for item in dry_run["eligible"]], [str(failed_scratch)])
        self.assertTrue(failed_scratch.exists())
        result = storage.prune(apply=True)
        self.assertEqual(result["protected"], 1)
        self.assertEqual(result["removed"], [str(failed_scratch)])
        self.assertTrue(active_scratch.exists())
        self.assertTrue((legacy / "keep").exists())

    def test_scratch_outside_run_root_and_nested_active_run_are_rejected(self) -> None:
        run_root = self.tmp / "run"
        run_root.mkdir()
        with self.assertRaisesRegex(ValueError, "child of run root"):
            storage.begin_run("traversal", run_root, scratch=[Path("../outside")])
        child_root = run_root / "child-run"
        child_root.mkdir()
        child = storage.begin_run("child", child_root)
        parent = storage.begin_run("parent", run_root, scratch=[child_root])
        with self.assertRaisesRegex(ValueError, "overlaps protected run"):
            storage.finish_run(parent, "success")
        self.assertTrue(child_root.exists())
        storage.finish_run(child, "failed")

    def test_scratch_symlink_escape_is_rejected(self) -> None:
        if not _can_symlink(self.tmp):
            self.skipTest("symlinks are not available")
        run_root = self.tmp / "run"
        run_root.mkdir()
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "keep").write_text("safe", encoding="utf-8")
        run_id = storage.begin_run("unsafe", run_root)
        (run_root / "escape").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            storage.finish_run(run_id, "success", scratch=[run_root / "escape"])
        self.assertEqual((outside / "keep").read_text(encoding="utf-8"), "safe")

    def test_invalid_run_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "run id"):
            storage.set_pinned("../../outside", True)


class CacheAndUsageTests(ArtifactStorageTestCase):
    def test_cache_reuses_verified_read_only_copy_and_repairs_corruption(self) -> None:
        source = self.tmp / "input.cf"
        source.write_bytes(b"immutable payload")
        duplicate = self.tmp / "duplicate.cf"
        duplicate.write_bytes(b"immutable payload")
        cached = storage.cache_file(source)
        self.assertEqual(storage.cache_file(duplicate), cached)
        source.write_bytes(b"mutated source")
        self.assertEqual(cached.suffix, ".cf")
        self.assertEqual(cached.read_bytes(), b"immutable payload")
        self.assertEqual(cached.stat().st_mode & 0o222, 0)
        cached.chmod(0o644)
        cached.write_bytes(b"corrupt")
        cached.chmod(0o444)
        self.assertEqual(storage.cache_file(duplicate).read_bytes(), b"immutable payload")

    @unittest.skipUnless(HAS_BLOCKS, "st_blocks is not available")
    def test_usage_counts_allocated_blocks_for_sparse_files(self) -> None:
        sparse = self.tmp / "sparse"
        with sparse.open("wb") as stream:
            stream.truncate(1024 * 1024)
        used_bytes, inodes = storage._tree_usage(sparse)  # pyright: ignore[reportPrivateUsage]
        self.assertEqual(used_bytes, getattr(sparse.stat(), "st_blocks", 0) * 512)
        self.assertEqual(inodes, 1)


class CliTests(ArtifactStorageTestCase):
    def test_cli_round_trip_and_budget_error(self) -> None:
        run_root = self.tmp / "cli-run"
        with patch("sys.stdout") as stdout:
            self.assertEqual(cli_main(["artifact-storage", "begin", "--kind", "cli", "--run-root", str(run_root)]), 0)
        run_id = "".join(call.args[0] for call in stdout.write.call_args_list).strip()
        self.assertRegex(run_id, r"^[0-9a-f]{32}$")
        self.assertEqual(cli_main(["artifact-storage", "finish", "--id", run_id, "--status", "success"]), 0)
        with (
            patch.dict(os.environ, {"ONEC_ARTIFACT_MAX_BYTES": "1"}),
            patch("sys.stderr") as stderr,
        ):
            code = cli_main(["artifact-storage", "begin", "--kind", "cli", "--run-root", str(self.tmp / "x")])
        self.assertEqual(code, 1)
        self.assertIn("artifact byte budget exceeded", "".join(c.args[0] for c in stderr.write.call_args_list))

    def test_wrappers_are_thin_and_paired(self) -> None:
        shell = (ROOT / "scripts" / "artifact-storage").read_text(encoding="utf-8")
        powershell = (ROOT / "scripts" / "artifact-storage.ps1").read_text(encoding="utf-8")
        self.assertIn('python/run-python.sh" "artifact-storage" "$@"', shell)
        self.assertIn('python\\run-python.ps1") "artifact-storage" @args', powershell)
        if sys.platform != "win32":
            self.assertTrue(os.access(ROOT / "scripts" / "artifact-storage", os.X_OK))
        self.assertIsNotNone(shutil.which("bash") or sys.platform == "win32")


if __name__ == "__main__":
    unittest.main()
