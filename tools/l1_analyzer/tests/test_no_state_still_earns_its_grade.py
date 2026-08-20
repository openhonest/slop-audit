"""A repository with no classified state scores 100, and that is the right answer.

Written to change it, and it should not change. The investigation is kept because the
reasoning is not obvious and the next reader of `vacuity.check` will land on the same
finding: `testable_share` publishes 100 when nothing was decided, which is a share of an
empty set and the top of the scale, and everywhere else in this package a zero denominator
refuses through `incomplete.ratio`.

Two things make it right here.

Refusing to grade a codebase with no mutable state was a defect once already.
`test_a_codebase_with_no_mutable_state_by_design_is_graded_not_refused` was written for it:
the enumerator looked at every declaration, admitted none because none was state, and the
report called its own successful reading insufficient basis. No mutable state is the
outcome this framework aims at, and the instrument must not punish the thing it advocates.

And the top grade is not reachable by hiding state. Three readings agree before this is
reached: the classifier decided nothing, L1.18 read zero, and the census declared
candidates and admitted none. When L1.18 disagrees the caller refuses outright, which
`test_a_classifier_that_decided_nothing_beside_a_non_zero_l1_18_refuses` covers. Two
measures disagreeing is a missing rule; three agreeing is a reading.

So these hold the behaviour and the reason, and the site carries the same note beside the
vacuity finding it is a false positive for.
"""

import pathlib
import tempfile

import pytest
from l1_analyzer import indicators, report

STATELESS = (
    "def add(a: int, b: int) -> int:\n"
    "    return a + b\n\n\n"
    "def mul(a: int, b: int) -> int:\n"
    "    return a * b\n"
)

# Real module-level mutable state, keyed by a literal, which is what the classifier bounds.
# An UPPERCASE binding is a constant and is not state at all: the first version of this
# fixture used one and classified nothing, which is the case the stateless tests cover.
WITH_STATE = (
    "cache = {}\n\n\n"
    "def remember(value: int) -> int:\n"
    "    cache['last'] = value\n"
    "    if cache['last'] > 0:\n"
    "        return cache['last']\n"
    "    return 0\n"
)


def _graded(source: str) -> dict:
    directory = pathlib.Path(tempfile.mkdtemp())
    (directory / "m.py").write_text(source)
    results = indicators.compute_source_indicators(
        directory, lang="python", exec_tests=False, timeout_seconds=30,
        classify_state_bounds=True)
    return report.grade_summary(results, report.UNORDERED_CLASS_BOUND)


def test_a_stateless_repository_is_graded_rather_than_refused():
    """The property the earlier defect was about, asserted end to end."""
    graded = _graded(STATELESS)
    assert graded["counts"] == {"neutral": 0, "promiscuous": 0, "unresolved": 0}
    assert graded["status"] == "can"
    assert graded["grade"] is not None
    assert graded["testable_pct"] == 100


def test_state_the_classifier_bounded_earns_its_own_share():
    """The measure still measures, so 100 is not simply what it always says."""
    graded = _graded(WITH_STATE)
    assert sum(graded["counts"].values()) > 0
    assert graded["testable_pct"] is not None


@pytest.mark.parametrize(("neutral", "decided", "expected"), [
    (0, 0, 100),
    (1, 1, 100),
    (3, 4, 75),
    (0, 4, 0),
])
def test_the_share_is_the_arithmetic_it_claims_to_be(neutral, decided, expected):
    """Including the boundary the whole investigation turned on: one decided piece of state
    gives a real 100, and zero decided gives the same number for a different reason. The
    two are told apart by the counts beside them, not by the percentage."""
    assert report.testable_share(neutral, decided) == expected


def test_the_site_records_why_the_vacuity_finding_there_is_a_false_positive():
    """The finding will be raised again by the next reader of vacuity.check, so the answer
    lives at the site rather than only in this file's history."""
    import inspect

    note = inspect.getdoc(report.testable_share)
    assert "FALSE POSITIVE" in note
    assert "graded_not_refused" in note
