"""Entry point of `scripts/migration/kd-rules-cycle`.

The outer process runs the executor under the shared observation adapter: it writes
`<run-root>/observation.jsonl` and follows `<run-root>/progress.txt`, where the executor names the
current stage. The inner process (`KD_RULES_CYCLE_INNER=1`) does the work; the outer one relays its
output and exit code.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TextIO

from scripts.migration.kd_cycle_cli import parse_args, run
from scripts.migration.kd_cycle_common import ROOT, CycleError
from scripts.migration.kd_cycle_validation import check_run_root, require_input_file
from scripts.python.runtime_errors import CommandError
from scripts.python.runtime_observation import ObservationRequest, run_observed

INNER_ENV = "KD_RULES_CYCLE_INNER"


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _relay(path: Path, offset: int, stream: TextIO) -> None:
    try:
        with path.open("rb") as source:
            source.seek(offset)
            text = source.read().decode("utf-8", errors="replace")
    except OSError:
        return
    if text:
        print(text, end="", file=stream)


def _observe(run_root: Path, argv: list[str]) -> int:
    run_root.mkdir(parents=True, exist_ok=True)
    stdout_log = run_root / "stdout.log"
    stderr_log = run_root / "stderr.log"
    offsets = (_size(stdout_log), _size(stderr_log))
    outcome = run_observed(
        ObservationRequest(
            capability="kd-rules-cycle",
            target="kd21",
            run_root=run_root,
            command=[sys.executable, "-m", "scripts.migration.kd_rules_cycle", *argv],
            stdout_log=stdout_log,
            stderr_log=stderr_log,
            cwd=ROOT,
            env={INNER_ENV: "1"},
            progress_file=run_root / "progress.txt",
        )
    )
    _relay(stdout_log, offsets[0], sys.stdout)
    _relay(stderr_log, offsets[1], sys.stderr)
    if outcome.signal == "SIGINT":
        raise KeyboardInterrupt
    return outcome.exit_code


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(arguments)
    try:
        if os.environ.get(INNER_ENV) == "1":
            return run(args)
        run_root = check_run_root(args.run_root)
        # Without the materialized module there is nothing to observe: fail before creating the run-root.
        require_input_file(args.profile, "profile")
        return _observe(run_root, arguments)
    except (CycleError, CommandError) as error:
        print(f"kd-rules-cycle: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
