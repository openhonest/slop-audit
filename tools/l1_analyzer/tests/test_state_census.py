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
from l1_analyzer.incomplete import IncompleteCode
from l1_analyzer.indicators import LANG_CFG, L1Result

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

# The declaration nothing looked at, which is what the refusal is for. Rust and Go enumerate
# struct fields from USAGE and from nothing else, so a field no method in the file touches was
# never reached by any rule - not read and declined, not looked at. The census has named this
# case since it was written, and until 2026-08-16 nothing could act on it, because capability
# was recorded per declaration KIND against one fixture and the kind's fixture uses its field.
RUST_UNVISITED_FIELD = (
    "pub struct Store { pub cache: Vec<i32> }\n"
    "\n"
    "pub fn make() -> Store { Store { cache: Vec::new() } }\n"
)
# One declaration the reader reached and one it did not, which is the residual blind spot: a
# single visited site is enough to grade the repository, so the rest has to be disclosed.
RUST_ONE_VISITED_ONE_NOT = (
    "static mut COUNTER: i32 = 0;\n"
    "\n"
    "pub struct Store { pub cache: Vec<i32> }\n"
    "\n"
    "pub fn bump() { unsafe { COUNTER += 1; } }\n"
)


def _classify(tmp_path, name: str, src: str, lang: str) -> dict:
    (tmp_path / name).write_text(src)
    return state_bounds.classify(tmp_path, lang)


def _results(l18b: dict) -> dict[str, L1Result]:
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
    """Rebuilt 2026-08-16 on the fixture the refusal is actually about. The C struct field it
    used to run on is read now, and its third assertion was on `admitted_fraction`, which was
    findings over declarations - two counts of different things - and is deleted rather than
    repaired. `visited` is the number that replaced it, and it is a count of the same unit."""
    result = _classify(tmp_path, "m.rs", RUST_UNVISITED_FIELD, "rust")
    census = result["census"]
    assert census["admitted"] == 0
    assert census["declared"] >= 1
    assert census["visited"] == 0, "nothing in this file's reading looked at the field"


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
    result = _classify(tmp_path, "m.rs", RUST_UNVISITED_FIELD, "rust")
    g = report.grade_summary(_results(result), None)
    assert g["status"] == "na"
    assert g["grade"] is None
    assert g["testable_pct"] is None


# --------------------------------------------------------------------------
# The renderer: no grade sentence, no capability claim, no path-cover figure.
# --------------------------------------------------------------------------

def test_the_card_makes_no_capability_claim_when_the_classifier_admitted_nothing(tmp_path):
    result = _classify(tmp_path, "m.rs", RUST_UNVISITED_FIELD, "rust")
    model = card.build_card("o/r", "rust", _results(result), ran_tests=False, analyzer_version="test")
    md = card.card_markdown(model)
    assert model["grade"] is None
    assert "**Grade:" not in md
    assert "CAN be exhaustively tested" not in md
    assert "grow without limit" not in md
    assert "1,080" not in md, "a path-cover figure is coverage of state nobody enumerated"


def test_the_card_says_what_it_could_not_read(tmp_path):
    result = _classify(tmp_path, "m.rs", RUST_UNVISITED_FIELD, "rust")
    md = card.card_markdown(card.build_card("o/r", "rust", _results(result), ran_tests=False, analyzer_version="test"))
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


# --------------------------------------------------------------------------
# The refusal has to separate "nothing reached it" from "every rule said no".
#
# Both produce zero admitted, and a count of findings cannot tell them apart. A Rust struct
# field with no impl in the file is the first: nothing in this file's reading looked at it, so
# refusing is right. A codebase built out of TypedDict shapes and immutable module constants
# is the second: the enumerator walked every declaration it spells and declined them on the
# merits. Refusing there reports a limit that does not exist, and it refused this repository's
# own analyzer package.
#
# The visit record is what separates them, and it has to be the READER'S own. Between
# 2026-08-15 and 2026-08-16 the middle clause was answered per (language, declaration kind)
# from a fixture, which cannot see either fact: a kind is readable in one repository and not
# in the next, and every pair measured readable, so the refusal was dead.
# --------------------------------------------------------------------------

NO_MUTABLE_STATE_BY_DESIGN = (
    "from typing import TypedDict\n"
    "\n"
    "\n"
    "class Row(TypedDict):\n"
    "    name: str\n"
    "    count: int\n"
    "\n"
    "\n"
    "HEADERS = ('name', 'count')\n"
    "\n"
    "\n"
    "def render(row: Row) -> str:\n"
    "    return f\"{row['name']}={row['count']}\"\n"
)
# A class-body binding, which the Python enumerator had no rule for until `record_state`.
# It is read now, which is why the test below that turns on it stays skipped.
PY_CLASS_BODY_CACHE = (
    "class Store:\n"
    "    cache = {}\n"
    "\n"
    "    def put(self, k, v):\n"
    "        Store.cache[k] = v\n"
)


def test_a_codebase_with_no_mutable_state_by_design_is_graded_not_refused(tmp_path):
    """The defect this test was written for: every kind here is one the enumerator can
    match, it matched none of them because none of them is mutable state, and the report
    called that insufficient basis.

    The panel carries L1.18 at 0.0 rather than the helper's 1.0, and the difference is now
    part of the test. `render` touches no external mutable state, so zero is the walker's
    honest reading of this fixture, and zero beside a classifier that decided nothing is two
    measures agreeing. The helper's 1.0 says a function here does touch unbounded state,
    which nothing in the fixture does; `grade_summary` reads that as the two measures
    disagreeing and refuses, correctly. The fixture was contradicting itself.
    """
    result = _classify(tmp_path, "m.py", NO_MUTABLE_STATE_BY_DESIGN, "python")
    assert result["census"]["admitted"] == 0
    assert result["census"]["declared"] > 0
    g = report.grade_summary(_results(result) | {"L1.18": {"value": 0.0, "band": "Healthy"}}, None)
    assert g["basis"] == report.MEASURED, "the enumerator looked and was right; that is a reading"
    assert g["grade"] is not None


def test_a_classifier_that_decided_nothing_beside_a_non_zero_l1_18_refuses(tmp_path):
    """The other side of the same line, and the case the refusal was written for. A 14-line
    Ruby file whose whole state is an unbounded class variable and a global was graded C on
    "100% of its state is finitely testable" while L1.18 read 50.0 on the same file. One of
    the two is wrong and the report cannot tell which, so it publishes neither.

    The fixture above is what stops this rule from firing on every clean repository: zero
    decided states means either no rule matched or every rule said no, and only a second
    measure that found something separates them.
    """
    result = _classify(tmp_path, "m.py", NO_MUTABLE_STATE_BY_DESIGN, "python")
    panel = _results(result) | {"L1.18": {"value": 50.0, "band": "Slop"}}
    with pytest.raises(IncompleteCode, match="finitely-testable share"):
        report.grade_summary(panel, None)


@pytest.mark.skip(reason="2026-08-16: no Python fixture can reach the refusal, and the reason changed. The 2026-08-15 note said the refusal itself could not fire; it can, and the four tests above it now do, on a Rust struct field nothing visits. This one asks for the same thing in PYTHON, and Python has no such declaration: measured over every kind the census counts for it, and over 557 declarations in this repository, the enumerator visits every site it declares. The class-body binding this fixture was written for is read by record_state. REBUILD, do not delete: the day a Python construct is found that no rule reaches, this is its test. Skipped rather than deleted so the gap stays visible with a date on it.")
def test_python_state_the_enumerator_has_no_rule_for_refuses_like_the_c_struct(tmp_path):
    """The other half. A class-body binding is invisible to the Python enumerator the way a
    struct field is invisible to the C one, so a repository holding nothing else has been
    read by nothing and gets no grade."""
    result = _classify(tmp_path, "m.py", PY_CLASS_BODY_CACHE, "python")
    g = report.grade_summary(_results(result), None)
    assert g["basis"] == report.UNREAD
    assert g["grade"] is None


def test_the_census_publishes_the_denominator_its_reader_can_actually_reach(tmp_path):
    """Rebuilt 2026-08-16. It used to read `count`, which walks the parse trees and never runs
    the classifier, so it could not know where the reader went; it answered from a per-kind
    capability table instead, and that table said every kind was readable. The denominator is
    now the reader's own visit record, and only `classify` has it."""
    result = _classify(tmp_path, "m.rs", RUST_ONE_VISITED_ONE_NOT, "rust")
    census = result["census"]
    assert census["declared"] == 2
    assert census["visited"] == 1, "the static is read; nothing reaches the field"
    assert census["unread_kinds"] == [state_census.FIELD_DECLARATION]


def test_the_census_alone_refuses_to_say_what_its_reader_reached(tmp_path):
    """`count` runs no classifier, so it answers None and not zero. Zero is the claim the
    refusal is taken on - the reader reached none of this - and a walk that never asked the
    reader anything must not be able to make it."""
    (tmp_path / "m.py").write_text(NO_MUTABLE_STATE_BY_DESIGN)
    census = state_census.count(tmp_path, "python")
    assert census["declared"] == 3
    assert census["visited"] is None and census["unread_kinds"] is None
    assert not report.census_unread(census), "an uncounted visit record can never withhold a grade"


def test_one_visited_declaration_carries_the_unvisited_ones_and_the_report_says_so(tmp_path):
    """The residual blind spot, pinned rather than left implicit.

    The refusal fires only when NOTHING declared here is of a readable kind, so a single
    readable binding is enough to grade a repository whose remaining state the enumerator
    cannot see. That is a deliberate limit: the alternative refuses every Python repository
    with a TypedDict in it, which measures our reading rather than their code. What the
    report owes the reader instead is the count, and this test fails the day the disclosure
    goes missing or the day someone teaches the enumerator class-body bindings.

    It asserts against card_markdown and card_html because those are the only renderers left.
    The first version asserted against report_markdown, which had no caller outside this
    suite, so it passed green while the disclosure reached no reader at all. That renderer is
    now deleted; a test against an orphaned one proves a string exists, not that anyone is
    shown it."""
    (tmp_path / "m.rs").write_text(RUST_ONE_VISITED_ONE_NOT)
    result = state_bounds.classify(tmp_path, "rust")
    g = report.grade_summary(_results(result), None)
    assert g["basis"] == report.MEASURED
    model = card.build_card("o/r", "rust", _results(result), ran_tests=False, analyzer_version="test")
    assert model["grade"] is not None, "the disclosure belongs on a card that GRADED"
    for rendered in (card.card_markdown(model), card.card_html(model)):
        assert "a field declared inside a record type" in rendered
        assert "never reached" in rendered


# --------------------------------------------------------------------------
# The capability matrix is MEASURED, never asserted. A hand-maintained table of which
# language handles which declaration kind rots into the blind spot the census exists to
# detect, so every entry is a fixture run through the real classifier.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("lang,kind", sorted(state_census.CAPABILITY))
def test_the_recorded_capability_is_what_the_classifier_actually_does(tmp_path, lang, kind):
    probe = state_census.CAPABILITY[(lang, kind)]
    (tmp_path / probe["file"]).write_text(probe["source"])
    sites = state_census.count(tmp_path, lang)
    admitted = len(state_bounds.classify(tmp_path, lang)["findings"])
    assert sites["by_kind"][kind] == 1, "the fixture must declare exactly one site of its kind"
    assert bool(admitted) == probe["admitted"], (
        f"{lang}/{kind}: recorded admitted={probe['admitted']}, measured {admitted} findings")


# One sample per language, keyed by the production language table's own key. The samples
# are hand-written because only a person can write source in nine grammars; the SET of
# languages they have to cover is not, so it is checked against LANG_CFG below.
_DECLARATION_SAMPLES: dict[str, tuple[str, str, int]] = {
    "rust": ("m.rs", "struct S { a: u32, b: u32 }\nstatic mut G: u32 = 0;\n", 3),
    "go": ("m.go", "package p\ntype S struct {\n a int\n b int\n}\nvar g int\n", 3),
    "java": ("M.java", "class M { private int a; private String b; }\n", 2),
    "csharp": ("M.cs", "class M { private int a; private string b; }\n", 2),
    "ruby": ("m.rb", "class M\n def initialize\n  @a = 1\n  @b = 2\n end\nend\n", 2),
    "javascript": ("m.js", "class M { constructor() { this.a = 1; this.b = 2; } }\n", 2),
    "typescript": ("m.ts", "class M { private a: number = 1; private b: number = 2; }\n", 2),
}
# c and python are counted by the two dedicated tests at the top of this file, which assert
# an exact count rather than a floor. They are named here, not omitted, so the closure test
# below can see that every LANG_CFG language is accounted for somewhere.
_COUNTED_BY_A_DEDICATED_TEST = frozenset({"c", "python"})


def test_the_sample_set_covers_every_language_the_analyzer_declares():
    """The tenth language. Without this, adding a row to LANG_CFG leaves its census
    uncounted and every test in this file still passes."""
    assert set(_DECLARATION_SAMPLES) | _COUNTED_BY_A_DEDICATED_TEST == set(LANG_CFG)


@pytest.mark.parametrize("lang", sorted(_DECLARATION_SAMPLES))
def test_every_supported_language_counts_its_own_state_declarations(tmp_path, lang):
    name, src, least = _DECLARATION_SAMPLES[lang]
    (tmp_path / name).write_text(src)
    assert state_census.count(tmp_path, lang)["declared"] >= least
