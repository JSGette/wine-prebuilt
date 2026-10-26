#!/usr/bin/env python3
"""Extract the pinned glibc 2.17 build sysroot; never install these RPMs on the host."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from fetch import ROOT, fetch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cpu", choices=("amd64", "arm64"))
    parser.add_argument("directory", type=Path, help="Parent directory for content-addressed sysroots")
    parser.add_argument("--cache", type=Path, default=ROOT / ".work/cache")
    args = parser.parse_args()
    sources = json.loads((ROOT / "sources.json").read_text())
    inputs = {key: value for key, value in sources.items() if key.startswith(f"sysroot-{args.cpu}-")}
    stamp = json.dumps(inputs, sort_keys=True, indent=2) + "\n"
    digest = hashlib.sha256(stamp.encode()).hexdigest()[:16]
    destination = args.directory.resolve() / f"{args.cpu}-{digest}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if (destination / "inputs.json").read_text() != stamp:
            parser.error(f"sysroot input stamp mismatch: {destination}")
        print(destination)
        return
    packages = ["glibc", "glibc-devel", "glibc-headers", "kernel-headers"]
    if args.cpu == "amd64":
        packages.append("gcc")
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staging = Path(temporary) / "sysroot"
        staging.mkdir()
        for package in packages:
            archive = fetch(f"sysroot-{args.cpu}-{package}", args.cache.resolve())
            producer = subprocess.Popen(["rpm2cpio", str(archive)], stdout=subprocess.PIPE)
            try:
                subprocess.run(["cpio", "--extract", "--make-directories", "--quiet",
                                "--no-absolute-filenames"], stdin=producer.stdout,
                               cwd=staging, check=True)
            finally:
                producer.stdout.close()
                status = producer.wait()
            if status:
                raise subprocess.CalledProcessError(status, producer.args)
        if args.cpu == "amd64":
            # Modern GCC's static unwinder references _dl_find_object (glibc 2.35).
            # Match the static GCC runtime to this sysroot instead.
            gcc = staging / "usr/lib/gcc/x86_64-redhat-linux/4.8.2"
            for name in ("libgcc.a", "libgcc_eh.a"):
                shutil.copy2(gcc / name, staging / "usr/lib64" / name)
        (staging / "inputs.json").write_text(stamp)
        staging.rename(destination)
    print(destination)


if __name__ == "__main__":
    main()
