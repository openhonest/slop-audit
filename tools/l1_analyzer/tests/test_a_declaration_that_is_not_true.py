"""A boundary declaration on a function that is not one.

The decorator says "this function is an edge". Clause 4 reads it and withholds the finding
it would otherwise report, which is right when the function really does obtain something.
On a function that touches nothing outside the process it is a false statement, and nothing
reported it: the clause never fires on such a function anyway, so the declaration silences
nothing and sat there looking like a fact.

It cannot be told from a stamp in general, and this package's own docstring says so. It can
be told in one case, and that case is computable: a function under the decorator that
reaches nothing outside the process is a suppression by construction. A peer maintaining
the write hook had built a detector that counted markers rather than markers that withheld
anything, found it wrong three times in four, and removed it. This counts something true.
"""

import ast

from l1_analyzer import honest_code_python_rules as python_rules


def _findings(source: str) -> list[dict]:
    return python_rules.io_below_the_boundary({
        "path": "m.py", "language": "python", "text": source,
        "tree": ast.parse(source), "readable": True, "unreadable_reason": ""}) or []


DECORATOR = "from l1_analyzer.boundary import boundary\n\n\n"


def test_a_declaration_on_a_function_that_obtains_nothing_is_reported():
    found = _findings(DECORATOR + "@boundary\ndef edge(n):\n    return n + 1\n\n\n"
                      "def run(n):\n    return edge(n)\n")
    assert [f["symbol"] for f in found] == ["edge"], found
    assert "no I/O" in found[0]["detail"] or "obtains nothing" in found[0]["detail"]


def test_a_declaration_on_a_function_that_does_obtain_something_is_not_reported():
    """The other direction, and the one that matters: a true declaration must stay silent
    or the rule punishes the thing it asks for."""
    found = _findings(DECORATOR + "@boundary\ndef edge(path):\n    return path.read_text()\n\n\n"
                      "def run(path):\n    return edge(path)\n")
    assert [f for f in found if f["withheld_by"] == ""] == [], found


def test_an_undeclared_function_that_obtains_nothing_is_not_reported():
    """Only a declaration can be false. A plain function claiming nothing cannot be."""
    assert _findings("def edge(n):\n    return n + 1\n\n\n"
                     "def run(n):\n    return edge(n)\n") == []


def test_a_declaration_on_an_uncalled_function_is_still_reported():
    """Clause 4 leaves an uncalled function alone, because it may be the entry point. That
    reasoning does not cover a false claim: an entry point that obtains nothing is still
    not an edge."""
    found = _findings(DECORATOR + "@boundary\ndef edge(n):\n    return n + 1\n")
    assert [f["symbol"] for f in found] == ["edge"], found


def test_the_report_says_what_to_do_about_it():
    found = _findings(DECORATOR + "@boundary\ndef edge(n):\n    return n + 1\n")
    assert found[0]["instead"].strip()
