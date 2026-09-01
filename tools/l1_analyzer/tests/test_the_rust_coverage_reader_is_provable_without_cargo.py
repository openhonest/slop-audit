"""Rust's region totals are read and banded by functions a test can call.

Every other harness lifts its reading out of the part that drives a toolchain. Rust was the
last one that did not: the region totals, the refusals and the band all sat inside the
function that runs cargo, so proving any of them needed a Rust toolchain and cargo-llvm-cov
on the machine. They were proved by a stand-in until the 2026-08-17 sweep removed those, and
by nothing since.

What these hold. The tool reports region coverage rather than branch coverage, because LLVM
branch coverage needs a nightly toolchain and region coverage runs on a stable one, so the
number a reader sees has to be the one the details line names. A report with no region
totals is a schema this reader does not know, and a tree with no regions at all is a suite
that ran nothing; neither is a coverage of zero, and publishing Slop for either would grade
a repository whose coverage was never measured.
"""

import pytest
from l1_analyzer import rust_trace

_FULL = {"data": [{"totals": {"regions": {"count": 40, "covered": 38}}}]}
_EMPTY_TREE = {"data": [{"totals": {"regions": {"count": 0, "covered": 0}}}]}
_NO_TOTALS = {"data": [{"files": []}]}


def test_the_region_totals_are_read_as_count_and_covered():
    assert rust_trace._region_totals(_FULL) == (40, 38)


def test_a_report_with_no_region_totals_is_refused_rather_than_read_as_zero():
    """The refusal that must never become 0.0. A report without totals is a schema this
    reader does not know, and grading it Slop publishes a verdict on a repository whose
    coverage was never measured."""
    assert rust_trace._region_totals(_NO_TOTALS) is None


@pytest.mark.parametrize("broken", [{}, {"data": []}, {"data": [{}]},
                                    {"data": [{"totals": {"regions": {"count": "x"}}}]}])
def test_a_report_that_is_not_a_report_is_refused(broken):
    assert rust_trace._region_totals(broken) is None


def test_a_tree_with_no_regions_is_told_apart_from_a_tree_with_none_covered():
    """Zero regions means the suite exercised nothing, and zero covered of forty means it
    ran and covered nothing. They are different facts and only one of them is a grade."""
    assert rust_trace._region_totals(_EMPTY_TREE) == (0, 0)


@pytest.mark.parametrize(("covered", "count", "band"), [
    (40, 40, "Healthy"), (37, 40, "Healthy"), (36, 40, "Not Healthy"),
    (24, 40, "Not Healthy"), (23, 40, "Slop"), (0, 40, "Slop"),
])
def test_the_bands_sit_where_the_specification_puts_them(covered, count, band):
    assert rust_trace._coverage_verdict((count, covered), 0, "rustc 1.80", 300.0)["band"] == band


def test_a_suite_that_exercised_no_region_is_refused_rather_than_graded():
    result = rust_trace._coverage_verdict((0, 0), 0, "rustc 1.80", 300.0)
    assert result["band"] == "n/a"
    assert result["value"] == "n/a"


def test_a_timed_out_run_is_refused_rather_than_graded():
    result = rust_trace._coverage_verdict(None, 124, "rustc 1.80", 300.0)
    assert result["band"] == "n/a"


def test_the_details_name_regions_rather_than_branches():
    """The number is region coverage, and a reader comparing it against another language's
    branch coverage has to be told which they are looking at."""
    assert "region" in rust_trace._coverage_verdict((40, 38), 0, "rustc 1.80", 300.0)["details"]


def test_the_details_name_the_toolchain_that_measured_it():
    assert "rustc 1.80" in rust_trace._coverage_verdict((40, 38), 0, "rustc 1.80", 300.0)["details"]


def test_a_failing_suite_is_graded_and_the_detail_says_the_suite_failed():
    """Coverage from a run whose tests failed is still coverage, and a reader has to know."""
    result = rust_trace._coverage_verdict((40, 38), 1, "rustc 1.80", 300.0)
    assert result["band"] == "Healthy"
    assert "exit 1" in result["details"]
