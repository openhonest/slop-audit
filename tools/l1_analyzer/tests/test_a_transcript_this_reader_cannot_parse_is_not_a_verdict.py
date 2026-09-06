"""A proof's verdict comes from pytest's prose, and prose is not a contract.

The Python retention gate decides whether a generated test proved anything by matching two
patterns against pytest's own human-readable output: the short-summary line, and the
`--tb=line` row. Neither is a promise pytest makes. When both miss, the gate returned
`incidental`, which is the noise bucket, so a proof that fired its assertion was thrown away
and the loop reported clean.

Reported on 2026-09-06 by the session auditing turso, on a clean box where three tests of
this gate fail and pass here. The two boxes run different pytest versions and the summary
line changed between them: this machine's pytest 9.0.3 prints `FAILED path::proof_0` with no
exception name at all, so only the second pattern is doing any work, and a version that
moves the second one leaves the gate reading nothing.

Two changes. The reading no longer depends on one line's shape: an exception name is taken
from whichever of the three places pytest puts it. And a transcript this reader cannot parse
is its own answer rather than the noise bucket, because "the setup failed" and "we could not
read the report" send a reader to different places, and only one of them is the repository's
fault.
"""

from __future__ import annotations

import pytest
from l1_analyzer import python_coverage_prove as pcp

# What pytest actually prints when a generated proof's assertion fires, in the three shapes
# this reader has met. The first is pytest 9, the second is what older versions put on the
# summary line, and the third is what --tb=native gives.
_SUMMARY_WITH_NAME = (
    "FAILED /tmp/x/test_l1_coverage_proof.py::proof_0 - AssertionError: must be four\n"
    "1 failed in 0.01s\n"
)
_TB_LINE = (
    "/tmp/x/test_l1_coverage_proof.py:3: AssertionError: must be four\n"
    "FAILED /tmp/x/test_l1_coverage_proof.py::proof_0\n1 failed in 0.00s\n"
)
_TB_NATIVE = (
    '  File "/tmp/x/test_l1_coverage_proof.py", line 3, in proof_0\n'
    '    assert result == 4, "must be four"\n'
    "AssertionError: must be four\n"
    "FAILED /tmp/x/test_l1_coverage_proof.py::proof_0\n1 failed in 0.01s\n"
)
_SETUP_FAILED = (
    "/tmp/x/test_l1_coverage_proof.py:2: TypeError: discounted_total() missing 1 argument\n"
    "FAILED /tmp/x/test_l1_coverage_proof.py::proof_0\n1 failed in 0.00s\n"
)


@pytest.mark.parametrize("output", [_SUMMARY_WITH_NAME, _TB_LINE, _TB_NATIVE],
                         ids=["summary", "tb-line", "tb-native"])
def test_a_fired_assertion_is_a_divergence_however_pytest_spelled_it(output):
    """The retention gate's whole job. It read one shape and pytest has printed three."""
    assert pcp._classify(output, 1) == "divergence"


def test_another_exception_is_still_incidental():
    """The distinction the gate exists to make. A proof that could not even call the
    function has proven nothing about it."""
    assert pcp._classify(_SETUP_FAILED, 1) == "incidental"


def test_a_clean_run_is_still_a_pass():
    assert pcp._classify("1 passed in 0.01s\n", 0) == "pass"


def test_a_transcript_with_no_verdict_in_it_says_so():
    """The change that matters most. A failing run this reader cannot parse used to be filed
    as incidental, so a proof that fired was discarded and the loop reported clean.

    Unreadable is its own answer because it sends a reader somewhere else: incidental is the
    generated test's fault, and this is ours."""
    assert pcp._classify("FAILED nothing::useful\n1 failed in 0.01s\n", 1) == "unreadable"


def test_the_unreadable_answer_has_a_bucket_to_be_counted_in():
    """A verdict with nowhere to be tallied would be dropped on the way to the report, which
    is the same silence one step along."""
    assert "unreadable" in pcp.EMPTY_OUTCOMES


def test_a_timeout_is_still_its_own_answer():
    assert pcp._classify("", 124) == "error"


def test_a_proof_that_never_ran_asserted_nothing():
    """Read before any exception name. A conftest raising AssertionError while the proof
    fails to import would otherwise read as the proof's own assert firing, which is a
    finding about a branch nothing exercised."""
    out = ("/repo/conftest.py:9: AssertionError: fixture broke\n"
           "ERROR /t/test_l1_coverage_proof.py::proof_0\n1 error in 0.01s\n")
    assert pcp._classify(out, 1) == "incidental"
