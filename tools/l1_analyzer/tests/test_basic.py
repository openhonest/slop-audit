"""Tests for the any-language L1 analyzer.

Self-contained: every test builds its own fixture under tmp_path, so nothing
depends on an external checkout. Pure assertions, no mocks (Honest Code Rule 10).
"""

import os
import subprocess

import pytest
from l1_analyzer import indicators, pytest_trace, scope
from l1_analyzer.incomplete import IncompleteCode
from l1_analyzer.indicators import (
    analyze_mutable_state,
    band,
    compute_git_indicators,
    detect_primary_language,
)

# One sample per supported language: a stateful method (references external
# mutable state) plus a pure function that must NOT be counted. This locks in
# that L1.18 both runs and discriminates for every language we advertise.
LANG_SAMPLES = {
    "java": ("Acc.java", "class Acc { private int total; int add(int x){ this.total += x; return this.total; } static int pure(int a, int b){ return a + b; } }"),
    "csharp": ("Acc.cs", "class Acc { private int total; int Add(int x){ this.total += x; return this.total; } static int Pure(int a, int b){ return a + b; } }"),
    "javascript": ("acc.js", "let counter = 0;\nclass Acc { add(x){ this.total += x; return this.total; } }\nfunction pure(a, b){ return a + b; }\n"),
    "ruby": ("acc.rb", "class Acc\n  def add(x)\n    @total += x\n  end\n  def self.pure(a, b)\n    a + b\n  end\nend\n"),
    "go": ("acc.go", "package main\ntype Acc struct { total int }\nfunc (a *Acc) Add(x int) int { a.total += x; return a.total }\nfunc Pure(a, b int) int { return a + b }\n"),
    "python": ("acc.py", "G = 0\nclass Acc:\n    def add(self, x):\n        self.total += x\n        return self.total\n\ndef pure(a, b):\n    return a + b\n"),
}


# --- pure scoring (Honest Code: band is a pure function of counts) -----------

def test_band_higher_is_better():
    assert band(95, 90, 60, higher_is_better=True) == "Healthy"
    assert band(75, 90, 60, higher_is_better=True) == "Not Healthy"
    assert band(50, 90, 60, higher_is_better=True) == "Slop"


def test_band_lower_is_better():
    assert band(5, 15, 40, higher_is_better=False) == "Healthy"
    assert band(20, 15, 40, higher_is_better=False) == "Not Healthy"
    assert band(60, 15, 40, higher_is_better=False) == "Slop"


# --- honest handling of the unknown / empty case ----------------------------

def test_detect_unknown_when_no_source(tmp_path):
    (tmp_path / "README.md").write_text("# docs only, no source")
    assert detect_primary_language(tmp_path) == "unknown"


def test_unknown_language_is_na_not_guessed(tmp_path):
    (tmp_path / "acc.py").write_text("x = 1\n")
    # An unknown language must NOT be silently analyzed as Python.
    assert analyze_mutable_state(tmp_path, "klingon")["band"] == "n/a"
    assert indicators._compute_type_escapes(tmp_path, "klingon")["band"] == "n/a"
    assert indicators._compute_decision_space(tmp_path, "klingon")["band"] == "n/a"


# --- config integrity: direct cfg[...] access is safe -----------------------

def test_every_language_config_has_required_keys():
    required = ("language", "extensions", "function_types", "class_types",
               "member_access", "this_ident", "module_level_assign", "type_escape_patterns")
    for lang, cfg in indicators.LANG_CFG.items():
        for key in required:
            assert key in cfg, f"{lang} missing required LANG_CFG key {key}"


# --- no silent swallow of arguments -----------------------------------------

def test_compute_source_indicators_rejects_unexpected_kwargs(tmp_path):
    (tmp_path / "acc.py").write_text("x = 1\n")
    with pytest.raises(TypeError):
        indicators.compute_source_indicators(tmp_path, lang="python", exec_tests=False, timeout_seconds=5.0, bogus=1)


# --- skipped files are surfaced, never silently dropped ---------------------

def test_unreadable_file_is_counted_not_swallowed(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root ignores file permissions")
    (tmp_path / "ok.py").write_text("def f(x):\n    return x\n")
    blocked = tmp_path / "blocked.py"
    blocked.write_text("def g(x):\n    return x\n")
    blocked.chmod(0o000)
    try:
        res = analyze_mutable_state(tmp_path, "python")   # bytes reader
    finally:
        blocked.chmod(0o644)
    assert "unreadable" in res["details"]


def test_unreadable_file_surfaced_by_text_reader(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root ignores file permissions")
    (tmp_path / "ok.py").write_text("x = 1\n")
    blocked = tmp_path / "blocked.py"
    blocked.write_text("y = 2\n")
    blocked.chmod(0o000)
    try:
        res = indicators._trailing_whitespace(tmp_path)   # text reader
    finally:
        blocked.chmod(0o644)
    assert "unreadable" in res["details"]


# --- a directory is not a file: neither measured nor disclosed ---------------

def test_directory_named_like_a_source_file_is_ignored_by_every_reader(tmp_path):
    """rglob yields directories too. node_modules/decimal.js is a real directory whose
    name ends in a source extension; it used to reach the readers, raise
    IsADirectoryError and be reported as an unreadable file. It is neither."""
    (tmp_path / "ok.py").write_text("x = 1\n")
    (tmp_path / "decimal.js").mkdir()
    (tmp_path / "pkg.py").mkdir()

    files, skipped = indicators._read_source_bytes(tmp_path, (".py",), scope.WHOLE_REPO)
    assert skipped == 0
    assert [p.name for p, _ in files] == ["ok.py"]

    text_files, text_skipped = indicators._read_text_files(tmp_path, frozenset({".py", ".js"}), scope.WHOLE_REPO)
    assert text_skipped == 0
    assert [p.name for p, _ in text_files] == ["ok.py"]

    res = indicators._god_files(tmp_path)
    assert "unreadable" not in res["details"]
    assert res["details"].startswith("0/1 files >1k LOC")


def test_a_directory_does_not_hide_a_genuinely_unreadable_file(tmp_path):
    """The honest disclosure survives the fix: a file the process cannot read is still
    counted and surfaced, and the directory beside it adds nothing to that count."""
    if os.geteuid() == 0:
        pytest.skip("root ignores file permissions")
    (tmp_path / "ok.py").write_text("x = 1\n")
    (tmp_path / "decimal.js").mkdir()
    blocked = tmp_path / "blocked.py"
    blocked.write_text("y = 2\n")
    blocked.chmod(0o000)
    try:
        god = indicators._god_files(tmp_path)
        _, skipped = indicators._read_source_bytes(tmp_path, (".py",), scope.WHOLE_REPO)
        _, text_skipped = indicators._read_text_files(tmp_path, frozenset({".py", ".js"}), scope.WHOLE_REPO)
    finally:
        blocked.chmod(0o644)
    assert "1 file(s) unreadable and excluded" in god["details"]
    assert skipped == 1
    assert text_skipped == 1


# --- git indicators run on a real, self-contained repo ----------------------

def test_git_indicators_run(tmp_path):
    (tmp_path / "m.py").write_text("def f():\n    return 1\n")
    (tmp_path / "README.md").write_text("# doc\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    res = compute_git_indicators(tmp_path, None, None)
    assert "L1.1" in res and "value" in res["L1.1"]


# --- L1.19 / L1.20 runtime harness ------------------------------------------

def test_l1_19_l1_20_non_python_is_na(tmp_path):
    cov = pytest_trace.decision_space_coverage(tmp_path, "go", 30.0)
    det = pytest_trace.test_determinism(tmp_path, "go", 5, 30.0)
    assert cov["band"] == "n/a" and det["band"] == "n/a"


def test_l1_19_static_fallback_when_exec_disabled(tmp_path):
    (tmp_path / "m.py").write_text("def f(x):\n    if x:\n        return 1\n    return 0\n")
    res = indicators._decision_space_l19(tmp_path, "python", exec_tests=False, timeout_seconds=30.0)
    assert res["band"] == "n/a"
    assert "coverage not measured" in res["details"]
    assert isinstance(res["value"], int) and res["value"] >= 1


# --- band boundary values (Honest Test: exercise the exact cutoffs) ---------

def test_band_boundaries_higher_is_better():
    assert band(10, 10, 1, higher_is_better=True) == "Healthy"       # == healthy cutoff
    assert band(1, 10, 1, higher_is_better=True) == "Not Healthy"    # == slop cutoff
    assert band(0.9, 10, 1, higher_is_better=True) == "Slop"


def test_band_boundaries_lower_is_better():
    assert band(14.9, 15, 40, higher_is_better=False) == "Healthy"
    assert band(15, 15, 40, higher_is_better=False) == "Not Healthy"  # == healthy cutoff
    assert band(40, 15, 40, higher_is_better=False) == "Slop"         # == slop cutoff


# --- L1.15 type escapes: real detection + regression for the string bug ------

def _escapes(tmp_path, lang, fname, code):
    (tmp_path / fname).write_text(code)
    return indicators._compute_type_escapes(tmp_path, lang)


def test_l1_15_detects_python_any(tmp_path):
    # Two uses. The import names the symbol; it does not opt out of anything, and this
    # assertion read "3 escapes  # import + param + return" until 2026-08-18.
    res = _escapes(tmp_path, "python", "a.py", "from typing import Any\ndef f(x: Any) -> Any:\n    return x\n")
    assert res["details"].startswith("2 escapes")


def test_l1_15_an_import_of_the_escape_token_is_not_an_escape(tmp_path):
    """`from typing import Any` says a symbol is available. It types nothing. Charging it
    put a floor of one under every statically-typed Python file and charged a file that
    imports the name and never uses it."""
    res = _escapes(tmp_path, "python", "a.py", "from typing import Any\nx = 1\n")
    assert res["details"].startswith("0 escapes")


def test_l1_15_quoting_an_annotation_does_not_hide_it(tmp_path):
    """The same cast written two ways is the same code and must carry the same count.
    It did not: the string exclusion dropped the quoted form, so a score moved on
    quotation marks alone. Raised from outside the project against a Jinja seam, where
    `cast("dict[str, Any]", ctx)` is the ordinary way to write it."""
    quoted = _escapes(tmp_path, "python", "a.py",
                      'from typing import Any, cast\nctx = cast("dict[str, Any]", d)\n')
    (tmp_path / "a.py").unlink()
    plain = _escapes(tmp_path, "python", "b.py",
                     "from typing import Any, cast\nctx = cast(dict[str, Any], d)\n")
    assert quoted["details"].startswith("1 escapes")
    assert plain["details"].startswith("1 escapes")


def test_l1_15_an_import_of_the_escape_token_is_not_an_escape_in_java_or_typescript(tmp_path):
    """The same defect, in the two other languages whose grammar names imports. Java's
    `import java.lang.Object` and TypeScript's `import {any}` were each charged one."""
    assert _escapes(tmp_path, "java", "A.java", "import java.lang.Object;\nclass A { }\n"
                    )["details"].startswith("0 escapes")
    (tmp_path / "A.java").unlink()
    assert _escapes(tmp_path, "typescript", "a.ts", 'import {any} from "x";\nconst v = 1;\n'
                    )["details"].startswith("0 escapes")


def test_l1_15_an_object_key_spelled_like_the_token_is_not_an_escape(tmp_path):
    """`{any: 1}` names a field. TypeScript's `any` in key position types nothing."""
    res = _escapes(tmp_path, "typescript", "a.ts", "const o = {any: 1};\n")
    assert res["details"].startswith("0 escapes")


def test_l1_15_string_literal_is_not_a_false_positive(tmp_path):
    # A string that merely contains the ignore-marker must NOT be counted.
    # This is the bug honest testing surfaced: the marker check used to run on
    # every node's text, so this module's own pattern list scored as escapes.
    res = _escapes(tmp_path, "python", "a.py", 'MARKER = "# type: ignore lives here"\nx = 1\n')
    assert res["details"].startswith("0 escapes")


def test_l1_15_counts_ignore_comment(tmp_path):
    res = _escapes(tmp_path, "python", "a.py", "x = 1  # type: ignore\n")
    assert res["details"].startswith("1 escapes")


def test_l1_15_a_type_token_inside_a_string_is_data(tmp_path):
    """`("Any",)` in a pattern table does not opt out of a type checker. The meter used
    to charge itself for its own vocabulary, and would charge any C# repo for every
    string that says "object"."""
    res = _escapes(tmp_path, "python", "a.py", 'PATTERNS = ("Any",)\nLABEL = "Any"\nx = 1\n')
    assert res["details"].startswith("0 escapes")


def test_l1_15_a_comment_explaining_the_marker_is_documentation(tmp_path):
    """A suppression BEGINS with the marker. A comment that mentions it mid-sentence is
    prose about the rule, which is how this meter came to report on its own docstrings."""
    res = _escapes(tmp_path, "python", "a.py",
                   "# the marker is # type: ignore, written at the head of a line\nx = 1\n")
    assert res["details"].startswith("0 escapes")


def test_l1_15_still_counts_a_real_suppression_with_a_code(tmp_path):
    """Tightening to a prefix must not cost a real suppression its count."""
    res = _escapes(tmp_path, "python", "a.py", "x = 1  # type: ignore[attr-defined]\n")
    assert res["details"].startswith("1 escapes")


def test_l1_15_counts_java_suppresswarnings_annotation(tmp_path):
    """Java's suppression marker is an annotation node, not a comment, so the comment
    path never saw it. @Override is an annotation too and is not a type escape."""
    res = _escapes(tmp_path, "java", "A.java",
                   "class A {\n"
                   "    @SuppressWarnings(\"unchecked\")\n"
                   "    @Override\n"
                   "    public void m() {}\n"
                   "}\n")
    assert res["details"].startswith("1 escapes")


def test_l1_15_java_suppression_counts_once_however_many_warnings(tmp_path):
    """One annotation is one decision to opt out, the rule `# type: ignore[a, b]`
    already gets. A scoped annotation names the same marker."""
    res = _escapes(tmp_path, "java", "A.java",
                   "class A {\n"
                   "    @SuppressWarnings({\"unchecked\", \"rawtypes\"})\n"
                   "    void m() {}\n"
                   "    @java.lang.SuppressWarnings(\"unchecked\")\n"
                   "    void n() {}\n"
                   "}\n")
    assert res["details"].startswith("2 escapes")


def test_l1_15_java_comment_mentioning_suppresswarnings_is_documentation(tmp_path):
    """Prose about the marker, and a string holding it, are not suppressions. Moving
    the marker to the annotation table must not reopen the self-reference hole."""
    res = _escapes(tmp_path, "java", "A.java",
                   "class A {\n"
                   "    // use @SuppressWarnings(\"unchecked\") only where the cast is proven\n"
                   "    void m() {\n"
                   "        String s = \"@SuppressWarnings\";\n"
                   "    }\n"
                   "}\n")
    assert res["details"].startswith("0 escapes")


def test_l1_15_the_ratchet_counts_what_the_indicator_counts(tmp_path):
    """The pre-commit gate and L1.15 must count by one rule. They unpacked the
    vocabulary separately, so a vocabulary added to one was invisible to the other."""
    from l1_analyzer import cli

    (tmp_path / "A.java").write_text("class A {\n    @SuppressWarnings(\"unchecked\")\n    void m() {}\n}\n")
    assert cli._count_type_escapes(tmp_path, "java") == 1
    assert indicators._compute_type_escapes(tmp_path, "java")["details"].startswith("1 escapes")


def test_l1_15_typescript_any_and_unknown(tmp_path):
    res = _escapes(tmp_path, "typescript", "a.ts", "let x: any = 1;\nlet y: unknown = 2;\n")
    assert res["details"].startswith("2 escapes")


def test_l1_15_untyped_language_is_na(tmp_path):
    res = _escapes(tmp_path, "ruby", "a.rb", "x = 1\n")
    assert res["band"] == "n/a"


# --- L1.15: the four position helpers, read directly ------------------------
# Every test above reaches these through _compute_type_escapes, which divides the count
# by a line total and publishes a rounded quotient. A helper that is only ever read
# through a quotient can be wrong by one and round clean, and the two defects these
# helpers exist to close were both off-by-one against a single file.


def _py_root(src: str):
    return indicators._get_parser("python").parse(src.encode()).root_node


def _leaves(node):
    if not node.children:
        yield node
    for child in node.children:
        yield from _leaves(child)


def test_in_non_type_position_refuses_the_import_and_keeps_the_annotation():
    """Two `Any` tokens, identical text, one an import and one an annotation. The token
    text cannot separate them; only the position can."""
    root = _py_root("from typing import Any\ndef f(x: Any) -> None:\n    return None\n")
    nonpositions = frozenset(indicators.LANG_CFG["python"]["type_escape_nonpositions"])
    imported, annotated = [n for n in _leaves(root) if indicators._node_text(n) == "Any"]

    assert indicators._in_non_type_position(imported, nonpositions) is True
    assert indicators._in_non_type_position(annotated, nonpositions) is False
    # The rule is a refusal, not an allow-list. A language that declares no non-type
    # position must refuse nothing, because Go and C# leave a bare type sitting in a
    # declaration with no node to key on and an allow-list would stop counting them.
    assert indicators._in_non_type_position(imported, frozenset()) is False


def test_cast_type_strings_reads_the_quoted_type_and_leaves_the_data_table_alone():
    """A quoted type is a type. A quoted word in a tuple is data. The call name is the
    whole of what separates them."""
    root = _py_root(
        "from typing import Any, cast\n"
        'ctx = cast("dict[str, Any]", d)\n'
        "plain = cast(dict[str, Any], d)\n"
        'PATTERNS = ("Any",)\n'
    )
    # The unquoted cast is absent on purpose: the leaf walk already counts it, and
    # returning it here too would charge that line twice.
    assert indicators._cast_type_strings(root, frozenset({"cast"})) == ['"dict[str, Any]"']
    # A language declaring no cast call gets no walk at all, which is what keeps this
    # rule free for Rust, C, Go, JavaScript and Ruby.
    assert indicators._cast_type_strings(root, frozenset()) == []


def test_refs_of_type_collects_every_node_of_one_type_in_document_order():
    """Document order, and a nested match reported as well as the node containing it."""
    root = _py_root("a = outer(inner(1))\nb = second(2)\n")
    found = [indicators._node_text(n) for n in indicators._refs_of_type(root, "call")]

    assert found == ["outer(inner(1))", "inner(1)", "second(2)"]
    # Exact type name, never a prefix and never a near miss. A caller that names the
    # node type a different grammar uses gets an empty list, which is the honest answer:
    # this walker cannot tell "no such construct" from "no such node name", and the
    # caller's language table is what has to be right.
    assert indicators._refs_of_type(root, "cal") == []
    assert indicators._refs_of_type(root, "method_invocation") == []


def test_node_text_decodes_what_it_can_and_never_raises():
    """Every caller compares the result against a vocabulary, so it must be a string."""
    assert indicators._node_text(_py_root('x = "ok"\n')) == 'x = "ok"\n'
    # A source file that is not valid UTF-8 must not stop a scan. The undecodable bytes
    # are dropped rather than replaced, so the text shrinks and never raises.
    ugly = indicators._get_parser("python").parse(b'x = "\xff\xfe"\n').root_node
    assert indicators._node_text(ugly) == 'x = ""\n'
    # A node spanning no bytes reads as the empty string, not None. No caller guards.
    assert indicators._node_text(indicators._get_parser("python").parse(b"").root_node) == ""


# --- L1.15: the thousand-line floor, removed 2026-08-15 ----------------------
# The floor read `if total_loc > 1000 else 0.0`. Under it, every input below a
# thousand production lines reported 0.0 escapes per kLOC and band Healthy
# however many escape hatches it held. That is not an empty-set claim, which
# would be honest; it is a fabricated number over a non-empty input, published
# in the field a reader actually looks at. The threshold has no derivation in
# 03-layer1-indicators.md, in the calibration note, or in any amendment, and
# the canon's bands (<1 / 1-5 / >5 per kLOC) name no minimum denominator.
# The tests below are the four cases the floor got wrong, in order of how badly.

def test_l1_15_a_small_file_of_nothing_but_escapes_is_not_healthy(tmp_path):
    """Twenty lines, twenty escape hatches, and the floor called it Healthy at 0.0.
    A rate is a rate at any denominator: 20 escapes in 20 lines is 1000/kLOC."""
    res = _escapes(tmp_path, "python", "a.py", "v: Any = 1\n" * 20)
    assert res["value"] == 1000.0
    assert res["band"] == "Slop"


def test_l1_15_one_escape_at_file_scope_is_measured(tmp_path):
    """The case that motivated the fix. At per-edit tempo an agent holds one file,
    and under the floor every file below a thousand lines banded Healthy by
    construction, which made L1.15 useless at exactly the scope it was being
    built toward. One escape in 200 lines is 5.0/kLOC, which is Slop, and the
    small denominator makes that reading jumpy rather than wrong."""
    src = "def f(x):\n    return x\n" * 99 + "v: Any = 1\n"   # 199 lines, 1 escape
    res = _escapes(tmp_path, "python", "a.py", src)
    assert res["value"] == 5.03
    assert res["band"] == "Slop"


def test_l1_15_a_clean_small_file_still_reads_healthy(tmp_path):
    """Honest zero is the control. Removing the floor must not turn every small
    input into a finding; a file the analyzer really read and found nothing in
    keeps its Healthy, and it is now earned rather than manufactured."""
    res = _escapes(tmp_path, "python", "a.py", "def f(x: int) -> int:\n    return x\n" * 20)
    assert res["value"] == 0.0
    assert res["band"] == "Healthy"


def test_l1_15_no_production_lines_is_na_not_healthy(tmp_path):
    """The empty-denominator half, and the one the floor shared with L1.16 and
    L1.17. Zero escapes over zero lines is the same 0.0 as zero escapes over a
    thousand, and the band field cannot tell them apart. With no line to divide
    by there is no density, so the indicator refuses instead of publishing one."""
    (tmp_path / "README.md").write_text("nothing here\n")
    res = indicators._compute_type_escapes(tmp_path, "python")
    assert res["value"] == "n/a" and res["band"] == "n/a"
    assert "no production" in res["details"]


# --- L1.16 / L1.17 indicators -----------------------------------------------

def test_l1_16_trailing_whitespace(tmp_path):
    (tmp_path / "a.py").write_text("x = 1  \ny = 2\n")  # one trailing-ws line
    res = indicators._trailing_whitespace(tmp_path)
    assert res["value"] > 0 and res["band"] in ("Healthy", "Not Healthy", "Slop")


def test_l1_17_god_files(tmp_path):
    (tmp_path / "big.py").write_text("x = 1\n" * 1500)
    assert "1/1 files >1k LOC" in indicators._god_files(tmp_path)["details"]
    (tmp_path / "huge.py").write_text("x = 1\n" * 4100)
    assert indicators._god_files(tmp_path)["band"] == "Slop"  # any >4k file forces Slop


# --- L1.18 module-global reference and malformed input ----------------------

def test_l1_18_counts_mutable_module_global_but_not_constant(tmp_path):
    # `counter` (lowercase, reassigned) is mutable module state; `LIMIT`
    # (uppercase) is a constant and must NOT be counted as mutable-state access.
    #
    # The fixture reassigns `counter`, which the comment always claimed and the
    # source never did. Until L1.18 became bound-aware on 2026-08-15 the difference
    # did not show: a binding written once with `0` and never touched again is a
    # constant whose partition has exactly one class, and the finite-testability
    # classifier says so. The old fixture therefore passed on the strength of the
    # name's casing rather than on the mutation it was written to demonstrate.
    (tmp_path / "m.py").write_text(
        "counter = 0\nLIMIT = 100\n"
        "def bump():\n    global counter\n    counter += 1\n    return counter\n"   # mutates -> counted
        "def bounded(x):\n    return x < LIMIT\n"     # reads constant only -> not counted
        "def pure(a, b):\n    return a + b\n"
    )
    res = analyze_mutable_state(tmp_path, "python")
    assert res["details"].startswith("1/3")  # only bump() references mutable state
    assert res["value"] == pytest.approx(33.3, abs=0.1)


def test_l1_18_refuses_on_malformed_source_rather_than_crashing_or_banding(tmp_path):
    """Malformed source enumerates no function, and L1.18 now refuses instead of banding.

    The old name said "does not crash" and the old body proved it by requiring a band, which
    made a crash and a fabricated verdict the only two outcomes on offer. There is a third,
    and it is the correct one: the parser survives the file, no function comes back, and a
    share of zero functions is absent rather than zero. The refusal names the measure, so a
    reader can tell L1.18's ignorance from any other module's.
    """
    (tmp_path / "broken.py").write_bytes(b"\xff\xfe def f( : : :\n\x00 ??? (((")
    with pytest.raises(IncompleteCode, match="L1.18 unbounded mutable state"):
        analyze_mutable_state(tmp_path, "python")


def test_l1_18_refusal_still_does_not_crash_the_boundary(tmp_path):
    """The half of the old name that was worth keeping. A refusal is not a crash: the one
    handler turns it into n/a with the basis printed, and nothing above it sees an
    exception."""
    (tmp_path / "broken.py").write_bytes(b"\xff\xfe def f( : : :\n\x00 ??? (((")
    res = indicators._measure(analyze_mutable_state, tmp_path, "python")
    assert res["value"] == "n/a" and res["band"] == "n/a"
    assert "L1.18 unbounded mutable state" in res["details"]


# --- L1.1-L1.7 git band logic on a crafted history --------------------------

def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _commit(repo, msg):
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg], check=True, capture_output=True)


def test_git_indicators_classify_and_score(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "doc.md").write_text("# doc\nline\n")
    _git(tmp_path, "add", "-A"); _commit(tmp_path, "doc only")
    (tmp_path / "app.py").write_text("def f():\n    return 1\n")
    _git(tmp_path, "add", "-A"); _commit(tmp_path, "code only")
    (tmp_path / "app.py").write_text("def f():\n    return 2\n    # note\n")
    (tmp_path / "doc.md").write_text("# doc\nline\nmore\n")
    _git(tmp_path, "add", "-A"); _commit(tmp_path, "mixed")
    (tmp_path / "app.py").write_text("x = 1\n")  # net-negative, delete-heavy
    _git(tmp_path, "add", "-A"); _commit(tmp_path, "shrink")

    res = compute_git_indicators(tmp_path, None, None)
    # 4 commits: 1 doc-only, 2 code-only, 1 mixed
    assert res["L1.1"]["value"] == 25.0
    assert res["L1.2"]["value"] == 50.0
    assert res["L1.3"]["value"] == 25.0
    assert res["L1.6"]["value"] > 0  # at least one net-negative commit
    for k in ("L1.1", "L1.2", "L1.3", "L1.4", "L1.5", "L1.6", "L1.7", "L1.8"):
        assert res[k]["band"] in ("Healthy", "Not Healthy", "Slop", "n/a")


def test_git_indicators_non_repo_is_na(tmp_path):
    res = compute_git_indicators(tmp_path, None, None)  # not a git repo
    assert res["L1.1"]["band"] == "n/a"


# --- L1.9-L1.11 config presence ---------------------------------------------

def test_config_indicators_present(tmp_path):
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n")
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n")
    res = indicators.compute_config_indicators(tmp_path)
    assert res["L1.9"]["band"] == "Healthy"
    assert res["L1.10"]["value"] == 1
    assert res["L1.11"]["band"] == "Healthy"


def test_config_indicators_absent(tmp_path):
    res = indicators.compute_config_indicators(tmp_path)
    assert res["L1.9"]["band"] == "Slop"
    assert res["L1.11"]["band"] == "Slop"


# --- L1.19 / L1.20 runtime harness happy path (real execution) --------------

def test_l1_19_l1_20_pass_on_a_clean_fixture(tmp_path):
    (tmp_path / "m.py").write_text("def classify(x):\n    if x < 0:\n        return 'n'\n    return 'p'\n")
    (tmp_path / "test_m.py").write_text("from m import classify\ndef test_neg():\n    assert classify(-1) == 'n'\ndef test_pos():\n    assert classify(1) == 'p'\n")
    cov = pytest_trace.decision_space_coverage(tmp_path, "python", 60.0)
    assert cov["value"] == 100.0 and cov["band"] == "Healthy"  # both branches exercised
    det = pytest_trace.test_determinism(tmp_path, "python", 5, 60.0)
    assert det["value"] == "5/5" and det["band"] == "Healthy"


# --- L1.12/13/14 external tools: absence proved by an emptied PATH ----------
# Setting PATH to a directory we own removes the tool from the environment and
# reaches the real refusal path. Nothing here answers for a tool.

def test_external_tools_absent_are_na(tmp_path, monkeypatch):
    bind = tmp_path / "bin"
    bind.mkdir()
    monkeypatch.setenv("PATH", str(bind))  # no jscpd on PATH
    res = indicators._compute_external_indicators(tmp_path, "python")
    assert res["L1.13"]["band"] == "n/a"


def test_a_tool_that_is_absent_is_distinguishable_from_one_that_failed(tmp_path):
    run = indicators._run_external([str(tmp_path / "no-such-binary")], tmp_path)
    assert run["ran"] is False and run["output"] == ""


def test_l1_12_and_l1_14_are_native_and_need_no_tool_on_path(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")   # no vulture, no gitleaks, no anything
    (tmp_path / "app.py").write_text(
        'AWS = "' + "AKIA" + "2E0RTQ4KJ7X9WZ1P" + '"\n\n\ndef orphan():\n    return 1\n')
    res = indicators.compute_source_indicators(
        tmp_path, lang="auto", exec_tests=False, timeout_seconds=5, classify_state_bounds=False)
    assert res["L1.12"]["band"] != "n/a" and res["L1.12"]["value"] > 0
    assert res["L1.14"]["value"] == 1 and res["L1.14"]["band"] == "Not Healthy"


# --- L1.8 / L1.15 / L1.19 remaining branches --------------------------------

def test_l1_8_no_production_files_is_na(tmp_path):
    (tmp_path / "test_only.py").write_text("def test_x():\n    assert True\n")
    assert indicators._test_to_prod_ratio(tmp_path)["band"] == "n/a"


def test_l1_15_density_over_a_kloc_is_slop(tmp_path):
    (tmp_path / "a.py").write_text("v: Any = 1\n" * 1100)  # >1000 LOC, all escapes
    res = indicators._compute_type_escapes(tmp_path, "python")
    assert res["value"] > 0 and res["band"] == "Slop"


def test_l1_19_falls_back_to_static_when_no_tests(tmp_path):
    (tmp_path / "m.py").write_text("def f(x):\n    if x:\n        return 1\n    return 0\n")
    res = indicators._decision_space_l19(tmp_path, "python", exec_tests=True, timeout_seconds=60.0)
    assert res["band"] == "n/a" and "coverage not measured" in res["details"]
    assert isinstance(res["value"], int) and res["value"] >= 1


# --- pytest_trace edge paths (real execution) -------------------------------

def test_l1_19_no_tests_is_na(tmp_path):
    (tmp_path / "m.py").write_text("def f(x):\n    return x\n")
    res = pytest_trace.decision_space_coverage(tmp_path, "python", 60.0)
    assert res["band"] == "n/a" and "no tests" in res["details"]


def test_l1_19_no_branches_is_na(tmp_path):
    (tmp_path / "m.py").write_text("def f():\n    return 1\n")  # straight-line, no branches
    (tmp_path / "test_m.py").write_text("from m import f\ndef test_f():\n    assert f() == 1\n")
    # The contract moved on 2026-08-17: this refuses rather than returning n/a, now that
    # L1.19 routes through `indicators._measure` like every other measure. The reason text is
    # unchanged, and a reader of the report still sees n/a; what changed is that a caller who
    # forgets to check can no longer spell the absence as a value.
    with pytest.raises(IncompleteCode, match="no enumerable decision branches"):
        pytest_trace.decision_space_coverage(tmp_path, "python", 60.0)


def test_l1_19_timeout_is_na(tmp_path):
    (tmp_path / "m.py").write_text("def f(x):\n    return x\n")
    (tmp_path / "test_slow.py").write_text("import time\ndef test_slow():\n    time.sleep(3)\n    assert True\n")
    res = pytest_trace.decision_space_coverage(tmp_path, "python", 0.5)  # far too short
    assert res["band"] == "n/a" and "timed out" in res["details"]


def test_l1_20_no_tests_is_na(tmp_path):
    (tmp_path / "m.py").write_text("def f(x):\n    return x\n")
    assert pytest_trace.test_determinism(tmp_path, "python", 5, 60.0)["band"] == "n/a"


def test_l1_20_not_run_when_exec_disabled(tmp_path):
    res = indicators._test_determinism_l20(tmp_path, "python", exec_tests=False, timeout_seconds=30.0)
    assert res["value"] == "not run" and res["band"] == "n/a"


def test_l1_20_order_dependent_scores_below_five(tmp_path):
    (tmp_path / "test_order.py").write_text("_s = {'x': False}\ndef test_a():\n    _s['x'] = True\ndef test_b():\n    assert _s['x'] is True\n")
    res = pytest_trace.test_determinism(tmp_path, "python", 5, 60.0)
    assert res["value"] != "5/5" and res["band"] in ("Not Healthy", "Slop")


def test_l1_20_timeout_is_na(tmp_path):
    (tmp_path / "test_slow.py").write_text("import time\ndef test_slow():\n    time.sleep(3)\n    assert True\n")
    res = pytest_trace.test_determinism(tmp_path, "python", 5, 0.5)
    assert res["band"] == "n/a" and "timed out" in res["details"]


def test_l1_14_finds_a_planted_secret_rather_than_only_proving_a_clean_tree_clean(tmp_path):
    """The finding case, which is the case the external-tool version never exercised."""
    from l1_analyzer import secret_scan
    (tmp_path / "settings.py").write_text(
        'GITHUB = "' + "ghp_" + "q7Rn2Xk9Lm4Pz8Tv1Bd6Hs3Jw5Ny0Cf8Ge2" + '"\n'
        'SLACK = "' + "xoxb" + "-2847361920-4827361958264-Kj8Nm2Pq7Rt4Vw9Xz1Bc5Df" + '"\n')
    res = secret_scan.analyze(tmp_path, "python")
    assert res["value"] == 2 and res["band"] == "Not Healthy"
    assert {f["rule"] for f in res["findings"]} == {"github-token", "slack-token"}


def test_git_indicators_binary_file_numstat(tmp_path):
    # a binary file yields "-\t-\tpath" numstat, exercising the non-digit branch
    _git(tmp_path, "init", "-q")
    (tmp_path / "data.bin").write_bytes(bytes(range(256)))
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _commit(tmp_path, "add code and binary")
    res = compute_git_indicators(tmp_path, None, None)
    assert res["L1.2"]["band"] in ("Healthy", "Not Healthy", "Slop")


def test_git_indicators_empty_repo_is_na(tmp_path):
    _git(tmp_path, "init", "-q")  # initialized but no commits
    res = compute_git_indicators(tmp_path, None, None)
    assert res["L1.1"]["band"] == "n/a"


def test_git_indicators_bad_path_is_na(tmp_path):
    # git cannot chdir here -> non-zero exit -> the failure branch
    res = compute_git_indicators(tmp_path / "does-not-exist", None, None)
    assert res["L1.1"]["band"] == "n/a" and "git log failed" in res["L1.1"]["details"]


def test_git_indicators_since_bound_is_applied(tmp_path):
    # a past --since keeps the commit; exercises the `if since:` append branch
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _commit(tmp_path, "init")
    res = compute_git_indicators(tmp_path, "2000-01-01", None)
    assert res["L1.1"]["band"] in ("Healthy", "Not Healthy", "Slop")


def test_git_indicators_until_past_leaves_no_commits(tmp_path):
    # a past --until filters out every commit -> the "no commits in range" path
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _commit(tmp_path, "init")
    res = compute_git_indicators(tmp_path, None, "2000-01-01")
    assert res["L1.1"]["band"] == "n/a" and "no commits" in res["L1.1"]["details"]


# --- Rust and C configs (advertised languages, previously untested) ---------

def test_l1_18_rust_static_mut_global_is_detected(tmp_path):
    # A `static mut` global read is mutable-state access; a pure fn is not. The
    # old smoke test only checked the band string and missed that Rust detected
    # nothing at all (0/2). This pins the real discrimination.
    from l1_analyzer.indicators import mutable_function_names
    (tmp_path / "a.rs").write_text(
        "static mut counter: i32 = 0;\n"
        "fn bump() { unsafe { counter += 1; } }\n"
        "fn pure(a: i32, b: i32) -> i32 { a + b }\n"
    )
    assert detect_primary_language(tmp_path) == "rust"
    res = analyze_mutable_state(tmp_path, "rust")
    assert res["value"] == 50.0
    assert res["details"].startswith("1/2") and res["details"].endswith("(rust)")
    assert mutable_function_names(tmp_path, "rust") == ["bump"]


def test_l1_18_rust_receiver_mutation_is_detected(tmp_path):
    # An `impl` method taking `&mut self` and touching `self.field` references
    # external mutable state; a pure associated fn does not.
    from l1_analyzer.indicators import mutable_function_names
    (tmp_path / "a.rs").write_text(
        "struct Counter { count: i32 }\n"
        "impl Counter {\n"
        "    fn increment(&mut self) { self.count += 1; }\n"
        "    fn pure(a: i32, b: i32) -> i32 { a + b }\n"
        "}\n"
    )
    res = analyze_mutable_state(tmp_path, "rust")
    assert res["value"] == 50.0
    assert mutable_function_names(tmp_path, "rust") == ["increment"]


def test_l1_18_rust_const_is_not_mutable_state(tmp_path):
    # `const` and plain `static` are immutable; only `static mut` counts.
    (tmp_path / "a.rs").write_text(
        "const MAX: i32 = 10;\n"
        "fn check(x: i32) -> bool { x < MAX }\n"
    )
    assert analyze_mutable_state(tmp_path, "rust")["value"] == 0.0


def test_l1_18_has_no_boundary_exclusion_a_subject_can_claim(tmp_path):
    # There is no I/O boundary exclusion, and this test is what stops one returning
    # by the door it left by. The exclusion the canon described was implemented as a
    # `honest: boundary` comment a function had to carry, which fired on no repository
    # that had not adopted this project's private marker. Recognising a boundary by
    # analysis needs a per-framework enumeration and cannot be done credibly, so the
    # claim was dropped on 2026-08-15 rather than faked, and the marker went with it:
    # an exclusion a subject opts into is a lever a subject controls, and this
    # instrument's primary consumer is an AI that optimises what it is told to
    # optimise. Both functions below are counted, marker or no marker.
    from l1_analyzer.indicators import mutable_function_names
    (tmp_path / "m.py").write_text(
        "CACHE = []\n"
        "def handler():\n"
        "    # honest: boundary\n"
        "    print(CACHE)\n"
        "    return CACHE[0]\n"
        "def reader(i):\n"
        "    return CACHE[i]\n"      # a variable key leaves CACHE unbounded
    )
    res = analyze_mutable_state(tmp_path, "python")
    assert res["details"].startswith("2/2")          # neither is excluded
    assert sorted(mutable_function_names(tmp_path, "python")) == ["handler", "reader"]


def test_l1_18_analyzer_is_self_clean(tmp_path):
    # Dogfooding: the analyzer's own source passes its own L1.18. Guards the
    # path_cover refactor (its stateful CFG builder used to score 11.7%).
    from pathlib import Path

    from l1_analyzer import indicators
    pkg = Path(indicators.__file__).parent
    assert analyze_mutable_state(pkg, "python")["value"] == 0.0


def test_l1_18_java_interface_method_has_no_body(tmp_path):
    # An abstract interface method has no block, exercising the no-body path.
    (tmp_path / "I.java").write_text(
        "interface I {\n"
        "    int compute(int x);\n"                       # no body
        "    default int twice(int x) { return x * 2; }\n"  # has a body
        "}\n"
    )
    res = analyze_mutable_state(tmp_path, "java")
    assert res["band"] in ("Healthy", "Not Healthy", "Slop")


def test_l1_18_go_receiver_and_plain_function(tmp_path):
    # A method has a receiver; a plain function does not - both receiver paths.
    (tmp_path / "a.go").write_text(
        "package main\n"
        "type Box struct { n int }\n"
        "func (b *Box) Set(v int) { b.n = v }\n"   # receiver -> mutable
        "func Add(a, b int) int { return a + b }\n"  # plain function -> pure
    )
    res = analyze_mutable_state(tmp_path, "go")
    assert res["details"].startswith("1/2")


def test_l1_18_c_config_runs(tmp_path):
    (tmp_path / "a.c").write_text(
        "int g;\n"
        "void touch(void) { g = 1; }\n"
        "int add(int a, int b) { return a + b; }\n"
    )
    assert detect_primary_language(tmp_path) == "c"
    res = analyze_mutable_state(tmp_path, "c")
    assert res["band"] in ("Healthy", "Not Healthy", "Slop")


# --- CLI end to end (exercises cli.main's argument dispatch) ----------------

def test_cli_git_and_config_json(tmp_path, capsys):
    from l1_analyzer import cli
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    _git(tmp_path, "add", "-A")
    _commit(tmp_path, "init")
    rc = cli.main([str(tmp_path), "--indicators", "1,9,10", "--format", "json"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"L1.1"' in out and '"L1.9"' in out


def test_cli_source_indicators_no_exec_text(tmp_path, capsys):
    from l1_analyzer import cli
    (tmp_path / "m.py").write_text("def f(x):\n    if x:\n        return 1\n    return 0\n")
    rc = cli.main([str(tmp_path), "--indicators", "16,17,18,19", "--lang", "python", "--no-exec"])
    assert rc == 0
    out = capsys.readouterr().out
    # The default CLI output is the full Slop Audit report (grade + verdict + audit checks).
    assert "Slop Audit" in out and "finitely testable" in out


def test_cli_all_indicators_auto_lang(tmp_path, capsys):
    from l1_analyzer import cli
    _git(tmp_path, "init", "-q")
    (tmp_path / "m.py").write_text("def f():\n    return 1\n")
    _git(tmp_path, "add", "-A")
    _commit(tmp_path, "init")
    rc = cli.main([str(tmp_path), "--indicators", "all", "--no-exec"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Slop Audit" in out and "(python)" in out  # the report titles with the language


# --- per-language L1.18 (runs and discriminates) ----------------------------

@pytest.mark.parametrize("lang", sorted(LANG_SAMPLES))
def test_l1_18_runs_and_discriminates_per_language(tmp_path, lang):
    fname, code = LANG_SAMPLES[lang]
    (tmp_path / fname).write_text(code)

    assert detect_primary_language(tmp_path) == lang

    res = analyze_mutable_state(tmp_path, lang)
    assert res["band"] in ("Healthy", "Not Healthy", "Slop")
    # exactly one of the two functions touches external mutable state
    assert res["details"].startswith("1/2"), res["details"]
    assert res["value"] == 50.0


# --- L1.8: the .NET and JVM test conventions --------------------------------

from pathlib import Path


def test_l1_8_counts_a_dotted_dotnet_test_project_as_test_code():
    """Newtonsoft.Json reported "0 test / 193720 production LOC", band Slop, for a repo
    with 704 test files. Its tests live in Src/Newtonsoft.Json.Tests, and no arm of the
    predicate knew that shape."""
    assert indicators._is_test_file(Path("Src/Newtonsoft.Json.Tests/Serialization/X.cs"))


def test_l1_8_counts_a_capitalised_test_stem_as_test_code():
    """The .NET and JVM file convention: JsonSerializerTests.cs, SmokeTest.java."""
    assert indicators._is_test_file(Path("src/JsonSerializerTests.cs"))
    assert indicators._is_test_file(Path("src/SmokeTest.java"))
    assert indicators._is_test_file(Path("src/ReaderSpec.scala"))


def test_l1_8_does_not_count_a_word_that_merely_ends_in_test():
    """`Latest.java` ends with "test" once lowercased. The capital in the stem arm is
    what keeps production code out of the numerator."""
    assert not indicators._is_test_file(Path("src/Latest.java"))
    assert not indicators._is_test_file(Path("src/manifest.py"))
    assert not indicators._is_test_file(Path("src/Protest.cs"))


def test_l1_8_ratio_moves_when_the_dotted_project_is_recognised(tmp_path):
    """End to end: a .NET layout now splits into test and production instead of
    reporting every line as production."""
    (tmp_path / "Src" / "Foo").mkdir(parents=True)
    (tmp_path / "Src" / "Foo.Tests").mkdir(parents=True)
    (tmp_path / "Src" / "Foo" / "Widget.cs").write_text("a\nb\nc\n")
    (tmp_path / "Src" / "Foo.Tests" / "WidgetTests.cs").write_text("x\ny\n")
    res = indicators._test_to_prod_ratio(tmp_path)
    assert res["details"] == "2 test / 3 production LOC"


# --- L1.4 and L1.5 over a range that added nothing (slop-audit-9o5) --------------
#
# Found by vacuity.check, the self-audit module nothing in production imports. Both read
# `(x / total_added * 100) if total_added > 0 else 0.0`, and 0.0 with higher_is_better=True
# against thresholds of 25 and 5 lands BELOW 5, so it bands Slop. This is the empty-denominator
# class fixed for L1.16, L1.17, L1.18 and absolute_paths, running the other way: it fabricates
# a bad score rather than a clean one. It matters because L1.5 is one of the four indicators
# that carried the separation in the 2026-08-17 validation run.

def _repo_whose_range_only_deletes(tmp_path):
    """A repository whose measured range contains a commit that adds no line at all.

    Real git, real commits: the first adds a file and the second deletes it, and the range
    starts after the first. A deletion-only range is ordinary in a cleanup or a revert.
    """
    import os
    import subprocess

    def run(*a, when=None):
        env = {**os.environ}
        if when is not None:
            # BOTH dates. `git log --since` filters on the COMMITTER date, and `--date` sets
            # only the author's, so setting one leaves every commit inside every range. The
            # first version of this fixture did exactly that and put both commits in the
            # range, which is why it measured 2 added lines rather than none.
            env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = when
        subprocess.run(["git", *a], cwd=tmp_path, capture_output=True, check=True, env=env)

    run("init", "-q")
    run("config", "user.email", "t@t")
    run("config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\ny = 2\n")
    run("add", "-A")
    run("-c", "commit.gpgsign=false", "commit", "-q", "-m", "add", when="2020-01-01T00:00:00")
    (tmp_path / "a.py").unlink()
    run("add", "-A")
    run("-c", "commit.gpgsign=false", "commit", "-q", "-m", "remove", when="2026-01-01T00:00:00")
    return tmp_path


def test_l1_4_and_l1_5_refuse_over_a_range_that_added_nothing(tmp_path):
    res = indicators.compute_git_indicators(_repo_whose_range_only_deletes(tmp_path), "2025-06-01", None)
    for key in ("L1.4", "L1.5"):
        assert res[key]["band"] == "n/a", f"{key} must not band a share of no lines"
        assert res[key]["value"] == "n/a", f"{key} must not publish a number over nothing"
        assert "INCOMPLETE CODE" in res[key]["details"], f"{key} must say why"


def test_the_other_git_indicators_still_answer_over_the_same_range(tmp_path):
    # The refusal is per indicator. A range with commits still measures everything that
    # divides by the commit count, and only the two that divide by added lines refuse.
    res = indicators.compute_git_indicators(_repo_whose_range_only_deletes(tmp_path), "2025-06-01", None)
    assert res["L1.1"]["band"] != "n/a" and res["L1.6"]["band"] != "n/a"
