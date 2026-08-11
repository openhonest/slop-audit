# slop-audit-rs

A compiled, portable build of the Slop Audit L1 panel, for running the audit from a USB key or an offline machine with no Python and no install.

Why Rust: the one hard part of shipping the Python tool is the tree-sitter grammars, which are compiled C extensions, one per platform. In Rust the same grammars link **statically into the binary**, so the result is a single self-contained file per platform (no shipped `.so`), and it cross-compiles to macOS, Linux, and Windows from one machine.

The Python `l1_analyzer` stays the **canonical** instrument. This crate is a certified-equivalent redistribution: each indicator is ported against the shared skeleton and validated by running both tools on the same repos and diffing the value and band.

## Status

Ported and validated equal to the Python reference:

- **L1.1 through L1.8** (git-log commit ratios)
- **L1.9 through L1.11** (config presence)
- **L1.15** type-escape density, **L1.16** trailing whitespace, **L1.17** god-file concentration (Python-language path)
- the `absolute_paths` additive check

Round two (against the same skeleton, same validated-equal discipline): L1.12/L1.13/L1.14, L1.18 and L1.18b (the state analysis), the additive `thread_surface` and `path_cover`, the multi-language grammars for the cross-language source indicators, and the L1.19/L1.20 runtime harnesses.

The runtime indicators, when added, will still drive the host's own toolchains to run the target's tests, exactly as the Python tool does; that part cannot be bundled, because it is the target's build environment.

## Build

```
cargo build --release                                  # native single binary
cargo zigbuild --release --target x86_64-unknown-linux-musl   # fully-static Linux (needs zig + cargo-zigbuild)
```

Run: `./target/release/slop-audit-rs <repo>`.

Adding an indicator: write `src/indicators/<name>.rs` exposing `pub fn analyze(repo: &Path) -> Indicator` on the shared skeleton in `src/lib.rs`, register it in `src/indicators/mod.rs` and `src/main.rs`, and validate it equal to `l1_analyzer` on real repos before landing.

License: Apache-2.0.
