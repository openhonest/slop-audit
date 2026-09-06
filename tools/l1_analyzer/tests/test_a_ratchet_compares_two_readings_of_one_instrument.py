"""A count is only comparable to a count the same instrument produced.

The self-audit ratchet stores how many vacuous paths the checker found and fails the build
when today's count is higher. It stored a bare number, so when the checker itself improved
the stored figure and the fresh one came from two different instruments and the comparison
meant nothing.

Measured on 2026-09-06. The stored baseline said 6. Today's checker finds 7 in today's code
and 8 in the code the baseline was recorded against, so by one instrument the codebase
improved by one and the ratchet reported it as a regression. The one finding it named,
`_sweep_verdict` in cli.py, is the function written to remove a vacuous affirmative from the
sweep's own summary line.

This is the shape the instrument exists to name, one level up: a number that meant different
things at two times, with nothing saying so. A ratchet that cannot tell "the code got worse"
from "the checker got better" teaches whoever meets it to run --record, which discards
whichever of the two it actually was.

So the baseline records what produced the number, and a comparison across two instruments
refuses rather than reporting a verdict it cannot support.
"""

from __future__ import annotations

import json
import sys

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts"))
import self_audit


def test_the_recorded_baseline_names_the_checker_that_produced_it():
    """Without it the two numbers are not comparable and nothing can say so."""
    recorded = json.loads(self_audit.BASELINE.read_text())
    assert "vacuity_checker" in recorded, sorted(recorded)


def test_the_recorded_checker_is_the_one_running_now():
    """The baseline in the repository has to have been recorded by the checker in the
    repository, or the ratchet in the repository is comparing two instruments."""
    recorded = json.loads(self_audit.BASELINE.read_text())
    assert recorded["vacuity_checker"] == self_audit.vacuity_checker()


@pytest.mark.parametrize("count,recorded,expect", [
    (7, 6, "regressed"),
    (5, 6, "improved"),
    (6, 6, "unchanged"),
])
def test_two_counts_from_one_checker_are_compared_as_before(count, recorded, expect):
    """The ratchet's whole job, unchanged where the instrument is the same."""
    assert self_audit.vacuity_verdict(count, {"vacuity": recorded,
                                              "vacuity_checker": "same"}, "same") == expect


@pytest.mark.parametrize("recorded,why", [
    ({"vacuity": 6, "vacuity_checker": "old"},
     "a baseline another checker produced, which is what made the false regression"),
    ({"vacuity": 6},
     "a baseline recorded before this rule, which carries no checker at all"),
], ids=["another-checker", "no-checker"])
def test_a_count_this_checker_did_not_produce_is_not_a_verdict(recorded, why):
    """Neither number is wrong. They answer different questions, and the honest report says
    the instrument moved rather than that the code did."""
    assert self_audit.vacuity_verdict(7, recorded, "new") == "incomparable", why
