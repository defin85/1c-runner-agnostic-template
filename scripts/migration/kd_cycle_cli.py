"""KD rules cycle: command line and stage execution.

Stages `doctor`, `reset`, `build`, `load`, `run`, `verify` run in dependency order on two expendable
bases (source and target). `build` calls the compiler core; `run build-rules` builds and publishes a
release without opening any base. Project application stages are scenario nodes started by `run <node>`.
"""

from __future__ import annotations

import argparse
import importlib
import os
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from scripts.migration import kd_cycle_state as state_store
from scripts.migration.kd_cycle_common import (
    BUILD_RULES,
    DEFAULT_PROFILE,
    DEFAULT_RESET_COMMAND,
    MODULE_HINT,
    ROLES,
    STAGE_DEPENDENCIES,
    STAGES,
    CycleError,
    atomic_json,
    canonical_json_sha256,
    path_sha256,
    profile_lock,
    project_path,
    publish_release,
    read_json,
    render_command,
    run_observed_stage,
    sha256,
    write_progress,
)
from scripts.migration.kd_cycle_validation import (
    check_expendable_targets,
    check_required_env,
    check_run_root,
    free_bytes,
    load_profile,
    load_scenario,
    require_input_file,
    runtime_profile_database,
    scenario_file,
)
from scripts.migration.kd_xml_compiler import ReleaseError, RuleProvider, TechnicalRules, compile_release
from scripts.migration.kd_xml_compiler.release import validate_matrix

COMMANDS = (*STAGES, "all")
RETRYABLE_AFTER_FAILURE = frozenset({"probe-and-reuse", "idempotent-retry"})


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="kd-rules-cycle",
        description="Build KD 2.01 rules and check them on two expendable bases.",
        epilog="Commands: doctor | reset | build | load | run [build-rules|<node>] | verify | all",
    )
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help=f"workbench profile (default {DEFAULT_PROFILE})")
    parser.add_argument("--scenario", default="", help="scenario.json or its directory (default technical-workbench)")
    parser.add_argument("--run-root", required=True, help="new absolute run directory outside the repository")
    parser.add_argument("--baseline-result", default="", help="result.json of the first generation (second run only)")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("name", nargs="?", default="", help="for run: build-rules or a scenario node")
    args = parser.parse_args(argv)
    if args.name and args.command != "run":
        parser.error("only `run` takes a name")
    return args


def _resolve_provider(scenario: Mapping[str, Any]) -> RuleProvider:
    reference = scenario.get("compiler", {}).get("rulesProvider")
    if not reference:
        return TechnicalRules()
    module_name, _, attribute = str(reference).partition(":")
    try:
        target = getattr(importlib.import_module(module_name), attribute)
    except (ImportError, AttributeError) as error:
        raise CycleError(f"scenario compiler.rulesProvider cannot be loaded: {reference}: {error}") from None
    return target() if isinstance(target, type) else target


class Cycle:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.run_root = check_run_root(args.run_root)
        self.profile_path = require_input_file(args.profile, "profile")
        self.profile = load_profile(self.profile_path)
        scenario_value = args.scenario or "migration/kd21/scenarios/technical-workbench/scenario.json"
        scenario_path = project_path(scenario_value)
        if not scenario_path.exists():
            raise CycleError(f"scenario not found: {scenario_path}; {MODULE_HINT}")
        self.scenario = load_scenario(scenario_path)
        self.nodes = {str(node["name"]): node for node in self.scenario["nodes"]}
        self.release_dir = self.run_root / "release"
        self.state: dict[str, Any] = {}

    # ----- bookkeeping -------------------------------------------------------------------------

    def save(self) -> None:
        state_store.save(self.run_root, self.state)

    def environment(self, stage: str, role: str) -> dict[str, str]:
        return {
            "KD_RULES_CYCLE_RUN_ID": str(self.state["runId"]),
            "KD_RULES_CYCLE_STAGE": stage,
            "KD_RULES_CYCLE_ROLE": role,
        }

    def execute(self, name: str, action: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        item = state_store.entry(self.state, name)
        item["attempts"] = int(item.get("attempts", 0)) + 1
        item["status"] = "running"
        self.save()
        write_progress(self.run_root / "progress.txt", f"stage:{name}")
        state_store.write_result(self.run_root, self.state, "in-progress", currentStage=name)
        try:
            evidence = action()
        except (CycleError, KeyboardInterrupt) as error:
            reason = str(error) if isinstance(error, CycleError) else "interrupted"
            item["status"] = "failed"
            # A failed node inside the `run` stage keeps its own name, so it can be retried.
            self.state["failure"] = self.state.get("failure") or {"stage": name, "reason": reason}
            self.save()
            state_store.write_result(self.run_root, self.state, "failed")
            raise
        item["status"] = "passed"
        item["evidence"] = evidence
        self.save()
        return evidence

    def stage_root(self, stage: str, role: str) -> Path:
        return self.run_root / "stages" / stage / role

    def workbase(self, role: str) -> Mapping[str, Any]:
        return next(item for item in self.profile["workbases"] if item["role"] == role)

    def reference(self, role: str) -> Mapping[str, Any]:
        return next(item for item in self.profile["references"] if item["role"] == role)

    def placeholders(self, stage: str, role: str) -> dict[str, str]:
        stage_root = self.stage_root(stage, role)
        values = {
            "runId": str(self.state["runId"]),
            "runRoot": str(self.run_root),
            "stageRoot": str(stage_root),
            "resultFile": str(stage_root / "result.json"),
            "progressFile": str(stage_root / "progress.txt"),
            "release": str(self.release_dir),
            "role": role,
        }
        if role in ROLES:
            workbase = self.workbase(role)
            values.update(
                database=str(workbase["database"]),
                target=str(workbase["target"]),
                runtimeProfile=str(project_path(str(workbase["runtimeProfile"]))),
                snapshot=str(project_path(str(self.reference(role)["snapshot"]))),
            )
        return values

    def reference_fingerprints(self) -> dict[str, Any]:
        fingerprints: dict[str, Any] = {}
        for item in self.profile["references"]:
            snapshot = project_path(str(item["snapshot"]))
            if not snapshot.is_file():
                raise CycleError(f"reference snapshot not found for {item['role']}: {snapshot}")
            fingerprints[str(item["role"])] = {
                "database": item["database"],
                "snapshot": str(snapshot),
                "snapshotBytes": snapshot.stat().st_size,
                "snapshotSha256": sha256(snapshot),
            }
        return fingerprints

    def generation_id(self) -> str:
        generations = self.state.get("generations") or {}
        return canonical_json_sha256({role: item.get("generationId") for role, item in sorted(generations.items())})

    # ----- stages ------------------------------------------------------------------------------

    def doctor(self) -> dict[str, Any]:
        targets = check_expendable_targets(self.profile)
        check_required_env(self.profile, os.environ)
        for role in ROLES:
            runtime_profile = project_path(str(self.workbase(role)["runtimeProfile"]))
            if not runtime_profile.is_file():
                raise CycleError(f"workbase {role} runtime profile not found: {runtime_profile}")
            database = runtime_profile_database(runtime_profile)
            if database is not None and database != targets[role]:
                raise CycleError(
                    f"workbase {role} runtime profile points to database {database}, profile expects {targets[role]}"
                )
        references = self.reference_fingerprints()
        for role, fingerprint in references.items():
            pinned = self.reference(role).get("snapshotSha256")
            if pinned and pinned != fingerprint["snapshotSha256"]:
                raise CycleError(f"reference snapshot SHA-256 mismatch for {role}: {fingerprint['snapshot']}")
        structures = {}
        for side in ROLES:
            path = project_path(str(self.scenario["inputs"][side + "Structure"]))
            if not path.is_file():
                raise CycleError(f"{side} metadata structure not found: {path}")
            if sha256(path) != self.scenario["inputs"][side + "StructureSha256"]:
                raise CycleError(f"KD structure SHA-256 mismatch: {path}")
            structures[side] = str(path)
        try:
            validate_matrix(read_json(scenario_file(self.scenario, "matrix")))
        except ReleaseError as error:
            raise CycleError(str(error)) from None
        commands = self.profile.get("commands", {})
        if "load" not in commands:
            raise CycleError(
                "profile commands.load is not set: declare the project command that loads the release "
                "into a workbase (docs/agent/kd21-rules-workbench-runbook.md)"
            )
        for key in ("reset", "load"):
            template = commands.get(key, list(DEFAULT_RESET_COMMAND) if key == "reset" else [])
            render_command(template, self.placeholders(key, "source"))
        free = free_bytes(self.run_root)
        minimum = int(self.profile["limits"].get("minFreeBytes", 0))
        if free < minimum:
            raise CycleError(f"not enough free space in run-root: {free} < {minimum}")
        before = self.run_root / "source-before.json"
        if not before.is_file():
            atomic_json(before, {"schemaVersion": 1, "references": references})
        return {"targets": targets, "freeBytes": free, "structures": structures, "references": references}

    def reset(self) -> dict[str, Any]:
        targets = check_expendable_targets(self.profile)
        template = self.profile.get("commands", {}).get("reset", list(DEFAULT_RESET_COMMAND))
        passports: dict[str, Any] = {}
        evidence: dict[str, Any] = {}
        for role in ROLES:
            command = render_command(template, self.placeholders("reset", role))
            evidence[role] = run_observed_stage(
                stage="reset",
                target=role,
                run_root=self.run_root,
                stage_root=self.stage_root("reset", role),
                command=command,
                environment=self.environment("reset", role),
                limits=self.profile["limits"],
                expect_result=False,
            )
            passports[role] = {
                "role": role,
                "database": targets[role],
                "generationId": str(uuid.uuid4()),
                "runId": self.state["runId"],
                "snapshotSha256": sha256(project_path(str(self.reference(role)["snapshot"]))),
            }
        state_store.invalidate_after_reset(self.state)
        self.state["generations"] = passports
        return {"commands": evidence, "generations": passports}

    def build(self) -> dict[str, Any]:
        manifest_path = self.release_dir / "manifest.json"
        if self.release_dir.exists():
            release = self.state.get("release") or {}
            if manifest_path.is_file() and release.get("manifestSha256") == sha256(manifest_path):
                return {"reused": True, "manifestSha256": release["manifestSha256"]}
            raise CycleError(f"release directory exists from an unfinished build: {self.release_dir}")
        inputs = self.scenario["inputs"]
        try:
            manifest = compile_release(
                self.scenario,
                self.release_dir,
                source_structure=project_path(str(inputs["sourceStructure"])),
                target_structure=project_path(str(inputs["targetStructure"])),
                matrix=read_json(scenario_file(self.scenario, "matrix")),
                rules=_resolve_provider(self.scenario),
            )
        except ReleaseError as error:
            raise CycleError(str(error)) from None
        size = sum(path.stat().st_size for path in self.release_dir.rglob("*") if path.is_file())
        limit = self.profile["limits"].get("maxReleaseBytes")
        if limit and size > int(limit):
            raise CycleError(f"release exceeds limits.maxReleaseBytes: {size} > {limit}")
        digest = sha256(manifest_path)
        self.state["release"] = {"path": str(self.release_dir), "manifestSha256": digest}
        return {"manifestSha256": digest, "files": len(manifest["files"]), "archives": len(manifest["archives"])}

    def load(self) -> dict[str, Any]:
        check_expendable_targets(self.profile)
        template = self.profile.get("commands", {}).get("load")
        if not template:
            raise CycleError("profile commands.load is not set")
        evidence: dict[str, Any] = {}
        for role in ROLES:
            evidence[role] = run_observed_stage(
                stage="load",
                target=role,
                run_root=self.run_root,
                stage_root=self.stage_root("load", role),
                command=render_command(template, self.placeholders("load", role)),
                environment=self.environment("load", role),
                limits=self.profile["limits"],
                expect_result=True,
            )
        return evidence

    def run_stage(self) -> dict[str, Any]:
        for name in self.nodes:
            if self.state["nodes"][name]["status"] not in state_store.READY:
                self.run_node(name)
        return {"nodes": {name: self.state["nodes"][name]["status"] for name in self.nodes}}

    def run_node(self, name: str) -> None:
        if name not in self.nodes:
            raise CycleError(f"unknown scenario node: {name}")
        node = self.nodes[name]
        retry = str(node["retry"])
        state_store.refuse_after_failure(self.state, name, retry_allowed=retry in RETRYABLE_AFTER_FAILURE)
        state_store.require_ready(self.state, name, node["dependencies"])
        item = self.state["nodes"][name]
        generation = self.generation_id()
        fingerprint = canonical_json_sha256(
            {
                "inputs": {path: path_sha256(project_path(path)) for path in node["inputs"]},
                "dependencies": {
                    dep: state_store.entry(self.state, dep).get("evidence", {}) for dep in node["dependencies"]
                },
                "generation": generation,
            }
        )
        if retry == "probe-and-reuse" and item["status"] in state_store.READY and item["inputSha256"] == fingerprint:
            item["status"] = "reused"
            self.save()
            return
        if retry == "fresh-generation-required" and any(
            entry.get("generation") == generation for entry in item.get("history", [])
        ):
            raise CycleError(f"node {name} requires a fresh generation of the bases: run reset in a new --run-root")
        if self.state.get("failure") and self.state["failure"].get("stage") == name:
            self.state["failure"] = None
        item.setdefault("history", []).append({"generation": generation, "attempt": int(item.get("attempts", 0)) + 1})
        item["inputSha256"] = fingerprint

        def action() -> dict[str, Any]:
            stage_root = self.stage_root("run", name)
            evidence = run_observed_stage(
                stage="run",
                target=name,
                run_root=self.run_root,
                stage_root=stage_root,
                command=render_command(node["command"], self.placeholders("run", name)),
                environment=self.environment("run", name),
                limits=self.profile["limits"],
                expect_result=True,
            )
            missing = [path for path in node["outputs"] if not (stage_root / path).exists()]
            if missing:
                raise CycleError(f"node {name} did not produce outputs: {', '.join(missing)}")
            return evidence

        self.execute(name, action)

    def verify(self) -> dict[str, Any]:
        release = self.state.get("release") or {}
        manifest_path = self.release_dir / "manifest.json"
        if not manifest_path.is_file() or sha256(manifest_path) != release.get("manifestSha256"):
            raise CycleError(f"release manifest is missing or changed: {manifest_path}")
        manifest = read_json(manifest_path)
        for relative, digest in {**manifest["files"], **manifest["archives"]}.items():
            if sha256(self.release_dir / relative) != digest:
                raise CycleError(f"release file changed after build: {relative}")
        if self.scenario.get("expected"):
            expected = read_json(scenario_file(self.scenario, "expected"))
            for key in ("files", "archives"):
                if key in expected and sorted(expected[key]) != sorted(manifest[key]):
                    raise CycleError(f"release {key} differ from expected.json")
        before = read_json(self.run_root / "source-before.json")
        after = {"schemaVersion": 1, "references": self.reference_fingerprints()}
        atomic_json(self.run_root / "source-after.json", after)
        if before.get("references") != after["references"]:
            raise CycleError("reference bases changed during the run: compare source-before.json and source-after.json")
        generations = self.state.get("generations") or {}
        if sorted(generations) != sorted(ROLES):
            raise CycleError("generations of both bases are missing; run reset")
        evidence: dict[str, Any] = {"manifestSha256": release["manifestSha256"]}
        if self.args.baseline_result:
            baseline = read_json(Path(self.args.baseline_result))
            previous = baseline.get("generations") or {}
            same = [
                role
                for role in ROLES
                if previous.get(role, {}).get("generationId") == generations[role]["generationId"]
            ]
            if same:
                raise CycleError("same generation: " + ", ".join(same))
            baseline_manifest = read_json(Path(str(baseline.get("release", {}).get("path", ""))) / "manifest.json")
            for key in ("files", "archives"):
                if baseline_manifest.get(key) != manifest[key]:
                    raise CycleError("release hashes differ from baseline generation")
            evidence["baselineResult"] = str(Path(self.args.baseline_result))
        return evidence

    # ----- commands ----------------------------------------------------------------------------

    def run_named_stage(self, name: str) -> None:
        state_store.refuse_after_failure(self.state, name)
        state_store.require_ready(self.state, name, STAGE_DEPENDENCIES[name])
        actions: dict[str, Callable[[], dict[str, Any]]] = {
            "doctor": self.doctor,
            "reset": self.reset,
            "build": self.build,
            "load": self.load,
            "run": self.run_stage,
            "verify": self.verify,
        }
        self.execute(name, actions[name])

    def finish(self) -> dict[str, Any]:
        if self.state["stages"]["verify"]["status"] in state_store.READY:
            status = "workbench-ready" if self.args.baseline_result else "workbench-run-passed"
        else:
            status = "in-progress"
        return state_store.write_result(self.run_root, self.state, status)

    def build_rules(self) -> dict[str, Any]:
        state_store.refuse_after_failure(self.state, "build")
        if self.state["stages"]["build"]["status"] not in state_store.READY:
            self.execute("build", self.build)
        manifest = read_json(self.release_dir / "manifest.json")
        published = publish_release(self.release_dir, manifest, Path(str(self.profile["releasePublishRoot"])))
        return state_store.write_result(
            self.run_root,
            self.state,
            "rules-built",
            publishedRelease=str(published),
            manifestSha256=self.state["release"]["manifestSha256"],
        )

    def main(self) -> int:
        self.run_root.mkdir(parents=True, exist_ok=True)
        with profile_lock(self.profile, self.run_root):
            self.state = state_store.load_or_init(self.run_root, self.profile_path, self.scenario, self.profile)
            self.save()
            command, name = self.args.command, self.args.name
            if command == "run" and name == BUILD_RULES:
                self.build_rules()
            elif command == "run" and name:
                self.run_node(name)
                self.finish()
            elif command == "all":
                for stage in STAGES:
                    if self.state["stages"][stage]["status"] not in state_store.READY:
                        self.run_named_stage(stage)
                self.finish()
            else:
                self.run_named_stage(command)
                self.finish()
        print(self.run_root / "result.json")
        return 0


def run(args: argparse.Namespace) -> int:
    return Cycle(args).main()
