"""KD rules cycle: `state.json` (schema 2), `result.json` and stage readiness."""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from scripts.migration.kd_cycle_common import (
    RESULT_SCHEMA_VERSION,
    STAGES,
    STATE_SCHEMA_VERSION,
    CycleError,
    atomic_json,
    canonical_json_sha256,
    read_json,
    sha256,
)
from scripts.migration.kd_cycle_validation import scenario_file

READY = frozenset({"passed", "reused"})
INPUTS_CHANGED = "inputs changed; use a new --run-root and reset"


def input_digests(profile_path: Path, scenario: Mapping[str, Any]) -> dict[str, str]:
    """Digests of everything that defines the run: profile, scenario, matrix, expected result, structure pins."""
    digests = {
        "profileSha256": sha256(profile_path),
        "scenarioSha256": sha256(Path(str(scenario["_path"]))),
        "matrixSha256": sha256(scenario_file(scenario, "matrix")),
        "sourceStructureSha256": str(scenario["inputs"]["sourceStructureSha256"]),
        "targetStructureSha256": str(scenario["inputs"]["targetStructureSha256"]),
    }
    if scenario.get("expected"):
        digests["expectedSha256"] = sha256(scenario_file(scenario, "expected"))
    return digests


def _entry() -> dict[str, Any]:
    return {"status": "pending", "attempts": 0, "evidence": {}}


def initial_state(
    profile_path: Path, scenario: Mapping[str, Any], profile: Mapping[str, Any], digests: Mapping[str, str]
) -> dict[str, Any]:
    return {
        "schemaVersion": STATE_SCHEMA_VERSION,
        "runId": str(uuid.uuid4()),
        "profileId": profile["profileId"],
        "scenarioId": scenario["scenarioId"],
        "control": {"profile": str(profile_path), "scenario": str(scenario["_path"])},
        "inputs": dict(digests),
        "inputsSha256": canonical_json_sha256(dict(digests)),
        "stages": {name: _entry() for name in STAGES},
        "nodes": {str(node["name"]): {**_entry(), "inputSha256": None, "history": []} for node in scenario["nodes"]},
        "generations": {},
        "release": None,
        "failure": None,
    }


def load_or_init(
    run_root: Path, profile_path: Path, scenario: Mapping[str, Any], profile: Mapping[str, Any]
) -> dict[str, Any]:
    """Return the saved state of this run-root, refusing when the run inputs changed since it started."""
    digests = input_digests(profile_path, scenario)
    path = run_root / "state.json"
    if not path.is_file():
        return initial_state(profile_path, scenario, profile, digests)
    state = read_json(path)
    if state.get("schemaVersion") != STATE_SCHEMA_VERSION:
        raise CycleError(f"state.json schemaVersion must be {STATE_SCHEMA_VERSION}: {path}")
    if state.get("profileId") != profile["profileId"] or state.get("inputsSha256") != canonical_json_sha256(digests):
        changed = sorted(key for key, value in digests.items() if state.get("inputs", {}).get(key) != value)
        detail = f" ({', '.join(changed)})" if changed else ""
        raise CycleError(INPUTS_CHANGED + detail)
    return state


def save(run_root: Path, state: Mapping[str, Any]) -> None:
    atomic_json(run_root / "state.json", state)


def entry(state: Mapping[str, Any], name: str) -> dict[str, Any]:
    if name in state["stages"]:
        return state["stages"][name]
    if name in state["nodes"]:
        return state["nodes"][name]
    raise CycleError(f"unknown stage or node: {name}")


def require_ready(state: Mapping[str, Any], name: str, dependencies: Iterable[str]) -> None:
    """Refuse to start `name` while a direct dependency is not passed; never run the dependency itself."""
    missing = [dep for dep in dependencies if entry(state, dep)["status"] not in READY]
    if missing:
        raise CycleError(f"dependency not ready for {name}: {', '.join(missing)}")


def refuse_after_failure(state: Mapping[str, Any], name: str, *, retry_allowed: bool = False) -> None:
    failure = state.get("failure")
    if not failure:
        return
    if retry_allowed and failure.get("stage") == name:
        return
    raise CycleError(
        f"run-root failed at {failure.get('stage')}: {failure.get('reason')}; use a new --run-root and reset"
    )


def invalidate_after_reset(state: dict[str, Any]) -> None:
    """A new generation of the bases makes every result that touched the old one pending again."""
    for name in ("load", "run", "verify"):
        state["stages"][name] = _entry()
    for node in state["nodes"].values():
        node.update(status="pending", evidence={}, inputSha256=None)


def result_payload(state: Mapping[str, Any], status: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "status": status,
        "runId": state["runId"],
        "profileId": state["profileId"],
        "scenarioId": state["scenarioId"],
        "generations": state.get("generations", {}),
        "stages": {name: item["status"] for name, item in state["stages"].items()},
        "nodes": {name: item["status"] for name, item in state["nodes"].items()},
    }
    if state.get("release"):
        payload["release"] = state["release"]
    if state.get("failure"):
        payload["failedStage"] = state["failure"]["stage"]
        payload["reason"] = state["failure"]["reason"]
    payload.update(extra)
    return payload


def write_result(run_root: Path, state: Mapping[str, Any], status: str, **extra: Any) -> dict[str, Any]:
    payload = result_payload(state, status, **extra)
    atomic_json(run_root / "result.json", payload)
    return payload
