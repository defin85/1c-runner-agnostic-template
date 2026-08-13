from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path

from scripts.python.runtime_atomic import atomic_read_json, atomic_write_json
from scripts.python.runtime_result import prepare_run_artifacts, publish_interrupted_summary


class RuntimeAtomicTests(unittest.TestCase):
    def test_concurrent_reader_never_observes_partial_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "registry.json"
            atomic_write_json(path, {"generation": 0, "payload": "x" * 1000})
            failures: list[Exception] = []
            done = threading.Event()

            def writer() -> None:
                try:
                    for generation in range(1, 100):
                        atomic_write_json(path, {"generation": generation, "payload": "я" * 1000})
                except Exception as error:
                    failures.append(error)
                finally:
                    done.set()

            thread = threading.Thread(target=writer)
            thread.start()
            while not done.is_set():
                try:
                    atomic_read_json(path)
                except Exception as error:
                    failures.append(error)
                    break
            thread.join()
            self.assertEqual(failures, [])

    def test_interruption_runs_cleanup_before_atomic_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts = prepare_run_artifacts(temp_dir)
            cleanup_calls: list[str] = []
            publish_interrupted_summary(
                artifacts,
                {"capability": {"id": "test"}},
                reason="operator cancellation",
                cleanup=lambda: cleanup_calls.append("owned-process"),
            )
            payload = json.loads(artifacts.summary_path.read_text(encoding="utf-8"))
            self.assertEqual(cleanup_calls, ["owned-process"])
            self.assertEqual(payload["status"], "interrupted")
            self.assertEqual(payload["exit_code"], 130)


if __name__ == "__main__":
    unittest.main()
