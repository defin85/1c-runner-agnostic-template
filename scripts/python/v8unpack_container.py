#!/usr/bin/env python3
"""Raw container round-trip for nested 1C artifacts unsupported by v8unpack CLI."""

import argparse
import filecmp
import importlib
import os
import tempfile
from pathlib import Path

extract = importlib.import_module("v8unpack.container_reader").extract
build = importlib.import_module("v8unpack.container_writer").build


def same_tree(left: Path, right: Path) -> bool:
    left_files = sorted(path.relative_to(left) for path in left.rglob("*") if path.is_file())
    right_files = sorted(path.relative_to(right) for path in right.rglob("*") if path.is_file())
    return left_files == right_files and all(
        filecmp.cmp(left / path, right / path, shallow=False) for path in left_files
    )


def pack_container(source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as directory:
        temporary = Path(directory)
        candidate = temporary / output.name
        verification = temporary / "verification"
        build(str(source), str(candidate), True)
        extract(str(candidate), str(verification), False, False)
        if not same_tree(source, verification):
            raise RuntimeError("v8unpack container round-trip differs")
        os.replace(candidate, output)


def main() -> None:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("action", choices=("container-extract", "container-build"))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if args.action == "container-extract":
        extract(str(args.input), str(args.output), False, False)
    else:
        pack_container(args.input, args.output)


if __name__ == "__main__":
    main()
