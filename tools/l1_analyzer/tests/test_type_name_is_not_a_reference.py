"""A name in type position is not a reference to state that shares it (L1.18b).

`private static readonly Encoding Encoding = null;` names a type and then a field, both
`Encoding`. The classifier collects references by matching identifier TEXT, so the type
occurrence was collected as a reference to the field, and no dispatch row covers an
identifier sitting in a declaration's type slot. It came out as `identifier in
variable_declaration`, which reads as a missing rule when the truth is that the
reference should never have been collected.

`_bound_to` already drops two kinds of matching name that denote something else: one
under an import path, and one a nearer parameter binds. This is the third.

Measured before the fix: 47 sites of `identifier in variable_declaration`, 46 of
`identifier in property_declaration` and 33 of `identifier in nullable_type` across the
pinned corpus, 84 of them in Newtonsoft.Json alone.
"""

import pathlib
import tempfile

from l1_analyzer import state_bounds


def _findings(lang: str, filename: str, src: str) -> dict[str, dict]:
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / filename).write_text(src)
        return {f["state"]: f for f in state_bounds.classify(p, lang)["findings"]}


def test_a_csharp_type_sharing_a_field_name_is_not_a_reference():
    src = ("class A {\n"
           "  private static readonly Encoding Encoding = null;\n"
           "  public bool Q() { return Encoding != null; }\n"
           "}\n")
    f = _findings("csharp", "m.cs", src).get("Encoding")
    assert f, "the field should still be found"
    assert f["silence"] == "", f'still silent as {f["construct"]!r}'


def test_a_java_type_sharing_a_field_name_is_not_a_reference():
    src = ("class A {\n"
           "  private Strictness Strictness = null;\n"
           "  boolean q() { return Strictness != null; }\n"
           "}\n")
    f = _findings("java", "M.java", src).get("Strictness")
    assert f, "the field should still be found"
    assert f["silence"] == "", f'still silent as {f["construct"]!r}'


def test_a_real_read_of_the_field_is_still_a_reference():
    """The guard that matters. Dropping type positions must not drop the uses: this field
    is read in a condition, so it still decides something and still has a partition."""
    src = ("class A {\n"
           "  private static readonly Encoding Encoding = null;\n"
           "  public int Q() { if (Encoding != null) { return 1; } return 0; }\n"
           "}\n")
    f = _findings("csharp", "m.cs", src)["Encoding"]
    assert f["verdict"] == "neutral"
    assert f["partition"]["classes"] > 0, "the condition read must still cut the partition"
