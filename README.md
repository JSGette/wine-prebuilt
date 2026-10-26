# wine-prebuilt

Source-built, headless Wine distributions for build tools. One archive per
executor OS/CPU; ARM64 archives include FEX for x64 Windows programs. No Rosetta,
QEMU, Linux guest rootfs, system Wine installation, or Windows SDK is required.

| Executor | Windows guest CPUs | Runtime requirement |
| --- | --- | --- |
| Linux amd64 | amd64, i386 | glibc 2.17+, installed UTF-8 locale |
| Linux ARM64 | ARM64, amd64, i386 | glibc 2.17+, installed UTF-8 locale |
| macOS ARM64 | ARM64, amd64 | macOS 26.5+; initial qualification only |

macOS i386 is **not supported** in the initial distribution. Its startup needs
low-address memory that the current unsigned command-line loader cannot obtain.
Developer ID signing, Apple's restricted cross-architecture entitlement, and
notarization are a separate qualification task. ARM64/x64 execution does not
establish that arbitrary Windows applications work; see [limitations](#limitations).

Windows amd64 and ARM64 executors run Windows programs natively and need no Wine
archive. These three distributions therefore cover the non-Windows portion of
the five-executor plan. Bazel integration belongs in `rules_wine`.

## Inputs

The initial recipe pins Wine **11.20**, LLVM-MinGW **20261020**, and MetalSharp's
FEX fork at `bfb6ef17d77dfeb751a9e60775b61b7a5200627b`. Downloads have SHA-256
checksums in `sources.json`. Wine 11.20 is a development release, not stable 11.0.

Linux amd64 uses upstream Wine. Linux ARM64 adds the FEX registry entries.
macOS applies 17 focused Wine patches, retaining their authorship and original
commit IDs. See [patch provenance](patches/PROVENANCE.md). FEX is built twice:
an ARM64EC module for x64 code and an ARM64 WoW64 module for i386 code. Both ship
inside the ARM64 runtime rather than as separate guest-specific archives.

## Build

Build on a native executor of the artifact CPU. Python 3.12+ is required.
Intermediate files and downloaded inputs live under `.work/`; `out/` holds
distribution archives and reports.

Local builds and GitHub Actions use the same entry point. On a native Linux
executor with Docker installed, from the repository root:

```sh
python3 tools/build-distribution.py linux-amd64 --serial 1
# On a native ARM64 Linux executor:
python3 tools/build-distribution.py linux-arm64 --serial 1
```

The container uses a pinned Ubuntu base image. The compiler's target sysroot is
assembled from pinned CentOS 7 glibc 2.17 RPMs, without installing those RPMs on
the builder. amd64 additionally uses the matching static GCC unwinder to avoid
the newer `_dl_find_object` dependency. Wine still dynamically links the host's
glibc and its own Unix modules. It is not a static executable.

macOS ARM64, with Xcode command-line tools and Homebrew available:

```sh
brew install bison cmake ninja python@3.14 zstd
python3 tools/build-distribution.py macos-arm64 --serial 1
```

The native compiler is Apple Clang; the pinned LLVM-MinGW compiler produces PE
modules and FEX. No compiler runtime rebuild is needed. Build output names
include a recipe/input fingerprint. Each completed build writes `build.json`
alongside its source, build, install, and log directories. The distribution
command builds, packages, and tests the complete artifact set in `out/`.
Use `--output` for a fresh output directory when repeating a local build;
existing artifact versions are never overwritten.

## Package and qualify

The distribution command runs qualification automatically. To invoke packaging
and qualification separately, use the same builder/path layout that produced
`build.json`:

```sh
python3 tools/qualify.py .work/macos-arm64/BUILD_ID/build.json --output out
```

On Linux, invoke that command inside the build container using the build path
under `/work` and `--output /out`. Qualification audits native dependencies,
packages the archive, extracts it at a different path containing spaces, and
tests the extracted runtime. It exercises every advertised guest CPU, including
cross-CPU children, DLL loading, threads, Unicode/empty arguments, filesystem
output and exit codes, plus upstream Windows Ninja builds.

Linux CI also tests the extracted archive on CentOS 7 (glibc 2.17), with the
host Python test driver operating a container. No Python installation is
required in the runtime image. `en_US.UTF-8` is used there; CentOS 7 does not
provide `C.UTF-8`.

Archives contain `bin/wine`, `bin/wineserver`, Wine's complete runtime tree,
license notices, and `manifest.json` directly at the archive root. No wrapper
directory or `strip_prefix` is required. Keep the directory layout intact. Use a fresh
`WINEPREFIX` for independent executions; Wine's prefix is mutable runtime state.

```sh
export WINEPREFIX="$PWD/prefix"
export WINESERVER="$PWD/wine/bin/wineserver"
"$PWD/wine/bin/wine" path/to/tool.exe
"$WINESERVER" -w
```

## Release updates

Update the source/compiler/dependency pins and checksums in `sources.json`,
review/rebase the patch series, then run the native three-platform build matrix.
Arbitrary upstream-version overrides and historical backfills are not supported.
Do not point a release at a moving branch. Increment the artifact serial for a
recipe change without a Wine version change.

Tags have the form `<wine-version>.<artifact-serial>`, for example `11.20.1`
for Wine 11.20, serial 1. Serial 0 is also valid. CI and release entry points
call `reusable-build.yml`; releases use `reusable-release.yml` to require all
three executors, verify attestations, and assemble a **draft** GitHub release.
Publishing remains an explicit step while macOS signing is outstanding.

```sh
git tag 11.20.1
git push origin 11.20.1
# Start a fresh release attempt at the same tagged recipe:
gh workflow run release.yml --ref 11.20.1 -f tag_name=11.20.1
```

For a failed upload, use GitHub's **Re-run failed jobs** to retain the original
build artifacts. Uploads retry transient failures and accept existing assets
only when their bytes match. They never clobber conflicting assets or add missing
assets to a published release. A fresh build may differ; give changed artifacts
a new serial instead of attempting to replace an existing version.

Release attestations are mandatory. Pull-request builds run without attestation;
trusted CI builds and releases generate it. Every executor exports its signed
`.attestation.jsonl` bundle alongside the archives, checksums and reports.

## Consumer contract

Runtime names are `wine-<os>-<cpu>-<wine-version>.<serial>.tar.gz` and `.tar.zst`.
The supported executor pairs are `linux-amd64`, `linux-arm64`, and `macos-arm64`.
Both compression formats contain the same normalized tar stream, verified during
packaging. Each has a `.sha256` file. Source companions insert `-sources` before
`.tar`; they contain `wine/`, optional `fex/`, `recipe/` and `manifest.json`.

For example, once release `11.20.1` is published:

```text
https://github.com/hermeticbuild/wine-prebuilt/releases/download/11.20.1/wine-linux-arm64-11.20.1.tar.zst
```

Consumers pin the release URL and checksum, extract the whole archive, and use
`bin/wine` and `bin/wineserver`. Schema version 1 of `manifest.json` records
`executor.os`, `executor.cpu`, `windows_cpus`, `requirements`, `executables`,
`artifact_version`, separate Wine version/serial, source pins and the recipe
fingerprint. The same manifest is available as a `.manifest.json` release asset.
Bazel setup and platform/toolchain selection belong in `rules_wine`.

Verify a download's provenance with its matching executor bundle:

```sh
gh attestation verify wine-linux-arm64-11.20.1.tar.zst \
  --repo hermeticbuild/wine-prebuilt \
  --bundle wine-linux-arm64-11.20.1.attestation.jsonl \
  --signer-workflow hermeticbuild/wine-prebuilt/.github/workflows/reusable-build.yml
```

Ship the matching source archives and checksum files with every runtime archive.
See [distribution requirements](DISTRIBUTION.md). The recipe normalizes archive
metadata, but does not claim byte-identical binaries: runner SDKs and host build
packages still vary. Their identities belong in build reports.

## Limitations

- Headless profile: graphics drivers, audio, printing, multimedia, USB and other
  optional integrations are disabled. This is not a gaming Wine distribution.
- GnuTLS/Kerberos integrations are disabled. Windows programs requiring Wine's
  HTTPS or domain-authentication implementation may not work.
- No macOS amd64 build; no Rosetta fallback; no ARM32 Windows guest.
- macOS FEX integration is young. Initial ARM64/x64 tests cover command-line
  build tools, not arbitrary PE loading or every Windows memory-layout behavior.
- macOS i386 is unqualified and fails the initial startup test. Unsigned build
  archives are not a completed Gatekeeper/notarization distribution solution.
- Wine is not a security sandbox. A Windows process inherits the executor's
  filesystem and network access. Prefix isolation does not change that.
- A glibc ABI audit covers linked symbols, not every kernel/API requirement.
  CentOS 7 userspace tests run on the CI host kernel; an actual old-kernel floor
  has not been established.
