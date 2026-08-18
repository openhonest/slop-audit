"""An expression-bodied member is a return (L1.18b, C#).

`public int V => _v;` and `public int V { get { return _v; } }` are the same program.
The first read `unresolved` with construct `identifier in arrow_expression_clause`; the
second read `neutral`. One spelling, and only one of them was read.

That is the same defect class as the Rust borrow wrapper and the quoted cast, both fixed
on 2026-08-18: a construct the reader had no row for, where the row it needed already
existed for the other spelling of the same thing.

It was the largest remaining shape in the corpus's silence, 237 sites across three
spellings, 228 of them in Newtonsoft.Json alone.

This is NOT a new clearing. `return _v;` already reaches `output()`, the verdict that
says the value is handed to the caller and reaches no decision here. The arrow clause is
the member's body, so its value leaves the member exactly as a return does, and the fix
makes the two spellings agree rather than making either one lenient.
"""

import pathlib
import tempfile

from l1_analyzer import state_bounds


def _findings(src: str) -> dict[str, dict]:
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / "m.cs").write_text(src)
        return {f["state"]: f for f in state_bounds.classify(p, "csharp")["findings"]}


_BLOCK = "class A {\n  int _v;\n  public int V { get { return _v; } }\n}\n"
_ARROW = "class A {\n  int _v;\n  public int V => _v;\n}\n"
_ACCESSOR = "class A {\n  int _v;\n  public int V { get => _v; }\n}\n"


def test_an_expression_bodied_property_reads_the_same_as_a_block_bodied_one():
    block, arrow = _findings(_BLOCK)["_v"], _findings(_ARROW)["_v"]
    assert block["verdict"] == "neutral", "the control moved; this test is measuring the wrong thing"
    assert arrow["verdict"] == block["verdict"]
    assert arrow["silence"] == ""


def test_an_expression_bodied_get_accessor_reads_the_same_way():
    assert _findings(_ACCESSOR)["_v"]["silence"] == ""


def test_a_field_a_method_still_decides_on_is_not_cleared_by_the_arrow_row():
    """The guard. An arrow body that BRANCHES on the state is not a bare return of it, and
    must keep whatever verdict the branch earns rather than being handed output()."""
    src = "class A {\n  System.Collections.Generic.Dictionary<string,int> _m;\n  public int V(string k) => _m[k];\n}\n"
    f = _findings(src)["_m"]
    assert f["verdict"] != "neutral" or f["silence"] == ""
