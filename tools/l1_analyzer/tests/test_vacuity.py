"""The vacuity check must find the shape without naming an instance, and must have no
way to say anything good.

Two things are under test and they pull in opposite directions. The first is the rule:
one predicate over the AST - a branch an empty input takes, publishing a constant that
is not a refusal - has to find the paths that were found by hand, and has to stay quiet
on the ones that were fixed. A check that convicted the fixes as well as the defects
would have a hit rate and no discrimination.

The second is the shape of the output, and it is the reason this module exists at all.
Every instance the rule looks for is a positive claim manufactured from an empty input.
A checker that can make a positive claim can manufacture one the same way, and would
then certify itself. So this one has no band, no verdict and no pass: zero findings
renders as a negation carrying its own reach, and the tests below hold that door shut
rather than trusting the author to remember. `test_the_check_convicts_itself` is the
proof that the door is load-bearing: it feeds the check a copy of a checker that emits
a band, and requires the finding.
"""

import ast
import pathlib

import pytest
from l1_analyzer import vacuity

PKG = pathlib.Path(vacuity.__file__).parent


def _scan(src: str) -> list[dict]:
    """Findings in one snippet, parsed as a module named `m.py`."""
    return vacuity.scan_module(ast.parse(src), pathlib.Path("m.py"), src.splitlines())


# --- the rule: what an empty input publishes -----------------------------------------

def test_a_zero_denominator_guard_publishing_a_number_is_a_finding():
    """The shape, in its plainest spelling. `total` at zero takes the else, and 0.0 is
    published as a measurement of a tree the check never measured."""
    found = _scan(
        "def f(files):\n"
        "    total = 0\n"
        "    for x in files:\n"
        "        total += 1\n"
        "    pct = (3 / total * 100) if total > 0 else 0.0\n"
        "    return {'value': pct}\n")
    assert len(found) == 1
    assert found[0]["field"] == "value" and found[0]["constant"] == "0.0"


def test_a_threshold_guard_is_the_same_finding_as_a_zero_guard():
    """`if total > 1000 else 0.0` is not a different rule. Substituting zero and
    evaluating the test decides the branch, and a floor above zero only widens the set
    of inputs that reach the constant."""
    found = _scan(
        "def f(files):\n"
        "    loc = 0\n"
        "    for x in files:\n"
        "        loc += 1\n"
        "    d = (7 / loc) if loc > 1000 else 0.0\n"
        "    return {'value': d}\n")
    assert len(found) == 1


def test_an_emptiness_test_selecting_a_verdict_token_is_a_finding():
    found = _scan(
        "def f(files):\n"
        "    hits = [x for x in files if x]\n"
        "    return {'band': 'Healthy' if len(hits) == 0 else 'Slop'}\n")
    assert len(found) == 1 and found[0]["constant"] == "'Healthy'"


def test_a_guard_chain_falls_through_to_the_empty_case():
    """No `else` anywhere. Every guard is a not-empty test, so the final return is the
    branch an empty input takes, and it publishes an affirmative token."""
    found = _scan(
        "def _status(counts):\n"
        "    if counts['bad'] > 0:\n"
        "        return 'cannot'\n"
        "    if counts['unknown'] > 0:\n"
        "        return 'might'\n"
        "    return 'can'\n"
        "def f(counts):\n"
        "    return {'status': _status(counts)}\n")
    assert len(found) == 1 and found[0]["field"] == "status"


def test_an_exception_handler_is_a_did_not_measure_branch():
    """The wrapper that swallowed a non-zero exit to an empty string. The count over
    that string is zero, and zero findings from a scan that never ran reads clean."""
    found = _scan(
        "def _run(cmd):\n"
        "    try:\n"
        "        return check_output(cmd)\n"
        "    except OSError:\n"
        "        return ''\n"
        "def f(cmd):\n"
        "    out = _run(cmd)\n"
        "    hits = out.count('x')\n"
        "    return {'value': hits}\n")
    assert len(found) == 1 and found[0]["rule"] == "handler"


def test_a_nested_conditional_does_not_hide_the_guard():
    """The outer test is about a string and decides nothing; the inner one is the guard.
    Descending into both arms of an undecidable test is what keeps this one rule."""
    found = _scan(
        "def f(counts, status):\n"
        "    total = sum(counts.values())\n"
        "    pct = None if status == 'na' else (100 if total == 0 else 7 / total)\n"
        "    return {'testable_pct': pct}\n")
    assert len(found) == 1 and found[0]["constant"] == "100"


# --- the cuts: what the rule must NOT convict ----------------------------------------

def test_a_refusal_on_the_empty_branch_is_not_a_finding():
    """The fix, and the control for the whole rule. If the check convicted this it would
    convict every repair as loudly as every defect and discriminate nothing."""
    found = _scan(
        "def f(files):\n"
        "    total = 0\n"
        "    for x in files:\n"
        "        total += 1\n"
        "    pct = (3 / total * 100) if total > 0 else 'n/a'\n"
        "    return {'value': pct}\n")
    assert found == []


def test_a_refusal_returned_before_the_guard_chain_cuts_the_path():
    """The other spelling of the same fix: refuse early and return. The constant below
    is then unreachable on an empty input, so it is not a vacuous path."""
    found = _scan(
        "def f(files):\n"
        "    n = len(files)\n"
        "    if n == 0:\n"
        "        return {'band': 'n/a'}\n"
        "    return {'band': 'Healthy' if n < 5 else 'Slop'}\n")
    assert found == []


def test_a_refusal_helper_cuts_the_path_the_same_way_a_literal_does():
    """Repositories spell the refusal as a helper. A call whose every returned field is
    a refusal is a refusal, decided from the callee rather than from its name."""
    found = _scan(
        "def _na(reason):\n"
        "    return {'value': 'n/a', 'band': 'n/a', 'details': reason}\n"
        "def f(branches):\n"
        "    n = len(branches)\n"
        "    if n == 0:\n"
        "        return _na('nothing to measure')\n"
        "    return {'band': 'Healthy' if n > 90 else 'Slop'}\n")
    assert found == []


def test_a_compound_guard_is_read_whole():
    """A refusal reached only when two conditions hold together still cuts the path.
    Reading `and` as undecidable would report every repaired check as unrepaired."""
    found = _scan(
        "def f(files, findings):\n"
        "    parsed = len(files)\n"
        "    if parsed == 0 and not findings:\n"
        "        return {'verdict': 'n/a'}\n"
        "    return {'verdict': 'clean' if not findings else 'exposed'}\n")
    assert found == []


def test_a_status_code_is_not_a_cardinality():
    """`returncode == 0` compares against zero and is not an emptiness test: a process
    that ran and succeeded returns zero too. The quantity has to be a size, decided from
    how it is built, or every comparison against zero in the tree becomes a finding."""
    found = _scan(
        "def f(run):\n"
        "    return {'value': 'passed' if run.returncode == 0 else 'failed'}\n")
    assert found == []


def test_prose_is_out_of_reach_and_not_a_finding():
    """A sentence cannot be told from a refusal mechanically, and guessing would put a
    word list at the centre of the rule. The check declines the field and says so in its
    reach rather than convicting or clearing it."""
    found = _scan(
        "def f(files):\n"
        "    n = len(files)\n"
        "    return {'details': 'no findings at all' if n == 0 else 'some findings'}\n")
    assert found == []


def test_a_container_filled_under_a_guard_is_not_a_published_constant():
    """Counting into a dict is not publishing a constant: an empty tally asserts
    nothing. Propagating vacuity through a subscript write conflated the two."""
    found = _scan(
        "def f(paths):\n"
        "    counts = {}\n"
        "    for p in paths:\n"
        "        counts[p] = counts.get(p, 0) + 1\n"
        "    return {'counts': counts}\n")
    assert found == []


# --- rule four: it has no way to say anything good -----------------------------------

def test_the_result_carries_no_band_and_no_verdict():
    """The whole poka-yoke. A field that can hold Healthy is a field that can hold a
    fabricated Healthy, and this check would then be its own first finding."""
    result = vacuity.check(PKG)
    assert "band" not in result and "verdict" not in result and "value" not in result
    assert set(result) == {"findings", "reach"}


def test_zero_findings_renders_as_a_negation_carrying_its_reach():
    """Not a pass. The numbers are the disclosure: a reader who wants to know what the
    silence is worth can see how much was looked at."""
    text = vacuity.render({"findings": [],
                           "reach": {"rules": 8, "emission_points": 40, "files_read": 12,
                                     "files_unparsed": 0, "languages_read": 1,
                                     "languages_total": 9, "fields_declined": 3}})
    assert text.startswith("no vacuous path found")
    assert "8 rules" in text and "40 emission points" in text and "1 of 9 languages" in text
    for good in ("Healthy", "clean", "pass", "PASS", "OK"):
        assert good not in text


def test_every_finding_is_a_withdrawal_and_not_a_fault():
    text = vacuity.render({
        "findings": [{"file": "a.py", "function": "f", "field": "band", "line": 3,
                      "guard": "x if n > 0 else 0.0", "constant": "0.0", "rule": "threshold"}],
        "reach": {"rules": 8, "emission_points": 1, "files_read": 1, "files_unparsed": 0,
                  "languages_read": 1, "languages_total": 9, "fields_declined": 0}})
    assert "cannot be relied on when the input is empty" in text
    assert "wrong" not in text and "fail" not in text


def test_the_check_convicts_itself():
    """Rule four, executable. A copy of this check that emits a band is fed to this
    check, and must come back as a finding. If it did not, the apophatic form would be
    a claim about the author's care rather than a property of the code."""
    found = _scan(
        "def check(root):\n"
        "    paths = [p for p in root]\n"
        "    return {'band': 'Healthy' if len(paths) == 0 else 'Slop',\n"
        "            'findings': paths}\n")
    assert len(found) == 1, "a checker that can emit a band is its own first finding"


def test_the_check_does_not_convict_itself_as_written():
    """The other half. Its own source must hold no vacuous path, and the way it manages
    that is by having no affirmative field to publish, not by being careful."""
    src = (PKG / "vacuity.py").read_text(encoding="utf8")
    found = vacuity.scan_module(ast.parse(src), PKG / "vacuity.py", src.splitlines())
    assert found == [], f"the check convicts itself: {found}"


# --- reach: the eight languages it refuses -------------------------------------------

def test_it_reads_python_only_and_says_so():
    """Eight of the nine grammars are read by tree-sitter, which reports node types and
    not the emptiness semantics this rule evaluates. Publishing over them would be the
    check's own recognition set standing in for the code."""
    result = vacuity.check(PKG)
    assert result["reach"]["languages_read"] == 1
    assert result["reach"]["languages_total"] == 9


@pytest.mark.parametrize("lang", ["rust", "go", "java", "csharp", "c", "ruby",
                                  "javascript", "typescript"])
def test_the_refused_languages_are_named_rather_than_skipped(lang):
    assert lang in vacuity.REFUSED


# --- the labelled set, pinned so a regression is visible ------------------------------

def test_two_of_the_three_labelled_paths_are_gone_and_the_third_is_a_reach_limit():
    """The live labelled set from test_read_nothing.py, after the 2026-08-16 repair.

    L1.16 and L1.17 are gone, and the checker is what says so. Both divided by a file count
    and substituted 0.0; both now hand the division to `incomplete.ratio`, which leaves no
    branch for an empty input to take, so the rule finds no path rather than being told
    there is none. L1.18's path in `mutable_state.analyze_mutable_state` left the same way
    on the same day, and it is asserted absent here beside the other two.

    `absolute_paths.scan` is still found, and it is the more useful of the two results
    because the reason is a limit of this rule and not of the repair. The repair spells its
    refusal `raise incomplete.refuse(...)`, and `_refuses` reads only `ast.Return`, so the
    raise does not cut the path and the `count == 0` guard below it still reads as
    reachable on an empty input. The finding is therefore a false one today. It is asserted
    rather than excused, so that teaching `_refuses` to read a raise fails this test and
    makes someone move the name out of the survivor list.
    """
    result = vacuity.check(PKG)
    hit = {(pathlib.Path(f["file"]).name, f["function"]) for f in result["findings"]}
    for gone in (("indicators.py", "_trailing_whitespace"),       # L1.16
                 ("indicators.py", "_god_files"),                 # L1.17
                 ("mutable_state.py", "analyze_mutable_state")):  # L1.18
        assert gone not in hit, f"the rule still finds {gone}, so the repair did not cut it"
    assert ("absolute_paths.py", "scan") in hit, (
        "the raise-shaped refusal now cuts this path, so move it out of the survivor list")


def test_the_rule_does_not_yet_read_a_raise_as_a_refusal():
    """The reason `absolute_paths.scan` survives above, stated as behaviour rather than as
    a comment. `_refuses` accepts a returned refusal and not a raised one, so the same
    repair spelled two ways gets two answers. The `return` spelling is the control: it cuts
    the path, which is what makes this a gap in the rule rather than a fact about the
    guard below it."""
    raised = _scan(
        "def f(files):\n"
        "    if not files:\n"
        "        raise Incomplete('nothing was read')\n"
        "    return {'band': 'Healthy' if len(files) == 0 else 'Slop'}\n")
    returned = _scan(
        "def f(files):\n"
        "    if not files:\n"
        "        return {'band': 'n/a'}\n"
        "    return {'band': 'Healthy' if len(files) == 0 else 'Slop'}\n")
    assert returned == []
    assert len(raised) == 1, "the rule learned to read a raise; fix the survivor list above"


def test_the_l1_15_path_is_gone_and_the_checker_is_what_says_so():
    """It was four until 2026-08-15. L1.15's `if total_loc > 1000 else 0.0` was the
    headline instance in this module's own docstring, and removing the floor removed the
    path. This assertion is the one that matters about the fix: the check that found the
    defect without being told where it was is the check that now reports it absent, so the
    evidence is independent of the test that drove the change.

    The refusal it was replaced with is not a second instance. `total_loc == 0` returns
    band `n/a`, and a refusal is what the rule looks for on that branch; a fix that kept
    publishing a verdict over nothing would still be found here."""
    result = vacuity.check(PKG)
    hit = {(pathlib.Path(f["file"]).name, f["function"]) for f in result["findings"]}
    assert ("indicators.py", "_compute_type_escapes") not in hit


def test_a_boolean_flag_parameter_is_not_a_cardinality():
    """`if higher_is_better:` looks exactly like `if total:` in the tree, and reading the
    flag as a tally made the shared banding helper itself a vacuous path - which then put
    a finding on every indicator that calls it. The evidence is arithmetic or indexing,
    not the bare truth test."""
    found = _scan(
        "def band(value, healthy, higher_is_better):\n"
        "    if higher_is_better:\n"
        "        return 'Healthy' if value >= healthy else 'Slop'\n"
        "    return 'Healthy' if value < healthy else 'Slop'\n"
        "def f(n):\n"
        "    return {'band': band(n, 5, True)}\n")
    assert found == []


def test_a_count_passed_in_as_a_parameter_is_a_cardinality():
    """The other side of the same line. This one is never indexed either, but it is
    divided by, and a parameter the body does arithmetic with is a size."""
    found = _scan(
        "def summary(items, total):\n"
        "    return {'fraction': round(len(items) / total, 3) if total else 0.0}\n")
    assert len(found) == 1 and found[0]["field"] == "fraction"
