# slop-audit/tools/

Reference implementations of audit instruments. **Not canonical.** The Slop Audit methodology is stack-agnostic; tools here demonstrate how to mechanise an audit for a specific pattern or stack. An auditor working on a stack that doesn't match the patterns these tools assume is expected to write or adapt their own.

## Tools

| Tool | Maps to dimension | Audits |
|---|---|---|
| `ui-audit/` | 4.18 (UX from code) | One aspect: stacks using the playground / enhance-function component pattern. Compares declared playground controls against actual `enhance()` implementations to surface dead controls, hidden features, and wiring mismatches. |
| `l1_analyzer/` | All L1.1-L1.20 (git history + source + runtime) | The canonical Python implementation of the 20 Layer 1 indicators, the additive checks, and the prove loops. Git indicators (L1.1-8) are language-agnostic; source indicators (L1.12-L1.18) use tree-sitter across ten languages; the runtime indicators (L1.19 coverage, L1.20 determinism) execute the target's own suite under the target's own runtime, which the tool auto-detects (`.venv`, rustup, `go.mod`, `global.json`, nvm, rbenv/asdf/jenv), so the result depends only on the repo. Opt-in prove loops generate a runnable test for an uncovered branch (Rust and Python) or a concurrency hazard. See `l1_analyzer/README.md`. |
| `slop-audit-rs/` | Portable redistribution of the L1 panel | A compiled Rust build of the analyzer for USB/offline use: one static binary per platform with the tree-sitter grammars linked in, no interpreter and no shipped `.so`. Cross-compiles to macOS/Linux/Windows. Ported indicator-by-indicator and validated equal to the Python instrument (the Python stays canonical). See `slop-audit-rs/`. |

## What "one example implementation" means

A tool here is a *demonstration* that the dimension is mechanically auditable for some stack — not a *requirement* to use that tool. If your stack doesn't use the pattern the tool assumes, the dimension is still auditable; you just need a different implementation. The dimension documentation in `../dimensions/` describes what to audit; the tool documentation here describes one way to do it.

## Adding a tool

A new tool belongs here when:

1. It targets a specific Slop Audit dimension (or a specific aspect of one).
2. It's a *reference* implementation, not the only-acceptable one — i.e., the methodology dimension document remains stack-agnostic and the tool is one possible mechanisation.
3. It's distributable under the same license as Slop Audit (Apache-2.0).

## License

Apache-2.0 — same as the rest of slop-audit.
