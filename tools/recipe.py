"""Identify the complete release recipe, excluding local build/cache files."""

import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ENTRIES = ("tools", "tests", "patches", ".github", "Dockerfile", "sources.json",
           "README.md", "DISTRIBUTION.md", "LICENSE", ".clang-format", ".gitignore")


def digest(root):
    result = hashlib.sha256()
    for entry in ENTRIES:
        path = root / entry
        files = sorted(path.rglob("*")) if path.is_dir() else [path]
        for file in files:
            if not file.is_file() or "__pycache__" in file.parts or file.suffix == ".pyc":
                continue
            result.update(str(file.relative_to(root)).encode() + b"\0")
            result.update(hashlib.sha256(file.read_bytes()).digest())
    return result.hexdigest()


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def builder_identity():
    identity = {"host": platform.platform(), "python": sys.version}
    if platform.system() == "Darwin":
        compiler = Path(command("xcrun", "--find", "clang"))
        identity.update(
            compiler=command("/usr/bin/clang", "--version"),
            compiler_path=str(compiler),
            sdk=command("xcrun", "--show-sdk-path"),
            sdk_version=command("xcrun", "--show-sdk-build-version"),
            packages=command("brew", "list", "--versions", "bison", "cmake", "ninja"),
        )
    else:
        identity.update(compiler=command("gcc", "--version"),
                        packages=command("dpkg-query", "-W"))
        compiler = Path(command("gcc", "-print-prog-name=cc1"))
    with compiler.open("rb") as stream:
        identity["compiler_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    return identity


def build_id(recipe_digest, builder):
    value = recipe_digest + json.dumps(builder, sort_keys=True)
    return hashlib.sha256(value.encode()).hexdigest()[:16]
