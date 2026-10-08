"""Public metadata entrypoint: one bounded JSON result, no legacy execution."""

import tests.python.metadata_test_support  # noqa: F401, I001 — runs first: skips the module without pytest, lxml, jsonschema
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from scripts.python import metadata, metadata_ops


ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize(
    "arguments,expected",
    [
        (["capabilities"], 0),
        ([], 2),
        (["--help"], 2),
        (["wrong-action"], 2),
        (["capabilities", "--secret=local-secret"], 2),
        (["plan", "--root", "local-secret"], 2),
        (["inspect", "--ro", "local-secret", "--object", "Catalog.X"], 2),
        (["inspect", "--root", "unused", "--object", "Catalog.X"], 2),
        (["verify", "--root", "unused", "--object", "Catalog.X"], 2),
        (["plan", "--root", "unused", "--request", "unused", "--out", "unused"], 2),
        (["apply", "--root", "unused", "--plan", "unused"], 2),
    ],
)
def test_public_cli_result(arguments, expected):
    process = subprocess.run(
        [sys.executable, "-m", "scripts.python.cli", "metadata", *arguments],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        timeout=30,
    )
    assert process.returncode == expected, process.stderr
    assert process.stderr == ""
    assert len(process.stdout.splitlines()) == 1
    result = json.loads(process.stdout)
    Draft202012Validator(metadata_ops.RESULT_SCHEMA).validate(result)
    assert "local-secret" not in process.stdout
    if expected == 0:
        assert result["status"] == "capabilities"
        assert {name for name, item in result["changes"]["operations"].items() if item["available"]} == {
            "object.borrow",
            "tabular-section.borrow",
            "form.borrow",
            "object.edit",
            "form.add-input",
            "object.copy-description",
            "object.extend-type",
            "object.register-borrowed",
            "member.extend-type",
            "form.create",
            "form.compile",
            "form.edit",
            "form.remove",
            "object.create",
            "object.remove",
            "object.rename",
            "predefined.create",
            "predefined.update",
            "predefined.normalize-dimension-refs",
            "form.set-properties",
            "form.move-element",
            "form.remove-element",
            "form.rename-element",
            "form.set-attribute",
            "form.set-command",
            "form.remove-event",
            "template.set-area",
            "template.set-parameter",
            "template.set-format",
            "template.insert-rows",
            "template.delete-rows",
            "template.insert-columns",
            "template.delete-columns",
            "template.merge-cells",
            "template.set-size",
            "template.set-print-settings",
            "template.set-header-footer",
            "template.import-xlsx",
            "catalog.set-description-fill-checking",
            "chart.add-predefined",
            "chart.remove-predefined",
            "chart.extend-characteristic-type",
            "exchange-plan.edit-content",
        }
    else:
        assert result["error"]["code"] == expected
        assert len(result["error"]["message"].encode("utf-8")) <= 8192


@pytest.mark.parametrize(
    "exception,code",
    [
        (metadata.Rejected("local-secret", 2), 2),
        (metadata.Rejected("local-secret", 3), 3),
        (metadata.Rejected("local-secret", 4), 4),
        (OSError("local-secret"), 5),
        (ValueError("local-secret"), 5),
    ],
)
def test_execution_errors_keep_codes_and_do_not_leak_input(monkeypatch, capsys, exception, code):
    def fail(_args):
        raise exception

    monkeypatch.setattr(metadata, "dispatch", fail)
    assert metadata.main(["capabilities"]) == code
    output = capsys.readouterr()
    assert output.err == "" and "local-secret" not in output.out
    result = json.loads(output.out)
    Draft202012Validator(metadata_ops.RESULT_SCHEMA).validate(result)
    assert result["error"]["code"] == code


def test_new_route_never_calls_legacy_editor_or_helpers(monkeypatch, capsys):
    import subprocess

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Legacy route must not run")

    monkeypatch.setattr(subprocess, "run", forbidden)
    assert metadata.main(["capabilities"]) == 0
    assert metadata.main(["apply", "--root", "unused", "--plan", "unused"]) == 2
    assert len(capsys.readouterr().out.splitlines()) == 2


def test_retired_managed_form_command_is_rejected_without_dispatch(monkeypatch, capsys):
    from scripts.python import cli

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Retired command must not invoke metadata")

    monkeypatch.setattr(metadata, "main", forbidden)
    assert cli.main(["managed-form", "inspect", "--root", "unused", "--form", "unused"]) != 0
    output = capsys.readouterr()
    assert output.out == ""
    assert "unknown python-cli command: managed-form" in output.err


@pytest.mark.parametrize(
    "name",
    sorted(
        {
            "meta-info",
            "meta-compile",
            "meta-edit",
            "meta-remove",
            "meta-validate",
            "form-info",
            "form-add",
            "form-compile",
            "form-edit",
            "form-remove",
            "form-validate",
            "cfe-borrow",
        }
    ),
)
def test_every_retired_imported_editor_is_rejected_without_dispatch(monkeypatch, capsys, name):
    from scripts.python import cli, imported_skills

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Retired editor must not be executed")

    monkeypatch.setattr(metadata, "main", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert name in imported_skills.RETIRED_METADATA_SKILLS
    assert cli.main(["imported-skill", name, "--help"]) != 0
    output = capsys.readouterr()
    assert output.out == ""
    assert f"imported skill not found in manifest: {name}" in output.err
