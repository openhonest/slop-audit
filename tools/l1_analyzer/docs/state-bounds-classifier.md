# L1.18b — state-bounds classifier (provenance note)

Added 2026-07-31. This records what the classifier is and, more importantly, what it is not, for anyone reading the replication package.

## What it does

L1.18 counts functions that read external mutable state. It cannot tell whether that state is *bounded* (a `bool`, an enum → a finite behavior domain, exhaustively testable) or *unbounded* (a growing `dict`/`list`, a `str`, an arbitrary-precision `int` → an infinite behavior domain, per `../../../research/amendments/paper-c-amendment-l118-rationale.md`, where the `State(S)` term is unbounded). L1.18b makes that call and reports, of the functions L1.18 flags, how many read unbounded state, how many read only bounded state, and how many are undetermined.

## Guarantees, and why the pre-registration is untouched

- **L1.18 is unchanged.** L1.18b never reads or writes L1.18's `value`/`band`. It is emitted under a separate key.
- **Gated, off for registered runs.** `compute_source_indicators(..., classify_state_bounds=)` defaults to `True` for the CLI and the hosted tool. The pre-registered experiments (Papers A–D) pass `False`. With the flag off, the emitted output is byte-for-byte the frozen L1.18 set — proven by `tests/test_state_bounds.py::test_frozen_mode_matches_registered_golden_byte_for_byte`, which holds the current off-mode output against a golden captured before the classifier existed. This is therefore **not** an amendment to L1.18; L1.18's registered definition and numbers are identical whether the classifier runs or not.
- **Denominator reconciles.** L1.18b classifies exactly the function set L1.18 flags (same `_count_mutable_refs > 0` predicate), so `unbounded + bounded + undetermined == L1.18 mutable_funcs`.
- **Provenance stamped.** The CLI JSON envelope records `"state_bounds": "on"|"off"`.

## Honest limits (this is a heuristic, not a decision procedure)

- **Sound, one-directional, conservative.** It reports UNBOUNDED only when it can point at an unbounded type or literal, BOUNDED only when every signal is bounded, and otherwise UNDETERMINED. A perfect classifier is impossible (Rice's theorem); "undetermined" is a first-class, labeled outcome, not a failure.
- **Python only, v1.** Other languages return `n/a`. Within Python it resolves types from annotations and assignment RHSs, and applies three observed-projection downgrades (`len(x)`, `k in x`, `if x:`). State reached through non-`self` receivers (e.g. `request.app.state.x`) or framework objects is currently UNDETERMINED rather than guessed.
- Not empirically validated. Accuracy is a candidate for the Paper E verification cycle; until then treat the breakdown as an informative refinement, not a measured indicator with calibrated bands.
