"""The Python coverage-gap prove loop. Only the pure pieces are tested here: branch location,
gap selection, import-path derivation, proof rendering, and the assertion-vs-setup-error
classification. Real source in, verdict out. No fixture, no stub, no monkeypatch.

The repair loop (_prove_one) is proved by nothing. Its old tests replaced propose, repair and
_run with canned answers, so they proved wiring against the test's own strings."""

from l1_analyzer import python_coverage_prove as pcp
from l1_analyzer import python_facets

_SRC = '''\
def classify(n):
    if n < 0:
        x = "neg"
    elif n == 0:
        x = "zero"
    else:
        x = "pos"
    for _i in range(n):
        x += "!"
    while n > 0:
        n -= 1
    return x


class C:
    def method(self, y):
        if y:
            return y


def test_helper():
    return 1
'''


# --- facet location -----------------------------------------------------------

def test_module_functions_enumerates_branches_and_skips_tests():
    fns = python_facets.module_functions(_SRC)
    names = [f["name"] for f in fns]
    assert "classify" in names and "method" in names and "test_helper" not in names
    classify = next(f for f in fns if f["name"] == "classify")
    kinds = {b["kind"] for b in classify["branches"]}
    assert kinds == {"if", "elif", "else", "for", "while"}
    assert classify["is_method"] is False
    method = next(f for f in fns if f["name"] == "method")
    assert method["is_method"] is True                      # first param is self


def test_uncovered_gaps_selects_only_branches_on_uncovered_lines():
    fns = python_facets.module_functions(_SRC)
    classify = next(f for f in fns if f["name"] == "classify")
    else_line = next(b["body_line"] for b in classify["branches"] if b["kind"] == "else")
    gaps = python_facets.uncovered_gaps(fns, frozenset({else_line}))
    assert gaps and all(g["function"] in ("classify",) for g in gaps)
    assert [g["kind"] for g in gaps] == ["else"]
    assert python_facets.uncovered_gaps(fns, frozenset()) == []


# --- import-path derivation ---------------------------------------------------

def test_import_path_walks_the_package_up_to_the_root(tmp_path):
    pkg = tmp_path / "src" / "mypkg" / "sub"
    pkg.mkdir(parents=True)
    (tmp_path / "src" / "mypkg" / "__init__.py").write_text("")
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("")
    assert pcp._import_path(tmp_path, pkg / "mod.py") == "mypkg.sub.mod"


# --- rendering + classification -----------------------------------------------

def test_render_test_wraps_and_indents_the_body():
    src = pcp.render_test('from m import f\nresult = f(1)\nassert result == 2, "must be 2"')
    assert src.startswith("def proof_0():\n")
    assert "    result = f(1)" in src and '    assert result == 2, "must be 2"' in src


def test_classify_assertion_failure_is_a_divergence():
    out = "F\n=== short test summary info ===\nFAILED test_l1_coverage_proof.py::proof_0 - AssertionError: must be 2\n"
    assert pcp._classify(out, 1) == "divergence"


def test_classify_other_exception_is_incidental_not_a_bug():
    out = "E\nFAILED test_l1_coverage_proof.py::proof_0 - TypeError: missing 1 required positional argument\n"
    assert pcp._classify(out, 1) == "incidental"


def test_classify_pass_and_collection_error_and_timeout():
    assert pcp._classify("1 passed in 0.01s", 0) == "pass"
    assert pcp._classify("ERROR test_l1_coverage_proof.py - ImportError: no module\n", 2) == "incidental"
    assert pcp._classify("", 124) == "error"

