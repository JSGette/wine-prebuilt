Source-built headless Wine. Download the archive for the executor's OS and CPU;
ARM64 archives include FEX for x64 Windows programs. Windows executors run
natively and need no archive.

Linux requires glibc 2.17+ and a UTF-8 locale. macOS targets Apple Silicon with an
imposed deployment minimum of 26.5; runtime reports identify the tested OS.
This does not establish Wine/FEX's intrinsic minimum or qualify an older macOS.
macOS i386 is unsupported; no Rosetta fallback is used.

This is a draft. The macOS archive is unsigned and not notarized. Review the
distribution gates before promoting it to a public release. Runtime archives
must remain accompanied by their exact source archives, notices and checksums.
