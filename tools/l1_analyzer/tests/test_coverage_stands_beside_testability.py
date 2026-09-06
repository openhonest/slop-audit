"""The two numbers a reader confuses must sit next to each other.

Coverage says how much of the code the suite ran. Finite testability says how much of the
state could ever be checked exhaustively. They are different measurements and a high one
does not buy the other, which is the whole claim this instrument exists to make. The card
carried both and put them pages apart: the grade sentence at the top, the coverage figure
down in the runtime table, and nothing anywhere saying they were different questions.

So a reader with 90 percent coverage read the grade as a contradiction rather than as the
finding.

Asked for on 2026-09-06: show the coverage number next to the mutability number, to prove
that coverage does not equal testability.

The pair is printed only where both halves are real. A card with no grade read no state, and
a run that measured no coverage has no figure; in each case the line says which half is
missing rather than pairing a number with a blank.
"""

from __future__ import annotations

from l1_analyzer import card

_BAND = {"value": 0, "band": "Healthy", "details": "d"}
_STATIC = {k: _BAND for k in ("L1.18", "L1.17", "L1.15", "L1.10", "L1.11", "L1.9", "L1.16")}

# One repository whose suite runs almost everything and whose state is mostly not
# enumerable: the case the pairing exists for.
_STATE = {
    "verdict": "promiscuous",
    "counts": {"neutral": 47, "promiscuous": 30, "unresolved": 23},
    "coverage": {v: {"observe_only": 0, "drives_decision": 0}
                 for v in ("neutral", "promiscuous", "unresolved")},
    "silence": {"count": 0, "fraction": 0.0, "sites": []},
    "resolvable_fraction": 0.47,
    "findings": [],
    "bucketed": {"counts": {}, "paths": []},
    "census": {"declared": 100, "visited": 100, "unread_kinds": {}},
}


def _markdown(panel: dict, ran_tests: bool) -> str:
    return card.card_markdown(
        card.build_card("x", "python", panel, ran_tests=ran_tests, analyzer_version="test"))


def test_the_coverage_figure_is_printed_beside_the_testability_figure():
    printed = _markdown({**_STATIC, "L1.18b": _STATE,
                         "L1.19": {"value": 92.4, "band": "Healthy", "details": "d"}}, True)
    assert "92.4" in printed
    head = printed[:printed.index("## ")] if "## " in printed else printed
    assert "92.4" in head, "the coverage figure is not beside the grade: " + head


def test_the_pair_says_the_two_numbers_answer_different_questions():
    """A number beside a number is a coincidence. The sentence is what makes it a finding."""
    printed = _markdown({**_STATIC, "L1.18b": _STATE,
                         "L1.19": {"value": 92.4, "band": "Healthy", "details": "d"}}, True)
    assert "exhaustively" in printed.lower()


def test_a_run_that_measured_no_coverage_says_so_rather_than_pairing_a_blank():
    """The half this instrument keeps getting wrong. A missing figure printed as nothing
    reads as a figure of nothing."""
    printed = _markdown({**_STATIC, "L1.18b": _STATE,
                         "L1.19": {"value": "n/a", "band": "n/a",
                                   "details": "pytest collected no tests"}}, True)
    assert "pytest collected no tests" in printed


def test_the_static_card_pairs_nothing_because_it_ran_no_suite():
    """try.slopaudit.org never executes anyone's code, so there is no coverage number to
    stand beside anything, and inventing the pairing there would be the vacuous claim in a
    new place."""
    printed = _markdown({**_STATIC, "L1.18b": _STATE}, False)
    assert "coverage does not" not in printed.lower()
