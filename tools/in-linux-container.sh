#!/usr/bin/env bash
set -euo pipefail

# Environment only: the caller chooses the build, packaging or test operation.
# Build this image first with: docker build -t wine-builder .
root=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$root/.work/home"
# GitHub's per-step output file lives outside the checkout. Forward only this
# output channel; each operation still receives its ordinary command-line inputs.
outputs=()
if [[ -n ${GITHUB_OUTPUT:-} ]]; then
    outputs=(--volume "$GITHUB_OUTPUT:$GITHUB_OUTPUT" --env "GITHUB_OUTPUT=$GITHUB_OUTPUT")
fi
exec docker run --rm --user "$(id -u):$(id -g)" \
    --volume "$root:$root" --workdir "$root" \
    --env "HOME=$root/.work/home" \
    "${outputs[@]}" wine-builder "$@"
