#!/usr/bin/env python3
"""Resolve and validate the serial of a release tag before starting builds."""

import argparse
import json
import os
import subprocess

from fetch import ROOT
from distribution import serial_from_tag


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    wine = json.loads((ROOT / "sources.json").read_text())["wine"]["version"]
    serial = serial_from_tag(args.tag, wine)
    revision = subprocess.check_output(["gh", "api", f"repos/{args.repository}/commits/{args.tag}",
                                       "--jq", ".sha"], text=True).strip()
    if revision != args.commit:
        parser.error("dispatch at the release tag ref; the tag must match the workflow commit")
    with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
        stream.write(f"serial={serial}\ntag={args.tag}\n")


if __name__ == "__main__":
    main()
