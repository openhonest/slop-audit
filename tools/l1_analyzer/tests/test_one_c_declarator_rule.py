"""The C declarator-unwrapping rule is spelled once.

state_census carried a copy of `_c_declarator_name` with a note saying it was
"deliberately re-derived here rather than imported from state_bounds: the census is the
second reading, and a shared helper is a shared blind spot."

The two bodies were byte-identical. An independent second reading that agrees with the
first by being a copy of it is not independent: it carries the cost of two copies and
delivers none of the benefit, and the note is what stopped anyone asking. Independence
buys something when the two derivations differ. Here neither derives anything. Unwrapping
`init_declarator` to its `declarator` field is a fact about the C grammar, not a
judgement, so two copies of it cannot disagree honestly, only drift.

It lives in ts_nodes, which both modules already import their other grammar facts from.
"""

import pathlib
import re

import pytest
from l1_analyzer import state_census, state_enum, ts_nodes

_PKG = pathlib.Path(ts_nodes.__file__).parent


def test_the_rule_is_defined_once_in_the_package():
    defs = re.findall(r"^def _?c_declarator_name\(", "\n".join(p.read_text() for p in _PKG.glob("*.py")), re.MULTILINE)
    assert len(defs) == 1, f"{len(defs)} definitions of a grammar fact; copies can only drift"


def test_the_other_c_declarator_question_has_its_own_name():
    """dead_code_defs asks a DIFFERENT question of the same grammar: it descends through a
    function_declarator to reach the function's name, because L1.12 is enumerating
    definitions. It used to carry the same name as the state rule, which returns nothing for
    a function. One name over two rules is how a caller reaches for the wrong one and gets a
    plausible answer, so the names are asserted distinct rather than the bodies merged."""
    from l1_analyzer import dead_code_defs
    assert hasattr(dead_code_defs, "_c_declared_identifier")
    assert not hasattr(dead_code_defs, "_c_declarator_name")


@pytest.mark.parametrize("module", [state_census, state_enum])
def test_both_readers_ask_the_same_function(module):
    """Not merely that each has one: that they are the SAME object."""
    assert module._c_declarator_name is ts_nodes.c_declarator_name


def test_a_missing_declarator_names_nothing():
    """The absent case is a real case here: `_field` returns None for a declarator shape
    the grammar did not produce, and the answer must be no name rather than a crash."""
    assert ts_nodes.c_declarator_name(None) == ""
