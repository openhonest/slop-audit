"""The dead-code detector cannot see a TypedDict field, and that is why it kept its own.

`Definition.name_byte` was declared in `dead_code_defs.py`, written once, and read
nowhere. Its comment claimed a live role, "byte offset of the name token, so its own site
is not a reference", and that job is done elsewhere and differently: `_referenced_from`
excludes the whole definition SPAN using start_byte and end_byte, which subsumes the name
token. The field was superseded and the comment outlived it.

L1.12 could not report it. `dead_code_defs._python` walks `root.named_children` only and
never descends into a class body, so a TypedDict field is outside its declaration model
entirely. The detector was blind to the exact shape its own dead field took, which is why
a sweep by hand found it and the tool never would have.

This test measures the blind spot rather than asserting it away. Closing it is not a
matter of walking deeper: a TypedDict field is referenced as `d["field"]`, a STRING
subscript and not an identifier, so admitting the declarations without a rule for that
reference form would report every field in every TypedDict as dead. The reference rule
has to come first.
"""

import pathlib
import tempfile

from l1_analyzer import dead_code

_TYPED_DICT = '''from typing import TypedDict


class Row(TypedDict):
    used: int
    never_read: int


def make() -> Row:
    return Row(used=1, never_read=2)


def read(r: Row) -> int:
    return r["used"]


print(read(make()))
'''


def test_a_typed_dict_field_is_not_reported_either_way():
    """Neither `used` nor `never_read` appears, because the walk never enters the class
    body. The point is that `never_read` IS dead and the detector says nothing."""
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / "m.py").write_text(_TYPED_DICT)
        r = dead_code.analyze(p, "python")
    names = {f["name"] for f in (r.get("findings") or [])}
    assert "never_read" not in names, "behaviour changed: the blind spot may be closed"
    assert "used" not in names


def test_the_detector_still_sees_a_module_level_definition_in_the_same_file():
    """The control. The walk works; it just does not go down."""
    src = _TYPED_DICT + "\n\ndef orphan():\n    return 1\n"
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / "m.py").write_text(src)
        r = dead_code.analyze(p, "python")
    assert "orphan" in {f["name"] for f in (r.get("findings") or [])}


def test_the_superseded_field_is_gone():
    source = (pathlib.Path(dead_code.__file__).parent / "dead_code_defs.py").read_text()
    assert "name_byte" not in source, "a field written once and read nowhere"
