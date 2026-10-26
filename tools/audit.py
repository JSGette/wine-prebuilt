#!/usr/bin/env python3
"""Reject host architecture mistakes and unexpected runtime dependencies."""

import argparse
import json
from pathlib import Path
import re
import subprocess

GLIBC_LIBRARIES = {"libc.so.6", "libm.so.6", "libdl.so.2", "libpthread.so.0",
                   "libresolv.so.2", "librt.so.1"}
ELF_MACHINES = {"linux-amd64": "Advanced Micro Devices X86-64", "linux-arm64": "AArch64"}
INTERPRETERS = {"linux-amd64": "/lib64/ld-linux-x86-64.so.2",
                "linux-arm64": "/lib/ld-linux-aarch64.so.1"}


def output(*command):
    return subprocess.check_output(command, text=True)


def audit(root, platform):
    records = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            if path.readlink().is_absolute() or not path.resolve().is_relative_to(root):
                raise ValueError(f"non-relocatable symlink: {path}")
            if not path.exists():
                raise ValueError(f"dangling symlink: {path}")
            continue
        if not path.is_file():
            continue
        with path.open("rb") as stream:
            magic = stream.read(4)
        relative = str(path.relative_to(root))
        if magic == b"\x7fELF":
            if platform not in ELF_MACHINES:
                raise ValueError(f"ELF in macOS distribution: {path}")
            info = output("readelf", "-h", "-l", "-d", "-V", str(path))
            machine = re.search(r"Machine:\s*(.+)", info).group(1)
            if machine != ELF_MACHINES[platform]:
                raise ValueError(f"wrong ELF machine: {path}: {machine}")
            versions = sorted(set(re.findall(r"Name: GLIBC_([0-9.]+)", info)))
            if any(tuple(map(int, version.split("."))) > (2, 17) for version in versions):
                raise ValueError(f"glibc newer than 2.17: {path}: {versions}")
            libraries = re.findall(r"Shared library: \[([^]]+)\]", info)
            for library in libraries:
                if library not in GLIBC_LIBRARIES and library not in ("ntdll.so", "win32u.so"):
                    raise ValueError(f"unexpected ELF dependency: {path}: {library}")
            interpreters = re.findall(r"Requesting program interpreter: ([^]]+)", info)
            if interpreters and interpreters != [INTERPRETERS[platform]]:
                raise ValueError(f"unexpected ELF interpreter: {path}: {interpreters}")
            for value in re.findall(r"\((?:RPATH|RUNPATH)\).*?\[([^]]+)\]", info):
                if any(not entry.startswith("$ORIGIN/") for entry in value.split(":")):
                    raise ValueError(f"non-relative ELF search path: {path}: {value}")
            records.append({"path": relative, "machine": machine, "glibc": versions,
                            "libraries": libraries, "interpreter": interpreters})
        elif magic in (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
            if platform != "macos-arm64" or output("lipo", "-archs", str(path)).strip() != "arm64":
                raise ValueError(f"unexpected Mach-O architecture: {path}")
            libraries = [line.strip().split(" (", 1)[0]
                         for line in output("otool", "-L", str(path)).splitlines()[1:]]
            identifiers = output("otool", "-D", str(path)).splitlines()[1:]
            libraries = [library for library in libraries if library not in identifiers]
            commands = output("otool", "-l", str(path))
            rpaths = re.findall(r"cmd LC_RPATH\s+cmdsize \d+\s+path (.+?) \(offset", commands)
            search = []
            for entry in rpaths:
                if not entry.startswith("@loader_path/"):
                    raise ValueError(f"non-relative Mach-O search path: {path}: {entry}")
                directory = (path.parent / entry.removeprefix("@loader_path/")).resolve()
                if not directory.is_relative_to(root):
                    raise ValueError(f"Mach-O search path outside archive: {path}: {entry}")
                search.append(directory)
            for library in libraries:
                if library.startswith(("/usr/lib/", "/System/Library/")):
                    continue
                if library.startswith("@rpath/") and any(
                    (directory / library.removeprefix("@rpath/")).is_file() for directory in search
                ):
                    continue
                raise ValueError(f"unexpected Mach-O dependency: {path}: {library}")
            records.append({"path": relative, "machine": "arm64", "libraries": libraries})
    if not records:
        raise ValueError("No native executables found")
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("platform", choices=("linux-amd64", "linux-arm64", "macos-arm64"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.runtime.resolve(), args.platform), indent=2) + "\n")
