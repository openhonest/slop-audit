"""The coverage-gap prove orchestration (Umbra merged in). The live loop needs umbra +
a model + cargo-llvm-cov, so here we test the pure mapping and the graceful not-run
paths; the end-to-end proof is exercised against a real crate under the coverage-prove
extra. Pure assertions, no mocks."""

from l1_analyzer import coverage_prove


def test_mapped_turns_an_umbra_proof_into_the_adoptable_shape():
    umbra_proof = {
        "function": "classify",
        "language": "rust",
        "gap": {"location": "src/lib.rs:3", "kind": "unexercised_branch"},
        "proposal": {"plain_explanation": "the zero branch is never exercised"},
        "verification": {"status": "fail", "test_source": "#[test] fn t() { assert_eq!(classify(0), \"zero\"); }"},
    }
    m = coverage_prove._mapped(umbra_proof)
    assert m == {
        "function": "classify", "language": "rust", "location": "src/lib.rs:3",
        "explanation": "the zero branch is never exercised",
        "test_source": "#[test] fn t() { assert_eq!(classify(0), \"zero\"); }",
    }


def test_mapped_falls_back_to_gap_kind_when_no_explanation():
    m = coverage_prove._mapped({"function": "f", "gap": {"location": "a.rs:1", "kind": "unexercised_branch"},
                                "proposal": {}, "verification": {"test_source": "x"}})
    assert m["explanation"] == "unexercised_branch"


def test_prove_coverage_is_graceful_when_umbra_is_absent(monkeypatch, tmp_path):
    # No umbra installed -> an explicit not-run reason, never a crash or a guessed proof.
    monkeypatch.setattr(coverage_prove, "umbra_available", lambda: False)
    result = coverage_prove.prove_coverage(tmp_path / "m.rs", tmp_path / "t.rs")
    assert result["retained"] == [] and result["attempted"] == 0
    assert "coverage-prove extra" in result["detail"]
