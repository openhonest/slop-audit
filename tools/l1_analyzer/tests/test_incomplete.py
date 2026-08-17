"""The refusal mechanism itself, asserted directly.

Every other test that reaches this module does so through a measure that raises, so the two
functions here were only ever exercised sideways. A helper nothing tests directly is how a
message format drifts, and the format is the point: `INCOMPLETE CODE: ` is what a reader
greps for in a CI transcript.
"""

import pytest
from l1_analyzer import incomplete
from l1_analyzer.incomplete import IncompleteCode


def test_refuse_returns_the_exception_rather_than_raising_it():
    """The call site reads `raise incomplete.refuse(...)`, so the raise stays visible where it
    happens. A helper that raised on the caller's behalf would hide control flow inside a
    function call, which is the thing this module exists to stop."""
    built = incomplete.refuse("L1.16 trailing whitespace", "no lines were read")
    assert isinstance(built, IncompleteCode)


def test_the_message_opens_with_the_greppable_marker_and_carries_both_halves():
    message = str(incomplete.refuse("L1.17 god-file concentration", "no production file was read"))
    assert message.startswith("INCOMPLETE CODE: ")
    assert "L1.17 god-file concentration" in message
    assert "no production file was read" in message


def test_ratio_is_a_percentage_not_a_fraction():
    # The four sites this replaced all multiplied by 100 themselves; returning a fraction here
    # would silently divide every published rate by a hundred.
    assert incomplete.ratio(1, 4, "m", "b") == 25.0
    assert incomplete.ratio(0, 4, "m", "b") == 0.0


def test_ratio_refuses_a_zero_denominator_rather_than_returning_zero():
    """Zero over zero is not zero percent, it is the absence of a measurement. This is the
    line that makes `if total > 0 else 0.0` unwriteable: there is no expression left that
    yields a number when nothing was counted."""
    with pytest.raises(IncompleteCode, match="L1.18 unbounded mutable state"):
        incomplete.ratio(0, 0, "L1.18 unbounded mutable state", "no function was enumerated")


def test_ratio_names_the_basis_so_the_boundary_can_print_it():
    with pytest.raises(IncompleteCode, match="no function was enumerated"):
        incomplete.ratio(3, 0, "L1.18 unbounded mutable state", "no function was enumerated")


# --- the boundary must cover every measure, not seven of nine -------------------
#
# L1.19 and L1.20 were the only measures in compute_source_indicators that did not pass
# through `_measure`, so a raise from a runtime harness would have aborted the audit instead
# of becoming an n/a. Three separate agents extracting the seven harnesses hit that wall and
# each returned `_na` rather than crash the analyzer. These pin the routing, end to end, on a
# real repository: no fake, no stub, and no patched module.

def _repo_with_no_branches(tmp_path):
    """A real package whose suite runs and whose code contains no decision at all.

    This is what makes the test honest. coverage.py really runs, really reports, and really
    finds num_branches == 0, so the refusal is reached the way a user would reach it rather
    than by handing the module a value it would never see.
    """
    (tmp_path / "m.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_path / "test_m.py").write_text("from m import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    return tmp_path


def test_a_verdict_with_no_branches_to_measure_raises_rather_than_returning_na():
    from l1_analyzer import pytest_trace
    with pytest.raises(IncompleteCode, match="L1.19 decision-space coverage"):
        pytest_trace._coverage_verdict(0, {"num_branches": 0, "covered_branches": 0}, "p")


def test_a_harness_refusal_reaches_the_report_as_an_n_a_and_not_as_a_traceback(tmp_path):
    """The routing, proved on a real run. Before this, `_runtime_coverage` called the harness
    directly and the raise would have escaped `compute_source_indicators` entirely."""
    from l1_analyzer import indicators
    repo = _repo_with_no_branches(tmp_path)
    result = indicators._decision_space_l19(repo, "python", True, 120)
    assert "INCOMPLETE CODE" in result["details"]
    assert "no enumerable decision branches" in result["details"]


def test_the_determinism_dispatch_is_routed_through_the_same_boundary(tmp_path):
    """`_runtime_determinism` is the second of the two, and it is routed by the same call.
    An unsupported language is the reachable half of its contract and must stay an n/a."""
    from l1_analyzer import indicators
    result = indicators._runtime_determinism(tmp_path, "klingon", 5, None)
    assert result["band"] == "n/a" and "not implemented" in result["details"]
