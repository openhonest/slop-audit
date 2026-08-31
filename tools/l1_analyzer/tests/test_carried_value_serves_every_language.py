"""The carried-value rule serves all nine languages, and the guard that makes it sound too.

`_drives_no_decision` is one line, `no reference sits in a test expression`, and it takes
the language spec and delegates to `reads.in_test`, which is vocabulary-driven. It looked
free to widen and it was not. This file was the record of why, written after an attempt on
2026-08-18 was put back, and it now records the three things that had to be true instead.

The rule is only sound behind `_selects_on_an_open_key`. Without that guard a map read by an
unbounded key and handed straight back clears, and the vectors declare that shape
promiscuous. Three things were wrong with the guard and each was found by the assertion that
caught it.

One: the guard read Python's node types directly, so widening the rule and not the guard
turned thirty-seven cross-language vectors red. Fixed 2026-08-18.

Two: it read only the SUBSCRIPT spelling of a keyed read. Six of the nine ask `d.get(k)`
instead, and the nested-call form of that was added the same day. The FLAT-call form was
not, so Java and Ruby hang the receiver, the method and the arguments off one node that the
loop never walked, and Java's `d.get(k)` went unseen. Fixed 2026-08-31.

Three: it counted a conditional assignment as a store. `@cache[k] ||= compute(k)` reads what
is at the key to decide whether to write there, so the answer depends on the key in exactly
the way the guard exists to catch. Counting it as a store cleared Ruby's commonest
memoization shape with no premise checked at all. Fixed 2026-08-31, and the vocabulary
already named those operators for every language that has them.

One more thing had to NOT change. The write-only accumulator rule is exempt from that guard
by construction: it clears a shape where every reference is a write, and a write at an open
key does not make the answer depend on the key. Putting the guard in front of both turned
five languages promiscuous on a per-key tally the vectors declare neutral.
"""

import pathlib
import tempfile

import pytest
from l1_analyzer import state_bounds

# A map read by an OPEN key and handed straight back: unbounded reach, no reference in a
# test. The cross-language vector `open-key-read-returned` declares this promiscuous, and
# that vector is the assertion a widening has to satisfy.
_CASES = {
    "csharp": ("m.cs", """class A {
  System.Collections.Generic.Dictionary<string,int> _d = new System.Collections.Generic.Dictionary<string,int>();
  int Get(string k) { return _d[k]; }
  void Put(string k, int v) { _d[k] = v; }
}
"""),
    "java": ("M.java", """class A {
  java.util.Map<String,Integer> d = new java.util.HashMap<>();
  Integer get(String k) { return d.get(k); }
  void put(String k, Integer v) { d.put(k, v); }
}
"""),
}


def _finding(lang: str, state: str) -> dict:
    filename, src = _CASES[lang]
    with tempfile.TemporaryDirectory() as t:
        p = pathlib.Path(t)
        (p / filename).write_text(src)
        r = state_bounds.classify(p, lang)
        return next((f for f in r["findings"] if f["state"].endswith(state)), {})


@pytest.mark.parametrize("lang,state", [("csharp", "_d"), ("java", "d")])
def test_an_open_key_read_returned_stays_flagged_outside_python(lang, state):
    """The assertion the widening had to satisfy, and it still holds. The vectors say this
    shape is promiscuous, and a widening that clears it has widened the rule past its guard.

    Java is here because it is the language that exposed the flat-call gap: its `d.get(k)`
    is one node where the guard was walking two."""
    f = _finding(lang, state)
    assert f, "the field should be found"
    assert f["verdict"] == "promiscuous", f'{f["verdict"]}: the open key is what decides'


def test_the_python_path_still_clears_a_value_that_reaches_no_branch():
    """The rule where it always ran, unchanged by the widening."""
    src = ("class A:\n"
           "    def __init__(self):\n"
           "        self.log = []\n"
           "    def add(self, s):\n"
           "        self.log.append(s)\n"
           "    def all(self):\n"
           "        return self.log\n")
    with tempfile.TemporaryDirectory() as t:
        p = pathlib.Path(t)
        (p / "m.py").write_text(src)
        r = state_bounds.classify(p, "python")
        f = next((x for x in r["findings"] if x["state"].endswith("log")), {})
    assert f
    assert f["verdict"] == "neutral"
