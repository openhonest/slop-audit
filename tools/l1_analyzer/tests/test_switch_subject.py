"""A switch on a piece of state partitions it by its arms (L1.18b).

`switch (_state) { case A: ... case B: ... default: ... }` is the clearest discriminator
a language has: the value selects one arm and the arms are countable from the tree. It
came out as `identifier in switch_statement`, a construct with no rule, so a state whose
whole job is to select behaviour contributed no classes at all.

This one differs from the five spelling fixes before it. Those moved a state from silent
to read without changing what it was worth. This one produces COUNTED CLASSES, which is
what the cardinality distribution and any future D-tier bound are measured from.

The count is the arms, plus one when no default arm exists, because a subject matching
no case is an outcome too. Unordered: there is no value "just above" a case label, which
is the distinction the D tier rests on.
"""

import pathlib
import tempfile

import pytest
from l1_analyzer import state_bounds

_CSHARP = """class A {
  int _s;
  int Q() { switch (_s) { case 1: return 1; case 2: return 2; default: return 0; } }
}
"""

_CSHARP_NO_DEFAULT = """class A {
  int _s;
  int Q() { switch (_s) { case 1: return 1; case 2: return 2; } return 0; }
}
"""

_JAVA = """class A {
  int s;
  int q() { switch (s) { case 1: return 1; case 2: return 2; default: return 0; } }
}
"""

_CASES = {
    "csharp": ("m.cs", _CSHARP, "_s", 3),
    "csharp_no_default": ("m.cs", _CSHARP_NO_DEFAULT, "_s", 3),
    "java": ("M.java", _JAVA, "s", 3),
}


def _finding(lang: str) -> dict:
    filename, src, state, _ = _CASES[lang]
    real = "csharp" if lang.startswith("csharp") else lang
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / filename).write_text(src)
        r = state_bounds.classify(p, real)
        return next((f for f in r["findings"] if f["state"].endswith(state)), {})


@pytest.mark.parametrize("lang", sorted(_CASES))
def test_a_switch_subject_is_read_and_counted(lang):
    f = _finding(lang)
    assert f, "the state should be found"
    assert f["construct"] == "", f'still an unread construct: {f["construct"]!r}'
    assert f["partition"]["classes"] == _CASES[lang][3]
    assert f["partition"]["ordered"] is False
