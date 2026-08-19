"""Ruby spells an append two ways and both are read.

`slop-audit-8j8` says the `"<<"` entry in `_RUBY_MUTATING` can never match, because Ruby
parses `@rows << x` as a `binary` node and no method name is ever `"<<"`. That is true of
the OPERATOR form and not of the other one: `@rows.<<(x)` is legal Ruby and parses as a
call whose method node is an `operator` wrapping `<<`, so the entry is reachable.

Both spellings are read, and by different vocabularies:

    @rows << x      binary node    write_in_place_ops {"binary": ("<<",)}
    @rows.<<(x)     call node      mutating, the "<<" entry

Neither is decoration and neither can be removed without losing a spelling. This file is
the assertion that says so, because the entry looks dead from the operator form alone and
the next reader will reach the same conclusion the bead did.
"""

import pathlib
import tempfile

from l1_analyzer import state_bounds

_BASE = """class A
  def initialize
    @rows = []
  end
  def add(x)
    %s
  end
  def q
    if @rows.size > 3
      1
    else
      0
    end
  end
end
"""


def _classes(statement: str) -> int:
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / "m.rb").write_text(_BASE % statement)
        r = state_bounds.classify(p, "ruby")
        f = next((x for x in r["findings"] if x["state"].endswith("rows")), {})
    assert f, "the collection should be found"
    return f["partition"]["classes"]


def test_both_spellings_of_an_append_read_the_same():
    assert _classes("@rows << x") == _classes("@rows.<<(x)") == 2


def test_the_operator_form_is_declared_where_it_can_fire():
    ops = state_bounds.LANG_SPEC["ruby"]["write_in_place_ops"]
    assert "<<" in ops.get("binary", ()), "the binary spelling needs the in-place vocabulary"


def test_the_method_form_is_declared_where_it_can_fire():
    """The entry the bead calls dead. `@rows.<<(x)` is a call and its method name is
    `<<`, so removing this would lose that spelling silently."""
    assert "<<" in state_bounds.LANG_SPEC["ruby"]["mutating"]
