#!/usr/bin/env python3
"""Audit, package, relocate, and test every advertised guest CPU."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

from fetch import ROOT
from distribution import FORMATS, PLATFORMS, basename, sha256


def run(script, *arguments):
    subprocess.run([sys.executable, str(ROOT / script), *map(str, arguments)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "out")
    parser.add_argument("--serial", type=int, default=1)
    args = parser.parse_args()
    build = json.loads(args.build.read_text())
    directory = args.build.resolve().parent
    run("tools/package.py", args.build, "--output", args.output, "--serial", args.serial)
    name = basename(build["platform"], build["wine"], args.serial)
    artifact = args.output.resolve() / f"{name}.tar.gz"
    relocated = Path(tempfile.mkdtemp(prefix="relocated runtime ", dir=directory))
    with tarfile.open(artifact) as archive:
        archive.extractall(relocated, filter="data")
    runtime = relocated
    fixtures = directory / "fixtures"
    run("tests/build.py", build["toolchain"], fixtures)
    guests = PLATFORMS[build["platform"]]["guests"]
    logs = directory / "qualification"
    run("tests/run.py", runtime, fixtures, "--guests", *guests, "--output", logs)
    for guest in guests:
        if guest != "i386":
            run("tests/ninja.py", runtime, guest, "--output", logs, "--cache", directory / "test-cache")
    archives = {name + extension: sha256(args.output / (name + extension)) for extension in FORMATS}
    report = {"archives": archives, "platform": build["platform"],
              "guests": guests, "relocated_runtime": str(runtime), "status": "passed",
              "tests": json.loads((logs / "results.json").read_text())}
    (args.output / f"{name}.qualification.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
