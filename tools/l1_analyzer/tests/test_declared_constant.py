"""A field the language declares immutable has a one-value domain (L1.18b).

`private static final int PEEKED_BEGIN_OBJECT = 11;` cannot be reassigned. Neither can
an enum member. Both were enumerated as state, both came back `unresolved`, and the
construct blamed was `identifier in switch_label` -- the place they are READ, in a case
label, which is not where the problem was. Nineteen sites in gson alone.

L1.18 has known this since it was written: `LANG_CFG` carries `immutable_modifiers`,
`final` for Java and `const`/`readonly` for C#, and mutable_state.py reads it. L1.18b
carries its own vocabulary and had no notion of immutability outside Python, where a
separate rule recognises immutable CONSTRUCTIONS. Two readers of one property, and only
one of them knew.

That gap also forced the language-identity check `sp is LANG_SPEC["python"]` in
`_finding`, which is the shape this project criticises elsewhere: a language conditional
welded into shared code instead of a row in the table. Declaring the modifiers per
language removes it.

A constant is NEUTRAL with one class. Not silent: we know exactly what it reaches,
which is one value, and one value costs one test.
"""

import pathlib
import tempfile

import pytest

from l1_analyzer import state_bounds

_JAVA = """class A {
  private static final int PEEKED = 11;
  int q(int p) { switch (p) { case PEEKED: return 1; default: return 0; } }
}
"""

# The mutable twin SWITCHES ON the field, so it earns three classes. The first draft of
# this guard only returned the field, which already read as one class, so it could not
# tell the constant rule firing from the field being narrow anyway.
_JAVA_MUTABLE = """class A {
  private static int peeked = 11;
  int q() { switch (peeked) { case 1: return 1; case 2: return 2; default: return 0; } }
  void bump() { peeked = peeked + 1; }
}
"""

_CSHARP = """class A {
  private const int Peeked = 11;
  int Q(int p) { switch (p) { case Peeked: return 1; default: return 0; } }
}
"""

_CASES = {"java": ("M.java", _JAVA, "PEEKED"), "csharp": ("m.cs", _CSHARP, "Peeked")}


def _finding(lang: str, filename: str, src: str, state: str) -> dict:
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / filename).write_text(src)
        r = state_bounds.classify(p, lang)
        return next((f for f in r["findings"] if f["state"].endswith(state)), {})


@pytest.mark.parametrize("lang", sorted(_CASES))
def test_a_declared_constant_is_neutral_with_one_class(lang):
    filename, src, state = _CASES[lang]
    f = _finding(lang, filename, src, state)
    assert f, "the constant should still be enumerated and reported"
    assert f["verdict"] == "neutral", f'{f["verdict"]}, silence {f["silence"]!r}'
    assert f["partition"]["classes"] == 1


def test_a_field_without_the_modifier_is_not_treated_as_constant():
    """The guard. Drop the modifier and the field is ordinary mutable state again, so the
    rule reads the declaration rather than assuming a capitalised name is a constant."""
    f = _finding("java", "M.java", _JAVA_MUTABLE, "peeked")
    assert f
    assert f["partition"]["classes"] == 3, "a switch on the mutable field cuts three classes"
