"""Fixture stage command for kd-rules-cycle tests: no 1C, no PostgreSQL.

It appends `<stage> <role>` to the log file, reports progress through the observation progress file and
writes the machine result the executor expects. `--mode` selects the behaviour:
`ok`, `fail` (exit 3), `stall` (report progress once, then hang), `slow` (succeed after `--seconds`).
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument("--mode", default="ok", choices=("ok", "fail", "stall", "slow"))
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    stage = os.environ.get("KD_RULES_CYCLE_STAGE", "?")
    role = os.environ.get("KD_RULES_CYCLE_ROLE", "?")
    with Path(args.log).open("a", encoding="utf-8") as stream:
        stream.write(f"{stage} {role}\n")
    progress = Path(os.environ["ONEC_OBSERVATION_PROGRESS_FILE"])
    progress.write_text(f"{stage}:{role}:started\n", encoding="utf-8")
    if args.mode == "fail":
        return 3
    if args.mode == "stall":
        time.sleep(3600)
    if args.mode == "slow":
        time.sleep(args.seconds)
    if args.output:
        Path(args.output).write_text("output\n", encoding="utf-8")
    result = os.environ.get("KD_RULES_CYCLE_RESULT_FILE")
    if result:
        Path(result).write_text(json.dumps({"status": "passed", "stage": stage, "role": role}) + "\n", encoding="utf-8")
    progress.write_text(f"{stage}:{role}:done\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
