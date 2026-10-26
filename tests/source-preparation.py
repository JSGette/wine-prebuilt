#!/usr/bin/env python3
"""Check real Wine source preparation inside an ignored Git work directory."""

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from build import prepare_wine
from fetch import ROOT, fetch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=ROOT / ".work")
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    source = fetch("wine", work / "cache")
    with tempfile.TemporaryDirectory(prefix="patch-regression-", dir=work) as temporary:
        repository = Path(temporary)
        subprocess.run(["git", "init", "--quiet", str(repository)], check=True)
        (repository / ".gitignore").write_text(".work/\n")
        staging = repository / ".work"
        staging.mkdir()
        macos = staging / "macos"
        prepare_wine(macos, source, "macos-arm64")
        assert "wine_darwin_minos" in (macos / "configure").read_text(), "macOS patches were skipped"
        assert "libarm64ecfex.dll" in (macos / "loader/wine.inf.in").read_text()
        linux = staging / "linux"
        prepare_wine(linux, source, "linux-arm64")
        assert "libarm64ecfex.dll" in (linux / "loader/wine.inf.in").read_text(), "FEX registration was skipped"
        assert (linux / "configure").read_bytes() == (source / "configure").read_bytes()
        assert "libarm64ecfex.dll" not in (source / "loader/wine.inf.in").read_text()
    print("Wine patches applied inside ignored Git directories; cached input stayed unchanged")


if __name__ == "__main__":
    main()
