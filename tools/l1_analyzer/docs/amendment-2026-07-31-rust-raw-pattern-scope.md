# Amendment 2026-07-31 — scope the Rust raw-mutable-pattern heuristic to Rust

## What changed

`_count_mutable_refs` (the L1.18 detector in this reference implementation) contained a raw-text heuristic that incremented the mutable-reference count for any AST node whose text contained `static mut`, `&mut self`, or `mut self`. It ran for **every** language. It is now gated to languages that declare `raw_mut_patterns` in `LANG_CFG`, which is Rust only.

## Why

The heuristic is meant to catch Rust mutable state (`static mut`, `&mut self`), which Rust expresses without the receiver-member-access pattern the other languages use. Because it matched raw text for all languages, it produced **false positives** on any non-Rust source that merely contained those strings. Concretely, when the analyzer audited its own Python source, `_count_mutable_refs` and its nested `walk` were flagged as reading external mutable state — solely because the function's body contains the pattern list `"static mut"`, `"&mut self"`, `"mut self"` as string literals. They use no mutable state.

This was surfaced by the L1.18b state-bounds classifier, which flagged those two functions as "undetermined" (it could locate no actual state to classify) — a true positive for the classifier, a false positive for L1.18.

## Blast radius

- Rust: unchanged. Rust still declares the patterns and is detected identically.
- Every other language: the raw-text check no longer runs. This changes an L1.18 count only for non-Rust source that contains the literal strings `static mut` / `&mut self` / `mut self` — in practice, essentially just this analyzer's own source and files discussing Rust. No real-world non-Rust codebase depends on these strings as a signal of its own mutable state.
- The frozen-equivalence golden (`tests/golden/py_repo.json`, a Python fixture with none of these strings) is unchanged; `test_state_bounds.py` passes without modification.

## Scope of this amendment

This touches only the **simplified reference implementation** in `tools/l1_analyzer`. The production L1.18 used for the pre-registered Paper A data collection lives in the Paper A replication package and is a separate artifact; it is not modified here. If that implementation carries the same all-language raw-text check, the same fix should be mirrored there and amended **before** any additional Paper A data collection, per the pre-registration freeze.
