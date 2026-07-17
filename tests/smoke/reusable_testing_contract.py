from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SOURCE_ROOT))

from scripts.python import common
from scripts.python.common import CommandError
from scripts.python.testing_campaign import STATUSES, TRANSITIONS, run_testing_campaign
from scripts.python.testing_tooling import CLASS_ID_RE, UUID_RE, init_test_tooling, install_test_tooling


def expect_failure(call, contains: str = "") -> None:
    try:
        call()
    except (CommandError, FileExistsError, ValueError, zipfile.BadZipFile) as error:
        assert not contains or contains in str(error), (contains, str(error))
    else:
        raise AssertionError("command unexpectedly succeeded")


def write_inputs(root: Path, jobs: list[dict], extra_entrypoint: bool = False) -> tuple[Path, Path]:
    entrypoints = {"prepareGolden": "golden", "startWarmService": "warm", "runJob": "run"}
    if extra_entrypoint:
        entrypoints["secret"] = "no"
    entries = root / "entrypoints.json"
    queue = root / "queue.jsonl"
    entries.write_text(json.dumps(entrypoints), encoding="utf-8")
    queue.write_text("".join(json.dumps(job) + "\n" for job in jobs), encoding="utf-8")
    return entries, queue


def bdd(job_id: str, status: str = "pending", **extra) -> dict:
    return {"id": job_id, "kind": "vanessa-bdd", "status": status, "selector": {"featurePath": "features/a.feature"}, **extra}


def yax(job_id: str, status: str = "pending") -> dict:
    return {"id": job_id, "kind": "yaxunit", "status": status, "selector": {"filters": {"tags": ["smoke"]}}}


def init_campaign(root: Path, campaign_id: str, jobs: list[dict]) -> None:
    entries, queue = write_inputs(root, jobs)
    run_testing_campaign(["init", "--id", campaign_id, "--queue", str(queue), "--entrypoints", str(entries)])


def campaign_contract(root: Path) -> None:
    (root / "features").mkdir()
    (root / "features" / "a.feature").touch()
    init_campaign(root, "main", [bdd("pending"), bdd("running", "running"), bdd("retry", "failed_retry"), yax("unit")])
    with contextlib.redirect_stdout(io.StringIO()) as output:
        run_testing_campaign(["next"])
    assert json.loads(output.getvalue())["job"]["id"] == "retry"
    run_testing_campaign(["set", "retry", "running"])
    run_testing_campaign(["set", "retry", "done", "--result-dir", ".artifacts/retry"])
    with contextlib.redirect_stdout(io.StringIO()) as output:
        run_testing_campaign(["next"])
    assert json.loads(output.getvalue())["job"]["id"] == "running"
    expect_failure(lambda: run_testing_campaign(["set", "retry", "running"]), "transition is not allowed")
    expect_failure(lambda: run_testing_campaign(["set", "pending", "done", "--result-dir", "out"]), "transition is not allowed")
    expect_failure(lambda: run_testing_campaign(["set", "running", "done"]), "resultDir")
    run_testing_campaign(["set", "running", "failed_retry"])
    run_testing_campaign(["set", "running", "blocked"])
    run_testing_campaign(["set", "pending", "skipped_by_policy"])
    with contextlib.redirect_stdout(io.StringIO()) as output:
        run_testing_campaign(["next"])
    assert json.loads(output.getvalue())["job"]["id"] == "unit"
    with contextlib.redirect_stdout(io.StringIO()) as output:
        run_testing_campaign(["status"])
    status = json.loads(output.getvalue())
    assert status["campaignId"] == "main" and set(status["counts"]) == set(STATUSES)

    init_campaign(root, "exhausted", [bdd("done", "done", resultDir="results/done"), bdd("blocked", "blocked")])
    with contextlib.redirect_stdout(io.StringIO()) as output:
        run_testing_campaign(["next"])
    assert json.loads(output.getvalue()) == {"campaignId": "exhausted", "job": None}
    entries, queue = write_inputs(root, [])
    expect_failure(lambda: run_testing_campaign(["init", "--id", "empty", "--queue", str(queue), "--entrypoints", str(entries)]), "at least one job")
    run_testing_campaign(["use", "main"])

    entries, queue = write_inputs(root, [bdd("same"), bdd("same")])
    expect_failure(lambda: run_testing_campaign(["init", "--id", "dupes", "--queue", str(queue), "--entrypoints", str(entries)]), "unique")
    entries, queue = write_inputs(root, [bdd("unknown", surprise=True)])
    expect_failure(lambda: run_testing_campaign(["init", "--id", "unknown", "--queue", str(queue), "--entrypoints", str(entries)]), "unknown fields")
    entries, queue = write_inputs(root, [bdd("escape", selector={"featurePath": "../x"})])
    expect_failure(lambda: run_testing_campaign(["init", "--id", "escape", "--queue", str(queue), "--entrypoints", str(entries)]), "project-relative")
    entries, queue = write_inputs(root, [bdd("dot", selector={"featurePath": "features/./a.feature"})])
    expect_failure(lambda: run_testing_campaign(["init", "--id", "dot", "--queue", str(queue), "--entrypoints", str(entries)]), "project-relative")
    entries, queue = write_inputs(root, [bdd("extra")], extra_entrypoint=True)
    expect_failure(lambda: run_testing_campaign(["init", "--id", "extra", "--queue", str(queue), "--entrypoints", str(entries)]), "unknown fields")
    symlink = root / "features" / "linked.feature"
    symlink.symlink_to(root / "features" / "a.feature")
    entries, queue = write_inputs(root, [{"id": "link", "kind": "vanessa-bdd", "status": "pending", "selector": {"featurePath": "features/linked.feature"}}])
    expect_failure(lambda: run_testing_campaign(["init", "--id", "link", "--queue", str(queue), "--entrypoints", str(entries)]), "symbolic links")

    campaign_file = root / "analysis/testing/campaigns/main/campaign.json"
    original = campaign_file.read_text(encoding="utf-8")
    broken = json.loads(original)
    broken["schemaVersion"] = 2
    campaign_file.write_text(json.dumps(broken), encoding="utf-8")
    expect_failure(lambda: run_testing_campaign(["use", "main"]), "schemaVersion")
    campaign_file.write_text(original, encoding="utf-8")

    pointer = root / "analysis/testing/active-campaign.txt"
    pointer.unlink()
    pointer.symlink_to(campaign_file)
    expect_failure(lambda: run_testing_campaign(["use", "main"]), "symbolic links")
    pointer.unlink()
    pointer.write_text("main\n", encoding="utf-8")
    campaign_queue = root / "analysis/testing/campaigns/main/queue.jsonl"
    queue_text = campaign_queue.read_text(encoding="utf-8")
    campaign_queue.unlink()
    campaign_queue.symlink_to(root / "queue.jsonl")
    expect_failure(lambda: run_testing_campaign(["status"]), "symbolic links")
    campaign_queue.unlink()
    campaign_queue.write_text(queue_text, encoding="utf-8")

    for old in STATUSES:
        for new in STATUSES:
            if old == new:
                continue
            campaign_id = f"transition-{old}-{new}"
            initial = bdd("job", old, **({"resultDir": "results/old"} if old == "done" else {}))
            init_campaign(root, campaign_id, [initial])
            command = ["set", "job", new]
            if new == "done":
                command += ["--result-dir", "results/new"]
            if new in TRANSITIONS[old]:
                run_testing_campaign(command)
            else:
                expect_failure(lambda command=command: run_testing_campaign(command), "transition is not allowed")


def campaign_state_symlink_contract(root: Path) -> None:
    outside = root.parent / f"{root.name}-outside"
    outside.mkdir()
    link = root / "analysis"
    try:
        link.symlink_to(outside, target_is_directory=True)
        entries, queue = write_inputs(root, [bdd("job")])
        expect_failure(lambda: run_testing_campaign(["init", "--id", "link", "--queue", str(queue), "--entrypoints", str(entries)]), "symbolic links")
    finally:
        link.unlink(missing_ok=True)
        outside.rmdir()


def tree_hash(root: Path, excluded: set[str] | None = None) -> str:
    digest = hashlib.sha256()
    excluded = excluded or {"LICENSE", "UPSTREAM.json"}
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.name not in excluded):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0" + hashlib.sha256(path.read_bytes()).hexdigest().encode() + b"\n")
    return digest.hexdigest()


def source_contract() -> None:
    base = SOURCE_ROOT / "automation/testing"
    all_template_text = "\n".join(path.read_text(encoding="utf-8-sig", errors="ignore") for path in (base / "templates").rglob("*") if path.is_file() and path.name != "SOURCE.json")
    assert "Delans" not in all_template_text
    assert "ЗащитаПерсональныхДанных" not in all_template_text
    assert "ОбщегоНазначенияКлиентПереопределяемый" not in all_template_text
    assert "b5856766-e641-4da0-bbe1-84679f609410" not in all_template_text
    assert "2976c29f-f482-463d-8f6e-6a632fb50893" not in all_template_text
    vatest = (base / "templates/VATestContour/CommonModules/VATestContour_VanessaAutomationСервисГлобальный/Ext/Module.bsl").read_text(encoding="utf-8-sig")
    assert "RunCompletePath" in vatest and "VisibleManager" in vatest
    template_trees = {
        "VATestContour": "3a289ff004088f3dece757ea41cc9081ac45d813",
        "ProjectYAxUnitTests": "ca01a015dcb5a310d6b0c602fe41051bc0c7d23c",
    }
    for name, git_tree in template_trees.items():
        template = base / "templates" / name
        source = json.loads((template / "SOURCE.json").read_text(encoding="utf-8"))
        assert source["delansGitTree"] == git_tree
        assert tree_hash(template, {"SOURCE.json"}) == source["sourceTreeSha256"]
    vendor_sources = {
        "YAxUnit": ("25.12", "805a2277c997a3c24be0b0d080696479e91e4a15ed7e27aaf3991a7346522d70", "9df32496af0985735968594c126a7e4bffb54e18"),
        "VAExtension": ("1.29", "fc557bb23371a37dbe22a7a7a83e28f6db75b57f87e8802028cf1f90c4e00605", "2d8b3b72df05c0282403f5b0c34d2235e2369462"),
    }
    for name, expected in vendor_sources.items():
        vendor = base / "vendor" / name
        upstream = json.loads((vendor / "UPSTREAM.json").read_text(encoding="utf-8"))
        assert (vendor / "LICENSE").is_file()
        assert (upstream["tag"], upstream["assetSha256"], upstream["delansGitTree"]) == expected
        assert tree_hash(vendor) == upstream["sourceTreeSha256"]
        if name == "VAExtension":
            assert upstream["upstreamSourceTreeSha256"] == "261b3b9a3450de806c52b0ec56ad4ae1a2f7043b869789a99d1f6630800cdb7e"
            assert len(upstream["patches"]) == 2
            assert "#Если Не ВебКлиент Тогда" in (vendor / "CommonModules/VAExtensionКлиент/Ext/Module.bsl").read_text(encoding="utf-8-sig")
            assert "#Если Не ВебКлиент Тогда" in (vendor / "DataProcessors/VAExtension_ПолучениеДанныхИзБазы/Forms/Форма/Ext/Form/Module.bsl").read_text(encoding="utf-8-sig")
            for form in ("VAExtension_НажатьГиперссылкуHTMLДокумента", "VAExtension_НажатьКнопкуHTMLДокумента"):
                assert "Form.Command.ВыполнитьКодСервер" not in (vendor / "DataProcessors" / form / "Forms/Форма/Ext/Form.xml").read_text(encoding="utf-8-sig")


def actual_tooling_contract(root: Path) -> None:
    shutil.copytree(SOURCE_ROOT / "automation/testing", root / "automation/testing")
    original = "\n".join(path.read_text(encoding="utf-8-sig", errors="ignore") for path in (root / "automation/testing/templates/ProjectYAxUnitTests").rglob("*") if path.is_file())
    protected = {value.lower() for value in CLASS_ID_RE.findall(original)}
    original_ids = {value.lower() for value in UUID_RE.findall(original)} - protected
    init_test_tooling(["--project-tests-name", "AcmeTests"])
    for name in ("VATestContour", "AcmeTests", "YAxUnit", "VAExtension"):
        assert (root / "src/cfe" / name / "Configuration.xml").is_file()
    text = "\n".join(path.read_text(encoding="utf-8-sig", errors="ignore") for path in (root / "src/cfe/AcmeTests").rglob("*") if path.is_file())
    assert "ProjectYAxUnitTests" not in text
    generated_ids = {value.lower() for value in UUID_RE.findall(text)}
    assert not original_ids & generated_ids
    assert protected <= generated_ids


def fixture_sources(root: Path) -> None:
    for rel in ("templates/VATestContour", "templates/ProjectYAxUnitTests", "vendor/YAxUnit", "vendor/VAExtension"):
        source = root / "automation/testing" / rel
        source.mkdir(parents=True)
        (source / "Configuration.xml").write_text('<Configuration uuid="11111111-1111-1111-1111-111111111111"><xr:ClassId>22222222-2222-2222-2222-222222222222</xr:ClassId><Name>ProjectYAxUnitTests</Name></Configuration>', encoding="utf-8")


def tooling_contract(root: Path) -> None:
    fixture_sources(root)
    expect_failure(lambda: init_test_tooling(["--project-tests-name", "yaxunit"]), "conflicts")
    existing = root / "src/cfe/VAExtension"
    existing.mkdir(parents=True)
    (existing / "marker.txt").write_text("keep", encoding="utf-8")
    expect_failure(lambda: init_test_tooling(["--project-tests-name", "AcmeTests"]), "already exists")
    assert [path.name for path in (root / "src/cfe").iterdir()] == ["VAExtension"]
    shutil.rmtree(existing)
    init_test_tooling(["--project-tests-name", "AcmeTests"])
    targets = [root / "src/cfe" / name for name in ("VATestContour", "AcmeTests", "YAxUnit", "VAExtension")]
    assert all(path.is_dir() for path in targets)
    text = (root / "src/cfe/AcmeTests/Configuration.xml").read_text(encoding="utf-8")
    assert "AcmeTests" in text and "11111111-1111-1111-1111-111111111111" not in text
    assert "22222222-2222-2222-2222-222222222222" in text
    snapshot = {path: sorted((item.relative_to(path).as_posix(), item.read_bytes()) for item in path.rglob("*") if item.is_file()) for path in targets}
    expect_failure(lambda: init_test_tooling(["--project-tests-name", "AcmeTests"]), "already exists")
    assert snapshot == {path: sorted((item.relative_to(path).as_posix(), item.read_bytes()) for item in path.rglob("*") if item.is_file()) for path in targets}

    payload = b"fixture epf"
    epf_hash = hashlib.sha256(payload).hexdigest()
    archive = root / "fixture.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("vanessa-automation-single.epf", payload)
    zip_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    dependencies = {"vanessaAutomationSingle": {"version": "test", "url": "unused", "asset": "fixture.zip", "zipSha256": zip_hash, "epfName": "vanessa-automation-single.epf", "epfSha256": epf_hash, "installPath": ".artifacts/testing/vanessa/test/vanessa-automation-single.epf", "license": "BSD-3-Clause"}}
    (root / "automation/testing/dependencies.json").write_text(json.dumps(dependencies), encoding="utf-8")
    install_test_tooling(["--archive", str(archive)])
    target = root / dependencies["vanessaAutomationSingle"]["installPath"]
    assert target.read_bytes() == payload
    install_test_tooling(["--archive", str(archive)])
    dependencies["vanessaAutomationSingle"]["installPath"] = ".artifacts/testing/vanessa/next/vanessa-automation-single.epf"
    (root / "automation/testing/dependencies.json").write_text(json.dumps(dependencies), encoding="utf-8")
    install_test_tooling(["--archive", str(archive)])
    assert target.read_bytes() == payload
    assert (root / dependencies["vanessaAutomationSingle"]["installPath"]).read_bytes() == payload
    dependencies["vanessaAutomationSingle"]["installPath"] = ".artifacts/testing/vanessa/test/vanessa-automation-single.epf"
    (root / "automation/testing/dependencies.json").write_text(json.dumps(dependencies), encoding="utf-8")
    bad = root / "bad.zip"
    bad.write_bytes(archive.read_bytes() + b"bad")
    target.write_bytes(b"previous file")
    expect_failure(lambda: install_test_tooling(["--archive", str(bad)]), "SHA-256")
    assert target.read_bytes() == b"previous file"
    target.unlink()
    wrong_epf = root / "wrong-epf.zip"
    with zipfile.ZipFile(wrong_epf, "w") as bundle:
        bundle.writestr("vanessa-automation-single.epf", b"wrong epf")
    dependencies["vanessaAutomationSingle"]["zipSha256"] = hashlib.sha256(wrong_epf.read_bytes()).hexdigest()
    dependencies["vanessaAutomationSingle"]["installPath"] = ".artifacts/testing/vanessa/wrong/vanessa-automation-single.epf"
    (root / "automation/testing/dependencies.json").write_text(json.dumps(dependencies), encoding="utf-8")
    expect_failure(lambda: install_test_tooling(["--archive", str(wrong_epf)]), "EPF SHA-256")
    assert not (root / dependencies["vanessaAutomationSingle"]["installPath"]).exists()
    dependencies["vanessaAutomationSingle"]["installPath"] = ".artifacts/testing/vanessa/test/vanessa-automation-single.epf"
    unsafe = root / "unsafe.zip"
    with zipfile.ZipFile(unsafe, "w") as bundle:
        bundle.writestr("../vanessa-automation-single.epf", payload)
    dependencies["vanessaAutomationSingle"]["zipSha256"] = hashlib.sha256(unsafe.read_bytes()).hexdigest()
    (root / "automation/testing/dependencies.json").write_text(json.dumps(dependencies), encoding="utf-8")
    expect_failure(lambda: install_test_tooling(["--archive", str(unsafe)]), "unsafe ZIP")
    assert not target.exists()
    link_zip = root / "link.zip"
    with zipfile.ZipFile(link_zip, "w") as bundle:
        info = zipfile.ZipInfo("vanessa-automation-single.epf")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        bundle.writestr(info, "target")
    dependencies["vanessaAutomationSingle"]["zipSha256"] = hashlib.sha256(link_zip.read_bytes()).hexdigest()
    (root / "automation/testing/dependencies.json").write_text(json.dumps(dependencies), encoding="utf-8")
    expect_failure(lambda: install_test_tooling(["--archive", str(link_zip)]), "unsafe ZIP")
    unexpected = root / "unexpected.zip"
    with zipfile.ZipFile(unexpected, "w") as bundle:
        bundle.writestr("vanessa-automation-single.epf", payload)
        bundle.writestr("extra.txt", b"extra")
    dependencies["vanessaAutomationSingle"]["zipSha256"] = hashlib.sha256(unexpected.read_bytes()).hexdigest()
    (root / "automation/testing/dependencies.json").write_text(json.dumps(dependencies), encoding="utf-8")
    expect_failure(lambda: install_test_tooling(["--archive", str(unexpected)]), "unexpected ZIP")
    dependencies["vanessaAutomationSingle"]["installPath"] = "../outside.epf"
    (root / "automation/testing/dependencies.json").write_text(json.dumps(dependencies), encoding="utf-8")
    expect_failure(lambda: install_test_tooling(["--archive", str(archive)]), "project-relative")
    dependencies["vanessaAutomationSingle"]["installPath"] = ".artifacts/testing/vanessa/test/vanessa-automation-single.epf"
    outside = root.parent / f"{root.name}-artifacts"
    outside.mkdir()
    shutil.rmtree(root / ".artifacts")
    (root / ".artifacts").symlink_to(outside, target_is_directory=True)
    (root / "automation/testing/dependencies.json").write_text(json.dumps(dependencies), encoding="utf-8")
    try:
        expect_failure(lambda: install_test_tooling(["--archive", str(archive)]), "symbolic links")
    finally:
        (root / ".artifacts").unlink()
        outside.rmdir()


def wrapper_contract() -> None:
    assert 'testing-campaign "$@"' in (SOURCE_ROOT / "scripts/test/testing-campaign.sh").read_text(encoding="utf-8")
    assert '"testing-campaign" @RemainingArgs' in (SOURCE_ROOT / "scripts/test/testing-campaign.ps1").read_text(encoding="utf-8")
    assert 'ONEC_CAPABILITY_RUN_ROOT=$RUN_ROOT' in (SOURCE_ROOT / "scripts/test/run-yaxunit.sh").read_text(encoding="utf-8")


def main() -> None:
    source_contract()
    wrapper_contract()
    old_root = common.PROJECT_ROOT
    try:
        with tempfile.TemporaryDirectory(prefix="campaign-contract-") as temp:
            common.PROJECT_ROOT = Path(temp)
            campaign_contract(common.PROJECT_ROOT)
        with tempfile.TemporaryDirectory(prefix="campaign-link-contract-") as temp:
            common.PROJECT_ROOT = Path(temp)
            campaign_state_symlink_contract(common.PROJECT_ROOT)
        with tempfile.TemporaryDirectory(prefix="tooling-contract-") as temp:
            common.PROJECT_ROOT = Path(temp)
            tooling_contract(common.PROJECT_ROOT)
        with tempfile.TemporaryDirectory(prefix="actual-tooling-contract-") as temp:
            common.PROJECT_ROOT = Path(temp)
            actual_tooling_contract(common.PROJECT_ROOT)
    finally:
        common.PROJECT_ROOT = old_root
    print("reusable testing contract passed")


if __name__ == "__main__":
    main()
