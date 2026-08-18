"""A cast passes the value through; sizeof does not read it (L1.18b, C).

Two shapes from libuv, the last pinned repository still above the silence floor.

A CAST. C# lists `cast_expression` in its passthrough types, so `(object)x` flows on.
C did not, so `(uv_handle_t*) &handle->field` stopped at the cast and was reported as a
construct with no rule. The same two-readers-disagree shape as the Rust borrow wrapper:
one language's table knew and the other's did not, for the same construct meaning the
same thing.

SIZEOF. `sizeof(state)` does not read the value at all. It is a compile-time question
about the TYPE, so the state reaches no decision through it and costs no test. Reporting
it as unread said we could not tell, when there is nothing there to tell.
"""

import pathlib
import tempfile

from l1_analyzer import state_bounds


def _finding(src: str, state: str) -> dict:
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / "m.c").write_text(src)
        r = state_bounds.classify(p, "c")
        return next((f for f in r["findings"] if f["state"].endswith(state)), {})


def test_a_cast_passes_the_state_through_to_what_reads_it():
    src = ("struct S { int flag; };\n"
           "static struct S g;\n"
           "int q(void) { if ((int) g.flag) { return 1; } return 0; }\n")
    f = _finding(src, "flag")
    assert f, "the field should be found"
    assert f["construct"] == "", f'still unread as {f["construct"]!r}'


def test_sizeof_is_not_a_read_of_the_value():
    src = ("struct S { int flag; };\n"
           "static struct S g;\n"
           "unsigned q(void) { return sizeof(g.flag); }\n")
    f = _finding(src, "flag")
    assert f, "the field should be found"
    assert f["construct"] == "", f'still unread as {f["construct"]!r}'
