"""The adoptable-proofs surface on the card: one section fed by two producers
(the concurrency prove loop and the coverage-gap prove loop), each proof carrying
the runnable test to adopt. Retained-only, per Umbra's discipline. Pure assertions."""

from l1_analyzer import card

_BASE = {
    "L1.18": {"value": 5.0, "band": "Healthy"},
    # Complete, because the analyzer's L1.18b always carries these. A fixture missing the
    # bucketed section or the silence summary is testing a shape state_bounds cannot emit,
    # and the card raised on it the moment those reads stopped defaulting.
    "L1.18b": {"counts": {"neutral": 4, "promiscuous": 0, "unresolved": 0}, "resolvable_fraction": 1.0,
               "findings": [], "bucketed": {"counts": {}, "paths": []}, "silence": None},
}


def _concurrency(verdict, test):
    """One concurrency outcome. `test` is required: the card must carry the source each
    proof was produced with, so every call site names its own rather than sharing one."""
    return {"proofs": {"outcomes": [
        {"file": "wal.rs", "line": 699, "symbol": "Coord", "verdict": verdict,
         "detail": "fired a race", "generated_test": test},
    ]}}


def test_demonstrated_concurrency_proof_is_exposed_with_its_test_source():
    c = card.build_card("o/r", "rust", {
        **_BASE, **_concurrency("demonstrated", "fn t() { assert!(raced); }")}, ran_tests=False, analyzer_version="test")
    assert len(c["proofs"]) == 1
    p = c["proofs"][0]
    assert p["layer"] == "concurrency" and p["target"] == "Coord" and p["location"] == "wal.rs:699"
    assert "assert!(raced)" in p["test_source"]


def test_non_demonstrated_concurrency_proof_is_not_exposed():
    # A clean run (no race fired) is not a proof and must never surface as an adoptable test.
    c = card.build_card("o/r", "rust", {
        **_BASE, **_concurrency("not-demonstrated", "fn t() { assert!(never_fired); }")}, ran_tests=False, analyzer_version="test")
    assert c["proofs"] == []


def test_demonstrated_but_missing_test_source_is_not_exposed():
    c = card.build_card("o/r", "rust", {**_BASE, **_concurrency("demonstrated", test="")}, ran_tests=False, analyzer_version="test")
    assert c["proofs"] == []


def test_coverage_proof_is_exposed_with_language_and_source():
    results = {**_BASE, "coverage_proofs": {"retained": [
        {"function": "classify", "language": "rust", "location": "util.rs:42",
         "explanation": "the zero branch is never exercised",
         "test_source": "#[test]\nfn zero() { assert_eq!(classify(0), \"zero\"); }"},
    ]}}
    c = card.build_card("o/r", "rust", results, ran_tests=False, analyzer_version="test")
    assert [p["layer"] for p in c["proofs"]] == ["coverage"]
    assert c["proofs"][0]["language"] == "rust"
    assert "classify(0)" in c["proofs"][0]["test_source"]


def test_both_producers_feed_one_surface_and_render():
    results = {**_BASE, **_concurrency("demonstrated", "fn t() { assert!(both_layers); }"),
               "coverage_proofs": {"retained": [
                   {"function": "f", "language": "rust", "location": "a.rs:1",
                    "explanation": "gap", "test_source": "#[test] fn t() {}"}]}}
    c = card.build_card("o/r", "rust", results, ran_tests=False, analyzer_version="test")
    assert {p["layer"] for p in c["proofs"]} == {"concurrency", "coverage"}
    md = card.card_markdown(c)
    assert "## Adoptable proofs" in md and "never writes into your test file" in md
    html = card.card_html(c)
    assert 'class="proofs"' in html and "proof--concurrency" in html and "proof--coverage" in html


def test_no_proofs_means_no_section():
    c = card.build_card("o/r", "rust", _BASE, ran_tests=False, analyzer_version="test")
    assert c["proofs"] == []
    assert "Adoptable proofs" not in card.card_markdown(c)
