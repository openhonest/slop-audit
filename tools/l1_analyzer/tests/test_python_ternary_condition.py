"""Python's ternary condition is read, the same as every other language's.

Six languages gained the ternary on 2026-08-18 by adding the node type to `branch_types`,
because each names a `condition` field. Python was left out and the gap recorded: its
`conditional_expression` carries NO named fields at all, so the condition cannot be read
by the key the other six use, and adding the node type would have made the reader take
the consequence FOR the condition.

`X if C else Y` puts the condition second among the named children, which is neither the
field form nor the first-named-child form `bare_condition` already had for Go. It needs
an index, and the index is declared per language rather than assumed.

`if self.flag:` is a two-class split. `1 if self.flag else 0` is the same split written
differently, and was silent.
"""

import pathlib
import tempfile

from l1_analyzer import state_bounds


def _classes(body: str) -> int:
    src = ("class S:\n"
           "    def __init__(self):\n"
           "        self.flag = False\n"
           "    def set(self, v):\n"
           "        self.flag = v\n"
           f"    def q(self):\n{body}")
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / "m.py").write_text(src)
        r = state_bounds.classify(p, "python")
        f = next((x for x in r["findings"] if x["state"].endswith("flag")), {})
    assert f, "the attribute should be found"
    return f["partition"]["classes"]


def test_a_ternary_condition_reads_like_an_if():
    if_form = _classes("        if self.flag:\n            return 1\n        return 0\n")
    ternary = _classes("        return 1 if self.flag else 0\n")
    assert if_form == 2, "the control moved; this test measures the wrong thing"
    assert ternary == if_form


def test_an_arm_is_not_read_as_the_condition():
    """The guard that the index earns. Python puts the CONSEQUENCE first, so an
    off-by-one here reads the returned value as the thing being tested."""
    src = ("class S:\n"
           "    def __init__(self):\n"
           "        self.v = 0\n"
           "    def set(self, x):\n"
           "        self.v = x\n"
           "    def q(self, c):\n"
           "        return self.v if c else 0\n")
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / "m.py").write_text(src)
        r = state_bounds.classify(p, "python")
        f = next((x for x in r["findings"] if x["state"].endswith(".v")), {})
    assert f
    assert f["partition"].get("key") != "truthy", "the consequence is not the condition"
