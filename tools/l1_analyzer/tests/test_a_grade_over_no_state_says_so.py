"""A percentage of an empty set is not a measurement, and the card printed one.

Run against this repository the audit reported "Grade A, 100% of its state is finitely
testable" over zero pieces of state: zero finitely testable, zero unbounded, zero undecided.
The zeroes were printed underneath, so nothing was hidden, and the headline still made a
claim about a set with nothing in it.

The classifier is not wrong. This package keeps no mutable state, which is what its own
rules ask for, and the census confirms the reader reached all 831 declaration sites and
admitted none. So the honest sentence is that there is no state to be unbounded, which is a
STRONGER claim than a percentage, not a weaker one.

This is the same objection this instrument makes everywhere else. A share over an empty
denominator reads as evidence and is not, and the reason the silence index exists is that
zero of zero comes out as a clean number.
"""

from l1_analyzer import report

_NO_STATE = {"neutral": 0, "promiscuous": 0, "unresolved": 0}
_SOME_STATE = {"neutral": 4, "promiscuous": 0, "unresolved": 0}
_CENSUS_READ_EVERYTHING = {"declared": 831, "visited": 831, "admitted": 0, "unread_kinds": []}


def test_a_repository_with_no_state_at_all_is_its_own_basis():
    """Not MEASURED. A reading over nothing is not the same kind of answer as a reading over
    something, and one word for both is what let the percentage print."""
    assert report._basis("Healthy", _NO_STATE, True, _CENSUS_READ_EVERYTHING) == report.NO_STATE


def test_a_repository_with_state_is_still_measured():
    """The other direction, and the one that keeps the grade worth having."""
    assert report._basis("Healthy", _SOME_STATE, True, _CENSUS_READ_EVERYTHING) == report.MEASURED


def test_no_state_is_not_the_same_as_state_nobody_read():
    """The census tells them apart. Here the reader reached every declaration site and
    admitted none; unread is where it reached none of them, and that already refuses a
    grade. Both have an empty denominator and only one is a gap in the instrument."""
    never_read = {"declared": 831, "visited": 0, "admitted": 0, "unread_kinds": ["a binding"]}
    assert report._basis("Healthy", _NO_STATE, True, never_read) == report.UNREAD


def test_the_card_says_there_is_no_state_rather_than_a_share_of_none():
    """What a reader sees. The headline claimed a percentage of an empty set, and the three
    zeroes underneath were the only thing saying otherwise."""
    import pathlib

    from l1_analyzer import card, indicators

    here = pathlib.Path(__file__).resolve().parents[1]
    results = indicators.compute_source_indicators(
        here, lang="python", exec_tests=False, timeout_seconds=5.0,
        classify_state_bounds=True, python_executable=None)
    model = card.build_card("o/r", "python", results, ran_tests=False, analyzer_version="test")
    rendered = card.card_markdown(model)
    assert "% of its state is finitely testable" not in rendered, rendered[:400]
    assert "keeps no data" in rendered.lower() or "no state" in rendered.lower(), rendered[:400]
