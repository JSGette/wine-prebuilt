#!/usr/bin/env python3
"""Build one executor-native, headless Wine distribution from pinned inputs."""

import argparse
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import tempfile

from fetch import ROOT, fetch
import recipe

PLATFORMS = {
    "linux-amd64": ("Linux", "x86_64", "x86_64,i386"),
    "linux-arm64": ("Linux", "aarch64", "arm64ec,aarch64,i386"),
    "macos-arm64": ("Darwin", "arm64", "arm64ec,aarch64,i386"),
}


def run(*command, **kwargs):
    subprocess.run(command, check=True, **kwargs)


def prepare_wine(destination, source, target):
    if destination.exists():
        return
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staging = Path(temporary) / "source"
        shutil.copytree(source, staging, symlinks=True)
        patches = sorted((ROOT / "patches/macos").glob("*.patch"))
        if target == "macos-arm64":
            for patch in patches:
                run("git", "apply", str(patch), cwd=staging)
        elif target == "linux-arm64":
            # The emulator registration is shared; macOS host adaptations are not.
            patch = next((ROOT / "patches/macos").glob("0004-*.patch"))
            run("git", "apply", "--include=loader/wine.inf.in", str(patch), cwd=staging)
        staging.rename(destination)


def prepare_fex(destination, cache):
    if destination.exists():
        return
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staging = Path(temporary) / "source"
        shutil.copytree(fetch("fex", cache), staging, symlinks=True)
        for name in ("fmt", "range-v3", "unordered_dense", "xxhash", "rpmalloc", "cpp-optparse"):
            parent = "Source/Common" if name == "cpp-optparse" else "External"
            shutil.copytree(fetch("fex-" + name, cache), staging / parent / name,
                            dirs_exist_ok=True, symlinks=True)
        staging.rename(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=PLATFORMS)
    parser.add_argument("--sysroot", type=Path)
    parser.add_argument("--work", type=Path, default=ROOT / ".work")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    system, cpu, architectures = PLATFORMS[args.platform]
    if (platform.system(), platform.machine()) != (system, cpu):
        parser.error(f"{args.platform} must build on native {system}/{cpu}")
    if system == "Linux" and args.sysroot is None:
        parser.error("Linux builds require the pinned glibc 2.17 --sysroot")
    work = args.work.resolve()
    cache = work / "cache"
    fingerprint = recipe.digest(ROOT)
    builder = recipe.builder_identity()
    directory = work / args.platform / recipe.build_id(fingerprint, builder)
    directory.mkdir(parents=True, exist_ok=True)
    toolchain = fetch("toolchain-" + args.platform, cache)
    source = directory / "wine-source"
    prepare_wine(source, fetch("wine", cache), args.platform)
    install = directory / "install"
    environment = os.environ.copy()
    for name in ("CC", "CXX", "CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS", "SDKROOT",
                 "MACOSX_DEPLOYMENT_TARGET", "PKG_CONFIG_PATH", "CONFIG_SITE"):
        environment.pop(name, None)
    environment["PATH"] = str(toolchain / "bin") + os.pathsep + environment["PATH"]
    environment["JOBS"] = str(args.jobs)
    sources = json.loads((ROOT / "sources.json").read_text())
    if system == "Darwin":
        environment.update(CC="/usr/bin/clang", CXX="/usr/bin/clang++",
                           MACOSX_DEPLOYMENT_TARGET="26.5")
        bison = subprocess.check_output(["brew", "--prefix", "bison"], text=True).strip()
        environment["BISON"] = str(Path(bison) / "bin/bison")
    else:
        sysroot = args.sysroot.resolve()
        expected = {key: value for key, value in sources.items()
                    if key.startswith(f"sysroot-{args.platform.removeprefix('linux-')}-")}
        if json.loads((sysroot / "inputs.json").read_text()) != expected:
            parser.error("--sysroot does not match the pinned sources.json inputs")
        flags = [f"--sysroot={sysroot}", f"-B{sysroot}/usr/lib64",
                 f"-L{sysroot}/lib64", "-static-libgcc"]
        environment["CC"] = shlex.join(["gcc", *flags])
        environment["CXX"] = shlex.join(["g++", *flags])
    print(f"Building {args.platform}: {directory}", flush=True)
    run("bash", str(ROOT / "tools/build-wine.sh"), str(source),
        str(directory / "wine-build"), str(install), architectures, env=environment)
    if cpu != "x86_64":
        fex = directory / "fex-source"
        prepare_fex(fex, cache)
        run("bash", str(ROOT / "tools/build-fex.sh"), str(fex),
            str(directory / "fex-build"), str(install), env=environment)
    if recipe.digest(ROOT) != fingerprint:
        raise RuntimeError("Recipe changed during the build; rerun with the final recipe before packaging")
    (directory / "build.json").write_text(json.dumps({
        "platform": args.platform, "wine": sources["wine"]["version"], "fex": cpu != "x86_64",
        "install": str(install), "toolchain": str(toolchain),
        "recipe_sha256": fingerprint,
        "builder": builder,
        "sources": sources,
        "host": platform.platform(),
        "native_compiler": subprocess.check_output(
            [*shlex.split(environment["CC"]), "--version"], text=True).strip(),
        "sysroot": str(args.sysroot.resolve()) if args.sysroot else None,
    }, indent=2) + "\n")
    print(install)


if __name__ == "__main__":
    main()
