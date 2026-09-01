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

import ast
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
def test_neither_sweep_spells_the_ceiling_itself(module):
    """Read from the source, because the sweep around it runs a coverage build.

    Twice over, this test has broken on the fix rather than on a regression, which is the
    direction it wants the code to go. It first read `prove_coverage_repo` for the text
    `budget.allowance`, and broke when the choosing was lifted out of that boundary into a
    function of its own. It then counted the call in the module, and broke again on
    2026-08-31 when the choosing itself moved to `budget`, shared by both sweeps: neither
    module spells the ceiling at all now, which is what it was always asking for.

    What it holds is the same thing it always held. A second spelling of this rule is how
    the budget drifts, and the budget is what decides how much money a run spends."""
    calls = [node for node in ast.walk(ast.parse(inspect.getsource(module)))
             if isinstance(node, ast.Call)
             and ast.unparse(node.func).endswith("allowance")]
    assert calls == [], (
        f"{module.__name__} spells the ceiling itself, which is a second copy of the rule "
        "that decides what a run spends"
    )


def test_the_rule_is_written_in_exactly_one_place():
    """The whole point of the two tests above, said once about the package.

    A slice and a `min` are different parse trees for the same arithmetic, so the package's
    duplicate-rule guard cannot see a second spelling. This can."""
    written = [node for node in ast.walk(ast.parse(inspect.getsource(budget)))
               if isinstance(node, ast.FunctionDef) and node.name == "allowance"]
    assert len(written) == 1

    asked = [node for node in ast.walk(ast.parse(inspect.getsource(budget)))
             if isinstance(node, ast.Call) and ast.unparse(node.func) == "allowance"]
    assert len(asked) == 1, "the selection rule asks the allowance once, per module it walks"


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
