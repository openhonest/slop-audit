This release carries the portable slop-audit binaries. Each one is a single self-contained file: no Python, no Rust toolchain, no install step and no network.

Three platforms ship: x86_64 Linux, built against musl and statically linked so it has no libc dependency; x86_64 Windows; and arm64 macOS. The tree-sitter grammars for nine languages (C, C#, Go, Java, JavaScript, Python, Ruby, Rust and TypeScript) link statically into the binary, which is why there is nothing to install beside it.

During the build the Linux and macOS binaries each audit this repository, and the release fails if their two panels differ by one byte.

The Windows binary is cross-built from Linux with mingw-w64 and has never been executed, because no Windows machine was available to run it. Report what it does.

Verify a download against `SHA256SUMS` before running it.

Usage: `./slop-audit-rs <repo> [--lang KEY] [--tsv]`
