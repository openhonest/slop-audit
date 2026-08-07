"""The native coverage-gap prove loop. The live loop needs a model + cargo + cargo-llvm-cov,
so here we test the deterministic pieces: facet location, uncovered-branch selection, test
rendering, run classification, and the graceful not-run paths. The end-to-end proof is
exercised against a real crate. Pure assertions, no mocks."""

from l1_analyzer import coverage_prove, rust_facets

_SRC = """\
pub fn classify(n: i32) -> &'static str {
    if n < 0 { "neg" } else if n == 0 { "zero" } else { "pos" }
}
#[cfg(test)]
mod tests {
    #[test] fn t() { assert_eq!(1, 1); }
}
"""


# --- native facet location -------------------------------------------------

def test_module_functions_extracts_signature_and_branches():
    fns = rust_facets.module_functions(_SRC)
    assert [f["name"] for f in fns] == ["classify"]        # the #[cfg(test)] fn is excluded
    f = fns[0]
    assert f["return_type"] == "&'static str"
    assert [p["type"] for p in f["parameters"]] == ["i32"]
    kinds = [b["kind"] for b in f["branches"]]
    assert "if" in kinds and "else" in kinds               # nested if/else enumerated


def test_uncovered_gaps_selects_only_branches_on_uncovered_lines():
    fns = rust_facets.module_functions(_SRC)
    # line 2 holds every branch body; mark it uncovered -> gaps, all for classify.
    gaps = rust_facets.uncovered_gaps(fns, frozenset({2}))
    assert gaps and all(g["function"] == "classify" for g in gaps)
    # nothing uncovered -> no gaps.
    assert rust_facets.uncovered_gaps(fns, frozenset()) == []


def test_uncovered_gaps_skips_functions_with_no_return_type():
    # No `-> T` (returns unit): the renderer's `let result = f(..)` has nothing to assert on,
    # so a function without a concrete return type is not proof-ready and is skipped.
    src = "pub fn f(n: i32) {\n    if n < 0 { println!(\"neg\") }\n}\n"
    fns = rust_facets.module_functions(src)
    assert fns[0]["return_type"] is None
    assert rust_facets.uncovered_gaps(fns, frozenset({2})) == []


# --- rendering + run classification ---------------------------------------

def test_render_test_builds_an_in_crate_proof_module():
    gap = {"function": "classify", "kind": "if", "line": 2, "function_source": "...",
           "parameters": [{"name": "n", "type": "i32"}], "return_type": "&'static str"}
    src = coverage_prove.render_test(gap, {"args": ["0"], "expected": 'result == "zero"', "explanation": "0 is zero"})
    assert "#[cfg(test)]" in src and "use super::*;" in src
    assert "let result = classify(0);" in src
    assert 'assert!(result == "zero"' in src


def test_run_classification_distinguishes_pass_fail_error():
    assert coverage_prove._classify_run("running 1 test\ntest result: ok. 1 passed; 0 failed", 0) == "pass"
    assert coverage_prove._classify_run("test result: FAILED. 0 passed; 1 failed", 101) == "fail"
    assert coverage_prove._classify_run("error[E0308]: mismatched types\ncould not compile", 101) == "error"


# --- graceful not-run ------------------------------------------------------

def test_prove_coverage_needs_a_model(monkeypatch, tmp_path):
    monkeypatch.setattr(coverage_prove, "model_available", lambda: False)
    monkeypatch.setattr(coverage_prove.rust_trace, "_cargo", lambda: "/usr/bin/cargo")
    result = coverage_prove.prove_coverage(tmp_path, "src/lib.rs")
    assert result["retained"] == [] and result["attempted"] == 0
    assert "OPENAI_API_KEY" in result["detail"]
