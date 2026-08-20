"""Both sweeps decide how much the next unit may spend with one rule.

`live_sweep.share` and the per-module slice inside `prove_coverage_repo` compute the same
thing: how many attempts the next unit gets, which is its own cap or whatever the run has
left, whichever is smaller, and never negative. One is written as `max(0, min(cap, ceiling
- spent))` and the other as a slice, `module_gaps[:max(0, max_attempts - attempted)]` after
an earlier `[:cap_per_module]`.

Two spellings of one rule is not caught by the package's duplicate-rule guard, which
compares parse trees: a slice and a `min` are different trees for the same arithmetic. It
is still two places for a budget to drift, and the budget is what decides how much money a
run spends.

Extracting it also reaches the arithmetic. `prove_coverage_repo` is a boundary - it runs a
coverage build and walks a tree - so 36 of its 60 lines are untested by construction, and
the ceiling logic was inside them. The rule is pure and belongs outside.
"""

import inspect

import pytest
from l1_analyzer import budget, coverage_prove, live_sweep, python_coverage_prove


@pytest.mark.parametrize(("cap", "ceiling", "spent", "expected"), [
    (5, 5, 0, 5),        # nothing spent: the cap binds
    (5, 5, 3, 2),        # the run has less left than the cap
    (5, 5, 5, 0),        # spent out
    (5, 5, 9, 0),        # over-spent, which must not go negative
    (5, 100, 0, 5),      # a generous ceiling: the cap still binds
    (0, 100, 0, 0),      # a cap of nothing offers nothing
    (5, 0, 0, 0),        # a ceiling of nothing offers nothing
])
def test_the_allowance_is_the_smaller_of_the_two_bounds(cap, ceiling, spent, expected):
    assert budget.allowance(cap, ceiling, spent) == expected


def test_the_repository_sweep_asks_the_same_rule():
    assert live_sweep.share(run_ceiling=5, per_repo=2, spent=4) == budget.allowance(2, 5, 4)


@pytest.mark.parametrize("module", [coverage_prove, python_coverage_prove], ids=["rust", "python"])
def test_the_module_sweep_asks_it_too(module):
    """Read from the source, because the sweep around it runs a coverage build."""
    assert "budget.allowance" in inspect.getsource(module.prove_coverage_repo), (
        f"{module.__name__} still spells the per-module ceiling as a slice, which is a "
        "second copy of the rule that decides what a run spends"
    )


def test_a_run_that_spends_its_ceiling_offers_nothing_to_the_rest():
    """The property the whole ceiling exists for, stated on the arithmetic: once the run
    ceiling is reached, every later unit is offered zero however large its own cap."""
    spent, offered = 0, []
    for _ in range(6):
        share = budget.allowance(cap=4, ceiling=10, spent=spent)
        offered.append(share)
        spent += share
    assert sum(offered) == 10
    assert offered[-1] == 0
