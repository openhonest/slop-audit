"""The independent denominator: state-bearing declarations counted from the parse tree.

Silence, resolvable_fraction and the section-7 partition count are all computed over the
state the classifier RECOGNIZED. Nothing measured over the enumerated set can see
non-enumeration, so a repository the classifier never read produces zero silence, a
resolvable fraction of 1.0, and - through the card - an affirmative claim that none of its
data can grow without limit. That claim was made about code nothing looked at.

The census is the second reading the first one cannot check itself against. It counts
state-bearing declaration sites straight from the grammar (struct fields, class fields,
instance-variable assignments, file-scope and package-level bindings), never through
`_enum_module_state` / `_enum_instance_state`, so a construct the classifier's enumerator
does not know about still shows up in the denominator.

The case that motivated it: an unbounded C cache graded F when it is a file-scope global
and A when the identical cache lives in a struct field, because the C enumerator reads
file-scope declarations only and struct fields are invisible to it. Same code, same
unboundedness, two letters apart. Both spellings must reach the same honest outcome - a
real verdict, or an explicit refusal to grade.
"""

from __future__ import annotations

import pytest
from l1_analyzer import card, report, state_bounds, state_census

# The same unbounded cache, spelled twice. `cache[k]` with a variable key is an unbounded
# lookup either way; only where the array is declared differs.
C_FILE_SCOPE = (
    "static int cache[256];\n"
    "void put(int k, int v) { cache[k] = v; }\n"
    "int get(int k) { return cache[k]; }\n"
)
C_STRUCT_FIELD = (
    "struct Store { int cache[256]; int hits; };\n"
    "void put(struct Store *s, int k, int v) { s->cache[k] = v; }\n"
    "int get(struct Store *s, int k) { return s->cache[k]; }\n"
)


def _classify(tmp_path, name: str, src: str, lang: str) -> dict:
    (tmp_path / name).write_text(src)
    return state_bounds.classify(tmp_path, lang)


def _results(l18b: dict) -> dict:
    """A panel with a healthy L1.18 and a path-cover figure, which is what the card needs
    to manufacture the false claim: the other indicators are fine, so only the state
    classifier can withhold the grade."""
    return {"L1.18": {"value": 1.0, "band": "Healthy"}, "L1.18b": l18b,
            "path_cover": {"value": 1080}}


# --------------------------------------------------------------------------
# The census itself: a count that does not go through the classifier's enumerator.
# --------------------------------------------------------------------------

def test_c_struct_fields_are_counted_even_though_the_classifier_cannot_read_them(tmp_path):
    (tmp_path / "case.c").write_text(C_STRUCT_FIELD)
    census = state_census.count(tmp_path, "c")
    assert census["declared"] >= 2, "struct Store declares cache and hits"


def test_python_instance_and_module_state_are_counted(tmp_path):
    (tmp_path / "m.py").write_text(
        "REGISTRY = {}\n"
        "class Cache:\n"
        "    def __init__(self):\n"
        "        self.entries = {}\n"
        "        self.hits = 0\n"
    )
    census = state_census.count(tmp_path, "python")
    assert census["declared"] == 3


def test_a_language_with_no_census_spec_declares_nothing_rather_than_zero(tmp_path):
    census = state_census.count(tmp_path, "cobol")
    assert census["declared"] is None, "no spec must be 'unknown', never a confident zero"


# --------------------------------------------------------------------------
# The classifier reports the gap beside its own counts.
# --------------------------------------------------------------------------

def test_classifier_publishes_the_census_beside_what_it_admitted(tmp_path):
    result = _classify(tmp_path, "case.c", C_STRUCT_FIELD, "c")
    census = result["census"]
    assert census["admitted"] == 0
    assert census["declared"] >= 2
    assert census["admitted_fraction"] == 0.0


# --------------------------------------------------------------------------
# The verdict: a large gap means the analysis did not see the code.
# --------------------------------------------------------------------------

def test_the_two_spellings_of_one_unbounded_cache_reach_the_same_honest_outcome(tmp_path):
    scope_dir, struct_dir = tmp_path / "a", tmp_path / "b"
    scope_dir.mkdir()
    struct_dir.mkdir()
    by_scope = report.grade_summary(_results(_classify(scope_dir, "case.c", C_FILE_SCOPE, "c")), None)
    by_field = report.grade_summary(_results(_classify(struct_dir, "case.c", C_STRUCT_FIELD, "c")), None)
    assert by_scope["status"] == "cannot" and by_scope["grade"] == "F"
    # Not a good grade for hiding the same cache one syntactic level down. Either the meter
    # reaches the same proof, or it says it had no basis - never A.
    assert by_field["status"] in ("cannot", "na")
    assert by_field["grade"] in ("F", None)


def test_a_repository_the_classifier_never_read_gets_no_grade(tmp_path):
    result = _classify(tmp_path, "case.c", C_STRUCT_FIELD, "c")
    g = report.grade_summary(_results(result), None)
    assert g["status"] == "na"
    assert g["grade"] is None
    assert g["testable_pct"] is None


# --------------------------------------------------------------------------
# The renderer: no grade sentence, no capability claim, no path-cover figure.
# --------------------------------------------------------------------------

def test_the_card_makes_no_capability_claim_when_the_classifier_admitted_nothing(tmp_path):
    result = _classify(tmp_path, "case.c", C_STRUCT_FIELD, "c")
    model = card.build_card("o/r", "c", _results(result))
    md = card.card_markdown(model)
    assert model["grade"] is None
    assert "**Grade:" not in md
    assert "CAN be exhaustively tested" not in md
    assert "grow without limit" not in md
    assert "1,080" not in md, "a path-cover figure is coverage of state nobody enumerated"


def test_the_card_says_what_it_could_not_read(tmp_path):
    result = _classify(tmp_path, "case.c", C_STRUCT_FIELD, "c")
    md = card.card_markdown(card.build_card("o/r", "c", _results(result)))
    assert "insufficient basis" in md.lower()


def test_a_classifier_that_read_the_code_still_grades(tmp_path):
    (tmp_path / "m.py").write_text(
        "class Router:\n"
        "    def __init__(self):\n"
        "        self.enabled = False\n"
        "    def route(self):\n"
        "        if self.enabled:\n"
        "            return 1\n"
        "        return 0\n"
    )
    result = state_bounds.classify(tmp_path, "python")
    g = report.grade_summary(_results(result), None)
    assert g["status"] == "can", "the census must not suppress a verdict the meter earned"
    assert g["grade"] is not None


@pytest.mark.parametrize("lang,name,src,least", [
    ("rust", "m.rs", "struct S { a: u32, b: u32 }\nstatic mut G: u32 = 0;\n", 3),
    ("go", "m.go", "package p\ntype S struct {\n a int\n b int\n}\nvar g int\n", 3),
    ("java", "M.java", "class M { private int a; private String b; }\n", 2),
    ("csharp", "M.cs", "class M { private int a; private string b; }\n", 2),
    ("ruby", "m.rb", "class M\n def initialize\n  @a = 1\n  @b = 2\n end\nend\n", 2),
    ("javascript", "m.js", "class M { constructor() { this.a = 1; this.b = 2; } }\n", 2),
    ("typescript", "m.ts", "class M { private a: number = 1; private b: number = 2; }\n", 2),
])
def test_every_supported_language_counts_its_own_state_declarations(tmp_path, lang, name, src, least):
    (tmp_path / name).write_text(src)
    assert state_census.count(tmp_path, lang)["declared"] >= least
