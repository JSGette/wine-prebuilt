#!/usr/bin/env python3
"""Exercise real Windows payloads against an already extracted, relocated runtime."""

import argparse
from functools import partial
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import tempfile


def windows_path(path):
    return "Z:" + str(path.resolve()).replace("/", "\\")


def run(command, environment, log, expected=0, timeout=90, container=None):
    if container:
        command = ["docker", "exec", container, "env", "-i",
                   *[f"{key}={value}" for key, value in environment.items()], *command]
        environment = os.environ.copy()
    with log.open("wb") as output:
        process = subprocess.Popen(command, env=environment, stdout=output, stderr=output,
                                   start_new_session=True)
        try:
            status = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise RuntimeError(f"Timed out: {command}; log: {log}") from None
    if status != expected:
        raise RuntimeError(f"Exit {status}, expected {expected}: {command}\n{log.read_text(errors='replace')}")
    return log.read_text(errors="replace")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("fixtures", type=Path)
    parser.add_argument("--guests", nargs="+", choices=("arm64", "amd64", "i386"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--container", help="Execute in an existing container; mount input/output paths unchanged")
    parser.add_argument("--locale", default="en_US.UTF-8" if platform.system() == "Darwin" else "C.UTF-8",
                        help="An installed UTF-8 locale on the executor")
    parser.add_argument("--prefix-root", type=Path,
                        help="Optional temporary filesystem for large Wine prefixes")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    runtime = args.runtime.resolve()
    fixtures = args.fixtures.resolve()
    loader = str(runtime / "bin/wine")
    server = str(runtime / "bin/wineserver")
    results = []
    execute = partial(run, container=args.container)
    for guest in args.guests:
        # Keep prefixes and logs on failure; never share state between CPU tests.
        scratch = Path(tempfile.mkdtemp(prefix=f"{guest} space-", dir=args.output.resolve()))
        prefix = (args.prefix_root.resolve() / scratch.name) if args.prefix_root else scratch / "prefix"
        environment = {
            "HOME": str(scratch), "TMPDIR": str(scratch), "PATH": "/usr/bin:/bin",
            "WINEPREFIX": str(prefix), "WINEARCH": "win64",
            "WINESERVER": server, "WINEDEBUG": "-all",
            "LC_ALL": args.locale,
            "WINEDLLOVERRIDES": "mscoree,mshtml,winemenubuilder.exe=",
        }
        try:
            execute([loader, "wineboot.exe", "--init"], environment, scratch / "boot.log")
            for child in args.guests:
                marker = scratch / f"output {child} café.txt"
                log = execute([loader, str(fixtures / f"{guest}.exe"), "--exercise",
                           windows_path(fixtures / f"{guest}.dll"),
                           windows_path(fixtures / f"{child}.exe"), windows_path(marker),
                           "argument with spaces", "café", ""], environment,
                          scratch / f"child-{child}.log")
                assert f"child={child}" in log and f"payload={guest}" in log, log
                assert marker.read_text() == "wine-prebuilt: args, DLL, threads, child OK\n"
            execute([loader, str(fixtures / f"{guest}.exe"), "--exit", "7"], environment,
                scratch / "exit.log", expected=7)
            result = {"guest": guest, "children": args.guests, "status": "passed", "logs": str(scratch)}
            results.append(result)
            print(json.dumps(result), flush=True)
        finally:
            execute([server, "-k"], environment, scratch / "stop.log", timeout=10)
            execute([server, "-w"], environment, scratch / "wait.log", timeout=10)
    (args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
