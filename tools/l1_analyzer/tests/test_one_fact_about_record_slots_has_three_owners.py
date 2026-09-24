"""Which node type declares a slot inside a record is one fact, and three tables answer it.

`LANG_SPEC["field_decl_types"]` is read by the Honest Code reader and by L1.18b.
`LANG_CFG["field_decl_types"]` is read by L1.18's class-fields scan.
`state_census._FIELDS` is read by the census, the independent denominator.

Nothing compared them, and they disagreed. C# gained `property_declaration` in two of the
three, so L1.18 counted a field and not an auto-property: `public int Count { get; set; }` is
state by any definition and was state nobody counted. The census carried a comment saying so
while the row beside it stayed wrong. Adding it moved RestSharp from 2.3 to 11.6 and
Newtonsoft.Json from 11.4 to 17.4, which crossed a band.

Java was the same shape one language over, found the same way and on the same day: the census
gained `constant_declaration` for an interface constant and the other two did not.

This does not merge the three tables, which is the structural answer and a larger change. It
turns the next disagreement into a failing test rather than an accident, and it makes every
deliberate difference say why it is deliberate.
"""

from __future__ import annotations

from l1_analyzer.indicators import LANG_CFG
from l1_analyzer.lang_spec import LANG_SPEC
from l1_analyzer.state_census import _FIELDS

# Where the three tables differ ON PURPOSE, and the reason. A language absent from this
# mapping must have the same answer in all three.
DELIBERATE = {
    # L1.18's class-fields scan is for the two languages that declare fields in a class body
    # and reach them by bare name. JavaScript and TypeScript go through the text scan
    # instead, so an empty row there is the right answer rather than a gap.
    ("javascript", "cfg"): (),
    ("typescript", "cfg"): (),
    # The census counts a Java interface constant and neither reader can reach one. That is
    # the census doing its job: it exists to report the classifier's blind spots, and a
    # denominator that shared this one could not report it.
    ("java", "census"): ("field_declaration", "constant_declaration"),
    # THE CASE THE CENSUS WAS BUILT FOR, and the three languages that carry it. A C struct
    # field, a Rust struct field and a Go struct field are counted by the census and reached
    # by neither reader through this table: the readers enumerate them from USAGE instead,
    # which is a different route with a different blind spot. The unbounded C cache that
    # graded F at file scope and A inside a struct is the defect this module opens with.
    ("c", "census"): ("field_declaration",),
    ("rust", "census"): ("field_declaration",),
    ("go", "census"): ("field_declaration",),
}


def answers(lang: str) -> dict[str, tuple[str, ...]]:
    """What each of the three tables says about this language."""
    return {
        "spec": tuple(LANG_SPEC[lang].get("field_decl_types") or ()),
        "cfg": tuple(LANG_CFG.get(lang, {}).get("field_decl_types") or ()),
        "census": tuple(_FIELDS[lang][0]),
    }


def test_the_three_tables_agree_except_where_a_reason_is_written_down():
    for lang in sorted(LANG_SPEC):
        given = answers(lang)
        for owner, declared in given.items():
            expected = DELIBERATE.get((lang, owner))
            if expected is not None:
                assert declared == expected, (
                    f"{lang}/{owner} differs deliberately and the declared difference is "
                    f"stale: the table says {declared}, this test says {expected}")
                continue
            others = {name: value for name, value in given.items()
                      if (lang, name) not in DELIBERATE}
            assert len(set(others.values())) == 1, (
                f"one fact about {lang} record slots, answered three ways with no reason "
                f"written down: {others}")


def test_every_deliberate_difference_names_a_language_and_a_table_that_exist():
    """A reason for a divergence that no longer exists hides the fact that nobody ruled on
    whatever replaced it."""
    for lang, owner in DELIBERATE:
        assert lang in LANG_SPEC, f"{lang} is not a language this analyzer reads"
        assert owner in answers(lang), f"{owner} is not one of the three tables"


def test_a_csharp_auto_property_is_a_record_slot_in_all_three():
    """The defect this file was written for, stated on its own so it cannot be lost in the
    loop above. It went unseen because two of the three tables were right."""
    for owner, declared in answers("csharp").items():
        assert "property_declaration" in declared, (
            f"{owner} does not count a C# auto-property as a slot the class keeps data in")
