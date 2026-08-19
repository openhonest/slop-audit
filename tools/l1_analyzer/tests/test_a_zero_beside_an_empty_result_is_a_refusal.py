"""A count of zero beside an empty result and an explanation is a refusal, not a measurement.

slop-audit-1ae, diagnosed 2026-08-18 and closed 2026-08-19.

`_is_refusal_dict` acquits a dict whose every field refuses, explains, or is an empty
shell. A numeric zero is none of those, so an honest refusal carrying `"attempted": 0`
beside its prose read as a fabricated affirmative. Four such dicts exist in this package
and the check convicted all four.

The discriminator is the EMPTY RESULT. An honest refusal shows the result it did not
produce: `{"retained": [], "attempted": 0, "detail": "..."}` says here is nothing, here is
how much work produced it, here is why. The half-repair this check must keep convicting
shows no such thing: `{"value": 0.0, "band": "n/a"}` publishes a measured-looking zero
beside a refusal and has no empty collection anywhere, because it never had a result to
be empty.

Prose alone is not enough, and that is the case that would have broken it. A dict reading
`{"value": 0.0, "band": "n/a", "details": "coverage not measured"}` carries a sentence and
still fabricates the zero. Both signals are required.
"""

import ast
import textwrap

from l1_analyzer import vacuity


def _dict_in(source: str) -> tuple[ast.expr, ast.AST]:
    tree = ast.parse(textwrap.dedent(source))
    scope = tree.body[0]
    for node in ast.walk(scope):
        if isinstance(node, ast.Dict):
            return node, scope
    raise AssertionError("no dict in the source")


def test_a_zero_beside_an_empty_result_and_prose_is_a_refusal():
    node, scope = _dict_in('''
        def f(ceiling):
            return {"retained": [], "attempted": 0, "modules": 0,
                    "detail": f"attempted nothing: the ceiling is {ceiling}"}
    ''')
    assert vacuity._is_refusal_dict(node, scope)


def test_a_fabricated_zero_with_no_empty_result_is_still_convicted():
    """The half-repair. It publishes a measured-looking zero beside a refusal and has no
    empty collection anywhere, because it never had a result to be empty."""
    node, scope = _dict_in('''
        def f():
            return {"value": 0.0, "band": "n/a"}
    ''')
    assert not vacuity._is_refusal_dict(node, scope)


def test_prose_alone_does_not_excuse_a_fabricated_zero():
    """The case that would have broken a prose-only rule."""
    node, scope = _dict_in('''
        def f():
            return {"value": 0.0, "band": "n/a", "details": "coverage was not measured"}
    ''')
    assert not vacuity._is_refusal_dict(node, scope)


def test_an_empty_result_alone_does_not_excuse_a_zero():
    """No explanation means a reader cannot tell a refusal from a real count of none."""
    node, scope = _dict_in('''
        def f():
            return {"findings": [], "count": 0}
    ''')
    assert not vacuity._is_refusal_dict(node, scope)


def test_a_nonzero_number_is_never_part_of_a_refusal_shape():
    """Only zero. A refusal that reports having done three of something is asserting."""
    node, scope = _dict_in('''
        def f():
            return {"retained": [], "attempted": 3, "detail": "a sentence explaining it"}
    ''')
    assert not vacuity._is_refusal_dict(node, scope)
