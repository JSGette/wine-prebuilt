"""Stable names and platform metadata for released Wine distributions."""

import hashlib
import re
from pathlib import Path

MACOS_DEPLOYMENT_TARGET = "26.5"

PLATFORMS = {
    "linux-amd64": {"guests": ["amd64", "i386"], "requirements": {"glibc": "2.17", "utf8_locale": True}},
    "linux-arm64": {"guests": ["arm64", "amd64", "i386"], "requirements": {"glibc": "2.17", "utf8_locale": True}},
    "macos-arm64": {"guests": ["arm64", "amd64"], "requirements": {"macos": MACOS_DEPLOYMENT_TARGET, "rosetta": False}},
}
FORMATS = (".tar.gz", ".tar.zst")


def version(wine, serial):
    if serial < 0:
        raise ValueError("artifact serial must be nonnegative")
    return f"{wine}.{serial}"


def basename(platform, wine, serial):
    return f"wine-{platform}-{version(wine, serial)}"


def serial_from_tag(tag, wine):
    match = re.fullmatch(re.escape(wine) + r"\.(0|[1-9][0-9]*)", tag)
    if not match:
        raise ValueError(f"expected a tag of the form {wine}.<serial>")
    return int(match.group(1))


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()
