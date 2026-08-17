"""The native coverage-gap prove loop. Only the pure pieces are tested here: facet location,
uncovered-branch selection, proof rendering, and run classification. Real source in, verdict
out. No fixture, no stub, no monkeypatch.

The orchestration (_prove_one, _prove_module, prove_coverage_repo, prove_coverage) is proved
by nothing. Its old tests replaced propose, repair and the run boundary with canned answers,
so they proved wiring against the test's own strings. See the deletion audit."""

import pytest
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


# --- reading the #[cfg(...)] gate on a branch ------------------------------
#
# _enclosing_cfg attaches a predicate to every branch so a branch the host cannot compile
# is spotted before a proof is spent trying to reach it. _cfg_inner is the text reader
# underneath it, and the balancing is what makes a nested predicate come back whole.

@pytest.mark.parametrize("attr,inner", [
    ("#[cfg(test)]", "test"),
    ('#[cfg(not(target_os = "linux"))]', 'not(target_os = "linux")'),
    ('#[cfg(all(unix, feature = "x"))]', 'all(unix, feature = "x")'),
    ('#[cfg(any(a, all(b, c)))]', 'any(a, all(b, c))'),
])
def test_cfg_inner_returns_the_whole_predicate(attr, inner):
    # Balanced to the matching close paren, not to the first one: stopping early would cut
    # `not(target_os = "linux")` down to `not(target_os = "linux"` and the predicate would
    # never parse.
    assert rust_facets._cfg_inner(attr) == inner


@pytest.mark.parametrize("attr", [
    "#[derive(Debug, Clone)]",
    "#[inline]",
    "",
    '#[cfg_attr(test, derive(Debug))]',
])
def test_a_non_cfg_attribute_yields_no_predicate(attr):
    # None, not the empty string: _enclosing_cfg tests `is not None` to decide whether the
    # attribute gates anything, so an attribute that gates nothing has to answer None.
    # cfg_attr is on this list because it applies an attribute conditionally rather than
    # gating compilation of the item, and because the `_` after `cfg` is what keeps it off
    # the substring match.
    assert rust_facets._cfg_inner(attr) is None


def test_an_unterminated_cfg_yields_no_predicate():
    # Truncated source, or a `cfg(` inside a string. The scan reaches the end without the
    # depth returning to zero and declines rather than returning the tail.
    assert rust_facets._cfg_inner("#[cfg(all(unix") is None


def test_an_empty_cfg_yields_an_empty_predicate_not_none():
    # Real behaviour, stated because it is a hole rather than a decision: `#[cfg()]` returns
    # "", which is not None, so _enclosing_cfg appends an empty conjunct and builds
    # `all(, ...)`. rustc rejects `#[cfg()]` outright, so nothing that compiles reaches it.
    assert rust_facets._cfg_inner("#[cfg()]") == ""


def test_the_first_cfg_in_the_text_is_the_one_read():
    # An attribute_item is one attribute, so the second `cfg(` here is a shape the reader
    # never meets in practice; the scan takes the leftmost either way.
    assert rust_facets._cfg_inner("#[cfg(a)] #[cfg(b)]") == "a"


def test_a_nested_cfg_inside_another_attribute_is_read_as_the_predicate():
    # Real behaviour, and it is over-eager: find() looks for `cfg(` anywhere in the
    # attribute text, so any attribute containing that substring reports a predicate it
    # does not gate on. The cost is bounded - a wrong predicate marks a branch host-dead
    # and skips a proof, it never invents a gap - but the reader is a substring search
    # where the caller means "this attribute IS a cfg".
    assert rust_facets._cfg_inner("#[some_macro(cfg(unix))]") == "unix"


def test_the_branch_carries_the_predicate_of_the_function_that_gates_it():
    # The end-to-end path: a cfg on the function reaches every branch inside it, which is
    # how a host-dead branch is recognised before a proof is spent on it.
    src = ('#[cfg(not(target_os = "linux"))]\n'
           'pub fn classify(n: i32) -> &\'static str {\n'
           '    if n < 0 { "neg" } else { "pos" }\n}\n')
    branches = rust_facets.module_functions(src)[0]["branches"]
    assert {b["cfg"] for b in branches} == {'not(target_os = "linux")'}


# --- rendering + run classification ---------------------------------------

def test_render_module_wraps_a_body_in_an_in_crate_proof_module():
    body = '        let result = classify(0);\n        assert!(result == "zero", "0 is zero");'
    src = coverage_prove.render_module(body)
    assert "#[cfg(test)]" in src and "use super::*;" in src
    assert "let result = classify(0);" in src
    assert 'assert!(result == "zero"' in src


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
