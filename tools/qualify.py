#!/usr/bin/env python3
"""Audit, package, relocate, and test every advertised guest CPU."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

from fetch import ROOT

GUESTS = {
    "linux-amd64": ["amd64", "i386"],
    "linux-arm64": ["arm64", "amd64", "i386"],
    "macos-arm64": ["arm64", "amd64"],
}


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
    name = f"wine-{build['wine']}-{args.serial}-{build['platform']}"
    artifact = args.output.resolve() / f"{name}.tar.gz"
    relocated = Path(tempfile.mkdtemp(prefix="relocated runtime ", dir=directory))
    with tarfile.open(artifact) as archive:
        archive.extractall(relocated, filter="data")
    runtime = relocated / name
    fixtures = directory / "fixtures"
    run("tests/build.py", build["toolchain"], fixtures)
    guests = GUESTS[build["platform"]]
    logs = directory / "qualification"
    run("tests/run.py", runtime, fixtures, "--guests", *guests, "--output", logs)
    for guest in guests:
        if guest != "i386":
            run("tests/ninja.py", runtime, guest, "--output", logs, "--cache", directory / "test-cache")
    with artifact.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    report = {"artifact": artifact.name, "sha256": digest, "platform": build["platform"],
              "guests": guests, "relocated_runtime": str(runtime), "status": "passed",
              "tests": json.loads((logs / "results.json").read_text())}
    (args.output / f"{name}.qualification.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
