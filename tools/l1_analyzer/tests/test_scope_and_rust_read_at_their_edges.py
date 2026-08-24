"""Two more clause-4 sites, of the two kinds that are left.

`_test_dir_corroborated` walks a directory and asks one question of each file's first
4 KiB. The walk is a boundary; the question is not, and it could not be asked without a
directory to walk.

`_llvm_cov_report` runs cargo and reads what it wrote. There is nothing to lift: every line
in it obtains something or reports why it could not, which is what a boundary is. It is
declared rather than split, and the test says which of the two it is.
"""

import pathlib

from l1_analyzer import rust_trace, scope


def test_a_head_holding_a_framework_marker_corroborates_a_test_directory():
    assert scope.holds_a_test_marker(b"import pytest\n\ndef test_go():\n    pass\n")


def test_a_head_holding_no_marker_does_not():
    assert not scope.holds_a_test_marker(b"def go(x):\n    return x + 1\n")


def test_the_marker_question_touches_nothing():
    source = pathlib.Path(scope.__file__).read_text()
    body = source.split("def holds_a_test_marker")[1].split("\ndef ")[0]
    for reach in ("read_bytes", "read_text", "rglob", "is_file", "open("):
        assert reach not in body, reach


def test_the_coverage_run_is_declared_rather_than_split():
    """Every line of it obtains something or says why it could not."""
    source = pathlib.Path(rust_trace.__file__).read_text()
    assert "@boundary\ndef _llvm_cov_report(" in source


def test_no_clause_four_finding_survives_in_either():
    import ast

    from l1_analyzer import honest_code_python_rules as python_rules

    for module in (scope, rust_trace):
        source = pathlib.Path(module.__file__).read_text()
        found = python_rules.io_below_the_boundary({
            "path": pathlib.Path(module.__file__).name, "language": "python", "text": source,
            "tree": ast.parse(source), "readable": True, "unreadable_reason": ""}) or []
        assert [f["symbol"] for f in found if f["withheld_by"] == ""] == [], module.__name__
