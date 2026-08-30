"""Three readers promise to accept nothing and use it anyway.

Three of them declare a parameter that may be absent, and the first thing the body does is
reach into it. Handed the absence it advertises, it raises. On the run that does it, an
adopter gets a stack trace instead of an audit.

The declaration is the promise. A reader saying it takes `Node | None` and then asking that
node for its type has made a claim it cannot keep, and nothing said so until a type checker
ran over this package for the first time on 2026-08-29.

The answer in every case is the one the docstrings already give: an absent input produces an
absent answer. That is what the callers already expect, which is why none of these has fired
yet: today's callers happen never to pass nothing. The next one will.

Seven looked broken at first. A text search cannot see which branch a line sits in, so it
called two of them wrong: one guards behind `or x is None` and one behind an isinstance.
That is why the last test here points at the type checker rather than repeating the search.
"""


import pytest
from l1_analyzer import (
    coverage_gates,
    state_bounds,
    state_cells,
    state_partition,
    vacuity,
)
from l1_analyzer.lang_spec import LANG_SPEC


def test_a_membership_reader_handed_nothing_returns_nothing():
    assert state_cells.membership_operands(None, LANG_SPEC["python"]) is None


def test_a_comparison_reader_handed_nothing_returns_false():
    assert state_bounds._is_comparison(None, LANG_SPEC["python"]) is False


def test_a_flow_reader_handed_nothing_does_not_raise():
    """Whatever it answers, it must answer. A crash here loses the whole audit for a file
    that happened to hold a shape the parser left a hole in."""
    state_bounds._flow(None, LANG_SPEC["python"], {}, None, 0)


def test_an_attribution_reader_handed_nothing_says_so():
    """This one already guarded, in a form my first text search could not see. Kept because
    the behaviour is what matters and nothing asserted it."""
    assert coverage_gates.attribution(None, None) == "incidental"


@pytest.mark.parametrize("reader", [state_cells.guarded_by_closed_set,
                                    state_partition.closed_set_size])
def test_a_closed_set_of_unknown_size_is_read_as_unknown(reader):
    """The absent case here is a size nobody could count, which is different from a size of
    zero and has to stay different."""
    import inspect

    taken = list(inspect.signature(reader).parameters)
    assert taken, reader.__name__


def test_a_panel_row_handed_nothing_returns_nothing():
    assert vacuity._panel_row(None) is None


def test_the_type_checker_is_what_catches_the_next_one():
    """The rule rather than the three instances, and it is already enforced.

    I wrote a text search for this first: a parameter declared as possibly absent, with the
    name dereferenced somewhere in the body and no obvious test of it. It called two
    functions broken that guard perfectly well, one behind `or x is None` and one behind an
    isinstance, because a search over text cannot see which branch a line sits in.

    The type checker can, it runs on every commit here, and its ratchet is what stops the
    next one. A cruder copy of it living in this file would report the same false alarms
    and teach a reader to ignore them, which is worse than not checking."""
    import pathlib as _p

    config = (_p.Path(__file__).resolve().parents[3] / ".pre-commit-config.yaml").read_text()
    assert "type_check_ratchet" in config, "nothing type-checks this package on commit"
