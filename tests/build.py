#!/usr/bin/env python3
"""Cross-compile independent Win32 integration payloads with the pinned compiler."""

import argparse
from pathlib import Path
import subprocess

TRIPLES = {"amd64": "x86_64", "arm64": "aarch64", "i386": "i686"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("toolchain", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve().parent
    for cpu, triple in TRIPLES.items():
        compiler = args.toolchain.resolve() / "bin" / f"{triple}-w64-mingw32-clang++"
        subprocess.run([str(compiler), "-O2", "-static", "-municode",
                        str(source / "payload.cc"), "-o", str(args.output / f"{cpu}.exe")],
                       check=True)
        subprocess.run([str(compiler), "-O2", "-static", "-shared",
                        str(source / "payload-dll.cc"), "-o", str(args.output / f"{cpu}.dll")],
                       check=True)


if __name__ == "__main__":
    main()
