"""A TypedDict spelled as a call is a type declaration, not state.

`class Panel(TypedDict)` is not state and nothing counted it. `Panel = TypedDict("Panel",
{...})` is the same declaration, and the reader counted it as one module-level mutable
value, because it read the assignment and not what was assigned.

The two spellings are not interchangeable at the author's option. A key that is not an
identifier can only be written the second way, and the indicator codes this repository
publishes are `L1.1` and `L1.18b`. So the rule as it stood said: declare your shape, unless
your keys have dots in them, in which case you have promiscuous state.

NamedTuple, NewType and TypeVar carry the same shape and the same answer.
"""

import pathlib

import pytest
from l1_analyzer import state_bounds

_DECLARATIONS = [
    ('Panel = TypedDict("Panel", {"L1.1": int}, total=False)', "TypedDict"),
    ('Row = NamedTuple("Row", [("a", int)])', "NamedTuple"),
    ('Code = NewType("Code", str)', "NewType"),
    ('T = TypeVar("T")', "TypeVar"),
]


def _states(tmp_path, source):
    (tmp_path / "m.py").write_text(
        "from typing import NamedTuple, NewType, TypedDict, TypeVar\n\n" + source + "\n")
    return state_bounds.classify(tmp_path, "python")["findings"]


@pytest.mark.parametrize(("source", "name"), _DECLARATIONS)
def test_a_type_built_by_a_call_is_not_state(tmp_path, source, name):
    assert _states(tmp_path, source) == [], name


def test_the_class_form_of_the_same_declaration_is_not_state_either(tmp_path):
    """The control. If the class form were counted too this would be a rule about type
    declarations rather than a gap between two spellings of one."""
    assert _states(tmp_path, "class Panel(TypedDict):\n    a: int\n") == []


def test_an_ordinary_module_level_value_is_still_read(tmp_path):
    """The rule this must not switch off. A mutable module-level value is what the
    indicator exists to find, and a call on the right-hand side is most of them."""
    assert _states(tmp_path, "CACHE = dict()\n") != []


def test_this_repository_declares_its_panel_and_is_not_charged_for_it():
    """Where it was found. The panel is twenty-seven rows keyed by indicator code, and
    `L1.1` is not an identifier, so the functional form is the only one that spells it."""
    repo = pathlib.Path(__file__).resolve().parents[1]
    charged = [f for f in state_bounds.classify(repo, "python")["findings"]
               if f["file"].endswith("panel.py")]
    assert charged == [], charged
