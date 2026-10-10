"""Mutation checks of `_generated_structural_contracts`: derived context and project-owned JSON of a generated project."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.python.agent_docs import _Docs, _generated_structural_contracts

CONTEXT = "automation/context/"
CONTOUR_IDS = (
    "codex-onboard",
    "agent-verify",
    "export-context-check",
    "doctor",
    "bdd",
    "bdd-warm-service",
    "smoke",
    "publish-http",
    "load-diff-src",
    "load-task-src",
)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture(root: Path) -> str:
    for rel in (
        CONTEXT + "source-tree.generated.txt",
        CONTEXT + "metadata-index.generated.json",
        CONTEXT + "project-map.md",
        "docs/agent/architecture-map.md",
        "docs/agent/operator-local-runbook.md",
        "docs/agent/generated-project-index.md",
        "AGENTS.md",
        "README.md",
        ".codex/README.md",
    ):
        _write(root, rel, "")
    _write(
        root,
        CONTEXT + "project-delta-hints.json",
        json.dumps(
            {
                "hintsRole": "project-owned-project-delta-hints",
                "selectors": {"pathPrefixes": [], "pathKeywords": []},
                "representativePaths": [],
            }
        ),
    )
    _write(
        root,
        CONTEXT + "runtime-profile-policy.json",
        json.dumps(
            {
                "rootEnvProfiles": {
                    "canonicalExamples": [],
                    "canonicalLocalPrivate": [],
                    "sanctionedAdditionalProfiles": [],
                    "localSandbox": "env/.local",
                }
            }
        ),
    )
    matrix_rel = CONTEXT + "runtime-support-matrix.json"
    contours = [
        {
            "id": contour,
            "status": "supported",
            "profileProvenance": "none",
            "entrypoint": "make check",
            "runbookPath": "README.md",
        }
        for contour in CONTOUR_IDS
    ]
    _write(
        root,
        matrix_rel,
        json.dumps(
            {
                "matrixRole": "project-owned-runtime-support-matrix",
                "statuses": ["supported", "unsupported", "operator-local", "provisioned"],
                "contours": contours,
                "projectSpecificBaselineExtension": None,
            }
        ),
    )
    _write(
        root,
        "docs/agent/runtime-quickstart.md",
        "\n".join(f"| `{contour}` | `supported` | `make check` | none | `README.md` |" for contour in CONTOUR_IDS),
    )
    return matrix_rel


def test_consistent_fixture_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _fixture(tmp_path)
    docs = _Docs(tmp_path)
    _generated_structural_contracts(docs)
    assert docs.status == 0, capsys.readouterr().err


def test_matrix_status_set_and_quickstart_drift_are_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    matrix_rel = _fixture(tmp_path)
    matrix = json.loads((tmp_path / matrix_rel).read_text(encoding="utf-8"))
    matrix["contours"][0]["status"] = "unsupported"
    matrix["statuses"] = ["supported"]
    _write(tmp_path, matrix_rel, json.dumps(matrix))
    docs = _Docs(tmp_path)
    _generated_structural_contracts(docs)
    errors = capsys.readouterr().err
    assert docs.status == 1
    assert "canonical status set" in errors
    assert "runtime quick reference drifts" in errors


def test_private_paths_are_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _fixture(tmp_path)
    tree = CONTEXT + "source-tree.generated.txt"
    _write(tmp_path, tree, "./.codex/README.md\n./.codex/config.toml\n./env/local.example.json\n")
    docs = _Docs(tmp_path)
    _generated_structural_contracts(docs)
    assert docs.status == 0, capsys.readouterr().err
    _write(tmp_path, tree, "./.codex/private.toml\n./.venv/bin/python\n./env/.local/private.json\n./env/local.json\n")
    _generated_structural_contracts(docs)
    errors = capsys.readouterr().err
    assert docs.status == 1
    assert errors.count("local-private path leaked") == 4


def test_baseline_extension_needs_existing_entrypoint_and_runbook(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    matrix_rel = _fixture(tmp_path)
    matrix = json.loads((tmp_path / matrix_rel).read_text(encoding="utf-8"))
    matrix["projectSpecificBaselineExtension"] = {
        "id": "project-checks",
        "entrypoint": "./scripts/qa/missing.sh",
        "runbookPath": "docs/missing.md",
        "summary": "project checks",
    }
    _write(tmp_path, matrix_rel, json.dumps(matrix))
    quickstart = tmp_path / "docs/agent/runtime-quickstart.md"
    quickstart.write_text(quickstart.read_text(encoding="utf-8") + "\nproject-checks ./scripts/qa/missing.sh\n")
    docs = _Docs(tmp_path)
    _generated_structural_contracts(docs)
    errors = capsys.readouterr().err
    assert docs.status == 1
    assert "project-specific baseline extension entrypoint is missing: ./scripts/qa/missing.sh" in errors
    assert "project-specific baseline extension runbook is missing: docs/missing.md" in errors
