"""L1.21: mechanical conformity with the Honest Code principles.

Nineteen principles, nineteen subclauses. The measure is mechanical, and what makes it
worth reading is that it says which clauses it decided.

Fifteen are decidable from a Python syntax tree. Two are questions about a browser and are
not applicable to a Python file at all. One is decidable only in part: a cache is readable,
and whether anyone profiled the query first is not. One is not decidable by anything, ever,
because it is a property of how work is sequenced rather than of code.

A clause nobody could check stays outside the numerator AND the denominator, carrying its
reason. That is the same rule the Silence index follows and it is the whole reason to trust
a conformity number: the score is over the clauses actually decided, so it cannot be raised
by looking away.

The second thing this has to be is FAST. It runs behind a hook on every write, so it parses
one file and runs nineteen pure functions over the tree. Nothing here starts a process,
reads a second file, or asks the network.
"""

import textwrap
import time

import pytest
from l1_analyzer import honest_code

CLEAN = textwrap.dedent('''
    """A module with nothing for any clause to find."""

    BANDS = {"high": 10, "low": 0}


    def band(n: int, table: dict) -> str:
        """Reads a table by subscript and lets an unknown key raise."""
        return "high" if n > table["high"] else "low"
''').lstrip("\n")

DIRTY = textwrap.dedent('''
    SETTINGS = {"timeout": 30}


    class User:
        def __init__(self, email, name):
            self.email = email
            self.name = name


    def send(channel, data, timeout=30):
        if channel == "email":
            return send_email(data)
        elif channel == "sms":
            return send_sms(data)
        elif channel == "push":
            return send_push(data)
        return None
''').lstrip("\n")


# --------------------------------------------------------------------------
# The clause table
# --------------------------------------------------------------------------

def test_there_is_one_clause_per_principle():
    """Nineteen, in the Honest Framework's numbering, so a clause number means one thing
    across every Open Honest artifact."""
    assert [c["code"] for c in honest_code.CLAUSES] == [f"L1.21.{n}" for n in range(1, 20)]


def test_every_clause_names_the_principle_it_measures():
    assert all(c["name"].strip() for c in honest_code.CLAUSES)


def test_every_clause_declares_what_decides_it():
    """Three answers, and the third is the one that makes the number honest."""
    assert {c["decides"] for c in honest_code.CLAUSES} <= {"tree", "partly", "nothing"}


def test_the_strangler_clause_is_the_one_nothing_decides():
    """A property of how work is sequenced over weeks. It is the only clause here excluded
    by its nature rather than by the reach of this reader."""
    undecidable = [c for c in honest_code.CLAUSES if c["decides"] == "nothing"]
    assert [c["code"] for c in undecidable] == ["L1.21.17"]


def test_the_browser_clauses_name_the_languages_they_apply_to():
    for code in ("L1.21.6", "L1.21.7"):
        clause = next(c for c in honest_code.CLAUSES if c["code"] == code)
        assert "python" not in clause["languages"]
        assert "javascript" in clause["languages"]


# --------------------------------------------------------------------------
# Reading one file
# --------------------------------------------------------------------------

def test_a_file_that_does_not_parse_is_unreadable_rather_than_clean(tmp_path):
    """A file nobody could read is not a file with no violations. Reporting it clean is
    exactly the failure this whole instrument is built to name."""
    (tmp_path / "broken.py").write_text("def f(\n")
    source = honest_code.read_source(tmp_path / "broken.py")
    assert source["readable"] is False
    assert source["unreadable_reason"].strip()


def test_an_unreadable_file_has_no_conformity(tmp_path):
    (tmp_path / "broken.py").write_text("def f(\n")
    assessment = honest_code.assess_file(tmp_path / "broken.py")
    assert assessment["conformity"] is None
    assert assessment["band"] == "n/a"


def test_the_language_is_read_from_the_suffix(tmp_path):
    (tmp_path / "app.js").write_text("const x = 1;\n")
    assert honest_code.read_source(tmp_path / "app.js")["language"] == "javascript"


# --------------------------------------------------------------------------
# Which clauses ran
# --------------------------------------------------------------------------

def test_a_clause_for_another_language_does_not_apply():
    source = honest_code.read_source_text(CLEAN, "m.py")
    browser = next(c for c in honest_code.CLAUSES if c["code"] == "L1.21.6")
    assert honest_code.applies_to(browser, source) is False


def test_a_clause_for_this_language_applies():
    source = honest_code.read_source_text(CLEAN, "m.py")
    first = honest_code.CLAUSES[0]
    assert honest_code.applies_to(first, source) is True


def test_every_clause_reports_whether_it_was_decided():
    assessed = honest_code.assess(honest_code.read_source_text(CLEAN, "m.py"))
    assert len(assessed) == 19
    assert all(c["decided"] in (True, False) for c in assessed)


def test_a_clause_that_could_not_be_decided_carries_its_reason():
    assessed = honest_code.assess(honest_code.read_source_text(CLEAN, "m.py"))
    undecided = [c for c in assessed if not c["decided"]]
    assert undecided
    assert all(c["reason"].strip() for c in undecided), undecided


def test_a_clause_that_could_not_be_decided_never_carries_findings():
    """Not applicable and not decidable are both silence. A finding under either would be a
    claim about something nobody read."""
    assessed = honest_code.assess(honest_code.read_source_text(CLEAN, "m.py"))
    assert all(c["findings"] == [] for c in assessed if not c["decided"])


# --------------------------------------------------------------------------
# The score
# --------------------------------------------------------------------------

def test_a_clean_file_conforms_on_every_clause_that_was_decided():
    assessment = honest_code.assess_file_text(CLEAN, "m.py")
    assert assessment["conformity"] == 100.0, [
        (c["code"], c["findings"]) for c in assessment["clauses"] if c["findings"]]


def test_a_dirty_file_scores_below_a_clean_one():
    dirty = honest_code.assess_file_text(DIRTY, "m.py")
    assert dirty["conformity"] < 100.0
    assert {f["clause"] for c in dirty["clauses"] for f in c["findings"]} >= {
        "L1.21.1", "L1.21.2", "L1.21.14"}


def test_only_decided_clauses_are_in_the_denominator():
    """The whole reason to trust the number. A clause nobody could check cannot raise the
    score by counting as a pass, and cannot lower it by counting as a failure."""
    assessment = honest_code.assess_file_text(CLEAN, "m.py")
    decided = [c for c in assessment["clauses"] if c["decided"]]
    assert assessment["decided_clauses"] == len(decided)
    assert assessment["decided_clauses"] < 19, "something undecidable was counted as decided"


def test_a_file_where_nothing_could_be_decided_has_no_conformity():
    """A share of nothing is not a hundred percent."""
    assert honest_code.conformity([]) is None
    assert honest_code.conformity([{"decided": False, "findings": []}]) is None


def test_the_share_is_of_clauses_that_hold_rather_than_of_findings():
    """One clause with nine findings is one clause. Counting findings would let a single
    noisy rule swamp the other eighteen."""
    clauses = [{"decided": True, "findings": [1, 2, 3, 4, 5, 6, 7, 8, 9]},
               {"decided": True, "findings": []},
               {"decided": True, "findings": []},
               {"decided": True, "findings": []}]
    assert honest_code.conformity(clauses) == 75.0


@pytest.mark.parametrize(("share", "band"), [
    (100.0, "Healthy"), (95.0, "Healthy"), (80.0, "Not Healthy"), (50.0, "Slop"),
])
def test_a_share_lands_in_the_panel_s_own_bands(share, band):
    assert honest_code.band_of(share) == band


def test_an_absent_share_is_not_the_worst_band():
    """Unmeasured is not the same as bad, and this instrument says so everywhere else."""
    assert honest_code.band_of(None) == "n/a"


# --------------------------------------------------------------------------
# What a reader sees
# --------------------------------------------------------------------------

def test_the_report_names_every_clause_with_its_number():
    printed = honest_code.report(honest_code.assess_file_text(DIRTY, "m.py"))
    assert "L1.21.1" in printed and "L1.21.19" in printed


def test_the_report_lists_the_undecided_clauses_apart_from_the_score():
    printed = honest_code.report(honest_code.assess_file_text(CLEAN, "m.py"))
    assert "L1.21.17" in printed
    assert "not decided" in printed.lower()


def test_the_report_says_which_half_of_a_partly_decided_clause_it_read():
    printed = honest_code.report(honest_code.assess_file_text(
        "from functools import lru_cache\n\n\n@lru_cache\ndef p(s):\n    return q(s)\n", "m.py"))
    assert "L1.21.9" in printed
    assert "profil" in printed.lower()


# --------------------------------------------------------------------------
# The hook
# --------------------------------------------------------------------------

def test_the_hook_report_locates_each_finding_in_one_readable_line():
    """A hook that fires on every write has to be read in a glance. The locator line is
    what carries that, and the instruction below it is allowed to be as long as acting on
    it requires: welding the two into one line makes neither readable."""
    lines = honest_code.hook_report(honest_code.assess_file_text(DIRTY, "m.py")).split("\n")
    locators = [line for line in lines if not line.startswith("    ")]
    assert locators
    assert all(len(line) < 120 for line in locators), locators
    assert all("m.py:" in line for line in locators)


def test_every_located_finding_carries_the_instruction_under_it():
    lines = honest_code.hook_report(honest_code.assess_file_text(DIRTY, "m.py")).split("\n")
    assert len(lines) % 2 == 0
    assert all(line.startswith("    instead: ") for line in lines[1::2]), lines


def test_the_hook_report_names_the_file_the_line_and_the_clause():
    printed = honest_code.hook_report(honest_code.assess_file_text(DIRTY, "m.py"))
    assert "m.py:" in printed
    assert "L1.21." in printed


def test_the_hook_report_says_what_to_do_instead():
    """A finding an agent cannot act on is noise arriving on every keystroke."""
    printed = honest_code.hook_report(honest_code.assess_file_text(DIRTY, "m.py"))
    assert "instead" in printed.lower() or "->" in printed


def test_a_clean_file_says_nothing_at_all():
    """Silence is the correct output on a clean write. A hook that congratulates the agent
    on every file teaches it to skip the output."""
    assert honest_code.hook_report(honest_code.assess_file_text(CLEAN, "m.py")) == ""


def test_the_assessment_of_one_file_is_fast_enough_for_a_hook():
    """It runs on every write. Nothing here starts a process, reads a second file or asks
    the network, and the budget is the thing that keeps it that way."""
    started = time.perf_counter()
    for _ in range(20):
        honest_code.assess_file_text(DIRTY, "m.py")
    each = (time.perf_counter() - started) / 20
    assert each < 0.05, f"{each:.3f}s per file is too slow to sit behind a write hook"


# --------------------------------------------------------------------------
# The panel entry
# --------------------------------------------------------------------------

def test_the_repository_measure_carries_the_share_the_band_and_the_undecided(tmp_path):
    (tmp_path / "clean.py").write_text(CLEAN)
    (tmp_path / "dirty.py").write_text(DIRTY)
    result = honest_code.analyze(tmp_path, "python")
    assert result["band"] in ("Healthy", "Not Healthy", "Slop")
    assert isinstance(result["value"], float)
    assert "L1.21.17" in result["details"]


def test_a_repository_with_no_readable_file_is_not_clean(tmp_path):
    result = honest_code.analyze(tmp_path, "python")
    assert result["band"] == "n/a"
    assert result["value"] == "n/a"


def test_a_clause_is_broken_for_the_repository_if_any_file_breaks_it(tmp_path):
    (tmp_path / "clean.py").write_text(CLEAN)
    (tmp_path / "dirty.py").write_text(DIRTY)
    result = honest_code.analyze(tmp_path, "python")
    assert result["value"] < 100.0


# --------------------------------------------------------------------------
# Which files each clause is measured over
# --------------------------------------------------------------------------

def test_the_two_test_scoped_clauses_are_decided_over_the_test_files(tmp_path):
    """Clauses 10 and 15 are ABOUT tests: how many mocks one carries, how much setup a step
    needs. Measuring only production files left both permanently undecided, so two of the
    nineteen were never checked in any full audit and the share said so without anyone
    reading the sentence."""
    (tmp_path / "m.py").write_text(CLEAN)
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_m.py").write_text(
        "def test_order():\n    a = Mock()\n    b = MagicMock()\n    c = Mock()\n"
        "    assert place(a, b, c)\n")
    result = honest_code.analyze(tmp_path, "python")
    assert "L1.21.10" not in result["undecided"], result["details"]
    assert any(f["clause"] == "L1.21.10" for f in result["findings"])


def test_a_production_clause_is_not_measured_over_a_test_file(tmp_path):
    """A test file with an if/elif chain is not a production concern, and counting it would
    make the score about the suite rather than about the code."""
    (tmp_path / "m.py").write_text(CLEAN)
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_m.py").write_text(
        "def test_it():\n"
        "    if k == 'a':\n        one()\n"
        "    elif k == 'b':\n        two()\n"
        "    elif k == 'c':\n        three()\n")
    result = honest_code.analyze(tmp_path, "python")
    assert not any(f["clause"] == "L1.21.1" for f in result["findings"]), result["findings"]


def test_a_repository_finding_names_the_file_it_is_in(tmp_path):
    """A line number with no file is not a finding anyone can act on. The per-file path
    knows which file it read; the repository path flattened the findings and dropped it."""
    (tmp_path / "dirty.py").write_text(DIRTY)
    result = honest_code.analyze(tmp_path, "python")
    assert result["findings"]
    assert all(f["file"].endswith("dirty.py") for f in result["findings"]), result["findings"]


def test_a_single_file_finding_names_its_file_too():
    """One shape for a finding, wherever it came from, so a caller reading both does not
    have to know which produced it."""
    assessment = honest_code.assess_file_text(DIRTY, "m.py")
    located = [f for c in assessment["clauses"] for f in c["findings"]]
    assert located
    assert all(f["file"] == "m.py" for f in located)


# --------------------------------------------------------------------------
# Exceptions the author declares, with reasons
# --------------------------------------------------------------------------

SWALLOW = ("def f(x):\n    try:\n        return g(x)\n"
           "    except ValueError:\n        return None\n")

ALLOWED = ("def f(x):\n    try:\n        return g(x)\n"
           "    # honest-code-allow: L1.21.8 — a body that will not parse asserts nothing\n"
           "    except ValueError:\n        return None\n")


def test_an_undeclared_swallow_is_a_violation():
    assessed = honest_code.assess(honest_code.read_source_text(SWALLOW, "m.py"))
    clause = next(c for c in assessed if c["code"] == "L1.21.8")
    assert clause["findings"]


def test_a_declared_exception_is_not_counted_as_a_violation():
    """Four handlers in this tool are correct as written and argued at the site. Leaving
    them as permanent findings would train a reader to skip the clause, and skipping a
    clause is how the one that matters gets skipped too."""
    assessed = honest_code.assess(honest_code.read_source_text(ALLOWED, "m.py"))
    clause = next(c for c in assessed if c["code"] == "L1.21.8")
    assert clause["findings"] == []


def test_a_declared_exception_is_still_reported_where_a_reader_can_audit_it():
    """Never dropped. An exception nobody can see is indistinguishable from a rule nobody
    checked, which is the thing this instrument is built to name."""
    assessed = honest_code.assess(honest_code.read_source_text(ALLOWED, "m.py"))
    clause = next(c for c in assessed if c["code"] == "L1.21.8")
    assert len(clause["allowed"]) == 1
    assert "will not parse" in clause["allowed"][0]["reason"]


def test_an_allowance_with_no_reason_is_not_honoured():
    """A suppression nobody justified is the silent skip this whole instrument exists to
    name. It has to cost the author a sentence."""
    text = SWALLOW.replace("    except ValueError:",
                           "    # honest-code-allow: L1.21.8\n    except ValueError:")
    assessed = honest_code.assess(honest_code.read_source_text(text, "m.py"))
    clause = next(c for c in assessed if c["code"] == "L1.21.8")
    assert clause["findings"], "a bare suppression silenced the clause"


def test_an_allowance_for_a_different_clause_does_not_apply():
    text = SWALLOW.replace("    except ValueError:",
                           "    # honest-code-allow: L1.21.1 — a reason for another clause\n"
                           "    except ValueError:")
    assessed = honest_code.assess(honest_code.read_source_text(text, "m.py"))
    clause = next(c for c in assessed if c["code"] == "L1.21.8")
    assert clause["findings"]


def test_the_report_names_the_declared_exceptions_and_their_reasons():
    printed = honest_code.report(honest_code.assess_file_text(ALLOWED, "m.py"))
    assert "declared" in printed.lower()
    assert "will not parse" in printed


def test_the_repository_measure_counts_the_declared_exceptions(tmp_path):
    (tmp_path / "allowed.py").write_text(ALLOWED)
    result = honest_code.analyze(tmp_path, "python")
    assert result["allowed"]
    assert "Declared exceptions: 1" in result["details"]


def test_the_repository_measure_states_the_exception_count_even_at_zero(tmp_path):
    """Stated with no conditional anywhere in the sentence. Writing the clause only when
    there were some published an empty string into `details`; spelling the plural with a
    conditional then published a bare "s" the same way. A reader cannot tell "none
    declared" from "this run does not report them"."""
    (tmp_path / "clean.py").write_text(CLEAN)
    assert "Declared exceptions: 0" in honest_code.analyze(tmp_path, "python")["details"]


def test_a_clause_with_only_declared_exceptions_holds(tmp_path):
    """The author stated a reason and a reader can read it. That is a different fact from
    a clause nobody checked, and the share treats it as decided and holding."""
    (tmp_path / "allowed.py").write_text(ALLOWED)
    result = honest_code.analyze(tmp_path, "python")
    assert not any(f["clause"] == "L1.21.8" for f in result["findings"])
