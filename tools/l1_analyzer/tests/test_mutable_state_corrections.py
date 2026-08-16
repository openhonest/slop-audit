"""Regression cover for the four defects corrected in L1.18 on 2026-08-15.

One test per defect, each written against a fixture the uncorrected indicator
answered wrongly, so the test fails while the defect stands and passes only once the
correction lands. All four were run against the unfixed code first and failed there,
so they measure the fix and not the fixture (see
research/amendments/amendment-2026-08-15-l1-18-corrected-ratio.md).

Self-contained: every test builds its own source tree under tmp_path, so nothing
depends on an external checkout. Pure assertions, no mocks (Honest Code Rule 10).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from l1_analyzer.incomplete import IncompleteCode
from l1_analyzer.indicators import LANG_CFG, _get_parser
from l1_analyzer.mutable_state import _find_module_mutable_names, analyze_mutable_state


def _tree(tmp_path: Path, name: str, src: str) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / name).write_text(src)
    return tmp_path


def _ratio(tmp_path: Path, name: str, src: str, lang: str) -> float:
    return analyze_mutable_state(_tree(tmp_path, name, src), lang)["value"]


def _names(src: str, lang: str) -> set[str]:
    root = _get_parser(lang).parse(src.encode()).root_node
    return _find_module_mutable_names(root, LANG_CFG[lang])


# ---------------------------------------------------------------------------
# Defect 1: the I/O boundary exclusion. It only ever fired on a literal
# `honest: boundary` comment, and recognising a boundary by analysis cannot be done
# without a per-framework enumeration, so the claim was dropped. The marker no
# longer excludes anything, and these two tests are what stop it coming back: an
# exclusion a subject opts into is a lever a subject controls.
# ---------------------------------------------------------------------------

_MARKED_BOUNDARY = "cache = []\ndef handler():\n    # honest: boundary\n    print(cache)\n    return len(cache)\n"


def test_the_boundary_marker_no_longer_excludes_a_function(tmp_path):
    assert _ratio(tmp_path, "m.py", _MARKED_BOUNDARY, "python") == 100.0


def test_the_boundary_marker_does_not_change_the_denominator(tmp_path):
    """The old exclusion removed a marked function from BOTH counts, so a marker
    could move the ratio of the functions around it. It cannot now."""
    marked = _ratio(tmp_path / "marked", "m.py", _MARKED_BOUNDARY, "python")
    plain = _ratio(tmp_path / "plain", "m.py", _MARKED_BOUNDARY.replace("    # honest: boundary\n", ""), "python")
    assert marked == plain


# ---------------------------------------------------------------------------
# Defect 2: the immutability vocabulary was shared across languages, so it did not
# match any of them. TypeScript inherited a default containing "let ", which made a
# module-level `let` immutable in .ts and mutable in .js: the same construct with two
# answers, decided by the file extension.
# ---------------------------------------------------------------------------

_MODULE_LET_TS = "let counter = 0;\nexport function bump(): number {\n  counter += 1;\n  return counter;\n}\n"
_MODULE_LET_JS = "let counter = 0;\nexport function bump() {\n  counter += 1;\n  return counter;\n}\n"


def test_typescript_module_let_is_mutable_state(tmp_path):
    assert _names(_MODULE_LET_TS, "typescript") == {"counter"}
    assert _ratio(tmp_path, "m.ts", _MODULE_LET_TS, "typescript") == 100.0


def test_module_let_reads_the_same_in_typescript_and_javascript(tmp_path):
    """The two files differ only in extension. One answer, or the indicator is
    measuring the file name."""
    ts = _ratio(tmp_path / "ts", "m.ts", _MODULE_LET_TS, "typescript")
    js = _ratio(tmp_path / "js", "m.js", _MODULE_LET_JS, "javascript")
    assert ts == js == 100.0


def test_typescript_module_const_is_not_mutable_state(tmp_path):
    src = "const LIMIT = 10;\nexport function cap(x: number): number {\n  return x > LIMIT ? LIMIT : x;\n}\n"
    assert _ratio(tmp_path, "m.ts", src, "typescript") == 0.0


# ---------------------------------------------------------------------------
# Defect 3: Java and C# fields were unreachable, twice over. The module scan looked at
# root children and one level below, while a field sits at root, class declaration,
# class body, field declaration; and the reference walk counted only receiver-prefixed
# access, so bare field access - the idiomatic form in both - was invisible. Between
# them the indicator measured how often authors write `this.`, a style preference.
# ---------------------------------------------------------------------------

_JAVA_FIELD = """class Counter {
    private int total = 0;
    int add(int x) { total += x; return total; }
    int pure(int a, int b) { return a + b; }
}
"""


def test_java_bare_field_access_is_counted(tmp_path):
    assert _names(_JAVA_FIELD, "java") == {"total"}
    assert _ratio(tmp_path, "Counter.java", _JAVA_FIELD, "java") == 50.0


def test_java_uninitialised_field_is_still_state(tmp_path):
    """`private int total;` carries no `=`, so the text heuristic required an equals
    sign the declaration does not have and never saw the field even at the right
    depth. A field with no initialiser is state exactly as an initialised one is."""
    src = "class Counter {\n    private int total;\n    int add(int x) { total += x; return total; }\n}\n"
    assert _names(src, "java") == {"total"}


def test_java_final_field_is_not_mutable_state(tmp_path):
    src = "class Counter {\n    private final int limit = 10;\n    int cap(int x) { return x > limit ? limit : x; }\n}\n"
    assert _names(src, "java") == set()
    assert _ratio(tmp_path, "Counter.java", src, "java") == 0.0


def test_java_local_variable_is_not_counted_as_a_field(tmp_path):
    """The corrected scan reaches into class bodies, which is where the fields are. It
    must not also harvest method locals: Java's module-level assignment vocabulary
    lists local_variable_declaration, so a deep walk over THAT vocabulary would count
    every local as external state, which is worse than the defect being fixed."""
    src = "class Counter {\n    int add(int x) { int total = x; return total; }\n}\n"
    assert _names(src, "java") == set()
    assert _ratio(tmp_path, "Counter.java", src, "java") == 0.0


_CSHARP_FIELD = """class Counter {
    private int total = 0;
    public int Add(int x) { total += x; return total; }
    public int Pure(int a, int b) { return a + b; }
}
"""


def test_csharp_bare_field_access_is_counted(tmp_path):
    assert _names(_CSHARP_FIELD, "csharp") == {"total"}
    assert _ratio(tmp_path, "Counter.cs", _CSHARP_FIELD, "csharp") == 50.0


def test_a_field_compared_against_a_literal_is_bounded_and_so_is_not_counted(tmp_path):
    """The two corrections interact, and the interaction is deliberate rather than a
    gap. Correction 3 makes the field visible; correction 4 then asks the classifier
    whether the state it reaches is bounded, and `total > 0` induces a two-class
    partition, which is exhaustively testable. So a Java field that only ever meets a
    literal comparison does not count, while the same field accumulated and returned
    does. Pinned here because the answer surprises on first reading, and because
    changing it means writing a second boundedness rule that would contradict the
    classifier printed beside this number."""
    src = ("class Counter {\n    private int total = 0;\n"
           "    int add(int x) { total += x; if (total > 0) { return total; } return 0; }\n}\n")
    assert _names(src, "java") == {"total"}          # correction 3: the field IS seen
    assert _ratio(tmp_path, "Counter.java", src, "java") == 0.0   # correction 4: bounded


def test_csharp_readonly_and_const_fields_are_not_mutable_state(tmp_path):
    src = """class Counter {
    private readonly int limit = 10;
    const int MAX = 99;
    public int Cap(int x) { return x > limit ? limit : MAX; }
}
"""
    assert _names(src, "csharp") == set()
    assert _ratio(tmp_path, "Counter.cs", src, "csharp") == 0.0


# ---------------------------------------------------------------------------
# Defect 4: the ratio was not bound-aware. A read keyed by a literal against a closed
# set is finite and exhaustively testable; an unbounded lookup is not. L1.18 counted
# both identically. It now asks the finite-testability classifier for its verdict on
# each piece of state and counts only state whose reaching-set that classifier could
# not bound.
# ---------------------------------------------------------------------------

def test_literal_keyed_read_against_a_closed_set_is_not_counted(tmp_path):
    src = 'limits = {"small": 1, "large": 9}\ndef cap():\n    if limits["small"] > 0:\n        return 1\n    return 0\n'
    assert _ratio(tmp_path, "m.py", src, "python") == 0.0


def test_unbounded_keyed_read_is_still_counted(tmp_path):
    src = "limits = {}\ndef cap(kind):\n    if limits[kind] > 0:\n        return 1\n    return 0\n"
    assert _ratio(tmp_path, "m.py", src, "python") == 100.0, (
        "an unbounded key leaves the partition unbounded, so the reference still counts"
    )


def test_state_that_drives_no_decision_is_not_treated_as_bounded(tmp_path):
    """The classifier returns NEUTRAL both for state it bounded and for state that
    reaches no decision at all, and the two are different facts. Reading NEUTRAL alone
    as "bounded" cancelled the Java and C# field correction, because a plain field
    accumulator is exactly the second shape. The rule requires a counted partition."""
    src = "seen = []\ndef note(x):\n    seen.append(x)\n    return len(seen)\n"
    assert _ratio(tmp_path, "m.py", src, "python") == 100.0


# ---------------------------------------------------------------------------
# Shape guarantees that hold whatever the corrections do.
# ---------------------------------------------------------------------------

def test_every_language_declares_its_own_module_scan(tmp_path):
    """No language reaches a scan by omission. The text scan used to be the
    fall-through of an if/elif chain, which is how TypeScript and C arrived on it
    without anyone choosing it for them, and inherited its shared keyword default."""
    for lang, cfg in LANG_CFG.items():
        assert "module_scan" in cfg, f"{lang} does not declare a module scan"
        if cfg["module_scan"] == "text":
            assert "const_keywords" in cfg, f"{lang} text-scans with no immutability vocabulary"


def test_malformed_source_refuses_in_every_language_rather_than_crashing(tmp_path):
    """Three grammars, three refusals, each naming L1.18 and the language it read.

    The old body asserted `value != "n/a"`, which required a number off a parse that
    recovered nothing. That is the defect this measure was corrected for, one language at a
    time: a file the parser could not read yielded no function, and 0/0 was published as a
    share. The refusal is not a crash - the parser still survives all three files - and the
    `match` pins which measure declined, so a refusal raised somewhere else could not pass
    this test by accident.
    """
    for name, src in (("m.py", "def ("), ("Counter.java", "class {{{"), ("m.ts", "let = ;")):
        (tmp_path / name).write_text(src)
    for lang in ("python", "java", "typescript"):
        with pytest.raises(IncompleteCode, match=f"L1.18 unbounded mutable state.*in {lang}"):
            analyze_mutable_state(tmp_path, lang)
