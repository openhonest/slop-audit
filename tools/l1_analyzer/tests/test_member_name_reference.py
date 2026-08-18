"""Reading a field off another receiver is a reference to that field (L1.18b).

The largest single source of silence in the corpus. `unmodeled_construct` accounts for
1,174 of 1,759 silent states, and its top two shapes were an identifier in a C# member
access, 173 times, and an identifier in a Java field access, 142.

The shape is ordinary. In the three languages whose class state is keyed by a bare
identifier -- C, C# and Java -- a field is enumerated as `v`, and a reference like
`other.v = s` puts that identifier in the NAME half of a member access. Every dispatch
row was written for the case where the state is the RECEIVER (`v.something`), so the
name half fell off the bottom and was reported as a construct nobody had taught.

The rule: when the reference is the name half, the member access IS the reference. A
write to it is a write; anything else flows on exactly as a bare read would. Nothing
here is a new judgement about what a field access means; it is the existing judgement
reached through one more node.

Measured before this file: RestSharp alone held 22 of these.
"""

import pathlib
import tempfile

from l1_analyzer import state_bounds

_CSHARP = """class A {
  public string V { get; set; }
  void M(A other, string s) { other.V = s; }
  string R(A other) { if (other.V != null) { return "y"; } return "n"; }
}
"""

_JAVA = """class A {
  String v;
  void m(A o, String s) { o.v = s; }
  String r(A o) { if (o.v != null) { return "y"; } return "n"; }
}
"""

_C = """struct A { int v; };
void m(struct A *o, int s) { o->v = s; }
int r(struct A *o) { if (o->v) { return 1; } return 0; }
"""

_SRC = {
    "csharp": ("m.cs", _CSHARP),
    "java": ("M.java", _JAVA),
    "c": ("m.c", _C),
}


def _finding(lang: str, state_ends: str) -> dict:
    name, src = _SRC[lang]
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / name).write_text(src)
        r = state_bounds.classify(p, lang)
        return next((f for f in r["findings"] if f["state"].endswith(state_ends)), {})


def test_a_csharp_property_read_off_another_receiver_is_not_silent():
    f = _finding("csharp", "V")
    assert f, "no finding for the property at all"
    assert f["silence"] == "", f'still silent as {f["construct"]!r}'


def test_a_java_field_read_off_another_receiver_is_not_silent():
    f = _finding("java", "v")
    assert f, "no finding for the field at all"
    assert f["silence"] == "", f'still silent as {f["construct"]!r}'


def test_a_c_struct_field_read_off_a_pointer_is_not_silent():
    f = _finding("c", "v")
    assert f, "no finding for the field at all"
    assert f["silence"] == "", f'still silent as {f["construct"]!r}'
