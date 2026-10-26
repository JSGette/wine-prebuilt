#!/usr/bin/env bash
set -euo pipefail

case "$(uname -m)" in
    x86_64) cpu=amd64 ;;
    aarch64) cpu=arm64 ;;
    *) echo "Use a native Linux amd64 or arm64 runner" >&2; exit 1 ;;
esac
root=$(cd "$(dirname "$0")/.." && pwd)
work=${WINE_BUILD_WORK:-"$root/.work"}
sysroot=$(python3 "$root/tools/prepare-sysroot.py" "$cpu" "$work/sysroots" --cache "$work/cache")
python3 "$root/tools/build.py" "linux-$cpu" --work "$work" --sysroot "$sysroot" --jobs "${JOBS:-4}"
