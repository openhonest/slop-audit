"""The outcome breakdown accounts for every gap the sweep paid for.

A sweep of 20 attempts printed "Of 15 generated tests: ... 15 passed". The other five were
declines: the model was asked, produced nothing usable, and cost the same as the fifteen.
The sentence did not mention them, so a reader reconciling the run against its bill was
five short with nothing to explain the gap.

The three-case rule fixed the all-declined sweep and left this one: declines are named when
NOTHING ran, and silent when anything did. What a reader needs is the same either way.
"""

import pytest
from l1_analyzer import coverage_prove, python_coverage_prove


@pytest.mark.parametrize("module", [coverage_prove, python_coverage_prove], ids=["rust", "python"])
def test_a_partly_declined_sweep_names_the_declines(module):
    outcomes = dict.fromkeys(module.EMPTY_OUTCOMES, 0)
    outcomes.update({"pass": 15, "declined": 5})
    said = module.sweep_detail(retained=0, modules=5, located=157, outcomes=outcomes,
                               provenance="cpython 3.13")
    # The run count belongs to the outcome breakdown the caller appends; what was missing
    # is the declines, which no part of the sentence mentioned once anything had run.
    assert "5" in said and "declin" in said.lower(), (
        f"the five gaps the model declined are missing from the account: {said}")


@pytest.mark.parametrize("module", [coverage_prove, python_coverage_prove], ids=["rust", "python"])
def test_a_sweep_with_no_declines_says_nothing_about_them(module):
    """It speaks only when there were any. A zero in every report is noise a reader learns
    to skip, which is how the one report that mattered would be missed."""
    outcomes = dict.fromkeys(module.EMPTY_OUTCOMES, 0)
    outcomes["pass"] = 15
    assert "declin" not in module.sweep_detail(
        retained=0, modules=5, located=15, outcomes=outcomes, provenance="cpython 3.13").lower()
