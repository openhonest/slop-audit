"""A `match` statement crashes the branch reader, and it is in our list of branches.

The reader walks a function for constructs where control can take more than one path, and
its list names `if`, `for`, `while`, `try` and `match`. It then asks each one for its body.
Four of the five have one. A `match` holds cases instead, so asking it for a body raises.

    def go(x):
        match x:
            case 1:
                return 2
        return 0

That is enough. Any repository with a `match` anywhere in an audited function loses the
whole reading, and `match` is ordinary modern Python.

The comment above the line said a guard there would be a check against a shape that cannot
arrive. It was right about four constructs and wrong about the fifth, which is why it read as
settled. Nothing had type-checked this package until 2026-08-29, and the checker named this
line the first time it ran.
"""

import ast

import pytest
from l1_analyzer import facets

_MATCH = '''def go(x):
    match x:
        case 1:
            return "one"
        case _:
            return "other"
'''

_IF = '''def go(x):
    if x:
        return "yes"
    return "no"
'''


def _branches(source: str, uncovered: frozenset[int] = frozenset()) -> list[dict]:
    return facets._branch_facets(ast.parse(source).body[0], uncovered)


def test_a_match_statement_is_read_rather_than_raising():
    found = _branches(_MATCH)
    assert found, "a match is a branch and the reader lists it as one"
    assert all(f["kind"] == "unexercised_branch" for f in found), found


def test_the_match_reports_the_line_it_sits_on():
    assert _branches(_MATCH)[0]["line"] == 2


def test_a_match_whose_first_case_never_ran_is_silent():
    """The reading the whole thing exists for: a branch whose body was never entered."""
    body_line = 4
    assert _branches(_MATCH, frozenset({body_line}))[0]["silent"] is True


def test_a_match_whose_first_case_did_run_is_not():
    assert _branches(_MATCH, frozenset({99}))[0]["silent"] is False


def test_the_four_constructs_that_always_had_a_body_still_read():
    assert _branches(_IF)[0]["line"] == 2


@pytest.mark.parametrize("source", [
    "def go(x):\n    for i in x:\n        pass\n",
    "def go(x):\n    while x:\n        break\n",
    "def go(x):\n    try:\n        f()\n    except ValueError:\n        pass\n",
])
def test_every_other_branch_construct_still_reads(source):
    assert _branches(source)
