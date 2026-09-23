# slop-audit-rs

A compiled, portable build of the Slop Audit L1 panel, for running the audit from a USB key or an offline machine with no Python and no install.

Why Rust: the one hard part of shipping the Python tool is the tree-sitter grammars, which are compiled C extensions, one per platform. In Rust the same grammars link **statically into the binary**, so the result is a single self-contained file per platform (no shipped `.so`), and it cross-compiles to macOS, Linux, and Windows from one machine.

The Python `l1_analyzer` stays the **canonical** instrument. This crate is a certified-equivalent redistribution: each indicator is ported against the shared skeleton and validated by running both tools on the same repos and diffing the value and band.

## Status

All nine supported languages are linked and driven off one table (`src/lang.rs`, ported from `LANG_CFG`): Python, Rust, C, Java, TypeScript, C#, JavaScript, Ruby, Go.

Every indicator the panel carries is ported and validated equal to the Python reference: L1.1 through L1.20, L1.18b, and the four additive checks (absolute paths, thread surface, path cover, interleaving robustness). Twenty-five of twenty-five, across thirteen pinned repositories in nine languages, and across nine projects of our own whose tests are actually executed.

**L1.12, L1.13 and L1.14 changed shape, by decision of 2026-08-13 and done on 2026-08-19.** The Python reference delegated them to vulture, jscpd and gitleaks and reported `n/a` when the tool was absent, which was most of the time and, for L1.13, every time: it returned `n/a` on every repository this methodology had ever measured. Three ecosystems' worth of tooling cannot be asked of an auditor at a client site, so all three are now native on tree-sitter in both tools, and `spec/03-layer1-indicators.md` defines each as an algorithm precisely enough to reimplement rather than deferring to whichever tool happens to be installed.

The runtime indicators drive the target repository's own toolchain to run its tests, exactly as the Python tool does; that part cannot be bundled, because it is the target's build environment. A developer who has the repository and its tests has that toolchain. Four cases need one extra install beyond it, and each reports why rather than guessing: `cargo-llvm-cov` for Rust coverage, `coverage.py` and `pytest-randomly` for Python, `c8` for JavaScript, `lcov` for C.

## Validating a port

The standing discipline: no indicator lands until it is validated equal to `l1_analyzer` on real repos.

```
uv run validate.py <repo> [lang]
```

It runs both tools on the same repo, prints every indicator they both produce as EQUAL or DIFF, and exits non-zero on any DIFF. The Python side runs with `--no-exec`, which is the same static half the port covers today.

For the whole corpus at once:

```
uv run validate_corpus.py            # every entry in corpus.toml
uv run validate_corpus.py csharp     # one language, or one slug
```

`corpus.toml` pins a real repository at a fixed commit for every language the analyzer reads, and the manifest is the only place that says how many. They are cloned into `~/.cache/slop-audit-corpus`, or `$SLOP_AUDIT_CORPUS`, and nothing is vendored into this tree. Clones are full, not shallow, because L1.1 through L1.8 read the history.

Real repositories are the point. A synthetic fixture agrees on zeros; these do not. Measured 2026-08-19: 2,452 type escapes and 16,807 decision points across the corpus, L1.15 spanning 6.4% on RestSharp to 26.2% on requests, and L1.17 spanning zero to 15.1% on libuv. An indicator that only ever ran against a hand-written fixture has not been validated, it has been rehearsed.

The current panel is equal on every indicator, across every repository in the manifest and all nine languages. There are no GAP lines left: L1.14, the secret scan, was the last indicator the binary did not measure, and it was ported on 2026-09-23. The GAP machinery stays in the differ, because the next indicator the canon adds will arrive here after it arrives in the reference.

`validate_exec.py` is the second sweep, and it is the one that EXECUTES. `corpus.toml` is thirteen real repositories and the sweep over it runs neither tool's execution path, on purpose, so L1.19's runtime half and the whole of L1.20 were compared by nothing in nine languages. `exec-corpus.toml` names nine projects of about ten lines each that we wrote, so the objection does not apply:

```
uv run validate_exec.py              # every project
uv run validate_exec.py rust go      # only these languages
```

Each project is copied into a temp directory and given one commit, and it is planted TWICE, once per tool: a suite writes into the tree it ran in, so the second tool would otherwise audit the first one's leftovers. A language whose toolchain is not installed is skipped by name, and a run that compared nothing exits 2.

It found nine disagreements in its first afternoon, among them a language with no coverage runner at all, a whole-number float spelled two ways, and a project graded Slop for flaky tests whose suite had never run.

Two of the indicators ship a harness of their own, because a corpus sweep is a weak test of them. `validate_secrets.py --specimens` plants one credential per rule in a throwaway tree and diffs both readings of it: eleven of the thirteen corpus repositories commit no credentials at all, so a scanner missing fifteen of its seventeen rules would sweep clean. `validate_defs.py` and `validate_corpus_names.py` do the same job for dead code, one definition and one reference at a time.

## Build

```
cargo build --release     # native single binary
```

The Linux and Windows binaries are cross-built from a Debian x86_64 host with a rustup toolchain, which is what carries the extra targets:

```
rustup target add x86_64-unknown-linux-musl x86_64-pc-windows-gnu
CC_x86_64_unknown_linux_musl=musl-gcc \
  cargo build --release --target x86_64-unknown-linux-musl   # static-pie, no libc dependency
cargo build --release --target x86_64-pc-windows-gnu         # PE32+ console binary
```

Debian needs two packages for the C the grammars carry: `musl-tools` supplies `musl-gcc`, and `mingw-w64` supplies the Windows cross-compiler. Homebrew's `rustc` ships only its own host target and cannot add these, so a macOS-only setup gets the native binary and nothing else.

Cross-platform equality is checked the same way indicator equality is: run the same repos through the macOS arm64 binary and the Linux x86_64 binary and diff the `--tsv` output. It is byte-identical today.

Run: `./target/release/slop-audit-rs <repo> [--lang KEY] [--tsv]`.

`--lang` takes a `LANG_CFG` key; omitted, the primary language is detected from file counts exactly as `detect_primary_language` does. `--tsv` prints one tab-separated row per indicator, which is what `validate.py` diffs.

Adding an indicator: write `src/indicators/<name>.rs` exposing `pub fn analyze(repo: &Path) -> Indicator` on the shared skeleton in `src/lib.rs`, register it in `src/indicators/mod.rs` and `src/main.rs`, and validate it equal to `l1_analyzer` on real repos before landing.

Adding a language: add a row to `LANGS` in `src/lang.rs` and an arm to `parser_for`. The tests there fail if a grammar does not load or a table entry has no matching row.

Two rules the port learned the hard way, both locked by tests in `src/lib.rs`:

- Never count lines of file text with Rust's `str::lines()`. It splits on `\n` alone, while the reference uses Python's `str.splitlines()`, which also splits on a lone `\r`, a form feed, NEL, and the two Unicode separators. Use `py_splitlines`.
- Never filter the file walk to regular files. The reference scans with `rglob`, which yields directories too, so a directory named `decimal.js` reaches the read and is disclosed as unreadable.

License: Apache-2.0.
