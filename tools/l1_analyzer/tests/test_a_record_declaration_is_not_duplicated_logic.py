"""Every record declaration in the language looks like every other one.

This check normalises identifiers and literals away so that two functions doing the same
thing with different names read alike. That is what makes it work on logic. It is also what
makes it wrong about a record: a record declaration IS its field names, and erasing them
leaves `class X: a: str; b: str; c: int`, which is the shape of every record ever written.

Four types in this package are called Finding. They hold different facts, and merging them
would be a defect rather than a fix: one names a clause and a line, one names a concurrency
site and its severity, one names a secret and how often it appears. They are four records,
and the check reported them as duplicated code because after normalising there was nothing
left to tell them apart.

This is the discount the god-file rule already makes and this module already borrows. That
one says a data table is not a pile of logic. A record declaration is the same argument: it
is a list of names, and the names are the whole content.

Measured before the change: 93 of 1207 duplicated lines in this repository were inside a
record declaration.
"""

from l1_analyzer import clone_detect

_TWO_RECORDS = '''from typing import TypedDict


class Finding(TypedDict):
    """One site a clause found."""

    clause: str
    symbol: str
    line: int
    detail: str
    instead: str


class Secret(TypedDict):
    """One credential-shaped string."""

    rule: str
    file: str
    line: int
    excerpt: str
    occurrences: int
'''

_TWO_FUNCTIONS = '''def widen(values, limit):
    out = []
    for value in values:
        if value > limit:
            out.append(value * 2)
        else:
            out.append(value)
    return out


def narrow(items, ceiling):
    kept = []
    for item in items:
        if item > ceiling:
            kept.append(item * 2)
        else:
            kept.append(item)
    return kept
'''


def _duplicated(source: str) -> int:
    from l1_analyzer.indicators import _get_parser

    root = _get_parser("python").parse(source.encode()).root_node
    streams = {"a.py": clone_detect.normalized_tokens(root, "python")}
    return sum(len(v) for v in clone_detect.duplicated_lines(streams, 20).values())


def test_two_records_are_not_duplicated_code():
    assert _duplicated(_TWO_RECORDS) == 0


def test_two_functions_doing_the_same_thing_still_are():
    """The direction that must not move. Erasing the names is the whole point on logic:
    these two are one function written twice and the check exists to say so."""
    assert _duplicated(_TWO_FUNCTIONS) > 0


def test_a_class_with_a_body_is_not_discounted():
    """Only a declaration. A class carrying methods is code, and skipping it would hide
    duplication behind a keyword."""
    with_logic = _TWO_FUNCTIONS.replace("def widen", "class A:\n    def widen").replace(
        "def narrow", "class B:\n    def narrow")
    assert _duplicated(with_logic) > 0
