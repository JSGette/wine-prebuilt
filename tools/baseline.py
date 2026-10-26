#!/usr/bin/env python3
"""Run a packaged Linux artifact in pinned CentOS 7 userspace on the native CPU."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

from fetch import ROOT
from qualify import GUESTS

IMAGES = {
    "linux-amd64": "centos@sha256:be65f488b7764ad3638f236b7b515b3678369a5124c47b8d32916d6487418ea4",
    "linux-arm64": "arm64v8/centos@sha256:73f11afcbb50d8bc70eab9f0850b3fa30e61a419bc48cf426e63527d14a8373b",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=IMAGES)
    parser.add_argument("output", type=Path)
    parser.add_argument("fixtures", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    (artifact,) = output.glob(f"*-{args.platform}.tar.gz")
    work = Path(tempfile.mkdtemp(prefix="glibc217 space-", dir=output.parent))
    with tarfile.open(artifact) as archive:
        archive.extractall(work, filter="data")
    runtime = work / artifact.name.removesuffix(".tar.gz")
    fixtures = args.fixtures.resolve()
    container = subprocess.check_output([
        "docker", "run", "--rm", "--detach", "--network", "none",
        "--volume", f"{work}:{work}", "--volume", f"{fixtures}:{fixtures}:ro",
        IMAGES[args.platform], "sleep", "infinity"], text=True).strip()
    try:
        subprocess.run([sys.executable, str(ROOT / "tests/run.py"), str(runtime), str(fixtures),
                        "--container", container, "--locale", "en_US.UTF-8", "--guests",
                        *GUESTS[args.platform], "--output", str(work / "logs")], check=True)
        report = {"artifact": artifact.name, "image": IMAGES[args.platform], "status": "passed",
                  "tests": json.loads((work / "logs/results.json").read_text())}
        (output / f"{artifact.name}.glibc217.json").write_text(json.dumps(report, indent=2) + "\n")
    finally:
        subprocess.run(["docker", "stop", "--time", "1", container], check=True)


if __name__ == "__main__":
    main()
