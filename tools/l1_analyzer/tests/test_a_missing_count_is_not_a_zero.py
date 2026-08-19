"""A coverage field the report never carried is not a coverage of zero.

Both branch-coverage readers refused a missing DENOMINATOR and defaulted the missing
NUMERATOR. pytest_trace raised incomplete.refuse when num_branches was absent, then read
covered_branches with a fall-through of 0; java_trace read JaCoCo's covered and missed
attributes with a fall-through of 0 each.

The asymmetry is the defect. A report that carries a branch total but no covered count is
malformed, and grading it 0% publishes Slop for a repository whose coverage was never
measured. That is the same shape as the zero denominator the other half already refuses,
and it is worse, because a zero denominator is obviously nothing while 0% looks like a
measurement.

coverage.py writes both fields together whenever branch coverage is on, and a JaCoCo
counter element carries covered and missed as required attributes. Neither absence is a
shape a working tool produces, so neither has a sensible value to stand in for it.
"""

import pytest
from l1_analyzer import incomplete, java_trace, pytest_trace


def test_pytest_refuses_a_total_with_no_covered_count():
    with pytest.raises(incomplete.IncompleteCode):
        pytest_trace._coverage_verdict(0, {"num_branches": 40}, "cpython 3.13")


def test_pytest_still_measures_when_both_are_there():
    result = pytest_trace._coverage_verdict(0, {"num_branches": 40, "covered_branches": 38}, "cpython 3.13")
    assert result["value"] == 95.0
    assert result["band"] == "Healthy"


def test_jacoco_refuses_a_branch_counter_missing_its_counts():
    with pytest.raises(incomplete.IncompleteCode):
        java_trace._branch_totals('<report><counter type="BRANCH" covered="12"/></report>')


def test_jacoco_reads_a_well_formed_counter():
    assert java_trace._branch_totals(
        '<report><counter type="BRANCH" covered="12" missed="8"/></report>') == (12, 8)


def test_jacoco_still_reports_no_branch_counter_as_a_pair_of_zeroes():
    """A report with no BRANCH counter at all is a project with no branches to cover,
    which is a different fact from a counter that lost its numbers."""
    assert java_trace._branch_totals('<report><counter type="LINE" covered="1" missed="0"/></report>') == (0, 0)
