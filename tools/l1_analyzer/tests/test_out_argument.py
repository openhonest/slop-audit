"""A value handed back through an out argument is still the state's value (L1.18b, C#).

`_d.Remove(k, out var v)` hands the stored value back through `v`. `Remove` is a mutating
method, so the reference reads as a write and stops there, and the value leaving through
the out argument is never followed. `_d` came back neutral and observe-only on a source
that branches on the removed value.

A rule watching the invocation's own value cannot see this: the invocation returns a
bool. The value goes out through the `declaration_expression` inside the argument, which
binds a local, and following a local is machinery this module already has.

C# is the only one of the nine that spells this. The vocabulary is empty elsewhere and
says so rather than being omitted.
"""

import pathlib
import tempfile

from l1_analyzer import state_bounds

_BRANCHES_ON_THE_OUT_VALUE = """class A {
  System.Collections.Generic.Dictionary<string,int> _d;
  int Q(string k) {
    if (_d.Remove(k, out var v)) { if (v > 3) { return 1; } return 2; }
    return 0;
  }
}
"""

_IGNORES_THE_OUT_VALUE = """class A {
  System.Collections.Generic.Dictionary<string,int> _d;
  int Q(string k) {
    if (_d.Remove(k, out var v)) { return 1; }
    return 0;
  }
}
"""


def _finding(src: str) -> dict:
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / "m.cs").write_text(src)
        r = state_bounds.classify(p, "csharp")
        return next((f for f in r["findings"] if f["state"].endswith("_d")), {})


def test_a_branch_on_the_out_value_is_a_decision_the_state_drives():
    f = _finding(_BRANCHES_ON_THE_OUT_VALUE)
    assert f, "the dictionary should be found"
    assert f["drives_decision"], "the removed value decides a branch and the state supplied it"


def test_an_out_value_nobody_reads_leaves_the_state_where_it_was():
    """The guard. Following the out argument must not turn every mutating call into a
    decision: if nothing reads the local, the state still only got written."""
    f = _finding(_IGNORES_THE_OUT_VALUE)
    assert f
    assert not f["drives_decision"]
