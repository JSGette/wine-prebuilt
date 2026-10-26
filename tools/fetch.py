#!/usr/bin/env python3
"""Fetch a checksum-pinned input from sources.json into the local build cache."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


def fetch(name, cache):
    item = json.loads((ROOT / "sources.json").read_text())[name]
    digest = item["sha256"]
    downloads = cache / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    archive = downloads / digest
    if not archive.exists():
        with tempfile.NamedTemporaryFile(dir=downloads, delete=False) as output:
            temporary = Path(output.name)
            with urllib.request.urlopen(item["url"], timeout=120) as response:
                shutil.copyfileobj(response, output)
        with temporary.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != digest:
            raise ValueError(f"{name}: expected {digest}, downloaded {actual}: {temporary}")
        temporary.replace(archive)
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != digest:
        raise ValueError(f"corrupt cache entry: {archive}")
    if item.get("format") == "file":
        return archive
    destination = cache / "sources" / f"{name}-{digest[:16]}"
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination.parent) as staging:
            with tarfile.open(archive) as source:
                source.extractall(staging, filter="data")
            (top,) = Path(staging).iterdir()
            top.rename(destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--cache", type=Path,
                        default=Path(os.environ.get("WINE_BUILD_CACHE", ROOT / ".work/cache")))
    args = parser.parse_args()
    print(fetch(args.name, args.cache.resolve()))
