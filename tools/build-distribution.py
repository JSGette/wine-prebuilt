#!/usr/bin/env python3
"""Build and qualify one release-shaped artifact set, locally or in CI."""

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from distribution import PLATFORMS, basename
from fetch import ROOT


def run(*command, **kwargs):
    subprocess.run(list(map(str, command)), check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=PLATFORMS)
    parser.add_argument("--serial", type=int, default=1)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--output", type=Path, default=ROOT / "out")
    args = parser.parse_args()
    host_os = {"Linux": "linux", "Darwin": "macos"}.get(platform.system())
    host_cpu = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine())
    if args.platform != f"{host_os}-{host_cpu}":
        parser.error("run on a native executor matching the requested platform")
    if args.serial < 0 or args.jobs < 1:
        parser.error("serial must be nonnegative and jobs must be positive")
    work = ROOT / ".work"
    output = args.output.resolve()
    work.mkdir(exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    wine = json.loads((ROOT / "sources.json").read_text())["wine"]["version"]
    name = basename(args.platform, wine, args.serial)
    if list(output.glob(name + "*")):
        parser.error("this artifact version already exists; use a fresh output directory or serial")
    result = work / f"{args.platform}-result.txt"
    if host_os == "linux":
        image = f"wine-prebuilt-{host_cpu}:builder"
        run("docker", "build", "--tag", image, ROOT)
        run("docker", "run", "--rm", "--volume", f"{ROOT}:/src:ro",
            "--volume", f"{work}:/work", "--volume", f"{output}:/out",
            "--env", "WINE_BUILD_WORK=/work", "--env", f"PLATFORM={args.platform}",
            "--env", f"JOBS={args.jobs}", "--env", f"SERIAL={args.serial}", image,
            "bash", "-euc", 'python3 -m unittest discover -s tests -p "*_test.py"; '
            'python3 tests/source-preparation.py --work /work; '
            'bash tools/build-linux.sh; '
            'python3 tools/qualify.py "$(cat /work/$PLATFORM-result.txt)" --output /out --serial "$SERIAL"')
        build = work / Path(result.read_text().strip()).relative_to("/work")
        run(sys.executable, ROOT / "tools/baseline.py", args.platform,
            output / f"{name}.tar.gz", build.parent / "fixtures")
    else:
        run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "*_test.py", cwd=ROOT)
        run(sys.executable, ROOT / "tests/source-preparation.py")
        run(sys.executable, ROOT / "tools/build.py", args.platform, "--jobs", args.jobs,
            "--result-file", result)
        run(sys.executable, ROOT / "tools/qualify.py", result.read_text().strip(),
            "--output", output, "--serial", args.serial)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
            stream.write(f"attestation_name={name}.attestation.jsonl\n")
    print(f"Qualified distribution: {output / name}")


if __name__ == "__main__":
    main()
