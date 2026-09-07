"""A proof a reader cannot check is a claim, not a proof.

A retained proof is kept only because running it contradicted its assertion, and the card
carried the assertion and the verdict and not the failure. So a reader met a test, a sentence
saying what it asserts, and a claim that it failed, with nothing saying HOW.

Asked for on 2026-09-06 by the session auditing turso, after the first proof this loop ever
retained on a live run. Their words: the branch the proof targets looks like it ought to pass,
and either the proof found something or the gate retained something it should not have, and
the card cannot tell them which. Checking it meant re-running the test by hand against a
checkout another run was still using.

The failure is what makes a retained proof auditable by somebody who was not there, which is
the whole reason to publish one. Both loops record it, because a field on one and not the
other is how this record grew crooked before.
"""

from __future__ import annotations

from l1_analyzer import coverage_prove, python_coverage_prove

_GAP = {"function": "discounted_total", "line": 12, "kind": "if",
        "return_type": "f64", "parameters": [], "function_source": "fn f() {}"}
_FAILURE = ("thread 'proof_0' panicked at src/lib.rs:14:\n"
            "assertion failed: total < undiscounted\n")


def test_the_record_has_somewhere_to_put_the_failure():
    assert "failure" in coverage_prove.CoverageProof.__required_keys__


def test_a_rust_proof_carries_the_failure_it_produced():
    entry = coverage_prove._retained_entry("src/lib.rs", _GAP, "a discount must lower the total",
                                           "let x = 1;", _FAILURE)
    assert entry["failure"] == _FAILURE.strip()
    assert entry["explanation"] == "a discount must lower the total"


def test_both_loops_record_the_same_fields():
    """One record, two producers. A field on one and not the other is how the report came to
    show a location on some proofs and not others."""
    rust = coverage_prove._retained_entry("src/lib.rs", _GAP, "e", "let x = 1;", _FAILURE)
    python = python_coverage_prove._retained_entry("m.py", _GAP, "e", "assert x", _FAILURE)
    assert set(rust) == set(python) == set(coverage_prove.CoverageProof.__required_keys__)


def test_the_card_shows_the_failure_under_the_proof():
    """At the surface a reader opens. The test source says what was asserted and the failure
    says what happened, and one without the other is a claim."""
    from l1_analyzer import card

    band = {"value": 0, "band": "Healthy", "details": "d"}
    panel = {k: band for k in ("L1.18", "L1.17", "L1.15", "L1.10", "L1.11", "L1.9", "L1.16")}
    panel["coverage_proofs"] = {
        "retained": [coverage_prove._retained_entry("src/lib.rs", _GAP, "e", "let x = 1;",
                                                    _FAILURE)],
        "attempted": 1, "detail": "1/1 retained",
    }
    printed = card.card_markdown(
        card.build_card("x", "rust", panel, ran_tests=True, analyzer_version="test"))
    assert "assertion failed: total < undiscounted" in printed, printed[-1200:]
