"""Project-owned tool configs: pyright `exclude` classification, the ruff base contract (R18), ruff availability."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.python import type_checking
from scripts.python.type_checking import (
    QualityError,
    check_ruff_available,
    check_ruff_config,
    find_unclassified_python,
)

ROOT = Path(__file__).resolve().parents[2]
BASE = (ROOT / "scripts/qa/ruff-base.toml").read_text(encoding="utf-8")


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_pyright_excluded_paths_are_not_unclassified(tmp_path: Path) -> None:
    for rel in (
        "scripts/tool.py",
        "tests/contract/case/test_case.py",
        "tests/experiments/probe.py",
        "infra/site/server/wrapper.py",
        "tools/one_off.py",
        "build/gen/x.py",
    ):
        _write(tmp_path, rel)
    unclassified = find_unclassified_python(
        tmp_path,
        ["scripts"],
        ["tests/contract", "./tests/experiments/", "infra/*/server", "**/gen", "tools/one_off.py"],
    )
    assert unclassified == []
    assert find_unclassified_python(tmp_path, ["scripts"], ["infra/*"]) == [
        "build/gen/x.py",
        "tests/contract/case/test_case.py",
        "tests/experiments/probe.py",
        "tools/one_off.py",
    ]
    # `*` stays inside one path component, as in basedpyright.
    assert "infra/site/server/wrapper.py" in find_unclassified_python(tmp_path, ["scripts"], ["infra*server"])


def _ruff_project(root: Path, config: str) -> Path:
    _write(root, "scripts/qa/ruff-base.toml", BASE)
    _write(
        root,
        "automation/context/template-managed-paths.txt",
        "# template\nscripts/python/qa.py\nscripts/qa/ruff-base.toml\ntests/python/\nautomation/vendor/tool/run.py\n",
    )
    _write(root, "tests/python/test_one.py")
    _write(root, "ruff.toml", config)
    return root


SEED = 'extend = "scripts/qa/ruff-base.toml"\n'


@pytest.mark.parametrize(
    "config",
    [
        SEED,
        'extend = "./scripts/qa/ruff-base.toml"\n',
        SEED + 'extend-exclude = ["tests/contract", "project_tools/generated"]\n',
        SEED + '[lint]\nextend-select = ["S"]\nignore = ["E501", "D100"]\n',
        SEED + '[lint.per-file-ignores]\n"tests/contract/**" = ["F401"]\n"scripts/python/qa.py" = ["D100"]\n',
        SEED + 'exclude = ["automation/vendor"]\n',
        SEED + '[lint]\nselect = ["E", "F", "B", "I", "UP", "S"]\n',
    ],
)
def test_project_additions_are_accepted(tmp_path: Path, config: str) -> None:
    check_ruff_config(_ruff_project(tmp_path, config))


@pytest.mark.parametrize(
    ("config", "needle"),
    [
        ("line-length = 100\n", 'must keep extend = "scripts/qa/ruff-base.toml"'),
        ('extend = "other.toml"\n', "must keep extend"),
        (SEED + '[lint]\nselect = ["F"]\n', "lint.select drops base rules E4, E7, E9, B, I, UP"),
        (SEED + 'select = ["F"]\n', "select drops base rules"),
        (SEED + '[lint]\nignore = ["F401"]\n', "lint.ignore switches off base rules for every file: F401"),
        (SEED + '[lint]\nextend-ignore = ["E"]\n', "lint.extend-ignore switches off base rules"),
        (SEED + 'extend-exclude = ["scripts/python"]\n', "extend-exclude pattern 'scripts/python' excludes"),
        (SEED + 'exclude = ["qa.py"]\n', "exclude pattern 'qa.py' excludes template files: scripts/python/qa.py"),
        (SEED + '[lint]\nexclude = ["tests/*"]\n', "lint.exclude pattern 'tests/*' excludes"),
        (SEED + '[format]\nexclude = ["scripts/**"]\n', "format.exclude pattern 'scripts/**' excludes"),
        (SEED + '[lint.per-file-ignores]\n"scripts/*" = ["F401"]\n', "lint.per-file-ignores 'scripts/*'"),
        (SEED + '[lint.per-file-ignores]\n"!project/**" = ["B"]\n', "lint.per-file-ignores '!project/**'"),
        (SEED + '[lint.extend-per-file-ignores]\n"tests/python/*.py" = ["ALL"]\n', "tests/python/test_one.py"),
        (SEED + 'include = ["project/**/*.py"]\n', "include leaves out template files"),
    ],
)
def test_weakening_the_base_for_template_files_is_refused(tmp_path: Path, config: str, needle: str) -> None:
    with pytest.raises(QualityError) as error:
        check_ruff_config(_ruff_project(tmp_path, config))
    assert needle in str(error.value)


def test_missing_ruff_config_is_reported(tmp_path: Path) -> None:
    _ruff_project(tmp_path, SEED)
    (tmp_path / "ruff.toml").unlink()
    with pytest.raises(QualityError, match="ruff.toml is missing"):
        check_ruff_config(tmp_path)


def test_template_repository_config_passes() -> None:
    check_ruff_config(ROOT)


def _fake_run(returncode: int, stdout: str = "", stderr: str = ""):
    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        assert command[1:] == ["run", "--locked", "ruff", "--version"]
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)

    return run


def test_missing_ruff_names_the_fix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(type_checking.subprocess, "run", _fake_run(2, stderr="error: Failed to spawn: `ruff`\n"))
    with pytest.raises(QualityError) as error:
        check_ruff_available(tmp_path, "uv")
    message = str(error.value)
    assert "ruff is not installed in the project uv environment" in message
    assert f'uv add --dev "ruff>={type_checking.REQUIRED_MINIMUMS["ruff"]}"' in message
    assert "uv export --locked" in message


def test_old_ruff_names_the_fix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(type_checking.subprocess, "run", _fake_run(0, stdout="ruff 0.1.0\n"))
    with pytest.raises(QualityError, match="ruff 0.1.0 is below the template minimum"):
        check_ruff_available(tmp_path, "uv")


def test_current_ruff_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    version = type_checking.REQUIRED_MINIMUMS["ruff"]
    monkeypatch.setattr(type_checking.subprocess, "run", _fake_run(0, stdout=f"ruff {version}\n"))
    check_ruff_available(tmp_path, "uv")


@pytest.mark.parametrize(("has_xdist", "expected_n"), [(True, ["-n", "auto"]), (False, [])])
def test_parallel_flag_adds_xdist_workers_only_when_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, has_xdist: bool, expected_n: list[str]
) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(type_checking, "_uv", lambda: "uv")
    monkeypatch.setattr(type_checking, "_has_pytest_xdist", lambda _uv, _root: has_xdist)
    monkeypatch.setattr(type_checking, "_run", lambda command, _root: commands.append(list(command)) or 0)

    assert type_checking.run_python_tests(["--parallel", "--fast"], tmp_path) == 0

    command = commands[0]
    assert "--parallel" not in command
    assert (
        command[command.index("no:cacheprovider") + 1 : command.index("no:cacheprovider") + 1 + len(expected_n)]
        == expected_n
    )
    assert command[-1] == type_checking.PYTEST_ROOT
    assert f"--ignore={type_checking.PYTEST_SLOW_FILES[0]}" in command
