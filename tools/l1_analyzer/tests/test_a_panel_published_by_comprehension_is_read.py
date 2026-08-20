"""A panel published row by row through a comprehension is read like any other.

`_published_dict` recognised a returned dict literal and a dict assigned into a results
table. It did not recognise a dict COMPREHENSION whose value is a dict, which is how a
whole panel is published at once:

    return {f"L1.{i}": {"value": 0, "band": "n/a", "details": reason} for i in range(1, 9)}

That is eight published results in one statement, and the checker walked past all eight.
The shape is not hypothetical: it is exactly how `compute_git_indicators` refuses when git
cannot be read, and the zero it published there rendered as `0%` on the card for L1.1
through L1.8. The defect was found on 2026-08-19 by reading every exception handler in the
package by hand, which is the work this rule exists to save.

`_is_refusal_dict` already reads a comprehension, on the same reasoning and with the same
comment. Only the reader that decides WHAT IS PUBLISHED had the gap, so the checker had a
rule for the shape and no way to reach it.
"""

import pathlib
import tempfile
import textwrap

from l1_analyzer import vacuity

PANEL_WITH_A_FABRICATED_ZERO = textwrap.dedent('''
    def compute(repo):
        rows = read(repo)
        if not rows:
            return {f"L1.{i}": {"value": 0, "band": "n/a", "details": "nothing was read"}
                    for i in range(1, 9)}
        return {"value": len(rows)}
''')

PANEL_THAT_REFUSES_HONESTLY = textwrap.dedent('''
    def compute(repo):
        rows = read(repo)
        if not rows:
            return {f"L1.{i}": {"value": "n/a", "band": "n/a", "details": "nothing was read"}
                    for i in range(1, 9)}
        return {"value": len(rows)}
''')


def _findings(source: str) -> list[dict]:
    directory = pathlib.Path(tempfile.mkdtemp())
    (directory / "m.py").write_text(source)
    return vacuity.check(directory)["findings"]


def test_a_comprehension_carries_the_row_it_publishes():
    """The reader itself, asserted on the pure half so it needs no walk context: a panel
    comprehension carries the dict each of its rows is."""
    import ast

    returned = ast.parse(PANEL_WITH_A_FABRICATED_ZERO).body[0].body[-2].body[0].value
    assert isinstance(returned, ast.DictComp), "the fixture no longer publishes a panel"
    row = vacuity._panel_row(returned)
    assert row is not None, "a panel published by comprehension is not read at all"
    assert isinstance(row, ast.Dict)
    assert vacuity._panel_row(ast.parse("{'a': 1}").body[0].value) is not None
    assert vacuity._panel_row(ast.parse("[1, 2]").body[0].value) is None


def test_a_fabricated_zero_in_a_comprehension_is_convicted():
    fields = {f["field"] for f in _findings(PANEL_WITH_A_FABRICATED_ZERO)}
    assert "value" in fields, "eight published results in one statement, and none was read"


def test_an_honest_refusal_in_a_comprehension_is_not():
    """The rule must not simply convict every comprehension. This one publishes n/a in
    every field and says why, which is a refusal and not a measurement."""
    assert _findings(PANEL_THAT_REFUSES_HONESTLY) == []


def test_the_real_refusal_this_was_found_by_stays_clean():
    """`compute_git_indicators` is the function whose comprehension carried the defect. It
    refuses honestly now, so the checker reading comprehensions must leave it alone."""
    from l1_analyzer import indicators

    package = pathlib.Path(indicators.__file__).parent
    convicted = {(f["function"], f["field"]) for f in vacuity.check(package)["findings"]}
    assert ("compute_git_indicators", "value") not in convicted
