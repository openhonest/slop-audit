"""The scorecard says what it holds, so the renderers can be told they read the wrong field.

`build_card` returned `dict[str, object]` and two renderers read thirty-eight fields off it.
Every read was an assumption. Nothing could say whether `culprits` was a list or `grade_pct`
a number, and twenty of those reads were indexing an `object` as far as the checker could
see. A field renamed in the builder and not in the Markdown renderer is a KeyError on the
line that prints it, on the run that publishes the measurement.

The fields were known the whole time: one return statement writes all thirty-eight.
"""

import ast
import pathlib
import typing

from l1_analyzer.card import CardModel


def _written():
    source = (pathlib.Path(__file__).resolve().parents[1] / "l1_analyzer" / "card.py").read_text()
    fn = next(n for n in ast.walk(ast.parse(source))
              if isinstance(n, ast.FunctionDef) and n.name == "build_card")
    rows = [{k.value for k in r.value.keys if isinstance(k, ast.Constant)}
            for r in ast.walk(fn) if isinstance(r, ast.Return) and isinstance(r.value, ast.Dict)]
    assert len(rows) == 1, f"{len(rows)} return dicts in build_card"
    return rows[0]


def test_the_declaration_holds_exactly_what_the_builder_writes():
    """Read from the builder rather than restated here, so the declaration cannot drift from
    the one place that fills it."""
    assert set(typing.get_type_hints(CardModel)) == _written()


def test_the_builder_says_it_returns_a_card():
    import inspect

    from l1_analyzer import card

    assert inspect.signature(card.build_card).return_annotation in ("CardModel", CardModel)


def test_both_renderers_say_they_read_a_card():
    """The two functions that print it. Either one reading a field the builder stopped
    writing is a KeyError on the run that publishes the measurement."""
    import inspect

    from l1_analyzer import card

    for renderer in (card.card_markdown, card.card_html):
        params = list(inspect.signature(renderer).parameters.values())
        assert params[0].annotation in ("CardModel", CardModel), renderer.__name__


def test_no_field_is_left_as_anything_at_all():
    anything = [k for k, v in typing.get_type_hints(CardModel).items() if v is object]
    assert anything == [], anything
