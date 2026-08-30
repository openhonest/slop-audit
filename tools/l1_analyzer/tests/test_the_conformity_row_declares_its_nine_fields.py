"""L1.21's panel row says it carries nine fields, because it carries nine.

It was declared `L1Result`, which is a value, a band and a sentence. Six more went out with
it on every run: the findings, the clauses nobody decided, the declared exceptions, the
boundary declarations, the unreadable file count and the count of blocks in another
language. The card reads the findings off it, and as far as anything could tell it was
reading a field the row had said it does not have.

Every one of the six is the reading a reader needs to see what the share left out, which is
the whole argument for publishing a share at all.
"""

import typing

from l1_analyzer.honest_code import ConformityRow
from l1_analyzer.pytest_trace import L1Result

_FIELDS = typing.get_type_hints(ConformityRow)


def test_the_row_is_an_indicator_result_and_six_fields_more():
    assert set(typing.get_type_hints(L1Result)) < set(_FIELDS)


def test_the_row_carries_what_the_share_left_out():
    for field in ("findings", "undecided", "allowed", "declared", "unreadable_files",
                  "unexamined"):
        assert field in _FIELDS, field


def test_the_panel_holds_the_conformity_row_rather_than_a_bare_result():
    """Where the card reads it. The panel said L1Result, so the card's read of `findings`
    had nothing behind it."""
    from l1_analyzer.panel import Panel

    assert typing.get_type_hints(Panel)["honest_code"] is ConformityRow


def test_both_returns_write_exactly_the_declared_fields():
    """Read from the function rather than restated here. The refusal path and the measured
    path each build the row, and a field added to one and not the other is how the card
    comes to read something that is sometimes there."""
    import ast
    import pathlib

    source = (pathlib.Path(__file__).resolve().parents[1]
              / "l1_analyzer" / "honest_code.py").read_text()
    fn = next(n for n in ast.walk(ast.parse(source))
              if isinstance(n, ast.FunctionDef) and n.name == "analyze")
    rows = [{k.value for k in r.value.keys if isinstance(k, ast.Constant)}
            for r in ast.walk(fn)
            if isinstance(r, ast.Return) and isinstance(r.value, ast.Dict)]
    assert rows, "analyze no longer returns a dict literal"
    for written in rows:
        assert written == set(_FIELDS), written
