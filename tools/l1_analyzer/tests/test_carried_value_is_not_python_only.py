"""Why the carried-value rule is still Python-only, asserted rather than assumed.

`_drives_no_decision` is one line, `no reference sits in a test expression`, and it
already takes the language spec and delegates to `reads.in_test`, which is
vocabulary-driven and whose own docstring works through the JavaScript, TypeScript and C#
condition wrappers. It looks free to widen. It is not, and the dependency chain is the
finding this file records so the next attempt starts from it.

Tried on 2026-08-18 and put back:

  The rule is only sound behind `_selects_on_an_open_key`, which was Python-only too.
  Widening the rule and not the guard turned thirty-seven cross-language vectors red.

  Widening that guard needs the subscript spelling AND the method spelling, because six
  of the nine ask `d.get(k)` rather than `d[k]`, and a guard reading only subscripts
  cleared an open-key read that the vectors declare promiscuous.

  With both, the Ruby conditional-assignment cache still clears when it must not.

The guard now reads the vocabulary, which is the part of that work worth keeping.

These tests assert the CURRENT behaviour, which is why they read backwards. The two
assertions a future attempt has to satisfy are named in the docstrings below.
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
    """Current behaviour, and also the RIGHT answer: the vectors say this shape is
    promiscuous. A widening that clears it has widened the rule past its guard."""
    f = _finding(lang, state)
    assert f, "the field should be found"
    assert f["verdict"] == "promiscuous", f'{f["verdict"]}: the open key is what decides'


def test_the_python_path_still_clears_a_value_that_reaches_no_branch():
    """The rule itself still works where it runs, so what is gated is reach and not
    correctness."""
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
