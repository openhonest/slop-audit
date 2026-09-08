"""A run that produced no compiler output did not fail to compile.

The retention loop reads a `cargo test` run and files what it sees. Anything that exited
non-zero without printing a test line was filed as a compile error, so every way of failing
to get cargo to run at all arrived in the report as tests the compiler had rejected.

The first parallel run on turso: 182 generated tests, 181 recorded as "did not compile", and
sampling every 30 seconds across the whole twelve-minute module loop found zero cargo and
zero rustc processes. 181 compiles do not hide from 24 consecutive samples. The compiler
never ran, and the report named 181 outcomes after an event that did not happen.

A compile error is something the toolchain TOLD us: rustc prints `error[E0308]` or cargo
prints "could not compile". Neither appearing, and no test line either, means nothing we can
see compiled anything. That is a fact about this tool's ability to run, not about the
generated test, and the two send a reader to different places.

Named `unrun` and counted apart, like `unreported` beside `error` before it, for the reason
that bucket already gives: counting one as the other makes a run whose totals do not add up
look like a run with noise in it.
"""

from __future__ import annotations

import pytest
from l1_analyzer import coverage_prove

_COMPILER_SPOKE = (
    "   Compiling turso-core v0.1.0\n"
    "error[E0308]: mismatched types\n"
    "error: could not compile `turso-core` (lib test) due to 1 previous error\n"
)
_TEST_RAN_AND_FAILED = (
    "running 1 test\ntest l1_coverage_proof::proof_0 ... FAILED\n"
    "test result: FAILED. 0 passed; 1 failed\n"
)
_TEST_RAN_AND_PASSED = "running 1 test\ntest result: ok. 1 passed; 0 failed\n"


def test_a_compiler_that_spoke_is_a_compile_error():
    """The reading that must not move. rustc rejected the test and said so."""
    assert coverage_prove._classify_run(_COMPILER_SPOKE, 101) == "error"


@pytest.mark.parametrize("output", ["", "no cargo", "error: no such subcommand: `test`\n"],
                         ids=["silence", "no cargo", "cargo refused"])
def test_a_run_that_produced_nothing_is_unrun_rather_than_a_compile_error(output):
    """Every way of not reaching the compiler at all, which used to be filed as the
    compiler rejecting the test."""
    assert coverage_prove._classify_run(output, 1) == "unrun"


def test_a_test_that_ran_is_still_read_from_its_result():
    assert coverage_prove._classify_run(_TEST_RAN_AND_FAILED, 101) == "fail"
    assert coverage_prove._classify_run(_TEST_RAN_AND_PASSED, 0) == "pass"


def test_the_unrun_answer_has_a_bucket_of_its_own():
    """A verdict with nowhere to be tallied is dropped on the way to the report."""
    assert "unrun" in coverage_prove.EMPTY_OUTCOMES
    assert coverage_prove.EMPTY_OUTCOMES["unrun"] == 0


def test_a_sweep_where_nothing_ran_says_so_rather_than_counting_compile_errors():
    """What turso's card should have said. 181 tests the compiler never saw is a fact about
    this tool, and a reader handed 181 compile errors goes and reads generated tests."""
    said = coverage_prove._outcome_detail(
        {**coverage_prove.EMPTY_OUTCOMES, "unrun": 181, "error": 0})
    assert "181" in said and "never ran" in said, said


def test_a_sweep_with_real_compile_errors_still_reports_them():
    said = coverage_prove._outcome_detail({**coverage_prove.EMPTY_OUTCOMES, "error": 7})
    assert "7 did not compile" in said, said
