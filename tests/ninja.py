#!/usr/bin/env python3
"""Run an upstream Windows Ninja release and inspect the file its child produces."""

import argparse
import os
from pathlib import Path
import platform
import sys
import tempfile
import zipfile

from run import run, windows_path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from fetch import fetch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("guest", choices=("amd64", "arm64"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix=f"ninja-{args.guest} space-", dir=args.output.resolve()))
    archive = fetch("test-ninja-" + args.guest, args.cache.resolve())
    with zipfile.ZipFile(archive) as source:
        (scratch / "ninja.exe").write_bytes(source.read("ninja.exe"))
    (scratch / "build.ninja").write_text(
        'rule write\n  command = cmd.exe /d /c echo ninja-ok > "$out"\n'
        'build result.txt: write\n')
    runtime = args.runtime.resolve()
    loader = str(runtime / "bin/wine")
    server = str(runtime / "bin/wineserver")
    environment = {
        "HOME": str(scratch), "TMPDIR": str(scratch), "PATH": "/usr/bin:/bin",
        "WINEPREFIX": str(scratch / "prefix"), "WINEARCH": "win64", "WINESERVER": server,
        "WINEDEBUG": "-all", "WINEDLLOVERRIDES": "mscoree,mshtml,winemenubuilder.exe=",
        "LC_ALL": "en_US.UTF-8" if platform.system() == "Darwin" else "C.UTF-8",
    }
    try:
        run([loader, "wineboot.exe", "--init"], environment, scratch / "boot.log")
        run([loader, str(scratch / "ninja.exe"), "-C", windows_path(scratch), "result.txt"],
            environment, scratch / "ninja.log")
        assert (scratch / "result.txt").read_text().strip() == "ninja-ok"
        print(f"Windows Ninja ({args.guest}) passed: {scratch}")
    finally:
        run([server, "-k"], environment, scratch / "stop.log", timeout=10)
        run([server, "-w"], environment, scratch / "wait.log", timeout=10)


if __name__ == "__main__":
    main()
