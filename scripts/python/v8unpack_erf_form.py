from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from xml.etree import ElementTree

from v8unpack import helper
from v8unpack.container_reader import extract as extract_container
from v8unpack.MetaDataObject.Form import Form0
from v8unpack.MetaDataObject.Form.Form9 import Form9
from v8unpack.version import __version__ as __version__

MD_NS = "http://v8.1c.ru/8.3/MDClasses"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def decode_form(binary: Path, destination: Path, name: str, form_uuid: str) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        raw_root = Path(temporary)
        extract_container(str(binary), str(raw_root), False, False)
        raw = raw_root / "0"
        if set(path.name for path in raw.iterdir()) != {"form", "module"}:
            raise ValueError(f"unexpected Form.bin content: {binary}")
        form = Form9(meta_obj_class=Form0, obj_version="13", options={})
        form.header = {"name": name, "Тип формы": "0"}
        form.form = [helper.brace_file_read(str(raw), "form")]
        decoder = form.get_form_element_decoder()
        if decoder is None or form.header["Версия элементов формы"] not in {"0-26", "0-27"}:
            raise ValueError(f"unsupported ordinary form schema: {name}")
        decoder(form).decode(str(raw), str(raw), "", form.form[0][0])
        form.header["obj_version"] = "9" if form.header["Версия элементов формы"] == "0-26" else "13"
        destination.mkdir(parents=True)
        write_json(destination / "Form.json", form.header)
        write_json(destination / "Form.id.json", {"uuid": form_uuid})
        write_json(
            destination / "Form.elem.json",
            {
                "params": form.params,
                "props": form.props,
                "commands": form.commands,
                "tree": form.elements_tree,
                "data": form.elements_data,
            },
        )
        shutil.copyfile(raw / "module", destination / "Form.obj.bsl")


def convert(designer_root: Path, destination: Path) -> None:
    roots = list(designer_root.glob("*.xml"))
    if len(roots) != 1:
        raise ValueError("Designer dump must contain exactly one root XML")
    document = ElementTree.parse(roots[0]).getroot()
    report = document.find(f"{{{MD_NS}}}ExternalReport")
    if report is None:
        raise ValueError("Designer dump root must be ExternalReport")
    name = report.findtext(f"{{{MD_NS}}}Properties/{{{MD_NS}}}Name")
    if not name:
        raise ValueError("ExternalReport name is missing")
    object_root = designer_root / name
    forms = report.find(f"{{{MD_NS}}}ChildObjects")
    form_names = (
        [] if forms is None else [child.text for child in forms if child.tag == f"{{{MD_NS}}}Form" and child.text]
    )
    destination.mkdir(parents=True)
    shutil.copytree(designer_root, destination / "Designer")
    write_json(
        destination / "ExternalReport.json",
        {
            "root": True,
            "v8unpack": __version__,
            "name": name,
            "obj_version": "803",
            "sourceFormat": "designer-xml-with-v8unpack-form-bin",
        },
    )
    for form_name in form_names:
        descriptor = ElementTree.parse(object_root / "Forms" / f"{form_name}.xml").getroot()
        form = descriptor.find(f"{{{MD_NS}}}Form")
        if form is None or form.findtext(f"{{{MD_NS}}}Properties/{{{MD_NS}}}FormType") != "Ordinary":
            raise ValueError(f"form is not ordinary: {form_name}")
        decode_form(
            object_root / "Forms" / form_name / "Ext" / "Form.bin",
            destination / "Form" / form_name,
            form_name,
            form.attrib["uuid"],
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("designer_root", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    convert(args.designer_root.resolve(), args.destination.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
