"""Region coverage over a crate with no tests is arithmetic on an empty question.

The Rust row refuses when cargo-llvm-cov reports zero regions, on the reasoning that no
regions means no measurement. Regions come from compiled code rather than from tests, so a
crate that compiles and has no tests has regions and no measurement, and the row bands it:

    rust banded a project with no tests Slop at 0.0:
    0/3 llvm-cov regions exercised by tests, region coverage (suite passed)

"Suite passed" is even true. `cargo test` passes when there is nothing to run.

Reported on 2026-09-06 by the session auditing turso. Their L1.19 figure of 66.9 stands,
because turso has tests; what does not stand is a Slop band and a number handed to a
repository this instrument never measured. That is the reading it exists to refuse, and the
count it was asking about could never have answered it.

The question is whether a test ran, and cargo says so in its own words. `_tests_run` already
reads those words for L1.20, so the row asks it rather than inferring from a region count.
"""

from __future__ import annotations

from l1_analyzer import rust_trace

_TOOLCHAIN = "1.88.0"
# What cargo prints for a crate whose suite has nothing in it, and for one that ran two.
_NO_TESTS = "running 0 tests\n\ntest result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out\n"
_TWO_TESTS = "running 2 tests\n\ntest result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out\n"


def test_a_crate_whose_suite_ran_nothing_is_not_banded():
    """The reported case. Three regions exist because three regions compiled."""
    result = rust_trace._coverage_verdict((3, 0), 0, _TOOLCHAIN, 600.0, _NO_TESTS, 1)
    assert result["band"] == "n/a", result
    assert "no test" in result["details"].lower(), result["details"]


def test_a_crate_whose_suite_ran_is_measured_as_before():
    """The other direction, and the one that must not move. turso has tests and its 66.9
    stands."""
    result = rust_trace._coverage_verdict((100, 66), 0, _TOOLCHAIN, 600.0, _TWO_TESTS, 1)
    assert result["value"] == 66.0
    assert result["band"] != "n/a"


def test_a_run_that_said_nothing_about_tests_is_still_refused():
    """Cargo prints no result line when the build failed before any test could run. Reading
    that as zero tests is the right answer for the wrong reason and lands in the same place:
    nothing ran, so there is nothing to report."""
    result = rust_trace._coverage_verdict((3, 0), 101, _TOOLCHAIN, 600.0, "error: could not compile\n", 1)
    assert result["band"] == "n/a", result


def test_zero_regions_is_still_refused_on_its_own_terms():
    """The refusal that was already there. A crate with no regions compiled nothing this
    reader can measure, which is a different fact from having no tests."""
    result = rust_trace._coverage_verdict((0, 0), 0, _TOOLCHAIN, 600.0, _TWO_TESTS, 1)
    assert result["band"] == "n/a"
    assert "region" in result["details"]
