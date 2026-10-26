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

Linux, from the repository root:

```sh
docker build -t wine-prebuilt-builder .
mkdir -p .work out
docker run --rm \
  -v "$PWD:/src:ro" -v "$PWD/.work:/work" -v "$PWD/out:/out" \
  -e WINE_BUILD_WORK=/work -e JOBS=4 \
  wine-prebuilt-builder bash tools/build-linux.sh
```

The container uses a pinned Ubuntu base image. The compiler's target sysroot is
assembled from pinned CentOS 7 glibc 2.17 RPMs, without installing those RPMs on
the builder. amd64 additionally uses the matching static GCC unwinder to avoid
the newer `_dl_find_object` dependency. Wine still dynamically links the host's
glibc and its own Unix modules. It is not a static executable.

macOS ARM64, with Xcode command-line tools and Homebrew available:

```sh
brew install bison cmake ninja python@3.14
python3 tools/build.py macos-arm64 --jobs 4
```

The native compiler is Apple Clang; the pinned LLVM-MinGW compiler produces PE
modules and FEX. No compiler runtime rebuild is needed. Build output names
include a recipe/input fingerprint. Each completed build writes `build.json`
alongside its source, build, install, and log directories.

## Package and qualify

Run inside the same builder/path layout that produced `build.json`:

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
license notices, and a manifest. Keep the directory layout intact. Use a fresh
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
Do not point a release at a moving branch. Increment the artifact serial for a
recipe change without a Wine version change. The workflow prepares a **draft**
GitHub release after all matrix jobs pass; publishing remains an explicit step.

Ship the matching source archive and checksum files with every runtime archive.
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
