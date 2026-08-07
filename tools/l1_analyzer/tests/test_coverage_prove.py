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

def test_render_module_wraps_a_body_in_an_in_crate_proof_module():
    body = '        let result = classify(0);\n        assert!(result == "zero", "0 is zero");'
    src = coverage_prove.render_module(body)
    assert "#[cfg(test)]" in src and "use super::*;" in src
    assert "let result = classify(0);" in src
    assert 'assert!(result == "zero"' in src


_GAP = {"function": "f", "kind": "if", "line": 2, "function_source": "fn f(){}",
        "parameters": [{"name": "n", "type": "i32"}], "return_type": "i32"}


def test_repair_loop_recovers_a_compile_error_then_retains_a_failure(monkeypatch, tmp_path):
    # First attempt does not compile; repair fixes it; the fixed test then fails -> retained.
    monkeypatch.setattr(coverage_prove, "propose", lambda gap: {"body": "bad", "explanation": "e0"})
    monkeypatch.setattr(coverage_prove, "repair", lambda gap, src, err: {"body": "good", "explanation": "e1"})
    runs = iter([("error", "error[E0308]"), ("fail", "test result: FAILED")])
    monkeypatch.setattr(coverage_prove, "_run_in_crate", lambda *a: next(runs))
    status, proposal, _src = coverage_prove._prove_one(tmp_path, "m.rs", _GAP, repair_rounds=3, timeout_seconds=1)
    assert status == "fail" and proposal["explanation"] == "e1"


def test_repair_rounds_zero_takes_only_the_first_attempt(monkeypatch, tmp_path):
    monkeypatch.setattr(coverage_prove, "propose", lambda gap: {"body": "bad", "explanation": "e"})
    called = []
    monkeypatch.setattr(coverage_prove, "repair", lambda *a: called.append(1) or {"body": "x", "explanation": "y"})
    monkeypatch.setattr(coverage_prove, "_run_in_crate", lambda *a: ("error", "error[E0308]"))
    status, _p, _s = coverage_prove._prove_one(tmp_path, "m.rs", _GAP, repair_rounds=0, timeout_seconds=1)
    assert status == "error" and called == []          # repair never called when rounds=0


def test_repair_stops_after_the_round_cap(monkeypatch, tmp_path):
    monkeypatch.setattr(coverage_prove, "propose", lambda gap: {"body": "bad", "explanation": "e"})
    rounds = []
    monkeypatch.setattr(coverage_prove, "repair", lambda *a: rounds.append(1) or {"body": "still-bad", "explanation": "e"})
    monkeypatch.setattr(coverage_prove, "_run_in_crate", lambda *a: ("error", "error[E0308]"))
    status, _p, _s = coverage_prove._prove_one(tmp_path, "m.rs", _GAP, repair_rounds=2, timeout_seconds=1)
    assert status == "error" and len(rounds) == 2      # exactly the cap, no more


def test_run_classification_distinguishes_pass_fail_error():
    assert coverage_prove._classify_run("running 1 test\ntest result: ok. 1 passed; 0 failed", 0) == "pass"
    assert coverage_prove._classify_run("test result: FAILED. 0 passed; 1 failed", 101) == "fail"
    assert coverage_prove._classify_run("error[E0308]: mismatched types\ncould not compile", 101) == "error"


# --- batching + whole-repo sweep ------------------------------------------

def test_render_batch_puts_every_proof_in_one_module():
    src = coverage_prove.render_batch(["let result = a(); assert!(result);", "let result = b(); assert!(!result);"])
    assert src.count("#[test]") == 2 and "fn proof_0()" in src and "fn proof_1()" in src
    assert src.count(f"mod {coverage_prove._PROOF_MOD}") == 1   # ONE module = one compile


def test_classify_batch_reads_each_tests_verdict():
    out = "running 2 tests\ntest l1_coverage_proof::proof_0 ... ok\ntest l1_coverage_proof::proof_1 ... FAILED\n"
    assert coverage_prove._classify_batch(out) == {0: "pass", 1: "fail"}
    assert coverage_prove._classify_batch("error[E0308]\ncould not compile") == {}   # no test lines


def test_prove_module_batches_when_it_compiles(monkeypatch, tmp_path):
    monkeypatch.setattr(coverage_prove, "propose", lambda gap: {"body": "b", "explanation": gap["function"]})
    # one batch run: proof_0 fails (bug), proof_1 passes (correct)
    monkeypatch.setattr(coverage_prove, "_append_and_run",
                        lambda *a: (101, "test l1_coverage_proof::proof_0 ... FAILED\ntest l1_coverage_proof::proof_1 ... ok\n"))
    gaps = [{**_GAP, "function": "a"}, {**_GAP, "function": "b"}]
    retained, outcomes = coverage_prove._prove_module(tmp_path, "m.rs", gaps, repair_rounds=3, timeout_seconds=1)
    assert outcomes == {"fail": 1, "pass": 1, "error": 0}
    assert [r["function"] for r in retained] == ["a"]


def test_prove_module_falls_back_to_per_gap_when_batch_wont_compile(monkeypatch, tmp_path):
    monkeypatch.setattr(coverage_prove, "propose", lambda gap: {"body": "b", "explanation": "e"})
    monkeypatch.setattr(coverage_prove, "_append_and_run", lambda *a: (101, "error[E0308]\ncould not compile"))
    calls = []
    monkeypatch.setattr(coverage_prove, "_prove_one", lambda *a: calls.append(1) or ("pass", {"explanation": "e"}, "src"))
    _retained, outcomes = coverage_prove._prove_module(tmp_path, "m.rs", [_GAP, _GAP], repair_rounds=3, timeout_seconds=1)
    assert len(calls) == 2 and outcomes["pass"] == 2   # batch failed to compile -> per-gap fallback ran


def test_prove_coverage_repo_aggregates_across_modules(monkeypatch, tmp_path):
    for name in ("a.rs", "b.rs", "notes.txt"):
        (tmp_path / name).write_text("fn f() {}")
    monkeypatch.setattr(coverage_prove.rust_trace, "_cargo", lambda: "/usr/bin/cargo")
    monkeypatch.setattr(coverage_prove, "model_available", lambda: True)
    monkeypatch.setattr(coverage_prove.rust_trace, "repo_uncovered_lines",
                        lambda repo, t: {"measured": True, "files": {"a.rs": frozenset({2}), "b.rs": frozenset({2}), "notes.txt": frozenset({1})}, "reason": ""})
    monkeypatch.setattr(coverage_prove.rust_facets, "module_functions", lambda src: [{"name": "f"}])
    monkeypatch.setattr(coverage_prove.rust_facets, "uncovered_gaps", lambda fns, lines: [dict(_GAP)])
    monkeypatch.setattr(coverage_prove, "_prove_module",
                        lambda repo, rel, gaps, rr, to: ([{"location": rel}], {"fail": 1, "pass": 0, "error": 0}))
    res = coverage_prove.prove_coverage_repo(tmp_path, cap_per_module=5)
    assert res["modules"] == 2                          # a.rs + b.rs, not the non-.rs notes.txt
    assert res["outcomes"]["fail"] == 2 and len(res["retained"]) == 2


# --- graceful not-run ------------------------------------------------------

def test_prove_coverage_needs_a_model(monkeypatch, tmp_path):
    monkeypatch.setattr(coverage_prove, "model_available", lambda: False)
    monkeypatch.setattr(coverage_prove.rust_trace, "_cargo", lambda: "/usr/bin/cargo")
    result = coverage_prove.prove_coverage(tmp_path, "src/lib.rs")
    assert result["retained"] == [] and result["attempted"] == 0
    assert "OPENAI_API_KEY" in result["detail"]
