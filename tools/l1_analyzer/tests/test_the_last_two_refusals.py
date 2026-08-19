"""The two refusals slop-audit-0it named that nothing asserted.

The bead lists eleven n/a refusals across seven harnesses that must never become a 0.0.
Nine were already covered. These are the other two, and both are the same failure if they
break: a run that could not be measured reporting a real-looking zero percent, which bands
Slop and reads as a codebase with terrible coverage rather than as a run nobody could read.

`branches-valid="0"` is the case that looks most like a measurement. The collector ran, the
report exists, and it says nothing had a branch. Usually the code under test sits in the
test assembly, which coverlet excludes by default, so the honest answer names the remedy.

pytest's invalid exit codes are the other. 2 through 5 each mean the suite never completed
a valid run, and each has its own sentence, because "collected no tests" and "internal
error" send a reader to different places.
"""

import pytest
from l1_analyzer import csharp_trace, pytest_trace


def test_zero_instrumented_branches_is_a_refusal_not_a_zero():
    result = csharp_trace._coverage_verdict((0, 0), 0, "dotnet 9.0.100")
    assert result["band"] == "n/a"
    assert result["value"] == "n/a"
    assert "test assembly" in result["details"]


def test_one_instrumented_branch_still_measures():
    """The boundary beside it: valid=1 is a denominator, so it is measured and banded."""
    result = csharp_trace._coverage_verdict((0, 1), 0, "dotnet 9.0.100")
    assert result["value"] == 0.0
    assert result["band"] == "Slop"


@pytest.mark.parametrize(("code", "phrase"), [
    (2, "interrupted"),
    (3, "internal error"),
    (4, "usage or collection error"),
    (5, "collected no tests"),
])
def test_each_invalid_pytest_exit_refuses_with_its_own_reason(code, phrase):
    result = pytest_trace._coverage_verdict(code, {"num_branches": 40, "covered_branches": 38}, "cpython 3.13")
    assert result["band"] == "n/a"
    assert result["value"] == "n/a"
    assert phrase in result["details"], result["details"]
    assert "did not complete a valid run" in result["details"]


def test_a_timeout_refuses_without_the_valid_run_wrapper():
    """124 is a timeout, and it says so on its own: the suite did not run long enough to be
    called an invalid run, it was cut off."""
    result = pytest_trace._coverage_verdict(124, {"num_branches": 40, "covered_branches": 38}, "cpython 3.13")
    assert result["band"] == "n/a"
    assert "timed out" in result["details"]
    assert "did not complete a valid run" not in result["details"]


def test_an_exit_code_no_row_names_reports_the_code_itself():
    """A named miss rather than a default: it cannot be mistaken for a row somebody wrote."""
    result = pytest_trace._coverage_verdict(99, {"num_branches": 40, "covered_branches": 38}, "cpython 3.13")
    assert result["band"] == "n/a"
    assert "pytest exit 99" in result["details"]
