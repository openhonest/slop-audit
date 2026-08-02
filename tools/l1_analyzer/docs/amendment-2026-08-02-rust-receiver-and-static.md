# Amendment 2026-08-02: Rust receiver and `static mut` detection

## What was wrong

L1.18 detected no mutable state in Rust at all. Two independent defects, both returning 0/N where the answer is non-zero:

1. **Receiver mutation missed.** A Rust method is a `function_item` carrying a `self_parameter`, and `self.field` is a `field_expression` whose text is `self.<field>`. The Rust config set `this_ident = set()`, so `_receiver_names` returned an empty set and `_count_mutable_refs` never counted the member access. An `impl` method doing `self.count += 1` scored 0.

2. **`static mut` global missed.** `_find_module_mutable_names` fell to the legacy text heuristic, which takes the token before `=`. For `static mut counter: i32 = 0` that token is the type `i32`, not `counter`, so the real name was never registered and a body reading `counter` was never counted.

The existing `test_l1_18_rust_config_runs` did not catch either: it asserted only that the band was one of three strings and that the details ended in `(rust)`, never the ratio. The behavioural (Gherkin) suite did not catch it either, because its step definitions fabricated results instead of calling the analyzer. Rewiring the behavioural suite to the real analyzer is what surfaced this.

## The fix

- Rust `this_ident = {"self"}`. A free function has no `self.` access, so this counts `impl`-method receiver access exactly as Python's `self.` detection does, and never over-counts free functions.
- New structural extractor `_module_mutables_by_specifier`: a top-level binding is mutable state iff its declaration carries a `mut` specifier (`static mut NAME`), and the name is read from the declaration's `identifier` child. `const` and plain `static` are immutable and excluded. Rust dispatches to it via `mutable_specifier_globals: True`.
- The Rust-only `raw_mut_patterns` are retained (see amendment 2026-07-31) but no longer load-bearing: structural detection carries it, and those patterns never appear inside a function body.

## Regression cover

`tests/test_basic.py`:

- `test_l1_18_rust_static_mut_global_is_detected` (1/2, `bump` flagged)
- `test_l1_18_rust_receiver_mutation_is_detected` (1/2, `increment` flagged)
- `test_l1_18_rust_const_is_not_mutable_state` (0/1)

## Note for Paper A

If the registered corpus includes Rust repositories, their L1.18 numbers change under this fix (from an under-count toward the true value). This is a correction of a defect, not a definitional change, and belongs in the v1-vs-v2 side-by-side re-run per the finite-testability supersession rule, not a silent edit. Capture it there.
