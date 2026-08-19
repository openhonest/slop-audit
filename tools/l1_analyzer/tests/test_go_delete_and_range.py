"""Go's key removal and map iteration are read, not reported as unread constructs.

Two shapes verified on 2026-08-17 and left standing:

    delete(s.m, k)        the container sits in an argument slot of a BUILTIN absent from
                          Go's extra_bounded, so the plainest key removal in the language
                          read unresolved with reason unmodeled_callee.

    for k := range s.m    iterating a state map had no row anywhere and read unresolved
                          with construct `selector_expression in range_clause`.

Neither is a false green: both fail closed, which is why they were reported rather than
patched at the time. Both inflate Go's silence index, and silence is what this instrument
spends its credibility on: a reader told the analyzer could not read `delete` will believe
it cannot read Go.

`delete` removes a key and returns nothing, so the container takes a WRITE. Ranging over a
map reads every key and value it holds, which is the container flowing into the loop, and
the loop is where the question of what it decides continues.
"""

import pathlib
import tempfile

from l1_analyzer import state_bounds

_HEAD = """package p

type S struct {
	m map[string]int
}

"""


def _finding(body: str) -> dict:
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / "m.go").write_text(_HEAD + body)
        r = state_bounds.classify(p, "go")
        return next((f for f in r["findings"] if f["state"].endswith("m")), {})


def test_delete_is_a_write_not_an_unmodeled_callee():
    f = _finding("func (s *S) Drop(k string) {\n\tdelete(s.m, k)\n}\n")
    assert f, "the map should be found"
    assert f["silence"] != "unmodeled_callee", "delete is a builtin, not an unknown callee"
    assert f["construct"] == "", f'unread as {f["construct"]!r}'


def test_ranging_a_state_map_is_not_an_unread_construct():
    f = _finding("func (s *S) Total() int {\n\tn := 0\n\tfor k := range s.m {\n\t\t_ = k\n\t\tn++\n\t}\n\treturn n\n}\n")
    assert f, "the map should be found"
    assert f["construct"] == "", f'unread as {f["construct"]!r}'


def test_an_unknown_callee_is_still_an_unknown_callee():
    """The guard. Teaching the reader `delete` must not teach it every function."""
    f = _finding("func (s *S) Hand() {\n\tmystery(s.m)\n}\n")
    assert f
    assert f["verdict"] == "unresolved", "a callee nobody modelled is still unread"
