# Distribution contents and release gates

Each runtime archive must be accompanied by its matching `-sources.tar.gz` and
SHA-256 files. The source archive includes the exact patched Wine source, the
populated FEX source and dependencies when used, and the build recipes/patches.
Do not redistribute only a binary while dropping these companion artifacts.

Wine and its derived patches retain LGPL-2.1-or-later licensing, with additional
notices for code incorporated by Wine. FEX is MIT-licensed and has third-party
components with their own notices. LLVM-MinGW contains LLVM runtimes and MinGW
runtime code under their respective licenses. Linux native code may include
GCC runtime code under the GCC Runtime Library Exception. The repository's MIT
license applies only to its original recipes and tests.

`LICENSES/` preserves named license/copyright/notice files from the source and
compiler trees. Complete source archives also preserve per-file notices. Review
the distribution and linked components when changing dependencies: filename
collection alone is not a license inventory or proof of compliance. Windows
Ninja downloads are test inputs and are not included in runtime archives.

## Release gates

1. Verify all download checksums and retain exact source revisions and patches.
2. Audit every ELF/Mach-O for architecture, runtime dependencies and relative
   search paths. Linux GLIBC version references must not exceed 2.17.
3. Test the final extracted archive at a different path, with fresh prefixes.
   Test all advertised guest CPUs, not merely `wine --version`.
4. Run Linux checks in both the current builder and glibc 2.17 userspace.
5. Attach the runtime, source, checksums, qualification reports and provenance.
6. Review macOS signing before promoting an unsigned draft to a user-facing
   release. Qualification on a build machine does not establish Gatekeeper
   acceptance of a quarantined download on another machine.

The initial macOS archive is a command-line runtime, not a signed/notarized app.
ARM64 and x64 tests require neither Rosetta nor a restricted provisioning profile.
i386 needs separate work on low-address mappings and Apple's cross-architecture
entitlement. Any later signing pipeline must sign the final layout, preserve
the signatures during packaging, notarize/staple where applicable, and test the
downloaded artifact on a separate machine. Never solve this by disabling SIP or
asking users to bypass Gatekeeper.
