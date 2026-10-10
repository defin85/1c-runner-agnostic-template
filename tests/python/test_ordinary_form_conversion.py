from __future__ import annotations  # noqa: I001 — the dependency guard below must run before other imports

import tests.python.ordinary_form_test_support  # noqa: F401 — runs first: skips the module without v8unpack, lxml, jsonschema
import json
import io
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock, patch

import scripts.python.ordinary_form_conversion as conversion
from scripts.python import metadata_form_compile
from scripts.python.common import CommandError, write_json
from scripts.python.ordinary_form_conversion import (
    _arrange_page,
    _extract,
    _input_sha,
    _live_start,
    _mark_ready,
    _object_inventory,
    _read_source,
    _report,
    _verify_remediation,
    _v8unpack_python,
    _validate_forms,
    run_ordinary_form_conversion,
)
from scripts.python.v8unpack_erf_form import convert as convert_designer_erf

FIXTURE = Path(__file__).parents[1] / "fixtures" / "ordinary-form-conversion" / "supported-epf"
ERF_FIXTURE = Path(__file__).parents[1] / "fixtures" / "ordinary-form-conversion" / "supported-erf"
DESIGNER_ERF_FIXTURE = Path(__file__).parents[1] / "fixtures" / "ordinary-form-conversion" / "designer-erf-form"
DESIGNER_EPF_FIXTURE = Path(__file__).parents[1] / "fixtures" / "ordinary-form-conversion" / "designer-epf-sources"


class OrdinaryFormConversionTest(unittest.TestCase):
    def prepare_stub(
        self,
        _input: Path,
        _source: Path,
        staging: Path,
        kind: str,
        _profile: Path,
        _run_root: Path,
        _v8unpack: str,
        ordinary_output: Path | None = None,
    ):
        name = "TestProcessor" if kind == "ExternalDataProcessor" else "ТестовыйОтчет"
        form_name = "Form1" if kind == "ExternalDataProcessor" else "Форма"
        attribute = "Value" if kind == "ExternalDataProcessor" else "Параметр"
        root_xml = staging / f"{name}.xml"
        root_xml.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" '
            'xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:xs="http://www.w3.org/2001/XMLSchema" version="2.17">'
            f'<{kind} uuid="00000000-0000-0000-0000-000000000021"><Properties><Name>{name}</Name></Properties>'
            '<ChildObjects><Attribute uuid="00000000-0000-0000-0000-000000000022"><Properties>'
            f"<Name>{attribute}</Name><Type><v8:Type>xs:string</v8:Type></Type></Properties></Attribute>"
            f"<Form>{form_name}</Form></ChildObjects></{kind}></MetaDataObject>",
            encoding="utf-8",
        )
        object_root = staging / name
        object_root.mkdir()
        if ordinary_output is not None:
            shutil.copytree(staging, ordinary_output)
        return object_root, [
            {
                "kind": "attribute",
                "name": attribute,
                "path": f"object/attribute/{attribute}",
                "type": "xs:string",
                "outcome": "converted",
            }
        ]

    def prepare_profile(self, root: Path) -> Path:
        profile = root / "profile.json"
        write_json(
            profile,
            {
                "schemaVersion": 3,
                "profileName": "test",
                "projectName": "test",
                "projectSlug": "test",
                "platform": {"binaryPath": "C:/Program Files/1cv8/8.3.27.1/bin/1cv8.exe"},
                "infobase": {"mode": "file", "filePath": "C:/ib", "auth": {"mode": "os"}},
            },
        )
        return profile

    def prepare_sources_fixture(
        self, root: Path, repository_name: str | None = None
    ) -> tuple[dict[str, object], Path, Path]:
        artifact = root / "input.epf"
        artifact.write_bytes(b"test epf")
        profile = self.prepare_profile(root)

        def dump(_input: Path, destination: Path, _profile: Path, _run: Path, _tool: str, _kind: str) -> Path:
            shutil.copytree(DESIGNER_EPF_FIXTURE, destination)
            return destination / "ТестоваяОбработка.xml"

        with (
            patch.object(conversion, "_dump_object_source", side_effect=dump),
            patch.object(conversion, "project_root", return_value=root),
        ):
            summary = conversion._prepare_sources(artifact, profile, "v8unpack", repository_name)
        return summary, root / "src/epf", root / ".artifacts/ordinary-form-conversion"

    def test_prepare_sources_publishes_canonical_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            summary, epf_root, artifacts = self.prepare_sources_fixture(root)
            ordinary = epf_root / "ordinary/ТестоваяОбработка"
            managed = epf_root / "managed/ТестоваяОбработка"
            self.assertEqual("agent-remediation-required", summary["status"])
            self.assertEqual("ExternalDataProcessor", summary["actualKind"])
            self.assertEqual(_input_sha(DESIGNER_EPF_FIXTURE), _input_sha(ordinary))
            self.assertEqual(_input_sha(ordinary), summary["ordinaryTreeSha256"])
            self.assertEqual(_input_sha(managed), summary["managedTreeSha256"])
            self.assertTrue((ordinary / "ТестоваяОбработка/Forms/Форма/Ext/Form.bin").is_file())
            self.assertTrue((managed / "ТестоваяОбработка/Forms/Форма/Ext/Form.xml").is_file())
            self.assertFalse((managed / "ТестоваяОбработка/Forms/Форма/Ext/Form.bin").exists())
            self.assertFalse(any(path.name.endswith(".dsl.json") for path in epf_root.rglob("*")))
            self.assertEqual(
                summary, json.loads(next(artifacts.glob("*/preparation-summary.json")).read_text(encoding="utf-8"))
            )
            self.assertNotIn(str(root), json.dumps(summary, ensure_ascii=False))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            summary, epf_root, _artifacts = self.prepare_sources_fixture(root, "ТестоваяОбработкаВариант")
            ordinary = epf_root / "ordinary/ТестоваяОбработкаВариант"
            managed = epf_root / "managed/ТестоваяОбработкаВариант"
            self.assertEqual("ТестоваяОбработка", summary["designerName"])
            self.assertEqual("ТестоваяОбработкаВариант", summary["repositoryName"])
            self.assertEqual(_input_sha(DESIGNER_EPF_FIXTURE), _input_sha(ordinary))
            self.assertTrue((ordinary / "ТестоваяОбработка.xml").is_file())
            self.assertTrue((managed / "ТестоваяОбработка/Forms/Форма/Ext/Form.xml").is_file())

    def test_prepare_sources_rejects_unsupported_and_invalid_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(CommandError, "repository-name"):
                self.prepare_sources_fixture(root, "../variant")
            self.assertFalse((root / "src").exists())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.prepare_sources_fixture(root)
            before = _input_sha(root / "src/epf")
            with self.assertRaisesRegex(CommandError, "src/epf/ordinary"):
                self.prepare_sources_fixture(root)
            self.assertEqual(before, _input_sha(root / "src/epf"))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = conversion._form_dsl

            def unsupported(*args: Any, **kwargs: Any):
                dsl, _diagnostics, coverage, outcomes = original(*args, **kwargs)
                return dsl, [{"code": "unsupported-element"}], coverage, outcomes

            with (
                patch.object(conversion, "_form_dsl", side_effect=unsupported),
                self.assertRaisesRegex(CommandError, "unsupported ordinary form"),
            ):
                self.prepare_sources_fixture(root)
            self.assertFalse((root / "src/epf/ordinary/ТестоваяОбработка").exists())
            self.assertFalse((root / "src/epf/managed/ТестоваяОбработка").exists())
        for case in ("extra-root", "wrong-kind", "mismatched-directory"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                shutil.copytree(DESIGNER_EPF_FIXTURE, root / "designer")
                source = root / "designer"
                root_xml = source / "ТестоваяОбработка.xml"
                if case == "extra-root":
                    (source / "extra.xml").write_text("<x/>", encoding="utf-8")
                    expected = "exactly one root XML"
                elif case == "wrong-kind":
                    root_xml.write_text(
                        root_xml.read_text(encoding="utf-8").replace("ExternalDataProcessor", "ExternalReport"),
                        encoding="utf-8",
                    )
                    expected = "ExternalDataProcessor"
                else:
                    (source / "ТестоваяОбработка").rename(source / "ДругоеИмя")
                    expected = "must match"
                with self.assertRaisesRegex(CommandError, expected):
                    conversion._validate_designer_epf(root_xml)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            real_replace = os.replace
            calls = 0

            def fail_second(source: Path, target: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("second publish failed")
                real_replace(source, target)

            with patch.object(conversion.os, "replace", side_effect=fail_second), self.assertRaises(CommandError):
                self.prepare_sources_fixture(root)
            self.assertFalse((root / "src/epf/ordinary/ТестоваяОбработка").exists())
            self.assertFalse((root / "src/epf/managed/ТестоваяОбработка").exists())

    def test_prepare_sources_maps_profiles_and_redacts_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            artifact = root / "input.epf"
            artifact.write_bytes(b"epf")
            commands: list[list[str]] = []
            secret = "resolved-secret"

            def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
                commands.append(command)
                destination = Path(command[command.index("-OutputDir") + 1])
                shutil.copytree(DESIGNER_EPF_FIXTURE, destination)
                return subprocess.CompletedProcess(command, 0, secret, "")

            profiles = (
                {"mode": "file", "filePath": "C:/ib", "auth": {"mode": "os"}},
                {
                    "mode": "client-server",
                    "server": "srv",
                    "ref": "base",
                    "auth": {"mode": "user-password", "user": "u", "passwordEnv": "TEST_SECRET"},
                },
            )
            stdout, stderr = io.StringIO(), io.StringIO()
            with (
                patch.dict(os.environ, {"TEST_SECRET": secret}),
                patch.object(conversion.subprocess, "run", side_effect=run),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                for index, infobase in enumerate(profiles):
                    profile = root / f"profile-{index}.json"
                    write_json(
                        profile,
                        {
                            "schemaVersion": 3,
                            "profileName": "test",
                            "projectName": "test",
                            "projectSlug": "test",
                            "platform": {"binaryPath": "C:/1cv8.exe"},
                            "infobase": infobase,
                        },
                    )
                    conversion._dump_object_source(
                        artifact,
                        root / f"out-{index}",
                        profile,
                        root / f"run-{index}",
                        "v8unpack",
                        "ExternalDataProcessor",
                    )
                    self.assertEqual(
                        (root / f"run-{index}" / "source.epf").resolve(),
                        Path(commands[-1][commands[-1].index("-InputFile") + 1]),
                    )
            for index, command in enumerate(commands):
                self.assertEqual(str(root / f"profile-{index}.json"), command[command.index("-Profile") + 1])
                self.assertNotIn("-Target", command)
                self.assertNotIn(secret, command)
            self.assertNotIn(secret, stdout.getvalue() + stderr.getvalue())

    def test_prepare_sources_routes_cli_and_legacy_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "output"
            output.mkdir()
            epf = root / "input.epf"
            epf.write_bytes(b"epf")
            with self.assertRaisesRegex(CommandError, "prepare-sources"):
                run_ordinary_form_conversion(
                    ["publish-sources", "--input", str(epf), "--output", str(output), "--run-root", str(root / "run")]
                )
            with self.assertRaisesRegex(CommandError, "requires --input and --profile"):
                run_ordinary_form_conversion(["prepare-sources"])
            with self.assertRaisesRegex(CommandError, "does not accept"):
                run_ordinary_form_conversion(
                    [
                        "prepare-sources",
                        "--input",
                        str(epf),
                        "--profile",
                        str(root / "profile"),
                        "--run-root",
                        str(root / "run"),
                    ]
                )
            with patch.object(conversion, "_prepare_sources", return_value={"status": "ok"}) as prepare:
                run_ordinary_form_conversion(
                    [
                        "prepare-sources",
                        "--input",
                        str(epf),
                        "--profile",
                        str(root / "profile"),
                        "--repository-name",
                        "Variant",
                    ]
                )
            self.assertEqual("Variant", prepare.call_args.args[3])
            with self.assertRaisesRegex(CommandError, "only supported"):
                run_ordinary_form_conversion(
                    [
                        "prepare",
                        "--input",
                        str(epf),
                        "--output",
                        str(root / "other"),
                        "--profile",
                        str(root / "profile"),
                        "--repository-name",
                        "Variant",
                    ]
                )

    def test_publish_sources_routes_supported_families(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "output"
            output.mkdir()
            epf = root / "input.epf"
            epf.write_bytes(b"epf")
            epf_tree = root / "epf-tree"
            epf_tree.mkdir()
            (epf_tree / "ExternalDataProcessor.json").write_text("{}", encoding="utf-8")
            for source in (epf, epf_tree):
                with self.subTest(source=source), self.assertRaisesRegex(CommandError, "prepare-sources"):
                    run_ordinary_form_conversion(
                        [
                            "publish-sources",
                            "--input",
                            str(source),
                            "--output",
                            str(output),
                            "--run-root",
                            str(root / f"run-{source.name}"),
                        ]
                    )
            erf = root / "input.erf"
            erf.write_bytes(b"erf")
            erf_tree = root / "erf-tree"
            erf_tree.mkdir()
            (erf_tree / "ExternalReport.json").write_text("{}", encoding="utf-8")
            with patch.object(conversion, "_publish_sources", return_value={"status": "ok"}) as publish:
                for source in (erf, erf_tree):
                    run_ordinary_form_conversion(
                        [
                            "publish-sources",
                            "--input",
                            str(source),
                            "--output",
                            str(output),
                            "--run-root",
                            str(root / f"run-{source.name}"),
                        ]
                    )
            self.assertEqual(2, publish.call_count)

    def test_publish_prepared_erf_binds_package_build_and_relative_evidence(self) -> None:
        def fixture(root: Path, input_hash: str = "a" * 64, has_forms: bool = True) -> tuple[Path, Path, Path]:
            package = root / ".artifacts/package"
            source = package / "source"
            managed = package / "managed"
            shutil.copytree(ERF_FIXTURE, source)
            (managed / "ТестовыйОтчет/Ext").mkdir(parents=True)
            (managed / "ТестовыйОтчет.xml").write_text("<ExternalReport/>", encoding="utf-8")
            (managed / "ТестовыйОтчет/Ext/ObjectModule.bsl").write_text("", encoding="utf-8")
            artifact = root / ".artifacts/erf/ТестовыйОтчет.erf"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"erf")
            report = {
                "schemaVersion": 1,
                "status": "agent-remediation-required",
                "inputSha256": input_hash,
                "source": {"kind": "ExternalReport", "name": "ТестовыйОтчет"},
                "forms": [{"name": "Форма"}] if has_forms else [],
                "coverage": {"manual": 0},
                "diagnostics": [],
                "agentChecks": {
                    "analyzerClean": True,
                    "allBindingsPresent": True,
                    "allProceduresVerified": True,
                    "diagnostics": [],
                },
                "builds": [
                    {
                        "artifact": artifact.relative_to(root).as_posix(),
                        "artifactSha256": conversion._sha(artifact),
                        "managedTreeSha256": conversion._managed_source_sha(
                            managed / "ТестовыйОтчет.xml", managed / "ТестовыйОтчет"
                        ),
                        "validation": [{"engine": "metadata", "form-validate": "passed", "form-info": "passed"}]
                        if has_forms
                        else [],
                    }
                ],
            }
            write_json(managed / "conversion-report.json", report)
            write_json(
                package / "preparation-summary.json",
                {
                    "source": {"kind": "ExternalReport", "family": "erf", "name": "ТестовыйОтчет"},
                    "inputSha256": input_hash,
                    "sourceTreeSha256": _input_sha(source),
                    "sourcePath": "source",
                    "managedPath": "managed",
                    "reportPath": "managed/conversion-report.json",
                },
            )
            return source, managed, artifact

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, managed, _artifact = fixture(root)
            run_root = root / ".artifacts/publish"
            run_root.mkdir()
            with patch.object(conversion, "project_root", return_value=root):
                result = conversion._publish_sources(source, managed, run_root, "v8unpack")
            self.assertTrue((root / "src/erf/ordinary/ТестовыйОтчет.v8unpack/ExternalReport.json").is_file())
            self.assertTrue((root / "src/erf/managed/ТестовыйОтчет/ТестовыйОтчет.xml").is_file())
            self.assertFalse((root / "src/epf").exists())
            serialized = json.dumps(result, ensure_ascii=False) + (
                run_root / "source-publication-summary.json"
            ).read_text(encoding="utf-8")
            self.assertNotIn(str(root), serialized)

        for alias in ("ЦФ_РеестрыДокументовПриложение1", "ЦФ_ОтчетПоОБУ", "ЦФ_ОтчетОС", "ЦФ_ОтчетНМА0405"):
            with self.subTest(alias=alias), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source, managed, _artifact = fixture(root)
                run_root = root / ".artifacts/publish"
                run_root.mkdir()
                with patch.object(conversion, "project_root", return_value=root):
                    conversion._publish_sources(source, managed, run_root, "v8unpack", repository_name=alias)
                self.assertTrue((root / f"src/erf/ordinary/{alias}.v8unpack/ExternalReport.json").is_file())
                self.assertTrue((root / f"src/erf/managed/{alias}/ТестовыйОтчет.xml").is_file())

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, managed, _artifact = fixture(root, has_forms=False)
            run_root = root / ".artifacts/publish"
            run_root.mkdir()
            with patch.object(conversion, "project_root", return_value=root):
                conversion._publish_sources(source, managed, run_root, "v8unpack")
            self.assertTrue((root / "src/erf/managed/ТестовыйОтчет/ТестовыйОтчет.xml").is_file())

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, managed, _artifact = fixture(root, has_forms=False)
            (source / "ExternalReport.json").unlink()
            (source / "Designer").mkdir()
            (source / "Designer/ТестовыйОтчет.xml").write_text("<ExternalReport/>", encoding="utf-8")
            summary = json.loads((source.parent / "preparation-summary.json").read_text(encoding="utf-8"))
            summary["sourceTreeSha256"] = _input_sha(source)
            write_json(source.parent / "preparation-summary.json", summary)
            run_root = root / ".artifacts/publish"
            run_root.mkdir()
            with patch.object(conversion, "project_root", return_value=root):
                conversion._publish_sources(source, managed, run_root, "v8unpack")
            self.assertTrue((root / "src/erf/ordinary/ТестовыйОтчет.v8unpack/Designer/ТестовыйОтчет.xml").is_file())

        for key in ("sourcePath", "managedPath", "reportPath"):
            for invalid in (None, 42, [], "../outside"):
                with self.subTest(key=key, invalid=invalid), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    source, managed, _artifact = fixture(root)
                    summary_path = source.parent / "preparation-summary.json"
                    summary = json.loads(summary_path.read_text(encoding="utf-8"))
                    summary[key] = invalid
                    write_json(summary_path, summary)
                    run_root = root / ".artifacts/publish"
                    run_root.mkdir()
                    with (
                        patch.object(conversion, "project_root", return_value=root),
                        self.assertRaisesRegex(CommandError, "paths must be relative"),
                    ):
                        conversion._publish_sources(source, managed, run_root, "v8unpack")
                    self.assertFalse((root / "src").exists())

        for changed in ("source", "managed"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source, managed, _artifact = fixture(root)
                target = (
                    source / "changed.txt" if changed == "source" else managed / "ТестовыйОтчет/Ext/ObjectModule.bsl"
                )
                target.write_text("changed", encoding="utf-8")
                run_root = root / ".artifacts/publish"
                run_root.mkdir()
                with patch.object(conversion, "project_root", return_value=root), self.assertRaises(CommandError):
                    conversion._publish_sources(source, managed, run_root, "v8unpack")

                self.assertFalse((root / "src").exists())

        for invalid_validation in (
            [],
            [{"form-validate": "passed", "form-info": "passed"}],
            [{"engine": "legacy", "form-validate": "passed", "form-info": "passed"}],
        ):
            with self.subTest(validation=invalid_validation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source, managed, _artifact = fixture(root)
                report_path = managed / "conversion-report.json"
                report = json.loads(report_path.read_text(encoding="utf-8"))
                report["builds"][0]["validation"] = invalid_validation
                write_json(report_path, report)
                before = report_path.read_bytes()
                run_root = root / ".artifacts/publish"
                run_root.mkdir()
                with (
                    patch.object(conversion, "project_root", return_value=root),
                    self.assertRaisesRegex(CommandError, "matching successful control build"),
                ):
                    conversion._publish_sources(source, managed, run_root, "v8unpack")
                self.assertFalse((root / "src").exists())
                self.assertEqual(before, report_path.read_bytes())

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, managed, _artifact = fixture(root)
            ordinary_target = root / "src/erf/ordinary/ТестовыйОтчет.v8unpack"
            managed_target = root / "src/erf/managed/ТестовыйОтчет"
            ordinary_target.mkdir(parents=True)
            managed_target.mkdir(parents=True)
            (ordinary_target / "unexpected.txt").write_text("different", encoding="utf-8")
            (managed_target / "unexpected.txt").write_text("different", encoding="utf-8")
            run_root = root / ".artifacts/publish"
            run_root.mkdir()
            with (
                patch.object(conversion, "project_root", return_value=root),
                self.assertRaisesRegex(CommandError, "refusing to overwrite"),
            ):
                conversion._publish_sources(source, managed, run_root, "v8unpack")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            binary = root / "input.erf"
            binary.write_bytes(b"erf")
            _source, managed, _artifact = fixture(root, _input_sha(binary))
            run_root = root / ".artifacts/publish"
            run_root.mkdir()
            with (
                patch.object(conversion, "project_root", return_value=root),
                patch.object(conversion, "_extract", return_value=ERF_FIXTURE),
            ):
                result = cast(
                    Any, conversion._publish_sources(binary, managed, run_root, "v8unpack", root / "profile.json")
                )
            self.assertEqual(_input_sha(ERF_FIXTURE), result["ordinary"]["sha256"])

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, managed, _artifact = fixture(root)
            target = root / "src/erf/ordinary/ТестовыйОтчет.v8unpack"
            target.mkdir(parents=True)
            marker = target / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            run_root = root / ".artifacts/publish"
            run_root.mkdir()
            with (
                patch.object(conversion, "project_root", return_value=root),
                self.assertRaisesRegex(CommandError, "refusing to overwrite"),
            ):
                conversion._publish_sources(source, managed, run_root, "v8unpack")
            self.assertEqual("keep", marker.read_text(encoding="utf-8"))

    def test_publish_prepared_epf_uses_preserved_ordinary_and_repository_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / ".artifacts/package"
            source, ordinary, managed = package / "source", package / "ordinary", package / "managed"
            source.mkdir(parents=True)
            (source / "ExternalDataProcessor.json").write_text("{}", encoding="utf-8")
            shutil.copytree(DESIGNER_EPF_FIXTURE, ordinary)
            (managed / "ТестоваяОбработка/Ext").mkdir(parents=True)
            (managed / "ТестоваяОбработка.xml").write_text("<ExternalDataProcessor/>", encoding="utf-8")
            (managed / "ТестоваяОбработка/Ext/ObjectModule.bsl").write_text("", encoding="utf-8")
            artifact = root / ".artifacts/candidate.epf"
            artifact.write_bytes(b"epf")
            report = {
                "schemaVersion": 1,
                "status": "agent-remediation-required",
                "inputSha256": "a" * 64,
                "source": {"kind": "ExternalDataProcessor", "name": "ТестоваяОбработка"},
                "forms": [{"name": "Форма"}],
                "coverage": {"manual": 0},
                "diagnostics": [],
                "agentChecks": {
                    "analyzerClean": True,
                    "allBindingsPresent": True,
                    "allProceduresVerified": True,
                    "diagnostics": [],
                },
                "builds": [
                    {
                        "artifact": artifact.relative_to(root).as_posix(),
                        "artifactSha256": conversion._sha(artifact),
                        "managedTreeSha256": conversion._managed_source_sha(
                            managed / "ТестоваяОбработка.xml", managed / "ТестоваяОбработка"
                        ),
                        "validation": [{"engine": "metadata", "form-validate": "passed", "form-info": "passed"}],
                    }
                ],
            }
            write_json(managed / "conversion-report.json", report)
            write_json(
                package / "preparation-summary.json",
                {
                    "source": {"kind": "ExternalDataProcessor", "family": "epf", "name": "ТестоваяОбработка"},
                    "inputSha256": report["inputSha256"],
                    "sourceTreeSha256": _input_sha(source),
                    "ordinaryTreeSha256": _input_sha(ordinary),
                    "sourcePath": "source",
                    "ordinaryPath": "ordinary",
                    "managedPath": "managed",
                    "reportPath": "managed/conversion-report.json",
                },
            )
            run_root = root / ".artifacts/publish"
            run_root.mkdir()
            with patch.object(conversion, "project_root", return_value=root):
                result = cast(
                    Any,
                    conversion._publish_sources(
                        source, managed, run_root, "v8unpack", repository_name="ТестоваяОбработка100000153"
                    ),
                )
            self.assertEqual(_input_sha(ordinary), result["ordinary"]["sha256"])
            self.assertTrue((root / "src/epf/ordinary/ТестоваяОбработка100000153/ТестоваяОбработка.xml").is_file())
            self.assertTrue((root / "src/epf/managed/ТестоваяОбработка100000153/ТестоваяОбработка.xml").is_file())
            profile = root / "profile.json"
            profile.write_text("{}", encoding="utf-8")
            control = root / ".artifacts/control/result.epf"
            with (
                patch.object(conversion, "project_root", return_value=root),
                patch.object(conversion, "_build_for_profile", return_value={"status": "passed"}) as build,
            ):
                conversion._build_published_sources(managed, profile, control, root / ".artifacts/build-published")
            self.assertEqual((root / "src/epf/managed/ТестоваяОбработка100000153").resolve(), build.call_args.args[0])
            self.assertEqual(control, build.call_args.args[2])
            self.assertEqual("ТестоваяОбработка", build.call_args.kwargs["object_name"])

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / ".artifacts/package"
            source, ordinary, managed = package / "source", package / "ordinary", package / "managed"
            source.mkdir(parents=True)
            (source / "ExternalDataProcessor.json").write_text("{}", encoding="utf-8")
            shutil.copytree(DESIGNER_EPF_FIXTURE, ordinary)
            (managed / "ТестоваяОбработка/Ext").mkdir(parents=True)
            (managed / "ТестоваяОбработка.xml").write_text("<ExternalDataProcessor/>", encoding="utf-8")
            (managed / "ТестоваяОбработка/Ext/ObjectModule.bsl").write_text("", encoding="utf-8")
            artifact = root / ".artifacts/candidate.epf"
            artifact.write_bytes(b"epf")
            report = {
                "schemaVersion": 1,
                "status": "agent-remediation-required",
                "inputSha256": "a" * 64,
                "source": {"kind": "ExternalDataProcessor", "name": "ТестоваяОбработка"},
                "forms": [{"name": "Форма"}],
                "coverage": {"manual": 0},
                "diagnostics": [],
                "agentChecks": {
                    "analyzerClean": True,
                    "allBindingsPresent": True,
                    "allProceduresVerified": True,
                    "diagnostics": [],
                },
                "builds": [
                    {
                        "artifact": artifact.relative_to(root).as_posix(),
                        "artifactSha256": conversion._sha(artifact),
                        "managedTreeSha256": conversion._managed_source_sha(
                            managed / "ТестоваяОбработка.xml", managed / "ТестоваяОбработка"
                        ),
                        "validation": [{"engine": "metadata", "form-validate": "passed", "form-info": "passed"}],
                    }
                ],
            }
            write_json(managed / "conversion-report.json", report)
            write_json(
                package / "preparation-summary.json",
                {
                    "source": {"kind": "ExternalDataProcessor", "name": "ТестоваяОбработка"},
                    "inputSha256": report["inputSha256"],
                    "sourceTreeSha256": _input_sha(source),
                    "ordinaryTreeSha256": _input_sha(ordinary),
                    "sourcePath": "source",
                    "ordinaryPath": "ordinary",
                    "managedPath": "managed",
                    "reportPath": "managed/conversion-report.json",
                },
            )
            original_write_json = conversion.write_json
            original_report = (managed / "conversion-report.json").read_bytes()

            def fail_summary(path: Path, value: object) -> None:
                if path.name == "source-publication-summary.json":
                    raise OSError("evidence write failed")
                original_write_json(path, value)

            run_root = root / ".artifacts/publish"
            run_root.mkdir()
            with (
                patch.object(conversion, "project_root", return_value=root),
                patch.object(conversion, "write_json", side_effect=fail_summary),
                self.assertRaises(OSError),
            ):
                conversion._publish_sources(
                    source, managed, run_root, "v8unpack", repository_name="ТестоваяОбработка100000153"
                )
            self.assertFalse((root / "src/epf/ordinary/ТестоваяОбработка100000153").exists())
            self.assertFalse((root / "src/epf/managed/ТестоваяОбработка100000153").exists())
            self.assertEqual(original_report, (managed / "conversion-report.json").read_bytes())

            write_json(managed / "conversion-report.json", report)
            original_replace = conversion.os.replace
            replace_calls = 0

            def fail_second_replace(source_path: Path, target_path: Path) -> None:
                nonlocal replace_calls
                replace_calls += 1
                if replace_calls == 2:
                    raise OSError("second publication move failed")
                original_replace(source_path, target_path)

            with (
                patch.object(conversion, "project_root", return_value=root),
                patch.object(conversion.os, "replace", side_effect=fail_second_replace),
                self.assertRaises(OSError),
            ):
                conversion._publish_sources(
                    source, managed, run_root, "v8unpack", repository_name="ТестоваяОбработка100000153"
                )
            self.assertFalse((root / "src/epf/ordinary/ТестоваяОбработка100000153").exists())
            self.assertFalse((root / "src/epf/managed/ТестоваяОбработка100000153").exists())
            self.assertNotIn(
                "canonicalSources", json.loads((managed / "conversion-report.json").read_text(encoding="utf-8"))
            )

    def test_build_published_erf_uses_erf_managed_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            managed = root / ".artifacts/package/managed"
            published = root / "src/erf/managed/ЦФ_ТестовыйОтчет"
            object_tree = published / "ТестовыйОтчет"
            object_tree.mkdir(parents=True)
            root_xml = published / "ТестовыйОтчет.xml"
            root_xml.write_text("<ExternalReport/>", encoding="utf-8")
            (object_tree / "Ext").mkdir()
            (object_tree / "Ext/ObjectModule.bsl").write_text("", encoding="utf-8")
            write_json(
                managed / "conversion-report.json",
                {
                    "schemaVersion": 1,
                    "status": "agent-remediation-required",
                    "source": {"kind": "ExternalReport", "name": "ТестовыйОтчет"},
                    "canonicalSources": {
                        "repositoryName": "ЦФ_ТестовыйОтчет",
                        "managed": {
                            "rootXml": root_xml.relative_to(root).as_posix(),
                            "objectTree": object_tree.relative_to(root).as_posix(),
                            "sha256": conversion._managed_source_sha(root_xml, object_tree),
                        },
                    },
                },
            )
            profile = root / "profile.json"
            profile.write_text("{}", encoding="utf-8")

            control = root / ".artifacts/control/test.erf"
            with (
                patch.object(conversion, "project_root", return_value=root),
                patch.object(conversion, "_build_for_profile", return_value={"status": "passed"}) as build,
            ):
                conversion._build_published_sources(managed, profile, control, root / ".artifacts/build-published")

            self.assertEqual(published.resolve(), build.call_args.args[0])
            self.assertEqual(control, build.call_args.args[2])

    def test_package_build_records_managed_hash_and_sanitized_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            managed = root / ".artifacts/package/managed"
            (managed / "ТестовыйОтчет/Ext").mkdir(parents=True)
            (managed / "ТестовыйОтчет.xml").write_text("<ExternalReport/>", encoding="utf-8")
            (managed / "ТестовыйОтчет/Ext/ObjectModule.bsl").write_text("", encoding="utf-8")
            write_json(
                managed / "conversion-report.json",
                {
                    "schemaVersion": 1,
                    "status": "agent-remediation-required",
                    "coverage": {"manual": 0},
                    "diagnostics": [],
                    "dependencies": [],
                    "agentChecks": {
                        "analyzerClean": True,
                        "allBindingsPresent": True,
                        "allProceduresVerified": True,
                        "diagnostics": [],
                    },
                },
            )
            profile = root / "profile.json"
            write_json(
                profile,
                {
                    "schemaVersion": 3,
                    "profileName": "demo",
                    "projectName": "test",
                    "projectSlug": "test",
                    "platform": {"binaryPath": "C:/Program Files/1cv8/8.3.27.1989/bin/1cv8.exe"},
                    "infobase": {
                        "mode": "client-server",
                        "server": "secret-server",
                        "ref": "secret-ref",
                        "auth": {"mode": "user-password", "user": "user", "passwordEnv": "BUILD_SECRET"},
                    },
                },
            )
            artifact = root / ".artifacts/erf/ТестовыйОтчет.erf"
            run_root = root / ".artifacts/build"
            run_root.mkdir(parents=True)

            def build(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
                Path(command[command.index("-OutputFile") + 1]).write_bytes(b"erf")
                return subprocess.CompletedProcess(command, 0, "", "")

            validation = [
                {
                    "form": "ТестовыйОтчет/Forms/Форма",
                    "engine": "metadata",
                    "form-validate": "passed",
                    "form-info": "passed",
                }
            ]
            with (
                patch.object(conversion, "project_root", return_value=root),
                patch.object(conversion, "resolve_secret_value", return_value="secret-password"),
                patch.object(conversion, "_validate_forms", return_value=validation),
                patch.object(conversion.subprocess, "run", side_effect=build),
            ):
                result = conversion._build_for_profile(managed, profile, artifact, run_root)
            self.assertEqual(
                conversion._managed_source_sha(managed / "ТестовыйОтчет.xml", managed / "ТестовыйОтчет"),
                result["managedTreeSha256"],
            )
            serialized = json.dumps(result, ensure_ascii=False) + (run_root / "build-summary.json").read_text(
                encoding="utf-8"
            )
            self.assertNotIn(str(root), serialized)
            self.assertNotIn("secret-server", serialized)
            self.assertNotIn("secret-ref", serialized)
            self.assertNotIn("secret-password", serialized)
            self.assertNotIn("binary", serialized)
            self.assertEqual(".artifacts/package/managed", result["managed"])
            self.assertEqual(".artifacts/erf/ТестовыйОтчет.erf", result["artifact"])

    def test_prepare_sources_excludes_downstream_stages(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            downstream = (
                "_verify_remediation",
                "_build_for_profile",
                "_build_published_sources",
                "_live_start",
                "_live_confirm",
                "_mark_ready",
            )
            patches = [patch.object(conversion, name) for name in downstream]
            mocks = [item.start() for item in patches]
            try:
                self.prepare_sources_fixture(root)
            finally:
                for item in patches:
                    item.stop()
            for mock in mocks:
                mock.assert_not_called()

    def test_unsupported_form_constructs_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            shutil.copytree(FIXTURE, source)
            source_sha = _input_sha(source)
            run_ordinary_form_conversion(["analyze", "--input", str(source), "--run-root", str(root / "valid")])
            self.assertEqual(
                "analyzed",
                json.loads((root / "valid" / "conversion-report.json").read_text(encoding="utf-8"))["status"],
            )
            self.assertEqual(source_sha, _input_sha(source))

            element_file = source / "Form" / "Форма" / "Form.elem.json"
            elements = json.loads(element_file.read_text(encoding="utf-8"))
            elements["tree"][0]["type"] = "UnknownWidget"
            element_file.write_text(json.dumps(elements), encoding="utf-8")
            run_ordinary_form_conversion(["analyze", "--input", str(source), "--run-root", str(root / "unsupported")])
            unsupported_report = json.loads(
                (root / "unsupported" / "conversion-report.json").read_text(encoding="utf-8")
            )
            self.assertEqual("structure-remediation-required", unsupported_report["status"])
            self.assertEqual("unsupported-element", unsupported_report["diagnostics"][0]["code"])
            self.assertEqual(
                unsupported_report["coverage"]["input"],
                sum(unsupported_report["coverage"][key] for key in ("converted", "manual", "excluded")),
            )
            report = json.loads((source / "ExternalDataProcessor.json").read_text(encoding="utf-8"))
            report["v8unpack"] = "999"
            (source / "ExternalDataProcessor.json").write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(CommandError, "unsupported"):
                run_ordinary_form_conversion(
                    ["analyze", "--input", str(source), "--run-root", str(root / "unknown-version")]
                )
            report["v8unpack"] = "1.2.6"
            (source / "ExternalDataProcessor.json").write_text(json.dumps(report), encoding="utf-8")
            (source / "Form" / "Форма" / "Form.id.json").unlink()
            with self.assertRaisesRegex(CommandError, "missing"):
                run_ordinary_form_conversion(["analyze", "--input", str(source), "--run-root", str(root / "corrupt")])

    def test_erf_conversion_and_binary_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            shutil.copytree(ERF_FIXTURE, source)
            run_ordinary_form_conversion(["analyze", "--input", str(source), "--run-root", str(root / "erf")])
            erf_report = json.loads((root / "erf" / "conversion-report.json").read_text(encoding="utf-8"))
            self.assertEqual("ExternalReport", erf_report["source"]["kind"])
            self.assertEqual("analyzed", erf_report["status"])
            self.assertEqual(
                "ExternalReportObject.ТестовыйОтчет", erf_report["forms"][0]["dsl"]["attributes"][0]["type"]
            )
            binary = root / "report.erf"
            binary.write_bytes(b"erf")
            with self.assertRaisesRegex(CommandError, "requires --profile"):
                _extract(binary, root / "missing-profile", "v8unpack")
            with patch(
                "scripts.python.ordinary_form_conversion._extract_erf", return_value=root / "normalized"
            ) as adapter:
                result = _extract(binary, root / "normalized", "v8unpack", root / "profile.json", root / "run")
            self.assertEqual(root / "normalized", result)
            adapter.assert_called_once_with(
                binary, root / "normalized", "v8unpack", root / "profile.json", root / "run"
            )
            output = root / "output"
            with patch("scripts.python.ordinary_form_conversion._prepare_object_root", side_effect=self.prepare_stub):
                run_ordinary_form_conversion(
                    [
                        "convert",
                        "--input",
                        str(ERF_FIXTURE),
                        "--run-root",
                        str(root / "convert"),
                        "--output",
                        str(output),
                        "--profile",
                        str(root / "profile.json"),
                    ]
                )
            form = (output / "ТестовыйОтчет/Forms/Форма/Ext/Form.xml").read_text(encoding="utf-8")
            self.assertIn("ExternalReportObject.ТестовыйОтчет", form)
            self.assertIn("ОтчетОбъект.Параметр", form)

    def test_erf_without_forms_preserves_empty_form_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            designer = root / "designer"
            designer.mkdir()
            (designer / "ОтчетБезФорм.xml").write_text(
                '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">'
                "<ExternalReport><Properties><Name>ОтчетБезФорм</Name></Properties>"
                "<ChildObjects/></ExternalReport></MetaDataObject>",
                encoding="utf-8",
            )
            (designer / "ОтчетБезФорм").mkdir()
            normalized = root / "normalized"

            convert_designer_erf(designer, normalized)

            kind, metadata, forms = _read_source(normalized)
            self.assertEqual(("ExternalReport", "ОтчетБезФорм", []), (kind, metadata["name"], forms))
            self.assertEqual([], _validate_forms(normalized))

    def test_v8unpack_console_launcher_resolves_its_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / "python.exe"
            runtime.write_bytes(b"")
            launcher = Path(temp) / "v8unpack.exe"
            launcher.write_bytes(b"launcher\x00#!" + os.fsencode(runtime) + b"\nscript")
            self.assertEqual(runtime, _v8unpack_python(str(launcher)))

    def test_v8unpack_sh_trampoline_resolves_its_python(self) -> None:
        # uv writes this form when the interpreter path exceeds the shebang limit.
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / "python3"
            runtime.write_bytes(b"")
            launcher = Path(temp) / "v8unpack"
            launcher.write_bytes(
                b"#!/bin/sh\n'''exec' '" + os.fsencode(runtime) + b"' \"$0\" \"$@\"\n' '''\nimport sys\n"
            )
            self.assertEqual(runtime, _v8unpack_python(str(launcher)))
            launcher.write_bytes(b'#!/bin/sh\nexec something-else "$@"\n')
            with self.assertRaises(CommandError):
                _v8unpack_python(str(launcher))

    @unittest.skipUnless(shutil.which("v8unpack"), "v8unpack is not installed")
    def test_designer_erf_form_bin_is_normalized_by_v8unpack(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "normalized"
            helper = Path(__file__).parents[2] / "scripts" / "python" / "v8unpack_erf_form.py"
            result = subprocess.run(
                [str(_v8unpack_python("v8unpack")), str(helper), str(DESIGNER_ERF_FIXTURE / "designer"), str(output)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(0, result.returncode, result.stderr or result.stdout)
            kind, metadata, forms = _read_source(output)
            self.assertEqual(
                ("ExternalReport", "ТестовыйВнешнийОтчет", ["Форма"]),
                (kind, metadata["name"], [form.name for form in forms]),
            )
            self.assertEqual(
                (DESIGNER_ERF_FIXTURE / "raw" / "0" / "module").read_bytes(),
                (output / "Form" / "Форма" / "Form.obj.bsl").read_bytes(),
            )
            self.assertEqual(
                (
                    DESIGNER_ERF_FIXTURE / "designer" / "ТестовыйВнешнийОтчет" / "Forms" / "Форма" / "Ext" / "Form.bin"
                ).read_bytes(),
                (output / "Designer" / "ТестовыйВнешнийОтчет" / "Forms" / "Форма" / "Ext" / "Form.bin").read_bytes(),
            )

    def test_supported_form_mapping_matches_golden(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_source(root)
            element_file = source / "Form" / "Form1" / "Form.elem.json"
            elements = json.loads(element_file.read_text(encoding="utf-8"))
            elements["tree"] = [
                {"name": "First", "type": "Label", "page": "Page1"},
                {"name": "Second", "type": "Field", "page": "Page2"},
            ]
            elements["data"] = {
                "-pages-": ["Page1", "Page2"],
                "Page1/First": {"id": "1", "ver": 27, "page": "Page1", "raw": []},
                "Page2/Second": {"id": "2", "ver": 27, "page": "Page2", "raw": [], "prop": "ОбработкаОбъект"},
            }
            element_file.write_text(json.dumps(elements), encoding="utf-8")
            run_ordinary_form_conversion(["analyze", "--input", str(source), "--run-root", str(root / "run")])
            dsl = json.loads((root / "run" / "conversion-report.json").read_text(encoding="utf-8"))["forms"][0]["dsl"]
            pages = dsl["elements"][0]["children"]
            self.assertEqual(["Page1", "Page2"], [page["page"] for page in pages])
            self.assertEqual(["Page1", "Page2"], [page["title"] for page in pages])
            self.assertEqual("First", pages[0]["children"][0]["label"])
            self.assertEqual("Second", pages[1]["children"][0]["input"])

            presentation_dsl = {
                "title": "Presentation",
                "attributes": [
                    {"name": "Период", "type": "StandardPeriod"},
                    {"name": "Подпись", "type": "string"},
                    {"name": "Группировка", "type": "string"},
                ],
                "commands": [{"name": "Выполнить", "action": "Выполнить"}],
                "elements": [
                    {
                        "group": "horizontal",
                        "name": "Параметры",
                        "showTitle": False,
                        "verticalStretch": False,
                        "children": [
                            {"group": "vertical", "name": "Раздел", "title": "Тип отчета", "showTitle": True},
                            {"input": "Период", "path": "Период", "title": "Период:", "choiceButton": True},
                            {
                                "input": "Подпись",
                                "path": "Подпись",
                                "listChoiceMode": True,
                                "choices": [{"title": "Иванов И.И.", "value": "Иванов И.И.", "type": "string"}],
                            },
                            {"label": "Предупреждение", "title": "Важно", "textColor": "#FF0000"},
                            {"progress": "Ход", "path": "Ход", "titleLocation": "none"},
                            {
                                "radio": "ПоДокументам",
                                "path": "Группировка",
                                "titleLocation": "none",
                                "choices": [{"title": "по документам", "value": "Документ", "type": "string"}],
                            },
                            {
                                "table": "Строки",
                                "path": "Строки",
                                "commandBarButtons": [
                                    {
                                        "button": "ОтметитьВсе",
                                        "type": "commandBar",
                                        "command": "ОтметитьВсе",
                                        "picture": "StdPicture.CheckAll",
                                        "representation": "picture",
                                    },
                                    {
                                        "button": "СнятьОтметки",
                                        "type": "commandBar",
                                        "command": "СнятьОтметки",
                                        "picture": "StdPicture.UncheckAll",
                                        "representation": "picture",
                                    },
                                ],
                            },
                            {
                                "popup": "Печать",
                                "title": "Печать",
                                "children": [
                                    {"button": "ПечатьПолный", "command": "Выполнить", "title": "Печать (развернутый)"},
                                    {
                                        "button": "ПечатьСвернутый",
                                        "command": "Выполнить",
                                        "title": "Печать (свернутый)",
                                    },
                                ],
                            },
                            {"button": "Выполнить", "command": "Выполнить", "defaultButton": True},
                        ],
                    }
                ],
            }
            xml = metadata_form_compile.render_form(presentation_dsl).decode("utf-8-sig")
            self.assertIn("<v8:Type>v8:StandardPeriod</v8:Type>", xml)
            self.assertIn("<VerticalStretch>false</VerticalStretch>", xml)
            self.assertIn("<ShowTitle>false</ShowTitle>", xml)
            self.assertIn("<ShowTitle>true</ShowTitle>", xml)
            self.assertIn("<v8:content>Период</v8:content>", xml)
            self.assertNotIn("<v8:content>Период:</v8:content>", xml)
            self.assertIn("<ChoiceButton>true</ChoiceButton>", xml)
            self.assertIn("<ListChoiceMode>true</ListChoiceMode>", xml)
            self.assertIn("<v8:content>Иванов И.И.</v8:content>", xml)
            self.assertIn("<TextColor>#FF0000</TextColor>", xml)
            self.assertIn('<ProgressBarField name="Ход"', xml)
            self.assertIn("<TitleLocation>None</TitleLocation>", xml)
            radio_xml = xml[xml.index('<RadioButtonField name="ПоДокументам"') : xml.index("</RadioButtonField>")]
            self.assertIn("<TitleLocation>None</TitleLocation>", radio_xml)
            self.assertEqual(
                "CatalogRef.Пользователи", conversion.OPAQUE_FORM_TYPES["bb356e79-e8e6-4912-8561-ad29cca2604f"]
            )
            self.assertIn("StdPicture.CheckAll", xml)
            self.assertIn("StdPicture.UncheckAll", xml)
            self.assertIn("<Representation>Picture</Representation>", xml)
            self.assertIn("<DefaultButton>true</DefaultButton>", xml)
            self.assertIn('<Popup name="Печать"', xml)
            self.assertIn("<v8:content>Печать (развернутый)</v8:content>", xml)
            self.assertIn("<v8:content>Печать (свернутый)</v8:content>", xml)
            color_raw = [
                None,
                None,
                [
                    None,
                    [
                        [None, None, None, ["3", "0", ["255"]]],
                    ],
                ],
            ]
            self.assertEqual("#FF0000", conversion._text_color(color_raw))
            command_raw = [None, None, [None, ["ru", "Подбор", "КомандаПодбор"]]]
            self.assertEqual(
                [("КомандаПодбор", "Подбор", "КомандаПодбор")],
                conversion._command_panel_buttons(command_raw, {"КомандаПодбор"}),
            )

            def command_definition(identifier: str, handler: str) -> list[object]:
                return ["7", identifier, "1", "command", ["3", f'"{handler}"'], "0", "1"]

            def command_item(name: str, title: str, parent: str) -> list[object]:
                return ["8", f'"{name}"', "0", "1", ["1", "1", ['"ru"', f'"{title}"']], "1", parent]

            print_group = [
                "5",
                "print-group",
                "2",
                "0",
                "4",
                "print-full",
                command_item("ПечатьПолный", "Печать (развернутый)", "print-group"),
                "print-short",
                command_item("ПечатьСвернутый", "Печать (свернутый)", "print-group"),
            ]
            root_group = [
                "5",
                "root-group",
                "1",
                "0",
                "4",
                "print-link",
                command_item("Печать", "Печать", "root-group"),
            ]
            payload = [
                "5",
                "wrapper",
                "0",
                "0",
                "0",
                command_definition("print-full", "ПечатьПолный"),
                command_definition("print-short", "ПечатьСвернутый"),
                ["7", "print-link", "1", "group", ["1", "print-group", "6"], "0", "1"],
                "2",
                print_group,
                root_group,
            ]
            tree_raw: list[Any] = [None, None, [None, [None] * 8]]
            tree_raw[2][1][7] = payload
            self.assertEqual(
                [
                    {
                        "popup": "Печать",
                        "title": "Печать",
                        "children": [
                            {
                                "button": "ПечатьПолный",
                                "command": "ПечатьПолный",
                                "title": "Печать (развернутый)",
                                "_action": "ПечатьПолный",
                            },
                            {
                                "button": "ПечатьСвернутый",
                                "command": "ПечатьСвернутый",
                                "title": "Печать (свернутый)",
                                "_action": "ПечатьСвернутый",
                            },
                        ],
                    }
                ],
                conversion._command_panel_tree(tree_raw, {"ПечатьПолный", "ПечатьСвернутый"}),
            )

            select_group = [
                "5",
                "select-group",
                "3",
                "0",
                "5",
                "select-all",
                command_item("ВыделитьВсе", "Выделить все", "select-group"),
                "clear-all",
                command_item("УбратьВыделениеВсе", "Убрать выделение все", "select-group"),
                "invert",
                command_item("ИнвертироватьВыделение", "Инвертировать выделение", "select-group"),
            ]
            select_payload = [
                "5",
                "wrapper",
                "0",
                "0",
                "0",
                ["6", "select-all", "1", "command", ["3", '"ВыделитьВсе"'], "1", ["4", "1", ["-10"]]],
                ["6", "clear-all", "1", "command", ["3", '"УбратьВыделениеВсе"'], "1", ["4", "1", ["-11"]]],
                ["6", "invert", "1", "command", ["3", '"ИнвертироватьВыделение"'], "1"],
                "2",
                select_group,
            ]
            select_raw: list[Any] = [None, None, [None, [None] * 8]]
            select_raw[2][1][7] = select_payload
            self.assertEqual(
                [
                    {
                        "button": "ВыделитьВсе",
                        "command": "ВыделитьВсе",
                        "title": "Выделить все",
                        "_action": "ВыделитьВсе",
                        "picture": "StdPicture.CheckAll",
                        "representation": "picture",
                    },
                    {
                        "button": "УбратьВыделениеВсе",
                        "command": "УбратьВыделениеВсе",
                        "title": "Убрать выделение все",
                        "_action": "УбратьВыделениеВсе",
                        "picture": "StdPicture.UncheckAll",
                        "representation": "picture",
                    },
                    {
                        "button": "ИнвертироватьВыделение",
                        "command": "ИнвертироватьВыделение",
                        "title": "Инвертировать выделение",
                        "_action": "ИнвертироватьВыделение",
                    },
                ],
                conversion._command_panel_tree(
                    select_raw, {"ВыделитьВсе", "УбратьВыделениеВсе", "ИнвертироватьВыделение"}
                ),
            )

            actual_select_payload = [
                "5",
                "wrapper-actual",
                "0",
                "0",
                "0",
                [
                    "7",
                    "select-all-actual",
                    "1",
                    "command",
                    ["3", '"ВыделитьВсе"', ["1", '"ВыделитьВсе"', ["1", "1", ['"ru"', '"Выделить все"']]]],
                    "1",
                    ["4", "1", ["-10"]],
                    "2",
                ],
                [
                    "7",
                    "clear-all-actual",
                    "1",
                    "command",
                    [
                        "3",
                        '"УбратьВыделениеВсе"',
                        ["1", '"УбратьВыделениеВсе"', ["1", "1", ['"ru"', '"Убрать выделение все"']]],
                    ],
                    "1",
                    ["4", "1", ["-11"]],
                    "2",
                ],
                [
                    "7",
                    "invert-actual",
                    "1",
                    "command",
                    [
                        "3",
                        '"ИнвертироватьВыделение"',
                        ["1", '"ИнвертироватьВыделение"', ["1", "1", ['"ru"', '"Инвертировать выделение"']]],
                    ],
                    "1",
                    "2",
                ],
                "1",
                [
                    "5",
                    "actual-group",
                    "2",
                    "0",
                    "3",
                    "select-all-actual",
                    command_item("ВыделитьВсе", "Выделить все", "actual-group"),
                    "clear-all-actual",
                    [
                        "8",
                        '"УбратьВыделениеВсе"',
                        "0",
                        "1",
                        ["1", "1", ['"#"', '"Убрать выделение все"']],
                        "0",
                        "actual-group",
                    ],
                    "invert-actual",
                    command_item("ИнвертироватьВыделение", "Инвертировать выделение", "actual-group"),
                ],
            ]
            actual_select_raw: list[Any] = [None, None, [None, [None] * 8]]
            actual_select_raw[2][1][7] = actual_select_payload
            self.assertEqual(
                [
                    {
                        "button": "ВыделитьВсе",
                        "command": "ВыделитьВсе",
                        "title": "Выделить все",
                        "_action": "ВыделитьВсе",
                        "picture": "StdPicture.CheckAll",
                        "representation": "picture",
                    },
                    {
                        "button": "УбратьВыделениеВсе",
                        "command": "УбратьВыделениеВсе",
                        "title": "Убрать выделение все",
                        "_action": "УбратьВыделениеВсе",
                        "picture": "StdPicture.UncheckAll",
                        "representation": "picture",
                    },
                    {
                        "button": "ИнвертироватьВыделение",
                        "command": "ИнвертироватьВыделение",
                        "title": "Инвертировать выделение",
                        "_action": "ИнвертироватьВыделение",
                    },
                ],
                conversion._command_panel_tree(
                    actual_select_raw, {"ВыделитьВсе", "УбратьВыделениеВсе", "ИнвертироватьВыделение"}
                ),
            )

            actual_select_raw.append(["14", '"КоманднаяПанель2"', "27", "0", "0", "0"])
            table_panel = conversion.SourceForm(
                "TablePanel",
                root,
                {},
                {
                    "props": [{"name": "ОбработкаОбъект"}],
                    "commands": [],
                    "tree": [
                        {"name": "СписокДокументов", "type": "Table", "page": "Page1"},
                        {"name": "КоманднаяПанель2", "type": "CommandPanel", "page": "Page1"},
                    ],
                    "data": {
                        "-pages-": ["Page1"],
                        "Page1/СписокДокументов": {"id": "27", "prop": "ОбработкаОбъект", "raw": ["НомерСтроки"]},
                        "Page1/КоманднаяПанель2": {"id": "29", "raw": actual_select_raw},
                    },
                },
            )
            table_panel_dsl, table_panel_diagnostics, _coverage, _outcomes = cast(
                Any,
                conversion._form_dsl(
                    table_panel,
                    {"ВыделитьВсе", "УбратьВыделениеВсе", "ИнвертироватьВыделение"},
                    "ExternalDataProcessor",
                    "Test",
                    [
                        {"kind": "tabular-section", "name": "СписокДокументов"},
                        {"kind": "column", "owner": "СписокДокументов", "name": "Выгружать"},
                    ],
                ),
            )
            self.assertEqual([], table_panel_diagnostics)
            table = next(
                item for item in table_panel_dsl["elements"][0]["children"] if item.get("table") == "СписокДокументов"
            )
            self.assertEqual(
                ["ВыделитьВсе", "УбратьВыделениеВсе", "ИнвертироватьВыделение"],
                [item["button"] for item in table["commandBarButtons"]],
            )

            fallback_panel = conversion.SourceForm(
                "FallbackTablePanel",
                root,
                {},
                {
                    "props": [{"name": "ОбработкаОбъект"}],
                    "commands": [],
                    "tree": [
                        {"name": "СписокДокументов", "type": "Table", "page": "Page1"},
                        {"name": "КоманднаяПанельСписокДокументов", "type": "CommandPanel", "page": "Page1"},
                    ],
                    "data": {
                        "-pages-": ["Page1"],
                        "Page1/СписокДокументов": {"id": "27", "prop": "ОбработкаОбъект", "raw": ["НомерСтроки"]},
                        "Page1/КоманднаяПанельСписокДокументов": {"id": "29", "raw": actual_select_raw[:-1]},
                    },
                },
            )
            fallback_dsl, fallback_diagnostics, _coverage, _outcomes = cast(
                Any,
                conversion._form_dsl(
                    fallback_panel,
                    {"ВыделитьВсе", "УбратьВыделениеВсе", "ИнвертироватьВыделение"},
                    "ExternalDataProcessor",
                    "Test",
                    [
                        {"kind": "tabular-section", "name": "СписокДокументов"},
                        {"kind": "column", "owner": "СписокДокументов", "name": "Выгружать"},
                    ],
                ),
            )
            self.assertEqual([], fallback_diagnostics)
            fallback_table = next(
                item for item in fallback_dsl["elements"][0]["children"] if item.get("table") == "СписокДокументов"
            )
            self.assertEqual(3, len(fallback_table["commandBarButtons"]))

            choice_raw: list[Any] = [None, None, [None, [None] * 27]]
            choice_raw[2][1][26] = [
                None,
                None,
                [
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    [
                        "1",
                        "2",
                        [None, None, None, ["S", "Иванов И.И."], ["ru", "Иванов И.И."]],
                    ],
                ],
            ]
            typed = conversion.SourceForm(
                "Typed",
                root,
                {},
                {
                    "props": [{"name": "ОбработкаОбъект"}, {"name": "Дата1", "raw": ["Pattern", "D"]}],
                    "commands": [],
                    "tree": [
                        {"name": "Дата1", "type": "Field", "page": "Page1"},
                        {"name": "Раздел", "type": "Group", "page": "Page1"},
                        {"name": "Выбор", "type": "SelectField", "page": "Page1"},
                    ],
                    "data": {
                        "-pages-": ["Page1"],
                        "Page1/Дата1": {"prop": "Дата1", "raw": []},
                        "Page1/Раздел": {"raw": ["ru", "Дополнительные фильтры"]},
                        "Page1/Выбор": {"prop": "ОбработкаОбъект", "raw": choice_raw},
                    },
                },
            )
            typed_dsl, diagnostics, _coverage, _outcomes = cast(
                Any, conversion._form_dsl(typed, set(), "ExternalDataProcessor", "Test", [])
            )
            self.assertEqual([], diagnostics)
            self.assertFalse(typed_dsl["elements"][0]["showTitle"])
            self.assertEqual(
                {"Дата1": "date", "Выбор": "string"},
                {item["name"]: item["type"] for item in typed_dsl["attributes"] if not item.get("main")},
            )
            typed_choice = next(item for item in typed_dsl["elements"][0]["children"] if item.get("input") == "Выбор")
            self.assertEqual(
                (True, [{"title": "Иванов И.И.", "value": "Иванов И.И.", "type": "string"}]),
                (typed_choice["listChoiceMode"], typed_choice["choices"]),
            )
            titled_group = next(item for item in typed_dsl["elements"][0]["children"] if item.get("name") == "Раздел")
            self.assertEqual(
                ("vertical", "Дополнительные фильтры", True),
                (titled_group["group"], titled_group["title"], titled_group["showTitle"]),
            )
            arranged = _arrange_page(
                [
                    ({"group": "vertical", "name": "Левая", "title": "Колонки"}, (0, 0, 40, 100), 0),
                    ({"check": "ЛевыйФлажок"}, (5, 20, 35, 30), 1),
                    ({"group": "vertical", "name": "Правая", "title": "Отборы"}, (50, 0, 100, 100), 2),
                    ({"input": "ПравоеПоле"}, (55, 20, 95, 30), 3),
                ]
            )
            sibling_groups = cast(Any, arranged[0]["children"])
            self.assertEqual(["ЛевыйФлажок"], [item["check"] for item in sibling_groups[0]["children"]])
            self.assertEqual(["ПравоеПоле"], [item["input"] for item in sibling_groups[1]["children"]])
            bottom_command_bar = _arrange_page(
                [
                    ({"label": "НадписьНаДату"}, (8, 33, 50, 52), 0),
                    ({"input": "НаДату"}, (56, 33, 136, 52), 1),
                    ({"spreadsheet": "Результат"}, (8, 57, 492, 367), 2),
                    ({"cmdBar": "ОсновныеДействияФормы"}, (0, 375, 500, 400), 3),
                ]
            )
            date_row = cast(Any, next(item for item in bottom_command_bar if item.get("group") == "horizontal"))
            self.assertEqual(
                ["НадписьНаДату", "НаДату"],
                [item.get("label") or item.get("input") for item in date_row["children"]],
            )
            side_column = _arrange_page(
                [
                    ({"table": "Контрагенты"}, (8, 80, 318, 129), 0),
                    ({"table": "Статусы"}, (320, 80, 566, 129), 1),
                    ({"label": "НадписьДоговор"}, (569, 58, 702, 77), 2),
                    ({"input": "Договор"}, (706, 58, 879, 77), 3),
                    ({"label": "НадписьКорСчет"}, (569, 82, 702, 101), 4),
                    ({"input": "КорСчет"}, (706, 82, 879, 101), 5),
                    ({"label": "НадписьТип"}, (569, 104, 702, 123), 6),
                    ({"input": "ТипДокумента"}, (706, 104, 879, 123), 7),
                ]
            )

            def find_side_column(items: list[dict[str, Any]]) -> dict[str, Any] | None:
                for item in items:
                    if item.get("name") == "Колонка2":
                        return item
                    found = find_side_column(item.get("children", []))
                    if found:
                        return found
                return None

            side_group = find_side_column(side_column)
            assert side_group is not None
            label_column, input_column = side_group["children"]
            self.assertEqual("horizontal", side_group["group"])
            self.assertEqual(
                ["НадписьДоговор", "НадписьКорСчет", "НадписьТип"],
                [child["label"] for child in label_column["children"]],
            )
            self.assertEqual(
                ["Договор", "КорСчет", "ТипДокумента"],
                [child["input"] for child in input_column["children"]],
            )

            def collect_group_names(items: list[dict[str, Any]]) -> list[str]:
                return [
                    name
                    for item in items
                    for name in ([item["name"]] if "group" in item else [])
                    + collect_group_names(item.get("children", []))
                ]

            group_names = collect_group_names(side_column)
            self.assertEqual(len(group_names), len(set(group_names)))
            self.assertEqual([], typed_dsl["commands"])

            def flatten(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
                return [element for item in elements for element in [item, *flatten(item.get("children", []))]]

            main_group = [
                "5",
                "main-group",
                "2",
                "0",
                "3",
                "run",
                command_item("КнопкаВыполнить", "Выполнить", "main-group"),
                "export",
                command_item("Выгрузить", "Выгрузить", "main-group"),
            ]
            main_payload = [
                "5",
                "wrapper-main",
                "0",
                "0",
                "0",
                command_definition("run", "КнопкаВыполнитьНажатие"),
                command_definition("export", "ВыгрузитьНажатие"),
                "1",
                main_group,
            ]
            main_raw: list[Any] = [None, None, [None, [None] * 8]]
            main_raw[2][1][7] = main_payload
            interactions = conversion.SourceForm(
                "Interactions",
                root,
                {},
                {
                    "props": [
                        {"name": "ОбработкаОбъект"},
                        {"name": "СчетУчета", "raw": ["Pattern", "6f58a5c7-f511-498f-abeb-390cf5afab39"]},
                        {"name": "ИмяФайла", "raw": ["Pattern", "S"]},
                    ],
                    "commands": [],
                    "tree": [
                        {"name": "СчетУчета", "type": "Field", "page": "Page1"},
                        {"name": "ИмяФайла", "type": "Field", "page": "Page1"},
                        {"name": "КнопкаПересчет", "type": "Button", "page": "Page1"},
                        {"name": "КнопкаБезЗаголовка", "type": "Button", "page": "Page1"},
                        {"name": "ОсновныеДействияФормы", "type": "CommandPanel", "page": "Page1"},
                    ],
                    "data": {
                        "-pages-": ["Page1"],
                        "Page1/СчетУчета": {"prop": "СчетУчета", "raw": []},
                        "Page1/ИмяФайла": {"prop": "ИмяФайла", "raw": ["ИмяФайлаНачалоВыбора"]},
                        "Page1/КнопкаПересчет": {"raw": ["ru", "Пересчитать", "КнопкаПересчетНажатие"]},
                        "Page1/КнопкаБезЗаголовка": {"raw": ["КнопкаБезЗаголовкаНажатие"]},
                        "Page1/ОсновныеДействияФормы": {"raw": main_raw},
                    },
                },
            )
            interactions_dsl, interactions_diagnostics, _coverage, _outcomes = cast(
                Any,
                conversion._form_dsl(
                    interactions,
                    {
                        "ИмяФайлаНачалоВыбора",
                        "КнопкаПересчетНажатие",
                        "КнопкаБезЗаголовкаНажатие",
                        "КнопкаВыполнитьНажатие",
                        "ВыгрузитьНажатие",
                    },
                    "ExternalDataProcessor",
                    "Test",
                    [],
                ),
            )
            self.assertEqual([], interactions_diagnostics)
            self.assertEqual(
                "ChartOfAccountsRef.Хозрасчетный",
                next(item["type"] for item in interactions_dsl["attributes"] if item["name"] == "СчетУчета"),
            )
            self.assertEqual(
                "DocumentRef.ПоступлениеТоваровУслуг",
                conversion.OPAQUE_FORM_TYPES["57289853-6dd7-4527-87a8-a23fa8981f5f"],
            )
            interaction_elements = flatten(interactions_dsl["elements"])
            file_field = next(item for item in interaction_elements if item.get("input") == "ИмяФайла")
            self.assertEqual({"StartChoice": "ИмяФайлаНачалоВыбора"}, file_field["handlers"])
            self.assertTrue(file_field["choiceButton"])
            execute_button = next(item for item in interaction_elements if item.get("button") == "КнопкаВыполнить")
            self.assertTrue(execute_button["defaultButton"])
            export_button = next(item for item in interaction_elements if item.get("button") == "Выгрузить")
            self.assertNotIn("defaultButton", export_button)
            recalculate_button = next(item for item in interaction_elements if item.get("button") == "КнопкаПересчет")
            self.assertEqual("Пересчитать", recalculate_button["title"])
            untitled_button = next(item for item in interaction_elements if item.get("button") == "КнопкаБезЗаголовка")
            self.assertNotIn("title", untitled_button)
            unknown = conversion.SourceForm(
                "Unknown",
                root,
                {},
                {
                    "props": [
                        {"name": "ОбработкаОбъект"},
                        {"name": "НеизвестныйТип", "raw": ["Pattern", "00000000-0000-0000-0000-000000000001"]},
                    ],
                    "commands": [],
                    "tree": [],
                    "data": {"-pages-": ["Page1"]},
                },
            )
            unknown_dsl, unknown_diagnostics, _coverage, _outcomes = cast(
                Any, conversion._form_dsl(unknown, set(), "ExternalDataProcessor", "Test", [])
            )
            self.assertEqual("unsupported-form-property", unknown_diagnostics[0]["code"])
            self.assertNotIn("НеизвестныйТип", {item["name"] for item in unknown_dsl["attributes"]})

            ambiguous = conversion.SourceForm(
                "Ambiguous",
                root,
                {},
                {
                    "props": [{"name": "ОбработкаОбъект"}],
                    "commands": [],
                    "tree": [
                        {"name": "Надпись1", "type": "Label", "page": "Page1"},
                        {"name": "Надпись2", "type": "Label", "page": "Page1"},
                        {"name": "Поле", "type": "Field", "page": "Page1"},
                    ],
                    "data": {
                        "-pages-": ["Page1"],
                        "Page1/Надпись1": {"raw": ["Первый:", [], [], ["8", "0", "0", "20", "10"]]},
                        "Page1/Надпись2": {"raw": ["Второй:", [], [], ["8", "21", "0", "40", "10"]]},
                        "Page1/Поле": {"prop": "ОбработкаОбъект", "raw": [[], [], [], ["8", "41", "0", "80", "10"]]},
                    },
                },
            )
            _dsl, ambiguous_diagnostics, _coverage, ambiguous_outcomes = cast(
                Any, conversion._form_dsl(ambiguous, set(), "ExternalDataProcessor", "Test")
            )
            self.assertIn("ambiguous-field-label", {item["code"] for item in ambiguous_diagnostics})
            self.assertIn(
                "manual", {item["outcome"] for item in ambiguous_outcomes if item["category"] == "presentation"}
            )
            ambiguous_elements = flatten(_dsl["elements"])
            self.assertEqual(
                {"Надпись1": 2, "Надпись2": 2},
                {item["label"]: item["width"] for item in ambiguous_elements if "label" in item},
            )

            def radio_raw(
                title: str, value: str, rectangle: tuple[int, int, int, int] | None = None, value_type: str = "N"
            ) -> list[object]:
                encoded_value = f'"{value}"' if value_type == "S" else value
                raw = [
                    None,
                    None,
                    [
                        "4",
                        ['"Pattern"'],
                        [[None, None, ["1", "1", ['"ru"', f'"{title}"']]], "2", "0", "0"],
                        "0",
                        [f'"{value_type}"', encoded_value],
                    ],
                ]
                if rectangle:
                    raw.append(["8", *(str(value) for value in rectangle)])
                return raw

            def table_raw(columns: list[tuple[str, str]]) -> list[object]:
                payload = [None, None, [None, [None] * 24, [None, [None] * 31]]]
                entries: list[object] = ["4"]
                for name, title in columns:
                    column: list[Any] = [""] * 31
                    column[1] = ["1", "1", ["ru", title]]
                    column[30] = name
                    entries.append(["id", ["8", ["8", column], name, "", "", ""]])
                payload[2][2][1][23] = entries
                return payload

            registry = conversion.SourceForm(
                "Registry",
                root,
                {},
                {
                    "props": [
                        {"name": "ОбработкаОбъект"},
                        {"name": "Реестр", "raw": ["Pattern", "#"]},
                        {"name": "ПереключательDBF", "raw": ["Pattern", "N"]},
                    ],
                    "commands": [],
                    "tree": [
                        {"name": "ПереключательDBF", "type": "RadioBtn", "page": "Page1"},
                        {"name": "ПереключательExcel", "type": "RadioBtn", "page": "Page1"},
                        {"name": "Реестр", "type": "Table", "page": "Page1"},
                    ],
                    "data": {
                        "-pages-": ["Page1"],
                        "Page1/ПереключательDBF": {"prop": "ПереключательDBF", "raw": radio_raw("DBF", "0")},
                        "Page1/ПереключательExcel": {"raw": radio_raw("Excel", "1")},
                        "Page1/Реестр": {
                            "prop": "Реестр",
                            "raw": table_raw(
                                [
                                    ("СчетФактураВыданная", "Счет-фактура выданная"),
                                    ("ДатаВходящегоДокумента", "Дата вх. документа"),
                                ]
                            ),
                        },
                    },
                },
            )
            registry_dsl, registry_diagnostics, _coverage, _outcomes = cast(
                Any, conversion._form_dsl(registry, set(), "ExternalDataProcessor", "Test", [])
            )
            registry_elements = flatten(registry_dsl["elements"])
            self.assertEqual([], registry_diagnostics)
            self.assertEqual(
                [("DBF", "0", "number"), ("Excel", "1", "number")],
                [
                    (item["choices"][0]["title"], item["choices"][0]["value"], item["choices"][0]["type"])
                    for item in registry_elements
                    if "radio" in item
                ],
            )
            self.assertTrue(all(item["titleLocation"] == "none" for item in registry_elements if "radio" in item))
            object_radio = conversion.SourceForm(
                "ObjectRadio",
                root,
                {},
                {
                    "props": [{"name": "ОтчетОбъект"}],
                    "commands": [],
                    "tree": [
                        {"name": "ПоДокументам", "type": "RadioBtn", "page": "Page1"},
                        {"name": "РамкаГруппировки", "type": "Group", "page": "Page1"},
                        {"name": "ПоТипамСканов", "type": "RadioBtn", "page": "Page1"},
                    ],
                    "data": {
                        "-pages-": ["Page1"],
                        "Page1/ПоДокументам": {
                            "prop": "ОтчетОбъект",
                            "raw": radio_raw("По документам", "Документ", (16, 75, 156, 94), "S"),
                        },
                        "Page1/РамкаГруппировки": {"raw": ["Группировка", None, None, ["8", "8", "58", "311", "101"]]},
                        "Page1/ПоТипамСканов": {
                            "raw": radio_raw("По типам сканов", "ТипСкана", (161, 75, 301, 94), "S")
                        },
                    },
                },
            )
            object_radio_dsl, object_radio_diagnostics, _coverage, _outcomes = cast(
                Any,
                conversion._form_dsl(
                    object_radio,
                    set(),
                    "ExternalReport",
                    "Test",
                    [{"kind": "attribute", "name": "Группировка", "type": "xs:string"}],
                ),
            )
            object_radio_elements = flatten(object_radio_dsl["elements"])
            object_radios = [item for item in object_radio_elements if "radio" in item]
            self.assertEqual([], object_radio_diagnostics)
            self.assertEqual(["ОтчетОбъект.Группировка"] * 2, [item["path"] for item in object_radios])
            self.assertEqual(["Документ", "ТипСкана"], [item["choices"][0]["value"] for item in object_radios])
            self.assertTrue(all(item["titleLocation"] == "none" for item in object_radios))
            self.assertTrue(
                any(
                    item.get("group") == "horizontal"
                    and len([child for child in item.get("children", []) if "radio" in child]) == 2
                    for item in object_radio_elements
                )
            )
            registry_attribute = next(item for item in registry_dsl["attributes"] if item["name"] == "Реестр")
            self.assertEqual(
                ("ValueTable", ["СчетФактураВыданная", "ДатаВходящегоДокумента"]),
                (
                    registry_attribute["type"],
                    [item["name"] for item in registry_attribute["columns"]],
                ),
            )
            self.assertEqual(
                ["Счет-фактура выданная", "Дата вх. документа"],
                [item["title"] for item in registry_attribute["columns"]],
            )

            missing_data = conversion.SourceForm(
                "MissingData",
                root,
                {},
                {
                    "props": [{"name": "ОбработкаОбъект"}],
                    "commands": [],
                    "tree": [
                        {"name": "ДокументыНаЭкспорт", "type": "Table", "page": "Page1"},
                        {"name": "СчетОрганизации", "type": "Field", "page": "Page1"},
                        {"name": "СчетОрганизации1", "type": "Field", "page": "Page1"},
                        {"name": "ВидДеятельности", "type": "Field", "page": "Page1"},
                        {"name": "Картинка1", "type": "Image", "page": "Page1"},
                    ],
                    "data": {
                        "-pages-": ["Page1"],
                        "Page1/ДокументыНаЭкспорт": {"prop": "ОбработкаОбъект", "raw": ["Номер", "Дата"]},
                        "Page1/СчетОрганизации": {
                            "prop": "ОбработкаОбъект",
                            "raw": ["Pattern", "6cb9f3e2-00cb-4e6e-9f35-618d6eac528f"],
                        },
                        "Page1/СчетОрганизации1": {
                            "prop": "ОбработкаОбъект",
                            "raw": ["Pattern", "6cb9f3e2-00cb-4e6e-9f35-618d6eac528f"],
                        },
                        "Page1/ВидДеятельности": {
                            "prop": "ОбработкаОбъект",
                            "raw": ["Pattern", "unknown-reference-type"],
                        },
                        "Page1/Картинка1": {"raw": []},
                    },
                },
            )
            missing_dsl, missing_diagnostics, _coverage, missing_outcomes = cast(
                Any, conversion._form_dsl(missing_data, set(), "ExternalDataProcessor", "Test", [])
            )
            self.assertEqual(["missing-object-data"], [item["code"] for item in missing_diagnostics])
            self.assertEqual(
                {
                    "ДокументыНаЭкспорт": "ValueTable",
                    "СчетОрганизации": "CatalogRef.БанковскиеСчета",
                    "СчетОрганизации1": "CatalogRef.БанковскиеСчета",
                },
                {item["name"]: item["type"] for item in missing_dsl["attributes"] if not item.get("main")},
            )
            self.assertIn(
                {"category": "element", "path": "form/MissingData/element/4", "outcome": "excluded"},
                missing_outcomes,
            )

            command_only = conversion.SourceForm(
                "CommandOnly",
                root,
                {},
                {
                    "props": [{"name": "ОбработкаОбъект"}],
                    "commands": [],
                    "tree": [{"name": "ОсновныеДействия", "type": "CommandPanel", "page": "Page1"}],
                    "data": {"-pages-": ["Page1"], "Page1/ОсновныеДействия": {"raw": ["СформироватьНажатие"]}},
                },
            )
            command_dsl, command_diagnostics, _coverage, _outcomes = cast(
                Any, conversion._form_dsl(command_only, {"СформироватьНажатие"}, "ExternalDataProcessor", "Test", [])
            )
            self.assertEqual([], command_diagnostics)
            self.assertEqual(
                [{"button": "Сформировать", "command": "Сформировать", "title": "Сформировать"}],
                command_dsl["elements"][0]["children"][0]["children"],
            )

    def test_designer_ordinary_report_matches_golden(self) -> None:
        # Needs a real ordinary report published by publish-sources; set ORDINARY_FORM_REPORT_SOURCE to use another tree.
        inv11_root = Path(
            os.environ.get("ORDINARY_FORM_REPORT_SOURCE")
            or Path(__file__).parents[2] / "src" / "erf" / "ordinary" / "ИНВ11.v8unpack"
        )
        if not inv11_root.is_dir():
            self.skipTest(f"ordinary report source is not available: {inv11_root}")

        def flatten(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [element for item in elements for element in [item, *flatten(item.get("children", []))]]

        kind, metadata, forms = conversion._read_source(inv11_root)
        inv11 = forms[0]
        inv11_dsl, inv11_diagnostics, inv11_coverage, inv11_outcomes = cast(
            Any,
            conversion._form_dsl(
                inv11,
                {cast(str, item["name"]) for item in conversion._procedures(inv11.directory / "Form.obj.bsl")},
                kind,
                metadata["name"],
            ),
        )
        elements = flatten(inv11_dsl["elements"])
        by_name = cast(
            Any,
            {
                element.get("name")
                or next(value for key, value in element.items() if key in conversion.ELEMENT_TYPES.values()): element
                for element in elements
                if any(key in conversion.ELEMENT_TYPES.values() for key in element)
            },
        )
        self.assertEqual([], inv11_diagnostics)
        self.assertEqual("none", by_name["НомерАкта"]["titleLocation"])
        self.assertEqual("none", by_name["ДатаНачалаИнвентаризации"]["titleLocation"])
        self.assertEqual(
            {"Номер:", "от:"},
            {by_name[name]["title"] for name in ("НадписьНомерИнвентаризации", "НадписьДатаНачалаИнвентаризации")},
        )
        self.assertEqual(
            ("normal", False), (by_name["РамкаГруппы1"]["representation"], by_name["РамкаГруппы1"]["showTitle"])
        )
        self.assertEqual("Печать", by_name["ОсновныеДействияФормы"]["children"][0]["title"])
        self.assertEqual({"OnOpen": "ПриОткрытии"}, inv11_dsl["events"])
        presentation_paths = {item["path"] for item in inv11_outcomes if item["category"] == "presentation"}
        self.assertTrue(
            {
                "form/ФормаОтчета/element/23/presentation/separate-label",
                "form/ФормаОтчета/element/23/presentation/field-title",
                "form/ФормаОтчета/element/1/presentation/КнопкаСформировать/title",
                "form/ФормаОтчета/element/1/presentation/КнопкаСформировать/panel-membership",
            }.issubset(presentation_paths)
        )
        self.assertEqual(
            inv11_coverage["input"], sum(inv11_coverage[key] for key in ("converted", "manual", "excluded"))
        )
        self.assertEqual(len(inv11_outcomes), len({item["path"] for item in inv11_outcomes}))

    def test_repeated_command_buttons_have_unique_coverage_and_one_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            form = conversion.SourceForm(
                "Repeated",
                Path(temp),
                {},
                {
                    "props": [{"name": "ОбработкаОбъект"}],
                    "commands": [],
                    "tree": [{"name": "ОсновныеДействия", "type": "CommandPanel", "page": "Page1"}],
                    "data": {"-pages-": ["Page1"], "Page1/ОсновныеДействия": {"raw": []}},
                },
            )
            repeated = [
                {"button": "Выполнить", "command": "Выполнить", "title": "Выполнить", "_action": "Выполнить"},
                {"button": "Выполнить", "command": "Выполнить", "title": "Повторить", "_action": "Выполнить"},
            ]
            with patch("scripts.python.ordinary_form_conversion._command_panel_tree", return_value=repeated):
                first = conversion._form_dsl(form, {"Выполнить"}, "ExternalDataProcessor", "Test", [])
                second = conversion._form_dsl(form, {"Выполнить"}, "ExternalDataProcessor", "Test", [])
            dsl, diagnostics, coverage, outcomes = cast(Any, first)
            self.assertEqual([], diagnostics)
            self.assertEqual([{"name": "Выполнить", "action": "Выполнить"}], dsl["commands"])
            self.assertEqual(
                [("Выполнить", "Выполнить"), ("Выполнить", "Повторить")],
                [(item["command"], item["title"]) for item in dsl["elements"][0]["children"][0]["children"]],
            )
            self.assertEqual(len(outcomes), len({item["path"] for item in outcomes}))
            self.assertEqual(coverage["input"], sum(coverage[key] for key in ("converted", "manual", "excluded")))
            self.assertEqual(outcomes, second[3])

            conflicting = [*repeated[:1], {**repeated[1], "_action": "ДругоеДействие"}]
            with patch("scripts.python.ordinary_form_conversion._command_panel_tree", return_value=conflicting):
                conflict_dsl, conflict_diagnostics, _coverage, conflict_outcomes = conversion._form_dsl(
                    form, {"Выполнить", "ДругоеДействие"}, "ExternalDataProcessor", "Test", []
                )
            self.assertEqual([{"name": "Выполнить", "action": "Выполнить"}], conflict_dsl["commands"])
            self.assertIn("ambiguous-command-handler", [item["code"] for item in conflict_diagnostics])
            self.assertIn("manual", [item["outcome"] for item in conflict_outcomes])

    def test_publication_is_fail_closed_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_source(root)
            metadata_file = source / "ExternalDataProcessor.json"
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            metadata["name"] = "Pwd=topsecret;Safe"
            metadata_file.write_text(json.dumps(metadata), encoding="utf-8")
            existing = root / "existing"
            existing.mkdir()
            with self.assertRaisesRegex(CommandError, "new path"):
                run_ordinary_form_conversion(
                    [
                        "convert",
                        "--input",
                        str(source),
                        "--run-root",
                        str(root / "run-existing"),
                        "--output",
                        str(existing),
                        "--profile",
                        str(root / "profile.json"),
                    ]
                )
            with self.assertRaisesRegex(CommandError, "outside the conversion output"):
                run_ordinary_form_conversion(
                    ["verify-remediation", "--output", str(existing), "--run-root", str(existing / "run")]
                )
            self.assertFalse((existing / "run").exists())
            with self.assertRaisesRegex(CommandError, "outside src"):
                run_ordinary_form_conversion(
                    [
                        "convert",
                        "--input",
                        str(source),
                        "--run-root",
                        str(root / "run-src"),
                        "--output",
                        str(Path(__file__).parents[2] / "src" / "forbidden-conversion-output"),
                        "--profile",
                        str(root / "profile.json"),
                    ]
                )
            output = root / "cancelled"
            with (
                patch("scripts.python.ordinary_form_conversion._prepare_object_root", side_effect=self.prepare_stub),
                patch("scripts.python.ordinary_form_conversion._compile_form", side_effect=KeyboardInterrupt),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    run_ordinary_form_conversion(
                        [
                            "convert",
                            "--input",
                            str(source),
                            "--run-root",
                            str(root / "run-cancel"),
                            "--output",
                            str(output),
                            "--profile",
                            str(root / "profile.json"),
                        ]
                    )
            self.assertFalse(output.exists())
            self.assertFalse(any(path.name.startswith(".cancelled.") for path in root.iterdir()))
            self.assertEqual(
                "failed", json.loads((root / "run-cancel" / "conversion-report.json").read_text())["status"]
            )

            run_ordinary_form_conversion(["analyze", "--input", str(source), "--run-root", str(root / "run-redacted")])
            serialized = (root / "run-redacted" / "conversion-report.json").read_text(encoding="utf-8")
            self.assertNotIn("topsecret", serialized)
            self.assertIn("<redacted>", serialized)

    def test_lifecycle_transitions_require_matching_evidence_and_permission(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "output"
            output.mkdir()
            artifact = root / "result.epf"
            artifact.write_bytes(b"artifact")
            artifact_hash = __import__("hashlib").sha256(b"artifact").hexdigest()
            report = {
                "schemaVersion": 1,
                "status": "agent-remediation-required",
                "diagnostics": [],
                "agentChecks": {"analyzerClean": True, "allBindingsPresent": True, "allProceduresVerified": True},
                "forms": [{"bsl": {"agentPlan": [{"procedure": "Run", "status": "verified"}]}}],
                "builds": [
                    {
                        "target": "demo",
                        "artifactSha256": artifact_hash,
                        "compatibilityMode": "Version8_3_27",
                        "platform": {"version": "8.3.27.1989"},
                        "validation": [{"engine": "metadata", "form-validate": "passed", "form-info": "passed"}],
                    }
                ],
                "liveChecks": [{"target": "demo", "artifactSha256": artifact_hash, "status": "passed"}],
            }
            (output / "conversion-report.json").write_text(json.dumps(report), encoding="utf-8")
            profile = Mock(name="profile")
            profile.name = "demo"
            profile.require_string.return_value = "demo"
            for engine in (None, "legacy"):
                validation = report["builds"][0]["validation"][0]
                validation.pop("engine", None)
                if engine is not None:
                    validation["engine"] = engine
                write_json(output / "conversion-report.json", report)
                before = (output / "conversion-report.json").read_bytes()
                with (
                    self.subTest(engine=engine),
                    patch("scripts.python.ordinary_form_conversion.load_runtime_profile", return_value=profile),
                ):
                    with self.assertRaisesRegex(CommandError, "matching build and live acceptance evidence"):
                        _mark_ready(output, root / "profile.json", artifact, root / "rejected")
                self.assertEqual(before, (output / "conversion-report.json").read_bytes())
            validation["engine"] = "metadata"
            write_json(output / "conversion-report.json", report)
            with patch("scripts.python.ordinary_form_conversion.load_runtime_profile", return_value=profile):
                ready = _mark_ready(output, root / "profile.json", artifact, root / "run")
            self.assertEqual("demo", ready["target"])
            self.assertEqual("ready", json.loads((output / "conversion-report.json").read_text())["status"])

            report["diagnostics"] = [{"code": "open"}]
            report["status"] = "agent-remediation-required"
            (output / "conversion-report.json").write_text(json.dumps(report), encoding="utf-8")
            with patch("scripts.python.ordinary_form_conversion.load_runtime_profile", return_value=profile):
                with self.assertRaisesRegex(CommandError, "clean structure"):
                    _mark_ready(output, root / "profile.json", artifact, root / "run-2")
            with self.assertRaisesRegex(CommandError, "allow-current-target"):
                _live_start(output, root / "profile.json", artifact, root / "run-3", False)

    def make_source(self, root: Path, element_type: str = "Field", module: bytes = b"\xef\xbb\xbf// test\r\n") -> Path:
        source = root / "source"
        form = source / "Form" / "Form1"
        form.mkdir(parents=True)
        (source / "ExternalDataProcessor.json").write_text(
            json.dumps({"root": True, "v8unpack": "1.2.6", "name": "TestProcessor", "obj_version": "802"}),
            encoding="utf-8",
        )
        (form / "Form.json").write_text(
            json.dumps({"name": "Form1", "obj_version": "13", "Версия элементов формы": "0-27"}),
            encoding="utf-8",
        )
        (form / "Form.id.json").write_text(
            json.dumps({"uuid": "00000000-0000-0000-0000-000000000001"}), encoding="utf-8"
        )
        (form / "Form.elem.json").write_text(
            json.dumps(
                {
                    "params": [],
                    "props": [{"name": "ОбработкаОбъект"}],
                    "commands": [],
                    "tree": [{"name": "Value", "type": element_type, "page": "Page1"}],
                    "data": {
                        "-pages-": ["Page1"],
                        "Page1/Value": {"id": "1", "ver": 27, "page": "Page1", "raw": [], "prop": "ОбработкаОбъект"},
                    },
                }
            ),
            encoding="utf-8",
        )
        (form / "Form.obj.bsl").write_bytes(module)
        return source

    def test_conversion_is_deterministic_and_copies_bsl(self) -> None:
        module = b"\xef\xbb\xbf// \xd1\x82\xd0\xb5\xd1\x81\xd1\x82\r\n\xd0\x9f\xd1\x80\xd0\xbe\xd1\x86\xd0\xb5\xd0\xb4\xd1\x83\xd1\x80\xd0\xb0 X()\r\n\xd0\x9a\xd0\xbe\xd0\xbd\xd0\xb5\xd1\x86\xd0\x9f\xd1\x80\xd0\xbe\xd1\x86\xd0\xb5\xd0\xb4\xd1\x83\xd1\x80\xd1\x8b"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_source(root, module=module)
            outputs = []
            with patch("scripts.python.ordinary_form_conversion._prepare_object_root", side_effect=self.prepare_stub):
                for index in (1, 2):
                    output = root / f"output-{index}"
                    self.assertEqual(
                        0,
                        run_ordinary_form_conversion(
                            [
                                "convert",
                                "--input",
                                str(source),
                                "--run-root",
                                str(root / f"run-{index}"),
                                "--output",
                                str(output),
                                "--profile",
                                str(root / "profile.json"),
                            ]
                        ),
                    )
                    outputs.append(output)
                    copied = output / "TestProcessor" / "Forms" / "Form1" / "Ext" / "Form" / "Module.bsl"
                    self.assertEqual(module, copied.read_bytes())
                    converted_report = json.loads((output / "conversion-report.json").read_text())
                    self.assertEqual("agent-remediation-required", converted_report["status"])
                    self.assertNotIn("initialAgentAnalysis", converted_report)
            files = ["TestProcessor.xml", "TestProcessor/Forms/Form1.xml", "TestProcessor/Forms/Form1/Ext/Form.xml"]
            for relative in files:
                self.assertEqual((outputs[0] / relative).read_bytes(), (outputs[1] / relative).read_bytes())
            validation = _validate_forms(outputs[0])[0]
            self.assertEqual("metadata", validation["engine"])
            self.assertEqual(("passed", "passed"), (validation["form-validate"], validation["form-info"]))

    def test_form_xml_is_written_only_through_metadata_plan_apply(self) -> None:
        # C2: the converter seeds a new staging Form.xml and hands the rest to
        # the shared engine (form.compile plan + apply + verify); no other writer.
        from scripts.python import metadata

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_source(root)
            output = root / "output"
            with (
                patch("scripts.python.ordinary_form_conversion._prepare_object_root", side_effect=self.prepare_stub),
                patch.object(metadata, "plan_make", wraps=metadata.plan_make) as planned,
                patch.object(metadata, "apply", wraps=metadata.apply) as applied,
            ):
                self.assertEqual(
                    0,
                    run_ordinary_form_conversion(
                        [
                            "convert",
                            "--input",
                            str(source),
                            "--run-root",
                            str(root / "run"),
                            "--output",
                            str(output),
                            "--profile",
                            str(root / "profile.json"),
                        ]
                    ),
                )
            # apply replays the stored request through plan_make; every call is the same form.compile.
            self.assertTrue(planned.call_count >= 1)
            for call in planned.call_args_list:
                self.assertEqual(["form.compile"], [operation["op"] for operation in call.args[1]["operations"]])
            self.assertEqual(1, applied.call_count)
            plan = applied.call_args.args[2]
            self.assertEqual(["TestProcessor/Forms/Form1/Ext/Form.xml"], [item["path"] for item in plan["writes"]])
            form = output / "TestProcessor/Forms/Form1/Ext/Form.xml"
            self.assertEqual(metadata.byte_state(form.read_bytes()), plan["writes"][0]["after"])
            # Recovery state and the plan copy are removed only after a clean apply.
            self.assertEqual([], [path.name for path in output.parent.iterdir() if "metadata-" in path.name])

    def test_object_metadata_mapping_preserves_types_and_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root_xml = Path(temp) / "Processor.xml"
            root_xml.write_text(
                """<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:v8="http://v8.1c.ru/8.1/data/core">
<ExternalDataProcessor><ChildObjects>
<Attribute><Properties><Name>Номенклатура</Name><Type><v8:Type>cfg:CatalogRef.Номенклатура</v8:Type></Type></Properties></Attribute>
<Attribute><Properties><Name>УстаревшаяНастройка</Name><Type/></Properties></Attribute>
<TabularSection><Properties><Name>УчетМарок</Name></Properties><ChildObjects><Attribute><Properties><Name>НомерМарки</Name><Type><v8:Type>xs:string</v8:Type></Type></Properties></Attribute></ChildObjects></TabularSection>
<TabularSection><Properties><Name>УчетМарокИсх</Name></Properties><ChildObjects><Attribute><Properties><Name>НомерМарки</Name><Type><v8:Type>xs:string</v8:Type></Type></Properties></Attribute></ChildObjects></TabularSection>
</ChildObjects></ExternalDataProcessor></MetaDataObject>""",
                encoding="utf-8",
            )
            entities = _object_inventory(root_xml, "ExternalDataProcessor")
            self.assertEqual(
                ["Номенклатура", "УстаревшаяНастройка", "УчетМарок", "НомерМарки", "УчетМарокИсх", "НомерМарки"],
                [str(item["name"]) for item in entities],
            )
            self.assertEqual("cfg:CatalogRef.Номенклатура", entities[0]["type"])
            self.assertEqual("manual", entities[1]["outcome"])
            self.assertEqual("xs:string", entities[3]["type"])

    def test_table_columns_come_from_object_metadata_not_raw_strings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_source(root)
            element_file = source / "Form" / "Form1" / "Form.elem.json"
            elements = json.loads(element_file.read_text(encoding="utf-8"))
            elements["tree"][0]["name"] = "Rows"
            elements["tree"][0]["type"] = "Table"
            elements["data"] = {
                "-pages-": ["Page1"],
                "Page1/Rows": {
                    "id": "1",
                    "ver": 27,
                    "page": "Page1",
                    "raw": ["ЛожнаяКолонка"],
                    "prop": "ОбработкаОбъект",
                },
            }
            element_file.write_text(json.dumps(elements), encoding="utf-8")
            kind, metadata, forms = _read_source(source)
            report = _report(
                kind,
                metadata,
                forms,
                [
                    {"kind": "tabular-section", "name": "Rows"},
                    {"kind": "column", "name": "RealColumn", "owner": "Rows"},
                ],
            )
            table = report["forms"][0]["dsl"]["elements"][0]["children"][0]
            self.assertEqual(["RealColumn"], [column["input"] for column in table["columns"]])

    def test_table_field_maps_to_spreadsheet_document(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_source(root, element_type="TableField")
            output = root / "output"
            with patch("scripts.python.ordinary_form_conversion._prepare_object_root", side_effect=self.prepare_stub):
                run_ordinary_form_conversion(
                    [
                        "convert",
                        "--input",
                        str(source),
                        "--run-root",
                        str(root / "run"),
                        "--output",
                        str(output),
                        "--profile",
                        str(root / "profile.json"),
                    ]
                )
            report = json.loads((output / "conversion-report.json").read_text(encoding="utf-8"))
            self.assertEqual([], report["diagnostics"])
            form_xml = (output / "TestProcessor" / "Forms" / "Form1" / "Ext" / "Form.xml").read_text(encoding="utf-8")
            self.assertIn('<SpreadSheetDocumentField name="Value"', form_xml)
            self.assertIn("mxl:SpreadsheetDocument", form_xml)
            run_ordinary_form_conversion(
                [
                    "verify-remediation",
                    "--output",
                    str(output),
                    "--run-root",
                    str(root / "verify"),
                ]
            )
            verified = json.loads((output / "conversion-report.json").read_text(encoding="utf-8"))
            self.assertEqual("excluded-external-artifact", verified["agentChecks"]["analyzerStatus"])
            self.assertNotIn("analyzerClean", verified["agentChecks"])

    def test_each_form_entity_has_one_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_source(root)
            element_file = source / "Form" / "Form1" / "Form.elem.json"
            elements = json.loads(element_file.read_text(encoding="utf-8"))
            elements["props"] = [{"name": "ОбработкаОбъект"}]
            elements["commands"] = [{"name": "Команда1"}]
            element_file.write_text(json.dumps(elements), encoding="utf-8")

            run_ordinary_form_conversion(["analyze", "--input", str(source), "--run-root", str(root / "run")])
            form = json.loads((root / "run" / "conversion-report.json").read_text(encoding="utf-8"))["forms"][0]
            outcomes = form["coverageOutcomes"]
            self.assertEqual(len(outcomes), len({item["path"] for item in outcomes}))
            self.assertEqual(
                form["coverage"]["input"],
                sum(form["coverage"][key] for key in ("converted", "manual", "excluded")),
            )

    def test_verify_remediation_reports_state_and_diagnostics_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "output"
            form = output / "TestProcessor/Forms/Form1/Ext/Form"
            form.mkdir(parents=True)
            (form / "Module.bsl").write_text("", encoding="utf-8")
            (form.parent / "Form.xml").write_text("<Form/>", encoding="utf-8")
            (output / "conversion-report.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "status": "agent-remediation-required",
                        "forms": [{"name": "Form1", "bsl": {"agentPlan": [{"procedure": "Run"}]}}],
                        "stages": {},
                    }
                ),
                encoding="utf-8",
            )

            verified = cast(Any, _verify_remediation(output, root / "run"))

            self.assertEqual("failed", verified["stages"]["agent"])
            self.assertEqual("excluded-external-artifact", verified["agentChecks"]["analyzerStatus"])
            self.assertIsInstance(verified["agentChecks"]["diagnostics"], list)

    def test_verify_remediation_requires_complete_structural_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "output"
            form = output / "TestProcessor/Forms/Form1/Ext/Form"
            form.mkdir(parents=True)
            (form / "Module.bsl").write_text("", encoding="utf-8")
            (form.parent / "Form.xml").write_text("<Form/>", encoding="utf-8")
            report = {
                "schemaVersion": 1,
                "status": "structure-remediation-required",
                "stages": {},
                "coverage": {"input": 1, "converted": 0, "manual": 1, "excluded": 0},
                "diagnostics": [{"code": "unsupported-form-property", "path": "form/Form1/property/9"}],
                "forms": [{"name": "Form1", "bsl": {"agentPlan": []}}],
            }
            write_json(output / "conversion-report.json", report)
            with self.assertRaisesRegex(CommandError, "--evidence"):
                _verify_remediation(output, root / "missing")
            evidence = root / "evidence.json"
            write_json(evidence, {"structuralDiagnostics": []})
            with self.assertRaisesRegex(CommandError, "exactly once"):
                _verify_remediation(output, root / "incomplete", evidence)
            write_json(
                evidence,
                {
                    "structuralDiagnostics": [
                        {"code": "unsupported-form-property", "path": "form/Form1/property/9", "outcome": "removed"}
                    ]
                },
            )
            with (
                patch.object(conversion, "_validate_forms", return_value=[]),
                self.assertRaisesRegex(CommandError, "profile validation"),
            ):
                _verify_remediation(output, root / "no-validation", evidence)
            report["coverage"]["manual"] = 0
            write_json(output / "conversion-report.json", report)
            with (
                patch.object(
                    conversion,
                    "_validate_forms",
                    return_value=[{"engine": "metadata", "form-validate": "passed", "form-info": "passed"}],
                ),
                self.assertRaisesRegex(CommandError, "coverage is inconsistent"),
            ):
                _verify_remediation(output, root / "bad-coverage", evidence)
            report["coverage"]["manual"] = 1
            write_json(output / "conversion-report.json", report)
            with patch.object(
                conversion,
                "_validate_forms",
                return_value=[{"engine": "metadata", "form-validate": "passed", "form-info": "passed"}],
            ):
                verified = cast(Any, _verify_remediation(output, root / "verified", evidence))
            self.assertEqual([], verified["diagnostics"])
            self.assertEqual("verified", verified["stages"]["structure"])
            self.assertEqual(0, verified["coverage"]["manual"])

    def test_dependencies_block_only_declared_stages(self) -> None:
        report = {"dependencies": [{"id": "scan", "status": "unresolved", "blockedStages": ["live-start"]}]}
        conversion._require_resolved_dependencies(report, "adaptation")
        with self.assertRaisesRegex(CommandError, "scan"):
            conversion._require_resolved_dependencies(report, "live-start")
        conversion._require_resolved_dependencies(
            {"dependencies": [{"id": "scan", "status": "resolved"}]}, "live-start"
        )

    def test_prepare_package_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = self.prepare_profile(root)
            exact_input = root / "exact.epf"
            exact_input.write_bytes(b"exact")
            rejected = root / "rejected"
            with self.assertRaisesRegex(CommandError, "does not match expected"):
                run_ordinary_form_conversion(
                    [
                        "prepare",
                        "--input",
                        str(exact_input),
                        "--output",
                        str(rejected),
                        "--profile",
                        str(profile),
                        "--expected-sha256",
                        "0" * 64,
                    ]
                )
            self.assertFalse(rejected.exists())
            cases = ((self.make_source(root), root / "epf-package", "epf"), (ERF_FIXTURE, root / "erf-package", "erf"))
            with patch.object(conversion, "_prepare_object_root", side_effect=self.prepare_stub):
                for source, output, family in cases:
                    with self.subTest(family=family):
                        run_ordinary_form_conversion(
                            ["prepare", "--input", str(source), "--output", str(output), "--profile", str(profile)]
                        )
                        summary = json.loads((output / "preparation-summary.json").read_text(encoding="utf-8"))
                        self.assertEqual(family, summary["source"]["family"])
                        self.assertTrue((output / "managed/conversion-report.json").is_file())
                        self.assertTrue((output / "source").is_dir())
                        self.assertFalse(any(output.glob("*.epf")))
                        self.assertFalse(any(output.glob("*.erf")))
            structural = root / "structural"

            def convert(
                _input: Path,
                managed: Path,
                _evidence: Path,
                _profile: Path,
                _tool: str,
                _root: str,
                _ordinary: Path | None = None,
            ):
                report = {
                    "source": {"kind": "ExternalDataProcessor", "name": "TestProcessor"},
                    "status": "structure-remediation-required",
                    "inputSha256": _input_sha(cases[0][0]),
                    "artifacts": {"modules": []},
                }
                write_json(managed / "conversion-report.json", report)
                return report, cases[0][0]

            with patch.object(conversion, "_convert_into", side_effect=convert):
                run_ordinary_form_conversion(
                    ["prepare", "--input", str(cases[0][0]), "--output", str(structural), "--profile", str(profile)]
                )
            self.assertEqual(
                "resolve-structure",
                json.loads((structural / "preparation-summary.json").read_text(encoding="utf-8"))["nextAction"],
            )

    def test_prepare_binary_epf_package_preserves_designer_ordinary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            artifact = root / "input.epf"
            artifact.write_bytes(b"epf")
            profile = self.prepare_profile(root)
            output = root / "package"

            def dump(_input: Path, destination: Path, _profile: Path, _run: Path, _tool: str, _kind: str) -> Path:
                shutil.copytree(DESIGNER_EPF_FIXTURE, destination, dirs_exist_ok=True)
                return destination / "ТестоваяОбработка.xml"

            with (
                patch.object(conversion, "_extract", return_value=FIXTURE),
                patch.object(conversion, "_dump_object_source", side_effect=dump),
            ):
                conversion._prepare_package(artifact, output, profile, "v8unpack")
            summary = json.loads((output / "preparation-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(_input_sha(DESIGNER_EPF_FIXTURE), summary["ordinaryTreeSha256"])
            self.assertEqual(_input_sha(DESIGNER_EPF_FIXTURE), _input_sha(output / summary["ordinaryPath"]))

    def test_prepare_package_failures_and_concurrency(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_source(root)
            profile = self.prepare_profile(root)
            with self.assertRaisesRegex(CommandError, "does not accept"):
                run_ordinary_form_conversion(
                    [
                        "prepare",
                        "--input",
                        str(source),
                        "--output",
                        str(root / "invalid"),
                        "--profile",
                        str(profile),
                        "--run-root",
                        str(root / "run"),
                    ]
                )
            with self.assertRaisesRegex(CommandError, "new path outside"):
                run_ordinary_form_conversion(
                    ["prepare", "--input", str(source), "--output", str(source / "nested"), "--profile", str(profile)]
                )
            failed = root / "failed"
            with (
                patch.object(conversion, "_convert_into", side_effect=CommandError("Pwd=topsecret")),
                self.assertRaisesRegex(CommandError, "redacted evidence") as raised,
            ):
                run_ordinary_form_conversion(
                    ["prepare", "--input", str(source), "--output", str(failed), "--profile", str(profile)]
                )
            evidence = Path(str(raised.exception).rsplit(": ", 1)[1]) / "preparation-failure.json"
            self.assertNotIn("topsecret", evidence.read_text(encoding="utf-8"))
            self.assertFalse(failed.exists())

            output = root / "concurrent"
            barrier = threading.Barrier(2)

            def convert(
                _input: Path,
                managed: Path,
                _evidence: Path,
                _profile: Path,
                _tool: str,
                _root: str,
                _ordinary: Path | None = None,
            ):
                report = {
                    "source": {"kind": "ExternalDataProcessor", "name": "TestProcessor"},
                    "status": "agent-remediation-required",
                    "inputSha256": _input_sha(source),
                    "artifacts": {"modules": []},
                }
                write_json(managed / "conversion-report.json", report)
                barrier.wait()
                return report, source

            def invoke() -> bool:
                try:
                    run_ordinary_form_conversion(
                        ["prepare", "--input", str(source), "--output", str(output), "--profile", str(profile)]
                    )
                    return True
                except CommandError:
                    return False

            with (
                patch.object(conversion, "_convert_into", side_effect=convert),
                ThreadPoolExecutor(max_workers=2) as pool,
            ):
                results = list(pool.map(lambda _index: invoke(), range(2)))
            self.assertEqual([False, True], sorted(results))
            self.assertTrue((output / "preparation-summary.json").is_file())

    def test_typed_organization_and_handlerless_close_button_are_converted(self) -> None:
        form = conversion.SourceForm(
            "Форма_БП",
            Path("."),
            {},
            {
                "props": [
                    {"name": "ОбработкаОбъект"},
                    {"name": "Организация", "raw": ["Pattern", "c92a1124-c41e-42a4-bda7-3bbac9c6039e"]},
                ],
                "commands": [],
                "tree": [
                    {"name": "Закрыть", "type": "Button", "page": "Страница1"},
                    {"name": "Организация", "type": "Field", "page": "Страница1"},
                ],
                "data": {
                    "-pages-": ["Страница1"],
                    "Страница1/Закрыть": {"raw": ["ru", "Закрыть"]},
                    "Страница1/Организация": {"prop": "Организация", "raw": []},
                },
            },
        )

        dsl, diagnostics, _coverage, _outcomes = cast(
            Any,
            conversion._form_dsl(
                form,
                set(),
                "ExternalDataProcessor",
                "Test",
                [],
            ),
        )

        self.assertEqual([], diagnostics)
        self.assertEqual(
            "CatalogRef.Организации",
            next(item["type"] for item in dsl["attributes"] if item["name"] == "Организация"),
        )
        close_button = next(
            item for group in dsl["elements"] for item in group.get("children", []) if item.get("button") == "Закрыть"
        )
        self.assertEqual("Close", close_button["stdCommand"])
        self.assertEqual([], dsl["commands"])


class BuildSourcesTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path, Path, Path, str]:
        managed = root / "src/epf/managed/TestProcessor"
        (managed / "TestProcessor/Ext").mkdir(parents=True)
        (managed / "TestProcessor.xml").write_text("<ExternalDataProcessor/>", encoding="utf-8")
        (managed / "TestProcessor/Ext/ObjectModule.bsl").write_text("", encoding="utf-8")
        profile = root / "profile.json"
        secret = "build-secret"
        write_json(
            profile,
            {
                "schemaVersion": 3,
                "profileName": "demo",
                "projectName": "test",
                "projectSlug": "test",
                "platform": {"binaryPath": "C:/Program Files/1cv8/8.3.27.1989/bin/1cv8.exe"},
                "infobase": {
                    "mode": "client-server",
                    "server": "server",
                    "ref": "demo",
                    "auth": {"mode": "user-password", "user": "user", "passwordEnv": "TEST_BUILD_SECRET"},
                },
            },
        )
        return managed, profile, root / ".artifacts/epf/TestProcessor.epf", root / ".artifacts/run", secret

    def test_build_sources_succeeds_with_profile_and_redacted_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            managed, profile, artifact, run_root, secret = self.fixture(root)
            variant = managed.with_name("TestProcessorVariant")
            managed.rename(variant)
            managed = variant
            commands: list[list[str]] = []

            def build(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
                commands.append(command)
                Path(command[command.index("-OutputFile") + 1]).write_bytes(b"epf")
                return subprocess.CompletedProcess(command, 0, "", "")

            with (
                patch.object(conversion, "project_root", return_value=root),
                patch.object(conversion, "resolve_secret_value", return_value=secret),
                patch.object(conversion.subprocess, "run", side_effect=build),
            ):
                result = conversion._build_sources(managed, profile, artifact, run_root)
            serialized = json.dumps(result) + (run_root / "build-summary.json").read_text(encoding="utf-8")
            self.assertEqual("built", result["status"])
            self.assertEqual("TestProcessor", result["designerName"])
            self.assertEqual("TestProcessorVariant", result["repositoryName"])
            self.assertNotIn(secret, serialized)
            self.assertEqual("epf-build", commands[0][commands[0].index("imported-skill") + 1])
            self.assertFalse(any(stage in commands[0] for stage in ("live-start", "live-confirm", "ready")))
            report = root / "src/erf/managed/TestReportVariant"
            report.parent.mkdir(parents=True)
            shutil.copytree(managed, report)
            with (
                patch.object(conversion, "project_root", return_value=root),
                patch.object(conversion, "resolve_secret_value", return_value=secret),
                patch.object(conversion.subprocess, "run", side_effect=build),
            ):
                conversion._build_sources(
                    report, profile, root / ".artifacts/erf/TestReport.erf", root / ".artifacts/report-run"
                )
            self.assertEqual("erf-build", commands[1][commands[1].index("imported-skill") + 1])

    def test_build_sources_rejects_invalid_boundaries_and_reused_run_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            managed, profile, artifact, run_root, _secret = self.fixture(root)
            with patch.object(conversion, "project_root", return_value=root):
                with self.assertRaisesRegex(CommandError, "src/epf/managed"):
                    conversion._build_sources(root / "other", profile, artifact, run_root)
                run_root.mkdir(parents=True)
                with self.assertRaisesRegex(CommandError, "new run-root"):
                    conversion._build_sources(managed, profile, artifact, run_root)

    def test_build_sources_failure_or_race_cleans_staging_without_overwrite(self) -> None:
        for race in (False, True):
            with self.subTest(race=race), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                managed, profile, artifact, run_root, secret = self.fixture(root)

                def build(
                    command: list[str],
                    *,
                    race: bool = race,
                    artifact: Path = artifact,
                    secret: str = secret,
                    **_kwargs: object,
                ) -> subprocess.CompletedProcess[str]:
                    Path(command[command.index("-OutputFile") + 1]).write_bytes(b"new")
                    if race:
                        artifact.write_bytes(b"racer")
                        return subprocess.CompletedProcess(command, 0, "", "")
                    return subprocess.CompletedProcess(command, 1, "", f"-Password {secret}")

                with (
                    patch.object(conversion, "project_root", return_value=root),
                    patch.object(conversion, "resolve_secret_value", return_value=secret),
                    patch.object(conversion.subprocess, "run", side_effect=build),
                    self.assertRaises(CommandError) as raised,
                ):
                    conversion._build_sources(managed, profile, artifact, run_root)
                self.assertNotIn(secret, str(raised.exception))
                self.assertEqual(b"racer" if race else None, artifact.read_bytes() if artifact.exists() else None)
                self.assertFalse(list(artifact.parent.glob(".*.tmp.epf")))


if __name__ == "__main__":
    unittest.main()
