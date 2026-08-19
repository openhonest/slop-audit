"""The Rust prove loop's orchestration, tested by injection rather than by patching.

The Python half was done first and this is the same argument. The 2026-08-17 sweep
deleted every test of these paths because each patched module globals: the
compile-error-then-repair-then-retain path, `repair_rounds=0`, the round cap,
`_prove_module`'s batch path and its per-gap fallback when the batch will not compile.

Rust's loop has one shape Python's does not, and it is the one worth covering: the batch.
Every proposal is compiled together and run once, which is fast and fragile, because a
single test that will not compile poisons the whole module. The fallback is per-gap with
compiler-feedback repair, and nothing has tested that either path is taken when it should
be.

`propose`, `repair` and the two runners are parameters now, as in `prove.prove` and in
the Python loop. Required, never defaulted: a default puts a real cargo invocation one
forgotten argument away from a test.
"""

import pathlib

from l1_analyzer import coverage_prove as cp

_GAP = {"function": "f", "line": 3, "branch": "if x > 3", "return_type": "i32"}


def _proposal(body="assert!(false);"):
    return {"body": body, "explanation": "why"}


def test_a_proposal_nobody_returns_is_skipped():
    bucket, proposal, source = cp._prove_one(
        pathlib.Path("."), "src/m.rs", _GAP, 3, 1.0,
        propose_fn=lambda gap: None,
        repair_fn=lambda *a: None,
        run_fn=lambda *a: ("pass", ""),
        refine_fn=lambda *a: "divergence")
    assert (bucket, proposal, source) == ("skipped", None, "")


def test_a_compile_error_is_repaired_and_then_gated():
    """The path the bead names first. The first run does not compile, the repair fixes it,
    and the SECOND run is what gets gated."""
    runs = iter([("error", "error[E0308]: mismatched types"),
                 ("fail", "assertion `left == right` failed")])
    bucket, _got, _src = cp._prove_one(
        pathlib.Path("."), "src/m.rs", _GAP, 3, 1.0,
        propose_fn=lambda gap: _proposal(),
        repair_fn=lambda *a: _proposal("assert_eq!(1, 2);"),
        run_fn=lambda *a: next(runs),
        # Injected because every fail output routes through the refinement, which re-runs
        # the crate. Its own logic is tested elsewhere; what this asserts is that the loop
        # repaired, ran again, and gated the SECOND result.
        refine_fn=lambda *a: "divergence")
    assert bucket == "divergence", bucket


def test_repair_rounds_zero_never_repairs():
    calls = []
    bucket, _got, _src = cp._prove_one(
        pathlib.Path("."), "src/m.rs", _GAP, 0, 1.0,
        propose_fn=lambda gap: _proposal(),
        repair_fn=lambda *a: calls.append(1) or _proposal(),
        run_fn=lambda *a: ("error", "error[E0308]"),
        refine_fn=lambda *a: "divergence")
    assert bucket == "error"
    assert calls == [], "a cap of zero must not call repair at all"


def test_the_repair_round_cap_is_honoured():
    calls = []
    bucket, _got, _src = cp._prove_one(
        pathlib.Path("."), "src/m.rs", _GAP, 2, 1.0,
        propose_fn=lambda gap: _proposal(),
        repair_fn=lambda *a: calls.append(1) or _proposal(),
        run_fn=lambda *a: ("error", "error[E0308]"),
        refine_fn=lambda *a: "divergence")
    assert bucket == "error"
    assert len(calls) == 2, f"repaired {len(calls)} times against a cap of 2"


def test_a_batch_that_compiles_gates_each_test_without_falling_back():
    """The fast path. One compile, one run, and every gap read out of the batch."""
    fell_back = []
    retained, outcomes = cp._prove_module(
        pathlib.Path("."), "src/m.rs", [_GAP, dict(_GAP, line=9)], 3, 1.0,
        propose_fn=lambda gap: _proposal(),
        repair_fn=lambda *a: None,
        batch_run_fn=lambda *a: (0, "test proof_0 ... ok\ntest proof_1 ... ok"),
        run_fn=lambda *a: fell_back.append(1) or ("pass", ""),
        refine_fn=lambda *a: "divergence")
    assert fell_back == [], "the batch compiled; nothing should have run per gap"
    assert outcomes["pass"] == 2
    assert retained == []


def test_a_batch_that_will_not_compile_falls_back_to_one_gap_at_a_time():
    """The slow path, and the reason it exists: one bad test poisons the whole module."""
    per_gap = []
    retained, outcomes = cp._prove_module(
        pathlib.Path("."), "src/m.rs", [_GAP, dict(_GAP, line=9)], 0, 1.0,
        propose_fn=lambda gap: _proposal(),
        repair_fn=lambda *a: None,
        batch_run_fn=lambda *a: (101, "error[E0433]: failed to resolve"),
        run_fn=lambda *a: per_gap.append(1) or ("pass", ""),
        refine_fn=lambda *a: "divergence")
    assert len(per_gap) == 2, "each gap should have been run on its own"
    assert outcomes["pass"] == 2
    assert retained == []
