#!/usr/bin/env python3
"""Run a packaged Linux artifact in pinned CentOS 7 userspace on the native CPU."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from fetch import ROOT
from distribution import PLATFORMS, sha256

IMAGES = {
    "linux-amd64": "centos@sha256:be65f488b7764ad3638f236b7b515b3678369a5124c47b8d32916d6487418ea4",
    "linux-arm64": "arm64v8/centos@sha256:73f11afcbb50d8bc70eab9f0850b3fa30e61a419bc48cf426e63527d14a8373b",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("fixtures", type=Path)
    parser.add_argument("--work", type=Path, default=ROOT / ".work/tests")
    args = parser.parse_args()
    artifact = args.artifact.resolve()
    output = artifact.parent
    args.work.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="glibc217 space-", dir=args.work.resolve()))
    with tarfile.open(artifact) as archive:
        archive.extractall(work, filter="data")
    runtime = work
    manifest = json.loads((runtime / "manifest.json").read_text())
    platform = manifest["platform"]
    if platform not in IMAGES:
        parser.error("minimum-environment runtime testing is currently available only for Linux")
    fixtures = args.fixtures.resolve()
    container = subprocess.check_output([
        "docker", "run", "--rm", "--detach", "--network", "none",
        "--user", f"{os.getuid()}:{os.getgid()}",
        "--volume", f"{work}:{work}", "--volume", f"{fixtures}:{fixtures}:ro",
        IMAGES[platform], "sleep", "infinity"], text=True).strip()
    try:
        subprocess.run([sys.executable, str(ROOT / "tests/run.py"), str(runtime), str(fixtures),
                        "--container", container, "--locale", "en_US.UTF-8", "--guests",
                        *PLATFORMS[platform]["guests"], "--output", str(work / "logs")], check=True)
        report = {"artifact": artifact.name, "sha256": sha256(artifact),
                  "image": IMAGES[platform], "status": "passed",
                  "scope": "glibc 2.17 userspace on the executor kernel; not an old-kernel test",
                  "tests": json.loads((work / "logs/results.json").read_text())}
        (output / f"{artifact.name}.glibc217.json").write_text(json.dumps(report, indent=2) + "\n")
    finally:
        subprocess.run(["docker", "stop", "--time", "1", container], check=True)


if __name__ == "__main__":
    main()
