"""The panel names its rows, so a reader asking for one that is not there is told.

It was `dict[str, object]` in the report and `dict[str, "L1Result | object"]` in the card,
and a union with `object` is `object`, so the second looked precise and said the same
nothing as the first. Two declarations of one shape, neither carrying a field.

Twenty-one indicator codes and six additions, every one produced by a function that already
declares what it returns. The keys were known the whole time. Thirty-five reads across the
card and the report were indexing an `object` as far as anything could tell.

Keyed by the indicator's published code, so the functional form is the only one that spells
it: `L1.1` is not an identifier.
"""

import typing

from l1_analyzer import indicators
from l1_analyzer.panel import Panel
from l1_analyzer.pytest_trace import L1Result


def _codes():
    import inspect
    import re

    return set(re.findall(r'"(L1\.[0-9]+[a-z]?)"', inspect.getsource(indicators)))


def test_every_indicator_code_is_a_row():
    """Read from the producer rather than restated here. A code added there and forgotten
    here is exactly the drift this file objects to."""
    missing = _codes() - set(typing.get_type_hints(Panel))
    assert missing == set(), missing


def test_every_row_the_builder_writes_is_a_row_the_panel_names():
    """The other direction, and the one that was wrong. `compute_source_indicators` writes
    the language, the path cover, the thread surface and the absolute-path scan alongside
    the indicator codes, and the panel named none of them. It declared its own result as a
    table of indicator results while putting five other shapes in it."""
    import ast
    import inspect

    from l1_analyzer import indicators

    fn = next(n for n in ast.walk(ast.parse(inspect.getsource(indicators)))
              if isinstance(n, ast.FunctionDef) and n.name == "compute_source_indicators")
    written = {t.slice.value for n in ast.walk(fn) if isinstance(n, ast.Assign)
               for t in n.targets
               if isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)}
    written |= {k.value for n in ast.walk(fn) if isinstance(n, ast.Dict)
                for k in n.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    assert written, "the builder no longer writes rows by name"
    assert written <= set(typing.get_type_hints(Panel)), written - set(typing.get_type_hints(Panel))


def test_the_ordinary_rows_are_indicator_results():
    hints = typing.get_type_hints(Panel)
    assert hints["L1.1"] is L1Result
    assert hints["L1.17"] is L1Result


def test_the_rows_that_are_not_indicator_results_say_what_they_are():
    """Six rows carry another shape, and each is produced by a function that already
    declares it. Naming them as their own shapes is what stops a reader treating a sweep or
    a state reading as a band and a value.

    L1.21 was the sixth, and it took writing this down to see it. It looked like an ordinary
    indicator row and was declared as one, while nine fields went out on every run and the
    card read one of them. It is a band and a value and six readings that say what the share
    left out."""
    hints = typing.get_type_hints(Panel)
    for row in ("L1.18b", "coverage_proofs", "honest_code", "race",
                "interleaving_robustness", "proofs"):
        assert row in hints, row
        assert hints[row] is not L1Result, row


def test_no_row_is_left_as_anything_at_all():
    """The declaration that says nothing is the one this replaces, so none of its rows may
    be it."""
    anything = [k for k, v in typing.get_type_hints(Panel).items() if v is object]
    assert anything == [], anything


def test_both_readers_share_the_one_declaration():
    from l1_analyzer import card, report

    assert card.Panel is Panel
    assert report.Panel is Panel
