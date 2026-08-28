"""Type Declarations Over Imperative Validation, which had no clause until now.

The principle, from the canon: a hand-written check is a copy of a constraint that already
exists elsewhere. The column is varchar(255), the field is typed, the form says
type="email", and then a function checks all three again in its own words. Copies drift, and
the copy that drifts is the one on the path nobody exercised.

This is NOT Trust the Contract in the Interior, which is the clause next door. That one is
about a branch nothing can reach: the caller was already excluded by the declaration. This
one is about two live constraints that can disagree, and the harm is the drift rather than
the unreachable branch. They were one clause under one name until the canon separated them.

What makes it decidable without reading a database is the duplicated bound. The same literal
appearing in a declaration and again in a hand-written check IS the copy. One is enforced by
the machinery and one by a programmer, and nothing keeps them equal.
"""

import pytest
from l1_analyzer import honest_code_contracts as contracts
from l1_analyzer import honest_code_read as read


def _found(source: str, lang: str = "python") -> list[dict]:
    return contracts.copied_constraints(read.read_tree(source, lang)) or []


_COPIED = '''from typing import Annotated


class Account(TypedDict):
    handle: Annotated[str, 255]


def register(handle):
    if len(handle) > 255:
        raise ValueError("too long")
    return handle
'''

_DECLARED_ONLY = '''class Account(TypedDict):
    handle: Annotated[str, 255]


def register(handle):
    return handle
'''

_CHECKED_ONLY = '''def register(handle):
    if len(handle) > 255:
        raise ValueError("too long")
    return handle
'''


def test_a_bound_declared_and_then_checked_by_hand_is_reported():
    found = _found(_COPIED)
    assert found, "the same bound is in a declaration and in a check"
    assert "255" in found[0]["detail"]
    assert "drift" in found[0]["detail"] or "disagree" in found[0]["detail"]


def test_a_bound_only_declared_is_left_alone():
    """What the rule asks for. The machinery enforces it and nobody wrote it twice."""
    assert _found(_DECLARED_ONLY) == []


def test_a_bound_only_checked_is_left_alone():
    """One constraint, written once, in the only place it exists. There is nothing for it
    to drift from, and the rule is about copies."""
    assert _found(_CHECKED_ONLY) == []


def test_it_names_where_the_declaration_is():
    """A reader has to see both halves to judge it, and the check is the half they are
    standing in front of."""
    assert "Account" in _found(_COPIED)[0]["instead"] or "declaration" in _found(_COPIED)[0]["instead"]


def test_a_number_used_for_something_else_is_not_a_copy():
    """The bound must be a CONSTRAINT in both places. A field holding the number 255 and a
    loop counting to 255 are not two copies of one rule."""
    assert _found("class C(TypedDict):\n    size: int\n\n\n"
                  "def go():\n    total = 0\n    for i in range(255):\n"
                  "        total += i\n    return total\n") == []


@pytest.mark.parametrize("lang", ["javascript", "ruby", "c"])
def test_a_language_with_no_declared_bound_here_is_not_decided(lang):
    """The vocabulary carries where a language declares a bound. Where it declares none,
    the question cannot arise, and an empty list would claim the file was read and clean."""
    sources = {"javascript": "function go(x) { if (x.length > 255) { throw new Error() } }\n",
               "ruby": "def go(x)\n  raise if x.length > 255\nend\n",
               "c": "int go(char *x) { return 0; }\n"}
    assert contracts.copied_constraints(read.read_tree(sources[lang], lang)) is None, lang


def test_two_checks_of_one_declared_bound_are_two_findings():
    """Each copy can drift on its own, so each is its own site to repair."""
    found = _found(_COPIED + '''

def rename(handle):
    if len(handle) > 255:
        raise ValueError("too long")
    return handle
''')
    assert len(found) == 2, found
