from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.python.runtime import PreparedCommand, execute_prepared_capability_command
from scripts.python.runtime_process import ProcessResult
from scripts.python.runtime_profiles import RuntimeProfile


class RemoteTransportTests(unittest.TestCase):
    def test_structured_response_preserves_capability_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = RuntimeProfile(root / "profile.json", {}, "remote", "remote-windows")
            prepared = PreparedCommand("dump-src", "Dump", "remote-windows", command_source="builder", command=["1cv8.exe", "DESIGNER"])
            with patch("scripts.python.runtime.run_transport_process", return_value=ProcessResult([], 0, json.dumps({"exitCode": 7, "stdout": "out", "stderr": "err"}), "")) as runner:
                result = execute_prepared_capability_command(prepared, profile, root, root / "stdout.log", root / "stderr.log")
            self.assertEqual(result, 7)
            request = json.loads(runner.call_args.kwargs["input_text"])
            self.assertEqual(request["argv"], ["1cv8.exe", "DESIGNER"])
            self.assertEqual((root / "stderr.log").read_text(encoding="utf-8"), "err")

    def test_transport_failure_is_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = RuntimeProfile(root / "profile.json", {}, "remote", "remote-windows")
            prepared = PreparedCommand("dump-src", "Dump", "remote-windows", command_source="builder", command=["1cv8.exe"])
            with patch("scripts.python.runtime.run_transport_process", return_value=ProcessResult([], 2, "", "offline")):
                result = execute_prepared_capability_command(prepared, profile, root, root / "stdout.log", root / "stderr.log")
            self.assertEqual(result, 70)
            self.assertIn("transport failure", (root / "stderr.log").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
