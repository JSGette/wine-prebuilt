#!/usr/bin/env python3
"""Extract a distribution elsewhere and test every declared Windows guest CPU."""

import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from distribution import FORMATS, sha256
from fetch import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("fixtures", type=Path)
    parser.add_argument("--work", type=Path, default=ROOT / ".work/tests")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="runtime space-", dir=args.work.resolve()))
    runtime = scratch / "relocated runtime"
    runtime.mkdir()
    with tarfile.open(args.artifact) as archive:
        archive.extractall(runtime, filter="data")
    manifest = json.loads((runtime / "manifest.json").read_text())
    guests = manifest["windows_cpus"]
    logs = scratch / "logs"
    subprocess.run([sys.executable, str(ROOT / "tests/run.py"), str(runtime), str(args.fixtures),
                    "--guests", *guests, "--output", str(logs)], check=True)
    for guest in guests:
        if guest != "i386":
            subprocess.run([sys.executable, str(ROOT / "tests/ninja.py"), str(runtime), guest,
                            "--output", str(logs), "--cache", str(args.work / "cache")], check=True)
    name = args.artifact.name.removesuffix(".tar.gz")
    report = {
        "status": "passed", "platform": manifest["platform"], "guests": guests,
        "archives": {name + extension: sha256(args.artifact.parent / (name + extension)) for extension in FORMATS},
        "tested_os": platform.platform(), "macos_version": platform.mac_ver()[0] or None,
        "tests": json.loads((logs / "results.json").read_text()),
    }
    destination = args.artifact.with_name(name + ".qualification.json")
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(destination)


if __name__ == "__main__":
    main()
