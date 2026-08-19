"""A gap the model declined is counted, and a report that located gaps never says it did not.

Both defects were found by the first live run, on 2026-08-19, which is what the run was
for. Sweeping this package at a ceiling of 2 printed:

    no proof-ready uncovered branches located across 1 modules
    STOPPED AT THE CEILING: 2 of 154 located gaps were attempted

Both halves of one sentence, contradicting each other. 154 gaps were located and 2 were
handed to a model. The model returned nothing usable for either, so both were dropped on
`if bucket == "skipped": continue`, `outcomes` summed to zero, and the report fell through
to the sentence it prints when it found nothing at all.

Two failures, one shape. A model call that produced nothing costs money and left no trace,
so a run's totals could not be reconciled against its bill. And a report that located 154
uncovered branches told a reader there were none, which is a measure publishing a claim it
never earned, the category this whole instrument exists to name.
"""


import pytest
from l1_analyzer import coverage_prove, python_coverage_prove


@pytest.mark.parametrize("module", [coverage_prove, python_coverage_prove],
                         ids=["rust", "python"])
def test_declined_is_a_bucket_the_outcomes_carry(module):
    """Not folded into error. A compile error is something the runner TOLD us; a decline is
    the model returning nothing, and the two send a reader to different places."""
    assert "declined" in module.EMPTY_OUTCOMES


def test_a_module_whose_every_gap_was_declined_reports_them(tmp_path):
    """The orchestration, by injection: a proposer that always returns None."""
    (tmp_path / "m.py").write_text("def f(x):\n    if x:\n        return 1\n    return 2\n")
    gaps = [{"function": "f", "line": 2, "kind": "if"}, {"function": "f", "line": 4, "kind": "else"}]
    retained, outcomes = python_coverage_prove._prove_module(
        tmp_path, "m.py", "python3", gaps, 0, 5.0,
        lambda *a, **k: None, lambda *a, **k: None,
        lambda *a, **k: (0, ""))
    assert retained == []
    assert outcomes["declined"] == 2
    assert sum(outcomes.values()) == 2, "a declined gap must reach the totals"


@pytest.mark.parametrize("module", [coverage_prove, python_coverage_prove],
                         ids=["rust", "python"])
def test_located_gaps_are_never_reported_as_none_located(module):
    """The sentence that lied. Located-but-none-ran is its own case, distinct from
    nothing-was-located, and it names how many were declined."""
    said = module.sweep_detail(retained=0, modules=1, located=154, outcomes={"declined": 2},
                               provenance="cpython 3.13")
    assert "no proof-ready uncovered branches located" not in said
    assert "154" in said and "2" in said


@pytest.mark.parametrize("module", [coverage_prove, python_coverage_prove],
                         ids=["rust", "python"])
def test_nothing_located_still_says_nothing_was_located(module):
    said = module.sweep_detail(retained=0, modules=3, located=0, outcomes={},
                               provenance="cpython 3.13")
    assert "no proof-ready uncovered branches located" in said
