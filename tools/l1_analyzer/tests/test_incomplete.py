"""The refusal mechanism itself, asserted directly.

Every other test that reaches this module does so through a measure that raises, so the two
functions here were only ever exercised sideways. A helper nothing tests directly is how a
message format drifts, and the format is the point: `INCOMPLETE CODE: ` is what a reader
greps for in a CI transcript.
"""

import pytest
from l1_analyzer import incomplete
from l1_analyzer.incomplete import IncompleteCode


def test_refuse_returns_the_exception_rather_than_raising_it():
    """The call site reads `raise incomplete.refuse(...)`, so the raise stays visible where it
    happens. A helper that raised on the caller's behalf would hide control flow inside a
    function call, which is the thing this module exists to stop."""
    built = incomplete.refuse("L1.16 trailing whitespace", "no lines were read")
    assert isinstance(built, IncompleteCode)


def test_the_message_opens_with_the_greppable_marker_and_carries_both_halves():
    message = str(incomplete.refuse("L1.17 god-file concentration", "no production file was read"))
    assert message.startswith("INCOMPLETE CODE: ")
    assert "L1.17 god-file concentration" in message
    assert "no production file was read" in message


def test_ratio_is_a_percentage_not_a_fraction():
    # The four sites this replaced all multiplied by 100 themselves; returning a fraction here
    # would silently divide every published rate by a hundred.
    assert incomplete.ratio(1, 4, "m", "b") == 25.0
    assert incomplete.ratio(0, 4, "m", "b") == 0.0


def test_ratio_refuses_a_zero_denominator_rather_than_returning_zero():
    """Zero over zero is not zero percent, it is the absence of a measurement. This is the
    line that makes `if total > 0 else 0.0` unwriteable: there is no expression left that
    yields a number when nothing was counted."""
    with pytest.raises(IncompleteCode, match="L1.18 unbounded mutable state"):
        incomplete.ratio(0, 0, "L1.18 unbounded mutable state", "no function was enumerated")


def test_ratio_names_the_basis_so_the_boundary_can_print_it():
    with pytest.raises(IncompleteCode, match="no function was enumerated"):
        incomplete.ratio(3, 0, "L1.18 unbounded mutable state", "no function was enumerated")
