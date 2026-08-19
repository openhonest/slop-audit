"""A repo-wide sweep stops at a ceiling, and says when it stopped there.

Both `prove_coverage_repo` functions capped gaps PER MODULE and had no repo-wide bound at
all. A crate with two hundred modules attempted up to a thousand gaps, each one a model
call and an in-crate compile. Nothing in the signature said how much a sweep could cost,
so nobody could authorise one.

The ceiling is a total across the repository, and it is adjustable because how much to
spend is not a fact about the code. What matters as much: a truncated sweep must SAY it
was truncated. A result reading "attempted 5, retained 1" with no further word reads as a
codebase with five uncovered branches, when it may have had five hundred. That is the
same unmeasured-read-as-clean shape the whole instrument exists to refuse, wearing a
budget for a disguise.
"""

import inspect

import pytest
from l1_analyzer import coverage_prove, python_coverage_prove

_SWEEPS = (coverage_prove.prove_coverage_repo, python_coverage_prove.prove_coverage_repo)


@pytest.mark.parametrize("sweep", _SWEEPS, ids=["rust", "python"])
def test_the_sweep_takes_an_adjustable_ceiling(sweep):
    parameter = inspect.signature(sweep).parameters.get("max_attempts")
    assert parameter is not None, "no repo-wide ceiling; the sweep's cost is unbounded"
    assert parameter.default == 5, "the ceiling starts at 5"


@pytest.mark.parametrize("sweep", _SWEEPS, ids=["rust", "python"])
def test_a_ceiling_of_zero_attempts_nothing_and_says_why(sweep, tmp_path):
    """The boundary that proves the ceiling is read before any model call: at zero the
    sweep must refuse without needing a toolchain, a key or a network."""
    result = sweep(tmp_path, max_attempts=0)
    assert result["attempted"] == 0
    assert result["retained"] == []
    assert "ceiling" in result["detail"], result["detail"]


def test_a_truncated_sweep_names_what_it_did_not_attempt():
    """The reporting half, asserted on the pure helper so it needs no model.

    Silence here would be the defect: a sweep that stopped early and said nothing reads as
    a sweep that finished."""
    detail = coverage_prove.ceiling_detail(attempted=5, located=137, ceiling=5)
    assert "5" in detail and "137" in detail
    assert "ceiling" in detail


def test_an_untruncated_sweep_says_nothing_about_a_ceiling():
    """It only speaks when it bit. A sweep that reached the end of the work is not
    truncated, and saying so anyway would train readers to ignore the sentence."""
    assert coverage_prove.ceiling_detail(attempted=12, located=12, ceiling=5000) == ""
